from __future__ import annotations

from artifacts.artifact import ArtifactType
from artifacts.store import ArtifactStore
from skills.base import Skill, SkillResult, SkillStatus, TaskContext
from tasks.task import Task
from terminal.runner import TerminalRunner
from workspace.workspace import Workspace

ALLOWED_BINARIES = {"python3", "pytest", "node", "npm", "git", "ls", "cat"}


class TerminalSkill(Skill):
    name = "TerminalSkill"

    def __init__(self, artifact_store: ArtifactStore, timeout_seconds: int = 60) -> None:
        self.artifact_store = artifact_store
        self.timeout_seconds = timeout_seconds

    def execute(self, task: Task, workspace: Workspace, context: TaskContext) -> SkillResult:
        command = task.input_data.get("command")
        if not command or not isinstance(command, list):
            return SkillResult(
                status=SkillStatus.FAILURE,
                summary="TerminalSkill requires input_data['command'] as a list",
                confidence=0.0,
            )

        binary = command[0]
        if binary not in ALLOWED_BINARIES:
            return SkillResult(
                status=SkillStatus.FAILURE,
                summary=f"Command '{binary}' not in allowed binaries: {sorted(ALLOWED_BINARIES)}",
                confidence=0.0,
            )

        runner = TerminalRunner(workspace.root, timeout_seconds=self.timeout_seconds)
        result = runner.run(command)

        log_text = f"$ {' '.join(command)}\nexit={result.exit_code} duration={result.duration:.2f}s\n\nSTDOUT:\n{result.stdout}\n\nSTDERR:\n{result.stderr}"
        artifact = self.artifact_store.add(
            ArtifactType.TERMINAL_OUTPUT,
            task.id,
            log_text,
            meta={"command": command, "exit_code": result.exit_code},
        )

        status = SkillStatus.SUCCESS if result.exit_code == 0 else SkillStatus.FAILURE
        return SkillResult(
            status=status,
            summary=f"Ran `{' '.join(command)}` (exit {result.exit_code}, {result.duration:.2f}s)",
            artifacts=[artifact.id],
            observations={
                "exit_code": result.exit_code,
                "stdout_tail": result.stdout[-1000:],
                "stderr_tail": result.stderr[-1000:],
            },
            confidence=1.0 if result.exit_code == 0 else 0.3,
        )
