from __future__ import annotations

import subprocess
import time
from dataclasses import dataclass
from pathlib import Path


@dataclass
class TerminalResult:
    stdout: str
    stderr: str
    exit_code: int
    duration: float


class TerminalRunner:
    """Runs commands with cwd pinned to the workspace root. No shell=True by default."""

    def __init__(self, workspace_root: Path, timeout_seconds: int = 60) -> None:
        self.workspace_root = Path(workspace_root)
        self.timeout_seconds = timeout_seconds

    def run(self, command: list[str]) -> TerminalResult:
        start = time.monotonic()
        try:
            proc = subprocess.run(
                command,
                cwd=self.workspace_root,
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
            )
            duration = time.monotonic() - start
            return TerminalResult(proc.stdout, proc.stderr, proc.returncode, duration)
        except subprocess.TimeoutExpired as e:
            duration = time.monotonic() - start
            return TerminalResult(
                stdout=e.stdout or "" if isinstance(e.stdout, str) else "",
                stderr=f"Command timed out after {self.timeout_seconds}s",
                exit_code=-1,
                duration=duration,
            )
        except FileNotFoundError as e:
            return TerminalResult(stdout="", stderr=str(e), exit_code=127, duration=0.0)
