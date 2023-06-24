from pinnacledb.misc.key_cache import KeyCache


def test_simple_cache():
    cache = KeyCache[str]()

    k1 = cache.put('one')
    assert k1 == '0'
    assert cache.put('one') == k1
    assert cache.get(k1) == 'one'

    k2 = cache.put('two')
    assert k2 == '1'
    assert k1 != k2

    assert cache.put('two') == k2
    assert cache.get(k2) == 'two'

    assert cache.get(k1) == 'one'


def test_keys():
    cache = KeyCache[str]()
    keys = [cache.put(i) for i in range(256)]

    assert len(keys) == len(set(keys))
    assert all(k.lower() == k for k in keys)
    assert all(len(k) <= 9 for k in keys)
    assert [int(k) for k in keys] == list(range(256))
