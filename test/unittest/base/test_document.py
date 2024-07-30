import dataclasses as dc
import pprint
import typing as t

import pytest

from pinnacle.backends.mongodb.query import MongoQuery
from pinnacle.base.constant import KEY_BLOBS, KEY_BUILDS
from pinnacle.components.datatype import Artifact, DataType
from pinnacle.components.model import ObjectModel
from pinnacle.components.schema import Schema
from pinnacle.components.table import Table
from pinnacle.ext.pillow.encoder import image_type, pil_image

try:
    import torch

    from pinnacle.ext.torch.encoder import tensor
except ImportError:
    torch = None

from pinnacle.base.document import Document


@pytest.fixture
def document():
    t = tensor(dtype='float', shape=(20,))
    yield Document({'x': t(torch.randn(20))})


@dc.dataclass
class _db:
    datatypes: t.Dict


@pytest.mark.skipif(not torch, reason='Torch not installed')
def test_document_encoding(document):
    t = tensor(dtype='float', shape=(20,))
    new_document = Document.decode(
        document.encode(), getters={'component': lambda x: t}
    )
    assert (new_document['x'].x - document['x'].x).sum() == 0


def test_flat_query_encoding():
    q = MongoQuery(table='docs').find({'a': 1}).limit(2)

    r = q._deep_flat_encode({}, {}, {})

    doc = Document({'x': 1})

    q = MongoQuery(table='docs').like(doc, vector_index='test').find({'a': 1}).limit(2)

    r = q._deep_flat_encode({}, {}, {})

    print(r)


def test_encode_decode_flattened_document():
    import PIL.Image

    from pinnacle.ext.pillow.encoder import image_type

    schema = Schema(
        'my-schema', fields={'img': image_type(identifier='png', encodable='artifact')}
    )

    img = PIL.Image.open('test/material/data/test.png')

    r = Document(
        {
            'x': 2,
            'img': img,
        },
        schema=schema,
    )

    encoded_r = r.encode()

    import yaml

    print(yaml.dump({k: v for k, v in encoded_r.items() if k != KEY_BLOBS}))

    assert not isinstance(encoded_r, Document)
    assert isinstance(encoded_r, dict)
    assert KEY_BUILDS in encoded_r
    assert KEY_BLOBS in encoded_r
    assert encoded_r['img'].startswith('&:blob:')
    assert isinstance(next(iter(encoded_r[KEY_BLOBS].values())), bytes)


def test_encode_model():
    m = ObjectModel(
        identifier='test',
        object=lambda x: x + 2,
    )

    encoded_r = m.encode()

    pprint.pprint(encoded_r)

    decoded_r = Document.decode(
        encoded_r, getters={'blob': lambda x: encoded_r[KEY_BLOBS][x]}
    )

    print(decoded_r)

    m = decoded_r.unpack()

    assert isinstance(m, ObjectModel)
    assert isinstance(m.object, Artifact)

    pprint.pprint(m)

    r = m.dict()

    assert isinstance(r, Document)
    assert {'version', 'hidden', 'type_id', '_path'}.issubset(set(r.keys()))

    print(r)

    pprint.pprint(m.dict().encode())


def test_decode_inline_data():
    import PIL.Image

    from pinnacle.ext.pillow.encoder import image_type

    it = image_type(identifier='png', encodable='artifact')

    schema = Schema('my-schema', fields={'img': it})

    img = PIL.Image.open('test/material/data/test.png')

    r = {
        'x': 2,
        'img': it.encoder(img),
    }

    r = Document.decode(r, schema=schema).unpack()
    print(r)


def test_refer_to_applied_item(db):
    dt = DataType(identifier='my-type', encodable='artifact')
    db.apply(dt)

    m = ObjectModel(
        identifier='test',
        object=lambda x: x + 2,
        datatype=dt,
    )

    db.apply(m)
    r = db.metadata.get_component_by_uuid(m.uuid)

    assert r['datatype'].startswith('&:component:datatype:my-type')

    import pprint

    pprint.pprint(r)

    print(db.show('datatype'))
    dt = db.load('datatype', 'my-type', 0)
    print(dt)
    c = db.load('model', 'test')
    print(c)


def test_column_encoding(db):
    import PIL

    img = PIL.Image.open('test/material/data/test.png')
    schema = Schema(
        'test',
        fields={
            'id': int,
            'x': int,
            'y': int,
            'img': pil_image,
        },
    )

    db.apply(Table('test', schema=schema))

    import PIL.Image

    img = PIL.Image.open('test/material/data/test.png')

    db['test'].insert(
        [
            Document({'id': 1, 'x': 1, 'y': 2, 'img': img}),
            Document({'id': 2, 'x': 3, 'y': 4, 'img': img}),
        ]
    ).execute()

    db['test'].select().execute()


def test_refer_to_system(db):
    image = image_type(identifier='image', encodable='artifact')
    db.apply(image)

    import PIL.Image
    import PIL.PngImagePlugin

    img = PIL.Image.open('test/material/data/test.png')

    db.artifact_store.put_bytes(db.datatypes['image'].encoder(img), file_id='12345')

    r = {
        '_builds': {
            'my_artifact': {
                '_path': 'pinnacle.components.datatype.LazyArtifact',
                'blob': '&:blob:12345',
                'datatype': "&:component:datatype:image",
            }
        },
        'img': '?my_artifact',
    }

    r = Document.decode(r, db=db).unpack()

    assert isinstance(r['img'], PIL.PngImagePlugin.PngImageFile)
