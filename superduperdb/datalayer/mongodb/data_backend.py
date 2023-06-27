import typing as t

from bson import ObjectId
from pymongo import UpdateOne
from pymongo.cursor import Cursor
from pymongo import results

from pinnacledb.core.documents import Document
from pinnacledb.datalayer.base.data_backend import BaseDataBackend
from pinnacledb.datalayer.mongodb.query import Delete, Update, Select, Insert
from pinnacledb.misc.special_dicts import MongoStyleDict
from pinnacledb.misc.logger import logging


class MongoDataBackend(BaseDataBackend):
    select_cls = Select
    id_field = '_id'

    def __init__(
        self,
        conn: t.Any,
        name: t.Optional[str] = None,
    ):
        super().__init__(conn, name)
        self.db = conn[name]

    def insert(self, insert: Insert) -> results.InsertManyResult:
        encoded = [r.encode() for r in insert.documents]
        return self.db[insert.collection].insert_many(
            encoded,
            ordered=insert.ordered,
            bypass_document_validation=insert.bypass_document_validation,
        )

    def download_update(self, table, id, key, bytes) -> Update:
        return Update(
            collection=table,
            one=True,
            filter={'_id': id},
            update=Document({'$set': {f'{key}._content.bytes': bytes}}),
        )

    def get_ids_from_select(self, select: Select) -> t.List[str]:
        return [
            r['_id'] for r in self.db[select.collection].find(select.filter, {'_id': 1})
        ]

    def get_output_from_document(
        self, r: Document, key: str, model: str
    ) -> MongoStyleDict:
        return (
            MongoStyleDict(r.content)[f'_outputs.{key}.{model}'],  # type: ignore
            r.content['_id'],  # type: ignore
        )

    def get_raw_cursor(self, select: Select) -> Cursor:
        return Cursor(
            self.db[select.collection],
            select.filter,
            select.projection,
            **select.kwargs,
        )

    def set_content_bytes(self, r, key, bytes_) -> MongoStyleDict:
        if not isinstance(r, MongoStyleDict):
            r = MongoStyleDict(r)
        r[f'{key}._content.bytes'] = bytes_
        return r

    def _add_features(self, r):
        r = MongoStyleDict(r)
        for k in self.features:
            r[k] = r['_outputs'][k][self.features[k]]
        if '_other' in r:
            for k in self.features:
                if k in r['_other']:
                    r['_other'][k] = r['_outputs'][k][self.features[k]]
        return r

    def write_outputs(self, watcher_info, outputs, _ids) -> None:
        logging.info('bulk writing...')
        select = Select(**watcher_info['select'])
        if watcher_info.get('target') is None:
            out_key = f'_outputs.{watcher_info["key"]}.{watcher_info["model"]}'
        else:
            out_key = watcher_info['target']

        self.db[select.collection].bulk_write(
            [
                UpdateOne(
                    {'_id': ObjectId(id)},
                    {'$set': {out_key: outputs[i]}},
                )
                for i, id in enumerate(_ids)
            ]
        )
        logging.info('done.')

    def update(self, update: Update) -> results.UpdateResult:
        row = self.db[update.collection]
        if update.replacement is not None:
            return row.replace_one(update.filter, update.replacement.encode())

        assert update.update is not None
        if update.one:
            return row.update_one(update.filter, update.update.encode())
        else:
            return row.update_many(update.filter, update.update.encode())

    def delete(self, delete: Delete) -> results.DeleteResult:
        if delete.one:
            return self.db[delete.collection].delete_one(delete.filter)
        else:
            return self.db[delete.collection].delete_many(delete.filter)

    def unset_outputs(self, info: t.Dict) -> results.UpdateResult:
        select = Select(**info['select'])
        logging.info(f'unsetting output field _outputs.{info["key"]}.{info["model"]}')
        doc = {'$unset': {f'_outputs.{info["key"]}.{info["model"]}': 1}}

        # doc = Document(doc)
        # TODO: The above looks like it should be correct, and fixes the mypy error, but
        # not passing in the dict breaks two unit tests!

        update = select.update(doc)  # type: ignore
        return self.db[select.collection].update_many(update.filter, update.update)
