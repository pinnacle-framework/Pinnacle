import typing as t

import pinnacledb as s
from pinnacledb.data.cache import uri_cache
from pinnacledb.misc import dataclasses as dc


class Str(uri_cache.Cached[str]):
    def __hash__(self):
        return object.__hash__(self)


class Tuple(uri_cache.Cached[tuple]):
    def __hash__(self):
        return object.__hash__(self)


@dc.dataclass
class Both:
    s: Str
    t: Tuple


class Top(s.JSONable):
    both: Both
    d: t.Dict
    li: t.List

    def __hash__(self):
        return object.__hash__(self)


def test_cache_uri():
    def tr(n):
        return tuple(range(n))

    top = Top(
        both=Both(Str('hello'), Tuple(tr(3))),
        d={'one': Str('wot')},
        li=[Tuple(tr(10)), tr(10)],
    )

    actual1 = top.dict()
    expected1 = {
        'both': Both(s=Str(uri=''), t=Tuple(uri='')),
        'd': {'one': Str(uri='')},
        'li': [Tuple(uri=''), tr(10)],
    }
    assert actual1 == expected1

    cache = uri_cache.URICache()
    cache.cache_all(top)

    actual2 = top.dict()
    expected2 = {
        'both': Both(s=Str(uri='str-0'), t=Tuple(uri='tuple-0')),
        'd': {'one': Str(uri='str-1')},
        'li': [Tuple(uri='tuple-1'), tr(10)],
    }
    assert actual2 == expected2

    top2 = Top(**actual2)
    cache.uncache_all(top2)

    assert top2.both.s.content == 'hello'
    assert top2.both.t.content == tr(3)
    assert top2.d['one'].content == 'wot'
    assert top2.li[0].content == tr(10)
