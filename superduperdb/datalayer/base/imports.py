import importlib

from pinnacledb import cf


def get_database_from_database_type(database_type, database_name):
    """
    Import the database connection from ``pinnacledb``

    :param database_type: type of database (supported: ['mongodb'])
    :param database_name: name of database
    """
    module = importlib.import_module(f'pinnacledb.dbs.{database_type}.client')
    client_cls = getattr(module, 'SuperDuperClient')
    client = client_cls(**cf.get(database_type, {}))
    return client.get_database_from_name(database_name)