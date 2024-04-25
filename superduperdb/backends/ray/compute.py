import typing as t

import ray

from pinnacledb import logging
from pinnacledb.backends.base.compute import ComputeBackend


class RayComputeBackend(ComputeBackend):
    """
    A client for interacting with a ray cluster. Initialize the ray client.

    :param address: The address of the ray cluster.
    :param local: Set to True to create a local Dask cluster. (optional)
    :param **kwargs: Additional keyword arguments to be passed to the ray client.
    """

    def __init__(
        self,
        address: t.Optional[str] = None,
        local: bool = False,
        **kwargs,
    ):
        self._futures_collection: t.Dict[str, ray.ObjectRef] = {}
        self.address = address
        if local:
            ray.init(ignore_reinit_error=True)
        else:
            ray.init(address=address, **kwargs, ignore_reinit_error=True)

    @property
    def type(self) -> str:
        return "distributed"

    @property
    def name(self) -> str:
        return f"ray://{self.address}"

    def submit(
        self, function: t.Callable, *args, compute_kwargs: t.Dict = {}, **kwargs
    ) -> ray.ObjectRef:
        """
        Submits a function to the ray server for execution.

        :param function: The function to be executed.
        """

        def _dependable_remote_job(function, *args, **kwargs):
            if (
                function.__name__ in ['method_job', 'callable_job']
                and 'dependencies' in kwargs
            ):
                dependencies = kwargs['dependencies']
                if dependencies:
                    ray.wait(dependencies)
            return function(*args, **kwargs)

        remote_function = ray.remote(_dependable_remote_job, **compute_kwargs)
        future = remote_function.remote(function, *args, **kwargs)
        task_id = str(future.task_id().hex())
        self._futures_collection[task_id] = future

        logging.success(
            f"Job submitted on {self}.  function: {function}; "
            f"task: {task_id}; job_id: {str(future.job_id())}"
        )
        return future, task_id

    @property
    def tasks(self) -> t.Dict[str, ray.ObjectRef]:
        """
        List all pending tasks
        """
        return self._futures_collection

    def wait(self, identifier: str) -> None:
        """
        Waits for task corresponding to identifier to complete.
        :param identifier: Future task id to wait
        """
        ray.wait([self._futures_collection[identifier]])

    def wait_all(self) -> None:
        """
        Waits for all tasks to complete.
        """
        ray.wait(
            list(self._futures_collection.values()),
            num_returns=len(self._futures_collection),
        )

    def result(self, identifier: str) -> t.Any:
        """
        Retrieves the result of a previously submitted task.
        Note: This will block until the future is completed.

        :param identifier: The identifier of the submitted task.
        """
        future = self._futures_collection[identifier]
        return ray.get(future)

    def disconnect(self) -> None:
        """
        Disconnect the ray client.
        """
        ray.shutdown()

    def shutdown(self) -> None:
        """
        Shuts down the ray cluster.
        """
        ray.shutdown()
