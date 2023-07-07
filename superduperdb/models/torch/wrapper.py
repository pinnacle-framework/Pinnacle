import inspect
import io
from contextlib import contextmanager
from typing import Optional, Callable, Union, Dict, List, Any

import torch
from torch.utils import data
from torch.utils.data import DataLoader
from tqdm import tqdm
from pinnacledb.core.metric import Metric
from pinnacledb.core.documents import Document
from pinnacledb.core.encoder import Encoder, Encodable
from pinnacledb.datalayer.base.database import BaseDatabase
from pinnacledb.datalayer.base.query import Select
from pinnacledb.core.model import Model, ModelEnsemble, TrainingConfiguration
from pinnacledb.misc.logger import logging
from pinnacledb.models.torch.utils import device_of, to_device, eval
from pinnacledb.datalayer.query_dataset import QueryDataset
from pinnacledb.misc.serialization import from_dict


class BasicDataset(data.Dataset):
    """
    Basic database iterating over a list of documents and applying a transformation

    :param documents: documents
    :param transform: function
    """

    def __init__(self, documents, transform):
        super().__init__()
        self.documents = documents
        self.transform = transform

    def __len__(self):
        return len(self.documents)

    def __getitem__(self, item):
        document = self.documents[item]
        if isinstance(document, Document):
            document = document.unpack()
        elif isinstance(document, Encodable):
            document = document.x
        return self.transform(document)


class TorchTrainerConfiguration(TrainingConfiguration):
    def __init__(
        self,
        identifier,
        objective,
        loader_kwargs,
        optimizer_cls=torch.optim.Adam,
        optimizer_kwargs=None,
        max_iterations=float('inf'),
        no_improve_then_stop=5,
        splitter=None,
        download=False,
        validation_interval=100,
        watch='objective',
        target_preprocessors=None,
        **kwargs,
    ):
        super().__init__(
            identifier,
            loader_kwargs=loader_kwargs,
            objective=objective,
            optimizer_cls=optimizer_cls,
            optimizer_kwargs=optimizer_kwargs or {},
            no_improve_then_stop=no_improve_then_stop,
            max_iterations=max_iterations,
            splitter=splitter,
            download=download,
            validation_interval=validation_interval,
            target_preprocessors=target_preprocessors or {},
            watch=watch,
            **kwargs,
        )


