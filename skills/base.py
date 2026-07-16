from __future__ import annotations

from abc import ABC, abstractmethod
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from tasks.task import Task
from workspace.workspace import Workspace


class SkillStatus(str, Enum):
    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"
    PARTIAL = "PARTIAL"


class SkillResult(BaseModel):
    status: SkillStatus
    summary: str
    artifacts: list[str] = Field(default_factory=list)  # artifact ids
    logs: list[str] = Field(default_factory=list)
    observations: dict[str, Any] = Field(default_factory=dict)
    confidence: float = 1.0


class TaskContext(BaseModel):
    """Minimal, task-scoped context. Never the full chat history."""

    task_summary: str
    relevant_files: dict[str, str] = Field(default_factory=dict)  # path -> content
    relevant_memory: list[str] = Field(default_factory=list)
    relevant_artifacts: list[str] = Field(default_factory=list)


class Skill(ABC):
    """Workers are stateless. No memory between calls, no knowledge of other skills."""

    name: str

    @abstractmethod
    def execute(self, task: Task, workspace: Workspace, context: TaskContext) -> SkillResult:
        ...
