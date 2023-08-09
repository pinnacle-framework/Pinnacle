import pytest
import torch

from pinnacledb.container.document import Document
from pinnacledb.ext.torch.tensor import tensor


@pytest.fixture(scope='function')
def document():
    t = tensor(torch.float, shape=(20,))

    yield Document({'x': t(torch.randn(20)), '_outputs': {'x': {'model_test': 1}}})


def test_document_encoding(document):
    t = tensor(torch.float, shape=(20,))
    print(document.encode())
    Document.decode(document.encode(), encoders={'torch.float32[20]': t})


def test_document_outputs(document):
    assert document.outputs('x', 'model_test') == 1


def test_only_uri(float_tensors_8):
    r = Document(
        Document.decode(
            {'x': {'_content': {'uri': 'foo', 'encoder': 'torch.float32[8]'}}},
            encoders=float_tensors_8.encoders,
        )
    )
    assert r['x'].uri == 'foo'