class Base(Model):
    def __init__(
        self,
        object: Union[torch.nn.Module, torch.jit.ScriptModule],
        identifier: str,
        collate_fn: Optional[Callable] = None,
        is_batch: Optional[Callable] = None,
        encoder: Optional[Union[Encoder, str]] = None,
        training_configuration: Optional[TorchTrainerConfiguration] = None,
        training_select: Optional[Select] = None,
        train_X: Optional[Union[str, List[str]]] = None,
        train_y: Optional[Union[str, List[str]]] = None,
        validation_sets: Optional[List[str]] = None,
        num_directions: int = 2,
        metrics: Optional[List[Metric]] = None,
    ):
        super().__init__(
            object=object,
            identifier=identifier,
            training_configuration=training_configuration,
            train_X=train_X,
            train_y=train_y,
            training_select=training_select,
            encoder=encoder,
            metrics=metrics,
        )
        self.optimizers = None
        self.collate_fn = collate_fn
        self.is_batch = is_batch
        self.num_directions = num_directions
        self.validation_sets = validation_sets

    @contextmanager
    def evaluating(self):
        raise NotImplementedError

    def train(self):
        raise NotImplementedError

    def build_optimizers(self):
        return (
            self.training_configuration.optimizer_cls(
                self.object.parameters(),
                **self.training_configuration.optimizer_kwargs,
            ),
        )

    def stopping_criterion(self, iteration):
        max_iterations = self.training_configuration.max_iterations
        no_improve_then_stop = self.training_configuration.no_improve_then_stop
        if isinstance(max_iterations, int) and iteration >= max_iterations:
            return True
        if isinstance(no_improve_then_stop, int):
            if self.training_configuration.watch == 'objective':
                to_watch = [-x for x in self.metric_values['objective']]
            else:
                to_watch = self.metric_values[self.training_configuration.watch]

            if max(to_watch[-no_improve_then_stop:]) < max(to_watch):
                logging.info('early stopping triggered!')
                return True
        return False

    def saving_criterion(self):
        if self.training_configuration.watch == 'objective':
            to_watch = [-x for x in self.metric_values['objective']]
        else:
            to_watch = self.metric_values[self.training_configuration.watch]
        if all([to_watch[-1] >= x for x in to_watch[:-1]]):
            return True
        return False

    def _fit(  # type: ignore[override]
        self,
        X: Union[List[str], str],
        y: Optional[Union[List, Any]] = None,
        db: Optional[BaseDatabase] = None,
        select: Optional[Union[Select, Dict]] = None,
        configuration: Optional[TorchTrainerConfiguration] = None,
        validation_sets: Optional[List[str]] = None,
        metrics: Optional[List[Metric]] = None,
    ):
        if configuration is not None:
            self.training_configuration = configuration
        if select is not None:
            if isinstance(select, dict):
                select = from_dict(select)
            self.training_select = select  # type: ignore[assignment]
        if validation_sets is not None:
            self.validation_sets = validation_sets
        if metrics is not None:
            self.metrics = metrics

        self.train_X = X
        self.train_y = y

        train_data, valid_data = self._get_data(db=db)
        # ruff: noqa: E501
        loader_kwargs = self.training_configuration.loader_kwargs  # type: ignore[union-attr]
        train_dataloader = DataLoader(train_data, **loader_kwargs)
        valid_dataloader = DataLoader(valid_data, **loader_kwargs)

        return self._fit_with_dataloaders(
            train_dataloader,
            valid_dataloader,
            db=db,  # type: ignore[arg-type]
            validation_sets=validation_sets or [],
            # TODO - add serializer to __init__ method of Model
        )

    def preprocess(self, r):
        raise NotImplementedError  # implemented in PyTorch wrapper and PyTorch pipeline

    def log(self, **kwargs):
        out = ''
        for k, v in kwargs.items():
            if isinstance(v, dict):
                for kk, vv in v.items():
                    out += f'{k}/{kk}: {vv}; '
            else:
                out += f'{k}: {v}; '
        logging.info(out)

    def train_forward(self, X, y=None):
        if hasattr(self.object, 'train_forward'):
            if y is None:
                return self.object.train_forward(X)
            else:
                return self.object.train_forward(X, y=y)
        else:
            if y is None:
                return (self.object(X),)
            else:
                return [self.object(X), y]

    def forward(self, X):
        return self.object(X)

    def extract_batch_key(self, batch, key: Union[List[str], str]):
        if isinstance(key, str):
            return batch[key]
        return [batch[k] for k in key]

    def extract_batch(self, batch):
        if self.train_y is not None:
            return [
                self.extract_batch_key(batch, self.train_X),
                self.extract_batch_key(batch, self.train_y),
            ]
        return [self.extract_batch_key(batch, self.train_X)]

    def take_step(self, batch, optimizers):
        batch = self.extract_batch(batch)
        outputs = self.train_forward(*batch)
        objective_value = self.training_configuration.objective(*outputs)
        for opt in optimizers:
            opt.zero_grad()
        objective_value.backward()
        for opt in optimizers:
            opt.step()
        return objective_value

    def compute_validation_objective(self, valid_dataloader):
        objective_values = []
        with self.evaluating(), torch.no_grad():
            for batch in valid_dataloader:
                batch = self.extract_batch(batch)
                objective_values.append(
                    self.training_configuration.objective(
                        *self.train_forward(*batch)
                    ).item()
                )
            return sum(objective_values) / len(objective_values)

    def save(self, database: BaseDatabase):
        database.replace_model(
            identifier=self.identifier,
            object=self,
            upsert=True,
        )  # TODO replace_object is redundant

    def compute_metrics(self, validation_set, database):
        validation_set = database.load('dataset', validation_set)
        validation_set = [r.unpack() for r in validation_set.data]
        return self.training_configuration.compute_metrics(
            validation_set,
            metrics=self.metrics,
            model=self,
        )

    def _fit_with_dataloaders(
        self,
        train_dataloader: DataLoader,
        valid_dataloader: DataLoader,
        db: BaseDatabase,  # type: ignore[arg-type]
        validation_sets: List[str],
    ):
        self.train()
        iteration = 0
        optimizers = self.build_optimizers()
        while True:
            for batch in train_dataloader:
                train_objective = self.take_step(batch, optimizers)
                self.log(fold='TRAIN', iteration=iteration, objective=train_objective)
                # ruff: noqa: E501
                if iteration % self.training_configuration.validation_interval == 0:  # type: ignore[union-attr]
                    valid_loss = self.compute_validation_objective(valid_dataloader)
                    all_metrics = {}
                    for vs in validation_sets:
                        metrics = self.compute_metrics(vs, db)
                        metrics = {f'{vs}/{k}': metrics[k] for k in metrics}
                        all_metrics.update(metrics)
                    all_metrics.update({'objective': valid_loss})
                    self.append_metrics(all_metrics)
                    self.log(fold='VALID', iteration=iteration, **all_metrics)
                    if self.saving_criterion():
                        self.save(db)
                    stop = self.stopping_criterion(iteration)
                    if stop:
                        return
                iteration += 1

    def train_preprocess(self):
        preprocessors = {}
        if isinstance(self.train_X, str):
            preprocessors[self.train_X] = self.preprocess
        else:
            for _id, X in zip(self._model_ids, self.train_X):
                preprocessors[X] = getattr(self, _id).preprocess
        if self.train_y is not None:
            if isinstance(self.train_y, str):
                preprocessors[
                    self.train_y
                ] = self.training_configuration.target_preprocessors.get(
                    self.train_y, lambda x: x
                )
            else:
                for y in self.train_y:
                    preprocessors[
                        y
                    ] = self.training_configuration.target_preprocessors.get(
                        y, lambda x: x
                    )
        return lambda r: {k: preprocessors[k](r[k]) for k in preprocessors}

    def _get_data(self, db: Optional[BaseDatabase]):
        train_data = QueryDataset(
            select=self.training_select,  # type: ignore[arg-type]
            keys=self.training_keys,
            fold='train',
            transform=self.train_preprocess(),
            database=db,
        )
        valid_data = QueryDataset(
            select=self.training_select,  # type: ignore[arg-type]
            keys=self.training_keys,
            fold='valid',
            transform=self.train_preprocess(),
            database=db,
        )
        return train_data, valid_data


