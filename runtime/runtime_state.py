from __future__ import annotations

from enum import Enum
from uuid import uuid4

from artifacts.store import ArtifactStore
from events.bus import EventBus
from memory.memory import MemoryStore
from tasks.queue import TaskQueue
from workspace.workspace import Workspace


class RunStatus(str, Enum):
    RUNNING = "RUNNING"
    DONE = "DONE"
    FAILED = "FAILED"
    WAITING_FOR_USER = "WAITING_FOR_USER"


class RuntimeState:
    """No duplicate state elsewhere. Everything belongs here."""

    def __init__(self, workspace_root: str) -> None:
        self.session_id: str = uuid4().hex[:12]
        self.workspace = Workspace(workspace_root)
        self.task_queue = TaskQueue()
        self.artifacts = ArtifactStore()
        self.memory = MemoryStore()
        self.events = EventBus()
        self.current_plan: list[str] = []  # task ids in planned order
        self.status: RunStatus = RunStatus.RUNNING
        self.logs: list[str] = []
        self.execution_metrics: dict[str, float | int] = {
            "tasks_run": 0,
            "tasks_failed": 0,
        }

    def log(self, message: str) -> None:
        self.logs.append(message)
