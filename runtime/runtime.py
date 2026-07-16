from __future__ import annotations

from artifacts.store import ArtifactStore
from runtime.context_builder import ContextBuilder
from runtime.dispatcher import Dispatcher
from runtime.executive import Executive
from runtime.llm_client import LLMClient, SharedLazyLLMClient
from runtime.runtime_state import RunStatus, RuntimeState
from skills.base import Skill
from skills.code_skill import CodeSkill
from skills.filesystem_skill import FilesystemSkill
from skills.terminal_skill import TerminalSkill


class Runtime:
    """Owns lifecycle, task execution, planning loop, events, memory, workspace access.
    Nothing bypasses Runtime.

    `provider` selects which LLM backend is used for both the Executive (planning/review)
    and CodeSkill (generation): "anthropic" | "openai" | "openrouter". Falls back to the
    LLM_PROVIDER env var, then to "anthropic", if not given. `model` overrides the default
    model id for whichever provider is chosen.

    The actual provider client/API key is resolved lazily, on first real LLM call, not at
    construction time - so building a Runtime never requires an API key to be present
    (useful for tests and for wiring that never reaches an LLM call).
    """

    def __init__(self, workspace_root: str, model: str | None = None, provider: str | None = None) -> None:
        self.state = RuntimeState(workspace_root)

        # One shared lazy handle so Executive and CodeSkill resolve to the same
        # provider/model/client, but only on first actual use.
        client: LLMClient = SharedLazyLLMClient(model=model, provider=provider)

        skills: dict[str, Skill] = {
            "CodeSkill": CodeSkill(self.state.artifacts, client=client),
            "FilesystemSkill": FilesystemSkill(self.state.artifacts),
            "TerminalSkill": TerminalSkill(self.state.artifacts),
        }

        context_builder = ContextBuilder(self.state.memory)
        self.dispatcher = Dispatcher(skills, context_builder, self.state.workspace, self.state.events)
        self.executive = Executive(self.state, self.dispatcher, client=client)

    def run(self, goal: str, max_iterations: int = 25) -> RunStatus:
        return self.executive.run(goal, max_iterations=max_iterations)

    def stream_log(self) -> list[str]:
        return self.state.logs
