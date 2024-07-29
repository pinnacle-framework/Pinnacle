import os

import pytest

skip = not os.environ.get('pinnacle_CONFIG', "").endswith('ibis.yaml')

if skip:
    pytest.skip("Skipping this file for now", allow_module_level=True)
