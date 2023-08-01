import PIL.PngImagePlugin
import pytest
import torch

from pinnacledb.container.document import Document
from pinnacledb.db.mongodb.query import Collection

n_data_points = 250

IMAGE_URL = 'https://www.pinnacledb.com/logos/white.png'


def test_delete_many(random_data):
    r = random_data.execute(Collection(name='documents').find_one())
    random_data.execute(Collection(name='documents').delete_many({'_id': r['_id']}))
    with pytest.raises(StopIteration):
        next(random_data.execute(Collection(name='documents').find({'_id': r['_id']})))


def test_replace(random_data):
    r = next(random_data.execute(Collection(name='documents').find()))
    x = torch.randn(32)
    t = random_data.encoders['torch.float32[32]']
    r['x'] = t(x)
    random_data.execute(
        Collection(name='documents').replace_one(
            {'_id': r['_id']},
            r,
        )
    )


def test_insert_from_uris(empty, image_type):
    to_insert = [
        Document(
            {
                'item': {
                    '_content': {
                        'uri': IMAGE_URL,
                        'encoder': 'pil_image',
                    }
                },
                'other': {
                    'item': {
                        '_content': {
                            'uri': IMAGE_URL,
                            'encoder': 'pil_image',
                        }
                    }
                },
            }
        )
        for _ in range(2)
    ]
    empty.execute(Collection(name='documents').insert_many(to_insert))
    r = empty.execute(Collection(name='documents').find_one())
    assert isinstance(r['item'].x, PIL.PngImagePlugin.PngImageFile)
    assert isinstance(r['other']['item'].x, PIL.PngImagePlugin.PngImageFile)


def test_update_many(random_data, a_watcher):
    to_update = torch.randn(32)
    t = random_data.encoders['torch.float32[32]']
    random_data.execute(
        Collection(name='documents').update_many(
            {}, Document({'$set': {'x': t(to_update)}})
        )
    )
    cur = random_data.execute(Collection(name='documents').find())
    r = next(cur)
    s = next(cur)

    assert all(r['x'].x == to_update)
    assert all(s['x'].x == to_update)
    assert (
        r['_outputs']['x']['linear_a'].x.tolist()
        == s['_outputs']['x']['linear_a'].x.tolist()
    )


def test_insert_many(random_data, a_watcher, an_update):
    random_data.execute(Collection(name='documents').insert_many(an_update))
    r = next(random_data.execute(Collection(name='documents').find({'update': True})))
    assert 'linear_a' in r['_outputs']['x']
    assert (
        len(list(random_data.execute(Collection(name='documents').find())))
        == n_data_points + 10
    )


def test_like(with_vector_index):
    db = with_vector_index
    r = db.execute(Collection(name='documents').find_one())
    query = Collection(name='documents').like(
        r=Document({'x': r['x']}),
        vector_index='test_vector_search',
    )
    s = next(db.execute(query))
    assert r['_id'] == s['_id']


def test_insert_one(random_data, a_watcher, a_single_insert):
    out, _ = random_data.execute(
        Collection(name='documents').insert_one(a_single_insert)
    )
    r = random_data.execute(
        Collection(name='documents').find({'_id': out.inserted_ids[0]})
    )
    docs = list(r)
    assert docs[0]['x'].x.tolist() == a_single_insert['x'].x.tolist()


def test_delete_one(random_data):
    r = random_data.execute(Collection(name='documents').find_one())
    random_data.execute(Collection(name='documents').delete_one({'_id': r['_id']}))
    with pytest.raises(StopIteration):
        next(random_data.execute(Collection(name='documents').find({'_id': r['_id']})))


def test_find(random_data):
    r = random_data.execute(Collection(name='documents').find().limit(1))
    assert len(list(r)) == 1


def test_find_one(random_data):
    r = random_data.execute(Collection(name='documents').find_one())
    assert isinstance(r, Document)


def test_aggregate(random_data):
    r = random_data.execute(
        Collection(name='documents').aggregate([{'$sample': {'size': 1}}])
    )
    assert len(list(r)) == 1


def test_replace_one(random_data):
    new_x = torch.randn(32)
    t = random_data.encoders['torch.float32[32]']
    r = random_data.execute(Collection(name='documents').find_one())
    random_data.execute(
        Collection(name='documents').replace_one(
            {'_id': r['_id']}, Document({'x': t(new_x)})
        )
    )
    doc = random_data.execute(Collection(name='documents').find_one({'_id': r['_id']}))
    assert doc.unpack()['x'].tolist() == new_x.tolist()
