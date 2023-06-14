import dataclasses as dc
import typing as t
from pinnacledb.core.type import DataVar


@dc.dataclass
class Document:
    """
    A wrapper around an instance of dict or a DataVar which may be used to dump
    that resource to a mix of jsonable content or `bytes`
    """

    content: t.Union[t.Dict, DataVar]

    def _encode(self, r: t.Any):
        if isinstance(r, dict):
            return {k: self._encode(v) for k, v in r.items()}
        elif isinstance(r, DataVar):
            return r.encode()
        return r

    def encode(self):
        return self._encode(self.content)

    @classmethod
    def decode(cls, r: t.Dict, types: t.Dict):
        if isinstance(r, Document):
            return Document(cls._decode(r, types))
        elif isinstance(r, dict):
            return cls._decode(r, types)
        raise NotImplementedError(f'type {type(r)} is not supported')

    @classmethod
    def _decode(cls, r: t.Dict, types: t.Dict):
        if isinstance(r, dict) and '_content' in r:
            type = types[r['_content']['type']]
            return type.decode(r['_content']['bytes'])
        elif isinstance(r, list):
            return [cls._decode(x, types) for x in r]
        elif isinstance(r, dict):
            for k in r:
                r[k] = cls._decode(r[k], types)
        return r

    def __getitem__(self, item: str):
        return self.content[item]

    def __setitem__(self, key: str, value: t.Any):
        self.content[key] = value

    @classmethod
    def _unpack_datavars(cls, item: t.Any):
        if isinstance(item, DataVar):
            return item.x
        elif isinstance(item, dict):
            return {k: cls._unpack_datavars(v) for k, v in item.items()}
        else:
            return item

    def unpack(self):
        return self._unpack_datavars(self.content)
