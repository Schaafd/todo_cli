"""Smoke tests for the main Click CLI."""

from click.testing import CliRunner

from todo_cli.cli.tasks import main
from todo_cli.config import ConfigModel
from todo_cli.storage import Storage


def test_root_help_runs_with_isolated_config(isolated_cli_config):
    config_path, _, _ = isolated_cli_config
    runner = CliRunner()

    result = runner.invoke(main, ["--config", str(config_path), "--help"])

    assert result.exit_code == 0
    assert "Usage: main [OPTIONS] COMMAND [ARGS]" in result.output
    assert "add" in result.output
    assert "list" in result.output


def test_add_dry_run_does_not_persist_task(isolated_cli_config):
    config_path, data_dir, _ = isolated_cli_config
    runner = CliRunner()

    result = runner.invoke(
        main,
        ["--config", str(config_path), "add", "Review storage hardening ~high", "--dry-run"],
    )

    assert result.exit_code == 0
    assert "DRY RUN" in result.output
    assert not (data_dir / "projects" / "inbox.md").exists()


def test_list_runs_without_real_user_data(isolated_cli_config):
    config_path, _, _ = isolated_cli_config
    runner = CliRunner()

    result = runner.invoke(main, ["--config", str(config_path), "list"])

    assert result.exit_code == 0
    assert "No todos found" in result.output


def test_bulk_complete_persists_changes(isolated_cli_config):
    config_path, data_dir, backup_dir = isolated_cli_config
    runner = CliRunner()

    add_result = runner.invoke(main, ["--config", str(config_path), "add", "Task to finish"])
    assert add_result.exit_code == 0

    bulk_result = runner.invoke(main, ["--config", str(config_path), "bulk", "complete", "1", "--confirm"])
    assert bulk_result.exit_code == 0
    assert "Successfully completed 1 todos" in bulk_result.output

    storage = Storage(ConfigModel(data_dir=str(data_dir), backup_dir=str(backup_dir)))
    _, todos = storage.load_project("inbox")
    assert len(todos) == 1
    assert todos[0].completed is True
