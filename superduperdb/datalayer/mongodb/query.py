from dataclasses import dataclass, field, asdict
from functools import cached_property
import typing as t
from bson import ObjectId

from pinnacledb.core.documents import Document
from pinnacledb.datalayer.base import query


@dataclass(frozen=True)
class Select(query.Select):
    collection: str
    filter: t.Optional[t.Mapping[str, t.Any]] = None
    projection: t.Optional[t.Mapping[str, t.Any]] = None
    one: bool = False
    kwargs: t.Mapping[str, t.Any] = field(default_factory=dict)
    like: t.Optional[Document] = None
    download: bool = False
    vector_index: t.Optional[str] = None
    similar_first: bool = False
    features: t.Optional[t.Mapping[str, str]] = None
    n: int = 100
    outputs: t.Optional[t.Dict] = None

    def add_fold(self, fold: str) -> 'Select':
        return Select(
            collection=self.collection,
            filter={'_fold': fold, **(self.filter or {})},
            projection=self.projection,
            kwargs=self.kwargs,
            one=self.one,
        )

    @cached_property
    def table(self):
        return self.collection

    @cached_property
    def is_trivial(self) -> bool:
        return not self.filter

    @cached_property
    def select_only_id(self) -> 'Select':
        variables = asdict(self)
        variables['projection'] = {'_id': 1}
        return Select(**variables)

    def select_using_ids(
        self, ids, features: t.Optional[t.Mapping[str, str]] = None
    ) -> 'Select':
        variables = asdict(self)
        # NOTE: here we assume that the _id field is ObjectId, although it may not be
        # the case.
        variables['filter'] = {
            '_id': {'$in': [ObjectId(id_) for id_ in ids]},
            **(self.filter if self.filter else {}),
        }
        if features is not None:
            variables['features'] = features
        return Select(**variables)

    def update(self, to_update: Document) -> 'Update':
        return Update(
            collection=self.collection,
            filter=self.filter or {},
            update=to_update,
        )


@dataclass(frozen=True)
class Update(query.Update):
    collection: str
    filter: t.Mapping[str, t.Any]
    update: t.Optional[Document] = None
    one: bool = False
    replacement: t.Optional[Document] = None

    @cached_property
    def table(self):
        return self.collection

    @cached_property
    def select_ids(self) -> Select:
        return Select(
            collection=self.collection,
            filter=self.filter,
            projection={'_id': 1},
        )

    @cached_property
    def select(self) -> Select:
        return Select(
            collection=self.collection,
            filter=self.filter,
            projection={'_id': 1},
        )


@dataclass(frozen=True)
class Delete(query.Delete):
    collection: str
    filter: t.Mapping[str, t.Any]
    one: bool = False

    @cached_property
    def table(self):
        return self.collection


@dataclass(frozen=False)
class Insert(query.Insert):
    collection: str
    ordered: bool = True
    bypass_document_validation: bool = False

    @cached_property
    def table(self):
        return self.collection

    @cached_property
    def select_table(self) -> Select:
        return Select(collection=self.collection, filter={})


def set_one_key_in_document(table, id, key, value):
    return Update(
        collection=table,
        filter={'_id': id},
        update={'$set': {key: value}},
        one=True,
    )
