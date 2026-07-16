from __future__ import annotations

import shlex
import sys

from config.credentials import clear_connection, current_connection_summary, save_connection
from config.limits import limits
from runtime.runtime import Runtime

HELP_TEXT = """Commands:
  /connect <provider> <api_key> [model]   Save a provider connection (anthropic|openai|openrouter)
  /status                                  Show current connection
  /disconnect                              Remove saved connection
  /model <model_id>                        Override model for this session only
  /workspace <path>                        Switch workspace root (starts a fresh runtime)
  /engine <loop|graph>                     Switch execution engine
  /help                                    Show this message
  /exit, /quit                             Exit

Anything else you type is treated as a goal and handed to the executive to plan + run.

Examples:
  /connect openrouter sk-or-v1-xxxx anthropic/claude-sonnet-4.6
  /connect anthropic sk-ant-xxxx
  Create a hello.py that prints Hello World, then run it
"""

VALID_PROVIDERS = {"anthropic", "openai", "openrouter"}


class Shell:
    def __init__(self, workspace_root: str = "./workspace_root", engine: str = "loop") -> None:
        self.workspace_root = workspace_root
        self.engine = engine
        self.session_model: str | None = None
        self.runtime: Runtime | None = None

    def _get_runtime(self) -> Runtime:
        # Rebuilt lazily so /connect, /model, /workspace changes take effect on next run.
        if self.runtime is None:
            self.runtime = Runtime(self.workspace_root, model=self.session_model)
        return self.runtime

    def handle_connect(self, args: list[str]) -> None:
        if len(args) < 2:
            print("Usage: /connect <provider> <api_key> [model]")
            print(f"  providers: {', '.join(sorted(VALID_PROVIDERS))}")
            return
        provider, api_key = args[0].lower(), args[1]
        model = args[2] if len(args) > 2 else None
        if provider not in VALID_PROVIDERS:
            print(f"Unknown provider '{provider}'. Expected one of: {', '.join(sorted(VALID_PROVIDERS))}")
            return
        save_connection(provider, api_key, model=model)
        self.runtime = None  # force rebuild so the new connection takes effect
        print(f"Connected. {current_connection_summary()}")

    def handle_disconnect(self) -> None:
        clear_connection()
        self.runtime = None
        print("Disconnected. Saved credentials removed.")

    def handle_status(self) -> None:
        print(current_connection_summary())
        print(f"Workspace: {self.workspace_root}")
        print(f"Engine: {self.engine}")
        if self.session_model:
            print(f"Session model override: {self.session_model}")

    def handle_model(self, args: list[str]) -> None:
        if not args:
            print("Usage: /model <model_id>")
            return
        self.session_model = args[0]
        self.runtime = None
        print(f"Session model set to: {self.session_model}")

    def handle_workspace(self, args: list[str]) -> None:
        if not args:
            print("Usage: /workspace <path>")
            return
        self.workspace_root = args[0]
        self.runtime = None
        print(f"Workspace set to: {self.workspace_root} (runtime will rebuild on next goal)")

    def handle_engine(self, args: list[str]) -> None:
        if not args or args[0] not in ("loop", "graph"):
            print("Usage: /engine <loop|graph>")
            return
        self.engine = args[0]
        print(f"Engine set to: {self.engine}")

    def run_goal(self, goal: str) -> None:
        try:
            runtime = self._get_runtime()
        except Exception as e:
            print(f"Could not start runtime: {e}")
            return

        try:
            if self.engine == "graph":
                from runtime.graph import run_graph

                status = run_graph(
                    runtime.state, runtime.dispatcher, runtime.executive, goal, max_iterations=limits.max_iterations
                )
            else:
                status = runtime.run(goal, max_iterations=limits.max_iterations)
        except RuntimeError as e:
            # Typically a missing-API-key error surfaced lazily on first LLM call.
            print(f"Error: {e}")
            return

        print(f"\n=== Execution finished: {status} ===")
        for line in runtime.stream_log():
            print(line)

    def loop(self) -> None:
        print("Autonomous Coding Runtime — interactive shell. Type /help for commands.")
        print(current_connection_summary())
        while True:
            try:
                raw = input("\n> ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\nExiting.")
                break

            if not raw:
                continue

            if raw.startswith("/"):
                parts = shlex.split(raw)
                cmd, args = parts[0].lower(), parts[1:]

                if cmd in ("/exit", "/quit"):
                    print("Exiting.")
                    break
                elif cmd == "/help":
                    print(HELP_TEXT)
                elif cmd == "/connect":
                    self.handle_connect(args)
                elif cmd == "/disconnect":
                    self.handle_disconnect()
                elif cmd == "/status":
                    self.handle_status()
                elif cmd == "/model":
                    self.handle_model(args)
                elif cmd == "/workspace":
                    self.handle_workspace(args)
                elif cmd == "/engine":
                    self.handle_engine(args)
                else:
                    print(f"Unknown command: {cmd}. Type /help for a list.")
                continue

            self.run_goal(raw)


def main() -> int:
    shell = Shell()
    shell.loop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
