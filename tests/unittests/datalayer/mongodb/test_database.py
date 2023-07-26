import PIL.PngImagePlugin
import pytest
import torch
from pinnacledb.core.dataset import Dataset
from pinnacledb.core.document import Document
from pinnacledb.core.encoder import Encoder
from pinnacledb.core.exceptions import ComponentInUseError, ComponentInUseWarning
from pinnacledb.core.watcher import Watcher
from pinnacledb.datalayer.mongodb.query import Collection
from pinnacledb.encoders.torch.tensor import tensor
from pinnacledb.models.torch.wrapper import TorchModel

n_data_points = 250

IMAGE_URL = 'https://www.pinnacledb.com/logos/white.png'


def test_create_component(empty, float_tensors_16, float_tensors_32):
    empty.add(TorchModel(object=torch.nn.Linear(16, 32), identifier='my-test-module'))
    assert 'my-test-module' in empty.show('model')
    model = empty.models['my-test-module']
    print(model)
    output = model.predict(torch.randn(16), one=True)
    assert output.shape[0] == 32


def test_update_component(empty):
    empty.add(TorchModel(object=torch.nn.Linear(16, 32), identifier='my-test-module'))
    m = TorchModel(object=torch.nn.Linear(16, 32), identifier='my-test-module')
    empty.add(m)
    assert empty.show('model', 'my-test-module') == [0, 1]
    empty.add(m)
    assert empty.show('model', 'my-test-module') == [0, 1]

    n = empty.models[m.identifier]
    empty.add(n)
    assert empty.show('model', 'my-test-module') == [0, 1]


def test_compound_component(empty):
    t = tensor(torch.float, shape=(32,))

    m = TorchModel(
        object=torch.nn.Linear(16, 32),
        identifier='my-test-module',
        encoder=t,
    )

    empty.add(m)
    assert 'torch.float32[32]' in empty.show('encoder')
    assert 'my-test-module' in empty.show('model')
    assert empty.show('model', 'my-test-module') == [0]

    empty.add(m)
    assert empty.show('model', 'my-test-module') == [0]
    assert empty.show('encoder', 'torch.float32[32]') == [0]

    empty.add(
        TorchModel(
            object=torch.nn.Linear(16, 32),
            identifier='my-test-module',
            encoder=t,
        )
    )
    assert empty.show('model', 'my-test-module') == [0, 1]
    assert empty.show('encoder', 'torch.float32[32]') == [0]

    m = empty.load(variety='model', identifier='my-test-module')
    assert isinstance(m.encoder, Encoder)

    with pytest.raises(ComponentInUseError):
        empty.remove('encoder', 'torch.float32[32]')

    with pytest.warns(ComponentInUseWarning):
        empty.remove('encoder', 'torch.float32[32]', force=True)

    empty.remove('model', 'my-test-module', force=True)


def test_select_vanilla(random_data):
    r = random_data.execute(Collection(name='documents').find_one())
    print(r)


def test_select(with_vector_index):
    db = with_vector_index
    r = db.execute(Collection(name='documents').find_one())
    query = Collection(name='documents').like(
        r=Document({'x': r['x']}),
        vector_index='test_vector_search',
    )
    s = next(db.execute(query))
    assert r['_id'] == s['_id']


def test_reload_dataset(si_validation):
    si_validation.load('dataset', 'my_valid')


def test_insert(random_data, a_watcher, an_update):
    random_data.execute(Collection(name='documents').insert_many(an_update))
    r = next(random_data.execute(Collection(name='documents').find({'update': True})))
    assert 'linear_a' in r['_outputs']['x']
    assert (
        len(list(random_data.execute(Collection(name='documents').find())))
        == n_data_points + 10
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


def test_update(random_data, a_watcher):
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


def test_watcher(random_data, a_model, b_model):
    random_data.add(
        Watcher(
            model='linear_a',
            select=Collection(name='documents').find(),
            key='x',
        ),
    )
    r = random_data.execute(Collection(name='documents').find_one())
    assert 'linear_a' in r['_outputs']['x']

    t = random_data.encoders['torch.float32[32]']

    random_data.execute(
        Collection(name='documents').insert_many(
            [Document({'x': t(torch.randn(32)), 'update': True}) for _ in range(5)]
        )
    )

    r = random_data.execute(Collection(name='documents').find_one({'update': True}))
    assert 'linear_a' in r['_outputs']['x']

    random_data.add(
        Watcher(
            model='linear_b',
            select=Collection(name='documents').find().featurize({'x': 'linear_a'}),
            key='x',
        )
    )
    r = random_data.execute(Collection(name='documents').find_one())
    assert 'linear_b' in r['_outputs']['x']


def test_predict(a_model, float_tensors_32, float_tensors_16):
    t = float_tensors_32.encoders['torch.float32[32]']
    a_model.predict('linear_a', Document(t(torch.randn(32))))


def test_delete(random_data):
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


def test_dataset(random_data):
    d = Dataset(
        identifier='test_dataset',
        select=Collection(name='documents').find({'_fold': 'valid'}),
    )
    random_data.add(d)
    assert random_data.show('dataset') == ['test_dataset']
    dataset = random_data.load('dataset', 'test_dataset')
    assert len(dataset.data) == len(list(random_data.execute(dataset.select)))