class TorchPipeline(Base):
    """
    Sklearn style PyTorch pipeline.

    :param steps: List of ``sklearn`` style steps/ transforms
    :param identifier: Unique identifier
    :param collate_fn: Function for collating batches
    """

    def __init__(
        self,
        identifier,
        steps,
        collate_fn: Optional[Callable] = None,
        is_batch: Optional[Callable] = None,
        encoder: Optional[Union[Encoder, str]] = None,
        training_configuration: Optional[TorchTrainerConfiguration] = None,
        training_select: Optional[Select] = None,
        train_X: Optional[Union[str, List[str]]] = None,
        train_y: Optional[Union[str, List[str]]] = None,
        num_directions: int = 2,
        metrics: Optional[Union[List[Metric], List[str]]] = None,
    ):
        self.steps = steps  # type: ignore[misc]
        self._forward_sequential = None
        self.is_batch = is_batch
        forward_steps = self.steps[self._forward_mark : self._post_mark]
        object = torch.nn.Sequential(*[s[1] for s in forward_steps])
        super().__init__(
            identifier=identifier,
            object=object,
            training_configuration=training_configuration,
            training_select=training_select,
            train_X=train_X,
            train_y=train_y,
            encoder=encoder,
            collate_fn=collate_fn,
            is_batch=is_batch,
            num_directions=num_directions,
            metrics=metrics,  # type: ignore[arg-type]
        )

    @contextmanager
    def evaluating(self):
        yield eval(self.object)

    def train(self):
        return self.object.train()

    def __repr__(self):
        lines = [
            'TorchPipeline(steps=[',
            *[f'   {(s[0], s[1])}' for s in self.steps],
            '])',
        ]
        return '\n'.join(lines)

    def _test_if_batch(self, x):
        if self.is_batch is not None:
            return self.is_batch(x)
        if hasattr(self.steps[0][1], '__call__'):
            type = next(
                iter(inspect.signature(self.steps[0][1].__call__).parameters.values())
            ).annotation
        else:
            type = next(
                iter(inspect.signature(self.steps[0][1]).parameters.values())
            ).annotation
        if type != inspect._empty:
            return not isinstance(x, type)
        return isinstance(x, list)

    @property
    def steps(self):
        return self._steps

    def preprocess(self, x):
        for s in self.steps[: self._forward_mark]:
            transform = s[1]
            if hasattr(transform, 'transform'):
                x = transform.transform(x)
            else:
                assert callable(transform)
                x = transform(x)
        return x

    @property
    def preprocess_pipeline(self):
        return TorchPipeline(
            identifier=f'{self.identifier}/preprocess',
            steps=self.steps[: self._forward_mark],
        )

    @property
    def forward_pipeline(self):
        if self._forward_sequential is None:
            forward_steps = self.steps[self._forward_mark : self._post_mark]
            self._forward_sequential = torch.nn.Sequential(
                *[s[1] for s in forward_steps]
            )
        return self._forward_sequential

    @property
    def postprocess_pipeline(self):
        return TorchPipeline(
            identifier=f'{self.identifier}/postprocess',
            steps=self.steps[self._post_mark :],
        )

    def postprocess(self, x):
        for s in self.steps[self._post_mark :]:
            transform = s[1]
            if hasattr(transform, 'transform'):
                x = transform.transform(x)
            else:
                assert callable(transform)
                x = transform(x)
        return x

    def _predict(self, X, **kwargs):
        if not self._test_if_batch(X):
            return self._predict_one(X, **kwargs)
        if self.preprocess_pipeline.steps:
            inputs = BasicDataset(X, self.preprocess)
            loader = torch.utils.data.DataLoader(
                inputs, **kwargs, collate_fn=self.collate_fn
            )
        else:
            loader = torch.utils.data.DataLoader(
                X, **kwargs, collate_fn=self.collate_fn
            )
        out = []
        for batch in tqdm(loader, total=len(loader)):
            batch = to_device(batch, device_of(self.forward_pipeline))
            tmp = self.forward(batch)
            tmp = to_device(tmp, 'cpu')
            tmp = unpack_batch(tmp)
            tmp = list(map(self.postprocess, tmp))
            out.extend(tmp)
        return out

    def _predict_one(self, X, **kwargs):
        with torch.no_grad(), eval(self.forward_pipeline):
            X = self.preprocess(X)
            X = to_device(X, device_of(self.forward_pipeline))
            singleton_batch = create_batch(X)
            output = self.forward(singleton_batch)
            output = unpack_batch(output)[0]
            return self.postprocess(output)

    @contextmanager
    def eval(self):
        was_training = self.forward_pipeline.steps[0][1].training
        try:
            for s in self.forward_pipeline.steps:
                s[1].eval()
            yield
        finally:
            if was_training:
                for s in self.forward_pipeline.steps:
                    s[1].eval()

    saving = eval

    @steps.setter  # type: ignore[no-redef,attr-defined]
    def steps(self, value):
        self._steps = value
        try:
            self._forward_mark = next(
                i
                for i, s in enumerate(value)
                if isinstance(s[1], torch.nn.Module)
                or isinstance(s[1], torch.jit.ScriptModule)
            )
        except StopIteration:
            self._forward_mark = len(self.steps)

        try:
            self._post_mark = next(
                len(value) - i
                for i, s in enumerate(value[::-1])
                if isinstance(s[1], torch.nn.Module)
                or isinstance(s[1], torch.jit.ScriptModule)
            )
        except StopIteration:
            self._post_mark = len(self.steps)

    def parameters(self):
        for s in self.forward_pipeline.steps:
            yield from s[1].parameters()


