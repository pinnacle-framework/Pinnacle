from pinnacledb.misc.git import git
import os

IN_CI = 'CI' in os.environ
PUNCTUATION = '.,-_'


def _errors(msg):
    if len(msg) > 50:
        yield 'length greater than 50'
    if msg[0].islower():
        yield 'does not start with a capital letter'
    if ps := [p for p in PUNCTUATION if msg.endswith(p)]:
        yield f'ends with punctuation: "{ps[0]}"'


def test_config():
    config = git.configs()
    assert isinstance(config, dict)
    if IN_CI:
        assert 10 < len(config) < 20
    else:
        assert len(config) > 20
        assert 'user.email' in config


def test_commit_errors():
    msg = 'this is a very very very very very very very bad error message.'

    actual = ', '.join(_errors(msg))
    expected = (
        'length greater than 50, '
        'does not start with a capital letter, '
        'ends with punctuation: "."'
    )
    assert actual == expected


def test_last_commit_names():
    # If you get here, it's because one of your last commit messages was suboptimal

    commits = git.commits('-10')
    if IN_CI:
        commits.pop(0)

    bad_commits = []

    for commit in commits:
        commit_id, date, msg = commit.split('|')
        if errors := ', '.join(_errors(msg)):
            bad_commits.append(f'{commit_id}: "{msg}":\n    {errors}')

    if bad_commits:
        print(*bad_commits, sep='\n')
        assert not bad_commits
