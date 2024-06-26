import pytest

from pinnacledb.base.document import Document

from .mock_client import curl_get, curl_post, curl_put, setup as _setup, teardown


@pytest.fixture
def setup():
    yield _setup()
    teardown()


def test_select_data(setup):
    result = curl_post('/db/execute', data={'query': 'coll.find({}, {"_id": 0})'})
    if 'error' in result:
        raise Exception(result['messages'] + result['traceback'])
    print(result)
    assert len(result) == 2


CODE = """
from pinnacledb import code

@code
def my_function(x):
    return x + 1
"""


def test_apply(setup):
    m = {
        '_builds': {
            'function_body': {
                '_path': 'pinnacledb.base.code.Code',
                'code': CODE,
            },
            'my_function': {
                '_path': 'pinnacledb.components.model.ObjectModel',
                'object': '?function_body',
                'identifier': 'my_function',
            },
        },
        '_base': '?my_function',
    }

    _ = curl_post(
        endpoint='/db/apply',
        data=m,
    )

    models = curl_get('/db/show', params={'type_id': 'model'})

    assert models == ['my_function']


def test_insert_image(setup):
    result = curl_put(
        endpoint='/db/artifact_store/put',
        file='test/material/data/test.png',
        media_type='image/png',
    )

    file_id = result['file_id']

    query = {
        '_path': 'pinnacledb.backends.mongodb.query.parse_query',
        'query': 'coll.insert_one(documents[0])',
        '_builds': {
            'image_type': {
                '_path': 'pinnacledb.ext.pillow.encoder.image_type',
                'encodable': 'artifact',
            },
            'my_artifact': {
                '_path': 'pinnacledb.components.datatype.LazyArtifact',
                'blob': f'&:blob:{file_id}',
                'datatype': "?image_type",
            },
        },
        'documents': [
            {
                'img': '?my_artifact',
            }
        ],
    }

    result = curl_post(
        endpoint='/db/execute',
        data=query,
    )

    query = {
        '_path': 'pinnacledb.backends.mongodb.query.parse_query',
        'query': 'coll.find(documents[0], documents[1])',
        'documents': [{}, {'_id': 0}],
    }

    result = curl_post(
        endpoint='/db/execute',
        data=query,
    )

    from pinnacledb import pinnacle

    db = pinnacle()

    result = [Document.decode(r[0], db=db).unpack() for r in result]

    assert len(result) == 3

    image_record = next(r for r in result if 'img' in r)

    from PIL.PngImagePlugin import PngImageFile

    assert isinstance(image_record['img'], PngImageFile)