class TorchModel(Base):
    def __init__(
        self,
        object: Union[torch.nn.Module, torch.jit.ScriptModule],
        identifier: str,
        collate_fn: Optional[Callable] = None,
        is_batch: Optional[Callable] = None,
        encoder: Optional[Union[Encoder, str]] = None,
        training_configuration: Optional[TorchTrainerConfiguration] = None,
        training_select: Optional[Select] = None,
        train_X: Optional[Union[str, List[str]]] = None,
        train_y: Optional[Union[str, List[str]]] = None,
        validation_sets: Optional[List[str]] = None,
        num_directions: int = 2,
        metrics: Optional[List[Metric]] = None,
        preprocess: Optional[Callable] = None,
        postprocess: Optional[Callable] = None,
    ):
        super().__init__(
            object=object,
            identifier=identifier,
            collate_fn=collate_fn,
            is_batch=is_batch,
            encoder=encoder,
            training_configuration=training_configuration,
            training_select=training_select,
            train_X=train_X,
            train_y=train_y,
            validation_sets=validation_sets,
            num_directions=num_directions,
            metrics=metrics,
        )
        self._preprocess = preprocess
        self._postprocess = postprocess
        if hasattr(self.object, 'preprocess') and preprocess is not None:
            raise Exception(
                'Ambiguous preprocessing between passed preprocess '
                'and object.preprocess'
            )
        if hasattr(self.object, 'postprocess') and postprocess is not None:
            raise Exception(
                'Ambiguous postprocessing between passed postprocess '
                'and object.postprocess'
            )
        if hasattr(self.object, 'preprocess'):
            self._preprocess = self.object.preprocess
        if hasattr(self.object, 'postprocess'):
            self._postprocess = self.object.postprocess

    def build_optimizers(self):
        return (
            self.training_configuration.optimizer_cls(
                self.object.parameters(),
                **self.training_configuration.optimizer_kwargs,
            ),
        )

    @contextmanager
    def evaluating(self):
        yield eval(self)

    def train(self):
        return self.object.train()

    def parameters(self):
        return self.object.parameters()

    def state_dict(self):
        return self.object.state_dict()

    @contextmanager
    def saving(self):
        with super().saving():
            was_training = self.object.training
            try:
                self.object.eval()
                yield
            finally:
                if was_training:
                    self.object.train()

    def __getstate__(self):
        state = self.__dict__.copy()
        if isinstance(self.object, torch.jit.ScriptModule) or isinstance(
            self.object, torch.jit.ScriptFunction
        ):
            f = io.BytesIO()
            torch.jit.save(self.object, f)
            state['_object_bytes'] = f.getvalue()
        return state

    def __setstate__(self, state):
        keys = state.keys()
        for k in keys:
            if k != '_object_bytes':
                self.__dict__[k] = state[k]
            else:
                state.__dict__['object'] = torch.jit.load(
                    io.BytesIO(state.pop('object_bytes'))
                )

    def _predict_one(self, x):
        with torch.no_grad(), eval(self.object):
            if hasattr(self.object, 'preprocess'):
                x = self.object.preprocess(x)
            x = to_device(x, device_of(self.object))
            singleton_batch = create_batch(x)
            output = self.object(singleton_batch)
            output = to_device(output, 'cpu')
            args = unpack_batch(output)[0]
            if hasattr(self.object, 'postprocess'):
                args = self.object.postprocess(args)
            return args

    def _predict(self, x, **kwargs):
        with torch.no_grad(), eval(self.object):
            if not isinstance(x, list) and not test_if_batch(x, self.num_directions):
                return self._predict_one(x)
            inputs = BasicDataset(x, self.preprocess)
            loader = torch.utils.data.DataLoader(inputs, **kwargs)
            out = []
            for batch in tqdm(loader, total=len(loader)):
                batch = to_device(batch, device_of(self.object))
                tmp = self.object(batch)
                tmp = to_device(tmp, 'cpu')
                tmp = unpack_batch(tmp)
                tmp = list(map(self.postprocess, tmp))
                out.extend(tmp)
            return out

    def preprocess(self, r):
        if self._preprocess is not None:
            return self._preprocess(r)
        return r

    def postprocess(self, r):
        if self._postprocess is not None:
            return self._postprocess(r)
        return r


