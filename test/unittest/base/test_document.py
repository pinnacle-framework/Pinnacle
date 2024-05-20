import dataclasses as dc
import pprint
import typing as t
from pinnacledb.components.datatype import LazyArtifact
from pinnacledb.components.schema import Schema
from test.db_config import DBConfig

import pytest

from pinnacledb.backends.mongodb.query import Collection
from pinnacledb.components.model import ObjectModel
from pinnacledb.components.vector_index import vector

try:
    import torch

    from pinnacledb.ext.torch.encoder import tensor
except ImportError:
    torch = None

from pinnacledb.base.document import Document, _build_leaves


@pytest.fixture
def document():
    t = tensor(torch.float, shape=(20,))
    yield Document({'x': t(torch.randn(20))})


@dc.dataclass
class _db:
    datatypes: t.Dict


@pytest.mark.skipif(not torch, reason='Torch not installed')
def test_document_encoding(document):
    t = tensor(torch.float, shape=(20,))
    db = _db(datatypes={'torch.float32[20]': t})
    new_document = Document.decode(document.encode(), db)
    assert (new_document['x'].x - document['x'].x).sum() == 0


def test_flat_query_encoding():
    q = Collection('docs').find({'a': 1}).limit(2)

    r = q._deep_flat_encode(None)

    doc = Document({'x': 1})

    q = Collection('docs').like(doc, vector_index='test').find({'a': 1}).limit(2)

    r = q._deep_flat_encode(None)

    print(r)


def test_encode_decode_flattened_document():
    from pinnacledb.ext.pillow.encoder import image_type
    import PIL.Image

    schema = Schema('my-schema', fields={'img': image_type(identifier='png', encodable='artifact')})

    img = PIL.Image.open('test/material/data/test.png')

    r = Document(
        {
            'x': 2,
            'img': img,
        },
        schema=schema,
    )

    encoded_r = r.deep_flat_encode()

    import yaml
    print(yaml.dump({k: v for k, v in encoded_r.items() if k != '_blobs'}))

    assert not isinstance(encoded_r, Document)
    assert isinstance(encoded_r, dict)
    assert '_leaves' in encoded_r
    assert '_blobs' in encoded_r
    assert isinstance(encoded_r['img'], str)
    assert encoded_r['img'].startswith('?artifact')
    assert isinstance(next(iter(encoded_r['_blobs'].values())), bytes)

    decoded_r = Document.deep_flat_decode(encoded_r).unpack()

    pprint.pprint(decoded_r)


def test_encode_model():

    m = ObjectModel(
        'test',
        object=lambda x: x + 2,
    )

    encoded_r = m.deep_flat_encode()

    pprint.pprint(encoded_r)

    decoded_r = Document.deep_flat_decode(encoded_r)

    print(decoded_r)

    m = decoded_r.unpack()

    assert isinstance(m, ObjectModel)
    assert isinstance(m.object, LazyArtifact)

    pprint.pprint(m)

    r = m.dict()

    assert isinstance(r, Document)
    assert {'version', 'hidden', 'type_id', '_path'}.issubset(set(r.keys()))

    print(r)

    pprint.pprint(m.dict().deep_flat_encode())


def test_decode_inline_data():
    from pinnacledb.ext.pillow.encoder import image_type
    import PIL.Image

    it = image_type(identifier='png', encodable='artifact')

    schema = Schema('my-schema', fields={'img': it})

    img = PIL.Image.open('test/material/data/test.png')

    r = {
        'x': 2,
        'img': it.encoder(img),
    }

    r = Document.deep_flat_decode(r, schema=schema).unpack()
    print(r)


def test_refer_to_applied_item():
    ...