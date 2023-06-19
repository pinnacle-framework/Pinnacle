import json
import random

import lorem
import numpy
import pytest
import torch

from pinnacledb.core.documents import Document
from pinnacledb.core.vector_index import VectorIndex
from pinnacledb.core.watcher import Watcher
from pinnacledb.datalayer.mongodb.client import SuperDuperClient
from pinnacledb.datalayer.mongodb.query import Select, Insert, Delete
from pinnacledb.models.torch.wrapper import SuperDuperModule
from pinnacledb.types.numpy.array import array
from pinnacledb.types.pillow.image import pil_image
from pinnacledb.types.torch.tensor import tensor
from tests.material.models import BinaryClassifier, LinearBase
from tests.material.metrics import PatK


n_data_points = 250


@pytest.fixture()
def empty(client: SuperDuperClient):
    db = client.test_db
    db.remote = False
    yield db
    client.drop_database('test_db', force=True)


@pytest.fixture()
def metric(empty):
    empty.add(PatK(1))
    yield empty
    empty.remove('metric', 'p@1', force=True)


@pytest.fixture
def random_data_factory(float_tensors_32):
    float_tensor = float_tensors_32.types['torch.float32[32]']

    def _factory(number_data_points=n_data_points):
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
        float_tensors_32.execute(
            Insert(collection='documents', documents=data), refresh=False
        )
        return float_tensors_32

    return _factory


@pytest.fixture()
def random_data(random_data_factory):
    return random_data_factory()


@pytest.fixture()
def random_arrays(arrays):
    float_array = arrays.types['numpy.float32[32]']
    data = []
    for i in range(n_data_points):
        x = numpy.random.randn(32).astype(numpy.float32)
        y = int(random.random() > 0.5)
        data.append(Document({'x': float_array(x), 'y': y}))
    arrays.execute(Insert(collection='documents', documents=data), refresh=False)
    yield arrays
    arrays.execute(Delete('documents', {}))


@pytest.fixture()
def an_update(float_tensors_32):
    float_tensor = float_tensors_32.types['torch.float32[32]']
    data = []
    for i in range(10):
        x = torch.randn(32)
        y = int(random.random() > 0.5)
        z = torch.randn(32)
        data.append(
            Document(
                {
                    'x': float_tensor(x),
                    'y': y,
                    'z': float_tensor(z),
                    'update': True,
                }
            )
        )
    return data


@pytest.fixture
def vector_index_factory(a_model):
    def _factory(db, identifier, **kwargs) -> VectorIndex:
        db.add(Watcher(select=Select('documents'), key='x', model='linear_a'))
        vi = VectorIndex(
            identifier=identifier,
            indexing_watcher='linear_a/x',
            **kwargs,
        )
        db.add(vi)
        return vi

    return _factory


@pytest.fixture()
def with_vector_index(random_data, vector_index_factory):
    vector_index_factory(random_data, 'test_vector_search')
    yield random_data


@pytest.fixture()
def si_validation(random_data):
    random_data._add_validation_set(
        'my_valid',
        select=Select('documents', filter={'_fold': 'valid'}),
        chunk_size=100,
    )

    yield random_data


@pytest.fixture()
def imputation_validation(random_data):
    random_data._add_validation_set('my_imputation_valid', chunk_size=100)
    yield random_data


@pytest.fixture()
def float_tensors_32(empty):
    empty.add(tensor(torch.float, shape=(32,)))
    yield empty
    empty.remove('type', 'torch.float32[32]', force=True)


@pytest.fixture()
def float_tensors_16(empty):
    empty.add(tensor(torch.float, shape=(16,)))
    yield empty
    empty.remove('type', 'torch.float32[16]', force=True)


@pytest.fixture()
def float_tensors_8(empty):
    empty.add(tensor(torch.float, shape=(8,)))
    yield empty
    empty.remove('type', 'torch.float32[8]', force=True)


@pytest.fixture()
def arrays(empty):
    empty.add(array('float32', shape=(32,)))
    yield empty
    empty.remove('type', 'numpy.float32[32]', force=True)


@pytest.fixture()
def sentences(empty):
    data = []
    for _ in range(100):
        data.append(Document({'text': lorem.sentence()}))
    empty.execute(Insert(collection='documents', documents=data))
    yield empty


@pytest.fixture()
def nursery_rhymes(empty):
    with open('tests/material/data/rhymes.json') as f:
        data = json.load(f)
    for i in range(len(data)):
        data[i] = Document({'text': data[i]})
    empty.execute(Insert(collection='documents', documents=data))
    yield empty


@pytest.fixture()
def image_type(empty):
    empty.add(pil_image)
    yield empty
    empty.remove('type', 'pil_image', force=True)


@pytest.fixture()
def a_model(float_tensors_32, float_tensors_16):
    float_tensors_32.add(
        SuperDuperModule(
            torch.nn.Linear(32, 16), 'linear_a', encoder='torch.float32[16]'
        )
    )
    yield float_tensors_32
    try:
        float_tensors_32.remove('model', 'linear_a', force=True)
    except TypeError as e:
        if "'NoneType' object is not subscriptable" in str(e):
            return
        raise e


@pytest.fixture()
def a_model_base(float_tensors_32, float_tensors_16):
    float_tensors_32.add(
        SuperDuperModule(
            LinearBase(32, 16), 'linear_a_base', encoder='torch.float32[16]'
        ),
    )
    yield float_tensors_32
    try:
        float_tensors_32.remove('model', 'linear_a_base', force=True)
    except TypeError as e:
        if "'NoneType' object is not subscriptable" in str(e):
            return
        raise e


@pytest.fixture()
def a_watcher(a_model):
    a_model.remote = False
    a_model.add(Watcher(model='linear_a', select=Select('documents'), key='x'))
    yield a_model
    a_model.remove('watcher', 'linear_a/x', force=True)


@pytest.fixture()
def a_watcher_base(a_model_base):
    a_model_base.add(
        Watcher(model='linear_a_base', select=Select('documents'), key='_base')
    )
    yield a_model_base
    a_model_base.remove('watcher', 'linear_a_base/_base', force=True)


@pytest.fixture()
def a_classifier(float_tensors_32):
    float_tensors_32.add(
        SuperDuperModule(BinaryClassifier(32), 'classifier'),
    )
    yield float_tensors_32
    try:
        float_tensors_32.remove('model', 'classifier', force=True)
    except TypeError as e:
        if "'NoneType' object is not subscriptable" in str(e):
            return
        raise e


@pytest.fixture()
def b_model(float_tensors_32, float_tensors_16, float_tensors_8):
    float_tensors_32.add(
        SuperDuperModule(
            torch.nn.Linear(16, 8), 'linear_b', encoder='torch.float32[8]'
        ),
    )
    yield float_tensors_32
    try:
        float_tensors_32.remove('model', 'linear_b', force=True)
    except TypeError as e:
        if "'NoneType' object is not subscriptable" in str(e):
            return
        raise e


@pytest.fixture()
def c_model(float_tensors_32, float_tensors_16):
    float_tensors_32.add(
        SuperDuperModule(
            torch.nn.Linear(32, 16),
            'linear_c',
            encoder='torch.float32[16]',
        ),
    )
    yield float_tensors_32
    try:
        float_tensors_32.remove('model', 'linear_c', force=True)
    except TypeError as e:
        if "'NoneType' object is not subscriptable" in str(e):
            return
        raise e
