"""Tests for undoing recent CLI task operations."""

from click.testing import CliRunner

from todo_cli.cli.tasks import main
from todo_cli.config import ConfigModel
from todo_cli.storage import Storage


def _storage(data_dir, backup_dir):
    return Storage(ConfigModel(data_dir=str(data_dir), backup_dir=str(backup_dir)))


def test_undo_empty_history_is_expected_error(isolated_cli_config):
    config_path, _, _ = isolated_cli_config
    runner = CliRunner()

    result = runner.invoke(main, ["--config", str(config_path), "undo"])

    assert result.exit_code == 1
    assert "Nothing to undo" in result.output
    assert "Traceback" not in result.output


def test_undo_last_add_removes_task(isolated_cli_config):
    config_path, data_dir, backup_dir = isolated_cli_config
    runner = CliRunner()

    add_result = runner.invoke(main, ["--config", str(config_path), "quick", "Undo me"])
    undo_result = runner.invoke(main, ["--config", str(config_path), "undo"])

    _, todos = _storage(data_dir, backup_dir).load_project("inbox")
    assert add_result.exit_code == 0
    assert undo_result.exit_code == 0
    assert "Removed added task 1" in undo_result.output
    assert todos == []


def test_undo_done_reopens_task(isolated_cli_config):
    config_path, data_dir, backup_dir = isolated_cli_config
    runner = CliRunner()

    runner.invoke(main, ["--config", str(config_path), "quick", "Finish me"])
    done_result = runner.invoke(main, ["--config", str(config_path), "done", "1"])
    undo_result = runner.invoke(main, ["--config", str(config_path), "undo"])

    _, todos = _storage(data_dir, backup_dir).load_project("inbox")
    assert done_result.exit_code == 0
    assert undo_result.exit_code == 0
    assert "Reopened completed task 1" in undo_result.output
    assert todos[0].completed is False


def test_undo_edit_restores_previous_state_and_project(isolated_cli_config):
    config_path, data_dir, backup_dir = isolated_cli_config
    runner = CliRunner()

    runner.invoke(main, ["--config", str(config_path), "quick", "Original", "--project", "inbox"])
    edit_result = runner.invoke(
        main,
        [
            "--config",
            str(config_path),
            "edit",
            "1",
            "--text",
            "Changed",
            "--priority",
            "high",
            "--project",
            "work",
        ],
    )
    undo_result = runner.invoke(main, ["--config", str(config_path), "undo"])

    storage = _storage(data_dir, backup_dir)
    _, inbox_todos = storage.load_project("inbox")
    _, work_todos = storage.load_project("work")
    assert edit_result.exit_code == 0
    assert undo_result.exit_code == 0
    assert "Restored edited task 1" in undo_result.output
    assert len(inbox_todos) == 1
    assert inbox_todos[0].text == "Original"
    assert inbox_todos[0].priority.value == "medium"
    assert work_todos == []


def test_undo_delete_restores_deleted_task(isolated_cli_config):
    config_path, data_dir, backup_dir = isolated_cli_config
    runner = CliRunner()

    runner.invoke(main, ["--config", str(config_path), "quick", "Restore me"])
    delete_result = runner.invoke(main, ["--config", str(config_path), "delete", "1", "--yes"])
    undo_result = runner.invoke(main, ["--config", str(config_path), "undo"])

    _, todos = _storage(data_dir, backup_dir).load_project("inbox")
    assert delete_result.exit_code == 0
    assert undo_result.exit_code == 0
    assert "Restored deleted task 1" in undo_result.output
    assert len(todos) == 1
    assert todos[0].text == "Restore me"
