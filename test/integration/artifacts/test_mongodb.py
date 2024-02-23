import dataclasses as dc
import filecmp
import os
import typing as t

import pytest

from pinnacledb.backends.local.artifacts import FileSystemArtifactStore
from pinnacledb.components.component import Component
from pinnacledb.components.datatype import (
    DataType,
    file_serializer,
    serializers,
)


@dc.dataclass(kw_only=True)
class TestComponent(Component):
    path: str
    type_id: t.ClassVar[str] = "TestComponent"

    _artifacts: t.ClassVar[t.Sequence[t.Tuple[str, "DataType"]]] = (
        ("path", file_serializer),
    )


@pytest.fixture
def artifact_strore(tmpdir) -> FileSystemArtifactStore:
    artifact_strore = FileSystemArtifactStore(f"{tmpdir}")
    artifact_strore._serializers = serializers
    return artifact_strore


def test_save_and_load_directory(test_db):
    # test save and load directory
    directory = os.path.join(os.getcwd(), "pinnacledb")
    test_component = TestComponent(path=directory, identifier="test")
    test_db.add(test_component)
    test_component_loaded = test_db.load("TestComponent", "test")
    test_component_loaded.init()
    # assert that the paths are different
    assert test_component.path != test_component_loaded.path
    # assert that the directory names are the same
    assert (
        os.path.split(test_component.path)[-1]
        == os.path.split(test_component_loaded.path)[-1]
    )
    # assert that the directory sizes are the same
    assert os.path.getsize(test_component.path) == os.path.getsize(
        test_component_loaded.path
    )


def test_save_and_load_file(test_db):
    # test save and load file
    file = os.path.abspath(__file__)
    test_component = TestComponent(path=file, identifier="test")
    test_db.add(test_component)
    test_component_loaded = test_db.load("TestComponent", "test")
    test_component_loaded.init()
    # assert that the paths are different
    assert test_component.path != test_component_loaded.path
    # assert that the file names are the same
    assert (
        os.path.split(test_component.path)[-1]
        == os.path.split(test_component_loaded.path)[-1]
    )
    # assert that the file sizes are the same
    assert filecmp.cmp(test_component.path, test_component_loaded.path)
