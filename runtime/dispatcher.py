from __future__ import annotations

from events.bus import EventBus
from events.events import Event, EventType
from runtime.context_builder import ContextBuilder
from skills.base import Skill, SkillResult
from tasks.task import Task
from workspace.workspace import Workspace


class Dispatcher:
    """Routes a task to its skill, executes it, publishes events.
    Never plans. Never retries. Only routes work.
    """

    def __init__(
        self,
        skills: dict[str, Skill],
        context_builder: ContextBuilder,
        workspace: Workspace,
        event_bus: EventBus,
    ) -> None:
        self.skills = skills
        self.context_builder = context_builder
        self.workspace = workspace
        self.event_bus = event_bus

    def dispatch(self, task: Task) -> SkillResult:
        self.event_bus.publish(Event(type=EventType.TASK_STARTED, payload={"task_id": task.id}))

        skill = self.skills.get(task.executor)
        if skill is None:
            result = SkillResult(
                status="FAILURE",
                summary=f"No skill registered for executor '{task.executor}'",
                confidence=0.0,
            )
            self.event_bus.publish(
                Event(type=EventType.TASK_FAILED, payload={"task_id": task.id, "error": result.summary})
            )
            return result

        context = self.context_builder.build(task, self.workspace)
        result = skill.execute(task, self.workspace, context)

        for artifact_id in result.artifacts:
            self.event_bus.publish(
                Event(type=EventType.ARTIFACT_CREATED, payload={"task_id": task.id, "artifact_id": artifact_id})
            )

        self.event_bus.publish(
            Event(type=EventType.WORKSPACE_UPDATED, payload={"task_id": task.id})
        )

        return result
