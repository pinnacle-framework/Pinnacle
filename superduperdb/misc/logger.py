import logging
from pinnacledb import cf

cf_logging = cf.get('logging', {})

logging.basicConfig(level=getattr(logging, cf_logging.get('level', 'DEBUG')),
                    **{k: v for k, v in cf_logging.items() if k != 'level'})
