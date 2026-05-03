"""Tests for application-layer task command handlers."""

from todo_cli.application.task_commands import add_task_from_input
from todo_cli.config import ConfigModel
from todo_cli.storage import Storage


def test_add_task_from_input_persists_task(tmp_path):
    config = ConfigModel(data_dir=str(tmp_path / "todo_data"), backup_dir=str(tmp_path / "todo_backups"))
    storage = Storage(config)

    result = add_task_from_input(
        storage=storage,
        config=config,
        input_text="Write tests for application layer @dev ~high",
        project="inbox",
    )

    assert result.todo.id == 1
    assert result.todo.text.startswith("Write tests")

    _, todos = storage.load_project("inbox")
    assert len(todos) == 1
    assert todos[0].text == result.todo.text
