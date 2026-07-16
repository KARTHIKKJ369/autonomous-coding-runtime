from __future__ import annotations

from tasks.dependency_graph import DependencyGraph
from tasks.task import Task, TaskStatus


class TaskQueue:
    """Task queue backed by a dependency graph. Not thread-safe; single-runtime use."""

    def __init__(self) -> None:
        self._graph = DependencyGraph()
        self._running: dict[str, Task] = {}
        self._completed: list[str] = []
        self._failed: list[str] = []

    def enqueue(self, task: Task) -> Task:
        self._graph.add(task)
        return task

    def dequeue(self) -> Task | None:
        """Pop the highest-priority READY task and mark it RUNNING."""
        ready = self._graph.ready_tasks()
        if not ready:
            return None
        task = ready[0]
        task.status = TaskStatus.RUNNING
        task.touch()
        self._running[task.id] = task
        return task

    def complete(self, task_id: str) -> list[Task]:
        task = self._graph.get(task_id)
        if task is None:
            return []
        task.status = TaskStatus.DONE
        task.touch()
        self._running.pop(task_id, None)
        self._completed.append(task_id)
        return self._graph.unlock_dependents(task_id)

    def fail(self, task_id: str, error: str) -> Task | None:
        task = self._graph.get(task_id)
        if task is None:
            return None
        task.error_message = error
        self._running.pop(task_id, None)
        if task.retry_count < task.max_retries:
            task.retry_count += 1
            task.status = TaskStatus.READY
            task.touch()
        else:
            task.status = TaskStatus.FAILED
            task.touch()
            self._failed.append(task_id)
        return task

    def cancel(self, task_id: str) -> None:
        task = self._graph.get(task_id)
        if task is None:
            return
        task.status = TaskStatus.FAILED
        task.error_message = task.error_message or "cancelled"
        task.touch()
        self._running.pop(task_id, None)

    def prioritize(self, task_id: str, priority: int) -> None:
        task = self._graph.get(task_id)
        if task:
            task.priority = priority
            task.touch()

    def has_pending_work(self) -> bool:
        return any(
            t.status in (TaskStatus.NEW, TaskStatus.READY, TaskStatus.RUNNING, TaskStatus.BLOCKED)
            for t in self._graph.all()
        )

    def all_tasks(self) -> list[Task]:
        return self._graph.all()

    @property
    def failed_ids(self) -> list[str]:
        return list(self._failed)

    @property
    def completed_ids(self) -> list[str]:
        return list(self._completed)
