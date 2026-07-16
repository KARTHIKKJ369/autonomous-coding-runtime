from __future__ import annotations

from artifacts.artifact import ArtifactType
from artifacts.store import ArtifactStore
from skills.base import Skill, SkillResult, SkillStatus, TaskContext
from tasks.task import Task
from workspace.workspace import Workspace


class FilesystemSkill(Skill):
    """Handles read/list/search-style tasks that don't require generation."""

    name = "FilesystemSkill"

    def __init__(self, artifact_store: ArtifactStore) -> None:
        self.artifact_store = artifact_store

    def execute(self, task: Task, workspace: Workspace, context: TaskContext) -> SkillResult:
        operation = task.input_data.get("operation", "list")

        try:
            if operation == "list":
                path = task.input_data.get("path", ".")
                files = workspace.list_files(path)
                content = "\n".join(files)
                artifact = self.artifact_store.add(
                    ArtifactType.SEARCH_RESULT, task.id, content, meta={"path": path}
                )
                return SkillResult(
                    status=SkillStatus.SUCCESS,
                    summary=f"Listed {len(files)} files under {path}",
                    artifacts=[artifact.id],
                    observations={"files": files},
                )

            if operation == "read":
                path = task.input_data["path"]
                content = workspace.read_file(path)
                artifact = self.artifact_store.add(
                    ArtifactType.FILE, task.id, content, meta={"path": path}
                )
                return SkillResult(
                    status=SkillStatus.SUCCESS,
                    summary=f"Read {path} ({len(content)} chars)",
                    artifacts=[artifact.id],
                    observations={"path": path},
                )

            if operation == "search":
                query = task.input_data.get("query", "")
                matches = []
                for path in workspace.list_files():
                    try:
                        content = workspace.reader.read(path)
                    except Exception:
                        continue
                    if query in content:
                        matches.append(path)
                artifact = self.artifact_store.add(
                    ArtifactType.SEARCH_RESULT,
                    task.id,
                    "\n".join(matches),
                    meta={"query": query},
                )
                return SkillResult(
                    status=SkillStatus.SUCCESS,
                    summary=f"Found '{query}' in {len(matches)} file(s)",
                    artifacts=[artifact.id],
                    observations={"matches": matches},
                )

            return SkillResult(
                status=SkillStatus.FAILURE,
                summary=f"Unknown filesystem operation: {operation}",
                confidence=0.0,
            )
        except Exception as e:
            return SkillResult(
                status=SkillStatus.FAILURE,
                summary=f"FilesystemSkill error: {e}",
                logs=[str(e)],
                confidence=0.0,
            )
