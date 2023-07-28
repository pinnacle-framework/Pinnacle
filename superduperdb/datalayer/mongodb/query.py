from bson import ObjectId
from pymongo import UpdateOne as _UpdateOne
import random
import typing as t
import dataclasses as dc

import pinnacledb as s
from pinnacledb.core.document import Document
from pinnacledb.core.serializable import Serializable
from pinnacledb.datalayer.base.cursor import SuperDuperCursor
from pinnacledb.datalayer.base.query import Select, SelectOne, Insert, Delete, Update
from pinnacledb.datalayer.base.query import Like


@dc.dataclass
class Collection(Serializable):
    name: str

    @property
    def table(self):
        return self.name

    def count_documents(self, *args, **kwargs):
        return CountDocuments(collection=self, args=list(args), kwargs=kwargs)

    def like(
        self,
        r: Document,
        vector_index: str,
        n: int = 100,
    ):
        return PreLike(collection=self, r=r, vector_index=vector_index, n=n)

    def insert_one(self, *args, refresh=True, encoders=(), **kwargs):
        return InsertMany(
            collection=self,
            documents=[args[0]],
            args=list(args[1:]),
            kwargs=kwargs,
            refresh=refresh,
            encoders=encoders,
        )

    def insert_many(self, *args, refresh=True, encoders=(), **kwargs):
        return InsertMany(
            collection=self,
            encoders=encoders,
            documents=args[0],
            args=list(args[1:]),
            refresh=refresh,
            kwargs=kwargs,
        )

    def delete_one(self, *args, **kwargs):
        return DeleteOne(collection=self, args=list(args), kwargs=kwargs)

    def delete_many(self, *args, **kwargs):
        return DeleteMany(collection=self, args=list(args), kwargs=kwargs)

    def update_one(self, *args, **kwargs):
        return UpdateOne(
            collection=self,
            filter=args[0],
            update=args[1],
            args=list(args),
            kwargs=kwargs,
        )

    def update_many(self, *args, **kwargs):
        return UpdateMany(
            collection=self,
            filter=args[0],
            update=args[1],
            args=list(args[2:]),
            kwargs=kwargs,
        )

    def find(self, *args, **kwargs):
        return Find(collection=self, args=list(args), kwargs=kwargs)

    def find_one(self, *args, **kwargs):
        return FindOne(collection=self, args=list(args), kwargs=kwargs)

    def aggregate(self, *args, **kwargs):
        return Aggregate(collection=self, args=list(args), kwargs=kwargs)

    def replace_one(self, *args, **kwargs):
        return ReplaceOne(
            collection=self,
            filter=args[0],
            update=args[1],
            args=list(args),
            kwargs=kwargs,
        )

    def change_stream(self, *args, **kwargs):
        return ChangeStream(collection=self, args=list(args), kwargs=kwargs)


@dc.dataclass
class ReplaceOne(Update):
    collection: Collection
    filter: t.Dict
    update: Document
    refresh: bool = True
    verbose: bool = True
    args: t.Sequence = dc.field(default_factory=list)
    kwargs: t.Dict = dc.field(default_factory=dict)

    type_id: t.Literal['mongodb.ReplaceOne'] = 'mongodb.ReplaceOne'

    @property
    def select_table(self):
        raise NotImplementedError

    def __call__(self, db):
        update = self.update.encode()
        return db.db[self.collection.name].replace_one(
            self.filter, update, *self.args[2:], **self.kwargs
        )

    def select(self):
        return Find(parent=self.collection, args=[self.args[0]])

    @property
    def select_ids(self):
        return Find(parent=self.collection, args=[self.args[0]]).select_ids


@dc.dataclass
class PreLike(Like):
    r: Document
    vector_index: str
    collection: Collection
    n: int = 100

    type_id: t.Literal['mongodb.PreLike'] = 'mongodb.PreLike'

    @property
    def table(self):
        return self.collection.name

    def find(self, *args, **kwargs):
        return Find(like_parent=self, args=args, kwargs=kwargs)

    def find_one(self, *args, **kwargs):
        return FindOne(like_parent=self, args=args, kwargs=kwargs)

    def __call__(self, db):
        ids, scores = db._select_nearest(
            like=self.r, vector_index=self.vector_index, n=self.n
        )
        cursor = db.db[self.collection.name].find(
            {'_id': {'$in': [ObjectId(_id) for _id in ids]}}
        )
        return SuperDuperCursor(
            raw_cursor=cursor,
            scores=dict(zip(ids, scores)),
            id_field='_id',
            encoders=db.encoders,
        )


