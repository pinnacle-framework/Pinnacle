import datetime
import inspect
from functools import wraps
import uuid

from pinnacledb.cluster.annotations import encode_args, encode_kwargs
from pinnacledb.cluster.function_job import function_job
from pinnacledb.cluster.dask.dask_client import dask_client
from pinnacledb.misc.logger import logging
from pinnacledb import CFG


def work(f):
    sig = inspect.signature(f)
    if CFG.remote:
        _dask_client = dask_client()

    @wraps(f)
    def work_wrapper(database, *args, remote=None, **kwargs):
        if remote is None:
            remote = database.remote
        if remote:
            args = encode_args(database, sig, args)
            kwargs = encode_kwargs(database, sig, kwargs)
            job_id = str(uuid.uuid4())
            database._create_job_record(
                {
                    'identifier': job_id,
                    'time': datetime.datetime.now(),
                    'status': 'pending',
                    'method': f.__name__,
                    'args': args,
                    'kwargs': kwargs,
                    'stdout': [],
                    'stderr': [],
                }
            )
            kwargs['remote'] = False
            return _dask_client.submit(
                function_job,
                database._database_type,
                database.name,
                f.__name__,
                args,
                kwargs,
                job_id,
                key=job_id,
            )
        else:
            logging.debug(database)
            logging.debug(args)
            logging.debug(kwargs)
            return f(database, *args, **kwargs)

    work_wrapper.signature = sig
    return work_wrapper
