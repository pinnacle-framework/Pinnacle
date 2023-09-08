import ibis
import pandas as pd
import PIL.Image
import pytest
import tdir
import torchvision

import pinnacledb as s
from pinnacledb.container.document import Document as D
from pinnacledb.db.base.build import build_vector_database
from pinnacledb.db.filesystem.artifacts import FileSystemArtifactStore
from pinnacledb.db.ibis.data_backend import IbisDataBackend
from pinnacledb.db.ibis.db import IbisDB
from pinnacledb.db.ibis.field_types import dtype
from pinnacledb.db.ibis.query import Table
from pinnacledb.db.ibis.schema import IbisSchema
from pinnacledb.db.sqlalchemy.metadata import SQLAlchemyMetadata
from pinnacledb.ext.pillow.image import pil_image
from pinnacledb.ext.torch.model import TorchModel


@pytest.fixture
def sqllite_conn():
    with tdir(chdir=False) as tmp_dir:
        yield ibis.sqlite.connect(tmp_dir / 'mydb.sqlite'), tmp_dir


@pytest.fixture
def ibis_db(sqllite_conn):
    connection, tmp_dir = sqllite_conn
    yield make_ibis_db(connection, connection, tmp_dir)


@pytest.fixture
def ibis_pandas_db(sqllite_conn):
    connection, tmp_dir = sqllite_conn
    df = pd.DataFrame(
        [[1, 0, 25, 'kk'], [2, 1, 26, 'kk'], [3, 0, 27, 'kk'], [4, 1, 28, 'kk']],
        columns=['id', 'health', 'age', 'name'],
    )
    t = ibis.memtable(df, name='pandas')
    yield make_ibis_db(t, connection, tmp_dir)


def make_ibis_db(db_conn, metadata_conn, tmp_dir):
    return IbisDB(
        databackend=IbisDataBackend(conn=db_conn, name='ibis'),
        metadata=SQLAlchemyMetadata(conn=metadata_conn.con, name='ibis'),
        artifact_store=FileSystemArtifactStore(conn=tmp_dir, name='ibis'),
        vector_database=build_vector_database(s.CFG),
    )


def test_end2end_sql(ibis_db):
    db = ibis_db
    schema = IbisSchema(
        identifier='my_table',
        fields={
            'id': dtype('int64'),
            'health': dtype('int32'),
            'age': dtype('int32'),
            'image': pil_image,
        },
    )
    im = PIL.Image.open('test/material/data/test-image.jpeg')
    data_to_insert = [
        {'id': 1, 'health': 0, 'age': 25, 'image': im},
        {'id': 2, 'health': 1, 'age': 26, 'image': im},
        {'id': 3, 'health': 0, 'age': 27, 'image': im},
        {'id': 4, 'health': 1, 'age': 28, 'image': im},
    ]
    t = Table(identifier='my_table', schema=schema)
    t.create(db)

    db.add(t)
    db.execute(
        t.insert(
            [
                D(
                    {
                        'id': d['id'],
                        'health': d['health'],
                        'age': d['age'],
                        'image': d['image'],
                    }
                )
                for d in data_to_insert
            ]
        )
    )

    # -------------- retrieve data  from table ----------------
    q = t.select('image', 'age', 'health')
    imgs = db.execute(q)
    for img in imgs:
        img = img.unpack()
        assert isinstance(img['image'], PIL.Image.Image)
        assert isinstance(img['age'], int)
        assert isinstance(img['health'], int)

    # preprocessing function
    preprocess = torchvision.transforms.Compose(
        [
            torchvision.transforms.Resize(256),
            torchvision.transforms.CenterCrop(224),
            torchvision.transforms.ToTensor(),
            torchvision.transforms.Normalize(
                mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]
            ),
        ]
    )

    def postprocess(x):
        return int(x.topk(1)[1].item())

    # create a torchvision model
    resnet = TorchModel(
        identifier='resnet18',
        preprocess=preprocess,
        postprocess=postprocess,
        object=torchvision.models.resnet18(pretrained=False),
        encoder=dtype('int32'),
    )

    # Apply the torchvision model
    resnet.predict(
        X='image',
        db=db,
        select=t.select('id', 'image'),
        max_chunk_size=3000,
        overwrite=True,
    )

    # Query the results back
    q = t.select('id', 'image', 'age').filter(t.age > 25).outputs('resnet18', db)
    curr = db.execute(q)

    for c in curr:
        assert all(
            [
                k
                in [
                    'id',
                    'health',
                    'age',
                    'image',
                    'output',
                    'query_id',
                    'key',
                    'input_id',
                ]
                for k in c.unpack().keys()
            ]
        )


def test_end2end_pandas(ibis_pandas_db):
    db = ibis_pandas_db
    # -------------- retrieve data  from table ----------------
    q = db.table.select('id', 'age', 'health').filter(db.table.age > 25)
    imgs = db.execute(q)
    for img in imgs:
        img = img.unpack()
        assert isinstance(img['age'], int)
        assert isinstance(img['health'], int)
