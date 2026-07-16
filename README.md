# Autonomous Coding Runtime (Claude-Code-style)

Single executive reasoning agent + stateless skill workers + shared workspace +
event-driven task queue, per the spec. This is a **working core**, not the full
20-module spec — scoped intentionally to prove the architecture end-to-end:

- `runtime/runtime_state.py` — the one global state object (workspace, queue, artifacts, memory, events)
- `runtime/executive.py` — the only reasoning agent: plans (LLM call), reviews results (LLM call), decides continue/replan/done. Never touches files or shells directly.
- `runtime/dispatcher.py` — routes a task to its skill, publishes events. No planning, no retries.
- `runtime/context_builder.py` — Task → relevant files/memory/artifacts → minimal `TaskContext`. Never the full chat history.
- `runtime/graph.py` — the same loop expressed as a LangGraph `StateGraph` (Observe→Plan→Select→Dispatch→Execute→Review→Update→loop), per spec.
- `tasks/` — `Task` model, `DependencyGraph`, `TaskQueue` (enqueue/dequeue/retry/complete/fail/unlock_dependents).
- `skills/` — stateless workers: `CodeSkill` (LLM-backed file generation/edit), `FilesystemSkill` (list/read/search), `TerminalSkill` (sandboxed allow-listed shell commands: python3, pytest, node, npm, git, ls, cat).
- `workspace/workspace.py` — single source of truth for files, opened/generated file tracking, scratchpad.
- `memory/memory.py` — short-term / workspace / long-term layers with keyword-overlap retrieval (swap for embeddings later without touching callers).
- `events/` — typed `Event`/`EventType` + synchronous in-process `EventBus`.
- `artifacts/` — immutable `Artifact` model + `ArtifactStore` (files, diffs, terminal output, search results...).
- `filesystem/` — `FileReader`/`FileWriter` (path-escape guarded) + unified diff helper.
- `terminal/runner.py` — subprocess runner, cwd pinned to workspace root, timeout-bounded.
- `config/limits.py` — all limits from env vars, no hardcoded values.

## Providers

`runtime/llm_client.py` is the one place that talks to a model API. Both the Executive
(planning/review) and CodeSkill (generation) go through this same abstraction, so you pick
a provider once and both use it consistently.

Supported: `anthropic`, `openai`, `openrouter` (OpenRouter is OpenAI-API-compatible, so it
shares the `OpenAICompatibleAdapter` with a different `base_url`).

```bash
# Anthropic (default)
export ANTHROPIC_API_KEY=sk-ant-...
python3 main.py "your goal"

# OpenAI
export LLM_PROVIDER=openai
export OPENAI_API_KEY=sk-...
python3 main.py "your goal"

# OpenRouter (access Claude/GPT/Gemini/Llama/etc through one key)
export LLM_PROVIDER=openrouter
export OPENROUTER_API_KEY=sk-or-...
python3 main.py "your goal" --model "anthropic/claude-sonnet-4.6"
```

Or via CLI flags instead of env vars: `--provider openrouter --model "openai/gpt-4.1"`.

`LLM_MODEL` env var / `--model` flag overrides the default model id for whichever provider
is active. Provider/API-key resolution is lazy — building a `Runtime` never requires a key
to be present; it's only resolved on the first actual LLM call (planning, review, or code
generation), so wiring and tests work with zero keys configured.

## Interactive shell (recommended over exporting env vars every time)

`shell.py` gives you a `/connect` command so you set the provider once and it's remembered
across sessions — no `export ANTHROPIC_API_KEY=...` every time you open a new terminal.

```bash
python3 shell.py
```

```
Autonomous Coding Runtime — interactive shell. Type /help for commands.
No provider connected yet. Use /connect <provider> <api_key> to set one up.

> /connect anthropic sk-ant-...
Connected. Connected: provider=anthropic model=claude-sonnet-4-6 key=sk-ant...xxxx

> /connect openrouter sk-or-v1-... anthropic/claude-sonnet-4.6
Connected. Connected: provider=openrouter model=anthropic/claude-sonnet-4.6 key=sk-or-v...xxxx

> Create a hello.py that prints Hello World, then run it
=== Execution finished: DONE ===
...
```

Commands:

| Command | Effect |
|---|---|
| `/connect <provider> <api_key> [model]` | Save a connection to `~/.autonomous_runtime/credentials.json` (chmod 600), persists across sessions |
| `/status` | Show current provider/model/masked key, workspace, engine |
| `/disconnect` | Remove the saved connection |
| `/model <model_id>` | Override model for this session only (doesn't persist) |
| `/workspace <path>` | Switch workspace root |
| `/engine <loop\|graph>` | Switch between the direct executive loop and the LangGraph engine |
| `/help` | List commands |
| `/exit`, `/quit` | Exit |

Anything typed that doesn't start with `/` is treated as a goal and run immediately.

Resolution priority (highest wins): explicit CLI/shell args → environment variables →
saved `/connect` credentials → provider default. So `export ANTHROPIC_API_KEY=...` still
works and takes priority if you ever want to override a saved connection for one shell session.

`~/.autonomous_runtime/credentials.json` is written with `0600` permissions (owner
read/write only). Override its location with `RUNTIME_CONFIG_DIR` if you'd rather keep it
elsewhere (e.g. on an encrypted volume).

## One-shot CLI (`main.py`)

```bash
export ANTHROPIC_API_KEY=sk-...
python3 main.py "Create a hello.py that prints Hello World, then run it" --workspace ./workspace_root
```

Use `--engine graph` to run the same thing through the LangGraph StateGraph instead of the direct loop.

## Tests

```bash
pip install pytest --break-system-packages
python3 -m pytest tests/ -q
```

15 tests cover the task queue/dependency graph, filesystem/terminal skills (including
path-escape and disallowed-binary guards), dispatcher event wiring, context building, and
a full mocked end-to-end run of the executive loop (planning LLM call and review LLM call
mocked out — no network needed to verify the control flow).

## Not yet built (deferred from the full spec)

GitSkill, DocsSkill, MemorySkill, SearchSkill (internet), streaming layer, `config/*.yaml`
files, structured logging/metrics/tracing, workspace `repository_index.py`/`file_index.py`,
`artifacts/serializer.py`. The architecture (RuntimeState as single source of truth,
stateless skills, event-driven dispatch, task queue with dependency unlocking) is in place
so these slot in as additional skills/modules without touching the executive or runtime core.
