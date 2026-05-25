"""Tests for the full-screen Textual dashboard."""

from datetime import date, timedelta

import pytest
from textual.widgets import Button, Input, Select

from todo_cli.config import ConfigModel
from todo_cli.domain import Priority, Project, Todo, TodoStatus
from todo_cli.storage import Storage
from todo_cli.theme import get_compact_ascii_title
from todo_cli.tui.app import EditResult, EditTodoScreen, SubtaskDraft, TaskEntry, TodoDashboardApp
from todo_cli.utils.datetime import now_utc


def _storage_with_tasks(tmp_path):
    config = ConfigModel(
        data_dir=str(tmp_path / "data"),
        backup_dir=str(tmp_path / "backups"),
        dashboard_grid_sections=["overdue", "today", "upcoming", "backlog"],
    )
    storage = Storage(config)
    project = Project(name="inbox")
    todos = [
        Todo(
            id=1,
            text="Fix production report",
            project="inbox",
            priority=Priority.HIGH,
            due_date=now_utc() - timedelta(days=1),
        ),
        Todo(
            id=2,
            text="Review backlog",
            project="inbox",
            priority=Priority.MEDIUM,
        ),
    ]
    storage.save_project(project, todos)
    return config, storage


@pytest.mark.asyncio
async def test_tui_dashboard_starts_and_indexes_clickable_tasks(tmp_path):
    config, storage = _storage_with_tasks(tmp_path)
    app = TodoDashboardApp(config=config, storage=storage)

    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()

        assert app.query_one("#panels") is not None
        assert app.title == "Productivity Ninja CLI"
        assert str(app.query_one("#brand-art").render()) == "\n".join(
            get_compact_ascii_title().splitlines()[:3]
        )
        assert app.query_one("#getting-started").border_title == "Getting Started"
        assert "Total: 2" in str(app.query_one("#summary").render())
        assert len(app.task_index) == 2


@pytest.mark.asyncio
async def test_tui_edit_overlay_uses_selects_for_distinct_options(tmp_path):
    config, storage = _storage_with_tasks(tmp_path)
    _, todos = storage.load_project("inbox")
    app = TodoDashboardApp(config=config, storage=storage)
    screen = EditTodoScreen(
        TaskEntry(project="inbox", todo=todos[0]),
        config,
        [
            SubtaskDraft(None, "First child", Priority.MEDIUM, TodoStatus.PENDING, None, None, [], False),
            SubtaskDraft(None, "Second child", Priority.MEDIUM, TodoStatus.PENDING, None, None, [], False),
        ],
    )

    async with app.run_test(size=(120, 40)) as pilot:
        await app.push_screen(screen)
        await pilot.pause()

        priority_select = screen.query_one("#edit-priority", Select)
        status_select = screen.query_one("#edit-status", Select)
        pinned_select = screen.query_one("#edit-pinned", Select)
        priority_select.value = Priority.LOW.value
        status_select.value = TodoStatus.BLOCKED.value
        pinned_select.value = "yes"

        result = screen._result()

        assert result is not None
        assert result.priority == Priority.LOW
        assert result.status == TodoStatus.BLOCKED
        assert result.pinned is True
        assert result.assignees
        assert [draft.text for draft in result.subtasks] == ["First child", "Second child"]


def test_tui_edit_result_persists_through_storage(tmp_path):
    config, storage = _storage_with_tasks(tmp_path)
    app = TodoDashboardApp(config=config, storage=storage)

    app._save_edit_result(
        EditResult(
            project="inbox",
            todo_id=1,
            text="Fix revised production report",
            priority=Priority.CRITICAL,
            status=TodoStatus.COMPLETED,
            due_date=None,
            start_date=now_utc(),
            assignees=["davidschaaf"],
            pinned=True,
            subtasks=[
                SubtaskDraft(None, "Confirm fix", Priority.MEDIUM, TodoStatus.PENDING, None, None, [], False),
                SubtaskDraft(None, "Notify team", Priority.MEDIUM, TodoStatus.PENDING, None, None, [], False),
            ],
        )
    )

    _, todos = storage.load_project("inbox")
    edited = next(todo for todo in todos if todo.id == 1)
    assert edited.text == "Fix revised production report"
    assert edited.priority == Priority.CRITICAL
    assert edited.status == TodoStatus.COMPLETED
    assert edited.completed is True
    assert edited.pinned is True
    assert edited.start_date is not None
    assert edited.assignees == ["davidschaaf"]
    children = [todo for todo in todos if todo.parent_id == 1]
    assert [child.text for child in children] == ["Confirm fix", "Notify team"]


@pytest.mark.asyncio
async def test_tui_date_picker_updates_editor_date(tmp_path):
    config, storage = _storage_with_tasks(tmp_path)
    _, todos = storage.load_project("inbox")
    app = TodoDashboardApp(config=config, storage=storage)
    screen = EditTodoScreen(TaskEntry(project="inbox", todo=todos[0]), config)

    async with app.run_test(size=(120, 40)) as pilot:
        await app.push_screen(screen)
        await pilot.pause()

        picked = now_utc().replace(month=1, day=15)
        screen._handle_date_pick(type("Result", (), {"target": "start", "value": picked})())

        assert screen.start_date == picked
        assert picked.strftime("%Y-%m-%d") in str(screen.query_one("#edit-start", Button).label)


