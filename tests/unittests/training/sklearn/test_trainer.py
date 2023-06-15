# ruff: noqa: F401, F811
from sklearn.svm import SVC

from pinnacledb.core.learning_task import LearningTask
from pinnacledb.datalayer.mongodb.query import Select
from pinnacledb.models.vanilla.wrapper import FunctionWrapper
from pinnacledb.training.sklearn.trainer import SklearnTrainingConfiguration
from pinnacledb.models.sklearn.wrapper import Pipeline

from tests.fixtures.collection import random_arrays, arrays, empty


def test_classifier(random_arrays):
    model = Pipeline([('svc', SVC(verbose=True))], 'svc')
    identity = FunctionWrapper(lambda x: x, 'identity')
    cf = SklearnTrainingConfiguration('my-sk-cf')
    random_arrays.add(cf)
    random_arrays.add(identity, serializer='dill')
    random_arrays.add(model)
    random_arrays.add(
        LearningTask(
            'my-sk-lt',
            models=['svc', 'identity'],
            keys=['x', 'y'],
            training_configuration='my-sk-cf',
            select=Select('documents'),
            metrics=[],
        )
    )
