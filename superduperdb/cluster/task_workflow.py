import networkx
import copy
import datetime
import dataclasses as dc
import functools
import typing as t
import uuid

from pinnacledb.cluster.function_job import function_job
from pinnacledb.cluster.job_submission import dask_client


@dc.dataclass
class TaskWorkflow:
    database: t.Any
    G: networkx.DiGraph = dc.field(default_factory=networkx.DiGraph)

    def add_edge(self, node1, node2) -> None:
        self.G.add_edge(node1, node2)

    def add_node(self, node, data=None) -> None:
        data = data or {}
        self.G.add_node(node)
        self.G.nodes[node].update(data)

    def asjson(self) -> t.Dict[str, t.Any]:
        return networkx.adjacency_data(self.G)

    def __imul__(self, other: 'TaskWorkflow') -> 'TaskWorkflow':
        for node in other.nodes:
            self.G.add_node(node)
        for edge in other.edges:
            self.G.add_edge(*edge)
        return self

    def __iadd__(self, other: 'TaskWorkflow') -> 'TaskWorkflow':
        for node in other.nodes:
            self.G.add_node(node)
        for edge in other.edges:
            self.G.add_edge(*edge)
        roots_other = [i for i in other if not networkx.ancestors(i)]
        leafs_this = [i for i in self.G if not networkx.descendants(i)]

        for node1 in leafs_this:
            for node2 in roots_other:
                self.add_edge(node1, node2)
        return self

    def __mul__(self, other: 'TaskWorkflow') -> 'TaskWorkflow':
        dc = copy.deepcopy(self)
        dc *= other
        return dc

    def __add__(self, other: 'TaskWorkflow') -> 'TaskWorkflow':
        dc = copy.deepcopy(self)
        dc += other
        return dc

    @functools.cached_property
    def path_lengths(self) -> t.Dict[t.Any, int]:
        p = {}

        for node in networkx.topological_sort(self.G):
            p[node] = len(p) and 1 + min([p[n] for n in self.G.predecessors(node)])

        return p

    def __call__(self, remote=None) -> networkx.DiGraph:
        if remote is None:
            remote = self.database.remote
        if remote:
            _dask_client = dask_client()
        current_group = [n for n in self.G.nodes if not networkx.ancestors(self.G, n)]
        done = []
        while current_group:
            job_id = str(uuid.uuid4())
            for node in current_group:
                node_object = self.G.nodes[node]
                if remote:
                    self.database._create_job_record(
                        {
                            'identifier': job_id,
                            'time': datetime.datetime.now(),
                            'status': 'pending',
                            'method': node_object['task'].__name__,
                            'args': node_object['args'],
                            'kwargs': node_object['kwargs'],
                            'stdout': [],
                            'stderr': [],
                        }
                    )
                    self.G.nodes[node]['job_id'] = job_id

                    dependencies = [
                        self.G.nodes[a]['future'] for a in self.G.predecessors(node)
                    ]
                    node_object['future'] = _dask_client.submit(
                        function_job,
                        self.database._database_type,
                        self.database.name,
                        node_object['task'].__name__,
                        node_object['args'],
                        {
                            **node_object['kwargs'],
                            'remote': False,
                            'dependencies': dependencies,
                        },
                        job_id,
                        key=job_id,
                    )
                    node_object['job_id'] = job_id
                else:
                    args = node_object['args']
                    kwargs = node_object['kwargs']
                    node_object['task'](*args, **{**kwargs, 'remote': False})
                done.append(node)
            current_group = [
                n
                for n in self.G.nodes
                if set(self.G.predecessors(n)).issubset(set(done))
                and n not in set(done)
            ]
        return self.G