@pytest.mark.asyncio
async def test_tui_date_picker_overlay_selects_and_clears_dates(tmp_path):
    config, storage = _storage_with_tasks(tmp_path)
    _, todos = storage.load_project("inbox")
    app = TodoDashboardApp(config=config, storage=storage)
    screen = EditTodoScreen(TaskEntry(project="inbox", todo=todos[0]), config)

    async with app.run_test(size=(120, 40)) as pilot:
        await app.push_screen(screen)
        await pilot.pause()

        await pilot.click("#edit-start")
        await pilot.pause()

        assert len(screen.query(".date-picker-overlay")) == 1

        await pilot.click("#date-day-15")
        await pilot.pause()

        expected = date.today().replace(day=15)
        assert screen.start_date is not None
        assert screen.start_date.date() == expected
        assert expected.strftime("%Y-%m-%d") in str(screen.query_one("#edit-start", Button).label)
        assert len(screen.query(".date-picker-overlay")) == 0

        await pilot.click("#edit-due")
        await pilot.pause()
        await pilot.click("#date-clear")
        await pilot.pause()

        assert screen.due_date is None
        assert str(screen.query_one("#edit-due", Button).label) == "No due date"


@pytest.mark.asyncio
async def test_tui_date_picker_month_and_year_navigation(tmp_path):
    config, storage = _storage_with_tasks(tmp_path)
    _, todos = storage.load_project("inbox")
    app = TodoDashboardApp(config=config, storage=storage)
    screen = EditTodoScreen(TaskEntry(project="inbox", todo=todos[0]), config)

    async with app.run_test(size=(120, 40)) as pilot:
        await app.push_screen(screen)
        await pilot.pause()

        await pilot.click("#edit-start")
        await pilot.pause()
        today = date.today()
        target_year = today.year - 2

        await pilot.click("#date-title-year")
        await pilot.pause()
        await pilot.click(f"#date-select-year-{target_year}")
        await pilot.pause()
        await pilot.click("#date-title-month")
        await pilot.pause()
        await pilot.click("#date-select-month-1")
        await pilot.pause()
        await pilot.click("#date-day-15")
        await pilot.pause()

        assert screen.start_date is not None
        assert screen.start_date.date() == date(target_year, 1, 15)


@pytest.mark.asyncio
async def test_tui_date_picker_stays_inside_editor(tmp_path):
    config, storage = _storage_with_tasks(tmp_path)
    _, todos = storage.load_project("inbox")
    app = TodoDashboardApp(config=config, storage=storage)
    screen = EditTodoScreen(TaskEntry(project="inbox", todo=todos[0]), config)

    async with app.run_test(size=(120, 40)) as pilot:
        await app.push_screen(screen)
        await pilot.pause()
        await screen._show_date_picker("due")
        await pilot.pause()

        editor = screen.query_one("#edit-dialog").region
        picker = screen.query_one(".date-picker-overlay").region
        assert picker.x >= editor.x
        assert picker.y >= editor.y
        assert picker.right <= editor.right
        assert picker.bottom <= editor.bottom


@pytest.mark.asyncio
async def test_tui_subtask_rows_open_child_editor(tmp_path):
    config, storage = _storage_with_tasks(tmp_path)
    _, todos = storage.load_project("inbox")
    app = TodoDashboardApp(config=config, storage=storage)
    screen = EditTodoScreen(
        TaskEntry(project="inbox", todo=todos[0]),
        config,
        [SubtaskDraft(3, "Existing child", Priority.LOW, TodoStatus.PENDING, None, None, [], False)],
    )

    async with app.run_test(size=(120, 40)) as pilot:
        await app.push_screen(screen)
        await pilot.pause()

        await pilot.click("#subtask-0")
        await pilot.pause()

        assert app.screen is not screen
        assert app.screen.query_one("#edit-text", Input).value == "Existing child"


def test_tui_edit_result_updates_existing_subtask(tmp_path):
    config = ConfigModel(
        data_dir=str(tmp_path / "data"),
        backup_dir=str(tmp_path / "backups"),
    )
    storage = Storage(config)
    project = Project(name="inbox")
    storage.save_project(
        project,
        [
            Todo(id=1, text="Parent task", project="inbox"),
            Todo(id=2, text="Child task", project="inbox", parent_id=1),
        ],
    )
    app = TodoDashboardApp(config=config, storage=storage)

    app._save_edit_result(
        EditResult(
            project="inbox",
            todo_id=1,
            text="Parent task",
            priority=Priority.MEDIUM,
            status=TodoStatus.PENDING,
            due_date=None,
            start_date=None,
            assignees=[],
            pinned=False,
            subtasks=[
                SubtaskDraft(2, "Updated child", Priority.HIGH, TodoStatus.COMPLETED, None, None, ["david"], True),
            ],
        )
    )

    _, todos = storage.load_project("inbox")
    child = next(todo for todo in todos if todo.id == 2)
    assert child.text == "Updated child"
    assert child.priority == Priority.HIGH
    assert child.status == TodoStatus.COMPLETED
    assert child.completed is True
    assert child.assignees == ["david"]
    assert child.pinned is True


def test_tui_drag_drop_panel_move_updates_task_state(tmp_path):
    config, storage = _storage_with_tasks(tmp_path)
    app = TodoDashboardApp(config=config, storage=storage)

    app._move_task_to_panel("inbox", 2, "in_progress")

    _, todos = storage.load_project("inbox")
    moved = next(todo for todo in todos if todo.id == 2)
    assert moved.status == TodoStatus.IN_PROGRESS
    assert moved.completed is False

    app._move_task_to_panel("inbox", 2, "backlog")

    _, todos = storage.load_project("inbox")
    moved = next(todo for todo in todos if todo.id == 2)
    assert moved.status == TodoStatus.PENDING
    assert moved.due_date is None


def test_tui_toggle_pin_updates_task(tmp_path):
    config, storage = _storage_with_tasks(tmp_path)
    app = TodoDashboardApp(config=config, storage=storage)

    app._toggle_pin("inbox", 2)

    _, todos = storage.load_project("inbox")
    pinned = next(todo for todo in todos if todo.id == 2)
    assert pinned.pinned is True
