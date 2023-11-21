import base64
import json
from functools import lru_cache

import requests

from pinnacledb import CFG, logging
from pinnacledb.ext.utils import pinnacleencode


@lru_cache(maxsize=None)
def _handshake(service: str):
    endpoint = 'handshake/config'
    cfg = json.dumps(CFG.comparables)
    try:
        _request_server(service, args={'cfg': cfg}, endpoint=endpoint)
    except Exception:
        raise Exception(
            'Service {service} not compatible with current client,\
             its configured with different configuration.'
        )


def _request_server(
    service: str = 'vector_search', data=None, endpoint='add', args={}, type='post'
):
    url = getattr(CFG.server, service) + '/' + service + '/' + endpoint
    logging.debug(f'Trying to connect {service} at {url} method: {type}')
    if type == 'post':
        data = pinnacleencode(data)
        if isinstance(data, dict):
            if '_content' in data:
                data['_content']['bytes'] = base64.b64encode(
                    data['_content']['bytes']
                ).decode()
        response = requests.post(url, json=data, params=args)
        result = json.loads(response.content)
    else:
        response = requests.get(url, params=args)
        result = None
    if response.status_code != 200:
        error = json.loads(response.content)
        msg = f'Server error at {service} with {response.status_code} :: {error}'
        logging.error(msg)
        raise Exception(msg)
    return result


def request_server(
    service: str = 'vector_search', data=None, endpoint='add', args={}, type='post'
):
    _handshake(service)
    return _request_server(
        service=service, data=data, endpoint=endpoint, args=args, type=type
    )
