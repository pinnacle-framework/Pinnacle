import uuid

import pytest

from pinnacledb import logging

try:
    import torch
except ImportError:
    torch = None
from contextlib import contextmanager

from pinnacledb.backends.mongodb.query import Collection
from pinnacledb.components.listener import Listener
from pinnacledb.jobs.job import FunctionJob
from pinnacledb.jobs.task_workflow import TaskWorkflow


@contextmanager
def add_and_cleanup_listener(database, collection_name):
    """Add listener to the database and remove it after the test"""
    listener_x = Listener(
        key='x',
        model='model_linear_a',
        select=Collection(identifier=collection_name).find(),
    )

    database.add(listener_x)
    try:
        yield database
    finally:
        database.remove('listener', 'model_linear_a/x', force=True)


@pytest.mark.skipif(not torch, reason='Torch not installed')
def test_taskgraph_futures_with_dask(
    local_dask_client, database_with_default_encoders_and_model, fake_updates
):
    collection_name = str(uuid.uuid4())
    database_with_default_encoders_and_model.distributed = True
    database_with_default_encoders_and_model._distributed_client = local_dask_client
    _, graph = database_with_default_encoders_and_model.execute(
        Collection(identifier=collection_name).insert_many(fake_updates)
    )

    next(
        database_with_default_encoders_and_model.execute(
            Collection(identifier=collection_name).find({'update': True})
        )
    )
    local_dask_client.wait_all_pending_tasks()

    nodes = graph.G.nodes
    jobs = [nodes[node]['job'] for node in nodes]

    assert all([job.future.status == 'finished' for job in jobs])


@pytest.mark.skipif(not torch, reason='Torch not installed')
@pytest.mark.parametrize(
    'local_dask_client, test_db',
    [('test_insert_with_distributed', 'test_insert_with_distributed')],
    indirect=True,
)
def test_insert_with_dask(
    local_dask_client, database_with_default_encoders_and_model, fake_updates
):
    collection_name = str(uuid.uuid4())

    with add_and_cleanup_listener(
        database_with_default_encoders_and_model,
        collection_name,
    ) as db:
        # Submit job
        db.distributed = True
        db._distributed_client = local_dask_client
        db.execute(Collection(identifier=collection_name).insert_many(fake_updates))

        # Barrier
        local_dask_client.wait_all_pending_tasks()

        # Get distributed logs
        logs = local_dask_client.client.get_worker_logs()

        logging.info("worker logs", logs)

        # Assert result
        q = Collection(identifier=collection_name).find({'update': True})
        r = next(db.execute(q))
        assert 'model_linear_a' in r['_outputs']['x']


@pytest.mark.skipif(not torch, reason='Torch not installed')
def test_dependencies_with_dask(
    local_dask_client, database_with_default_encoders_and_model
):
    database = database_with_default_encoders_and_model

    def test_node_1(*args, **kwargs):
        return 1

    def test_node_2(*args, **kwargs):
        return 2

    G = TaskWorkflow(database)
    G.add_node(
        'test_node_1',
        job=FunctionJob(callable=test_node_1, kwargs={}, args=[]),
    )

    G.add_node(
        'test_node_2',
        job=FunctionJob(callable=test_node_2, kwargs={}, args=[]),
    )
    G.add_edge(
        'test_node_1',
        'test_node_2',
    )
    local_dask_client.futures_collection.clear()

    database.distributed = True
    database._distributed_client = local_dask_client
    G.run_jobs(distributed=True)
    local_dask_client.wait_all_pending_tasks()
    futures = list(local_dask_client.futures_collection.values())
    assert len(futures) == 2
    assert futures[0].status == 'finished'
    assert futures[1].status == 'finished'
    assert futures[0].result() == 1
    assert futures[1].result() == 2
