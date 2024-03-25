import json
import typing as t

from . import command


@command(help='Start local cluster: server, ray and change data capture')
def local_cluster():
    from pinnacledb.base.build import build_datalayer
    from pinnacledb.server.cluster import cluster

    db = build_datalayer()
    cluster(db)


@command(help='Start vector search server')
def vector_search():
    from pinnacledb.vector_search.server.app import app

    app.start()


@command(help='Start standalone change data capture')
def cdc():
    from pinnacledb.cdc.app import app

    app.start()


@command(help='Serve a model on ray')
def ray_serve(
    model: str,
    version: t.Optional[int] = None,
    ray_actor_options: str = '',
    num_replicas: int = 1,
):
    from pinnacledb.backends.ray.serve import run

    run(
        model=model,
        version=version,
        ray_actor_options=json.loads(ray_actor_options),
        num_replicas=num_replicas,
    )
