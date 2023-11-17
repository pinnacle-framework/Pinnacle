import os
import shutil

import numpy
import pandas
import pytest

from pinnacledb import pinnacle
from pinnacledb.backends.ibis.field_types import dtype
from pinnacledb.backends.ibis.query import Table
from pinnacledb.base.serializable import Serializable
from pinnacledb.components.model import Model
from pinnacledb.components.schema import Schema
from pinnacledb.ext.numpy.encoder import array
from pinnacledb.ext.pillow.encoder import pil_image


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

    s = schema.serialize()
    print(s)
    ds = Serializable.deserialize(s)

    print(ds)

    t = Table(identifier='my_table', schema=schema)

    s = t.serialize()
    ds = Serializable.deserialize(s)

    print(ds)


@pytest.fixture
def duckdb():
    os.makedirs('.pinnacledb', exist_ok=True)
    db = pinnacle('duckdb://.pinnacledb/test.ddb')

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
        t.insert(pandas.DataFrame([{'x': 'test', 'id': str(i)} for i in range(20)]))
    )

    model = Model(
        object=lambda _: numpy.random.randn(32),
        identifier='test',
        encoder=array('float64', shape=(32,)),
    )
    model.predict('x', select=t, db=db)

    yield db

    shutil.rmtree('.pinnacledb')


def test_renamings(duckdb):
    t = duckdb.load('table', 'test')

    data = duckdb.execute(t.outputs(x='test'))

    assert isinstance(data[0]['_outputs.x.test'].x, numpy.ndarray)
