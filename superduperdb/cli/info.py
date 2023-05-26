from . import command
from pathlib import Path
from pinnacledb import ROOT
from pinnacledb.misc import run
import datetime
import json
import os
import platform
import socket
import sys

PYPROJECT = ROOT / 'pyproject.toml'


@command(help='Print information about the current machine and installation')
def info():
    print(json.dumps(_get_info(), default=str, indent=2))


def _get_info():
    return {
        'cfg': _cfg(),
        'cwd': Path.cwd(),
        'git': _git(),
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


def _gethostname():
    try:
        return socket.gethostname()
    except Exception as e:
        return f'socket.gethostname() failed with {e}'


def _git():
    def run_out(key, *cmd):
        try:
            return run.out(cmd, cwd=ROOT)
        except Exception as e:
            return f'{cmd} failed with {e}'

    return {
        'branch': run_out('git', 'branch', '--show-current'),
        'commit': run_out('git', 'show', '-s', '--format="%h: %s"'),
    }


def _package_versions():
    return {}


def _platform():
    return {
        'platform': platform.platform(),
        'python_version': platform.python_version(),
    }


def _sys():
    return {'argv': sys.argv, 'path': sys.path}
