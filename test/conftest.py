import inspect
import os
import random
import time
from pathlib import Path
from threading import Lock
from typing import Iterator

import pytest

import pinnacledb as s
from pinnacledb import CFG, logging
from pinnacledb.backends.ibis.field_types import dtype
from pinnacledb.backends.ibis.query import Table
from pinnacledb.backends.mongodb.data_backend import MongoDataBackend
from pinnacledb.backends.mongodb.query import Collection

# ruff: noqa: E402
from pinnacledb.base import config as _config, pinnacle
from pinnacledb.base.build import build_datalayer
from pinnacledb.base.datalayer import Datalayer
from pinnacledb.base.document import Document
from pinnacledb.components.dataset import Dataset
from pinnacledb.components.listener import Listener
from pinnacledb.components.schema import Schema
from pinnacledb.components.vector_index import VectorIndex
from pinnacledb.ext.pillow.encoder import pil_image

_config._CONFIG_IMMUTABLE = False


try:
    import torch

    from pinnacledb.ext.torch.encoder import tensor
    from pinnacledb.ext.torch.model import TorchModel
except ImportError:
    torch = None

GLOBAL_TEST_N_DATA_POINTS = 250
LOCAL_TEST_N_DATA_POINTS = 5

MONGOMOCK_URI = 'mongomock:///test_db'
SQLITE_URI = 'sqlite://:memory:'


_sleep = time.sleep

SCOPE = 'function'
LOCK = Lock()
SLEEPS = {}
SLEEP_FILE = s.ROOT / 'test/sleep.json'
MAX_SLEEP_TIME = float('inf')

SDDB_USE_MONGOMOCK = 'SDDB_USE_MONGOMOCK' in os.environ
SDDB_INSTRUMENT_TIME = 'SDDB_INSTRUMENT_TIME' in os.environ


@pytest.fixture(autouse=SDDB_INSTRUMENT_TIME, scope=SCOPE)
def patch_sleep(monkeypatch):
    monkeypatch.setattr(time, 'sleep', sleep)


def sleep(t: float) -> None:
    _write(t)
    _sleep(min(t, MAX_SLEEP_TIME))


def _write(t):
    stack = inspect.stack()
    if len(stack) <= 2:
        return
    module = inspect.getmodule(stack[2][0]).__file__
    with LOCK:
        entry = SLEEPS.setdefault(module, [0, 0])
        entry[0] += 1
        entry[1] += t
        with open(SLEEP_FILE, 'w') as f:
            f.write(SLEEPS, f)


@pytest.fixture(autouse=SDDB_USE_MONGOMOCK)
def patch_mongomock(monkeypatch):
    import gridfs.grid_file
    import pymongo
    from mongomock import Collection, Database, MongoClient

    from pinnacledb.backends.base.backends import CONNECTIONS

    monkeypatch.setattr(gridfs, 'Collection', Collection)
    monkeypatch.setattr(gridfs.grid_file, 'Collection', Collection)
    monkeypatch.setattr(gridfs, 'Database', Database)
    monkeypatch.setattr(pinnacle, 'Database', Database)
    monkeypatch.setattr(pymongo, 'MongoClient', MongoClient)

    monkeypatch.setitem(CONNECTIONS, 'pymongo', MongoClient)


@pytest.fixture
def test_db(monkeypatch, request) -> Iterator[Datalayer]:
    from pinnacledb import CFG
    from pinnacledb.base.build import build_datalayer

    # mongodb instead of localhost is required for CFG compatibility with docker-host
    db_name = "test_db"
    data_backend = f'mongodb://pinnacle:pinnacle@mongodb:27017/{db_name}'

    monkeypatch.setattr(CFG, 'data_backend', data_backend)

    db = build_datalayer(CFG)

    yield db

    logging.info("Dropping database ", {db_name})

    db.databackend.conn.drop_database(db_name)
    db.databackend.conn.drop_database(f'_filesystem:{db_name}')


@pytest.fixture
def valid_dataset():
    d = Dataset(
        identifier='my_valid',
        select=Collection('documents').find({'_fold': 'valid'}),
        sample_size=100,
    )
    return d


