import dataclasses as dc
import inspect
import typing as t
import uuid

import click
import requests
from pinnacledb.core.artifact_tree import (
    get_artifacts,
    replace_artifacts_with_dict,
    load_artifacts,
)
from pinnacledb.core.component import Component
from pinnacledb.core.documents import Document
from pinnacledb.core.serializable import Serializable
from pinnacledb.datalayer.base.database import ExecuteQuery
from pinnacledb.datalayer.base.query import (
    Delete,
    Insert,
    Like,
    Select,
    SelectOne,
    Update,
)
from pinnacledb.misc.serialization import serializers


class ClientArtifactStore:
    def __init__(self, get, put, request_id):
        self.request_id = request_id
        self.get = get
        self.put = put

    def load_artifact(self, file_id, serializer, info=None):
        bytes = self.get(self.request_id, file_id)
        if info in inspect.signature(serializers[serializer]).parameters:
            return serializers[serializer].decode(bytes, info=info)
        else:
            return serializers[serializer].decode(bytes)

    def create_artifact(self, bytes):
        d = self.put(self.request_id, bytes).json()
        return d['file_id'], d['sha1']


class Client:
    def __init__(self, uri):
        self.uri = uri
        self.encoders = LoadDict(self, 'encoder')

    def execute(self, query: ExecuteQuery):
        if isinstance(query, Delete):
            return self.delete(query)
        if isinstance(query, Insert):
            return self.insert(query)
        if isinstance(query, Select):
            return self.select(query)
        if isinstance(query, Like):
            return self.like(query)
        if isinstance(query, SelectOne):
            return self.select_one(query)
        if isinstance(query, Update):
            return self.update(query)
        raise TypeError(
            f'Wrong type of {query}; '
            f'Expected object of type {t.Union[Select, Delete, Update, Insert]}; '
            f'Got {type(query)};'
        )

    def select(self, query: Select):
        request_id = str(uuid.uuid4())
        response = self._make_get_request(
            'select',
            json={
                'query': query.serialize(),
                'request_id': request_id,
            },
        ).json()
        result = self._get(request_id=request_id, file_id=response['file_id'])
        documents = Document.load_bsons(result, encoders=self.encoders)
        return documents

    def insert(self, query: Insert):
        documents = Document.dump_bsons(query.documents)
        query.documents = None
        serialized = query.serialize()
        file_id = str(uuid.uuid4())
        request_id = str(uuid.uuid4())
        self._put(request_id=request_id, file_id=file_id, data=documents)
        return self._make_post_or_put_request(
            'insert',
            method='POST',
            json={
                'query': serialized,
                'documents': file_id,
                'request_id': request_id,
            },
        )

    def delete(self, query: Delete):
        self._make_post_or_put_request(
            'delete', method='POST', json={'query': query.serialize()}
        )
        return 'ok'

    def _get(self, request_id, file_id):
        response = self._make_get_request(
            f'artifacts/get/{request_id}/{file_id}',
        )
        return response.content

    def _put(self, request_id, file_id, data):
        response = self._make_post_or_put_request(
            f'artifacts/put/{request_id}/{file_id}',
            method='PUT',
            data=data,
        )
        return response.text

    def add(self, component: Component):
        request_id = str(uuid.uuid4())
        d = component.serialize()
        artifacts = set(get_artifacts(d))
        lookup = {a: str(uuid.uuid4()) for a in artifacts}
        serializers = {lookup[a]: a.serializer for a in artifacts}
        d = replace_artifacts_with_dict(d, lookup)
        request_id = str(uuid.uuid4())
        for a in artifacts:
            self._put(
                request_id=request_id,
                file_id=lookup[a],
                data=a.serialize(),
            )
        self._make_post_or_put_request(
            'add',
            method='POST',
            json={
                'component': d,
                'serializers': serializers,
                'request_id': request_id,
            },
        )

    def show(
        self,
        variety: str,
        identifier: t.Optional[str] = None,
        version: t.Optional[int] = None,
    ):
        return self._make_get_request(
            'show',
            json={
                'variety': variety,
                'identifier': identifier,
                'version': version,
            },
        ).json()

    def remove(
        self,
        variety: str,
        identifier: str,
        version: t.Optional[int] = None,
        force: bool = False,
    ):
        version_str = '' if version is None else f'/{version}'

        if not force and not click.confirm(
            f'You are about to delete {variety}/{identifier}{version_str}'
            ', are you sure?',
            default=False,
        ):
            print('aborting...')
            return

        self._make_post_or_put_request(
            'remove',
            method='POST',
            json={
                'variety': variety,
                'identifier': identifier,
                'version': version,
            },
        )

    def load(self, variety: str, identifier: str, version: t.Optional[int] = None):
        request_id = str(uuid.uuid4())
        d = self._make_get_request(
            'load',
            json={
                'variety': variety,
                'identifier': identifier,
                'version': version,
                'request_id': request_id,
            },
        ).json()
        d = load_artifacts(
            d, getter=lambda x: self._get(request_id=request_id, file_id=x), cache={}
        )
        return Serializable.deserialize(d)

    def select_one(self, query: SelectOne) -> t.Dict:
        request_id = str(uuid.uuid4())
        response = self._make_get_request(
            'select_one',
            json={
                'query': query.serialize(),
                'request_id': request_id,
            },
        ).json()
        result = self._get(request_id=request_id, file_id=response['file_id'])
        return Document.load_bson(result, encoders=self.encoders)

    def like(self, query: Like):
        like = Document.dump_bson(query.like)
        query.like = None
        serialized = query.serialize()
        file_id = str(uuid.uuid4())
        request_id = str(uuid.uuid4())
        self._put(request_id=request_id, file_id=file_id, data=like)
        out = self._make_get_request(
            'like',
            json={
                'query': serialized,
                'like': file_id,
                'request_id': request_id,
            },
        ).json
        results = self._get(request_id=request_id, file_id=out['file_id'])
        return Document.load_bsons(results, encoders=self.encoders)

    def update(self, query: Update):
        update = Document.dump_bson(query.update)
        file_id = str(uuid.uuid4())
        request_id = str(uuid.uuid4())
        self._put(request_id=request_id, file_id=file_id, data=update)
        query.update = None
        query.serialize()
        return self._make_post_or_put_request(
            'update',
            method='POST',
            json={
                'query': query.serialize(),
                'update': file_id,
                'request_id': request_id,
            },
        )

    def _make_get_request(
        self,
        route: str,
        params: t.Optional[t.Dict] = None,
        json: t.Optional[t.Dict] = None,
    ):
        response = requests.get(f'{self.uri}/{route}', params=params, json=json)
        if response.status_code != 200:
            raise ServerSideException(
                f'Non 200 status while making request to'
                f' /{route} with params {params} and json {json}:\n'
                f'{response.text}'
            )
        return response

    def _make_post_or_put_request(
        self,
        route: str,
        method: str,
        json: t.Optional[t.Dict] = None,
        data: t.Optional[t.Dict] = None,
    ):
        if method not in ['PUT', 'POST']:
            raise ServerSideException('Only PUT or POST methods are supported')
        fn = getattr(requests, method.lower())
        response = fn(
            f'{self.uri}/{route}',
            data=data,
            json=json,
        )
        if response.status_code != 200:
            raise ServerSideException(
                f'Non 200 status while making request to'
                f' /{route} with json {json}:\n'
                f'{response.text}'
            )
        return response


class ServerSideException(ValueError):
    pass


@dc.dataclass
class LoadDict(dict):
    client: Client
    field: str

    def __missing__(self, key: str):
        value = self[key] = self.client.load(self.field, key)
        return value
