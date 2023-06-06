from typing import Any, Optional, Union

from pinnacledb.core.base import Component, Placeholder
from pinnacledb.core.type import Type


class Model(Component):
    """
    Model component which wraps a model to become serializable

    :param object: Model object, e.g. sklearn model, etc..
    :param identifier: Unique identifying ID
    :param type: Type instance (optional)
    """

    variety = 'model'

    def __init__(
        self, object: Any, identifier: str, type: Optional[Union[Type, str]] = None
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

        try:
            self.predict = object.predict
        except AttributeError:
            pass

    def asdict(self):
        return {
            'identifier': self.identifier,
            'type': self.type.identifier if isinstance(self.type, Type) else self.type,
        }