def add_random_data_to_sql_db(
    db: Datalayer,
    table_name: str = 'documents',
    number_data_points: int = GLOBAL_TEST_N_DATA_POINTS,
):
    float_tensor = db.encoders['torch.float32[32]']
    data = []

    schema = Schema(
        identifier=table_name,
        fields={
            'id': dtype('str'),
            'x': float_tensor,
            'y': dtype('int32'),
            'z': float_tensor,
        },
    )
    t = Table(identifier=table_name, schema=schema)
    db.add(t)

    for i in range(number_data_points):
        x = torch.randn(32)
        y = int(random.random() > 0.5)
        z = torch.randn(32)
        data.append(
            Document(
                {
                    'id': str(i),
                    'x': x,
                    'y': y,
                    'z': z,
                }
            )
        )
    db.execute(
        t.insert(data),
        refresh=False,
    )


def add_random_data_to_mongo_db(
    db: Datalayer,
    collection_name: str = 'documents',
    number_data_points: int = GLOBAL_TEST_N_DATA_POINTS,
):
    float_tensor = db.encoders['torch.float32[32]']
    data = []

    for i in range(number_data_points):
        x = torch.randn(32)
        y = int(random.random() > 0.5)
        z = torch.randn(32)
        data.append(
            Document(
                {
                    'x': float_tensor(x),
                    'y': y,
                    'z': float_tensor(z),
                }
            )
        )

    db.execute(
        Collection(collection_name).insert_many(data),
        refresh=False,
    )


def add_encoders(db: Datalayer):
    for n in [8, 16, 32]:
        db.add(tensor(torch.float, shape=(n,)))
    db.add(pil_image)


def add_models(db: Datalayer):
    # identifier, weight_shape, encoder
    params = [
        ['linear_a', (32, 16), 'torch.float32[16]'],
        ['linear_b', (16, 8), 'torch.float32[8]'],
    ]
    for identifier, weight_shape, encoder in params:
        db.add(
            TorchModel(
                object=torch.nn.Linear(*weight_shape),
                identifier=identifier,
                encoder=encoder,
            )
        )


def add_vector_index(
    db: Datalayer, collection_name='documents', identifier='test_vector_search'
):
    # TODO: Support configurable key and model
    is_mongodb_bachend = isinstance(db.databackend, MongoDataBackend)
    if is_mongodb_bachend:
        select_x = Collection(collection_name).find()
        select_z = Collection(collection_name).find()
    else:
        table = db.load('table', collection_name).to_query()
        select_x = table.select('id', 'x')
        select_z = table.select('id', 'z')

    db.add(
        Listener(
            select=select_x,
            key='x',
            model='linear_a',
        )
    )
    db.add(
        Listener(
            select=select_z,
            key='z',
            model='linear_a',
        )
    )
    vi = VectorIndex(
        identifier=identifier,
        indexing_listener='linear_a/x',
        compatible_listener='linear_a/z',
    )
    db.add(vi)


@pytest.fixture(scope='session')
def image_url():
    path = Path(__file__).parent / 'material' / 'data' / '1x1.png'
    return f'file://{path}'


def create_db(CFG, **kwargs):
    # TODO: support more parameters to control the setup
    db = build_datalayer(CFG)
    if kwargs.get('empty', False):
        return db

    add_encoders(db)
    n_data = kwargs.get('n_data', LOCAL_TEST_N_DATA_POINTS)

    # prepare data
    is_mongodb_bachend = isinstance(db.databackend, MongoDataBackend)
    if is_mongodb_bachend:
        add_random_data_to_mongo_db(db, number_data_points=n_data)
    else:
        add_random_data_to_sql_db(db, number_data_points=n_data)

    # prepare models
    if kwargs.get('add_models', True):
        add_models(db)

    # prepare vector index
    if kwargs.get('add_vector_index', True):
        add_vector_index(db)

    return db


@pytest.fixture
def db(request, monkeypatch) -> Iterator[Datalayer]:
    # TODO: Use pre-defined config instead of dict here
    db_type, setup_config = (
        request.param if hasattr(request, 'param') else ("mongodb", None)
    )
    setup_config = setup_config or {}
    if db_type == "mongodb":
        monkeypatch.setattr(CFG, 'data_backend', MONGOMOCK_URI)
    elif db_type == "sqldb":
        monkeypatch.setattr(CFG, 'data_backend', SQLITE_URI)

    db = create_db(CFG, **setup_config)
    yield db

    if db_type == "mongodb":
        db.drop(force=True)
    elif db_type == "sqldb":
        db.artifact_store.drop(force=True)
        tables = db.databackend.conn.list_tables()
        for table in tables:
            db.databackend.conn.drop_table(table, force=True)
