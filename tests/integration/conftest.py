import random
import numpy as np
import time
from threading import Thread
from unittest import mock

import pytest
import torch
from pymongo import MongoClient
from tenacity import RetryError, Retrying, stop_after_delay

from pinnacledb import CFG
from pinnacledb.cluster.dask.dask_client import dask_client
from pinnacledb.core.document import Document
from pinnacledb.datalayer.base.build import build_datalayer
from pinnacledb.encoders.torch.tensor import tensor
from pinnacledb.misc.config import DataLayer, DataLayers
from pinnacledb.models.torch.wrapper import TorchModel
from pinnacledb.serve.server import serve

'''
All pytest fixtures with _package scope_ are defined in this module.
Package scope means that the fixture will be executed once per package,
which in this case means once per `test/integration/` directory.

Fixtures included here can create:
- a MongoDB client
- a MongoDB collection with some basic data
- a local Dask client
- a local SuperDuperDB server linked to the MongoDB client

When adding new fixtures, please try to avoid building on top of other fixtures
as much as possible. This will make it easier to understand the test suite.
'''

# Set the seeds
random.seed(42)
torch.manual_seed(42)
np.random.seed(42)


mongodb_test_config = {
    'host': '0.0.0.0',
    'port': 27018,
    'username': 'testmongodbuser',
    'password': 'testmongodbpassword',
    'serverSelectionTimeoutMS': 5000,
}


@pytest.fixture(autouse=True, scope="package")
def patch_pinnacle_config():
    data_layers_cfg = DataLayers(
        artifact=DataLayer(name='_filesystem:test_db', kwargs=mongodb_test_config),
        data_backend=DataLayer(name='test_db', kwargs=mongodb_test_config),
        metadata=DataLayer(name='test_db', kwargs=mongodb_test_config),
    )

    with mock.patch('pinnacledb.CFG.data_layers', data_layers_cfg):
        yield


@pytest.fixture(scope="package")
def create_mongodb_client_clean_and_close():
    mongo_client = MongoClient(**mongodb_test_config)

    try:
        for attempt in Retrying(stop=stop_after_delay(15)):
            with attempt:
                mongo_client.is_mongos
                print("Connected to test MongoDB client!")
    except RetryError:
        pytest.fail("Could not connect to mongodb,")

    yield mongo_client

    for database_name in mongo_client.list_database_names():
        if database_name in ("admin", "config", "local"):
            continue
        mongo_client.drop_database(database_name)
    mongo_client.close()


@pytest.fixture()
def fresh_client():
    mongo_client = MongoClient(**mongodb_test_config)
    try:
        for attempt in Retrying(stop=stop_after_delay(15)):
            with attempt:
                mongo_client.is_mongos
                print("Connected to test MongoDB client!")
    except RetryError:
        pytest.fail("Could not connect to mongodb,")
    yield mongo_client


@pytest.fixture(scope="package")
def database_with_default_encoders_and_model(create_mongodb_client_clean_and_close):
    database = build_datalayer(pymongo=create_mongodb_client_clean_and_close)
    database.add(tensor(torch.float, shape=(32,)))
    database.add(tensor(torch.float, shape=(16,)))
    database.add(
        TorchModel(
            object=torch.nn.Linear(32, 16),
            identifier='model_linear_a',
            encoder='torch.float32[16]',
        )
    )
    yield database

    database.remove('model', 'model_linear_a', force=True)
    database.remove('encoder', 'torch.float32[16]', force=True)
    database.remove('encoder', 'torch.float32[32]', force=True)


@pytest.fixture
def fresh_database(fresh_client):
    database = build_datalayer(pymongo=fresh_client)
    yield database
    for m in database.show('model'):
        if m != 'model_linear_a':
            database.remove('model', m, force=True)
    for e in database.show('encoder'):
        if e not in {'torch.float32[16]', 'torch.float32[32]'}:
            database.remove('encoder', e, force=True)


def fake_tensor_data(encoder, update=True):
    data = []
    for i in range(10):
        x = torch.randn(32)
        y = int(random.random() > 0.5)
        z = torch.randn(32)
        data.append(
            Document(
                {
                    'x': encoder(x),
                    'y': y,
                    'z': encoder(z),
                    'update': update,
                }
            )
        )

    return data


@pytest.fixture(scope="package")
def fake_inserts(database_with_default_encoders_and_model):
    encoder = database_with_default_encoders_and_model.encoders['torch.float32[32]']
    return fake_tensor_data(encoder, update=False)


@pytest.fixture(scope="package")
def fake_updates(database_with_default_encoders_and_model):
    encoder = database_with_default_encoders_and_model.encoders['torch.float32[32]']
    return fake_tensor_data(encoder, update=True)


@pytest.fixture(scope="package")
def test_server(database_with_default_encoders_and_model):
    app = serve(database_with_default_encoders_and_model)
    t = Thread(
        target=app.run,
        kwargs={"host": CFG.server.host, "port": CFG.server.port},
        daemon=True,
    )
    t.start()
    time.sleep(2)
    yield


@pytest.fixture(scope="package")
def local_dask_client():
    client = dask_client(CFG.dask, local=True)
    yield client
    client.shutdown()
