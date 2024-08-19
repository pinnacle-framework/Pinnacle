import dataclasses as dc
import os
import shutil
import tempfile
import typing as t

import pytest

from pinnacle import ObjectModel
from pinnacle.components.component import Component
from pinnacle.components.datatype import (
    Artifact,
    DataType,
    Empty,
    LazyArtifact,
    dill_serializer,
)
from pinnacle.components.listener import Listener


@pytest.fixture
def cleanup():
    yield
    try:
        os.remove("test_export.tar.gz")
        shutil.rmtree("test_export")
    except FileNotFoundError:
        pass


@dc.dataclass(kw_only=True)
class MyComponent(Component):
    type_id: t.ClassVar[str] = "my_type"
    _lazy_fields: t.ClassVar[t.Sequence[str]] = ("my_dict",)
    my_dict: t.Dict
    nested_list: t.List
    a: t.Callable


def test_init(monkeypatch):
    from unittest.mock import MagicMock

    e = Artifact(x=None, identifier="123", datatype=dill_serializer)
    a = Artifact(x=None, identifier="456", datatype=dill_serializer)

    def side_effect(*args, **kwargs):
        a.x = lambda x: x + 1

    a.init = MagicMock()
    a.init.side_effect = side_effect

    list_ = [e, a]

    c = MyComponent("test", my_dict={"a": a}, a=a, nested_list=list_)

    c.init()

    assert callable(c.my_dict["a"])
    assert c.my_dict["a"](1) == 2

    assert callable(c.a)
    assert c.a(1) == 2

    assert callable(c.nested_list[1])
    assert c.nested_list[1](1) == 2


def test_load_lazily(db):
    m = ObjectModel("lazy_model", object=lambda x: x + 2)

    db.add(m)

    reloaded = db.load("model", m.identifier)

    assert isinstance(reloaded.object, LazyArtifact)
    assert isinstance(reloaded.object.x, Empty)

    reloaded.init(db=db)

    assert callable(reloaded.object)


def test_export_and_read():
    m = ObjectModel("test", object=lambda x: x + 2, datatype=dill_serializer)

    with tempfile.TemporaryDirectory() as tmpdir:
        save_path = os.path.join(tmpdir, "tmp_save")
        m.export(save_path)
        assert os.path.exists(os.path.join(tmpdir, "tmp_save", "blobs"))

        def load(blob):
            with open(blob, "rb") as f:
                return f.read()

        reloaded = Component.read(save_path)  # getters=getters

        assert isinstance(reloaded, ObjectModel)
        assert isinstance(reloaded.datatype, DataType)


def test_set_variables(db):
    m = Listener(
        identifier="test",
        model=ObjectModel(
            identifier="<var:test>",
            object=lambda x: x + 2,
        ),
        key="<var:key>",
        select=db["docs"].find(),
    )

    from pinnacle import Document

    e = m.encode()
    recon = Document.decode(e).unpack()

    recon.init(db=db)

    listener = m.set_variables(test="test_value", key="key_value", docs="docs_value")
    assert listener.model.identifier == "test_value"
    assert listener.key == "key_value"


def test_upstream(db):
    class MyComponent1(Component):
        triggered_schedule_jobs = False

        def schedule_jobs(self, *args, **kwargs):
            self.triggered_schedule_jobs = True
            return ('my_dependency_listener',)

    c1 = MyComponent1(identifier='c1')

    m = Listener(
        identifier='l1',
        upstream=c1,
        model=ObjectModel(
            identifier="model1",
            object=lambda x: x + 2,
        ),
        key="x",
        select=db["docs"].find(),
    )

    def mock_schedule_jobs(self, *args, **kwargs):
        assert kwargs == {'dependencies': ['my_dependency_listener']}
        return []

    m.schedule_jobs = mock_schedule_jobs
    db.apply(m)
    assert m.upstream.triggered_schedule_jobs == True  # noqa
