from test.db_config import DBConfig

import pytest

from pinnacledb.backends.mongodb.query import Collection
from pinnacledb.components.listener import Listener
from pinnacledb.components.model import ObjectModel


def test_listener_serializes_properly():
    q = Collection('test').find({}, {})
    listener = Listener(
        model=ObjectModel('test', object=lambda x: x),
        select=q,
        key='test',
    )
    r = listener.dict().encode()

    # check that the result is JSON-able
    import json

    print(json.dumps(r, indent=2))


@pytest.mark.parametrize("db", [DBConfig.mongodb_empty], indirect=True)
def test_listener_chaining(db):
    collection = Collection('test')
    data = []
    import random

    from pinnacledb import Document

    def insert_random():
        for _ in range(5):
            y = int(random.random() > 0.5)
            x = int(random.random() > 0.5)
            data.append(
                Document(
                    {
                        'x': x,
                        'y': y,
                    }
                )
            )

        db.execute(collection.insert_many(data))

    # Insert data
    insert_random()

    m1 = ObjectModel(
        'm1', object=lambda x: x + 1, model_update_kwargs={'document_embedded': False}
    )
    m2 = ObjectModel('m2', object=lambda x: x + 2)

    listener1 = Listener(
        model=m1,
        select=collection.find({}),
        key='x',
    )

    listener2 = Listener(
        model=m2,
        select=Collection('_outputs.x.m1.0').find(),
        key='_outputs.x.m1.0',
    )

    db.add(listener2)
    db.add(listener1)
    docs = db.execute(Collection('_outputs.x.m1.0').find_one({}))

    assert docs['_outputs']['x']['m2']

    # TODO: add more data and next test

    # Insert more data
    insert_random()
    docs = list(db.execute(Collection('_outputs.x.m1.0').find({})))

    assert all(['m2' in d['_outputs']['x'] for d in docs])
