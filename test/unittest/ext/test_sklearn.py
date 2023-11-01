import random

import numpy
import pytest
from sklearn.base import TransformerMixin
from sklearn.pipeline import Pipeline
from sklearn.svm import SVC

from pinnacledb.backends.mongodb.query import Collection
from pinnacledb.base.document import Document
from pinnacledb.ext.sklearn.model import Estimator


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
        yield ['apple', 'orange', 'banana', 'toast']

    @pytest.fixture()
    def pipeline(self, dictionary):
        yield Estimator(
            identifier='my-svc',
            object=Pipeline([('my-encoding', Lookup(dictionary)), ('my-svc', SVC())]),
        )

    @pytest.fixture()
    def X(self, dictionary):
        yield [random.choice(dictionary) for _ in range(100)]

    @pytest.fixture()
    def data_in_db(self, local_empty_db, X, y):
        local_empty_db.execute(
            Collection('documents').insert_many(
                [Document({'X': x, 'y': yy}) for x, yy in zip(X, y)]
            )
        )
        yield local_empty_db

    @pytest.fixture()
    def y(self):
        yield (numpy.random.rand(100) > 0.5).astype(int).tolist()

    def test_fit_predict_classic(self, pipeline, X, y):
        pipeline.fit(X, y)
        output = pipeline.predict(X)
        assert len(output) == len(X)

    def test_fit_db(self, pipeline, data_in_db):
        pipeline.fit(
            X='X',
            y='y',
            db=data_in_db,
            select=Collection('documents').find(),
        )
