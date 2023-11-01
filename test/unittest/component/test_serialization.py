import pytest

try:
    import torch

    from pinnacledb.ext.torch.encoder import tensor
except ImportError:
    torch = None
from sklearn.svm import SVC

from pinnacledb.base.artifact import Artifact
from pinnacledb.components.model import Model
from pinnacledb.ext.sklearn.model import Estimator


@pytest.mark.skipif(not torch, reason='Torch not installed')
def test_model():
    m = Model(
        identifier='test',
        encoder=tensor(torch.float, shape=(32,)),
        object=torch.nn.Linear(13, 18),
    )
    m_dict = m.dict()
    assert m_dict['identifier'] == m.identifier
    assert m_dict['object'] == m.object
    assert m_dict['encoder']['identifier'] == 'torch.float32[32]'


@pytest.mark.skipif(not torch, reason='Torch not installed')
def test_sklearn(local_empty_data_layer):
    m = Estimator(
        identifier='test',
        object=SVC(),
        encoder=tensor(torch.float, shape=(32,)),
    )
    local_empty_data_layer.add(m)
    assert local_empty_data_layer.metadata.component_collection.count_documents({}) == 2
    reloaded = local_empty_data_layer.load(type_id='model', identifier='test')
    assert isinstance(reloaded.object, Artifact)
