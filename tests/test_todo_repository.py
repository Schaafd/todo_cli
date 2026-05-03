"""Tests for repository abstraction over storage."""

from todo_cli.config import ConfigModel
from todo_cli.domain import Todo
from todo_cli.infrastructure.storage.repository import TodoRepository
from todo_cli.storage import Storage


def test_repository_next_id_and_add(tmp_path):
    config = ConfigModel(data_dir=str(tmp_path / "data"), backup_dir=str(tmp_path / "backups"))
    storage = Storage(config)
    repo = TodoRepository(storage)

    assert repo.next_todo_id("inbox") == 1

    first = Todo(id=1, text="first", project="inbox")
    assert repo.add_todo("inbox", first)
    assert repo.next_todo_id("inbox") == 2

    second = Todo(id=2, text="second", project="inbox")
    assert repo.add_todo("inbox", second)

    _, todos = repo.load_project("inbox")
    assert [t.id for t in todos] == [1, 2]