@dc.dataclass
class Find(Select):
    collection: t.Optional[Collection] = None
    like_parent: t.Optional[PreLike] = None
    args: t.Sequence = dc.field(default_factory=lambda: [])
    kwargs: t.Dict = dc.field(default_factory=lambda: {})

    type_id: t.Literal['mongodb.Find'] = 'mongodb.Find'

    @property
    def parent(self):
        if bool(self.like_parent) == bool(self.collection):
            raise ValueError('Exactly one of "like_parent" or "collection" must be set')
        return self.collection if self.like_parent is None else self.like_parent

    @property
    def table(self):
        return self.parent.table

    def limit(self, n: int):
        return Limit(parent=self, n=n)  # type

    def count(self, *args, **kwargs):
        return Count(parent=self, *args, **kwargs)  # type

    def like(
        self, r: Document, vector_index: str = '', n: int = 100, max_ids: int = 1000
    ):
        return PostLike(
            find_parent=self, r=r, n=n, max_ids=max_ids, vector_index=vector_index
        )

    def add_fold(self, fold: str) -> 'Find':
        args = []
        try:
            args.append(self.args[0])
        except IndexError:
            args.append({})
        args.extend(self.args[1:])
        args[0]['_fold'] = fold
        return Find(
            like_parent=self.like_parent,
            collection=self.collection,
            args=args,
            kwargs=self.kwargs,
        )

    def is_trivial(self) -> bool:
        raise NotImplementedError

    @property
    def select_ids(self):
        try:
            filter = self.args[0]
        except IndexError:
            filter = {}
        return Find(
            collection=self.collection,
            like_parent=self.like_parent,
            args=[filter, {'_id': 1}],
        )

    def select_using_ids(self, ids: t.Sequence[str]) -> t.Any:
        args = [*self.args, {}, {}][:2]
        args[0] = {'_id': {'$in': [ObjectId(_id) for _id in ids]}, **args[0]}

        return Find(
            collection=self.collection,
            like_parent=self.like_parent,
            args=args,
            kwargs=self.kwargs,
        )

    def featurize(self, features):
        return Featurize(parent=self, features=features)

    def get_ids(self, db):
        args = [{}, {}]
        args[: len(self.args)] = self.args
        args[1] = {'_id': 1}
        cursor = Find(
            collection=self.collection,
            like_parent=self.like_parent,
            args=args,
            kwargs=self.kwargs,
        )(db)
        return [r['_id'] for r in cursor]

    def model_update(self, db, model, key, outputs, ids):
        if key.startswith('_outputs'):
            key = key.split('.')[1]

        db.db[self.collection.name].bulk_write(
            [
                _UpdateOne(
                    {'_id': ObjectId(id)},
                    {'$set': {f'_outputs.{key}.{model}': outputs[i]}},
                )
                for i, id in enumerate(ids)
            ]
        )

    def model_cleanup(self, db, model, key):
        db.db[self.collection.name].update_many(
            {}, {'$unset': {f'_outputs.{key}.{model}': 1}}
        )

    @property
    def select_table(self):
        return Find(parent=self.parent)

    def download_update(self, db, id, key, bytes):
        return UpdateOne(
            collection=self.collection,
            filter={'_id': id},
            update={'$set': {f'{key}._content.bytes': bytes}},
        )(db)

    # ruff: noqq: E501
    def __call__(self, db):
        if isinstance(self.parent, Collection):
            cursor = db.db[self.collection.name].find(  # type: ignore[union-attr]
                *self.args, **self.kwargs
            )  #  type: ignore[union-attr]
        elif isinstance(self.parent, Like):  # type: ignore[union-attr]
            intermediate = self.parent(db)
            ids = [ObjectId(r['_id']) for r in intermediate]
            try:
                filter = self.args[0]  # type: ignore[index]
            except IndexError:  # type: ignore[index]
                filter = {}
            filter = {'$and': [filter, {'_id': {'$in': ids}}]}  # type: ignore[union-attr]
            cursor = db.db[self.like_parent.collection.name].find(  # type: ignore[index,union-attr]
                filter, *self.args[1:], **self.kwargs  # type: ignore[index]
            )
        else:
            raise NotImplementedError
        return SuperDuperCursor(raw_cursor=cursor, id_field='_id', encoders=db.encoders)


