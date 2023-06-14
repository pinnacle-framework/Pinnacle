from pinnacledb.datalayer.base.imports import get_database_from_database_type
import traceback
from pinnacledb.cluster.logging import handle_function_output


def function_job(database_type, database_name, function_name, args_, kwargs_, job_id):
    database = get_database_from_database_type(database_type, database_name)
    database.remote = False
    function = getattr(database, function_name)
    database.metadata.update_job(job_id, 'status', 'running')
    try:
        handle_function_output(
            function,
            database,
            job_id,
            *args_,
            **kwargs_,
        )
    except Exception as e:
        tb = traceback.format_exc()
        database.metadata.update_job(job_id, 'status', 'failed')
        database.metadata.update_job(job_id, 'msg', tb)
        raise e
    database.set_job_flag(job_id, ('status', 'success'))
