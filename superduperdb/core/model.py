import multiprocessing
from dask.distributed import Future
import inspect
import dataclasses as dc
import typing as t

from pinnacledb.core.dataset import Dataset
from pinnacledb.core.job import Job, ComponentJob
from pinnacledb.core.metric import Metric
from pinnacledb.core.artifact import Artifact
from pinnacledb.core.component import Component
from pinnacledb.core.encoder import Encoder
from pinnacledb.core.serializable import Serializable
from pinnacledb.datalayer.base.query import Select
from pinnacledb.misc.special_dicts import MongoStyleDict


EncoderArg = t.Union[Encoder, str, None]
ObjectsArg = t.Sequence[t.Union[t.Any, Artifact]]
DataArg = t.Optional[t.Union[str, t.Sequence[str]]]


def TrainingConfiguration(
    identifier: str,
    **kwargs,
):
    return _TrainingConfiguration(identifier=identifier, kwargs=kwargs)


@dc.dataclass
class _TrainingConfiguration(Component):
    """
    Training configuration object, containing all settings necessary for a particular
    learning-task use-case to be serialized and initiated. The object is ``callable``
    and returns a class which may be invoked to apply training.

    :param identifier: Unique identifier of configuration
    :param **parameters: Key-values pairs, the variables which configure training.
    """

    variety: t.ClassVar[str] = 'training_configuration'

    identifier: str
    kwargs: t.Optional[t.Dict] = None
    version: t.Optional[int] = None

    def get(self, k, default=None):
        try:
            return getattr(self, k)
        except AttributeError:
            return self.kwargs.get(k, default=default)


class PredictMixin:
    # ruff: noqa: F821

    def _predict_one(self, X, **kwargs):
        if self.preprocess is not None:
            X = self.preprocess.artifact(X)
        output = self.to_call(X, **kwargs)
        if self.postprocess is not None:
            output = self.postprocess.artifact(output)
        return output

    def _forward(self, X, num_workers=0):
        if self.batch_predict:
            return self.to_call(X)

        outputs = []
        if num_workers:
            pool = multiprocessing.Pool(processes=num_workers)
            for r in pool.map(self.to_call, X):
                outputs.append(r)
            pool.close()
            pool.join()
        else:
            for r in X:
                outputs.append(self.to_call(r))
        return outputs

    def _predict(self, X, one: bool = False, **predict_kwargs):
        if one:
            return self._predict_one(X)
        if self.preprocess is not None:
            X = list(map(self.preprocess.artifact, X))
        if self.collate_fn is not None:
            X = self.collate_fn(X)
        outputs = self._forward(X, **predict_kwargs)
        if self.postprocess is not None:
            outputs = list(map(self.postprocess.artifact, outputs))
        return outputs

    def predict(
        self,
        X: t.Any,
        db: 'BaseDatabase' = None,  # type: ignore[name-defined]
        select: t.Optional[Select] = None,
        distributed: bool = False,
        ids: t.Optional[t.Sequence[str]] = None,
        max_chunk_size: t.Optional[int] = None,
        dependencies: t.Sequence[Job] = (),  # type: ignore[assignment]
        watch: bool = False,
        one: bool = False,
        **kwargs,
    ):
        # TODO this should be separated into sub-procedures

        if isinstance(select, dict):
            select = Serializable.deserialize(select)

        if watch:
            from pinnacledb.core.watcher import Watcher

            return db.add(
                Watcher(
                    model=self,  # type: ignore[arg-type]
                    select=select,  # type: ignore[arg-type]
                    key=X,
                ),
                dependencies=dependencies,
            )

        if db is not None:
            db.add(self)

        if distributed:
            assert not one
            return self.create_predict_job(
                X, select=select, ids=ids, max_chunk_size=max_chunk_size, **kwargs
            )(db=db, distributed=distributed, dependencies=dependencies)
        else:
            if select is not None and ids is None:
                assert not one
                ids = [
                    str(r[db.databackend.id_field])
                    for r in db.execute(select.select_ids)
                ]
                return self.predict(
                    X=X,
                    db=db,
                    ids=ids,
                    distributed=False,
                    select=select,
                    max_chunk_size=max_chunk_size,
                    one=False,
                    **kwargs,
                )

            elif select is not None and ids is not None and max_chunk_size is None:
                assert not one
                docs = list(db.execute(select.select_using_ids(ids)))
                if X != '_base':
                    X_data = [MongoStyleDict(r.unpack())[X] for r in docs]
                else:
                    X_data = [r.unpack() for r in docs]

                outputs = self.predict(X=X_data, one=False, distributed=False)
                if self.encoder is not None:
                    # ruff: noqa: E501
                    outputs = [self.encoder(x).encode() for x in outputs]  # type: ignore[operator]

                select.model_update(
                    db=db,
                    model=self.identifier,
                    outputs=outputs,
                    key=X,
                    ids=ids,
                )
                return

            elif select is not None and ids is not None and max_chunk_size is not None:
                assert not one
                it = 0
                for i in range(0, len(ids), max_chunk_size):
                    print(f'Computing chunk {it}/{int(len(ids) / max_chunk_size)}')
                    self.predict(
                        X=X,
                        db=db,
                        ids=ids[i : i + max_chunk_size],
                        select=select,
                        max_chunk_size=None,
                        one=False,
                        **kwargs,
                    )
                    it += 1
                return

            else:
                if 'one' in inspect.signature(self._predict).parameters:
                    return self._predict(X, one=one, **kwargs)
                else:
                    return self._predict(X, **kwargs)


