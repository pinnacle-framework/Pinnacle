import itertools
import typing as t
import dataclasses as dc

import pinnacledb as s
from pinnacledb.core.component import Component
from pinnacledb.core.dataset import Dataset
from pinnacledb.core.document import Document
from pinnacledb.core.encoder import Encodable
from pinnacledb.core.metric import Metric
from pinnacledb.core.model import ModelEnsemble
from pinnacledb.core.watcher import Watcher
from pinnacledb.datalayer.base.datalayer import Datalayer
from pinnacledb.metrics.vector_search import VectorSearchPerformance
from pinnacledb.misc.logger import logging
from pinnacledb.misc.special_dicts import MongoStyleDict
from pinnacledb.vector_search.base import VectorCollectionConfig, VectorCollectionItem

T = t.TypeVar('T')


def ibatch(iterable: t.Iterable[T], batch_size: int) -> t.Iterator[t.List[T]]:
    """
    Batch an iterable into chunks of size `batch_size`
    """
    iterator = iter(iterable)
    while True:
        batch = list(itertools.islice(iterator, batch_size))
        if not batch:
            break
        yield batch


# TODO configurable
_BACKFILL_BATCH_SIZE = 100


@dc.dataclass
class VectorIndex(Component):
    """
    Vector-index

    :param identifier: Unique ID of index
    :param indexing_watcher: watcher which is applied to create vectors
    :param compatible_watchers: list of additional watchers which can
                                "talk" to the index (e.g. multi-modal)
    :param measure: Measure which is used to compare vectors in index
    """

    variety: t.ClassVar[str] = 'vector_index'

    identifier: str
    indexing_watcher: t.Union[Watcher, str]
    compatible_watcher: t.Union[Watcher, str] = dc.field(default_factory=list)
    measure: str = 'cosine'
    version: t.Optional[int] = None
    metric_values: t.Optional[t.Dict] = dc.field(default_factory=dict)

    def _on_create(self, db):
        if isinstance(self.indexing_watcher, str):
            self.indexing_watcher = db.load('watcher', self.indexing_watcher)
        if isinstance(self.compatible_watcher, str):
            self.compatible_watcher = db.load('watcher', self.compatible_watcher)

    def _on_load(self, db):
        self.vector_table = db.vector_database.get_table(
            VectorCollectionConfig(
                id=self.identifier,
                dimensions=self._dimensions,
                measure=self.measure,
            ),
            create=True,
        )

        if not s.CFG.cdc:
            self._initialize_vector_database(db)

    @property
    def child_components(self) -> t.List[t.Tuple[str, str]]:
        out = [('indexing_watcher', 'watcher')]
        if self.compatible_watcher is not None:
            out.append(('compatible_watcher', 'watcher'))
        return out

    def _initialize_vector_database(self, db):
        logging.info(f'loading hashes: {self.identifier!r}')
        for record_batch in ibatch(
            db.execute(self.indexing_watcher.select),
            _BACKFILL_BATCH_SIZE,
        ):
            items = []
            for record in record_batch:
                h, id = db.databackend.get_output_from_document(
                    record,
                    self.indexing_watcher.key,
                    self.indexing_watcher.model.identifier,
                )
                if isinstance(h, Encodable):
                    h = h.x
                items.append(VectorCollectionItem.create(id=str(id), vector=h))
            self.vector_table.add(items)

    @property
    def _dimensions(self) -> int:
        if not isinstance(self.indexing_watcher, Watcher):
            raise NotImplementedError
        if not hasattr(self.indexing_watcher.model.encoder, 'shape'):
            raise NotImplementedError(
                'Couldn\'t find shape of model outputs, based on model encoder.'
            )
        model_encoder = self.indexing_watcher.model.encoder
        try:
            dimensions = int(model_encoder.shape[-1])
        except Exception:
            dimensions = None
        if not dimensions:
            raise ValueError(
                f"Model {self.indexing_watcher.model.identifier} has no shape"
            )
        return dimensions

    def get_nearest(
        self,
        like: Document,
        db: t.Any = None,
        outputs: t.Optional[t.Dict] = None,
        featurize: bool = True,
        ids: t.Optional[t.List[str]] = None,
        n: int = 100,
    ) -> t.Tuple[t.List[str], t.List[float]]:
        models, keys = self.models_keys
        if len(models) != len(keys):
            raise ValueError(f'len(models={models}) != len(keys={keys})')
        within_ids = ids or ()

        if isinstance(like.content, dict) and db.db.id_field in like.content:
            nearest = self.vector_table.find_nearest_from_id(
                str(like[db.db.id_field]), within_ids=within_ids, limit=n
            )
            return (
                [result.id for result in nearest],
                [result.score for result in nearest],
            )

        document = MongoStyleDict(like.unpack())

        if featurize:
            outputs = outputs or {}
            if '_outputs' not in document:
                document['_outputs'] = {}
            document['_outputs'].update(outputs)
            features = self.indexing_watcher.features or ()
            for subkey in features:
                subout = document['_outputs'].setdefault(subkey, {})
                f_subkey = features[subkey]
                if f_subkey not in subout:
                    subout[f_subkey] = db.models[f_subkey]._predict(document[subkey])
                document[subkey] = subout[f_subkey]
        available_keys = list(document.keys()) + ['_base']
        try:
            model, key = next(
                (m, k) for m, k in zip(models, keys) if k in available_keys
            )
        except StopIteration:
            raise Exception(
                f'Keys in provided {like} don\'t match'
                f' VectorIndex keys: {keys}, with models: {models}'
            )
        model_input = document[key] if key != '_base' else document

        model = db.models[model]
        h = model.predict(model_input, one=True)
        nearest = self.vector_table.find_nearest_from_array(
            h, within_ids=within_ids, limit=n
        )
        return (
            [result.id for result in nearest],
            [result.score for result in nearest],
        )

    @property
    def models_keys(self) -> t.Tuple[t.List[str], t.List[str]]:
        if self.compatible_watcher:
            watchers = [self.indexing_watcher, self.compatible_watcher]
        else:
            watchers = [self.indexing_watcher]
        models = [w.model.identifier for w in watchers]
        keys = [w.key for w in watchers]
        return models, keys

    def _validate(
        self,
        db: Datalayer,
        validation_set: t.Union[str, Dataset],
        metrics: t.List[t.Union[Metric, str]],
    ) -> t.Dict[str, t.List]:
        models, keys = self.models_keys
        models = [db.models[m] for m in models]
        if isinstance(validation_set, str):
            validation_data = db.load('dataset', validation_set)

        def to_metric(m):
            return m if isinstance(m, Metric) else db.load('metric', m)

        metric_list = [to_metric(m) for m in metrics]

        unpacked = [r.unpack() for r in validation_data.data]
        model_ensemble = ModelEnsemble(identifier='tmp', models=models)
        if len(keys) < 2:
            msg = 'Can only evaluate VectorSearch with compatible watchers...'
            raise ValueError(msg)

        return VectorSearchPerformance(
            measure=self.measure,
            index_key=self.indexing_watcher.key,
            compatible_keys=[self.compatible_watcher.key],
        )(
            validation_data=unpacked,
            model=model_ensemble,
            metrics=metric_list,
        )
