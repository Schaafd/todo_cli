"""Application-layer task command handlers."""

from dataclasses import dataclass
from typing import Optional

from ..config import ConfigModel
from ..core.errors import ValidationError, StorageError
from ..domain import TaskBuilder, parse_task_input, Todo
from ..storage import Storage
from ..infrastructure.storage.repository import TodoRepository


@dataclass
class AddTaskResult:
    todo: Todo
    suggestions: list[str]


def add_task_from_input(
    *,
    storage: Storage,
    config: ConfigModel,
    input_text: str,
    project: Optional[str] = None,
) -> AddTaskResult:
    """Parse natural-language input and persist a new task."""
    repository = TodoRepository(storage)
    all_todos: list[Todo] = []
    projects = repository.list_projects() or [config.default_project]

    for proj_name in projects:
        _, todos = repository.load_project(proj_name)
        if todos:
            all_todos.extend(todos)

    available_projects = list({t.project for t in all_todos if t.project})
    available_tags = list({tag for t in all_todos for tag in t.tags})
    available_people = list({person for t in all_todos for person in t.assignees})

    parsed, errors, suggestions = parse_task_input(
        input_text,
        config,
        project_hint=project or config.default_project,
        available_projects=available_projects,
        available_tags=available_tags,
        available_people=available_people,
    )

    blocking_errors = [e for e in errors if e.severity == "error"]
    if blocking_errors:
        joined = "; ".join(e.message for e in blocking_errors)
        raise ValidationError(joined)

    target_project = parsed.project or project or config.default_project
    proj, existing_todos = repository.load_project(target_project)
    next_id = repository.next_todo_id(target_project)

    builder = TaskBuilder(config)
    todo = builder.build(parsed, next_id)
    todo.project = target_project

    existing_todos.append(todo)
    if not repository.save_project(proj, existing_todos):
        raise StorageError("Failed to save todo")

    return AddTaskResult(todo=todo, suggestions=suggestions)
