"""Tests for guided interactive add."""

from click.testing import CliRunner

from todo_cli.cli.tasks import main
from todo_cli.config import ConfigModel
from todo_cli.storage import Storage


def _storage(data_dir, backup_dir):
    return Storage(ConfigModel(data_dir=str(data_dir), backup_dir=str(backup_dir)))


def test_add_without_text_or_interactive_fails_fast(isolated_cli_config):
    config_path, _, _ = isolated_cli_config
    runner = CliRunner()

    result = runner.invoke(main, ["--config", str(config_path), "add"])

    assert result.exit_code == 1
    assert "Task text is required" in result.output
    assert "todo add --interactive" in result.output


def test_interactive_add_saves_prompted_task(isolated_cli_config):
    config_path, data_dir, backup_dir = isolated_cli_config
    runner = CliRunner()

    result = runner.invoke(
        main,
        ["--config", str(config_path), "add", "--interactive"],
        input="\n".join(
            [
                "Draft roadmap",
                "work",
                "high",
                "2026-05-25",
                "planning,leadership",
                "office",
                "y",
            ]
        )
        + "\n",
    )

    _, todos = _storage(data_dir, backup_dir).load_project("work")
    assert result.exit_code == 0
    assert "Preview:" in result.output
    assert "Added:" in result.output
    assert len(todos) == 1
    assert todos[0].text == "Draft roadmap"
    assert todos[0].priority.value == "high"
    assert todos[0].tags == ["planning", "leadership"]
    assert todos[0].context == ["office"]
    assert todos[0].due_date.strftime("%Y-%m-%d") == "2026-05-25"


def test_interactive_add_cancel_does_not_save(isolated_cli_config):
    config_path, data_dir, backup_dir = isolated_cli_config
    runner = CliRunner()

    result = runner.invoke(
        main,
        ["--config", str(config_path), "add", "--interactive"],
        input="\n".join(
            [
                "Do not save",
                "inbox",
                "medium",
                "",
                "",
                "",
                "n",
            ]
        )
        + "\n",
    )

    _, todos = _storage(data_dir, backup_dir).load_project("inbox")
    assert result.exit_code == 0
    assert "Task not saved" in result.output
    assert todos == []
