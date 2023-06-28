from pinnacledb.core.base import Component

import typing as t


class Metric(Component):
    """
    Metric base object with which to evaluate performance on a data-set.
    These objects are ``callable`` and are applied row-wise to the data, and averaged.
    """

    variety = 'metric'

    def __init__(self, identifier: str, object: t.Callable):
        super().__init__(identifier)
        self.object = object

    def __call__(self, x, y):
        return self.object(x, y)
