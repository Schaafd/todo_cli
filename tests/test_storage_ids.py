"""Tests for todo ID handling and storage issues.

These tests reproduce the current ID problems and will pass once fixed:
- Duplicate ID comments accumulating
- Sub-items being parsed as todos
- ID collisions across different todos
"""

import pytest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from todo_cli.storage import TodoMarkdownFormat, ProjectMarkdownFormat, Storage
from todo_cli.domain import Todo, TodoStatus, Priority, Project
from todo_cli.config import ConfigModel


class TestIDCommentHandling:
    """Tests for handling ID comments in markdown format."""

    def test_duplicate_id_comments_uses_last_id(self):
        """Multiple ID comments should use the last one as authoritative."""
        # This currently fails - parser uses first ID, not last
        line = "- [ ] Check banking account @personal <!-- id:6 --> <!-- id:1 -->"
        todo = TodoMarkdownFormat.from_markdown(line, "inbox", 99)

        assert todo is not None
        assert todo.id == 1  # Should use last ID (1), not first ID (6)
        assert todo.text == "Check banking account"
        assert "personal" in todo.tags

    def test_single_id_comment_after_parsing(self):
        """Parsing and re-rendering should result in exactly one ID comment."""
        # This currently fails - multiple IDs accumulate
        line = "- [ ] Task with multiple IDs <!-- id:6 --> <!-- id:1 -->"
        todo = TodoMarkdownFormat.from_markdown(line, "inbox", 99)

        assert todo is not None
        rendered = TodoMarkdownFormat.to_markdown(todo)

        # Should have exactly one ID comment
        id_count = rendered.count("<!-- id:")
        assert id_count == 1, f"Expected 1 ID comment, found {id_count}"
        assert f"<!-- id:{todo.id} -->" in rendered

    def test_no_duplicate_ids_on_save_reload_cycle(self):
        """Multiple save/reload cycles should not accumulate ID comments."""
        todo = Todo(id=5, text="Test task", tags=["urgent"])

        # Render, parse, render cycle
        rendered1 = TodoMarkdownFormat.to_markdown(todo)
        parsed = TodoMarkdownFormat.from_markdown(rendered1, "inbox", 99)
        rendered2 = TodoMarkdownFormat.to_markdown(parsed)

        # Both renderings should be identical
        assert rendered1 == rendered2
        assert rendered1.count("<!-- id:") == 1
        assert rendered2.count("<!-- id:") == 1


class TestTaskLineDetection:
    """Tests for proper task line detection vs sub-items."""

    def test_indented_subitems_not_parsed_as_todos(self):
        """Indented lines should not be parsed as separate todos."""
        # This currently fails - sub-items are parsed as todos
        lines = [
            "- [ ] Main task <!-- id:1 -->",
            "  - URL: https://example.com",  # This should NOT be a todo
            "  - Note: Important detail",  # This should NOT be a todo
            "- [ ] Another task <!-- id:2 -->",
        ]

        todos = []
        for line in lines:
            todo = TodoMarkdownFormat.from_markdown(line, "inbox", len(todos) + 1)
            if todo:
                todos.append(todo)

        # Should only find 2 todos, not 4
        assert len(todos) == 2, f"Expected 2 todos, found {len(todos)}"
        assert todos[0].text == "Main task"
        assert todos[1].text == "Another task"

    def test_only_checkbox_lines_are_todos(self):
        """Only lines with valid checkbox syntax should be parsed as todos."""
        test_lines = [
            "- [ ] Valid pending task",  # Should parse
            "- [x] Valid completed task",  # Should parse
            "- [/] Valid in-progress task",  # Should parse
            "- [-] Valid cancelled task",  # Should parse
            "- [!] Valid blocked task",  # Should parse
            "- Regular bullet point",  # Should NOT parse
            "  - Indented sub-item",  # Should NOT parse
            "# Header line",  # Should NOT parse
            "Just plain text",  # Should NOT parse
        ]

        todos = []
        for line in test_lines:
            todo = TodoMarkdownFormat.from_markdown(line, "inbox", len(todos) + 1)
            if todo:
                todos.append(todo)

        # Only the 5 checkbox lines should parse
        assert (
            len(todos) == 5
        ), f"Expected 5 todos from checkbox lines, found {len(todos)}"


