import datetime
import importlib
import json
import os
import platform
import socket
import sys
import typing as t
from pathlib import Path

from pinnacledb import ROOT
from pinnacledb.base.exceptions import RequiredPackageVersionsNotFound

from . import command

PYPROJECT = ROOT / 'pyproject.toml'


@command(help='Print information about the current machine and installation')
def info():
    print('```')
    print(json.dumps(_get_info(), default=str, indent=2))
    print('```')


@command(help='Print information about the current machine and installation')
def requirements(ext: t.List[str]):
    out = []
    for e in ext:
        try:
            m = importlib.import_module(f'pinnacledb.ext.{e}')
            out.extend(m.requirements)
        except RequiredPackageVersionsNotFound as e:
            out.extend([x for x in str(e).split('\n') if x])
    print('\n'.join(out))


def _get_info():
    return {
        'cfg': _cfg(),
        'cwd': Path.cwd(),
        'freeze': _freeze(),
        'hostname': socket.gethostname(),
        'os_uname': list(os.uname()),
        'package_versions': _package_versions(),
        'platform': _platform(),
        'startup_time': datetime.datetime.now(),
        'pinnacle_db_root': ROOT,
        'sys': _sys(),
    }


def _cfg():
    try:
        from pinnacledb import CFG

        return CFG.dict()
    except Exception:
        return '(CFG not yet commited)'


def _freeze():
    try:
        from pip._internal.operations.freeze import freeze

        return list(freeze())
    except Exception as e:
        return [f'Freeze failed with {e}']


def _package_versions():
    return {}


def _platform():
    return {
        'platform': platform.platform(),
        'python_version': platform.python_version(),
    }


def _sys():
    return {'argv': sys.argv, 'path': sys.path}
