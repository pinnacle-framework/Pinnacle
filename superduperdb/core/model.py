from typing import Any, Optional, Union

from pinnacledb.core.base import Component, Placeholder
from pinnacledb.core.encoder import Encoder


class Model(Component):
    """
    Model component which wraps a model to become serializable

    :param object: Model object, e.g. sklearn model, etc..
    :param identifier: Unique identifying ID
    :param type: Encoder instance (optional)
    """

    variety = 'model'

    def __init__(
        self,
        object: Any,
        identifier: str,
        type: Optional[Union[Encoder, str]] = None,
    ):
        super().__init__(identifier)
        self.object = object

        if isinstance(type, str):
            self.type = Placeholder(type, 'type')
        else:
            self.type = type

        try:
            self.predict_one = object.predict_one
        except AttributeError:
            pass

        if not hasattr(self, 'predict'):
            try:
                self.predict = object.predict
            except AttributeError:
                pass
                self.predict = self._predict

    def _predict(self, inputs, **kwargs):
        return [self.predict_one(x, **kwargs) for x in inputs]

    def asdict(self):
        return {
            'identifier': self.identifier,
            'type': self.type.identifier if self.type is not None else None,
        }