@dc.dataclass
class Model(Component, PredictMixin):
    """
    Model component which wraps a model to become serializable

    :param object: Model object, e.g. sklearn model, etc..
    :param encoder: Encoder instance (optional)
    :param variety: ...
    """

    variety: t.ClassVar[str] = 'model'
    artifacts: t.ClassVar[t.Sequence[str]] = ['object']

    identifier: str
    object: t.Union[Artifact, t.Any]
    encoder: EncoderArg = None
    preprocess: t.Union[t.Callable, Artifact, None] = None
    postprocess: t.Union[t.Callable, Artifact, None] = None
    collate_fn: t.Union[t.Callable, Artifact, None] = None
    metrics: t.Sequence[t.Union[str, Metric, None]] = ()
    # Need also historical metric values
    predict_method: t.Optional[str] = None
    batch_predict: bool = False

    train_X: DataArg = None  # TODO add to FitMixin
    train_y: DataArg = None
    training_select: t.Union[Select, None] = None
    metric_values: t.Optional[t.Dict] = dc.field(default_factory=dict)
    # TODO should be training_metric_values
    training_configuration: t.Union[str, _TrainingConfiguration, None] = None

    version: t.Optional[int] = None
    future: t.Optional[Future] = None  # TODO what's this?
    device: str = "cpu"

    def __post_init__(self):
        if not isinstance(self.object, Artifact):
            self.object = Artifact(artifact=self.object)
        if self.preprocess and not isinstance(self.preprocess, Artifact):
            self.preprocess = Artifact(artifact=self.preprocess)
        if self.postprocess and not isinstance(self.postprocess, Artifact):
            self.postprocess = Artifact(artifact=self.postprocess)
        if self.predict_method is None:
            self.to_call = self.object.artifact
        else:
            self.to_call = getattr(self.object.artifact, self.predict_method)

    @property
    def child_components(self) -> t.List[t.Tuple[str, str]]:
        out = []
        if self.encoder is not None:
            out.append(('encoder', 'encoder'))
        if self.training_configuration is not None:
            out.append(('training_configuration', 'training_configuration'))
        return out

    @property
    def training_keys(self):
        out = [self.train_X]
        if self.train_y is not None:
            out.append(self.train_y)
        return out

    def append_metrics(self, d):
        for k in d:
            if k not in self.metric_values:
                self.metric_values[k] = []
            self.metric_values[k].append(d[k])

    def create_predict_job(
        self,
        X: str,
        select: t.Optional[Select] = None,
        ids: t.Optional[t.Sequence[str]] = None,
        max_chunk_size: t.Optional[int] = None,
        **kwargs,
    ):
        return ComponentJob(
            component_identifier=self.identifier,
            method_name='predict',
            variety='model',
            args=[X],
            kwargs={
                'remote': False,
                'select': select.serialize() if select else None,
                'ids': ids,
                'max_chunk_size': max_chunk_size,
                **kwargs,
            },
        )

    def validate(self, db, validation_set: Dataset, metrics: Metric):
        db.add(self)
        out = self._validate(db, validation_set, metrics)
        self.metrics_values.update(out)
        db.metadata.update_object(
            variety='model',
            identifier=self.identifier,
            version=self.version,
            key='dict.metric_values',
            value=self.metric_values,
        )

    def _validate(self, db, validation_set: Dataset, metrics: Metric):
        if isinstance(validation_set, str):
            validation_set = db.load('dataset', validation_set)
        prediction = self._predict(
            [MongoStyleDict(r.unpack())[self.train_X] for r in validation_set.data]
        )
        results = {}
        for m in metrics:
            out = m(
                prediction,
                [MongoStyleDict(r.unpack())[self.train_y] for r in validation_set.data],
            )
            results[f'{validation_set.identifier}/{m.identifier}'] = out
        return results

    def create_fit_job(
        self,
        X: t.Union[str, t.Sequence[str]],
        select: t.Optional[Select] = None,
        y: t.Optional[str] = None,
        **kwargs,
    ):
        return ComponentJob(
            component_identifier=self.identifier,
            method_name='fit',
            variety='model',
            args=[X],
            kwargs={
                'y': y,
                'remote': False,
                'select': select.serialize() if select else None,
                **kwargs,
            },
        )

    def _fit(
        self,
        X: t.Any,
        y: t.Any = None,
        db: t.Optional['Datalayer'] = None,  # type: ignore[name-defined]
        select: t.Optional[Select] = None,
        dependencies: t.Sequence[Job] = (),  # type: ignore[assignment]
        configuration: t.Optional[_TrainingConfiguration] = None,
        validation_sets: t.Optional[t.Sequence[t.Union[str, Dataset]]] = None,
        metrics: t.Optional[t.Sequence[Metric]] = None,
    ):
        raise NotImplementedError

    # ruff: noqa: F821
    def fit(
        self,
        X: t.Any,
        y: t.Any = None,
        db: t.Optional['Datalayer'] = None,  # type: ignore[name-defined]
        select: t.Optional[Select] = None,
        distributed: bool = False,
        dependencies: t.Sequence[Job] = (),  # type: ignore[assignment]
        configuration: t.Optional[_TrainingConfiguration] = None,
        validation_sets: t.Optional[t.Sequence[t.Union[str, Dataset]]] = None,
        metrics: t.Optional[t.Sequence[Metric]] = None,
        data_prefetch: bool = False,
        **kwargs,
    ):
        if isinstance(select, dict):
            select = Serializable.deserialize(select)

        if validation_sets:
            validation_sets = list(validation_sets)  # type: ignore[arg-type]
            for i, vs in enumerate(validation_sets):
                if isinstance(vs, Dataset):
                    db.add(vs)  # type: ignore[union-attr]
                    validation_sets[i] = vs.identifier

        if db is not None:
            db.add(self)

        if distributed:
            return self.create_fit_job(
                X,
                select=select,
                y=y,
                **kwargs,
            )(db=db, distributed=True, dependencies=dependencies)
        else:
            return self._fit(
                X,
                y=y,
                db=db,
                validation_sets=validation_sets,
                metrics=metrics,
                configuration=configuration,
                select=select,
                data_prefetch=data_prefetch,
                **kwargs,
            )
