from tasks.queue import TaskQueue
from tasks.task import Task, TaskStatus


def make_task(title, deps=None, priority=0):
    return Task(title=title, description="", executor="FilesystemSkill", dependencies=deps or [], priority=priority)


def test_ready_task_dequeues():
    q = TaskQueue()
    t = make_task("a")
    q.enqueue(t)
    assert t.status == TaskStatus.READY
    popped = q.dequeue()
    assert popped.id == t.id
    assert popped.status == TaskStatus.RUNNING


def test_blocked_until_dependency_done():
    q = TaskQueue()
    t1 = make_task("first")
    q.enqueue(t1)
    t2 = make_task("second", deps=[t1.id])
    q.enqueue(t2)
    assert t2.status == TaskStatus.BLOCKED

    assert q.dequeue().id == t1.id  # only t1 is ready
    unlocked = q.complete(t1.id)
    assert t2.id in [t.id for t in unlocked]
    assert t2.status == TaskStatus.READY


def test_priority_ordering():
    q = TaskQueue()
    low = make_task("low", priority=0)
    high = make_task("high", priority=10)
    q.enqueue(low)
    q.enqueue(high)
    popped = q.dequeue()
    assert popped.id == high.id


def test_retry_then_fail():
    q = TaskQueue()
    t = make_task("flaky")
    t.max_retries = 1
    q.enqueue(t)
    q.dequeue()
    q.fail(t.id, "boom")
    assert t.status == TaskStatus.READY  # first retry
    q.dequeue()
    q.fail(t.id, "boom again")
    assert t.status == TaskStatus.FAILED
    assert t.id in q.failed_ids


def test_has_pending_work_false_when_all_done():
    q = TaskQueue()
    t = make_task("only")
    q.enqueue(t)
    q.dequeue()
    q.complete(t.id)
    assert q.has_pending_work() is False
