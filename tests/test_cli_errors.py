"""Tests for shared CLI error rendering on core commands."""

from click.testing import CliRunner

from todo_cli.cli.tasks import main


def test_done_missing_task_uses_expected_error_renderer(isolated_cli_config):
    config_path, _, _ = isolated_cli_config
    runner = CliRunner()

    result = runner.invoke(main, ["--config", str(config_path), "done", "42"])

    assert result.exit_code == 1
    assert "Error: could not complete task: Task 42 not found." in result.output
    assert "Try: Run `todo list` to see available tasks." in result.output
    assert "Traceback" not in result.output


def test_debug_flag_shows_stack_trace_for_expected_error(isolated_cli_config):
    config_path, _, _ = isolated_cli_config
    runner = CliRunner()

    result = runner.invoke(main, ["--config", str(config_path), "--debug", "done", "42"])

    assert result.exit_code == 1
    assert "Stack trace:" in result.output
    assert "TaskNotFoundError" in result.output


def test_list_corrupted_project_uses_expected_error_renderer(isolated_cli_config):
    config_path, data_dir, _ = isolated_cli_config
    project_path = data_dir / "projects" / "broken.md"
    project_path.write_text("---\nname: [unterminated\n---\n# Broken\n", encoding="utf-8")
    runner = CliRunner()

    result = runner.invoke(main, ["--config", str(config_path), "list"])

    assert result.exit_code == 1
    assert "Error: could not list tasks: Could not load project 'broken'" in result.output
    assert "Try: Check the project markdown file or restore from backup." in result.output
    assert "Traceback" not in result.output


def test_projects_corrupted_project_uses_expected_error_renderer(isolated_cli_config):
    config_path, data_dir, _ = isolated_cli_config
    project_path = data_dir / "projects" / "broken.md"
    project_path.write_text("---\nname: [unterminated\n---\n# Broken\n", encoding="utf-8")
    runner = CliRunner()

    result = runner.invoke(main, ["--config", str(config_path), "projects"])

    assert result.exit_code == 1
    assert "Error: could not list projects: Could not load project 'broken'" in result.output


def test_export_corrupted_project_uses_expected_error_renderer(isolated_cli_config, tmp_path):
    config_path, data_dir, _ = isolated_cli_config
    project_path = data_dir / "projects" / "broken.md"
    project_path.write_text("---\nname: [unterminated\n---\n# Broken\n", encoding="utf-8")
    runner = CliRunner()

    result = runner.invoke(
        main,
        ["--config", str(config_path), "export", "json", "--output", str(tmp_path / "out.json")],
    )

    assert result.exit_code == 1
    assert "Error: export failed: Could not load project 'broken'" in result.output


def test_add_dry_run_invalid_priority_uses_same_validation_path(isolated_cli_config):
    config_path, _, _ = isolated_cli_config
    runner = CliRunner()

    result = runner.invoke(main, ["--config", str(config_path), "add", "Broken ~urgent", "--dry-run"])

    assert result.exit_code == 1
    assert "Invalid priority: urgent" in result.output


def test_quick_invalid_tag_is_rejected(isolated_cli_config):
    config_path, _, _ = isolated_cli_config
    runner = CliRunner()

    result = runner.invoke(main, ["--config", str(config_path), "quick", "Task", "--tag", "needs review"])

    assert result.exit_code == 1
    assert "Invalid tag 'needs review'" in result.output


def test_done_zero_id_is_rejected(isolated_cli_config):
    config_path, _, _ = isolated_cli_config
    runner = CliRunner()

    result = runner.invoke(main, ["--config", str(config_path), "done", "0"])

    assert result.exit_code == 1
    assert "todo ID must be a positive integer" in result.output


def test_list_invalid_project_is_rejected_before_storage_path_use(isolated_cli_config):
    config_path, _, _ = isolated_cli_config
    runner = CliRunner()

    result = runner.invoke(main, ["--config", str(config_path), "list", "--project", "../outside"])

    assert result.exit_code == 1
    assert "Invalid project name '../outside'" in result.output
