"""Tests for the demo mode service."""

import tempfile
import os
from pathlib import Path

import pytest

from todo_cli.config import ConfigModel, Config
from todo_cli.storage import Storage
from todo_cli.domain import Todo, TodoStatus, Priority
from todo_cli.services.demo import DemoDataGenerator, DEMO_TAG


@pytest.fixture(autouse=True)
def isolated_storage(tmp_path):
    """Provide an isolated storage backed by a temp directory."""
    config = ConfigModel(data_dir=str(tmp_path / "data"), backup_dir=str(tmp_path / "backups"))
    # Reset the global config singleton so tests don't interfere
    Config._instance = config
    yield config
    Config._instance = None


def _make_generator(isolated_storage):
    storage = Storage(isolated_storage)
    return DemoDataGenerator(storage=storage)


# ---------------------------------------------------------------------------
# Generation tests
# ---------------------------------------------------------------------------

class TestGenerateTasks:
    def test_generates_correct_count(self, isolated_storage):
        gen = _make_generator(isolated_storage)
        tasks = gen.generate_tasks(count=10)
        assert len(tasks) == 10

    def test_generates_default_count(self, isolated_storage):
        gen = _make_generator(isolated_storage)
        tasks = gen.generate_tasks()
        assert len(tasks) == 30

    def test_all_tasks_have_demo_tag(self, isolated_storage):
        gen = _make_generator(isolated_storage)
        tasks = gen.generate_tasks(count=20)
        for task in tasks:
            assert DEMO_TAG in task.tags, f"Task '{task.text}' missing demo tag"

    def test_variety_in_priorities(self, isolated_storage):
        gen = _make_generator(isolated_storage)
        tasks = gen.generate_tasks(count=50, seed=42)
        priorities = {t.priority for t in tasks}
        # With 50 tasks we should hit at least 3 different priorities
        assert len(priorities) >= 3, f"Only got priorities: {priorities}"

    def test_variety_in_statuses(self, isolated_storage):
        gen = _make_generator(isolated_storage)
        tasks = gen.generate_tasks(count=50, seed=42)
        statuses = {t.status for t in tasks}
        # Should have at least pending and in_progress
        assert TodoStatus.PENDING in statuses
        assert len(statuses) >= 2, f"Only got statuses: {statuses}"

    def test_variety_in_projects(self, isolated_storage):
        gen = _make_generator(isolated_storage)
        tasks = gen.generate_tasks(count=50, seed=42)
        projects = {t.project for t in tasks}
        # Templates cover work, personal, home, side-project, health
        assert len(projects) >= 4, f"Only got projects: {projects}"

    def test_some_tasks_have_due_dates(self, isolated_storage):
        gen = _make_generator(isolated_storage)
        tasks = gen.generate_tasks(count=50, seed=42)
        with_due = [t for t in tasks if t.due_date is not None]
        without_due = [t for t in tasks if t.due_date is None]
        assert len(with_due) > 0, "Expected some tasks with due dates"
        assert len(without_due) > 0, "Expected some tasks without due dates"

    def test_some_tasks_have_assignees(self, isolated_storage):
        gen = _make_generator(isolated_storage)
        tasks = gen.generate_tasks(count=50, seed=42)
        with_assignees = [t for t in tasks if t.assignees]
        assert len(with_assignees) > 0

    def test_some_tasks_pinned(self, isolated_storage):
        gen = _make_generator(isolated_storage)
        tasks = gen.generate_tasks(count=50, seed=42)
        pinned = [t for t in tasks if t.pinned]
        assert len(pinned) > 0

    def test_some_tasks_have_descriptions(self, isolated_storage):
        gen = _make_generator(isolated_storage)
        tasks = gen.generate_tasks(count=50, seed=42)
        with_desc = [t for t in tasks if t.description]
        assert len(with_desc) > 0


# ---------------------------------------------------------------------------
# Seed / reproducibility tests
# ---------------------------------------------------------------------------

class TestSeedReproducibility:
    def test_same_seed_same_output(self, isolated_storage):
        gen = _make_generator(isolated_storage)
        tasks_a = gen.generate_tasks(count=20, seed=123)
        tasks_b = gen.generate_tasks(count=20, seed=123)
        for a, b in zip(tasks_a, tasks_b):
            assert a.text == b.text
            assert a.project == b.project
            assert a.priority == b.priority
            assert a.status == b.status

    def test_different_seed_different_output(self, isolated_storage):
        gen = _make_generator(isolated_storage)
        tasks_a = gen.generate_tasks(count=20, seed=1)
        tasks_b = gen.generate_tasks(count=20, seed=2)
        # At least some tasks should differ in ordering or status
        differences = sum(
            1 for a, b in zip(tasks_a, tasks_b)
            if a.text != b.text or a.status != b.status
        )
        assert differences > 0


# ---------------------------------------------------------------------------
# Populate / clear lifecycle tests
# ---------------------------------------------------------------------------

class TestPopulateClearLifecycle:
    def test_populate_creates_tasks(self, isolated_storage):
        gen = _make_generator(isolated_storage)
        created = gen.populate(count=15, seed=42)
        assert created == 15
        assert gen.get_demo_count() == 15

    def test_clear_removes_only_demo_tasks(self, isolated_storage):
        storage = Storage(isolated_storage)
        gen = DemoDataGenerator(storage=storage)

        # Add a non-demo task manually
        real_task = Todo(id=0, text="Real task", project="work", tags=["important"])
        storage.add_todo(real_task)

        # Populate demo tasks
        gen.populate(count=10, seed=42)
        total = len(storage.get_all_todos())
        assert total == 11  # 1 real + 10 demo

        # Clear demo tasks
        removed = gen.clear()
        assert removed == 10
        remaining = storage.get_all_todos()
        assert len(remaining) == 1
        assert remaining[0].text == "Real task"

    def test_clear_when_no_demo_tasks(self, isolated_storage):
        gen = _make_generator(isolated_storage)
        removed = gen.clear()
        assert removed == 0

    def test_has_demo_data(self, isolated_storage):
        gen = _make_generator(isolated_storage)
        assert gen.has_demo_data() is False
        gen.populate(count=5, seed=42)
        assert gen.has_demo_data() is True
        gen.clear()
        assert gen.has_demo_data() is False

    def test_get_demo_count(self, isolated_storage):
        gen = _make_generator(isolated_storage)
        assert gen.get_demo_count() == 0
        gen.populate(count=8, seed=42)
        assert gen.get_demo_count() == 8

    def test_populate_twice_adds_more(self, isolated_storage):
        gen = _make_generator(isolated_storage)
        gen.populate(count=5, seed=1)
        gen.populate(count=5, seed=2)
        assert gen.get_demo_count() == 10

    def test_clear_after_double_populate(self, isolated_storage):
        gen = _make_generator(isolated_storage)
        gen.populate(count=5, seed=1)
        gen.populate(count=5, seed=2)
        removed = gen.clear()
        assert removed == 10
        assert gen.get_demo_count() == 0


# ---------------------------------------------------------------------------
# Count larger than templates
# ---------------------------------------------------------------------------

class TestLargeCount:
    def test_count_exceeds_templates(self, isolated_storage):
        gen = _make_generator(isolated_storage)
        tasks = gen.generate_tasks(count=80, seed=42)
        assert len(tasks) == 80
        # All should still have demo tag
        for t in tasks:
            assert DEMO_TAG in t.tags
