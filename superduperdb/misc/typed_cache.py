from .key_cache import KeyCache
from threading import Lock
from pinnacledb.misc import dataclasses as dc
import typing as t

SEP = '-'


@dc.dataclass
class TypedCache:
    """Cache objects by class.

    Each class of object is given a unique name and its own cache.

    The key for an object is that unique class name, joined with the object's key from
    its class cache.
    """

    def put(self, entry: t.Any) -> str:
        """Put an item into the cache, return a string key"""
        name = self._get_name(type(entry))
        cache = self._name_to_cache[name]
        key = cache.put(entry)
        return f'{name}{SEP}{key}'

    def _get_name(self, cls: t.Type) -> str:
        with self._lock:
            try:
                return self._class_to_name[cls]
            except KeyError:
                name = cls.__name__
                if name in self._name_to_cache:
                    name = f'{cls.__module__}.{name}'
                cache = KeyCache[cls]()  # type: ignore

                self._class_to_name[cls] = name
                self._name_to_cache[name] = cache
        return name

    def get(self, key: str) -> t.Any:
        """Given a key, returns an entry or raises KeyError"""
        name, key = key.split(SEP)
        return self._name_to_cache[name].get(key)

    _class_to_name: t.Dict[t.Type, str] = dc.field(default_factory=dict)
    _lock: Lock = dc.field(default_factory=Lock)
    _name_to_cache: t.Dict[str, KeyCache] = dc.field(default_factory=dict)
