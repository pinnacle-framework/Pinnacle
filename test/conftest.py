import os
from pathlib import Path
from typing import Iterator

import pytest

pinnacle_CONFIG = os.environ.get("pinnacle_CONFIG", "test/configs/default.yaml")

os.environ["pinnacle_CONFIG"] = pinnacle_CONFIG


from pinnacle import pinnacle
from pinnacle.base.datalayer import Datalayer


@pytest.fixture
def db() -> Iterator[Datalayer]:
    db = pinnacle(force_apply=True)

    yield db
    db.drop(force=True, data=True)


@pytest.fixture(scope='session')
def image_url():
    path = Path(__file__).parent / 'material' / 'data' / '1x1.png'
    return f'file://{path}'
