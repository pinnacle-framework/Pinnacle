import numpy
import torch
import typing as t

from pinnacledb.core.encoder import Encoder
from pinnacledb.types.utils import str_shape


class EncodeTensor:
    def __init__(self, dtype):
        self.dtype = dtype

    def __call__(self, x):
        assert self.dtype == x.dtype
        return memoryview(x.numpy()).tobytes()


class DecodeTensor:
    def __init__(self, dtype):
        self.dtype = torch.randn(1).type(dtype).numpy().dtype

    def __call__(self, bytes):
        array = numpy.frombuffer(bytes, dtype=self.dtype)
        return torch.from_numpy(array)


def tensor(dtype, shape: t.Tuple):
    return Encoder(
        identifier=f'{str(dtype)}[{str_shape(shape)}]',
        encoder=EncodeTensor(dtype),
        decoder=DecodeTensor(dtype),
        shape=shape,
    )
