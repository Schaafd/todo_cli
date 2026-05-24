"""Input validation helpers shared across CLI, application, and storage code."""

import re
from typing import Iterable, Optional

from .core.errors import ValidationError


MAX_TASK_TEXT_LENGTH = 500
TOKEN_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")
CONTROL_CHARS = re.compile(r"[\x00-\x1f\x7f]")


def validate_task_text(text: str, *, field_name: str = "task text") -> str:
    """Validate user-facing task text and return the stripped value."""
    stripped = (text or "").strip()
    if not stripped:
        raise ValidationError(
            f"{field_name.capitalize()} cannot be empty.",
            suggestion="Add a short task description.",
        )
    if len(stripped) > MAX_TASK_TEXT_LENGTH:
        raise ValidationError(
            f"{field_name.capitalize()} is too long ({len(stripped)} characters). Maximum is {MAX_TASK_TEXT_LENGTH}.",
            suggestion="Keep the task title short and put details in notes or description.",
        )
    return stripped


def validate_project_name(project_name: Optional[str], *, field_name: str = "project") -> Optional[str]:
    """Validate a project name before it is used as a storage path segment."""
    if project_name is None:
        return None

    name = project_name.strip()
    if not name:
        raise ValidationError(
            f"{field_name.capitalize()} name cannot be empty.",
            suggestion="Use letters, numbers, underscores, or hyphens.",
        )
    if name in {".", ".."} or "/" in name or "\\" in name or CONTROL_CHARS.search(name):
        raise ValidationError(
            f"Invalid {field_name} name '{project_name}'.",
            suggestion="Use a single project name, not a path.",
        )
    return name


def validate_name_token(token: str, *, field_name: str) -> str:
    """Validate tag/context-style tokens."""
    value = (token or "").strip()
    if not value:
        raise ValidationError(
            f"{field_name.capitalize()} cannot be empty.",
            suggestion="Use letters, numbers, underscores, or hyphens.",
        )
    if not TOKEN_PATTERN.fullmatch(value):
        raise ValidationError(
            f"Invalid {field_name} '{token}'.",
            suggestion="Use only letters, numbers, underscores, and hyphens.",
        )
    return value


def validate_name_tokens(tokens: Iterable[str], *, field_name: str) -> list[str]:
    """Validate and normalize a list of tag/context-style tokens."""
    return [validate_name_token(token, field_name=field_name) for token in tokens]


def validate_todo_id(todo_id: int, *, field_name: str = "todo ID") -> int:
    """Validate a positive todo ID."""
    if todo_id <= 0:
        raise ValidationError(
            f"{field_name} must be a positive integer.",
            suggestion="Run `todo list` to see available task IDs.",
        )
    return todo_id


def validate_parsed_task(parsed) -> None:
    """Validate parser output before preview or persistence."""
    parsed.text = validate_task_text(parsed.text)
    parsed.project = validate_project_name(parsed.project)
    parsed.tags = validate_name_tokens(parsed.tags, field_name="tag")
    parsed.context = validate_name_tokens(parsed.context, field_name="context")
