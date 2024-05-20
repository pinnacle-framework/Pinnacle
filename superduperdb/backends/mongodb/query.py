import dataclasses as dc
import copy
import typing as t
from collections import defaultdict
from pinnacledb import logging

from bson import ObjectId
import pymongo

from pinnacledb.backends.base.query import (
    Query,
    applies_to,
    parse_query as _parse_query,
)
from pinnacledb.base.cursor import SuperDuperCursor
from pinnacledb.base.document import Document, QueryUpdateDocument
from pinnacledb.base.leaf import Leaf
from pinnacledb.misc.special_dicts import SuperDuperFlatEncode

if t.TYPE_CHECKING:
    from pinnacledb.base.datalayer import Datalayer


def parse_query(query, documents, db: t.Optional['Datalayer'] = None):
    """Parse a string query into a query object.

    :param query: The query to parse.
    :param documents: The documents to query.
    :param db: The datalayer to use to execute the query.
    """
    return _parse_query(
        query=query,
        documents=documents,
        builder_cls=MongoQuery,
        db=db,
    )

@dc.dataclass
class ChangeStream:
    """Change stream class to watch for changes in specified collection.

    :param collection: The collection to perform the query on
    :param args: Positional query arguments to ``pymongo.Collection.watch``
    :param kwargs: Named query arguments to ``pymongo.Collection.watch``
    """

    collection: str
    args: t.Sequence = dc.field(default_factory=list)
    kwargs: t.Dict = dc.field(default_factory=dict)

    def __call__(self, db):
        """Watch for changes in the database in specified collection.

        :param db: The datalayer instance
        """
        collection = db.databackend.get_table_or_collection(self.collection)
        return collection.watch(**self.kwargs)


