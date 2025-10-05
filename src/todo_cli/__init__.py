"""Todo CLI - A powerful command-line todo application with advanced features."""

__version__ = "0.1.1"
__author__ = "Todo CLI Team"

from .domain import (
    Todo,
    TodoStatus,
    Priority,
    Project,
)

__all__ = ["Todo", "TodoStatus", "Priority", "Project", "__version__"]