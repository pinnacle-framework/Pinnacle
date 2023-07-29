from pinnacledb.datalayer.mongodb.query import Collection
from pinnacledb.datalayer.query_dataset import QueryDataset


def test_query_dataset(random_data, a_watcher):
    train_data = QueryDataset(
        select=Collection(name='documents').find(
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
        select=Collection(name='documents').find(),
        keys=['x', 'y'],
        fold='train',
    )

    r = train_data[0]
    assert '_id' not in r
    assert set(r.keys()) == {'x', 'y'}

    _ = QueryDataset(
        select=Collection(name='documents').find(),
        fold='valid',
    )


def test_query_dataset_base(random_data, a_watcher_base):
    train_data = QueryDataset(
        select=Collection(name='documents').find({}, {'_id': 0}),
        keys=['_base', 'y'],
        fold='train',
    )
    r = train_data[0]
    print(r)
