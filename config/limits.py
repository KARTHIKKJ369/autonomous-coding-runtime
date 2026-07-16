from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Limits:
    max_iterations: int = int(os.environ.get("RUNTIME_MAX_ITERATIONS", "25"))
    terminal_timeout_seconds: int = int(os.environ.get("RUNTIME_TERMINAL_TIMEOUT", "60"))
    max_context_files: int = int(os.environ.get("RUNTIME_MAX_CONTEXT_FILES", "5"))
    max_retries: int = int(os.environ.get("RUNTIME_MAX_RETRIES", "2"))
    default_model: str = os.environ.get("RUNTIME_MODEL", "claude-sonnet-4-6")


limits = Limits()
