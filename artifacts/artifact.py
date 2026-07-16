from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


class ArtifactType(str, Enum):
    FILE = "FILE"
    PATCH = "PATCH"
    DIFF = "DIFF"
    SUMMARY = "SUMMARY"
    TERMINAL_OUTPUT = "TERMINAL_OUTPUT"
    LOG = "LOG"
    SEARCH_RESULT = "SEARCH_RESULT"
    TEST_REPORT = "TEST_REPORT"


class Artifact(BaseModel):
    model_config = ConfigDict(frozen=True)  # artifacts are immutable

    id: str = Field(default_factory=lambda: uuid4().hex[:12])
    type: ArtifactType
    task_id: str
    content: str
    meta: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
