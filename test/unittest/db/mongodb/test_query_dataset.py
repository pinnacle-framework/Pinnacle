import pytest

from pinnacledb.db.mongodb.query import Collection
from pinnacledb.db.query_dataset import QueryDataset

try:
    import torch
except ImportError:
    torch = None


@pytest.mark.skipif(not torch, reason='Torch not installed')
def test_query_dataset(random_data, a_listener):
    train_data = QueryDataset(
        select=Collection('documents').find(
            {}, {'_id': 0, 'x': 1, '_fold': 1, '_outputs': 1}
        ),
        fold='train',
        features={'x': 'linear_a'},
    )
    r = train_data[0]
    assert '_id' not in r
    assert r['_fold'] == 'train'
    assert 'y' not in r
    assert r['x'].shape[0] == 16

    train_data = QueryDataset(
        select=Collection('documents').find(),
        keys=['x', 'y'],
        fold='train',
    )

    r = train_data[0]
    assert '_id' not in r
    assert set(r.keys()) == {'x', 'y'}

    _ = QueryDataset(
        select=Collection('documents').find(),
        fold='valid',
    )


@pytest.mark.skipif(not torch, reason='Torch not installed')
def test_query_dataset_base(random_data, a_listener_base):
    train_data = QueryDataset(
        select=Collection('documents').find({}, {'_id': 0}),
        keys=['_base', 'y'],
        fold='train',
    )
    r = train_data[0]
    print(r)
