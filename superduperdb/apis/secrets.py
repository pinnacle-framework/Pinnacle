import importlib

from . import api_cf


def client_init():
    for provider in api_cf.get('providers', {}):
        importlib.import_module(f'pinnacledb.apis.{provider}.init').init_fn()
