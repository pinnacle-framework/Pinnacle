import math

import gridfs
import torch
from pymongo import UpdateOne
from pymongo.database import Database as MongoDatabase
import pinnacledb.mongodb.collection
from pinnacledb.database import BaseDatabase
from pinnacledb.lookup import hashes
from pinnacledb.mongodb import loading
from pinnacledb.training.validation import validate_representations
from pinnacledb.utils import MongoStyleDict, progressbar


class Database(MongoDatabase, BaseDatabase):
    """
    Database building on top of :code:`pymongo.database.Database`. Collections in the
    database are SuperDuperDB objects :code:`pinnacledb.collection.Collection`.
    """

    _database_type = 'mongodb'

    def __init__(self, *args, **kwargs):
        MongoDatabase.__init__(self, *args, **kwargs)
        BaseDatabase.__init__(self)
        self._filesystem = None
        self._filesystem_name = f'_{self.name}:files'

    def __getitem__(self, name: str):
        if name != '_validation_sets' and name.startswith('_'):
            return super().__getitem__(name)
        return pinnacledb.mongodb.collection.Collection(self, name)

    @property
    def filesystem(self):
        if self._filesystem is None:
            self._filesystem = gridfs.GridFS(
                self.client[self._filesystem_name]
            )
        return self._filesystem

    def _add_split_to_row(self, r, other):
        r['_other'] = other
        return r

    def create_imputation(self, identifier, model, model_key, target, target_key, collection, filter_=None,
                          objective=None, metrics=None, projection=None,
                          splitter=None, watch=True, loader_kwargs=None, **trainer_kwargs):
        if 'loader_suppress' not in trainer_kwargs:
            trainer_kwargs['loader_suppress'] = []
        if '_id' not in trainer_kwargs['loader_suppress']:
            trainer_kwargs['loader_suppress'].append('_id')

        query_params = [collection, filter_ or {}]
        if projection is not None:
            query_params.append(projection)

        return self._create_imputation(
            identifier, model, model_key, target, target_key, query_params,
            objective=objective, metrics=metrics,
            splitter=splitter, watch=watch, loader_kwargs=loader_kwargs, **trainer_kwargs
        )

    def _create_job_record(self, r):
        self['_jobs'].insert_one(r)

    def _create_object_entry(self, info):
        return self['_objects'].insert_one(info)

    def create_semantic_index(self, identifier, models, keys, measure, collection, validation_sets=(),
                              metrics=(), objective=None, filter_=None, splitter=None,
                              projection=None,
                              loader_kwargs=None, **trainer_kwargs):
        query_params = [collection]
        if filter_ is None:
            query_params.append({})
        else:
            query_params.append(filter_)
        if projection is not None:
            query_params.append(projection)
        if 'loader_suppress' not in trainer_kwargs:
            trainer_kwargs['loader_suppress'] = []
        if '_id' not in trainer_kwargs['loader_suppress']:
            trainer_kwargs['loader_suppress'].append('_id')
        return self._create_semantic_index(identifier, query_params, models, keys, measure,
                                           validation_sets=validation_sets,
                                           metrics=metrics, objective=objective,
                                           splitter=splitter, loader_kwargs=loader_kwargs,
                                           **trainer_kwargs)

    def create_watcher(self, identifier, model, collection, filter_=None, projection=None,
                       key='_base', verbose=False,
                       target=None, process_docs=True, features=None, loader_kwargs=None,
                       dependencies=()):

        query_params = [collection]
        if filter_ is None:
            query_params.append({})
        else:
            query_params.append(filter_)
        if projection is not None:
            query_params.append(projection)

        return self._create_watcher(identifier, model, query_params=query_params, key=key,
                                      verbose=verbose, target=target, process_docs=process_docs,
                                      features=features, loader_kwargs=loader_kwargs,
                                      dependencies=dependencies)

    def create_validation_set(self, identifier, collection, filter_, chunk_size=1000,
                              splitter=None, sample_size=None):
        if filter_ is None:
            filter_ = {}
        if sample_size is not None:
            sample = self[collection].aggregate([
                {'$match': filter_},
                {'$sample': {'size': sample_size}},
                {'$project': {'_id': 1}}
            ])
            _ids = [r['_id'] for r in sample]
            filter_['_id'] = {'$in': _ids}
        return super()._create_validation_set(identifier, collection, filter_, chunk_size=chunk_size,
                                              splitter=splitter)

    def _delete_object_info(self, identifier, variety):
        return self['_objects'].delete_one({'identifier': identifier, 'variety': variety})

    def _download_update(self, collection, _id, key, bytes_):
        self[collection].update_one({'_id': _id}, {'$set': {f'{key}._content.bytes': bytes_}})

    def _execute_query_to_get_hashes(self, *query_params):
        query_params = list(query_params)
        if len(query_params) >= 3:
            query_params[2]['_id'] = 1
        return self.execute_query(*query_params)

    def execute_query(self, collection, filter_, *args, **kwargs):
        return self[collection].find(filter_, *args, **kwargs)

    def _get_docs_from_ids(self, _ids, *query_params, features=None, raw=False):
        query_params = list(query_params)
        if query_params[1:]:
            query_params[1] = {'_id': {'$in': _ids}, **query_params[1]}
        else:
            query_params.append({})
        return list(self[query_params[0]].find(*query_params[1:],
                                               features=features,
                                               raw=raw))

    def _get_hash_from_record(self, r, watcher_info):
        return MongoStyleDict(r)[f'_outputs.{watcher_info["key"]}.{watcher_info["model"]}']

    def get_ids_from_result(self, query_params, result):
        _ids = []
        for r in result:
            _ids.append(r['_id'])
        return _ids

    def _get_ids_from_query(self, *query_params):
        collection, filter_ = query_params[:2]
        _ids = [r['_id'] for r in self[collection].find(filter_, {'_id': 1})]
        return _ids

    def _get_job_info(self, identifier):
        return self['_jobs'].find_one({'identifier': identifier})

    def get_meta_data(self, **kwargs):
        return self['_meta'].find_one(kwargs)['value']

    def get_object_info(self, identifier, variety):
        return self['_objects'].find_one({'identifier': identifier, 'variety': variety})

    def get_query_params_for_validation_set(self, validation_set):
        return ('_validation_sets', {'identifier': validation_set})

    def _insert_validation_data(self, tmp, identifier):
        tmp = [{**r, 'identifier': identifier} for r in tmp]
        self['_validation_sets'].insert_many(tmp)

    def list_jobs(self, status=None):
        status = {} if status is None else {'status': status}
        return list(self['_jobs'].find(status, {'identifier': 1, '_id': 0, 'method': 1,
                                                'status': 1, 'time': 1}))

    def _list_objects(self, variety):
        return self['_objects'].distinct('identifier', {'variety': variety})

    def list_validation_sets(self):
        """
        List validation sets
        :return: list of validation sets
        """
        return self['_validation_sets'].distinct('identifier')

    def _load_blob_of_bytes(self, file_id):
        return loading.load(file_id, filesystem=self.filesystem)

    def _replace_object(self, file_id, new_file_id, variety, identifier):
        self.filesystem.delete(file_id)
        self['_objects'].update_one({
            'identifier': identifier,
            'variety': variety,
        }, {'$set': {'object': new_file_id}})

    def _save_blob_of_bytes(self, bytes_):
        return loading.save(bytes_, self.filesystem)

    def save_metrics(self, identifier, variety, metrics):
        self['_objects'].update_one({'identifier': identifier, 'variety': variety},
                                    {'$set': {'metric_values': metrics}})

    def separate_query_part_from_validation_record(self, r):
        return r['_other'], {k: v for k, v in r.items() if k != '_other'}

    def _set_content_bytes(self, r, key, bytes_):
        if not isinstance(r, MongoStyleDict):
            r = MongoStyleDict(r)
        r[f'{key}._content.bytes'] = bytes_
        return r

    def _unset_neighbourhood_data(self, info, watcher_info):
        collection, filter_ = watcher_info['query_params']
        print(f'unsetting neighbourhood {info["info"]}')
        self[collection].update_many(filter_, {'$unset': {f'_like.{info["identifier"]}': 1}},
                                     refresh=False)

    def _unset_watcher_outputs(self, info):
        collection, filter_ = info['query_params']
        print(f'unsetting output field _outputs.{info["key"]}.{info["model"]}')
        self[collection].update_many(
            filter_,
            {'$unset': {f'_outputs.{info["key"]}.{info["model"]}': 1}},
            refresh=False
        )

    def _update_neighbourhood(self, ids, similar_ids, identifier, *query_params):
        collection = self[query_params[0]]
        collection.bulk_write([
            UpdateOne({'_id': id_}, {'$set': {f'_like.{identifier}': sids}})
            for id_, sids in zip(ids, similar_ids)
        ])

    def _update_object_info(self, identifier, variety, key, value):
        self['_objects'].update_one(
            {'identifier': identifier, 'variety': variety},
            {'$set': {key: value}}
        )

    def validate_semantic_index(self, name, validation_sets, metrics):
        results = {}
        features = self['_objects'].find_one({'name': name,
                                              'variety': 'semantic_index'}).get('features')
        for vs in validation_sets:
            results[vs] = validate_representations(self, vs, name, metrics, features=features)

        for vs in results:
            for m in results[vs]:
                self['_objects'].update_one(
                    {'name': name, 'variety': 'semantic_index'},
                    {'$set': {f'final_metrics.{vs}.{m}': results[vs][m]}}
                )

    def _write_watcher_outputs(self, watcher_info, outputs, ids):
        collection = watcher_info['query_params'][0]
        key = watcher_info.get('key', '_base')
        model_name = watcher_info['model']
        print('bulk writing...')
        if watcher_info.get('target') is None:
            self[collection].bulk_write([
                UpdateOne({'_id': id},
                          {'$set': {f'_outputs.{key}.{model_name}': outputs[i]}})
                for i, id in enumerate(ids)
            ])
        else:  # pragma: no cover
            self[collection].bulk_write([
                UpdateOne({'_id': id},
                          {'$set': {
                              watcher_info['target']: outputs[i]
                          }})
                for i, id in enumerate(ids)
            ])
        print('done.')
