"""Tests for shell completion script generation."""

from click.testing import CliRunner

from todo_cli.cli.tasks import main


def test_completion_show_generates_zsh_script(isolated_cli_config):
    config_path, _, _ = isolated_cli_config
    runner = CliRunner()

    result = runner.invoke(
        main,
        ["--config", str(config_path), "completion", "show", "--shell", "zsh"],
    )

    assert result.exit_code == 0
    assert result.output.startswith("#compdef todo")
    assert "_TODO_COMPLETE=zsh_complete todo" in result.output
    assert "Loaded configuration" not in result.output


def test_completion_show_generates_fish_script(isolated_cli_config):
    config_path, _, _ = isolated_cli_config
    runner = CliRunner()

    result = runner.invoke(
        main,
        ["--config", str(config_path), "completion", "show", "--shell", "fish"],
    )

    assert result.exit_code == 0
    assert result.output.startswith("function _todo_completion;")
    assert "_TODO_COMPLETE=fish_complete" in result.output
    assert "Loaded configuration" not in result.output


def test_completion_show_generates_bash_script(isolated_cli_config):
    config_path, _, _ = isolated_cli_config
    runner = CliRunner()

    result = runner.invoke(
        main,
        ["--config", str(config_path), "completion", "show", "--shell", "bash"],
    )

    assert result.exit_code == 0
    assert "_todo_completion()" in result.output
    assert "_TODO_COMPLETE=bash_complete" in result.output
    assert "Loaded configuration" not in result.output


def test_completion_show_rejects_unknown_shell(isolated_cli_config):
    config_path, _, _ = isolated_cli_config
    runner = CliRunner()

    result = runner.invoke(
        main,
        ["--config", str(config_path), "completion", "show", "--shell", "powershell"],
    )

    assert result.exit_code != 0
    assert "Invalid value for '--shell'" in result.output


def test_completion_install_writes_default_fish_file(isolated_cli_config):
    config_path, _, _ = isolated_cli_config
    runner = CliRunner()

    result = runner.invoke(
        main,
        ["--config", str(config_path), "completion", "install", "--shell", "fish"],
    )

    expected_path = config_path.parent / "home" / ".config" / "fish" / "completions" / "todo.fish"
    assert result.exit_code == 0
    assert expected_path.exists()
    assert expected_path.read_text(encoding="utf-8").startswith("function _todo_completion;")
    assert "Installed fish completion" in result.output
    assert "automatically" in result.output


def test_completion_install_is_idempotent(isolated_cli_config):
    config_path, _, _ = isolated_cli_config
    runner = CliRunner()

    first = runner.invoke(
        main,
        ["--config", str(config_path), "completion", "install", "--shell", "fish"],
    )
    second = runner.invoke(
        main,
        ["--config", str(config_path), "completion", "install", "--shell", "fish"],
    )

    assert first.exit_code == 0
    assert second.exit_code == 0
    assert "already up to date" in second.output


def test_completion_uninstall_removes_installed_file(isolated_cli_config):
    config_path, _, _ = isolated_cli_config
    runner = CliRunner()
    custom_path = config_path.parent / "completion" / "_todo"

    install = runner.invoke(
        main,
        [
            "--config",
            str(config_path),
            "completion",
            "install",
            "--shell",
            "zsh",
            "--path",
            str(custom_path),
        ],
    )
    assert install.exit_code == 0
    assert custom_path.exists()

    uninstall = runner.invoke(
        main,
        [
            "--config",
            str(config_path),
            "completion",
            "uninstall",
            "--shell",
            "zsh",
            "--path",
            str(custom_path),
        ],
    )

    assert custom_path.exists() is False
    assert uninstall.exit_code == 0
    assert "Removed zsh completion" in uninstall.output