@dc.dataclass
class CountDocuments(Find):
    collection: t.Optional[Collection] = None
    like_parent: t.Optional[PreLike] = None
    args: t.Sequence = dc.field(default_factory=lambda: [])
    kwargs: t.Dict = dc.field(default_factory=lambda: {})

    def __call__(self, db):
        return db.db[self.collection.name].count_documents(*self.args, **self.kwargs)


@dc.dataclass
class FeaturizeOne(SelectOne):
    features: t.Dict[str, str]
    parent_find_one: t.Optional[Find] = None

    type_id: t.Literal['mongodb.FeaturizeOne'] = 'mongodb.FeaturizeOne'

    # ruff: noqa: E501
    def __call__(self, db):
        r = self.parent_find_one(db)  # type: ignore[misc]
        r = SuperDuperCursor.add_features(r.content, self.features)  # type: ignore[misc]
        return Document(r)


@dc.dataclass
class FindOne(SelectOne):
    args: t.Optional[t.Sequence] = dc.field(default_factory=list)
    kwargs: t.Optional[t.Dict] = dc.field(default_factory=dict)
    like_parent: t.Optional[PreLike] = None
    collection: t.Optional[Collection] = None

    type_id: t.Literal['mongodb.FindOne'] = 'mongodb.FindOne'

    def add_fold(self, fold: str) -> 'Select':
        raise NotImplementedError

    def __call__(self, db):
        if self.collection is not None:
            return SuperDuperCursor.wrap_document(
                db.db[self.collection.name].find_one(*self.args, **self.kwargs),
                encoders=db.encoders,
            )
        else:
            parent_cursor = self.like_parent(db)  # type: ignore[misc]
            ids = [r['_id'] for r in parent_cursor]  # type: ignore[misc]
            filter = self.args[0] if self.args else {}
            filter['_id'] = {'$in': ids}
            r = db.db[self.like_parent.collection.name].find_one(  # type: ignore[union-attr]
                filter,  # type: ignore[union-attr]
                *self.args[1:],  # type: ignore[index]
                **self.kwargs,  # type: ignore[index]
            )
            return Document(Document.decode(r, encoders=db.encoders))

    def featurize(self, features):
        return FeaturizeOne(parent_find_one=self, features=features)


@dc.dataclass
class Aggregate(Select):
    collection: Collection
    args: t.Sequence = dc.field(default_factory=list)
    kwargs: t.Dict = dc.field(default_factory=dict)

    type_id: t.Literal['mongodb.Aggregate'] = 'mongodb.Aggregate'

    def add_fold(self, fold: str) -> 'Select':
        raise NotImplementedError

    def is_trivial(self) -> bool:
        raise NotImplementedError

    @property
    def select_ids(self) -> 'Select':
        raise NotImplementedError

    def model_update(self, db, model, key, outputs, ids):
        raise NotImplementedError

    @property
    def select_table(self):
        raise NotImplementedError

    def select_using_ids(
        self,
        ids: t.Sequence[str],
    ) -> t.Any:
        raise NotImplementedError

    def __call__(self, db):
        return SuperDuperCursor(
            id_field='_id',
            raw_cursor=db.db[self.collection.name].aggregate(*self.args, **self.kwargs),
            encoders=db.encoders,
        )


@dc.dataclass
class DeleteOne(Delete):
    collection: Collection
    args: t.Sequence = dc.field(default_factory=list)
    kwargs: t.Dict = dc.field(default_factory=dict)

    type_id: t.Literal['mongodb.DeleteOne'] = 'mongodb.DeleteOne'

    def __call__(self, db):
        return db.db[self.collection.name].delete_one(*self.args, **self.kwargs)


@dc.dataclass
class DeleteMany(Delete):
    collection: Collection
    args: t.Sequence = dc.field(default_factory=list)
    kwargs: t.Dict = dc.field(default_factory=dict)

    type_id: t.Literal['mongodb.DeleteMany'] = 'mongodb.DeleteMany'

    def __call__(self, db):
        return db.db[self.collection.name].delete_many(*self.args, **self.kwargs)


