from .test_dicts import PARENT
from collections import Counter
from pydantic import ValidationError
from pinnacledb.misc.config import Factory, Serializable, Config, Notebook
import pytest

TYPE_ERROR = """
1 validation error for Config
dask -> port
  value is not a valid integer (type=type_error.integer)
"""
NAME_ERROR = """
1 validation error for Config
bad_name
  extra fields not permitted (type=value_error.extra)
"""
VALIDATION_ERROR = """
1 validation error for Notebook
__root__
  At most one of password and token may be set (type=assertion_error)
"""


def test_type_error():
    d2 = Config().dict()
    d2['dask']['port'] = 'bad port'

    with pytest.raises(ValidationError) as pr:
        Config(**d2)
    assert str(pr.value).strip() == TYPE_ERROR.strip()


def test_unknown_name():
    with pytest.raises(ValidationError) as pr:
        Config(bad_name={})
    assert str(pr.value).strip() == NAME_ERROR.strip()


def test_validation():
    with pytest.raises(ValidationError) as pr:
        Notebook(password='password', token='token')
    assert str(pr.value).strip() == VALIDATION_ERROR.strip()


def _dict_names(d, *address):
    if isinstance(d, dict):
        for k, v in d.items():
            yield from _dict_names(v, *address, k)
    else:
        yield '_'.join(address)


def test_dict_names():
    actual = list(_dict_names(PARENT))
    expected = [
        ('red_crimson'),
        ('red_ruby'),
        ('blue_green_puce'),
        ('blue_green_orange'),
        ('blue_green_puce'),
        ('blue_green_puce'),
        ('blue_green_yellow'),
        ('tan_green_orange'),
    ]

    assert actual == expected


def _dupes(cls):
    counts = Counter(_dict_names(cls().dict()))
    return [k for k, v in counts.items() if v > 1]


def test_config_has_no_dupes():
    assert _dupes(Config) == []


def test_find_dupes():
    class Red(Serializable):
        crimson = 'Crimson'
        ruby = 'Ruby'

    class Green(Serializable):
        puce = 'Puce'
        orange = 'Orange'

    class Blue(Serializable):
        green_puce = 'Green Puce'
        green: Green = Factory(Green)

    class BlueGreen(Serializable):
        puce = 0
        yellow = 30

    class Green2(Serializable):
        orange = 'lime'

    class Tan(Serializable):
        green: Green2 = Factory(Green2)

    class Colors(Serializable):
        red: Red = Factory(Red)
        blue: Blue = Factory(Blue)
        blue_green: BlueGreen = Factory(BlueGreen)
        tan: Tan = Factory(Tan)

    assert Colors().dict() == PARENT
    assert _dupes(Colors) == ['blue_green_puce']
