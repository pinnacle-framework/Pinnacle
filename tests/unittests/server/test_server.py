from .test_registry import setup_registry
from fastapi.testclient import TestClient
from pinnacledb.server.server import Server
import io
import json
import pinnacledb as s


def setup_test_client():
    server = Server()
    test = setup_registry(server.register)

    test.client = TestClient(server.app)
    test.object = test.Object()
    test.server = server

    server.add_endpoints(test.object)

    return test


def test_basics():
    with setup_test_client().client as client:
        response = client.get('/')
        assert response.status_code == 200
        assert response.text == s.CFG.server.fastapi.title

        response = client.get('/health')
        assert response.status_code == 200
        assert response.text == 'ok'

        response = client.get('/stats')
        assert response.status_code == 200
        assert response.json() == {}


def test_methods():
    with setup_test_client().client as client:
        response = client.post('/first', json={'one': 'three'})
        assert response.status_code == 200
        assert response.json() == {'one': 'three', 'two': 'two'}


def test_execute():
    with setup_test_client().client as client:
        response = client.post('/execute?method=first', json=[{'one': 'three'}])
        assert response.status_code == 200, json.dumps(response.json(), indent=2)
        assert response.json() == {'one': 'three', 'two': 'two'}


class One(s.JSONable):
    one = 'one'


class Two(One):
    two = 'two'


class Three(One):
    two = 'three'


class Object:
    def first(self, one: One) -> Two:
        return Two(**one.dict())

    def second(self, one: One, three: Three) -> One:
        return one


def test_auto_register():
    obj = Object()
    server = Server()
    server.auto_register(obj)
    server.add_endpoints(obj)
    with TestClient(server.app) as client:
        response = client.post('/execute?method=first', json=[{'one': 'three'}])
        assert response.status_code == 200, json.dumps(response.json(), indent=2)
        assert response.json() == {'one': 'three', 'two': 'two'}


def test_download():
    test = setup_test_client()

    blob = bytes(range(256))
    test.server.artifact_store['test-key'] = blob

    with TestClient(test.server.app) as client:
        response = client.get('/download/test-key')
        assert response.status_code == 200
        assert response.content == blob


def test_upload():
    test = setup_test_client()

    blob = bytes(range(256))

    with TestClient(test.server.app) as client:
        fp = io.BytesIO(blob)
        files = {'file': ('test-key', fp, 'multipart/form-data')}
        response = client.post('/upload/test-key', files=files)
        assert response.status_code == 200, json.dumps(response.json(), indent=2)
        assert response.json() == {'created': 'test-key'}

        fp = io.BytesIO(blob)
        files = {'file': ('test-key', fp, 'multipart/form-data')}
        response = client.post('/upload/test-key', files=files)
        assert response.status_code == 200, json.dumps(response.json(), indent=2)
        assert response.json() == {'replaced': 'test-key'}

        response = client.get('/download/test-key')
        assert response.status_code == 200
        assert response.content == blob
