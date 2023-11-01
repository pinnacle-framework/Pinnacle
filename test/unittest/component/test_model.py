import pytest

try:
    import torch

    from pinnacledb.ext.torch.model import TorchModel
except ImportError:
    torch = None

from pinnacledb.backends.mongodb.query import Collection


@pytest.mark.skipif(not torch, reason='Torch not installed')
def test_predict(local_data_layer):
    encoder = local_data_layer.encoders['torch.float32[32]']

    m = TorchModel(
        identifier='my-model',
        object=torch.nn.Linear(32, 7),
        encoder=encoder,
    )

    X = [r['x'] for r in local_data_layer.execute(Collection('documents').find())]

    out = m.predict(X=X, distributed=False)

    assert len(out) == len(X)

    m.predict(
        X='x',
        db=local_data_layer,
        select=Collection('documents').find(),
        distributed=False,
        listen=True,
    )


# TODO: test pinnacle.base.model(predict, fit...)
