"""Centralized application error taxonomy."""

from typing import Optional


class TodoCliError(Exception):
    """Base error for all Todo CLI domain/application failures."""

    def __init__(self, message: str, *, suggestion: Optional[str] = None):
        super().__init__(message)
        self.message = message
        self.suggestion = suggestion


class ValidationError(TodoCliError):
    """Raised when input or entity validation fails."""


class ConfigurationError(TodoCliError):
    """Raised when configuration is invalid or unavailable."""


class StorageError(TodoCliError):
    """Raised for persistence and serialization errors."""


class TaskNotFoundError(TodoCliError):
    """Raised when a requested task ID cannot be found."""

    def __init__(self, todo_id: int, *, project: Optional[str] = None):
        scope = f" in project '{project}'" if project else ""
        super().__init__(
            f"Task {todo_id} not found{scope}.",
            suggestion="Run `todo list` to see available tasks.",
        )
        self.todo_id = todo_id
        self.project = project


class ProjectNotFoundError(TodoCliError):
    """Raised when a requested project cannot be found."""

    def __init__(self, project: str):
        super().__init__(
            f"Project '{project}' not found.",
            suggestion="Run `todo projects` to see available projects.",
        )
        self.project = project


class ProviderError(TodoCliError):
    """Raised for external provider/network failures."""
