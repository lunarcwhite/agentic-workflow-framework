from src import Task, complete_task

def test_complete_task_changes_state():
    task = Task('TASK-0001', 'Document UAAF flow')
    complete_task(task)
    assert task.completed is True

def test_complete_task_is_idempotent():
    task = Task('TASK-0001', 'Document UAAF flow', True)
    complete_task(task)
    assert task.completed is True
