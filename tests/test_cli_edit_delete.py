"""Tests for editing and deleting tasks from the CLI."""

from click.testing import CliRunner

from todo_cli.cli.tasks import main
from todo_cli.config import ConfigModel
from todo_cli.domain import Priority
from todo_cli.storage import Storage


def _storage(data_dir, backup_dir):
    return Storage(ConfigModel(data_dir=str(data_dir), backup_dir=str(backup_dir)))


def test_edit_updates_text_priority_and_due_date(isolated_cli_config):
    config_path, data_dir, backup_dir = isolated_cli_config
    runner = CliRunner()

    add_result = runner.invoke(
        main,
        ["--config", str(config_path), "quick", "Draft proposal", "--project", "work"],
    )
    edit_result = runner.invoke(
        main,
        [
            "--config",
            str(config_path),
            "edit",
            "1",
            "--text",
            "Draft revised proposal",
            "--priority",
            "high",
            "--due",
            "2026-05-25",
        ],
    )

    _, todos = _storage(data_dir, backup_dir).load_project("work")
    assert add_result.exit_code == 0
    assert edit_result.exit_code == 0
    assert "Updated task 1" in edit_result.output
    assert todos[0].text == "Draft revised proposal"
    assert todos[0].priority == Priority.HIGH
    assert todos[0].due_date.strftime("%Y-%m-%d") == "2026-05-25"


def test_edit_moves_task_to_project(isolated_cli_config):
    config_path, data_dir, backup_dir = isolated_cli_config
    runner = CliRunner()

    add_result = runner.invoke(
        main,
        ["--config", str(config_path), "quick", "Move me", "--project", "inbox"],
    )
    edit_result = runner.invoke(
        main,
        ["--config", str(config_path), "edit", "1", "--project", "work"],
    )

    storage = _storage(data_dir, backup_dir)
    _, inbox_todos = storage.load_project("inbox")
    _, work_todos = storage.load_project("work")
    assert add_result.exit_code == 0
    assert edit_result.exit_code == 0
    assert inbox_todos == []
    assert len(work_todos) == 1
    assert work_todos[0].project == "work"
    assert work_todos[0].text == "Move me"


def test_edit_without_setters_is_rejected(isolated_cli_config):
    config_path, _, _ = isolated_cli_config
    runner = CliRunner()

    result = runner.invoke(main, ["--config", str(config_path), "edit", "1"])

    assert result.exit_code == 1
    assert "No edits specified" in result.output
    assert "Use --text, --priority, --due, or --project" in result.output


def test_delete_cancel_keeps_task(isolated_cli_config):
    config_path, data_dir, backup_dir = isolated_cli_config
    runner = CliRunner()

    runner.invoke(main, ["--config", str(config_path), "quick", "Keep me"])
    result = runner.invoke(main, ["--config", str(config_path), "delete", "1"], input="n\n")

    _, todos = _storage(data_dir, backup_dir).load_project("inbox")
    assert result.exit_code == 0
    assert "Deletion cancelled" in result.output
    assert len(todos) == 1


def test_delete_yes_removes_task_and_creates_backup(isolated_cli_config):
    config_path, data_dir, backup_dir = isolated_cli_config
    runner = CliRunner()

    add_result = runner.invoke(main, ["--config", str(config_path), "quick", "Remove me"])
    delete_result = runner.invoke(main, ["--config", str(config_path), "delete", "1", "--yes"])

    _, todos = _storage(data_dir, backup_dir).load_project("inbox")
    backup_files = list(backup_dir.glob("*/inbox.md"))
    assert add_result.exit_code == 0
    assert delete_result.exit_code == 0
    assert "Deleted task 1" in delete_result.output
    assert todos == []
    assert backup_files
    assert "Remove me" in backup_files[0].read_text(encoding="utf-8")