def test_if_batch(x, num_directions: Union[Dict, int]):
    """
    :param x: item to test whether batch or singleton
    :param num_directions: dictionary to test a leaf node in ``x`` whether batch or not

    >>> test_if_batch(torch.randn(10), 2)
    False
    >>> test_if_batch(torch.randn(2, 10), 2)

    :param documents: documents
    :param transform: function
    """

    def __init__(self, documents, transform):
        super().__init__()
        self.documents = documents
        self.transform = transform

    def __len__(self):
        return len(self.documents)

    def __getitem__(self, item):
        document = self.documents[item]
        if isinstance(document, Document):
            document = document.unpack()
        elif isinstance(document, Encodable):
            document = document.x
        return self.transform(document)


def unpack_batch(args):
    """
    Unpack a batch into lines of tensor output.

    :param args: a batch of model outputs

    >>> unpack_batch(torch.randn(1, 10))[0].shape
    torch.Size([10])
    >>> out = unpack_batch([torch.randn(2, 10), torch.randn(2, 3, 5)])
    >>> type(out)
    <class 'list'>
    >>> len(out)
    2
    >>> out = unpack_batch({'a': torch.randn(2, 10), 'b': torch.randn(2, 3, 5)})
    >>> [type(x) for x in out]
    [<class 'dict'>, <class 'dict'>]
    >>> out[0]['a'].shape
    torch.Size([10])
    >>> out[0]['b'].shape
    torch.Size([3, 5])
    >>> out = unpack_batch({'a': {'b': torch.randn(2, 10)}})
    >>> out[0]['a']['b'].shape
    torch.Size([10])
    >>> out[1]['a']['b'].shape
    torch.Size([10])
    """

    if isinstance(args, torch.Tensor):
        return [args[i] for i in range(args.shape[0])]
    else:
        if isinstance(args, list) or isinstance(args, tuple):
            tmp = [unpack_batch(x) for x in args]
            batch_size = len(tmp[0])
            return [[x[i] for x in tmp] for i in range(batch_size)]
        elif isinstance(args, dict):
            tmp = {k: unpack_batch(v) for k, v in args.items()}
            batch_size = len(next(iter(tmp.values())))
            return [{k: v[i] for k, v in tmp.items()} for i in range(batch_size)]
        else:  # pragma: no cover
            raise NotImplementedError