@dc.dataclass(kw_only=True, repr=False)
class MongoQuery(Query):
    """A query class for MongoDB.

    This class is used to build and execute queries on a MongoDB database.
    """

    flavours: t.ClassVar[t.Dict[str, str]] = {
        'pre_like': '^.*\.like\(.*\)\.find',
        'post_like': '^.*\.find\(.*\)\.like(.*)$',
        'bulk_write': '^.*\.bulk_write\(.*\)$',
        'find_one': '^.*\.find_one\(.*\)',
        'find': '^.*\.find\(.*\)',
        'insert_many': '^.*\.insert_many\(.*\)$',
        'insert_one': '^.*\.insert_one\(.*\)$',
        'replace_one': '^.*\.replace_one\(.*\)$',
        'update_many': '^.*\.update_many\(.*\)$',
        'update_one': '^.*\.update_one\(.*\)$',
        'delete_many': '^.*\.delete_many\(.*\)$',
        'delete_one': '^.*\.delete_one\(.*\)$',
    }

    metholds_mapping: t.ClassVar[t.Dict[str, str]] = {
        "insert": "insert_many",
        "select": "find",
    }

    def _create_table_if_not_exists(self):
        return

    def _deep_flat_encode(self, cache, blobs, files, leaves_to_keep=(), schema=None):
        r = super()._deep_flat_encode(
            cache, blobs, files, leaves_to_keep=leaves_to_keep, schema=schema
        )
        cache[r[1:]]['_path'] = 'pinnacledb/backends/mongodb/query/parse_query'
        return r

    @property
    def type(self):
        """Return the type of the query."""
        return defaultdict(
            lambda: 'select',
            {
                'update_many': 'update',
                'update_one': 'update',
                'delete_many': 'delete',
                'delete_one': 'delete',
                'bulk_write': 'write',
                'insert_many': 'insert',
                'insert_one': 'insert',
                'outputs': 'outputs',
            },
        )[self.flavour]

    def _prepare_inputs(self, inputs):
        if isinstance(inputs, BulkOp):
            return inputs.op
        if isinstance(inputs, (list, tuple)):
            return [self._prepare_inputs(i) for i in inputs]
        if isinstance(inputs, dict):
            return {k: self._prepare_inputs(v) for k, v in inputs.items()}
        return inputs

    def _execute_delete_one(self, parent):
        r = next(self.select_ids.limit(1)._execute(parent))
        self.table_or_collection.delete_one({'_id': r['_id']})._execute(parent)
        return [str(r['_id'])]

    def _execute_delete_many(self, parent):
        id_cursor = self.select_ids._execute(parent)
        ids = [r['_id'] for r in id_cursor]
        if not ids:
            return {}
        self.table_or_collection.delete_many({'_id': {'$in': ids}})._execute(parent)
        return [str(id) for id in ids]

    def _execute(self, parent, method='encode'):
        c = super()._execute(parent, method=method)
        import mongomock
        import pymongo

        if isinstance(c, (pymongo.cursor.Cursor, mongomock.collection.Cursor)):
            return SuperDuperCursor(
                raw_cursor=c,
                db=self.db,
                id_field='_id',
            )
        return c

    def _execute_pre_like(self, parent):
        assert self.parts[0][0] == 'like'
        assert self.parts[1][0] in ['find', 'find_one']

        similar_ids, similar_scores = self._prepare_pre_like(parent)

        find_args = self.parts[1][1]
        find_kwargs = self.parts[1][2]
        if find_args == ():
            find_args = ({},)

        find_args[0]['_id'] = {'$in': [ObjectId(id) for id in similar_ids]}

        q = type(self)(
            db=self.db,
            identifier=self.identifier,
            parts=[(self.parts[1][0], tuple(find_args), find_kwargs), *self.parts[2:]],
        )
        result = q.do_execute(db=self.db)
        result.scores = similar_scores
        return result


    def _execute_post_like(self, parent):
        assert len(self.parts) == 2
        assert self.parts[0][0] == 'find'
        assert self.parts[1][0] == 'like'

        find_args = self.parts[0][1]
        find_kwargs = self.parts[0][2]

        like_args = self.parts[1][1]

        like_kwargs = self.parts[1][2]
        r = like_args[0] or like_kwargs.pop('r')
        if isinstance(r, Document):
            r = r.unpack()
        range = like_kwargs.pop('range', None)

        parent_query = self[:-1].select_ids
        if range:
            parent_query = parent_query.limit(range)

        relevant_ids = [str(r['_id']) for r in parent_query.do_execute()]

        similar_ids, scores = self.db.select_nearest(
            like=r,
            ids=relevant_ids,
            vector_index=like_kwargs.pop('vector_index'),
            n=like_kwargs.get('n', 100),
        )
        scores = dict(zip(similar_ids, scores))
        similar_ids = [ObjectId(id) for id in similar_ids]

        final_args = find_args[:]
        if not final_args:
            final_args = [{}]
        final_args[0]['_id'] = {'$in': similar_ids}

        final_query = self.table_or_collection.find(*final_args, **find_kwargs)
        result = final_query._execute(parent)

        result.scores = scores
        return result
    def _execute_bulk_write(self, parent):
        """Execute the query.

        :param db: The datalayer instance
        """
        assert self.parts[0][0] == 'bulk_write'
        operations = self.parts[0][1][0]
        for query in operations:
            assert isinstance(query, (BulkOp))
            if not query.kwargs.get('arg_ids', None):
                raise ValueError(
                    'Please provided update/delete id in args',
                    'all ids selection e.g `\{\}` is not supported',
                    )

        collection = self.db.databackend.get_table_or_collection(
            self.table_or_collection.identifier
        )
        bulk_operations = []
        bulk_update_ids = []
        bulk_delete_ids = []
        bulk_result = {'delete': [], 'update': []}
        for query in operations:
            operation = query.op

            bulk_operations.append(operation)
            ids = query.kwargs['arg_ids']
            if query.identifier == 'DeleteOne':
                bulk_result['delete'].append({'query': query, 'ids': ids})
                bulk_delete_ids += ids
            else:
                bulk_update_ids += ids
                bulk_result['update'].append({'query': query, 'ids': ids})

        result = collection.bulk_write(bulk_operations)
        if result.deleted_count != bulk_delete_ids:
            logging.warn(
                'Some delete ids are not executed',
                ', hence halting execution',
                'Please note the partially executed operations',
                'wont trigger any `model/listeners` unless CDC is active.',
            )
        elif (result.modified_count + result.upserted_count) != bulk_update_ids:
            logging.warn(
                'Some update ids are not executed',
                ', hence halting execution',
                'Please note the partially executed operations',
                'wont trigger any `model/listeners` unless CDC is active.',
            )
        return bulk_result, bulk_update_ids, bulk_delete_ids


    def _execute_find(self, parent):
        return self._execute(parent, method='unpack')

    def _execute_replace_one(self, parent):
        documents = self.parts[0][1][0]
        trailing_args = list(self.parts[0][1][1:])
        kwargs = self.parts[0][2]

        schema = kwargs.pop('schema', None)

        replacement = trailing_args[0]
        if isinstance(replacement, Document):
            replacement = replacement.encode(schema)
        trailing_args[0] = replacement

        q = self.table_or_collection.replace_one(documents, *trailing_args, **kwargs)
        q._execute(parent)

    def _execute_find_one(self, parent):
        r = self._execute(parent, method='unpack')
        if r is None:
            return
        return Document.decode(r, db=self.db)

    def _execute_insert_one(self, parent):
        insert_part = self.parts[0]
        parts = self.parts[1:]
        insert_part = (insert_part[0], [insert_part[1]], insert_part[2])

        self.parts = [insert_part] + parts
        return self._execute_insert_many(parent)

    def _execute_insert_many(self, parent):
        trailing_args = self.parts[0][1][1:]
        kwargs = self.parts[0][2]
        documents = self._prepare_documents()
        q = self.table_or_collection.insert_many(documents, *trailing_args, **kwargs)
        result = q._execute(parent)
        return result.inserted_ids

    def _execute_insert(self, parent):
        """Provide a unified insertion interface."""
        return self._execute_insert_many(parent)

    def _execute_update_many(self, parent):
        ids = [r['_id'] for r in self.select_ids._execute(parent)]
        filter = self.parts[0][1][0]
        trailing_args = list(self.parts[0][1][1:])
        update = {}

        # Encode update document
        for ix, arg in enumerate(trailing_args):
            if '$set' in arg:
                if isinstance(arg, Document):
                    update = QueryUpdateDocument.from_document(arg)
                else:
                    update = arg
                del trailing_args[ix]
                break

        kwargs = self.parts[0][2]
        filter['_id'] = {'$in': ids}
        trailing_args.insert(0, update.encode())

        parent.update_many(filter, *trailing_args, **kwargs)
        return ids

    def change_stream(self, *args, **kwargs):
        '''
        Return a callable Mongodb change stream instance.
        '''
        return ChangeStream(collection=self.identifier, args=args, kwargs=kwargs)

    @applies_to('find')
    def outputs(self, *predict_ids):
        """Return a query that selects the outputs of the given predict ids.

        :param *predict_ids: The ids of the predictions to select.
        """
        find_args, find_kwargs = self.parts[0][1:]
        find_args = list(find_args)

        if not find_args:
            find_args = [{}]

        if not find_args[1:]:
            find_args.append({})
        for identifier in predict_ids:
            find_args[1][f'_outputs.{identifier}'] = 1
            find_args[1]['_leaves'] = 1
            find_args[1]['_files'] = 1
            find_args[1]['_blobs'] = 1
        x = type(self)(
            db=self.db,
            identifier=self.identifier,
            parts=[
                ('find', tuple(find_args), find_kwargs),
                *self.parts[1:],
            ],
        )
        return x

    @applies_to('find')
    def add_fold(self, fold: str):
        """Return a query that adds a fold to the query.

        :param fold: The fold to add.
        """
        find_args, find_kwargs = self.parts[0][1:]
        find_args = list(find_args)
        if not find_args:
            find_args = [{}]
        find_args[0]['_fold'] = fold
        return type(self)(
            db=self.db,
            identifier=self.identifier,
            parts=[
                ('find', tuple(find_args), find_kwargs),
                *self.parts[1:],
            ],
        )

    @property
    @applies_to('insert_many', 'insert_one')
    def documents(self):
        """Return the documents to insert."""
        if self.parts[0][0] == 'insert_many':
            return self.parts[0][1][0]
        return [self.parts[0][1][0]]

    @property
    def primary_id(self):
        """Return the primary id of the documents."""
        return '_id'

    def select_using_ids(self, ids: t.Sequence[str]):
        """Return a query that selects using the given ids.

        :param ids: The ids to select.
        """
        if self.parts == () or isinstance(self.parts[0], str):
            args, kwargs = (), {}
        else:
            args, kwargs = self.parts[0][1:]
        args = list(args)[:]
        if not args:
            args = [{}]
        args[0]['_id'] = {'$in': [ObjectId(id) for id in ids]}
        return type(self)(
            db=self.db,
            identifier=self.identifier,
            parts=[
                ('find', args, kwargs),
                *self.parts[1:],
            ],
        )

    @property
    @applies_to('find', 'update_many', 'delete_many', 'delete_one')
    def select_ids(self):
        """Select the ids of the documents."""
        filter_ = {}
        if self.parts[0][1]:
            filter_ = self.parts[0][1][0]
        projection = {'_id': 1}
        coll = type(self)(identifier=self.identifier, db=self.db)
        return coll.find(filter_, projection)

    @property
    def table_or_collection(self):
        """Return the table or collection to select from."""
        return type(self)(identifier=self.identifier, db=self.db)

    @applies_to('find')
    def select_ids_of_missing_outputs(self, predict_id: str):
        """Select the ids of documents that are missing the given output.

        :param predict_id: The id of the prediction.
        """
        args, kwargs = self.parts[0][1:]
        if args:
            args = [
                {
                    '$and': [
                        args[0],
                        {f'_outputs.{predict_id}': {'$exists': 0}},
                    ]
                },
                *args[1:],
            ]
        else:
            args = [{f'_outputs.{predict_id}': {'$exists': 0}}]

        if len(args) == 1:
            args.append({})
        args[1] = {'_id': 1}

        return self.table_or_collection.find(*args, **kwargs)

    @property
    @applies_to('find')
    def select_single_id(self, id: str):
        """Return a query that selects a single id.

        :param id: The id to select.
        """
        args, kwargs = self.parts[0][1:]
        args = list(self.args)[:]
        if not args:
            args[0] = {}
        args[0]['_id'] = ObjectId(id)
        return type(self)(
            db=self.db, identifier=self.identifier, parts=[('find_one', args, kwargs)]
        )

    @property
    def select_table(self):
        """Return the table or collection to select from."""
        return self.table_or_collection.find()

    def model_update(
        self,
        ids: t.List[t.Any],
        predict_id: str,
        outputs: t.Sequence[t.Any],
        flatten: bool = False,
        **kwargs,
    ):
        """Update the model outputs in the database.

        :param ids: The ids of the documents to update.
        :param predict_id: The id of the prediction.
        :param outputs: The outputs to store.
        :param flatten: Whether to flatten the outputs.
        :return: The result of the update operation.
        """
        if not len(outputs):
            return

        document_embedded = kwargs.get('document_embedded', True)
        if document_embedded:
            if flatten:
                raise AttributeError(
                    'Flattened outputs cannot be stored along with input documents.'
                    'Please use `document_embedded = False` option with flatten = True'
                )

            bulk_operations = []
            for i, id in enumerate(ids):
                mongo_filter = {'_id': ObjectId(id)}

                output = outputs[i]

                if isinstance(output, SuperDuperFlatEncode):
                    output = output.get('_base', output)

                update = {f'_outputs.{predict_id}': output}

                update = QueryUpdateDocument._create_metadata_update(update, outputs[i])
                update = Document(update)
                bulk_operations.append(
                    UpdateOne(
                        filter=mongo_filter,
                        update=update,

                    )
                )
            return self.table_or_collection.bulk_write(bulk_operations)
        else:
            collection = MongoQuery(f'_outputs.{predict_id}')
            documents = []
            leaves, blobs, files = {}, {}, {}
            if flatten:
                for i, id in enumerate(ids):
                    _outputs = outputs[i]
                    if isinstance(_outputs, (list, tuple)):
                        for offset, output in enumerate(_outputs):
                            if isinstance(output, SuperDuperFlatEncode):
                                leaves, blobs, files = (
                                    output.pop_leaves(),
                                    output.pop_blobs(),
                                    output.pop_files(),
                                )
                                output = output.get('_base', output)[offset]
                            documents.append(
                                {
                                    '_outputs': {predict_id: output},
                                    '_source': ObjectId(id),
                                    '_offset': offset,
                                    '_leaves': leaves,
                                    '_blobs': blobs,
                                    '_files': files,
                                }
                            )
                    else:
                        output = outputs[i]
                        if isinstance(output, SuperDuperFlatEncode):
                            leaves, blobs, files = (
                                output.pop_leaves(),
                                output.pop_blobs(),
                                output.pop_files(),
                            )
                            output = output.get('_base', output)
                        for o in output:
                            documents.append(
                                {
                                    '_outputs': {predict_id: o},
                                    '_source': ObjectId(id),
                                    '_offset': 0,
                                    '_leaves': leaves,
                                    '_blobs': blobs,
                                    '_files': files,
                                }
                            )

            else:
                for i, id in enumerate(ids):
                    output = outputs[i]
                    if isinstance(output, SuperDuperFlatEncode):
                        leaves, blobs, files = (
                            output.pop_leaves(),
                            output.pop_blobs(),
                            output.pop_files(),
                        )
                        output = output.get('_base', output)
                    documents.append(
                        {
                            '_id': ObjectId(id),
                            '_outputs': {predict_id: output},
                            '_leaves': leaves,
                            '_blobs': blobs,
                            '_files': files,
                        }
                    )

            return collection.insert_many(documents)

    @staticmethod
    def infer_schema(data: t.Mapping[str, t.Any], identifier: t.Optional[str] = None):
        """Infer a schema from a given data object.

        :param data: The data object
        :param identifier: The identifier for the schema, if None, it will be generated
        :return: The inferred schema
        """
        from pinnacledb.misc.auto_schema import infer_schema

        return infer_schema(data, identifier)


