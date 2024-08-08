import random
from test.utils.component import utils as component_utils

import numpy
import pytest
from sklearn.base import TransformerMixin
from sklearn.pipeline import Pipeline
from sklearn.svm import SVC

from pinnacle.backends.base.query import Query
from pinnacle.base.document import Document
from pinnacle.ext.sklearn.model import Estimator, SklearnTrainer


class Lookup(TransformerMixin):
    def __init__(self, dictionary):
        table = numpy.random.randn(len(dictionary), 32)
        self.dictionary = {d: table[i] for i, d in enumerate(dictionary)}

    def fit(self, X, y=None):
        return self

    def transform(self, X):
        if isinstance(X, list):
            return [self.dictionary[x] for x in X]
        else:
            return self.dictionary[X]


class TestPipeline:
    @pytest.fixture()
    def dictionary(self):
        yield ["apple", "orange", "banana", "toast"]

    @pytest.fixture()
    def X(self, dictionary):
        yield [random.choice(dictionary) for _ in range(100)]

    @pytest.fixture()
    def data_in_db(self, db, X, y):
        db.cfg.auto_schema = True
        db.execute(
            db["documents"].insert([Document({"X": x, "y": yy}) for x, yy in zip(X, y)])
        )
        yield db

    @pytest.fixture()
    def y(self):
        yield (numpy.random.rand(100) > 0.5).astype(int).tolist()

    def test_fit_db(self, dictionary, data_in_db):
        pipeline = Estimator(
            identifier="my-svc",
            object=Pipeline([("my-encoding", Lookup(dictionary)), ("my-svc", SVC())]),
            trainer=SklearnTrainer(
                "my-trainer",
                key=("X", "y"),
                select=data_in_db["documents"].select(),
            ),
        )
        _ = data_in_db.apply(pipeline)


def test_encode_and_decode():
    model = Estimator(
        identifier="my-svc",
        object=Pipeline(
            [
                ("my-encoding", Lookup(["apple", "orange", "banana", "toast"])),
                ("my-svc", SVC()),
            ]
        ),
        trainer=SklearnTrainer(
            "my-trainer",
            key=("X", "y"),
            select=Query(table="document").select(),
        ),
    )
    decode_model = component_utils.test_encode_and_decode(model)

    assert decode_model.trainer.identifier == "my-trainer"
    assert decode_model.trainer.key == ("X", "y")
    assert decode_model.trainer.select.table == "document"
