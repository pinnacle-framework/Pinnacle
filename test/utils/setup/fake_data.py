import random

try:
    import torch

    from pinnacle.ext.torch.encoder import tensor
    from pinnacle.ext.torch.model import TorchModel
except ImportError:
    torch = None

from pinnacle.backends.ibis.field_types import dtype
from pinnacle.backends.mongodb.data_backend import MongoDataBackend
from pinnacle.backends.mongodb.query import MongoQuery

# ruff: noqa: E402
from pinnacle.base.datalayer import Datalayer
from pinnacle.components.dataset import Dataset
from pinnacle.components.listener import Listener
from pinnacle.components.schema import Schema
from pinnacle.components.table import Table
from pinnacle.components.vector_index import VectorIndex
from pinnacle.ext.pillow.encoder import pil_image

GLOBAL_TEST_N_DATA_POINTS = 100


def get_valid_dataset(db):
    if isinstance(db.databackend.type, MongoDataBackend):
        select = MongoQuery(table='documents').find({'_fold': 'valid'})
    else:
        table = db['documents']
        select = table.select('id', '_fold', 'x', 'y', 'z').filter(
            table._fold == 'valid'
        )
    d = Dataset(
        identifier='my_valid',
        select=select,
        sample_size=100,
    )
    return d


def add_random_data(
    db: Datalayer,
    table_name: str = 'documents',
    n: int = GLOBAL_TEST_N_DATA_POINTS,
):
    float_tensor = tensor(dtype='float', shape=(32,))

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
    data = []
    for i in range(n):
        x = torch.randn(32)
        y = int(random.random() > 0.5)
        z = torch.randn(32)
        fold = int(random.random() > 0.5)
        fold = 'valid' if fold else 'train'
        data.append({'id': str(i), 'x': x, 'y': y, 'z': z, '_fold': fold})
    db[table_name].insert(data).execute()


def add_datatypes(db: Datalayer):
    for n in [8, 16, 32]:
        db.apply(tensor(dtype='float', shape=(n,)))
    db.apply(pil_image)


def add_models(db: Datalayer):
    # identifier, weight_shape, encoder
    params = [
        ['linear_a', (32, 16), tensor(dtype='float', shape=(16,))],
        ['linear_b', (16, 8), tensor(dtype='float', shape=(8,))],
    ]
    for identifier, weight_shape, datatype in params:
        m = TorchModel(
            object=torch.nn.Linear(*weight_shape),
            identifier=identifier,
            datatype=datatype,
            preferred_devices=['cpu'],
        )
        db.add(m)


def add_listener(db: Datalayer, collection_name='documents'):
    add_models(db)
    model = db.load('model', 'linear_a')
    select = db[collection_name].select()

    _, i_list = db.add(Listener(select=select, key='x', model=model, uuid="vector-x"))

    _, c_list = db.add(Listener(select=select, key='z', model=model, uuid="vector-y"))

    return i_list, c_list


def add_vector_index(
    db: Datalayer,
    identifier='test_vector_search',
):
    try:
        i_list = db.load('listener', 'vector-x')
        c_list = db.load('listener', 'vector-y')
    except FileNotFoundError:
        i_list, c_list = add_listener(db)

        db.add(i_list)
        db.add(c_list)

    vi = VectorIndex(
        identifier=identifier,
        indexing_listener=i_list,
        compatible_listener=c_list,
    )

    db.add(vi)
