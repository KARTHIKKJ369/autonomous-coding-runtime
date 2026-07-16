import tempfile

from artifacts.store import ArtifactStore
from events.bus import EventBus
from events.events import EventType
from memory.memory import MemoryStore
from runtime.context_builder import ContextBuilder
from runtime.dispatcher import Dispatcher
from skills.base import SkillStatus
from skills.filesystem_skill import FilesystemSkill
from tasks.task import Task
from workspace.workspace import Workspace


def make_dispatcher():
    tmp = tempfile.mkdtemp()
    ws = Workspace(tmp)
    ws.write_file("a.txt", "content-a")
    store = ArtifactStore()
    bus = EventBus()
    memory = MemoryStore()
    skills = {"FilesystemSkill": FilesystemSkill(store)}
    ctx_builder = ContextBuilder(memory)
    dispatcher = Dispatcher(skills, ctx_builder, ws, bus)
    return dispatcher, bus, ws


def test_dispatch_success_publishes_events():
    dispatcher, bus, ws = make_dispatcher()
    task = Task(title="read a", description="", executor="FilesystemSkill", input_data={"operation": "read", "path": "a.txt"})
    result = dispatcher.dispatch(task)
    assert result.status == SkillStatus.SUCCESS
    published_types = [e.type for e in bus.history]
    assert EventType.TASK_STARTED in published_types
    assert EventType.ARTIFACT_CREATED in published_types
    assert EventType.WORKSPACE_UPDATED in published_types


def test_dispatch_unknown_executor_fails_gracefully():
    dispatcher, bus, ws = make_dispatcher()
    task = Task(title="ghost", description="", executor="NoSuchSkill")
    result = dispatcher.dispatch(task)
    assert result.status == "FAILURE"
    assert EventType.TASK_FAILED in [e.type for e in bus.history]


def test_context_builder_includes_target_path_content():
    dispatcher, bus, ws = make_dispatcher()
    from runtime.context_builder import ContextBuilder
    from memory.memory import MemoryStore

    cb = ContextBuilder(MemoryStore())
    task = Task(title="edit a", description="", executor="CodeSkill", input_data={"target_path": "a.txt"})
    ctx = cb.build(task, ws)
    assert "a.txt" in ctx.relevant_files
    assert ctx.relevant_files["a.txt"] == "content-a"
