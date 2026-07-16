from __future__ import annotations

from artifacts.artifact import ArtifactType
from artifacts.store import ArtifactStore
from filesystem.diff import unified_diff
from runtime.llm_client import LLMClient, get_llm_client
from skills.base import Skill, SkillResult, SkillStatus, TaskContext
from tasks.task import Task
from workspace.workspace import Workspace

SYSTEM_PROMPT = """You are a stateless code-writing worker. You receive one task and
relevant file context. Output ONLY the full new content of the target file, no
explanations, no markdown fences. If no target file is given, decide the most sensible
relative path and put it on the first line as `# FILE: <path>` followed by the content."""


class CodeSkill(Skill):
    name = "CodeSkill"

    def __init__(
        self,
        artifact_store: ArtifactStore,
        model: str | None = None,
        provider: str | None = None,
        client: LLMClient | None = None,
    ) -> None:
        self.artifact_store = artifact_store
        self._model = model
        self._provider = provider
        self._client = client  # lazily built on first use if not injected

    def _get_client(self) -> LLMClient:
        if self._client is None:
            self._client = get_llm_client(model=self._model, provider=self._provider)
        return self._client

    def execute(self, task: Task, workspace: Workspace, context: TaskContext) -> SkillResult:
        target_path = task.input_data.get("target_path")

        file_context = "\n\n".join(
            f"--- {path} ---\n{content}" for path, content in context.relevant_files.items()
        )
        memory_context = "\n".join(context.relevant_memory)

        user_prompt = (
            f"Task: {task.title}\n{task.description}\n\n"
            f"Target file: {target_path or '(choose one)'}\n\n"
            f"Relevant files:\n{file_context or '(none)'}\n\n"
            f"Relevant memory:\n{memory_context or '(none)'}"
        )

        try:
            client = self._get_client()
            new_content = client.complete(SYSTEM_PROMPT, user_prompt, max_tokens=4096)
        except Exception as e:
            return SkillResult(
                status=SkillStatus.FAILURE,
                summary=f"CodeSkill failed to generate content: {e}",
                logs=[str(e)],
                confidence=0.0,
            )

        path = target_path
        if not path and new_content.startswith("# FILE:"):
            first_line, _, rest = new_content.partition("\n")
            path = first_line.replace("# FILE:", "").strip()
            new_content = rest

        if not path:
            return SkillResult(
                status=SkillStatus.FAILURE,
                summary="CodeSkill could not determine a target file path",
                confidence=0.2,
            )

        old_content = workspace.read_file(path) if workspace.file_exists(path) else ""
        workspace.write_file(path, new_content)
        diff_text = unified_diff(old_content, new_content, path)

        file_artifact = self.artifact_store.add(
            ArtifactType.FILE, task.id, new_content, meta={"path": path}
        )
        diff_artifact = self.artifact_store.add(
            ArtifactType.DIFF, task.id, diff_text, meta={"path": path}
        )

        return SkillResult(
            status=SkillStatus.SUCCESS,
            summary=f"Wrote {path} ({len(new_content)} chars)",
            artifacts=[file_artifact.id, diff_artifact.id],
            observations={"path": path},
            confidence=0.85,
        )
