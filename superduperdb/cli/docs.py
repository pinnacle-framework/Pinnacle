from . import command
from pinnacledb import ROOT
from pinnacledb.misc import run
from pinnacledb.misc.git import Git, git
from typer import Argument, Option
import functools
import shutil
import sys

DOCS = 'docs'
DOCS_ROOT = ROOT / DOCS
SOURCE_ROOT = DOCS_ROOT / 'source'
CODE_ROOT = ROOT / 'pinnacledb'
GH_PAGES = ROOT / '.cache/gh-pages'
UPSTREAM = 'git@github.com:SuperDuperDB/pinnacledb-stealth.git'

run_gh = functools.partial(run.run, cwd=GH_PAGES)
out_gh = functools.partial(run.out, cwd=GH_PAGES)
git_gh = Git(out=run_gh)  # type: ignore[call-arg]


@command(help='Build documentation, optionally committing and pushing got ')
def docs(
    commit_message: str = Argument(
        '',
        help=(
            'The git commit message for the docs update.'
            'An empty message means do not commit and push.'
        ),
    ),
    _open: bool = Option(
        False,
        '-o',
        '--open',
        help='If true, open the index.html of the generated pages on completion',
    ),
    push_local_to_upstream: bool = Option(
        False, help='If True, DO NOT BUILD, just push to upstream'
    ),
    remote: str = Option('origin', help='The remote to push to'),
):
    if push_local_to_upstream:
        if git_gh.is_dirty():
            sys.exit('You did not commit your work in gh-pages')
        else:
            git_gh('push', 'upstream', 'gh-pages')
        return

    if not GH_PAGES.exists():
        _make_gh_pages()
    else:
        git_gh('pull')

    _clean()
    run_gh(('sphinx-apidoc', '-f', '-o', str(SOURCE_ROOT), str(CODE_ROOT)))
    run_gh(('sphinx-build', '-a', str(DOCS_ROOT), '.'))

    if commit_message:
        git_gh('add', '.')
        git_gh('commit', '-m', commit_message)
        git_gh('push', remote, 'gh-pages')

    if _open:
        run_gh(('open', 'index.html'))


def _make_gh_pages():
    GH_PAGES.mkdir(parents=True)

    configs = git.configs()
    branches = git.branches()

    origin = configs['remote.origin.url']

    exists = 'gh-pages' in branches['origin']
    if exists:
        git_gh('clone', origin, '-b', 'gh-pages', '.')
    else:
        git_gh('clone', origin, '.')

    git_gh('remote', 'add', 'upstream', UPSTREAM)
    git_gh('fetch', 'upstream')
    git_gh('switch', '-C', 'gh-pages', 'upstream/gh-pages')
    git_gh('push', '--force-with-lease', '--set-upstream', 'origin')


def _clean():
    if SOURCE_ROOT.exists():
        shutil.rmtree(SOURCE_ROOT)

    for i in GH_PAGES.iterdir():
        if i.name != '.git':
            if i.is_dir():
                shutil.rmtree(i)
            else:
                i.unlink()
