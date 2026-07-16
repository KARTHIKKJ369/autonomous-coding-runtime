"""End-to-end test of Runtime with Executive LLM calls mocked out.
Verifies: plan -> dequeue -> dispatch -> review -> completion, without hitting the network.
"""
import tempfile
from unittest.mock import patch

from runtime.runtime import Runtime
from runtime.runtime_state import RunStatus

PLAN_RESPONSE = {
    "tasks": [
        {
            "title": "list workspace files",
            "description": "See what's in the workspace",
            "executor": "FilesystemSkill",
            "priority": 1,
            "dependencies": [],
            "input_data": {"operation": "list"},
        }
    ],
    "done": False,
}

REVIEW_DONE_RESPONSE = {"decision": "done", "reason": "goal satisfied"}

_call_count = {"n": 0}


def fake_call_llm(self, system, user):
    # Distinguish by the literal planning marker, not a substring that also
    # appears inside the review prompt (e.g. "replan").
    if "produce a JSON plan" in system:
        return PLAN_RESPONSE
    return REVIEW_DONE_RESPONSE


def test_full_loop_with_mocked_executive_llm():
    tmp = tempfile.mkdtemp()
    runtime = Runtime(tmp)

    with patch("runtime.executive.Executive._call_llm", fake_call_llm):
        status = runtime.run("List all files in the repo", max_iterations=5)

    assert status == RunStatus.DONE
    assert runtime.state.execution_metrics["tasks_run"] == 1
    assert len(runtime.state.task_queue.completed_ids) == 1
    logs = runtime.stream_log()
    assert any("DONE" in line for line in logs)


if __name__ == "__main__":
    test_full_loop_with_mocked_executive_llm()
    print("smoke test passed")