@dc.dataclass
class UpdateOne(Update):
    collection: Collection
    update: Document
    filter: t.Dict
    refresh: bool = True
    verbose: bool = True
    args: t.Sequence = dc.field(default_factory=list)
    kwargs: t.Dict = dc.field(default_factory=dict)

    type_id: t.Literal['mongodb.UpdateOne'] = 'mongodb.UpdateOne'

    def __call__(self, db):
        return db.db[self.collection.name].update_one(
            self.filter,
            self.update,
            *self.args,
            **self.kwargs,
        )

    @property
    def select_table(self):
        raise NotImplementedError

    @property
    def select(self):
        return Find(collection=self.collection, args=[self.args[0]])

    @property
    def select_ids(self):
        raise NotImplementedError


@dc.dataclass
class UpdateMany(Update):
    collection: Collection
    filter: t.Dict
    update: Document
    refresh: bool = True
    verbose: bool = True
    args: t.Sequence = dc.field(default_factory=list)
    kwargs: t.Dict = dc.field(default_factory=dict)

    type_id: t.Literal['mongodb.UpdateMany'] = 'mongodb.UpdateMany'

    def __call__(self, db):
        to_update = self.update.encode()
        ids = [
            r['_id'] for r in db.db[self.collection.name].find(self.filter, {'_id': 1})
        ]
        out = db.db[self.collection.name].update_many(
            {'_id': {'$in': ids}},
            to_update,
            *self.args[2:],
            **self.kwargs,
        )
        graph = None
        if self.refresh and not s.CFG.cdc:
            graph = db.refresh_after_update_or_insert(
                query=self, ids=ids, verbose=self.verbose
            )
        return out, graph

    @property
    def select_table(self):
        return Find(collection=self.collection, args=[{}])

    @property
    def select_ids(self):
        raise NotImplementedError

    @property
    def select(self):
        return Find(parent=self.args[0])


@dc.dataclass
class InsertMany(Insert):
    collection: Collection
    refresh: bool = True
    verbose: bool = True
    args: t.Sequence = dc.field(default_factory=list)
    kwargs: t.Dict = dc.field(default_factory=dict)
    encoders: t.Sequence = dc.field(default_factory=list)

    type_id: t.Literal['mongodb.InsertMany'] = 'mongodb.InsertMany'

    @property
    def table(self):
        return self.collection.name

    @property
    def select_table(self):
        return Find(collection=self.collection)

    def select_using_ids(self, ids):
        return Find(collection=self.collection, args=[{'_id': {'$in': ids}}])

    def __call__(self, db):
        valid_prob = self.kwargs.get('valid_prob', 0.05)
        for e in self.encoders:
            db.add(e)
        documents = [r.encode() for r in self.documents]
        for r in documents:
            if '_fold' in r:
                continue
            if random.random() < valid_prob:
                r['_fold'] = 'valid'
            else:
                r['_fold'] = 'train'
        output = db.db[self.collection.name].insert_many(
            documents,
            *self.args,
            **self.kwargs,
        )
        graph = None
        if self.refresh and not s.CFG.cdc:
            graph = db.refresh_after_update_or_insert(
                query=self,  # type: ignore[arg-type]
                ids=output.inserted_ids,
                verbose=self.verbose,
            )
        return output, graph


@dc.dataclass
class PostLike(Select):
    find_parent: t.Optional[Find]
    r: Document
    vector_index: str
    n: int = 100
    max_ids: int = 1000

    type_id: t.Literal['mongodb.PostLike'] = 'mongodb.PostLike'

    class Config:
        arbitrary_types_allowed = True
        # TODO: the server will crash when it tries to JSONize whatever it is that
        # this allows.

    def __call__(self, db):
        cursor = self.find_parent.select_ids.limit(self.max_ids)(db)  # type: ignore[union-attr]
        ids = [r['_id'] for r in cursor]  # type: ignore[union-attr]
        ids, scores = db._select_nearest(
            like=self.r,
            vector_index=self.vector_index,
            n=self.n,
            ids=[str(_id) for _id in ids],
        )
        ids = [ObjectId(_id) for _id in ids]
        # ruff: noqa: E501
        return Find(
            collection=self.find_parent.collection, args=[{'_id': {'$in': ids}}]  # type: ignore[union-attr]
        )(db)

    def add_fold(self, fold: str) -> 'Select':
        raise NotImplementedError

    def is_trivial(self) -> bool:
        raise NotImplementedError

    @property
    def select_ids(self) -> 'Select':
        raise NotImplementedError

    def model_update(self, db, model, key, outputs, ids):
        raise NotImplementedError

    @property
    def select_table(self):
        raise NotImplementedError

    def select_using_ids(
        self,
        ids: t.Sequence[str],
    ) -> t.Any:
        raise NotImplementedError


