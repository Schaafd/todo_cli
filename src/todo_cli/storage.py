"""Storage layer for Todo CLI using markdown files with YAML frontmatter."""

import os
import re
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
import frontmatter
import yaml

from .todo import Todo, TodoStatus, Priority
from .project import Project
from .config import ConfigModel


# ID comment handling utilities
ID_COMMENT_RE = re.compile(r"<!--\s*id\s*:\s*(\d+)\s*-->")
TASK_LINE_RE = re.compile(r"^- \[( |/|x|-|!)\]\s+")


def extract_last_id_and_strip(text: str) -> Tuple[Optional[int], str]:
    """Extract the last ID comment and strip all ID comments from text.

    Args:
        text: Text that may contain ID comments

    Returns:
        Tuple of (last_id, cleaned_text) where:
        - last_id is the numeric value of the last ID comment, or None if no IDs
        - cleaned_text is the text with all ID comments removed and whitespace normalized
    """
    ids = ID_COMMENT_RE.findall(text)
    cleaned = ID_COMMENT_RE.sub("", text)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return (int(ids[-1]) if ids else None, cleaned)


class TodoMarkdownFormat:
    """Handles conversion between Todo objects and markdown format."""

    @staticmethod
    def to_markdown(todo: Todo) -> str:
        """Convert Todo to markdown format with inline metadata."""
        # Checkbox format based on status
        checkbox_map = {
            TodoStatus.PENDING: "- [ ]",
            TodoStatus.IN_PROGRESS: "- [/]",
            TodoStatus.COMPLETED: "- [x]",
            TodoStatus.CANCELLED: "- [-]",
            TodoStatus.BLOCKED: "- [!]",
        }

        checkbox = checkbox_map.get(todo.status, "- [ ]")

        # Build task line with all metadata
        task_line = f"{checkbox} {todo.text}"

        # Add inline metadata
        if todo.tags:
            task_line += f" {' '.join(['@' + tag for tag in todo.tags])}"

        if todo.context:
            task_line += f" {' '.join(['@' + ctx for ctx in todo.context])}"

        if todo.start_date:
            task_line += f" ^{todo.start_date.strftime('%Y-%m-%d')}"

        if todo.due_date:
            task_line += f" !{todo.due_date.strftime('%Y-%m-%d')}"

        if todo.priority != Priority.MEDIUM:
            task_line += f" ~{todo.priority.value}"

        if todo.effort:
            task_line += f" *{todo.effort}"

        if todo.assignees:
            task_line += f" {' '.join(['+' + assignee for assignee in todo.assignees])}"

        if todo.stakeholders:
            task_line += (
                f" {' '.join(['&' + stakeholder for stakeholder in todo.stakeholders])}"
            )

        if todo.recurrence:
            task_line += f" %{todo.recurrence}"

        if todo.pinned:
            task_line += " [PINNED]"

        if todo.location:
            task_line += f" @{todo.location}"

        if todo.waiting_for:
            task_line += f" (waiting: {', '.join(todo.waiting_for)})"

        # Ensure no existing ID comments before adding the current one (defensive coding)
        _, task_line = extract_last_id_and_strip(task_line)
        task_line += f" <!-- id:{todo.id} -->"

        # Add extended metadata as sub-items if present
        if todo.description or todo.notes or todo.url or todo.files:
            lines = [task_line]

            if todo.description:
                lines.extend([f"  - {line}" for line in todo.description.split("\n")])

            if todo.url:
                lines.append(f"  - URL: {todo.url}")

            if todo.files:
                lines.append(f"  - Files: {', '.join(todo.files)}")

            if todo.progress > 0:
                lines.append(f"  - Progress: {todo.progress:.0%}")

            if todo.time_estimate:
                lines.append(f"  - Estimate: {todo.time_estimate}m")

            if todo.time_spent > 0:
                lines.append(f"  - Time spent: {todo.time_spent}m")

            if todo.notes:
                for note in todo.notes:
                    lines.append(f"  - Note: {note}")

            return "\n".join(lines)

        return task_line

    @staticmethod
    def from_markdown(
        line: str, project: str = "inbox", line_id: Optional[int] = None
    ) -> Optional[Todo]:
        """Parse markdown line back to Todo object."""
        # Skip empty lines
        line = line.strip()
        if not line:
            return None

        # Only parse lines that match task checkbox pattern
        if not TASK_LINE_RE.match(line):
            return None

        # Extract checkbox status
        status_map = {
            "- [ ]": TodoStatus.PENDING,
            "- [/]": TodoStatus.IN_PROGRESS,
            "- [x]": TodoStatus.COMPLETED,
            "- [-]": TodoStatus.CANCELLED,
            "- [!]": TodoStatus.BLOCKED,
        }

        status = TodoStatus.PENDING
        for checkbox, todo_status in status_map.items():
            if line.startswith(checkbox):
                status = todo_status
                line = line[len(checkbox) :].strip()
                break

        # Extract and strip all ID comments (use last one as authoritative)
        parsed_id, line = extract_last_id_and_strip(line)
        todo_id = parsed_id or (line_id or 1)

        # Initialize metadata variables
        start_date = due_date = None
        priority = Priority.MEDIUM
        effort = ""
        recurrence = None
        pinned = False
        location = None
        waiting_for = []
        tags, context, assignees, stakeholders = [], [], [], []

        # Parse metadata with explicit assignments (no locals() usage)

        # Parse @tags and @contexts
        for m in re.finditer(r"@(\w+)", line):
            token = m.group(1)
            if token in {"home", "work", "phone", "office"}:
                context.append(token)
            else:
                tags.append(token)

        # Parse start date ^YYYY-MM-DD
        m = re.search(r"\^(\d{4}-\d{2}-\d{2})", line)
        if m:
            try:
                start_date = datetime.strptime(m.group(1), "%Y-%m-%d")
            except ValueError:
                pass  # Ignore invalid dates

        # Parse due date !YYYY-MM-DD
        m = re.search(r"!(\d{4}-\d{2}-\d{2})", line)
        if m:
            try:
                due_date = datetime.strptime(m.group(1), "%Y-%m-%d")
            except ValueError:
                pass  # Ignore invalid dates

        # Parse priority ~critical|high|medium|low
        m = re.search(r"~(critical|high|medium|low)", line)
        if m:
            try:
                priority = Priority(m.group(1))
            except ValueError:
                pass  # Keep default priority

        # Parse effort *small|medium|large|etc
        m = re.search(r"\*(\w+)", line)
        if m:
            effort = m.group(1)

        # Parse assignees +person
        for m in re.finditer(r"\+(\w+)", line):
            assignees.append(m.group(1))

        # Parse stakeholders &person
        for m in re.finditer(r"&(\w+)", line):
            stakeholders.append(m.group(1))

        # Parse recurrence %daily|weekly:friday|etc
        m = re.search(r"%(\w+:?\w*)", line)
        if m:
            recurrence = m.group(1)

        # Parse pinned flag [PINNED]
        if re.search(r"\[PINNED\]", line):
            pinned = True

        # Parse waiting for (waiting: thing1, thing2)
        m = re.search(r"\(waiting: ([^)]+)\)", line)
        if m:
            waiting_for = [w.strip() for w in m.group(1).split(",")]

        # Strip all metadata tokens from the text to get clean task text
        text = line
        metadata_patterns = [
            r"@\w+",  # @tags and @contexts
            r"\^\d{4}-\d{2}-\d{2}",  # ^start dates
            r"!\d{4}-\d{2}-\d{2}",  # !due dates
            r"~(critical|high|medium|low)",  # ~priority
            r"\*\w+",  # *effort
            r"\+\w+",  # +assignees
            r"&\w+",  # &stakeholders
            r"%\w+:?\w*",  # %recurrence
            r"\[PINNED\]",  # [PINNED] flag
            r"\(waiting: [^)]+\)",  # (waiting: ...) clause
        ]

        for pattern in metadata_patterns:
            text = re.sub(pattern, "", text)

        # Clean up the text (normalize whitespace)
        text = re.sub(r"\s+", " ", text).strip()

        # Create Todo object
        todo = Todo(
            id=todo_id,
            text=text,
            project=project,
            status=status,
            completed=(status == TodoStatus.COMPLETED),
            tags=tags,
            context=context,
            start_date=start_date,
            due_date=due_date,
            priority=priority,
            effort=effort,
            assignees=assignees,
            stakeholders=stakeholders,
            recurrence=recurrence,
            pinned=pinned,
            location=location,
            waiting_for=waiting_for,
        )

        return todo


