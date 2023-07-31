import typing as t

from pymongo.results import DeleteResult, InsertOneResult, UpdateResult

from pinnacledb.core.component import Component
from pinnacledb.datalayer.base.metadata import MetaDataStore


class MongoMetaDataStore(MetaDataStore):
    def __init__(
        self,
        conn: t.Any,
        name: t.Optional[str] = None,
    ) -> None:
        self.name = name
        db = conn[name]
        self.meta_collection = db['_meta']
        self.object_collection = db['_objects']
        self.job_collection = db['_jobs']
        self.parent_child_mappings = db['_parent_child_mappings']

    def create_parent_child(self, parent: str, child: str) -> None:
        self.parent_child_mappings.insert_one(
            {
                'parent': parent,
                'child': child,
            }
        )

    def create_component(self, info: t.Dict) -> InsertOneResult:
        if 'hidden' not in info:
            info['hidden'] = False
        return self.object_collection.insert_one(info)

    def create_job(self, info: t.Dict) -> InsertOneResult:
        return self.job_collection.insert_one(info)

    def get_parent_child_relations(self):
        c = self.parent_child_mappings.find()
        return [(r['parent'], r['child']) for r in c]

    def get_component_version_children(self, unique_id: str):
        return self.parent_child_mappings.distinct('child', {'parent': unique_id})

    def get_job(self, identifier: str):
        return self.job_collection.find_one({'identifier': identifier})

    def get_metadata(self, key: str):
        return self.meta_collection.find_one({'key': key})['value']

    def get_latest_version(
        self, variety: str, identifier: str, allow_hidden: bool = False
    ) -> int:
        try:
            if allow_hidden:
                return sorted(
                    self.object_collection.distinct(
                        'version', {'identifier': identifier, 'variety': variety}
                    )
                )[-1]
            else:
                return sorted(
                    self.object_collection.distinct(
                        'version',
                        {
                            '$or': [
                                {
                                    'identifier': identifier,
                                    'variety': variety,
                                    'hidden': False,
                                },
                                {
                                    'identifier': identifier,
                                    'variety': variety,
                                    'hidden': {'$exists': 0},
                                },
                            ]
                        },
                    )
                )[-1]
        except IndexError:
            raise FileNotFoundError(f'Can\'t find {variety}: {identifier} in metadata')

    def update_job(self, identifier: str, key: str, value: t.Any) -> UpdateResult:
        return self.job_collection.update_one(
            {'identifier': identifier}, {'$set': {key: value}}
        )

    def show_components(self, variety: str, **kwargs) -> t.List[t.Union[t.Any, str]]:
        return self.object_collection.distinct(
            'identifier', {'variety': variety, **kwargs}
        )

    def show_component_versions(
        self, variety: str, identifier: str
    ) -> t.List[t.Union[t.Any, int]]:
        return self.object_collection.distinct(
            'version', {'variety': variety, 'identifier': identifier}
        )

    def list_components_in_scope(self, scope: str):
        out = []
        for r in self.object_collection.find({'parent': scope}):
            out.append((r['variety'], r['identifier']))
        return out

    def show_jobs(self, status=None):
        status = {} if status is None else {'status': status}
        return list(
            self.job_collection.find(
                status, {'identifier': 1, '_id': 0, 'method': 1, 'status': 1, 'time': 1}
            )
        )

    def _component_used(
        self, variety: str, identifier: str, version: t.Optional[int] = None
    ) -> bool:
        if version is None:
            return bool(
                self.object_collection.count_documents(
                    {'members': {'$regex': f'^{identifier}/{variety}'}}
                )
            )
        else:
            return bool(
                self.object_collection.count_documents(
                    {'members': Component.make_unique_id(variety, identifier, version)}
                )
            )

    def component_has_parents(self, variety: str, identifier: str):
        return (
            self.parent_child_mappings.count_documents(
                {'child': {'$regex': f'^{variety}/{identifier}/'}}
            )
            > 0
        )

    def component_version_has_parents(
        self, variety: str, identifier: str, version: int
    ) -> bool:
        return (
            self.parent_child_mappings.count_documents(
                {'child': Component.make_unique_id(variety, identifier, version)}
            )
            > 0
        )

    def delete_component_version(
        self, variety: str, identifier: str, version: int
    ) -> DeleteResult:
        if self._component_used(variety, identifier, version=version):
            raise Exception('Component version already in use in other components!')

        self.parent_child_mappings.delete_many(
            {'parent': Component.make_unique_id(variety, identifier, version)}
        )

        return self.object_collection.delete_many(
            {
                'identifier': identifier,
                'variety': variety,
                'version': version,
            }
        )

    def _get_component(
        self,
        variety: str,
        identifier: str,
        version: int,
        allow_hidden: bool = False,
    ) -> t.Dict[str, t.Any]:
        if not allow_hidden:
            r = self.object_collection.find_one(
                {
                    '$or': [
                        {
                            'identifier': identifier,
                            'variety': variety,
                            'version': version,
                            'hidden': False,
                        },
                        {
                            'identifier': identifier,
                            'variety': variety,
                            'version': version,
                            'hidden': {'$exists': 0},
                        },
                    ]
                }
            )
        else:
            r = self.object_collection.find_one(
                {
                    'identifier': identifier,
                    'variety': variety,
                    'version': version,
                },
            )
        return r

    def get_component_version_parents(self, unique_id: str) -> t.List[str]:
        return [
            r['parent'] for r in self.parent_child_mappings.find({'child': unique_id})
        ]

    def _replace_object(
        self,
        info: t.Dict[str, t.Any],
        identifier: str,
        variety: str,
        version: int,
    ) -> None:
        self.object_collection.replace_one(
            {'identifier': identifier, 'variety': variety, 'version': version},
            info,
        )

    def _update_object(
        self,
        identifier: str,
        variety: str,
        key: str,
        value: t.Any,
        version: int,
    ):
        return self.object_collection.update_one(
            {'identifier': identifier, 'variety': variety, 'version': version},
            {'$set': {key: value}},
        )

    def write_output_to_job(self, identifier, msg, stream):
        if stream not in ('stdout', 'stderr'):
            raise ValueError(f'stream is "{stream}", should be stdout or stderr')
        self.job_collection.update_one(
            {'identifier': identifier}, {'$push': {stream: msg}}
        )

    def hide_component_version(
        self, variety: str, identifier: str, version: int
    ) -> None:
        self.object_collection.update_one(
            {'variety': variety, 'identifier': identifier, 'version': version},
            {'$set': {'hidden': True}},
        )
