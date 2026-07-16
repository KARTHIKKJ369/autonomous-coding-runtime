import tempfile
from pathlib import Path

from artifacts.store import ArtifactStore
from skills.base import SkillStatus, TaskContext
from skills.filesystem_skill import FilesystemSkill
from skills.terminal_skill import TerminalSkill
from tasks.task import Task
from workspace.workspace import Workspace


def make_workspace():
    tmp = tempfile.mkdtemp()
    ws = Workspace(tmp)
    ws.write_file("hello.txt", "hello world\n")
    ws.write_file("sub/nested.py", "print('hi')\n")
    return ws


def test_filesystem_skill_list():
    ws = make_workspace()
    store = ArtifactStore()
    skill = FilesystemSkill(store)
    task = Task(title="list", description="", executor="FilesystemSkill", input_data={"operation": "list"})
    ctx = TaskContext(task_summary="list")
    result = skill.execute(task, ws, ctx)
    assert result.status == SkillStatus.SUCCESS
    assert "hello.txt" in result.observations["files"]
    assert "sub/nested.py" in result.observations["files"]


def test_filesystem_skill_read():
    ws = make_workspace()
    store = ArtifactStore()
    skill = FilesystemSkill(store)
    task = Task(title="read", description="", executor="FilesystemSkill", input_data={"operation": "read", "path": "hello.txt"})
    ctx = TaskContext(task_summary="read")
    result = skill.execute(task, ws, ctx)
    assert result.status == SkillStatus.SUCCESS
    artifact = store.get(result.artifacts[0])
    assert artifact.content == "hello world\n"


def test_filesystem_skill_search():
    ws = make_workspace()
    store = ArtifactStore()
    skill = FilesystemSkill(store)
    task = Task(title="search", description="", executor="FilesystemSkill", input_data={"operation": "search", "query": "hi"})
    ctx = TaskContext(task_summary="search")
    result = skill.execute(task, ws, ctx)
    assert result.status == SkillStatus.SUCCESS
    assert "sub/nested.py" in result.observations["matches"]


def test_terminal_skill_runs_allowed_command():
    ws = make_workspace()
    store = ArtifactStore()
    skill = TerminalSkill(store)
    task = Task(title="ls", description="", executor="TerminalSkill", input_data={"command": ["ls"]})
    ctx = TaskContext(task_summary="ls")
    result = skill.execute(task, ws, ctx)
    assert result.status == SkillStatus.SUCCESS
    assert result.observations["exit_code"] == 0


def test_terminal_skill_blocks_disallowed_binary():
    ws = make_workspace()
    store = ArtifactStore()
    skill = TerminalSkill(store)
    task = Task(title="rm", description="", executor="TerminalSkill", input_data={"command": ["rm", "-rf", "/"]})
    ctx = TaskContext(task_summary="rm")
    result = skill.execute(task, ws, ctx)
    assert result.status == SkillStatus.FAILURE


def test_filesystem_reader_blocks_path_escape():
    ws = make_workspace()
    try:
        ws.reader.read("../../etc/passwd")
        assert False, "should have raised"
    except PermissionError:
        pass
