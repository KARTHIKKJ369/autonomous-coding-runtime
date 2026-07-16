from __future__ import annotations

from typing import Any, TypedDict

from langgraph.graph import END, StateGraph

from events.events import Event, EventType
from runtime.dispatcher import Dispatcher
from runtime.executive import Executive
from runtime.runtime_state import RunStatus, RuntimeState
from skills.base import SkillStatus
from tasks.task import Task


class GraphState(TypedDict, total=False):
    goal: str
    current_task: Task | None
    last_result: Any
    decision: str
    iterations: int
    max_iterations: int


def build_graph(state: RuntimeState, dispatcher: Dispatcher, executive: Executive):
    """StateGraph owns RuntimeState, Task Queue, Workspace, Memory, Events indirectly
    through the closures below; GraphState only carries per-tick control data.
    """

    def observe(gs: GraphState) -> GraphState:
        gs["iterations"] = gs.get("iterations", 0) + 1
        return gs

    def plan(gs: GraphState) -> GraphState:
        executive.plan(gs["goal"])
        return gs

    def select_task(gs: GraphState) -> GraphState:
        gs["current_task"] = state.task_queue.dequeue()
        return gs

    def dispatch(gs: GraphState) -> GraphState:
        task = gs["current_task"]
        if task is None:
            gs["last_result"] = None
            return gs
        gs["last_result"] = dispatcher.dispatch(task)
        return gs

    def execute_skill(gs: GraphState) -> GraphState:
        # Execution happens inside dispatch (skills are synchronous); this node
        # records bookkeeping so the graph shape matches the spec exactly.
        task = gs["current_task"]
        result = gs["last_result"]
        if task is None or result is None:
            return gs
        state.execution_metrics["tasks_run"] += 1
        if result.status == SkillStatus.SUCCESS:
            state.task_queue.complete(task.id)
            state.log(f"[DONE] {task.title}: {result.summary}")
            state.events.publish(Event(type=EventType.TASK_COMPLETED, payload={"task_id": task.id}))
        else:
            state.execution_metrics["tasks_failed"] += 1
            state.task_queue.fail(task.id, result.summary)
            state.log(f"[FAILED] {task.title}: {result.summary}")
            state.events.publish(
                Event(type=EventType.TASK_FAILED, payload={"task_id": task.id, "error": result.summary})
            )
        return gs

    def review(gs: GraphState) -> GraphState:
        task = gs["current_task"]
        result = gs["last_result"]
        if task is None or result is None:
            gs["decision"] = "continue"
            return gs
        gs["decision"] = executive.review(task, result)
        return gs

    def update_workspace(gs: GraphState) -> GraphState:
        # Workspace is already updated by the skill via Dispatcher; this node exists
        # as an explicit checkpoint per the spec's graph shape.
        return gs

    def route_after_review(gs: GraphState) -> str:
        if gs["decision"] == "done":
            return "end"
        if gs["decision"] == "replan":
            return "plan_again"
        if gs["iterations"] >= gs.get("max_iterations", 25):
            return "end"
        if gs["current_task"] is None and not state.task_queue.has_pending_work():
            return "end"
        return "more_tasks"

    graph = StateGraph(GraphState)
    graph.add_node("observe", observe)
    graph.add_node("plan", plan)
    graph.add_node("select_task", select_task)
    graph.add_node("dispatch", dispatch)
    graph.add_node("execute_skill", execute_skill)
    graph.add_node("review", review)
    graph.add_node("update_workspace", update_workspace)

    graph.set_entry_point("observe")
    graph.add_edge("observe", "plan")
    graph.add_edge("plan", "select_task")
    graph.add_edge("select_task", "dispatch")
    graph.add_edge("dispatch", "execute_skill")
    graph.add_edge("execute_skill", "review")
    graph.add_edge("review", "update_workspace")
    graph.add_conditional_edges(
        "update_workspace",
        route_after_review,
        {"more_tasks": "select_task", "plan_again": "plan", "end": END},
    )

    return graph.compile()


def run_graph(state: RuntimeState, dispatcher: Dispatcher, executive: Executive, goal: str, max_iterations: int = 25) -> RunStatus:
    app = build_graph(state, dispatcher, executive)
    app.invoke(
        {"goal": goal, "iterations": 0, "max_iterations": max_iterations},
        config={"recursion_limit": max_iterations * 4 + 10},
    )
    if state.status == RunStatus.RUNNING:
        state.status = RunStatus.DONE if not state.task_queue.has_pending_work() else RunStatus.FAILED
    state.events.publish(Event(type=EventType.EXECUTION_FINISHED, payload={"status": state.status}))
    return state.status
