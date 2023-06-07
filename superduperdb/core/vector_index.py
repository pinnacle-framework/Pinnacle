from typing import List, Union, Optional, Any

from pinnacledb.core.base import (
    ComponentList,
    PlaceholderList,
    Component,
    Placeholder,
    is_placeholders_or_components,
    DBPlaceholder,
)
from pinnacledb.core.metric import Metric
from pinnacledb.core.model import Model
from pinnacledb.core.watcher import Watcher
from pinnacledb.datalayer.base.query import Select
from pinnacledb.misc import progress
from pinnacledb.misc.special_dicts import MongoStyleDict
from pinnacledb.training.query_dataset import QueryDataset
from pinnacledb.training.validation import validate_vector_search
from pinnacledb.vector_search import VanillaHashSet
from pinnacledb.misc.logger import logging


class VectorIndex(Component):
    """
    Vector-index

    :param identifier: Unique ID of index
    :param keys: Keys which may be used to search index
    :param watcher: Watcher which is applied to create vectors
    :param watcher_id: ID of Watcher which is applied to create vectors
    :param models:  models which may be used to search index
    :param model_ids: ID of models which may be used to search index
    :param measure: Measure which is used to compare vectors in index
    :param hash_set_cls: Class which is used to execute similarity lookup
    """

    variety = 'vector_index'

    def __init__(
        self,
        identifier: str,
        keys: List[str],
        watcher: Union[Watcher, str],
        models: Union[List[Model], List[str]] = None,
        measure: str = 'css',
        hash_set_cls: type = VanillaHashSet,
    ):
        super().__init__(identifier)
        self.keys = keys
        self.watcher = (
            Placeholder(watcher, 'watcher') if isinstance(watcher, str) else watcher
        )

        is_placeholders, is_components = is_placeholders_or_components(models)
        assert is_placeholders or is_components
        if is_placeholders:
            self.models = PlaceholderList('model', models)
        else:
            self.models = ComponentList('model', models)
        assert len(self.keys) == len(self.models)
        self.measure = measure
        self.hash_set_cls = hash_set_cls
        self._hash_set = None
        self.database = DBPlaceholder()

    def repopulate(self, database: Optional[Any] = None):
        if database is None:
            database = self.database
            assert not isinstance(database, DBPlaceholder)
        super().repopulate(database)
        c = database.select(self.select)
        loaded = []
        ids = []
        docs = progress.progressbar(c)
        logging.info(f'loading hashes: "{self.identifier}')
        for r in docs:
            h = database._get_output_from_document(
                r, self.watcher.key, self.watcher.model.identifier
            )
            loaded.append(h)
            ids.append(r['_id'])

        self._hash_set = self.hash_set_cls(
            loaded,
            ids,
            measure=self.measure,
        )

    @property
    def select(self):
        return self.watcher.select

    def get_nearest(
        self,
        like,
        database: Optional[Any] = None,
        ids=None,
        n=100,
    ):
        if database is None:
            database = self.database
            assert not isinstance(database, DBPlaceholder)

        models = [m.identifier for m in self.models]
        keys = self.keys

        hash_set = self._hash_set
        if ids:
            hash_set = hash_set[ids]

        if database.id_field in like:
            return hash_set.find_nearest_from_id(like['_id'], n=n)

        available_keys = list(like.keys()) + ['_base']
        model, key = next((m, k) for m, k in zip(models, keys) if k in available_keys)
        document = MongoStyleDict(like)
        if '_outputs' not in document:
            document['_outputs'] = {}

        for subkey in self.watcher.features:
            if subkey not in document:
                continue
            if subkey not in document['_outputs']:
                document['_outputs'][subkey] = {}
            if self.watcher.features[subkey] not in document['_outputs'][subkey]:
                document['_outputs'][subkey][
                    self.watcher.features[subkey]
                ] = database.models[self.watcher.features[subkey]].predict_one(
                    document[subkey]
                )
            document[subkey] = document['_outputs'][subkey][
                self.watcher.features[subkey]
            ]
        model_input = document[key] if key != '_base' else document

        model = database.models[model]
        h = model.predict_one(model_input)
        return hash_set.find_nearest_from_hash(h, n=n)

    def validate(
        self,
        database: 'pinnacledb.datalayer.base.database.Database',  # noqa: F821  why?
        validation_selects: List[Select],
        metrics: List[Metric],
    ):
        out = []
        for vs in validation_selects:
            validation_data = QueryDataset(
                vs,
                database_type=database._database_type,
                database=database.name,
                keys=self.keys,
                fold='valid',
            )
            res = validate_vector_search(
                validation_data=validation_data,
                models=self.models,
                keys=self.keys,
                metrics=metrics,
                hash_set_cls=self.hash_set_cls,
                measure=self.measure,
                predict_kwargs={},
            )
            out.append(res)
        return out

    def asdict(self):
        return {
            'identifier': self.identifier,
            'watcher': self.watcher.identifier,
            'keys': self.keys,
            'models': self.models.aslist(),
            'measure': self.measure,
            'hash_set_cls': self.hash_set_cls.name,
        }
