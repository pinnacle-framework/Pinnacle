import random

import lorem
import numpy

from pinnacledb.core.vector_index import VectorIndex
from pinnacledb.core.watcher import Watcher
from pinnacledb.datalayer.mongodb.client import SuperDuperClient
from pinnacledb.datalayer.mongodb.query import Select, Insert, Delete
from pinnacledb.models.torch.wrapper import SuperDuperModule
from pinnacledb.types.numpy.array import Array
from pinnacledb.types.pillow.image import Image
from pinnacledb.types.torch.tensor import Tensor
from pinnacledb.vector_search import FaissHashSet
from pinnacledb.vector_search.vanilla.hashes import VanillaHashSet
from tests.material.models import BinaryClassifier, BinaryTarget, LinearBase
from tests.material.measures import css
from tests.material.metrics import PatK, accuracy

import pytest
import torch


n_data_points = 250


@pytest.fixture()
def empty(client: SuperDuperClient):
    db = client.test_db.documents
    db.remote = False
    yield db
    client.drop_database('test_db', force=True)


@pytest.fixture()
def metric(empty):
    empty.database.create_component(PatK(1))
    yield empty
    empty.database.delete_component('p@1', 'metric', force=True)


@pytest.fixture()
def accuracy_metric(empty):
    empty.create_metric('accuracy_metric', accuracy)
    yield empty
    empty.delete_metric('accuracy_metric', force=True)


@pytest.fixture()
def random_data(float_tensors):
    data = []
    for i in range(n_data_points):
        x = torch.randn(32)
        y = int(random.random() > 0.5)
        z = torch.randn(32)
        data.append({'x': x, 'z': z, 'y': y})
    float_tensors.database.insert(Insert('documents', documents=data), refresh=False)
    yield float_tensors
    float_tensors.delete_many({})


@pytest.fixture()
def random_arrays(arrays):
    data = []
    for i in range(n_data_points):
        x = numpy.random.randn(32).astype(numpy.float32)
        y = int(random.random() > 0.5)
        data.append({'x': x, 'y': y})
    arrays.database.insert(Insert('documents', documents=data), refresh=False)
    yield arrays
    arrays.database.delete(Delete('documents', {}))


@pytest.fixture()
def an_update():
    data = []
    for i in range(10):
        x = torch.randn(32)
        y = int(random.random() > 0.5)
        z = torch.randn(32)
        data.append({'x': x, 'z': z, 'y': y, 'update': True})
    return data


@pytest.fixture()
def with_vector_index(random_data, a_model):
    random_data.database.create_component(
        Watcher(select=Select('documents'), key='x', model_id='linear_a')
    )
    random_data.database.create_component(
        VectorIndex(
            'test_vector_search',
            model_ids=['linear_a'],
            keys=['x'],
            watcher_id='linear_a/x',
        )
    )
    yield random_data
    random_data.database.delete_component('test_vector_search', 'vector_index', force=True)


@pytest.fixture()
def with_vector_index_faiss(random_data, a_model):
    random_data.database.create_component(
        Watcher(select=Select('documents'), key='x', model_id='linear_a')
    )
    random_data.database.create_component(
        VectorIndex(
            'test_vector_search',
            model_ids=['linear_a'],
            keys=['x'],
            watcher_id='linear_a/x',
            hash_set_cls=FaissHashSet,
        )
    )
    yield random_data
    random_data.database.delete_component('test_vector_search', 'vector_index', force=True)


@pytest.fixture()
def si_validation(random_data):
    random_data.database.create_validation_set('my_valid', select=Select('documents', filter={'_fold': 'valid'}), chunk_size=100)

    yield random_data


@pytest.fixture()
def imputation_validation(random_data):
    random_data.create_validation_set('my_imputation_valid', chunk_size=100)
    yield random_data


@pytest.fixture()
def float_tensors(empty):
    empty.database.create_component(
        Tensor('float_tensor', torch.float32, types=[torch.FloatTensor, torch.Tensor])
    )
    yield empty
    empty.database.delete_component('float_tensor', 'type', force=True)


@pytest.fixture()
def arrays(empty):
    empty.database.create_component(Array('array', numpy.float32, types=[numpy.ndarray]))
    yield empty
    empty.database.delete_component('array', 'type', force=True)


@pytest.fixture()
def sentences(empty):
    data = []
    for _ in range(100):
        data.append({'text': lorem.sentence()})
    empty.database.insert(Insert('documents', documents=data))
    yield empty


@pytest.fixture()
def int64(empty):
    empty.database.create_component(Array('int64', numpy.int64))
    yield empty
    empty.database.delete_component('int64', 'type', force=True)


@pytest.fixture()
def image_type(empty):
    empty.database.create_component(Image('image'))
    yield empty
    empty.database.delete_component('image', 'type', force=True)


@pytest.fixture()
def a_model(float_tensors):
    float_tensors.database.create_component(
        SuperDuperModule(torch.nn.Linear(32, 16), 'linear_a', type='float_tensor')
    )
    yield float_tensors
    try:
        float_tensors.database.delete_component('linear_a', 'model', force=True)
    except TypeError as e:
        if "'NoneType' object is not subscriptable" in str(e):
            return
        raise e


@pytest.fixture()
def a_model_base(float_tensors):
    float_tensors.database.create_component(
        SuperDuperModule(LinearBase(32, 16), 'linear_a_base', type='float_tensor'),
    )
    yield float_tensors
    try:
        float_tensors.database.delete_component('linear_a_base', 'model', force=True)
    except TypeError as e:
        if "'NoneType' object is not subscriptable" in str(e):
            return
        raise e


@pytest.fixture()
def a_watcher(a_model):
    a_model.remote = False
    a_model.database.create_component(Watcher(model_id='linear_a', select=Select('documents'), key='x'))
    yield a_model
    a_model.database.delete_component('linear_a/x', 'watcher', force=True)


@pytest.fixture()
def a_watcher_base(a_model_base):
    a_model_base.database.create_component(Watcher(model_id='linear_a_base', select=Select('documents'), key='_base'))
    yield a_model_base
    a_model_base.database.delete_component('linear_a_base/_base', 'watcher', force=True)


@pytest.fixture()
def a_classifier(float_tensors):
    float_tensors.database.create_component(
        SuperDuperModule(BinaryClassifier(32), 'classifier'),
    )
    yield float_tensors
    try:
        float_tensors.database.delete_component('classifier', 'model', force=True)
    except TypeError as e:
        if "'NoneType' object is not subscriptable" in str(e):
            return
        raise e


@pytest.fixture()
def a_target(float_tensors):
    float_tensors.create_function('target', BinaryTarget())
    yield float_tensors
    try:
        float_tensors.delete_function('target', force=True)
    except TypeError as e:
        if "'NoneType' object is not subscriptable" in str(e):
            return
        raise e


@pytest.fixture()
def b_model(float_tensors):
    float_tensors.database.create_component(
        SuperDuperModule(torch.nn.Linear(16, 8), 'linear_b', type='float_tensor'),
    )
    yield float_tensors
    try:
        float_tensors.database.delete_component('linear_b', 'model', force=True)
    except TypeError as e:
        if "'NoneType' object is not subscriptable" in str(e):
            return
        raise e


@pytest.fixture()
def c_model(float_tensors):
    float_tensors.database.create_component(
        SuperDuperModule(torch.nn.Linear(32, 16), 'linear_c', type='float_tensor'),
    )
    yield float_tensors
    try:
        float_tensors.database.delete_component('linear_c', 'model', force=True)
    except TypeError as e:
        if "'NoneType' object is not subscriptable" in str(e):
            return
        raise e