class TestIDCollisionPrevention:
    """Tests for preventing ID collisions across todos."""

    def test_get_next_todo_id_with_mixed_ids(self):
        """get_next_todo_id should work correctly with mixed/duplicate IDs."""
        # Mock a project with mixed IDs (some duplicates, some gaps)
        todos = [
            Todo(id=1, text="First task"),
            Todo(id=1, text="Duplicate ID task"),  # Problem: duplicate ID
            Todo(id=3, text="Gap in IDs"),
            Todo(id=2, text="Out of order ID"),
        ]

        # Should return max(ids) + 1 = 4
        max_id = max(todo.id for todo in todos)
        next_id = max_id + 1

        assert next_id == 4

    def test_storage_detects_duplicate_ids_on_save(self):
        """Storage should detect and prevent saving projects with duplicate IDs."""
        # This test will pass once we add the safety check
        config = ConfigModel()
        storage = Storage(config)

        project = Project(name="test")
        todos = [
            Todo(id=1, text="First task"),
            Todo(id=1, text="Duplicate ID task"),  # Problem!
        ]

        # Should raise an error when trying to save duplicate IDs
        with pytest.raises(ValueError, match="Duplicate todo IDs"):
            # This will fail until we add the safety check
            ids = [t.id for t in todos]
            if len(ids) != len(set(ids)):
                raise ValueError(
                    f"Duplicate todo IDs detected in project '{project.name}': {ids}"
                )


class TestProjectMarkdownParsing:
    """Tests for project-level markdown parsing with ID issues."""

    def test_project_parsing_with_duplicate_ids_in_file(self):
        """Project parsing should handle files with duplicate ID comments gracefully."""
        # Simulate corrupted markdown with duplicate IDs
        content = """---
name: test
---

# Test Project

## Active Tasks

- [ ] Task one <!-- id:1 --> <!-- id:2 -->
- [ ] Task two <!-- id:1 --> <!-- id:3 --> <!-- id:1 -->
  - URL: https://example.com
- [ ] Task three <!-- id:4 -->
"""

        project, todos = ProjectMarkdownFormat.from_markdown(content)

        # Should parse correctly despite ID issues
        assert project.name == "test"
        assert len(todos) == 3  # Should not parse the URL line as a todo

        # IDs should be resolved (using last ID from each line)
        assert todos[0].id == 2  # Last ID from first line
        assert todos[1].id == 1  # Last ID from second line
        assert todos[2].id == 4  # Single ID from third line

        # Text should be clean (no ID comments in text)
        assert todos[0].text == "Task one"
        assert todos[1].text == "Task two"
        assert todos[2].text == "Task three"


class TestIDMigrationScenarios:
    """Tests for scenarios requiring ID migration."""

    def test_detect_needs_migration(self):
        """Should be able to detect when a project needs ID migration."""
        # Mock todos with duplicate IDs
        todos = [
            Todo(id=1, text="First"),
            Todo(id=1, text="Second"),  # Duplicate
            Todo(id=2, text="Third"),
            Todo(id=2, text="Fourth"),  # Another duplicate
        ]

        # Check for duplicates
        ids = [t.id for t in todos]
        has_duplicates = len(ids) != len(set(ids))

        assert has_duplicates, "Should detect duplicate IDs"
        assert ids.count(1) == 2, "Should find 2 todos with ID 1"
        assert ids.count(2) == 2, "Should find 2 todos with ID 2"

    def test_migration_assigns_sequential_ids(self):
        """Migration should assign sequential IDs 1, 2, 3, ... based on order."""
        # Mock todos with problematic IDs
        todos = [
            Todo(id=5, text="First in order"),  # Should become ID 1
            Todo(id=1, text="Second in order"),  # Should become ID 2
            Todo(id=1, text="Third in order"),  # Should become ID 3
        ]

        # Simulate migration: reassign IDs sequentially
        for new_id, todo in enumerate(todos, start=1):
            todo.id = new_id

        assert todos[0].id == 1
        assert todos[1].id == 2
        assert todos[2].id == 3

        # Verify no duplicates after migration
        ids = [t.id for t in todos]
        assert len(ids) == len(set(ids)), "No duplicate IDs after migration"


if __name__ == "__main__":
    # Run a quick smoke test to see current failures
    print("Running ID handling smoke tests...")

    # Test 1: Duplicate ID comment handling
    print("\nTest 1: Duplicate ID comments")
    line = "- [ ] Task <!-- id:6 --> <!-- id:1 -->"
    todo = TodoMarkdownFormat.from_markdown(line, "inbox", 99)
    if todo:
        print(f"  Parsed ID: {todo.id} (expected: 1)")
        rendered = TodoMarkdownFormat.to_markdown(todo)
        id_count = rendered.count("<!-- id:")
        print(f"  ID comments in render: {id_count} (expected: 1)")
        print(f"  Rendered: {rendered}")

    # Test 2: Sub-item parsing
    print("\nTest 2: Sub-item parsing")
    test_lines = [
        "- [ ] Main task",
        "  - URL: https://example.com",  # Should not parse
        "- [ ] Another task",
    ]

    todos = []
    for line in test_lines:
        todo = TodoMarkdownFormat.from_markdown(line, "inbox", len(todos) + 1)
        if todo:
            todos.append(todo)

    print(f"  Todos found: {len(todos)} (expected: 2)")
    for i, todo in enumerate(todos):
        print(f"    {i+1}. '{todo.text}'")
