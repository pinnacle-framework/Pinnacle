import time
import uuid
from contextlib import contextmanager

import pytest
import torch

from pinnacledb.container.document import Document
from pinnacledb.container.listener import Listener
from pinnacledb.db.base.cdc import DatabaseListener
from pinnacledb.db.mongodb.query import Collection

# NOTE 1:
# Some environments take longer than others for the changes to appear. For this
# reason this module has a special retry wrapper function.
#
# If you find yourself experiencing non-deterministic test runs which are linked
# to this module, consider increasing the number of retry attempts.

# NOTE 2:
# Each fixture writes to a collection with a unique name. This means that the
# tests can be run in parallel without interactions between the tests. Be very
# careful if you find yourself changing the name of a collection in this module...

# NOTE 3:
# TODO: Modify this module so that the tests are actually run in parallel...


@pytest.fixture(scope="function")
def listener_and_collection_name(database_with_default_encoders_and_model):
    collection_name = str(uuid.uuid4())
    listener = DatabaseListener(
        db=database_with_default_encoders_and_model, on=Collection(name=collection_name)
    )
    listener._cdc_change_handler._QUEUE_TIMEOUT = 1
    listener._cdc_change_handler._QUEUE_BATCH_SIZE = 1

    yield listener, collection_name

    listener.stop()


@pytest.fixture(scope="function")
def listener_without_cdc_handler_and_collection_name(
    database_with_default_encoders_and_model,
):
    collection_name = str(uuid.uuid4())
    listener = DatabaseListener(
        db=database_with_default_encoders_and_model, on=Collection(name=collection_name)
    )
    yield listener, collection_name
    listener.stop()


def retry_state_check(state_check):
    _attempts = 5
    while _attempts > 0:
        _attempts -= 1
        time.sleep(5 - _attempts)  # 1, 2, 3, 4, 5
        try:
            state_check()
            return
        except AssertionError:
            pass
    state_check()
    return


def test_smoke(listener_without_cdc_handler_and_collection_name):
    """Health-check before we test stateful database changes"""
    listener, name = listener_without_cdc_handler_and_collection_name
    listener.listen()
    assert isinstance(name, str)


def test_task_workflow_on_insert(
    listener_and_collection_name, database_with_default_encoders_and_model, fake_inserts
):
    """Test that task graph executed on `insert`"""

    listener, name = listener_and_collection_name
    listener.listen()

    with add_and_cleanup_listeners(
        database_with_default_encoders_and_model, name
    ) as database_with_listeners:
        # `refresh=False` to ensure `_outputs` not produced after `Insert` refresh.
        output_id, _ = database_with_listeners.execute(
            Collection(name=name).insert_many([fake_inserts[0]], refresh=False)
        )

        def state_check():
            doc = database_with_listeners.db[name].find_one(
                {'_id': output_id.inserted_ids[0]}
            )
            assert '_outputs' in list(doc.keys())

        retry_state_check(state_check)

        # state_check_2 can't be pinnacled with state_check because the
        # '_outputs' key needs to be present in 'doc'
        def state_check_2():
            doc = database_with_listeners.db[name].find_one(
                {'_id': output_id.inserted_ids[0]}
            )
            state = []
            state.append('model_linear_a' in doc['_outputs']['x'].keys())
            state.append('model_linear_a' in doc['_outputs']['z'].keys())
            assert all(state)

        retry_state_check(state_check_2)


def test_single_insert(
    listener_without_cdc_handler_and_collection_name,
    database_with_default_encoders_and_model,
    fake_inserts,
):
    listener, name = listener_without_cdc_handler_and_collection_name
    listener.listen()
    database_with_default_encoders_and_model.execute(
        Collection(name=name).insert_many([fake_inserts[0]])
    )

    def state_check():
        assert listener.info()["inserts"] == 1

    retry_state_check(state_check)


def test_many_insert(
    listener_without_cdc_handler_and_collection_name,
    database_with_default_encoders_and_model,
    fake_inserts,
):
    listener, name = listener_without_cdc_handler_and_collection_name
    listener.listen()
    database_with_default_encoders_and_model.execute(
        Collection(name=name).insert_many(fake_inserts)
    )

    def state_check():
        assert listener.info()["inserts"] == len(fake_inserts)

    retry_state_check(state_check)


def test_single_update(
    listener_without_cdc_handler_and_collection_name,
    database_with_default_encoders_and_model,
    fake_updates,
):
    listener, name = listener_without_cdc_handler_and_collection_name
    listener.listen()
    output_id, _ = database_with_default_encoders_and_model.execute(
        Collection(name=name).insert_many(fake_updates)
    )
    encoder = database_with_default_encoders_and_model.encoders['torch.float32[32]']
    database_with_default_encoders_and_model.execute(
        Collection(name=name).update_many(
            {"_id": output_id.inserted_ids[0]},
            Document({'$set': {'x': encoder(torch.randn(32))}}),
        )
    )

    def state_check():
        assert listener.info()["updates"] == 1

    retry_state_check(state_check)


def test_many_update(
    listener_without_cdc_handler_and_collection_name,
    database_with_default_encoders_and_model,
    fake_updates,
):
    listener, name = listener_without_cdc_handler_and_collection_name
    listener.listen()
    output_id, _ = database_with_default_encoders_and_model.execute(
        Collection(name=name).insert_many(fake_updates)
    )
    encoder = database_with_default_encoders_and_model.encoders['torch.float32[32]']
    database_with_default_encoders_and_model.execute(
        Collection(name=name).update_many(
            {"_id": {"$in": output_id.inserted_ids[:5]}},
            Document({'$set': {'x': encoder(torch.randn(32))}}),
        )
    )

    def state_check():
        assert listener.info()["updates"] == 5

    retry_state_check(state_check)


def test_insert_without_cdc_handler(
    listener_without_cdc_handler_and_collection_name,
    database_with_default_encoders_and_model,
    fake_inserts,
):
    """Test that `insert` without CDC handler does not execute task graph"""
    listener, name = listener_without_cdc_handler_and_collection_name
    listener.listen()
    output_id, _ = database_with_default_encoders_and_model.execute(
        Collection(name=name).insert_many(fake_inserts, refresh=True)
    )
    doc = database_with_default_encoders_and_model.db[name].find_one(
        {'_id': output_id.inserted_ids[0]}
    )
    assert '_outputs' not in doc.keys()


def test_cdc_stop(listener_and_collection_name):
    """Test that CDC listen service stopped properly"""
    listener, _ = listener_and_collection_name
    listener.listen()
    listener.stop()

    def state_check():
        assert not all(
            [listener._scheduler.is_alive(), listener._cdc_change_handler.is_alive()]
        )

    retry_state_check(state_check)


@contextmanager
def add_and_cleanup_listeners(database, collection_name):
    """Add listeners to the database and remove them after the test"""
    listener_x = Listener(
        key='x',
        model='model_linear_a',
        select=Collection(name=collection_name).find(),
    )

    listener_z = Listener(
        key='z',
        model='model_linear_a',
        select=Collection(name=collection_name).find(),
    )

    database.add(listener_x)
    database.add(listener_z)
    try:
        yield database
    finally:
        database.remove('listener', 'model_linear_a/x', force=True)
        database.remove('listener', 'model_linear_a/z', force=True)
