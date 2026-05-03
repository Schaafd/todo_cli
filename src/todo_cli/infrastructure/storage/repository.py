"""Repository abstraction over Storage for todo/project persistence."""

from typing import List, Tuple

from ...core.errors import StorageError
from ...domain import Project, Todo
from ...storage import Storage


class TodoRepository:
    """Encapsulates todo persistence operations."""

    def __init__(self, storage: Storage):
        self.storage = storage

    def list_projects(self) -> List[str]:
        return self.storage.list_projects()

    def load_project(self, project_name: str) -> Tuple[Project, List[Todo]]:
        """Load a project and its todos.

        Raises:
            StorageError: If the project file cannot be read or parsed.
        """
        project, todos = self.storage.load_project(project_name)
        if project is None:
            raise StorageError(f"Failed to load project '{project_name}'")
        return project, todos

    def save_project(self, project: Project, todos: List[Todo]) -> bool:
        return self.storage.save_project(project, todos)

    def next_todo_id(self) -> int:
        """Return the next globally unique todo ID across all projects."""
        return self.storage.get_next_todo_id()

    def add_todo(self, project_name: str, todo: Todo) -> bool:
        project, todos = self.load_project(project_name)
        todos.append(todo)
        return self.storage.save_project(project, todos)
