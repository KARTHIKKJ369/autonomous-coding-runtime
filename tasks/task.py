from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional
from uuid import uuid4

from pydantic import BaseModel, Field


class TaskStatus(str, Enum):
    NEW = "NEW"
    READY = "READY"
    RUNNING = "RUNNING"
    WAITING = "WAITING"
    BLOCKED = "BLOCKED"
    FAILED = "FAILED"
    DONE = "DONE"


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Task(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex[:12])
    title: str
    description: str
    executor: str  # skill name, e.g. "CodeSkill"
    priority: int = 0
    status: TaskStatus = TaskStatus.NEW
    dependencies: list[str] = Field(default_factory=list)
    artifacts: list[str] = Field(default_factory=list)  # artifact ids produced
    retry_count: int = 0
    max_retries: int = 2
    input_data: dict[str, Any] = Field(default_factory=dict)
    error_message: Optional[str] = None
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)

    def touch(self) -> None:
        self.updated_at = _now()
