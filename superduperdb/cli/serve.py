import json
import typing as t

from . import command


@command(help='Start local cluster: server, ray and change data capture')
def local_cluster(action: str, notebook_token: t.Optional[str] = None):
    """Start local cluster: server, ray and change data capture.

    :param action: Action to perform (up, down, attach).
    :param notebook_token: Notebook token.
    """
    from pinnacledb.server.cluster import attach_cluster, down_cluster, up_cluster

    action = action.lower()

    if action == 'up':
        up_cluster(notebook_token=notebook_token)
    elif action == 'down':
        down_cluster()
    elif action == 'attach':
        attach_cluster()


@command(help='Start vector search server')
def vector_search():
    """Start vector search server."""
    from pinnacledb.vector_search.server.app import app

    app.start()


@command(help='Start standalone change data capture')
def cdc():
    """Start standalone change data capture."""
    from pinnacledb.cdc.app import app

    app.start()


@command(help='Serve a model on ray')
def ray_serve(
    model: str,
    version: t.Optional[int] = None,
    ray_actor_options: str = '',
    num_replicas: int = 1,
):
    """Serve a model on ray.

    :param model: Model name.
    :param version: Model version.
    :param ray_actor_options: Ray actor options.
    :param num_replicas: Number of replicas.
    """
    from pinnacledb.backends.ray.serve import run

    run(
        model=model,
        version=version,
        ray_actor_options=json.loads(ray_actor_options),
        num_replicas=num_replicas,
    )


@command(help='Start FastAPI REST server')
def rest():
    """Start FastAPI REST server."""
    from pinnacledb.rest.app import app

    app.start()
