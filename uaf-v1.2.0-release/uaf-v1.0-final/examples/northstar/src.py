from dataclasses import dataclass

@dataclass
class Task:
    id: str
    title: str
    completed: bool = False


def complete_task(task: Task) -> Task:
    if task.completed:
        return task
    task.completed = True
    return task
