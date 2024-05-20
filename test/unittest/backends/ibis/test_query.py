import tempfile
from pinnacledb.base.document import Document
from test.db_config import DBConfig

import numpy
import pandas
import pytest

from pinnacledb import pinnacle
from pinnacledb.backends.ibis.field_types import dtype
from pinnacledb.components.model import ObjectModel
from pinnacledb.components.schema import Schema
from pinnacledb.ext.numpy.encoder import array
from pinnacledb.ext.pillow.encoder import pil_image

try:
    import torch
except ImportError:
    torch = None


def test_serialize_table():
    schema = Schema(
        identifier='my_table',
        fields={
            'id': dtype('int64'),
            'health': dtype('int32'),
            'age': dtype('int32'),
            'image': pil_image,
        },
    )

    s = schema.encode()
    print(s)
    ds = Document.decode(s).unpack()

    print(ds)

    t = Table(identifier='my_table', schema=schema)

    s = t.encode()
    ds = Document.decode(s).unpack()

    print(ds)


@pytest.fixture
def duckdb(monkeypatch):
    with tempfile.TemporaryDirectory() as d:
        from pinnacledb import CFG
        from pinnacledb.base.config import Cluster

        monkeypatch.setattr(CFG, 'cluster', Cluster())
        db = pinnacle(f'duckdb://{d}/test.ddb')

        _, t = db.add(
            Table(
                'test',
                primary_id='id',
                schema=Schema(
                    'my-schema',
                    fields={'x': dtype(str), 'id': dtype(str)},
                ),
            )
        )

        db.execute(
            t.insert(
                pandas.DataFrame([{'x': f'test::{i}', 'id': str(i)} for i in range(20)])
            )
        )

        model = ObjectModel(
            object=lambda _: numpy.random.randn(32),
            identifier='test',
            datatype=array('float64', shape=(32,)),
        )
        output_table = db.databackend.create_output_dest('test::0', model.datatype)
        db.add(output_table)
        model.predict_in_db('x', select=t, db=db, predict_id='test::0')

        _, s = db.add(
            Table(
                'other',
                primary_id='other_id',
                schema=Schema(
                    'my-schema',
                    fields={'y': dtype(str), 'other_id': dtype(str), 'id2': dtype(str)},
                ),
            )
        )

        db.execute(
            s.insert(
                pandas.DataFrame(
                    [
                        {'y': f'test2::{i}', 'other_id': str(i // 2), 'id2': str(i)}
                        for i in range(40)
                    ]
                )
            )
        )

        yield db


def test_auto_inference_primary_id():
    s = IbisQueryTable('other', primary_id='other_id')
    t = IbisQueryTable('test', primary_id='id')

    q = t.join(s, t.id == s.other_id)

    assert q.primary_id == ['id', 'other_id']

    q = t.join(s, t.id == s.other_id).group_by('id')

    assert q.primary_id == 'other_id'


def test_renamings(duckdb):
    t = duckdb.load('table', 'test')
    q = t.outputs('test::0')
    print(q)
    data = duckdb.execute(t.outputs('test::0'))
    assert isinstance(data[0]['_outputs.test::0'], numpy.ndarray)


def test_serialize_deserialize():
    from pinnacledb.backends.ibis.query import IbisQuery

    t = IbisQuery(
        'test', primary_id='id', schema=Schema('my-schema', fields={'x': dtype(str)})
    )

    q = t.filter(t.id == 1).select(t.id, t.x)

    print(Document.decode(q.encode()).unpack())


@pytest.mark.skipif(not torch, reason='Torch not installed')
@pytest.mark.parametrize(
    "db",
    [
        (DBConfig.sqldb_data, {'n_data': 500}),
    ],
    indirect=True,
)
def test_add_fold(db):
    table = db.load('table', 'documents')
    select_train = table.select('id', 'x', '_fold').add_fold('train')
    result_train = db.execute(select_train)

    select_valid = table.select('id', 'x', '_fold').add_fold('valid')
    result_vaild = db.execute(select_valid)
    assert len(result_train) + len(result_vaild) == 500


@pytest.mark.skipif(not torch, reason='Torch not installed')
@pytest.mark.parametrize(
    "db",
    [
        (DBConfig.sqldb_data, {'n_data': 500}),
    ],
    indirect=True,
)
def test_get_data(db):
    q = db['documents'].limit(2)
    r = db.metadata.get_component('table', 'documents')