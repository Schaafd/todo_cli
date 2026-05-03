"""Repository abstraction over Storage for todo/project persistence."""

from typing import List, Tuple

from ...domain import Project, Todo
from ...storage import Storage


class TodoRepository:
    """Encapsulates todo persistence operations."""

    def __init__(self, storage: Storage):
        self.storage = storage

    def list_projects(self) -> List[str]:
        return self.storage.list_projects()

    def load_project(self, project_name: str) -> Tuple[Project, List[Todo]]:
        return self.storage.load_project(project_name)

    def save_project(self, project: Project, todos: List[Todo]) -> bool:
        return self.storage.save_project(project, todos)

    def next_todo_id(self, project_name: str) -> int:
        return self.storage.get_next_todo_id()

    def add_todo(self, project_name: str, todo: Todo) -> bool:
        project, todos = self.storage.load_project(project_name)
        todos.append(todo)
        return self.storage.save_project(project, todos)