@dc.dataclass
class Featurize(Select):
    features: t.Dict[str, str]
    parent: t.Union[PreLike, Find, PostLike]
    type_id: t.Literal['mongodb.Featurize'] = 'mongodb.Featurize'

    @property
    def select_table(self):
        return self.parent.select_table

    def get_ids(self, *args, **kwargs):
        return self.parent.get_ids(*args, **kwargs)

    def is_trivial(self):
        return self.parent.is_trivial()

    @property
    def select_ids(self):
        return self.parent.select_ids

    # ruff: noqa: E501
    def add_fold(self, fold: str):
        return self.parent.add_fold(fold).featurize(self.features)  # type: ignore[union-attr]

    # ruff: noqa: E501
    def select_using_ids(self, ids: t.Sequence[str]) -> t.Any:
        return self.parent.select_using_ids(ids=ids).featurize(features=self.features)  # type: ignore[union-attr]

    def model_update(self, *args, **kwargs):
        return self.parent.model_update(*args, **kwargs)

    def __call__(self, db):
        if (
            isinstance(self.parent, Find)
            or isinstance(self.parent, Limit)
            or isinstance(self.parent, Like)
        ):
            out = self.parent(db)
            out.features = self.features
            return out
        else:
            r = self.parent(db)
            r = SuperDuperCursor.add_features(r.content, self.features)
            return Document(r)


@dc.dataclass
class Count(SelectOne):
    parent: t.Union[Find, PostLike, PreLike, Featurize]
    type_id: t.Literal['mongodb.Count'] = 'mongodb.Count'
    args: t.Sequence = dc.field(default_factory=list)
    kwargs: t.Dict = dc.field(default_factory=dict)

    def __call__(self, db):
        return db[self.parent.name].count_documents()

    def add_fold(self, fold: str) -> 'Select':
        raise NotImplementedError

    def is_trivial(self) -> bool:
        raise NotImplementedError

    def select_using_ids(
        self,
        ids: t.Sequence[str],
    ) -> t.Any:
        raise NotImplementedError

    def model_update(self, db, model, key, outputs, ids):
        raise NotImplementedError

    @property
    def select_ids(self) -> 'Select':
        raise NotImplementedError

    @property
    def select_table(self):
        raise NotImplementedError


@dc.dataclass
class Limit(Select):
    n: int
    parent: t.Union[Find, PostLike, PreLike, Featurize]
    type_id: t.Literal['mongodb.Limit'] = 'mongodb.Limit'

    def __call__(self, db):
        return self.parent(db).limit(self.n)

    def add_fold(self, fold: str) -> 'Select':
        raise NotImplementedError

    def is_trivial(self) -> bool:
        raise NotImplementedError

    def select_using_ids(
        self,
        ids: t.Sequence[str],
    ) -> t.Any:
        raise NotImplementedError

    def model_update(self, db, model, key, outputs, ids):
        raise NotImplementedError

    @property
    def select_ids(self) -> 'Select':
        raise NotImplementedError

    @property
    def select_table(self):
        raise NotImplementedError


@dc.dataclass
class ChangeStream:
    collection: Collection
    args: t.Sequence = dc.field(default_factory=list)
    kwargs: t.Dict = dc.field(default_factory=dict)

    def __call__(self, db):
        collection = db.db[self.collection.name]
        return collection.watch(**self.kwargs)

    @property
    def select_ids(self) -> 'Select':
        raise NotImplementedError

    def model_update(self, db, model, key, outputs, ids):
        raise NotImplementedError

    @property
    def select_table(self):
        raise NotImplementedError

    def select_using_ids(
        self,
        ids: t.Sequence[str],
    ) -> t.Any:
        raise NotImplementedError


all_items = {
    'Aggregate': Aggregate,
    'Collection': Collection,
    'DeleteMany': DeleteMany,
    'DeleteOne': DeleteOne,
    'Featurize': Featurize,
    'Find': Find,
    'FindOne': FindOne,
    'InsertMany': InsertMany,
    'PreLike': PreLike,
    'PostLike': PostLike,
    'Limit': Limit,
    'UpdateOne': UpdateOne,
    'UpdateMany': UpdateMany,
}
