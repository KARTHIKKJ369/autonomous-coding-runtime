from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class EventType(str, Enum):
    TASK_CREATED = "TaskCreated"
    TASK_STARTED = "TaskStarted"
    TASK_COMPLETED = "TaskCompleted"
    TASK_FAILED = "TaskFailed"
    ARTIFACT_CREATED = "ArtifactCreated"
    WORKSPACE_UPDATED = "WorkspaceUpdated"
    PLAN_UPDATED = "PlanUpdated"
    MEMORY_UPDATED = "MemoryUpdated"
    EXECUTION_FINISHED = "ExecutionFinished"
    USER_INTERRUPTED = "UserInterrupted"


class Event(BaseModel):
    type: EventType
    payload: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