def create_batch(args):
    """
    Create a singleton batch in a manner similar to the PyTorch dataloader

    :param args: single data point for batching

    >>> create_batch(3.).shape
    torch.Size([1])
    >>> x, y = create_batch([torch.randn(5), torch.randn(3, 7)])
    >>> x.shape
    torch.Size([1, 5])
    >>> y.shape
    torch.Size([1, 3, 7])
    >>> d = create_batch(({'a': torch.randn(4)}))
    >>> d['a'].shape
    torch.Size([1, 4])
    """
    if isinstance(args, (tuple, list)):
        return tuple([create_batch(x) for x in args])
    if isinstance(args, dict):
        return {k: create_batch(args[k]) for k in args}
    if isinstance(args, torch.Tensor):
        return args.unsqueeze(0)
    if isinstance(args, (float, int)):
        return torch.tensor([args])
    raise TypeError(
        'only tensors and tuples of tensors recursively supported...'
    )  # pragma: no cover


class TorchModelEnsemble(Base, ModelEnsemble):
    def __init__(
        self,
        models: List[Base],
        identifier: str,
        collate_fn: Optional[Callable] = None,
        is_batch: Optional[Callable] = None,
        encoder: Optional[Union[Encoder, str]] = None,
        training_configuration: Optional[TorchTrainerConfiguration] = None,
        training_select: Optional[Select] = None,
        train_X: Optional[Union[str, List[str]]] = None,
        train_y: Optional[Union[str, List[str]]] = None,
        num_directions: int = 2,
    ):
        Base.__init__(
            self,
            object=None,  # type: ignore[arg-type]
            identifier=identifier,
            collate_fn=collate_fn,
            is_batch=is_batch,
            encoder=encoder,
            training_configuration=training_configuration,
            training_select=training_select,
            train_X=train_X,
            train_y=train_y,
            num_directions=num_directions,
        )
        ModelEnsemble.__init__(self, models)  # type: ignore[arg-type]

    def build_optimizers(self):
        optimizers = []
        for m in self._model_ids:
            optimizers.append(
                self.training_configuration.optimizer_cls(
                    getattr(self, m).object.parameters(),
                    **self.training_configuration.optimizer_kwargs,
                )
            )
        return optimizers

    @contextmanager
    def evaluating(self):
        was_training = getattr(self, self._model_ids[0]).object.training
        try:
            for m in self._model_ids:
                getattr(self, m).object.eval()
            yield
        finally:
            if was_training:
                for m in self._model_ids:
                    getattr(self, m).object.train()

    def train(self):
        for m in self._model_ids:
            getattr(self, m).train()

    def train_forward(self, X, y=None):
        out = []
        for i, k in enumerate(self.train_X):
            submodel = getattr(self, self._model_ids[i])
            out.append(submodel.object(X[i]))
        if y is not None:
            return out, y
        else:
            return out
