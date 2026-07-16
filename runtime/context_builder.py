from __future__ import annotations

from memory.memory import MemoryStore
from skills.base import TaskContext
from tasks.task import Task
from workspace.workspace import Workspace

MAX_FILES = 5
MAX_FILE_CHARS = 6000


class ContextBuilder:
    """Task -> relevant files -> relevant memory -> relevant artifacts -> TaskContext.

    Workers only receive what their task needs. Never the full chat history.
    """

    def __init__(self, memory: MemoryStore) -> None:
        self.memory = memory

    def build(self, task: Task, workspace: Workspace) -> TaskContext:
        relevant_files: dict[str, str] = {}

        explicit_paths = task.input_data.get("relevant_paths", [])
        candidate_paths = list(explicit_paths)

        target = task.input_data.get("target_path")
        if target and target not in candidate_paths:
            candidate_paths.append(target)

        if not candidate_paths:
            # fall back to files already touched this session, most-recent-ish
            candidate_paths = list(workspace.opened_files | workspace.generated_files)

        for path in candidate_paths[:MAX_FILES]:
            if workspace.file_exists(path):
                content = workspace.reader.read(path)
                relevant_files[path] = content[:MAX_FILE_CHARS]

        memory_hits = self.memory.retrieve(f"{task.title} {task.description}", k=5)
        relevant_memory = [f"{m.key}: {m.value}" for m in memory_hits]

        return TaskContext(
            task_summary=f"{task.title} — {task.description}",
            relevant_files=relevant_files,
            relevant_memory=relevant_memory,
            relevant_artifacts=list(task.artifacts),
        )
