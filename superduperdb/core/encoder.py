import dataclasses as dc
import io
import pickle
import typing as t

from pinnacledb.core.base import Component

Decode = t.Callable[[bytes], t.Any]
Encode = t.Callable[[t.Any], bytes]


def _pickle_decoder(b: bytes) -> t.Any:
    return pickle.load(io.BytesIO(b))


def _pickle_encoder(x: t.Any) -> bytes:
    f = io.BytesIO()
    pickle.dump(x, f)
    return f.getvalue()


@dc.dataclass
class Encoder(Component):
    """
    Storeable ``Component`` allowing byte encoding of primary data,
    i.e. data inserted using ``datalayer.base.BaseDatabase.insert``

    :param identifier: unique identifier
    :param encoder: callable converting an ``Encodable`` of this ``Encoder`` to
                    be converted to ``bytes``
    :param decoder: callable converting a ``bytes`` string to a ``Encodable`` of
                    this ``Encoder``
    :param shape: shape of the data, if any
    """

    identifier: str
    decoder: Decode = _pickle_decoder
    encoder: Encode = _pickle_encoder
    shape: t.Optional[t.Tuple] = None

    variety = 'type'  # This cannot yet be changed

    def __post_init__(self):
        super().__init__(self.identifier)

    def __call__(self, x):
        return Encodable(x, self)

    def decode(self, b: bytes) -> t.Any:
        return self(self.decoder(b))

    def encode(self, x: t.Any) -> t.Dict[str, t.Any]:
        if self.encoder is not None:
            return {'_content': {'bytes': self.encoder(x), 'type': self.identifier}}
        else:
            return x


@dc.dataclass
class Encodable:
    """
    Data variable wrapping encode-able item. Encoding is controlled by the referred
    to ``Encoder`` instance.

    :param x: Wrapped content
    :param encoder: Instance of ``Encoder`` controlling encoding
    """

    x: t.Any
    encoder: Encoder

    def encode(self) -> t.Dict[str, t.Any]:
        return self.encoder.encode(self.x)
