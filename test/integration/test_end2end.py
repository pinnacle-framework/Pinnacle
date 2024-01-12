import random
import time

import numpy as np
import pytest
from PIL import Image

from pinnacledb.backends.mongodb.query import Collection
from pinnacledb.base.document import Document
from pinnacledb.components.listener import Listener
from pinnacledb.components.model import Model
from pinnacledb.components.schema import Schema
from pinnacledb.components.vector_index import VectorIndex
from pinnacledb.ext.pillow.encoder import pil_image

# Setup:
# Take empty database
# Add two models
# Add encoder
# create custom serializer
# take output from model 1 as input to model 2
# create listener for model1 and model2
# add new data to collection
# delete data on collection
# start cdc service
# add new data to collection
# collection should have one image, one string, one float, one int data
# Make the entire service as distributed on dask


class Model1:
    def predict(self, x):
        return [
            {
                'image': Image.fromarray(np.random.randn(10, 10, 3).astype(np.uint8)),
                'int': np.asarray([x * 100] * 10),
            }
        ] * random.randint(1, 2)

    @staticmethod
    def preprocess(x):
        return x

    @staticmethod
    def postprocess(x):
        return x


class Model2:
    def predict(self, x):
        if isinstance(x, str):
            return np.asarray([int(x) * 100] * 10)
        return x

    @staticmethod
    def preprocess(x):
        return x

    @staticmethod
    def postprocess(x):
        return x


def _wait_for_keys(db, collection='_outputs.int.model1', n=10, key=''):
    retry_left = 5

    def check_outputs():
        docs = list(db.databackend.db[collection].find({}))
        p = 0
        for d in docs:
            try:
                for k in key.split('.'):
                    d = d[k]
            except KeyError:
                pass
            else:
                p += 1
        return len(docs) == p

    while not check_outputs() and retry_left != 0:
        time.sleep(2)
        retry_left -= 1


def _wait_for_outputs(db, collection='_outputs.int.model1', n=10):
    retry_left = 5

    def check_outputs():
        docs = list(db.databackend.db[collection].find({}))
        return docs

    while not len(check_outputs()) >= n and retry_left != 0:
        time.sleep(2)
        retry_left -= 1
    return len(check_outputs())


@pytest.fixture
def distributed_db(monkeypatch, test_db, dask_client):
    from pinnacledb import CFG

    existing_databackend = CFG.data_backend
    CFG.force_set(
        'data_backend', 'mongodb://pinnacle:pinnacle@mongodb:27017/test_db'
    )
    cdc = 'http://localhost:8001'
    vector_search = 'in_memory://localhost:8000'
    monkeypatch.setattr(CFG.cluster.cdc, 'uri', cdc)
    monkeypatch.setattr(CFG.cluster, 'vector_search', vector_search)
    test_db.set_compute(dask_client)

    def update_syspath():
        import sys

        sys.path.append('./')

    test_db.get_compute().submit(update_syspath)

    yield test_db
    CFG.force_set('data_backend', existing_databackend)
    monkeypatch.setattr(CFG.cluster, 'cdc', None)
    monkeypatch.setattr(CFG.cluster, 'vector_search', None)


def test_advance_setup(distributed_db, image_url):
    db = distributed_db
    # Take empty database

    image = [
        {
            '_content': {
                'uri': image_url,
                'encoder': 'pil_image',
            }
        }
    ]

    raw_bytes = 'some raw bytes'.encode('utf-8')
    data = [
        Document(
            {
                'image': image,
                'int': i,
                'text': str(i),
                'float': float(i),
                'raw_bytes': raw_bytes,
            }
        )
        for i in range(5)
    ]

    mixed_input = Collection('mixed_input')
    db.add(pil_image)
    db.execute(Collection('mixed_input').insert_many(data))

    from pinnacledb.ext.numpy import array

    model1 = Model(
        identifier='model1',
        object=Model1(),
        preprocess=Model1.preprocess,
        postprocess=Model1.postprocess,
        flatten=True,
        model_update_kwargs={'document_embedded': False},
        output_schema=Schema(
            identifier='myschema',
            fields={'image': pil_image, 'int': array('int64', (10,))},
        ),
        predict_method='predict',
    )
    db.add(model1)

    e = array('int64', (10,))

    model2 = Model(
        identifier='model2',
        object=Model2(),
        preprocess=Model2.preprocess,
        postprocess=Model2.postprocess,
        predict_method='predict',
        encoder=e,
    )
    db.add(model2)

    listener1 = Listener(
        model=db.load('model', 'model1'), key='int', select=mixed_input.find()
    )
    db.add(listener1)
    n = _wait_for_outputs(db=db, n=10)

    db.add(
        VectorIndex(
            identifier='test_search_index',
            measure='l2',
            indexing_listener=Listener(
                model=model2,
                key='_outputs.int.model1.0.int',
                select=Collection('_outputs.int.model1').find(),
            ),
            compatible_listener=Listener(
                model=model2, key='text', select=None, active=False
            ),
        )
    )

    search_phrase = '4'
    _wait_for_keys(
        db=db, n=n, collection='_outputs.int.model1', key='_outputs.int.model2'
    )

    r = next(
        db.execute(
            Collection('_outputs.int.model1')
            .like(
                Document({'text': search_phrase}), vector_index='test_search_index', n=1
            )
            .find()
        )
    )
    r = r.unpack()

    assert '_outputs' in r
    assert np.allclose(
        np.asarray([400] * 10), r['_outputs']['int']['model1']['0']['int']
    )
