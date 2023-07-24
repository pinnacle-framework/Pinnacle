import subprocess
import os
import tempfile
import shutil

import pytest


@pytest.fixture(scope="module")
def copy_pinnacledb():
    with tempfile.TemporaryDirectory() as tmp_dir:
        shutil.copytree('pinnacledb', os.path.join(tmp_dir, 'pinnacledb'))
        yield tmp_dir


def run_python_file(file_path, tmp_dir):
    completed_process = subprocess.run(
        ['jupyter', 'nbconvert', file_path, '--output-dir', tmp_dir, '--to', 'python'],
        capture_output=True,
        text=True,
    )

    py_file_path = os.path.basename(os.path.splitext(file_path)[0]) + '.py'

    completed_process = subprocess.run(
        ['python3', os.path.join(tmp_dir, py_file_path)],
        capture_output=True,
        text=True,
        timeout=60 * 2,
    )
    print(completed_process.stdout)
    assert completed_process.returncode == 0


NOTEBOOKS = [
    'notebooks/mnist_clean.ipynb',
]


@pytest.mark.skipif(
    os.environ.get('NB_TEST', 0) == 0, reason="Notebook tests are disabled"
)
@pytest.mark.parametrize("nb_file", NOTEBOOKS)
def test_notebooks(nb_file, copy_pinnacledb):
    run_python_file(nb_file, tmp_dir=copy_pinnacledb)
