from __future__ import annotations
from .job import Job, ComponentJob, FunctionJob
from functools import wraps
from networkx import DiGraph, ancestors
import dataclasses as dc
import networkx
import pinnacledb as s
import typing as t

if t.TYPE_CHECKING:
    from pinnacledb.datalayer.base.datalayer import Datalayer


@dc.dataclass
class TaskWorkflow:
    """
    Keep a graph of jobs that need to be performed and their dependencies,
    and perform them when called.
    """

    database: Datalayer
    G: DiGraph = dc.field(default_factory=DiGraph)

    @wraps(DiGraph.add_edge)
    def add_edge(self, node1: str, node2: str) -> None:
        self.G.add_edge(node1, node2)

    @wraps(DiGraph.add_node)
    def add_node(self, node: str, job: t.Union[FunctionJob, ComponentJob]) -> None:
        self.G.add_node(node, job=job)

    def watch(self) -> None:
        """Watch each job in this workflow in topological order"""
        for node in list(networkx.topological_sort(self.G)):
            self.G.nodes[node]['job'].watch()

    def run_jobs(self, distributed: t.Optional[bool] = False):
        """Run all the jobs in this workflow

        :param distributed: if True, use dask to distribute these tasks
        """
        if distributed is None:
            distributed = s.CFG.distributed
        pred = self.G.predecessors
        current_group = [n for n in self.G.nodes if not ancestors(self.G, n)]
        done = set()

        while current_group:
            for node in current_group:
                job: Job = self.G.nodes[node]['job']
                dependencies = [self.G.nodes[a]['job'].future for a in pred(node)]
                job(self.database, dependencies=dependencies, distributed=distributed)
                done.add(node)

            current_group = [
                n for n in self.G.nodes if set(pred(n)) <= done and n not in done
            ]
