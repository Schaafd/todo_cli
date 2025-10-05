"""Storage layer for Todo CLI using markdown files with YAML frontmatter."""

import os
import re
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timezone
import frontmatter
import yaml

from .domain import Todo, TodoStatus, Priority, Project
from .config import ConfigModel
from .utils.datetime import now_utc, max_utc, min_utc, ensure_aware


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
                start_date = datetime.strptime(m.group(1), "%Y-%m-%d").replace(tzinfo=timezone.utc)
            except ValueError:
                pass  # Ignore invalid dates

        # Parse due date !YYYY-MM-DD
        m = re.search(r"!(\d{4}-\d{2}-\d{2})", line)
        if m:
            try:
                due_date = datetime.strptime(m.group(1), "%Y-%m-%d").replace(tzinfo=timezone.utc)
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
            # Normalize datetimes to avoid naive vs aware comparison errors
            active_todos.sort(
                key=lambda t: (
                    priority_order.get(t.priority, 2),
                    ensure_aware(t.due_date) if getattr(t, 'due_date', None) else max_utc(),
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
                key=lambda t: ensure_aware(t.completed_date) if getattr(t, 'completed_date', None) else min_utc(),
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
            try:
                project.update_stats(todos)
            except Exception as stats_error:
                print(f"Error in update_stats for project {project.name}: {stats_error}")
                print(f"Todo details:")
                for i, todo in enumerate(todos[:3]):
                    print(f"  Todo {i}: created={getattr(todo, 'created', None)} (tz={getattr(todo.created, 'tzinfo', 'N/A') if hasattr(todo, 'created') and todo.created else 'N/A'})")
                    print(f"  Todo {i}: modified={getattr(todo, 'modified', None)} (tz={getattr(todo.modified, 'tzinfo', 'N/A') if hasattr(todo, 'modified') and todo.modified else 'N/A'})")
                    print(f"  Todo {i}: due_date={getattr(todo, 'due_date', None)} (tz={getattr(todo.due_date, 'tzinfo', 'N/A') if hasattr(todo, 'due_date') and todo.due_date else 'N/A'})")
                print(f"Project details: created={project.created} (tz={project.created.tzinfo if project.created else 'N/A'})")
                raise stats_error

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
            timestamp = now_utc().strftime("%Y-%m-%d_%H-%M-%S")
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

    def get_next_todo_id(self, project_name: Optional[str] = None) -> int:
        """Get the next available todo ID globally across all projects.
        
        Args:
            project_name: Optional project name (kept for backward compatibility)
            
        Returns:
            Next unique ID across all projects
        """
        all_todos = self.get_all_todos()
        if not all_todos:
            return 1

        max_id = max(todo.id for todo in all_todos)
        return max_id + 1
    
    def get_all_projects(self) -> List[str]:
        """Get all project names (alias for list_projects)."""
        return self.list_projects()
    
    def get_all_todos(self) -> List[Todo]:
        """Get all todos from all projects.
        
        Returns:
            List of all todos across all projects
        """
        all_todos = []
        projects = self.list_projects()
        
        # Include default project if no projects exist
        if not projects:
            projects = [self.config.default_project]
        
        for project_name in projects:
            _, todos = self.load_project(project_name)
            if todos:
                all_todos.extend(todos)
        
        return all_todos
    
    def get_todo(self, todo_id: int, project: Optional[str] = None) -> Optional[Todo]:
        """Get a specific todo by ID.
        
        Args:
            todo_id: ID of the todo to find
            project: Optional project name to search in (searches all if None)
            
        Returns:
            Todo object if found, None otherwise
        """
        if project:
            # Search in specific project
            _, todos = self.load_project(project)
            for todo in todos:
                if todo.id == todo_id:
                    return todo
        else:
            # Search all projects
            for todo in self.get_all_todos():
                if todo.id == todo_id:
                    return todo
        return None
    
    def add_todo(self, todo: Todo) -> int:
        """Add a new todo to storage.
        
        Args:
            todo: Todo object to add
            
        Returns:
            ID of the added todo
        """
        project_name = todo.project or self.config.default_project
        project, todos = self.load_project(project_name)
        
        # Ensure unique ID globally across all projects
        if not todo.id:
            todo.id = self.get_next_todo_id()
        else:
            # Check for duplicate IDs across all projects
            all_todos = self.get_all_todos()
            existing_ids = {t.id for t in all_todos}
            if todo.id in existing_ids:
                todo.id = self.get_next_todo_id()
        
        todos.append(todo)
        self.save_project(project, todos)
        return todo.id
    
    def update_todo(self, todo: Todo) -> bool:
        """Update an existing todo in storage.
        
        Args:
            todo: Todo object with updated data
            
        Returns:
            True if updated successfully, False otherwise
        """
        project_name = todo.project or self.config.default_project
        project, todos = self.load_project(project_name)
        
        # Find and update the todo
        for i, existing_todo in enumerate(todos):
            if existing_todo.id == todo.id:
                todos[i] = todo
                return self.save_project(project, todos)
        
        # If not found in the expected project, search all projects
        for proj_name in self.list_projects():
            if proj_name == project_name:
                continue
            project, todos = self.load_project(proj_name)
            for i, existing_todo in enumerate(todos):
                if existing_todo.id == todo.id:
                    # Found in different project, remove from old and add to new
                    todos.pop(i)
                    self.save_project(project, todos)
                    # Add to new project
                    return self.add_todo(todo) is not None
        
        return False
    
    def delete_todo(self, todo_id: int, project: Optional[str] = None) -> bool:
        """Delete a todo from storage.
        
        Args:
            todo_id: ID of the todo to delete
            project: Optional project name to search in (searches all if None)
            
        Returns:
            True if deleted successfully, False otherwise
        """
        if project:
            project_obj, todos = self.load_project(project)
            original_count = len(todos)
            todos = [t for t in todos if t.id != todo_id]
            if len(todos) < original_count:
                return self.save_project(project_obj, todos)
        else:
            # Search all projects
            for proj_name in self.list_projects():
                project_obj, todos = self.load_project(proj_name)
                original_count = len(todos)
                todos = [t for t in todos if t.id != todo_id]
                if len(todos) < original_count:
                    return self.save_project(project_obj, todos)
        return False


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
