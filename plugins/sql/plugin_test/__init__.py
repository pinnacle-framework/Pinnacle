import os

basedir = os.path.abspath(os.path.dirname(__file__))

pinnacle_CONFIG = os.environ.get(
    "pinnacle_CONFIG", os.path.join(basedir, "config.yaml")
)

os.environ["pinnacle_CONFIG"] = pinnacle_CONFIG
