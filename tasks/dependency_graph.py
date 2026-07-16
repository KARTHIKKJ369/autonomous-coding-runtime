from __future__ import annotations

from tasks.task import Task, TaskStatus


class DependencyGraph:
    """Tracks task dependencies and determines which tasks are unblocked."""

    def __init__(self) -> None:
        self._tasks: dict[str, Task] = {}

    def add(self, task: Task) -> None:
        self._tasks[task.id] = task
        self._refresh_status(task)

    def get(self, task_id: str) -> Task | None:
        return self._tasks.get(task_id)

    def all(self) -> list[Task]:
        return list(self._tasks.values())

    def _refresh_status(self, task: Task) -> None:
        if task.status in (TaskStatus.DONE, TaskStatus.FAILED, TaskStatus.RUNNING):
            return
        if self._deps_satisfied(task):
            task.status = TaskStatus.READY
        else:
            task.status = TaskStatus.BLOCKED
        task.touch()

    def _deps_satisfied(self, task: Task) -> bool:
        for dep_id in task.dependencies:
            dep = self._tasks.get(dep_id)
            if dep is None or dep.status != TaskStatus.DONE:
                return False
        return True

    def unlock_dependents(self, completed_task_id: str) -> list[Task]:
        """Call after a task completes; returns newly-READY tasks."""
        newly_ready = []
        for task in self._tasks.values():
            if completed_task_id in task.dependencies and task.status == TaskStatus.BLOCKED:
                if self._deps_satisfied(task):
                    task.status = TaskStatus.READY
                    task.touch()
                    newly_ready.append(task)
        return newly_ready

    def ready_tasks(self) -> list[Task]:
        return sorted(
            (t for t in self._tasks.values() if t.status == TaskStatus.READY),
            key=lambda t: -t.priority,
        )
