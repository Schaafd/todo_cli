"""Tests for command compatibility while simplifying the CLI surface."""

from click.testing import CliRunner

from todo_cli.cli import tasks as task_cli
from todo_cli.cli.tasks import main


def _clear_recurring_tasks(monkeypatch):
    monkeypatch.setattr(task_cli.recurring_manager, "recurring_tasks", {})


def test_recurring_group_help_shows_subcommands(isolated_cli_config, monkeypatch):
    config_path, _, _ = isolated_cli_config
    _clear_recurring_tasks(monkeypatch)
    runner = CliRunner()

    result = runner.invoke(main, ["--config", str(config_path), "recurring", "--help"])

    assert result.exit_code == 0
    assert "Create and manage recurring tasks." in result.output
    assert "create" in result.output
    assert "list" in result.output
    assert "generate" in result.output
    assert "pause" in result.output
    assert "resume" in result.output
    assert "delete" in result.output


def test_recurring_group_list_command_executes(isolated_cli_config, monkeypatch):
    config_path, _, _ = isolated_cli_config
    _clear_recurring_tasks(monkeypatch)
    runner = CliRunner()

    result = runner.invoke(main, ["--config", str(config_path), "recurring", "list"])

    assert result.exit_code == 0
    assert "No recurring tasks found" in result.output


def test_legacy_recurring_list_alias_still_executes(isolated_cli_config, monkeypatch):
    config_path, _, _ = isolated_cli_config
    _clear_recurring_tasks(monkeypatch)
    runner = CliRunner()

    result = runner.invoke(main, ["--config", str(config_path), "recurring-list"])

    assert result.exit_code == 0
    assert "No recurring tasks found" in result.output


def test_legacy_recurring_alias_help_still_executes(isolated_cli_config, monkeypatch):
    config_path, _, _ = isolated_cli_config
    _clear_recurring_tasks(monkeypatch)
    runner = CliRunner()

    for command in (
        "recurring-list",
        "recurring-generate",
        "recurring-pause",
        "recurring-resume",
        "recurring-delete",
    ):
        result = runner.invoke(main, ["--config", str(config_path), command, "--help"])

        assert result.exit_code == 0
        assert command in result.output


def test_recurring_create_command_supports_preview(isolated_cli_config, monkeypatch):
    config_path, _, _ = isolated_cli_config
    _clear_recurring_tasks(monkeypatch)
    runner = CliRunner()

    result = runner.invoke(
        main,
        [
            "--config",
            str(config_path),
            "recurring",
            "create",
            "Team standup",
            "daily",
            "--preview",
        ],
    )

    assert result.exit_code == 0
    assert "Preview of recurring task" in result.output
    assert "Team standup" in result.output


def test_legacy_recurring_create_shorthand_supports_preview(isolated_cli_config, monkeypatch):
    config_path, _, _ = isolated_cli_config
    _clear_recurring_tasks(monkeypatch)
    runner = CliRunner()

    result = runner.invoke(
        main,
        [
            "--config",
            str(config_path),
            "recurring",
            "Team standup",
            "daily",
            "--preview",
        ],
    )

    assert result.exit_code == 0
    assert "Preview of recurring task" in result.output
    assert "Team standup" in result.output


def test_complete_alias_is_hidden_and_executes(isolated_cli_config):
    config_path, _, _ = isolated_cli_config
    runner = CliRunner()

    add_result = runner.invoke(
        main,
        ["--config", str(config_path), "quick", "Close the loop", "--project", "work"],
    )
    help_result = runner.invoke(main, ["--config", str(config_path), "--help"])
    complete_result = runner.invoke(
        main,
        ["--config", str(config_path), "complete", "1", "--project", "work"],
    )

    assert add_result.exit_code == 0
    assert help_result.exit_code == 0
    assert "complete  Alias for done." not in help_result.output
    assert complete_result.exit_code == 0
    assert "Completed task 1" in complete_result.output
