from __future__ import annotations

import argparse
import sys

from config.limits import limits
from runtime.runtime import Runtime


def main() -> int:
    parser = argparse.ArgumentParser(description="Claude-Code-style autonomous coding runtime")
    parser.add_argument("goal", help="Natural-language goal for the executive to plan and execute")
    parser.add_argument("--workspace", default="./workspace_root", help="Workspace root directory")
    parser.add_argument(
        "--provider",
        choices=["anthropic", "openai", "openrouter"],
        default=None,
        help="LLM provider; falls back to LLM_PROVIDER env var, then 'anthropic'",
    )
    parser.add_argument(
        "--model", default=None, help="Model id override; falls back to LLM_MODEL env var, then provider default"
    )
    parser.add_argument(
        "--max-iterations", type=int, default=limits.max_iterations, help="Max planning/execution iterations"
    )
    parser.add_argument(
        "--engine",
        choices=["loop", "graph"],
        default="loop",
        help="'loop' uses Executive.run directly; 'graph' uses the LangGraph StateGraph engine",
    )
    args = parser.parse_args()

    runtime = Runtime(args.workspace, model=args.model, provider=args.provider)

    if args.engine == "graph":
        from runtime.graph import run_graph

        status = run_graph(
            runtime.state, runtime.dispatcher, runtime.executive, args.goal, max_iterations=args.max_iterations
        )
    else:
        status = runtime.run(args.goal, max_iterations=args.max_iterations)

    print(f"\n=== Execution finished: {status} ===")
    for line in runtime.stream_log():
        print(line)

    return 0 if str(status) in ("RunStatus.DONE", "DONE") else 1


if __name__ == "__main__":
    sys.exit(main())