class ProjectMarkdownFormat:
    """Handles conversion between Project objects and markdown files."""

    @staticmethod
    def to_markdown(project: Project, todos: List[Todo]) -> str:
        """Convert project and todos to markdown file with YAML frontmatter."""
        # Create frontmatter
        frontmatter_data = project.to_dict()

        # Create markdown content
        content_lines = []

        # Project title and description
        content_lines.append(f"# {project.display_name or project.name}")
        content_lines.append("")

        if project.description:
            content_lines.append(project.description)
            content_lines.append("")

        # Group todos by status and priority
        pinned_todos = [t for t in todos if t.pinned and not t.completed]
        active_todos = [t for t in todos if not t.completed and not t.pinned]
        completed_todos = [t for t in todos if t.completed]

        if pinned_todos:
            content_lines.append("## Pinned Tasks")
            content_lines.append("")
            for todo in pinned_todos:
                content_lines.append(TodoMarkdownFormat.to_markdown(todo))
            content_lines.append("")

        if active_todos:
            content_lines.append("## Active Tasks")
            content_lines.append("")
            # Sort by priority then due date
            priority_order = {
                Priority.CRITICAL: 0,
                Priority.HIGH: 1,
                Priority.MEDIUM: 2,
                Priority.LOW: 3,
            }
            active_todos.sort(
                key=lambda t: (
                    priority_order.get(t.priority, 2),
                    t.due_date or datetime.max,
                )
            )

            for todo in active_todos:
                content_lines.append(TodoMarkdownFormat.to_markdown(todo))
            content_lines.append("")

        if completed_todos:
            content_lines.append("## Completed Tasks")
            content_lines.append("")
            for todo in sorted(
                completed_todos,
                key=lambda t: t.completed_date or datetime.min,
                reverse=True,
            ):
                content_lines.append(TodoMarkdownFormat.to_markdown(todo))

        # Combine frontmatter and content
        content = "\n".join(content_lines)

        # Create frontmatter post
        post = frontmatter.Post(content, **frontmatter_data)

        return frontmatter.dumps(post)

    @staticmethod
    def from_markdown(content: str) -> Tuple[Project, List[Todo]]:
        """Parse markdown file back to Project and Todo objects."""
        # Parse frontmatter
        post = frontmatter.loads(content)

        # Create Project from frontmatter
        project_data = post.metadata
        project = Project.from_dict(project_data)

        # Parse todos from content
        todos = []
        lines = post.content.split("\n")
        todo_id_counter = 1

        for line in lines:
            todo = TodoMarkdownFormat.from_markdown(line, project.name, todo_id_counter)
            if todo:
                todos.append(todo)
                todo_id_counter = max(todo_id_counter, todo.id) + 1

        return project, todos