def InsertOne(**kwargs):
    """InsertOne operation for MongoDB.

    :param kwargs: The arguments to pass to the operation.
    """
    return BulkOp(identifier='InsertOne', kwargs=kwargs)


def UpdateOne(**kwargs):
    """UpdateOne operation for MongoDB.

    :param kwargs: The arguments to pass to the operation.
    """
    try:
        filter = kwargs['filter']
    except:
        raise KeyError('Filter not found in `UpdateOne`')
    
    id = filter['_id']
    if isinstance(id, ObjectId):
        ids = [id]
    else:
        ids = id['$in']
    kwargs['arg_ids'] = ids
    return BulkOp(identifier='UpdateOne', kwargs=kwargs)


def DeleteOne(**kwargs):
    """DeleteOne operation for MongoDB.

    :param kwargs: The arguments to pass to the operation.
    """
    return BulkOp(identifier='DeleteOne', kwargs=kwargs)


def ReplaceOne(**kwargs):
    """ReplaceOne operation for MongoDB.

    :param kwargs: The arguments to pass to the operation.
    """
    return BulkOp(identifier='ReplaceOne', kwargs=kwargs)


@dc.dataclass(kw_only=True)
class BulkOp(Leaf):
    """A bulk operation for MongoDB.

    :param identifier: The operation to perform.
    :param kwargs: The arguments to pass to the operation.
    """

    ops: t.ClassVar[t.Sequence[str]] = [
        'InsertOne',
        'UpdateOne',
        'DeleteOne',
        'ReplaceOne',
    ]
    identifier: str
    kwargs: t.Dict = dc.field(default_factory=dict)

    def __post_init__(self, db):
        super().__post_init__(db)
        assert self.identifier in self.ops

    @property
    def op(self):
        """Return the operation."""

        kwargs = copy.deepcopy(self.kwargs)
        kwargs.pop('arg_ids')
        for k, v in kwargs.items():
            if isinstance(v, Document):
                kwargs[k] = v.unpack()
        return getattr(pymongo, self.identifier)(**kwargs)

