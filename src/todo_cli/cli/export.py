"""Export CLI command."""

import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import click
from rich.console import Console

from ..config import get_config
from ..core.errors import TodoCliError
from ..storage import Storage
from ..theme import get_themed_console
from ..validation import validate_project_name
from .error_handling import exit_with_error


def get_console() -> Console:
    """Get a themed console that reflects current configuration."""
    return get_themed_console()


def get_storage() -> Storage:
    """Get initialized storage instance."""
    return Storage(get_config())


@click.command()
@click.argument("format_type", type=click.Choice(["json", "csv", "markdown", "md", "html", "pdf", "ical", "yaml", "tsv"]))
@click.option("--output", "-o", help="Output file path (auto-generated if not specified)")
@click.option("--project", "-p", help="Export specific project only")
@click.option("--include-completed", is_flag=True, default=True, help="Include completed tasks")
@click.option("--no-completed", "exclude_completed", is_flag=True, help="Exclude completed tasks")
@click.option("--include-metadata", is_flag=True, default=True, help="Include extended metadata")
@click.option("--group-by-project", is_flag=True, help="Group tasks by project (Markdown only)")
@click.option("--open-after", is_flag=True, help="Open the exported file after creation")
def export(
    format_type: str,
    output: str | None,
    project: str | None,
    include_completed: bool,
    exclude_completed: bool,
    include_metadata: bool,
    group_by_project: bool,
    open_after: bool,
) -> None:
    """Export tasks to various formats."""
    try:
        from ..services import ExportFormat, ExportManager

        storage = get_storage()
        config = get_config()
        export_manager = ExportManager()

        if exclude_completed:
            include_completed = False

        format_map = {
            "json": ExportFormat.JSON,
            "csv": ExportFormat.CSV,
            "tsv": ExportFormat.TSV,
            "markdown": ExportFormat.MARKDOWN,
            "md": ExportFormat.MARKDOWN,
            "html": ExportFormat.HTML,
            "pdf": ExportFormat.PDF,
            "ical": ExportFormat.ICAL,
            "yaml": ExportFormat.YAML,
        }

        export_format = format_map[format_type]

        all_todos = []
        project_info = None

        if project:
            validated_project = validate_project_name(project)
            assert validated_project is not None
            project = validated_project
            projects: list[str] = [project]
            project_info, _ = storage.load_project(project)
        else:
            projects = storage.list_projects()
            if not projects:
                projects = [config.default_project]

        for project_name in projects:
            _, todos = storage.load_project(project_name)
            if todos:
                all_todos.extend(todos)

        if not all_todos:
            get_console().print("[yellow]No tasks found to export.[/yellow]")
            return

        if not output:
            project_name = project or "all_projects"
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            extension = export_manager.get_file_extension(export_format)
            output = f"todo_export_{project_name}_{timestamp}.{extension}"

        export_kwargs: dict[str, Any] = {
            "include_completed": include_completed,
            "include_metadata": include_metadata,
            "project_name": project_info.display_name if project_info and hasattr(project_info, "display_name") else (project or "Todo Export"),
        }

        if export_format == ExportFormat.MARKDOWN:
            export_kwargs["group_by_project"] = group_by_project

        get_console().print(f"[primary]🔄 Exporting {len(all_todos)} tasks to {format_type.upper()}...[/primary]")

        export_manager.export_todos(
            all_todos,
            export_format,
            output_path=output,
            **export_kwargs,
        )

        exported_todos = all_todos if include_completed else [todo for todo in all_todos if not todo.completed]
        stats = {
            "total": len(exported_todos),
            "completed": sum(1 for todo in exported_todos if todo.completed),
            "pending": sum(1 for todo in exported_todos if not todo.completed),
            "overdue": sum(1 for todo in exported_todos if todo.is_overdue() and not todo.completed),
        }

        get_console().print(f"\n[success]✅ Successfully exported to {output}[/success]")
        get_console().print(
            f"[muted]📊 Stats: {stats['total']} total, {stats['completed']} completed, "
            f"{stats['pending']} pending, {stats['overdue']} overdue[/muted]"
        )

        file_size = Path(output).stat().st_size
        if file_size > 1024 * 1024:
            size_str = f"{file_size / (1024 * 1024):.1f} MB"
        elif file_size > 1024:
            size_str = f"{file_size / 1024:.1f} KB"
        else:
            size_str = f"{file_size} bytes"

        get_console().print(f"[muted]📁 File size: {size_str}[/muted]")

        if open_after:
            try:
                import subprocess

                if sys.platform == "darwin":
                    subprocess.run(["open", output])
                elif sys.platform == "win32":
                    os.startfile(output)  # type: ignore[attr-defined]
                else:
                    subprocess.run(["xdg-open", output])
                get_console().print(f"[success]🚀 Opened {output}[/success]")
            except Exception as e:
                get_console().print(f"[warning]⚠️  Could not open file: {e}[/warning]")

    except ImportError as e:
        suggestion = None
        if "fpdf2" in str(e):
            suggestion = "Install lightweight PDF support with `pip install fpdf2`, or use html/markdown."
        exit_with_error(TodoCliError(str(e), suggestion=suggestion), console=get_console(), prefix="export failed")
    except TodoCliError as e:
        exit_with_error(e, console=get_console(), prefix="export failed")
    except Exception as e:
        exit_with_error(TodoCliError(str(e)), console=get_console(), prefix="export failed")
