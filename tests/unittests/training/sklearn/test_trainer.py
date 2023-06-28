# ruff: noqa: F401, F811
from sklearn.svm import SVC

from pinnacledb.core.fit import Fit
from pinnacledb.datalayer.mongodb.query import Select
from pinnacledb.models.vanilla.wrapper import FunctionWrapper
from pinnacledb.models.sklearn.wrapper import Pipeline, SklearnTrainingConfiguration

from tests.fixtures.collection import random_arrays, arrays, empty


def test_classifier(random_arrays):
    model = Pipeline('svc', [('svc', SVC(verbose=True))])
    identity = FunctionWrapper(lambda x: x, 'identity')
    cf = SklearnTrainingConfiguration('my-sk-cf')
    random_arrays.add(cf)
    random_arrays.add(identity, serializer='dill')
    random_arrays.add(model)
    random_arrays.add(
        Fit(
            'my-sk-lt',
            model=model.identifier,
            keys=['x', 'y'],
            training_configuration='my-sk-cf',
            select=Select(collection='documents'),
            metrics=[],
        )
    )
