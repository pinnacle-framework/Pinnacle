from . import command
from pinnacledb import ROOT
from pinnacledb.misc import run

DOCS = 'docs'
DOCS_ROOT = ROOT / DOCS


@command(help='Build documentation')
def docs():
    run.run(('make', 'clean'), cwd=DOCS_ROOT)
    run.run(('make', 'html'), cwd=DOCS_ROOT)
