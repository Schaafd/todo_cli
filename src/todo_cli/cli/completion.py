"""Shell completion commands for the Todo CLI."""

import io
from contextlib import redirect_stdout
from pathlib import Path

import click
from click.shell_completion import shell_complete


SUPPORTED_SHELLS = ("bash", "zsh", "fish")


def create_completion_group(root_command: click.Command) -> click.Group:
    """Create completion commands bound to the root CLI command."""

    def completion_source(shell: str) -> str:
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            shell_complete(root_command, {}, "todo", "_TODO_COMPLETE", f"{shell}_source")
        return buffer.getvalue()

    def default_completion_path(shell: str) -> Path:
        home = Path.home()
        if shell == "fish":
            return home / ".config" / "fish" / "completions" / "todo.fish"
        if shell == "zsh":
            return home / ".todo" / "completions" / "zsh" / "_todo"
        return home / ".todo" / "completions" / "todo.bash"

    def write_completion_file(path: Path, source: str) -> bool:
        if path.exists() and path.read_text(encoding="utf-8") == source:
            return False

        path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = path.with_name(f".{path.name}.tmp")
        temp_path.write_text(source, encoding="utf-8")
        temp_path.replace(path)
        return True

    def activation_hint(shell: str, path: Path) -> str:
        display_path = str(path.expanduser())
        if shell == "fish":
            return "Fish will load this file automatically for new shells."
        if shell == "zsh":
            return f"Add this directory to fpath before compinit: {path.parent}"
        return f"Source this file from your shell startup: source {display_path}"

    @click.group()
    def completion():
        """Shell completion commands."""

    @completion.command("show")
    @click.option(
        "--shell",
        type=click.Choice(SUPPORTED_SHELLS),
        required=True,
        help="Shell to generate completion for.",
    )
    def completion_show(shell):
        """Print a shell completion script."""
        click.echo(completion_source(shell), nl=False)

    @completion.command("install")
    @click.option(
        "--shell",
        type=click.Choice(SUPPORTED_SHELLS),
        required=True,
        help="Shell to install completion for.",
    )
    @click.option(
        "--path",
        "install_path",
        type=click.Path(path_type=Path),
        help="Override the completion script path.",
    )
    def completion_install(shell, install_path):
        """Install a shell completion script."""
        path = install_path or default_completion_path(shell)
        changed = write_completion_file(path, completion_source(shell))

        if changed:
            click.echo(f"Installed {shell} completion to {path}")
        else:
            click.echo(f"{shell} completion already up to date at {path}")

        click.echo(activation_hint(shell, path))

    @completion.command("uninstall")
    @click.option(
        "--shell",
        type=click.Choice(SUPPORTED_SHELLS),
        required=True,
        help="Shell to uninstall completion for.",
    )
    @click.option(
        "--path",
        "install_path",
        type=click.Path(path_type=Path),
        help="Override the completion script path.",
    )
    def completion_uninstall(shell, install_path):
        """Remove an installed shell completion script."""
        path = install_path or default_completion_path(shell)
        if not path.exists():
            click.echo(f"No {shell} completion installed at {path}")
            return

        path.unlink()
        click.echo(f"Removed {shell} completion from {path}")

    return completion
