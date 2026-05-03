"""Tests for repository abstraction over storage."""

from todo_cli.config import ConfigModel
from todo_cli.core.errors import StorageError
from todo_cli.domain import Todo
from todo_cli.infrastructure.storage.repository import TodoRepository
from todo_cli.storage import Storage
import pytest


def test_repository_next_id_and_add(tmp_path):
    config = ConfigModel(data_dir=str(tmp_path / "data"), backup_dir=str(tmp_path / "backups"))
    storage = Storage(config)
    repo = TodoRepository(storage)

    # IDs are allocated globally across all projects.
    assert repo.next_todo_id() == 1

    first = Todo(id=1, text="first", project="inbox")
    assert repo.add_todo("inbox", first)

    # After adding the first inbox todo, the next global ID must advance.
    assert repo.next_todo_id() == 2

    second = Todo(id=2, text="second", project="work")
    assert repo.add_todo("work", second)

    _, inbox_todos = repo.load_project("inbox")
    assert [t.id for t in inbox_todos] == [1]

    _, work_todos = repo.load_project("work")
    assert [t.id for t in work_todos] == [2]


def test_load_project_raises_storage_error_on_corrupt_file(tmp_path):
    """load_project must raise StorageError rather than returning None."""
    config = ConfigModel(data_dir=str(tmp_path / "data"), backup_dir=str(tmp_path / "backups"))
    storage = Storage(config)
    repo = TodoRepository(storage)

    # Write a corrupt (non-parseable) markdown file for the project.
    projects_dir = tmp_path / "data" / "projects"
    projects_dir.mkdir(parents=True, exist_ok=True)
    corrupt_file = projects_dir / "corrupt.md"
    corrupt_file.write_text("<<< this is not valid project markdown >>>")

    with pytest.raises(StorageError):
        repo.load_project("corrupt")
