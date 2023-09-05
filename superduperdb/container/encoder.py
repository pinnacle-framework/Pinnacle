import dataclasses
import dataclasses as dc
import io
import pickle
import typing as t

from pinnacledb.container.artifact import Artifact
from pinnacledb.container.component import Component

Decode = t.Callable[[bytes], t.Any]
Encode = t.Callable[[t.Any], bytes]


def _pickle_decoder(b: bytes) -> t.Any:
    return pickle.load(io.BytesIO(b))


def _pickle_encoder(x: t.Any) -> bytes:
    f = io.BytesIO()
    pickle.dump(x, f)
    return f.getvalue()


@dataclasses.dataclass
class Encoder(Component):
    """
    Storeable ``Component`` allowing byte encoding of primary data,
    i.e. data inserted using ``db.base.db.Datalayer.insert``

    :param identifier: unique identifier
    :param encoder: callable converting an ``Encodable`` of this ``Encoder`` to
                    be converted to ``bytes``
    :param decoder: callable converting a ``bytes`` string to a ``Encodable`` of
                    this ``Encoder``
    :param shape: shape of the data, if any
    """

    artifacts: t.ClassVar[t.Sequence[str]] = ['decoder', 'encoder']

    identifier: str
    decoder: t.Union[t.Callable, Artifact] = dc.field(
        default_factory=lambda: Artifact(artifact=_pickle_decoder)
    )
    encoder: t.Union[t.Callable, Artifact] = dc.field(
        default_factory=lambda: Artifact(artifact=_pickle_encoder)
    )

    shape: t.Optional[t.Sequence] = None
    version: t.Optional[int] = None

    #: A unique name for the class
    type_id: t.ClassVar[str] = 'encoder'

    encoders: t.ClassVar[t.List] = []

    def __post_init__(self):
        self.encoders.append(self.identifier)
        if isinstance(self.decoder, t.Callable):
            self.decoder = Artifact(artifact=self.decoder)
        if isinstance(self.encoder, t.Callable):
            self.encoder = Artifact(artifact=self.encoder)

    def __call__(
        self, x: t.Optional[t.Any] = None, uri: t.Optional[str] = None
    ) -> 'Encodable':
        return Encodable(self, x=x, uri=uri)

    def decode(self, b: bytes) -> t.Any:
        assert isinstance(self.decoder, Artifact)
        return self(self.decoder.artifact(b))

    def dump(self, other):
        return self.encoder.artifact(other)

    def encode(
        self,
        x: t.Optional[t.Any] = None,
        uri: t.Optional[str] = None,
        wrap: bool = True,
    ) -> t.Union[t.Optional[str], t.Dict[str, t.Any]]:
        def _wrap_content(x):
            return {
                '_content': {
                    'bytes': self.encoder.artifact(x),
                    'encoder': self.identifier,
                }
            }

        if self.encoder is not None:
            if x is not None:
                if wrap:
                    return _wrap_content(x)
                return self.encoder.artifact(x)  # type: ignore[union-attr]
            else:
                if wrap:
                    return {
                        '_content': {
                            'uri': uri,
                            'encoder': self.identifier,
                        }
                    }
                return uri
        else:
            assert x is not None
            return x


@dc.dataclass
class Encodable:
    """
    Data variable wrapping encode-able item. Encoding is controlled by the referred
    to ``Encoder`` instance.

    :param encoder: Instance of ``Encoder`` controlling encoding
    :param x: Wrapped content
    :param uri: URI of the content, if any
    """

    encoder: t.Callable
    x: t.Optional[t.Any] = None
    uri: t.Optional[str] = None

    def encode(self) -> t.Dict[str, t.Any]:
        assert hasattr(self.encoder, 'encode')
        return self.encoder.encode(x=self.x, uri=self.uri)


default_encoder = Encoder(identifier='_default')
