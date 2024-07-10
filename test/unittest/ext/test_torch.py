import pytest

try:
    import torch

    from pinnacle.ext.torch.model import TorchModel
except ImportError:
    torch = None

from test.db_config import DBConfig

from pinnacle.backends.mongodb.data_backend import MongoDataBackend
from pinnacle.backends.mongodb.query import MongoQuery
from pinnacle.components.datatype import DataType
from pinnacle.components.metric import Metric
from pinnacle.components.model import Validation
from pinnacle.ext.torch.training import TorchTrainer


class ToDict:
    def __init__(self):
        self.dict = dict(zip(list('abcdefghiklmnopqrstuvwyz'), range(26)))

    def __call__(self, input: str):
        return [self.dict[k] for k in input]


class TensorLookup:
    def __init__(self):
        self.d = torch.randn(26, 32)

    def __call__(self, x):
        return torch.stack([self.d[y] for y in x])


def pad_to_ten(x):
    to_stack = []
    for i, y in enumerate(x):
        out = torch.zeros(10, 32)
        y = y[:10]
        out[: y.shape[0], :] = y
        to_stack.append(out)
    return torch.stack(to_stack)


def my_loss(X, y):
    return torch.nn.functional.binary_cross_entropy_with_logits(
        X[:, 0], y.type(torch.float)
    )


def acc(x, y):
    return x == y


@pytest.fixture
def model():
    return TorchModel(
        object=torch.nn.Linear(32, 1),
        identifier='test',
        preferred_devices=('cpu',),
        postprocess=lambda x: int(torch.sigmoid(x).item() > 0.5),
        datatype=DataType(identifier='base'),
    )


@pytest.mark.skipif(not torch, reason='Torch not installed')
@pytest.mark.parametrize(
    'db',
    [
        (DBConfig.mongodb_data, {'n_data': 500}),
        (DBConfig.sqldb_data, {'n_data': 500}),
    ],
    indirect=True,
)
def test_fit(db, valid_dataset, model):
    m = model

    if isinstance(db.databackend.type, MongoDataBackend):
        select = MongoQuery(table='documents').find()
    else:
        select = db['documents'].select('id', '_fold', 'x', 'y', 'z')
    trainer = TorchTrainer(
        key=('x', 'y'),
        select=select,
        identifier='my_trainer',
        objective=my_loss,
        loader_kwargs={'batch_size': 10},
        max_iterations=100,
        validation_interval=10,
    )

    model.trainer = trainer
    model.validation = Validation(
        'my_valid',
        metrics=[Metric(identifier='acc', object=acc)],
        datasets=[valid_dataset],
    )
    db.apply(m)
