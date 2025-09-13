"""Todo CLI - A powerful command-line todo application with advanced features."""

__version__ = "0.1.0"
__author__ = "Todo CLI Team"

from .todo import Todo, TodoStatus, Priority
from .project import Project

__all__ = ["Todo", "TodoStatus", "Priority", "Project", "__version__"]