"""Tests for root CLI help organization."""

from click.testing import CliRunner

from todo_cli.cli.tasks import main


def test_root_help_shows_common_commands_before_categories(isolated_cli_config):
    config_path, _, _ = isolated_cli_config
    runner = CliRunner()

    result = runner.invoke(main, ["--config", str(config_path), "--help"])

    assert result.exit_code == 0
    output = result.output
    assert "Common commands:" in output
    assert "Core:" in output
    assert "Integrations:" in output
    assert output.index("Common commands:") < output.index("Core:")
    assert output.index("Core:") < output.index("Integrations:")
    assert 'todo add "Review PR @work due tomorrow"' in output


def test_root_help_hides_flat_recurring_compatibility_commands(isolated_cli_config):
    config_path, _, _ = isolated_cli_config
    runner = CliRunner()

    result = runner.invoke(main, ["--config", str(config_path), "--help"])

    assert result.exit_code == 0
    assert "recurring-list" not in result.output
    assert "recurring-generate" not in result.output
    assert "recurring-pause" not in result.output
    assert "recurring-resume" not in result.output
    assert "recurring-delete" not in result.output


def test_hidden_recurring_compatibility_command_still_executes(isolated_cli_config):
    config_path, _, _ = isolated_cli_config
    runner = CliRunner()

    result = runner.invoke(main, ["--config", str(config_path), "recurring-list"])

    assert result.exit_code == 0
    assert "No recurring tasks found" in result.output


def test_unknown_command_suggests_close_match(isolated_cli_config):
    config_path, _, _ = isolated_cli_config
    runner = CliRunner()

    result = runner.invoke(main, ["--config", str(config_path), "lst"])

    assert result.exit_code != 0
    assert "No such command 'lst'." in result.output
    assert "Did you mean 'list'?" in result.output