class Storage:
    """File-based storage for Todo CLI using markdown files."""

    def __init__(self, config: ConfigModel):
        self.config = config
        self._ensure_directories()

    def _ensure_directories(self):
        """Ensure necessary directories exist."""
        Path(self.config.data_dir).mkdir(parents=True, exist_ok=True)
        Path(self.config.data_dir, "projects").mkdir(parents=True, exist_ok=True)
        Path(self.config.backup_dir).mkdir(parents=True, exist_ok=True)

    def load_project(self, project_name: str) -> Tuple[Optional[Project], List[Todo]]:
        """Load a project and its todos from markdown file."""
        project_path = self.config.get_project_path(project_name)

        if not project_path.exists():
            # Create default project
            project = Project(name=project_name)
            return project, []

        try:
            with open(project_path, "r", encoding="utf-8") as f:
                content = f.read()

            return ProjectMarkdownFormat.from_markdown(content)

        except Exception as e:
            print(f"Error loading project {project_name}: {e}")
            return None, []

    def save_project(self, project: Project, todos: List[Todo]) -> bool:
        """Save a project and its todos to markdown file."""
        project_path = self.config.get_project_path(project.name)

        try:
            # Safety check: detect duplicate IDs before saving
            ids = [t.id for t in todos]
            if len(ids) != len(set(ids)):
                raise ValueError(
                    f"Duplicate todo IDs detected in project '{project.name}': {ids}"
                )

            # Update project stats
            project.update_stats(todos)

            # Generate markdown content
            content = ProjectMarkdownFormat.to_markdown(project, todos)

            # Write to file
            project_path.parent.mkdir(parents=True, exist_ok=True)
            with open(project_path, "w", encoding="utf-8") as f:
                f.write(content)

            return True

        except Exception as e:
            print(f"Error saving project {project.name}: {e}")
            return False

    def list_projects(self) -> List[str]:
        """List all available projects."""
        projects_dir = Path(self.config.data_dir) / "projects"
        if not projects_dir.exists():
            return []

        project_files = projects_dir.glob("*.md")
        return [f.stem for f in project_files]

    def delete_project(self, project_name: str) -> bool:
        """Delete a project file."""
        project_path = self.config.get_project_path(project_name)

        try:
            if project_path.exists():
                project_path.unlink()
                return True
            return False
        except Exception as e:
            print(f"Error deleting project {project_name}: {e}")
            return False

    def backup_project(
        self, project_name: str, backup_path: Optional[Path] = None
    ) -> bool:
        """Create a backup of a project file."""
        project_path = self.config.get_project_path(project_name)

        if not project_path.exists():
            return False

        if backup_path is None:
            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            backup_dir = self.config.get_backup_path(timestamp)
            backup_dir.mkdir(parents=True, exist_ok=True)
            backup_path = backup_dir / f"{project_name}.md"

        try:
            import shutil

            shutil.copy2(project_path, backup_path)
            return True
        except Exception as e:
            print(f"Error backing up project {project_name}: {e}")
            return False

    def get_next_todo_id(self, project_name: str) -> int:
        """Get the next available todo ID for a project."""
        _, todos = self.load_project(project_name)
        if not todos:
            return 1

        max_id = max(todo.id for todo in todos)
        return max_id + 1
    
    def get_all_projects(self) -> List[str]:
        """Get all project names (alias for list_projects)."""
        return self.list_projects()


# Global storage instance
_storage_instance: Optional[Storage] = None


def get_storage() -> Storage:
    """Get the global storage instance.
    
    Returns:
        Storage instance initialized with current config
    """
    global _storage_instance
    
    if _storage_instance is None:
        from .config import get_config
        config = get_config()
        _storage_instance = Storage(config)
    
    return _storage_instance


def reset_storage() -> None:
    """Reset the global storage instance (useful for testing)."""
    global _storage_instance
    _storage_instance = None
