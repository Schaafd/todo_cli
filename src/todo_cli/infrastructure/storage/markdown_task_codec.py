"""Markdown codec for Todo lines with inline metadata and ID comments."""

from typing import Optional, Tuple

from ...storage import TodoMarkdownFormat
from ...domain import Todo


def todo_to_markdown(todo: Todo) -> str:
    """Serialize Todo to markdown task representation."""
    return TodoMarkdownFormat.to_markdown(todo)


def todo_from_markdown(line: str, project: str = "inbox", line_id: Optional[int] = None) -> Optional[Todo]:
    """Deserialize markdown task line into Todo."""
    return TodoMarkdownFormat.from_markdown(line, project=project, line_id=line_id)


def strip_id_comments(text: str) -> Tuple[Optional[int], str]:
    """Extract last embedded ID comment and return cleaned text."""
    from ...storage import extract_last_id_and_strip

    return extract_last_id_and_strip(text)
