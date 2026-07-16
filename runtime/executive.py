from __future__ import annotations

import json

from events.events import Event, EventType
from runtime.dispatcher import Dispatcher
from runtime.llm_client import LLMClient, get_llm_client
from runtime.runtime_state import RunStatus, RuntimeState
from skills.base import SkillStatus
from tasks.task import Task

PLANNING_SYSTEM_PROMPT = """You are the Executive: the single reasoning agent of an autonomous
coding runtime. You never edit files or run commands yourself. You only decide.

Given a user goal and the current workspace state, produce a JSON plan: a list of tasks.
Each task has: title, description, executor (one of: CodeSkill, FilesystemSkill, TerminalSkill),
priority (int, higher runs first), dependencies (list of 0-based indices of other tasks in this
same list that must complete first), and input_data (object with fields the skill needs).

CodeSkill input_data: {"target_path": "relative/path.py"} (writes/overwrites a file via LLM).
FilesystemSkill input_data: {"operation": "list"|"read"|"search", "path": "...", "query": "..."}.
TerminalSkill input_data: {"command": ["pytest", "-q"]} (list of argv, binary must be one of
python3, pytest, node, npm, git, ls, cat).

Respond ONLY with JSON: {"tasks": [...], "done": false}. Set "done": true with an empty task
list only if the goal is already fully satisfied by prior results."""

REVIEW_SYSTEM_PROMPT = """You are the Executive reviewing a completed task's result. Decide
one of: "continue" (plan stands, proceed to next task), "replan" (goal needs new/changed tasks),
or "done" (overall goal is satisfied). Respond ONLY with JSON:
{"decision": "continue"|"replan"|"done", "reason": "short reason"}."""


class Executive:
    """The only reasoning component. Never edits files. Never runs commands. Only decides."""

    def __init__(
        self,
        state: RuntimeState,
        dispatcher: Dispatcher,
        model: str | None = None,
        provider: str | None = None,
        client: LLMClient | None = None,
    ) -> None:
        self.state = state
        self.dispatcher = dispatcher
        self._model = model
        self._provider = provider
        self._client = client  # lazily built on first use if not injected

    def _get_client(self) -> LLMClient:
        if self._client is None:
            self._client = get_llm_client(model=self._model, provider=self._provider)
        return self._client

    def _call_llm(self, system: str, user: str) -> dict:
        client = self._get_client()
        text = client.complete(system, user, max_tokens=2048)
        text = text.strip()
        if text.startswith("```"):
            text = text.strip("`")
            text = text.split("\n", 1)[-1] if text.lower().startswith("json") else text
        return json.loads(text)

    # --- planning ---
    def plan(self, goal: str) -> bool:
        """Generate tasks for `goal`, enqueue them. Returns True if any tasks were added."""
        workspace_summary = "\n".join(self.state.workspace.repository_tree(50)) or "(empty workspace)"
        prior_results = "\n".join(self.state.logs[-10:])

        user_prompt = (
            f"Goal: {goal}\n\nWorkspace files:\n{workspace_summary}\n\n"
            f"Recent execution log:\n{prior_results or '(none yet)'}"
        )
        plan_data = self._call_llm(PLANNING_SYSTEM_PROMPT, user_prompt)

        if plan_data.get("done"):
            self.state.status = RunStatus.DONE
            return False

        raw_tasks = plan_data.get("tasks", [])
        id_by_index: dict[int, str] = {}
        tasks: list[Task] = []
        for idx, t in enumerate(raw_tasks):
            task = Task(
                title=t.get("title", f"task-{idx}"),
                description=t.get("description", ""),
                executor=t.get("executor", "FilesystemSkill"),
                priority=t.get("priority", 0),
                input_data=t.get("input_data", {}),
            )
            id_by_index[idx] = task.id
            tasks.append(task)

        for idx, t in enumerate(raw_tasks):
            dep_indices = t.get("dependencies", [])
            tasks[idx].dependencies = [id_by_index[d] for d in dep_indices if d in id_by_index]

        for task in tasks:
            self.state.task_queue.enqueue(task)
            self.state.current_plan.append(task.id)
            self.state.events.publish(Event(type=EventType.TASK_CREATED, payload={"task_id": task.id}))

        self.state.events.publish(Event(type=EventType.PLAN_UPDATED, payload={"task_count": len(tasks)}))
        return len(tasks) > 0

    # --- review ---
    def review(self, task: Task, result) -> str:
        user_prompt = (
            f"Task: {task.title}\nExpected: {task.description}\n"
            f"Result status: {result.status}\nSummary: {result.summary}\n"
            f"Confidence: {result.confidence}"
        )
        try:
            decision_data = self._call_llm(REVIEW_SYSTEM_PROMPT, user_prompt)
            return decision_data.get("decision", "continue")
        except Exception:
            # fall back to a deterministic rule if the LLM review call fails
            return "continue" if result.status == SkillStatus.SUCCESS else "replan"

    # --- main loop ---
    def run(self, goal: str, max_iterations: int = 25) -> RunStatus:
        if not self.plan(goal):
            return self.state.status

        iterations = 0
        while iterations < max_iterations:
            iterations += 1

            task = self.state.task_queue.dequeue()
            if task is None:
                if self.state.task_queue.has_pending_work():
                    # blocked tasks with unmet deps that will never resolve
                    self.state.status = RunStatus.FAILED
                    self.state.log("No runnable tasks but pending work remains; stopping.")
                    break
                # queue empty: ask executive if goal is fully done or needs a new plan
                if not self.plan(goal):
                    break
                continue

            result = self.dispatcher.dispatch(task)
            self.state.execution_metrics["tasks_run"] += 1

            if result.status == SkillStatus.SUCCESS:
                self.state.task_queue.complete(task.id)
                self.state.log(f"[DONE] {task.title}: {result.summary}")
                self.state.events.publish(
                    Event(type=EventType.TASK_COMPLETED, payload={"task_id": task.id})
                )
            else:
                self.state.execution_metrics["tasks_failed"] += 1
                updated = self.state.task_queue.fail(task.id, result.summary)
                self.state.log(f"[FAILED] {task.title}: {result.summary}")
                self.state.events.publish(
                    Event(type=EventType.TASK_FAILED, payload={"task_id": task.id, "error": result.summary})
                )

            decision = self.review(task, result)
            if decision == "done":
                self.state.status = RunStatus.DONE
                break
            if decision == "replan":
                self.plan(goal)

        else:
            self.state.log("Max iterations reached.")

        if self.state.status == RunStatus.RUNNING and not self.state.task_queue.has_pending_work():
            self.state.status = RunStatus.DONE

        self.state.events.publish(
            Event(type=EventType.EXECUTION_FINISHED, payload={"status": self.state.status})
        )
        return self.state.status
