"""Full-screen Textual dashboard for Todo CLI."""

from __future__ import annotations

import calendar
import getpass
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Optional

from textual import events
from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.css.query import NoMatches
from textual.message import Message
from textual.screen import ModalScreen
from textual.widgets import Button, Footer, Input, Label, Select, Static

from ..config import ConfigModel, get_config
from ..domain import Priority, Project, Todo, TodoStatus
from ..storage import Storage
from ..theme import get_compact_ascii_title
from ..utils.datetime import ensure_aware, now_utc


@dataclass(frozen=True)
class TaskEntry:
    """A task plus the project that owns it."""

    project: str
    todo: Todo


@dataclass(frozen=True)
class SubtaskDraft:
    """Editable child task state carried by the parent task editor."""

    id: Optional[int]
    text: str
    priority: Priority
    status: TodoStatus
    due_date: Optional[datetime]
    start_date: Optional[datetime]
    assignees: list[str]
    pinned: bool


@dataclass(frozen=True)
class EditResult:
    """Validated task edits from the modal screen."""

    project: str
    todo_id: int
    text: str
    priority: Priority
    status: TodoStatus
    due_date: Optional[datetime]
    start_date: Optional[datetime]
    assignees: list[str]
    pinned: bool
    subtasks: list[SubtaskDraft]


@dataclass(frozen=True)
class DragState:
    """Mouse drag state for moving a task between panels."""

    option_id: str
    start_x: int
    start_y: int


@dataclass(frozen=True)
class DatePickerResult:
    """Selected date from the date picker, or None when cleared."""

    target: str
    value: Optional[datetime]


PANEL_TITLES = {
    "pinned": "Pinned",
    "overdue": "Overdue",
    "today": "Today",
    "upcoming": "Due This Week",
    "backlog": "Backlog",
    "in_progress": "In Progress",
    "blocked": "Blocked",
}

DEFAULT_TUI_PANELS = ["overdue", "today", "upcoming", "backlog"]

PRIORITY_OPTIONS = tuple((priority.value.title(), priority.value) for priority in Priority)
STATUS_OPTIONS = tuple((status.value.replace("_", " ").title(), status.value) for status in TodoStatus)
PINNED_OPTIONS = (("No", "no"), ("Yes", "yes"))
TUI_COMPACT_TITLE = "\n".join(get_compact_ascii_title().splitlines()[:3])
TUI_GETTING_STARTED = """[b]Quick Start:[/]
  [#2d8fd3]click task[/]       Edit details, dates, pinning, subtasks
  [#2d8fd3]drag task[/]        Move between panels
  [#2d8fd3]right-click[/]      Pin or unpin
  [#2d8fd3]r[/] reload         [#2d8fd3]q[/] quit
[b #2d8fd3]Pro Tips:[/] Use [#00a1a7]@tags[/], [#8fbf00]+assignees[/], [#c59f00]~high[/], due/start dates, and subtasks."""


def _default_assignee(config: ConfigModel) -> str:
    return config.collab_username or config.collab_user_id or getpass.getuser()


def _date_label(value: Optional[datetime], placeholder: str) -> str:
    return value.strftime("%Y-%m-%d") if value else placeholder


def _midnight(value: date) -> datetime:
    return ensure_aware(datetime.combine(value, datetime.min.time()))


def _split_people(value: str) -> list[str]:
    return [
        token.lstrip("+")
        for token in value.replace(",", " ").split()
        if token.strip()
    ]


def _subtask_from_todo(todo: Todo) -> SubtaskDraft:
    return SubtaskDraft(
        id=todo.id,
        text=todo.text,
        priority=todo.priority,
        status=todo.status,
        due_date=todo.due_date,
        start_date=todo.start_date,
        assignees=list(todo.assignees),
        pinned=todo.pinned,
    )


def _subtask_from_result(result: EditResult) -> SubtaskDraft:
    return SubtaskDraft(
        id=result.todo_id if result.todo_id > 0 else None,
        text=result.text,
        priority=result.priority,
        status=result.status,
        due_date=result.due_date,
        start_date=result.start_date,
        assignees=result.assignees,
        pinned=result.pinned,
    )


def _todo_from_subtask_draft(project: str, parent_id: int, draft: SubtaskDraft) -> Todo:
    todo = Todo(
        id=draft.id or 0,
        text=draft.text,
        project=project,
        priority=draft.priority,
        due_date=draft.due_date,
        start_date=draft.start_date,
        assignees=list(draft.assignees),
        pinned=draft.pinned,
        parent_id=parent_id,
    )
    todo.status = draft.status
    todo.completed = draft.status == TodoStatus.COMPLETED
    return todo


def _format_task(entry: TaskEntry) -> str:
    todo = entry.todo
    due = f" !{todo.due_date.strftime('%Y-%m-%d')}" if todo.due_date else ""
    tags = " ".join(f"@{tag}" for tag in todo.tags)
    project = "" if entry.project == "inbox" else f" ({entry.project})"
    meta = " ".join(part for part in [tags, due, project] if part)
    suffix = f"  {meta}" if meta else ""
    return f"{todo.id:>3} {todo.priority.value.upper():<8} {todo.text}{suffix}"


def _is_open(todo: Todo) -> bool:
    return not todo.completed and not todo.archived and todo.status != TodoStatus.CANCELLED


def _panel_tasks(panel: str, tasks: list[TaskEntry]) -> list[TaskEntry]:
    today = date.today()
    week_from_now = today + timedelta(days=7)

    def due_day(todo: Todo) -> Optional[date]:
        return todo.due_date.date() if todo.due_date else None

    if panel == "pinned":
        return [entry for entry in tasks if entry.todo.pinned and _is_open(entry.todo)]
    if panel == "overdue":
        return [entry for entry in tasks if entry.todo.is_overdue() and _is_open(entry.todo)]
    if panel == "today":
        return [entry for entry in tasks if due_day(entry.todo) == today and _is_open(entry.todo)]
    if panel == "upcoming":
        return [
            entry
            for entry in tasks
            if (day := due_day(entry.todo)) is not None
            and today < day <= week_from_now
            and _is_open(entry.todo)
        ]
    if panel == "backlog":
        return [entry for entry in tasks if entry.todo.due_date is None and _is_open(entry.todo)]
    if panel == "in_progress":
        return [entry for entry in tasks if entry.todo.status == TodoStatus.IN_PROGRESS and _is_open(entry.todo)]
    if panel == "blocked":
        return [entry for entry in tasks if entry.todo.status == TodoStatus.BLOCKED and not entry.todo.completed]
    return []


def _ordered_panels(config: ConfigModel) -> list[str]:
    configured = getattr(config, "dashboard_grid_sections", None)
    if not isinstance(configured, list):
        configured = []

    panels = [panel for panel in configured if panel in PANEL_TITLES]
    for panel in DEFAULT_TUI_PANELS:
        if panel not in panels:
            panels.append(panel)
    return panels


class TaskRow(Static):
    """A mouse-aware task row."""

    def __init__(self, entry: TaskEntry, option_id: str) -> None:
        super().__init__(_format_task(entry), classes="task-row")
        self.entry = entry
        self.option_id = option_id

    def on_mouse_down(self, event: events.MouseDown) -> None:
        if event.button == 2:
            self.app._toggle_pin_from_option(self.option_id)
            event.stop()
            return

        if event.button == 1:
            self.capture_mouse()
            self.app._start_drag(
                self.option_id,
                int(event.screen_x if event.screen_x is not None else event.x),
                int(event.screen_y if event.screen_y is not None else event.y),
            )
            event.stop()

    def on_mouse_up(self, event: events.MouseUp) -> None:
        if event.button == 1:
            self.release_mouse()
            self.app._finish_drag(
                int(event.screen_x if event.screen_x is not None else event.x),
                int(event.screen_y if event.screen_y is not None else event.y),
            )
            event.stop()

    def on_click(self, event: events.Click) -> None:
        if event.button == 1:
            self.app.open_task_editor(self.option_id)
            event.stop()


class TaskPanel(Vertical):
    """One task panel in the TUI dashboard."""

    def __init__(self, panel_key: str, entries: list[TaskEntry], option_ids: list[str]) -> None:
        super().__init__(id=f"panel-{panel_key}", classes="task-panel")
        self.panel_key = panel_key
        self.entries = entries
        self.option_ids = option_ids

    def compose(self) -> ComposeResult:
        yield Static(f"{PANEL_TITLES[self.panel_key]}  [dim]{len(self.entries)}[/dim]", classes="panel-title")
        if not self.entries:
            yield Static("No tasks", classes="empty-panel")
            return

        with Vertical(id=f"panel-{self.panel_key}-list", classes="task-list"):
            for entry, option_id in zip(self.entries, self.option_ids):
                yield TaskRow(entry, option_id)


class DateAction(Static):
    """Clickable date-picker command cell."""

    class Selected(Message):
        """Posted when a date-picker command is clicked."""

        def __init__(self, action_id: str) -> None:
            super().__init__()
            self.action_id = action_id

    def __init__(self, label: str, action_id: str, classes: str = "date-action") -> None:
        super().__init__(label, id=action_id, classes=classes)
        self.action_id = action_id

    def on_click(self, event: events.Click) -> None:
        event.stop()
        self.post_message(self.Selected(self.action_id))


class DateDay(Static):
    """Clickable day cell in the date picker calendar."""

    class Selected(Message):
        """Posted when a day cell is clicked."""

        def __init__(self, day: int) -> None:
            super().__init__()
            self.day = day

    def __init__(self, day: int, classes: str) -> None:
        super().__init__(str(day), id=f"date-day-{day}", classes=classes)
        self.day = day

    def on_click(self, event: events.Click) -> None:
        event.stop()
        self.post_message(self.Selected(self.day))


class DatePickerOverlay(Vertical):
    """Inline calendar popover for optional task dates."""

    class Picked(Message):
        """Posted when the user picks or clears a date."""

        def __init__(self, sender: "DatePickerOverlay", result: DatePickerResult) -> None:
            super().__init__()
            self.result = result

    def __init__(self, target: str, value: Optional[datetime]) -> None:
        super().__init__(classes="date-picker-overlay")
        selected = value.date() if value else date.today()
        self.selected = selected
        self.target = target
        self.year = selected.year
        self.month = selected.month
        self.mode = "days"

    def compose(self) -> ComposeResult:
        with Horizontal(id="date-picker-title"):
            yield DateAction("", "date-title-month", classes="date-title-action")
            yield DateAction("", "date-title-year", classes="date-title-action")
        with Horizontal(id="date-picker-nav"):
            yield DateAction("<", "date-prev")
            yield DateAction("Today", "date-today")
            yield DateAction("Clear", "date-clear")
            yield DateAction(">", "date-next")
        yield Container(id="date-grid")

    async def on_mount(self) -> None:
        await self._render_picker()

    async def on_date_action_selected(self, message: DateAction.Selected) -> None:
        message.stop()
        if message.action_id == "date-prev":
            self._move_backward()
            await self._render_picker()
            return

        if message.action_id == "date-next":
            self._move_forward()
            await self._render_picker()
            return

        if message.action_id == "date-today":
            self.post_message(
                self.Picked(self, DatePickerResult(self.target, _midnight(date.today())))
            )
            return

        if message.action_id == "date-clear":
            self.post_message(self.Picked(self, DatePickerResult(self.target, None)))
            return

        if message.action_id == "date-title-month":
            self.mode = "months"
            await self._render_picker()
            return

        if message.action_id == "date-title-year":
            self.mode = "years"
            await self._render_picker()
            return

        if message.action_id.startswith("date-select-month-"):
            self.month = int(message.action_id.rsplit("-", 1)[1])
            self.mode = "days"
            await self._render_picker()
            return

        if message.action_id.startswith("date-select-year-"):
            self.year = int(message.action_id.rsplit("-", 1)[1])
            self.mode = "days"
            await self._render_picker()
            return

    def on_date_day_selected(self, message: DateDay.Selected) -> None:
        message.stop()
        picked = _midnight(date(self.year, self.month, message.day))
        self.post_message(self.Picked(self, DatePickerResult(self.target, picked)))

    def _move_backward(self) -> None:
        if self.mode == "months":
            self.year -= 1
            return
        if self.mode == "years":
            self.year -= 12
            return
        self.month -= 1
        if self.month == 0:
            self.month = 12
            self.year -= 1

    def _move_forward(self) -> None:
        if self.mode == "months":
            self.year += 1
            return
        if self.mode == "years":
            self.year += 12
            return
        self.month += 1
        if self.month == 13:
            self.month = 1
            self.year += 1

    async def _render_picker(self) -> None:
        self.query_one("#date-title-month", DateAction).update(calendar.month_name[self.month])
        self.query_one("#date-title-year", DateAction).update(str(self.year))
        grid = self.query_one("#date-grid", Container)
        await grid.remove_children()

        if self.mode == "months":
            await self._render_month_choices(grid)
            return

        if self.mode == "years":
            await self._render_year_choices(grid)
            return

        await self._render_days(grid)

    async def _render_days(self, grid: Container) -> None:
        await grid.mount(
            Horizontal(
                *(Static(weekday, classes="date-weekday") for weekday in ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")),
                classes="date-weekdays",
            )
        )
        month_days = calendar.Calendar(firstweekday=0).monthdayscalendar(self.year, self.month)
        for week in month_days:
            row_widgets = []
            for day in week:
                if day == 0:
                    row_widgets.append(Static("", classes="date-empty"))
                else:
                    classes = "date-day"
                    is_selected = (
                        self.selected.year == self.year
                        and self.selected.month == self.month
                        and self.selected.day == day
                    )
                    if is_selected:
                        classes = "date-day selected-day"
                    row_widgets.append(DateDay(day, classes=classes))
            row = Horizontal(*row_widgets, classes="date-week")
            await grid.mount(row)

    async def _render_month_choices(self, grid: Container) -> None:
        month_names = list(calendar.month_abbr)[1:]
        for start in range(0, 12, 4):
            row = Horizontal(
                *(
                    DateAction(
                        month_names[index],
                        f"date-select-month-{index + 1}",
                        classes="date-choice selected-day" if index + 1 == self.month else "date-choice",
                    )
                    for index in range(start, start + 4)
                ),
                classes="date-choice-row",
            )
            await grid.mount(row)

    async def _render_year_choices(self, grid: Container) -> None:
        start_year = self.year - 5
        years = list(range(start_year, start_year + 12))
        for start in range(0, 12, 4):
            row = Horizontal(
                *(
                    DateAction(
                        str(year),
                        f"date-select-year-{year}",
                        classes="date-choice selected-day" if year == self.year else "date-choice",
                    )
                    for year in years[start:start + 4]
                ),
                classes="date-choice-row",
            )
            await grid.mount(row)


class SubtaskRow(Static):
    """Clickable child task row in the parent editor."""

    class Selected(Message):
        """Posted when the subtask row is clicked."""

        def __init__(self, index: int) -> None:
            super().__init__()
            self.index = index

    class Removed(Message):
        """Posted when the subtask row is removed."""

        def __init__(self, index: int) -> None:
            super().__init__()
            self.index = index

    def __init__(self, index: int, draft: SubtaskDraft) -> None:
        checkbox = "x" if draft.status == TodoStatus.COMPLETED else " "
        identifier = str(draft.id) if draft.id is not None else "new"
        super().__init__(
            f"[{checkbox}] {identifier:>3} {draft.priority.value.upper():<8} {draft.text}",
            id=f"subtask-{index}",
            classes="subtask-row",
        )
        self.index = index

    def on_click(self, event: events.Click) -> None:
        if event.button == 1:
            event.stop()
            self.post_message(self.Selected(self.index))

    def on_mouse_down(self, event: events.MouseDown) -> None:
        if event.button == 2:
            event.stop()
            self.post_message(self.Removed(self.index))


class EditTodoScreen(ModalScreen[EditResult]):
    """Editable task overlay."""

    BINDINGS = [("escape", "cancel", "Cancel")]

    def __init__(
        self,
        entry: TaskEntry,
        config: ConfigModel,
        subtasks: Optional[list[SubtaskDraft]] = None,
        *,
        allow_subtasks: bool = True,
    ) -> None:
        super().__init__()
        self.entry = entry
        self.config = config
        self.due_date = entry.todo.due_date
        self.start_date = entry.todo.start_date
        self.subtasks = subtasks or []
        self.allow_subtasks = allow_subtasks

    def compose(self) -> ComposeResult:
        todo = self.entry.todo
        assignees = " ".join(todo.assignees) if todo.assignees else _default_assignee(self.config)

        with Container(id="edit-dialog"):
            title = "New subtask" if todo.id <= 0 else f"Edit task {todo.id}"
            yield Label(title, id="edit-title")
            yield Label("Task")
            yield Input(todo.text, id="edit-text")
            with Horizontal(classes="edit-row"):
                with Vertical(classes="edit-field"):
                    yield Label("Priority")
                    yield Select(
                        PRIORITY_OPTIONS,
                        value=todo.priority.value,
                        allow_blank=False,
                        id="edit-priority",
                    )
                with Vertical(classes="edit-field"):
                    yield Label("Status")
                    yield Select(
                        STATUS_OPTIONS,
                        value=todo.status.value,
                        allow_blank=False,
                        id="edit-status",
                    )
                with Vertical(classes="edit-field"):
                    yield Label("Due")
                    yield Button(_date_label(self.due_date, "No due date"), id="edit-due")
                with Vertical(classes="edit-field"):
                    yield Label("Start")
                    yield Button(_date_label(self.start_date, "No start date"), id="edit-start")
                with Vertical(classes="edit-field"):
                    yield Label("Pinned")
                    yield Select(
                        PINNED_OPTIONS,
                        value="yes" if todo.pinned else "no",
                        allow_blank=False,
                        id="edit-pinned",
                    )
            with Horizontal(classes="edit-row"):
                with Vertical(classes="edit-field wide-field"):
                    yield Label("Assignees")
                    yield Input(assignees, placeholder="Optional, space or comma separated", id="edit-assignees")
            yield Container(id="date-picker-slot")
            if self.allow_subtasks:
                yield Label("Subtasks")
                yield Container(id="subtask-list")
                with Horizontal(id="subtask-actions"):
                    yield Button("Add Subtask", id="subtask-add")
            yield Static("", id="edit-error")
            with Horizontal(id="edit-actions"):
                yield Button("Save", id="edit-save")
                yield Button("Complete", id="edit-complete")
                yield Button("Cancel", id="edit-cancel")

    async def on_mount(self) -> None:
        if self.allow_subtasks:
            await self._render_subtasks()

    async def action_cancel(self) -> None:
        slot = self.query_one("#date-picker-slot", Container)
        if slot.children:
            await slot.remove_children()
            slot.styles.height = 0
            return
        self.dismiss(None)

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "edit-cancel":
            self.dismiss(None)
            return

        if event.button.id == "edit-due":
            await self._show_date_picker("due")
            return

        if event.button.id == "edit-start":
            await self._show_date_picker("start")
            return

        if event.button.id == "subtask-add":
            await self._add_subtask()
            return

        result = self._result(force_complete=event.button.id == "edit-complete")
        if result is not None:
            self.dismiss(result)

    async def on_date_picker_overlay_picked(self, message: DatePickerOverlay.Picked) -> None:
        message.stop()
        self._handle_date_pick(message.result)
        slot = self.query_one("#date-picker-slot", Container)
        await slot.remove_children()
        slot.styles.height = 0

    async def _show_date_picker(self, target: str) -> None:
        slot = self.query_one("#date-picker-slot", Container)
        await slot.remove_children()
        slot.styles.height = 12
        current_value = self.due_date if target == "due" else self.start_date
        await slot.mount(DatePickerOverlay(target, current_value))
        slot.scroll_visible()

    def _handle_date_pick(self, result: Optional[DatePickerResult]) -> None:
        if result is None:
            return
        if result.target == "due":
            self.due_date = result.value
            self.query_one("#edit-due", Button).label = _date_label(self.due_date, "No due date")
        elif result.target == "start":
            self.start_date = result.value
            self.query_one("#edit-start", Button).label = _date_label(self.start_date, "No start date")

    async def on_subtask_row_selected(self, message: SubtaskRow.Selected) -> None:
        message.stop()
        self._open_subtask_editor(message.index)

    async def on_subtask_row_removed(self, message: SubtaskRow.Removed) -> None:
        message.stop()
        if 0 <= message.index < len(self.subtasks):
            self.subtasks.pop(message.index)
            await self._render_subtasks()

    async def _add_subtask(self) -> None:
        draft = SubtaskDraft(
            id=None,
            text="New subtask",
            priority=Priority.MEDIUM,
            status=TodoStatus.PENDING,
            due_date=None,
            start_date=None,
            assignees=[_default_assignee(self.config)],
            pinned=False,
        )
        self.subtasks.append(draft)
        await self._render_subtasks()
        self._open_subtask_editor(len(self.subtasks) - 1)

    async def _render_subtasks(self) -> None:
        if not self.allow_subtasks:
            return
        list_widget = self.query_one("#subtask-list", Container)
        await list_widget.remove_children()
        if not self.subtasks:
            await list_widget.mount(Static("No subtasks", classes="empty-subtasks"))
            return
        for index, draft in enumerate(self.subtasks):
            await list_widget.mount(SubtaskRow(index, draft))

    def _open_subtask_editor(self, index: int) -> None:
        if not 0 <= index < len(self.subtasks):
            return
        draft = self.subtasks[index]
        child = _todo_from_subtask_draft(self.entry.project, self.entry.todo.id, draft)
        self.app.push_screen(
            EditTodoScreen(
                TaskEntry(project=self.entry.project, todo=child),
                self.config,
                [],
                allow_subtasks=False,
            ),
            lambda result: self._handle_subtask_edit(index, result),
        )

    def _handle_subtask_edit(self, index: int, result: Optional[EditResult]) -> None:
        if result is None or not 0 <= index < len(self.subtasks):
            return
        self.subtasks[index] = _subtask_from_result(result)
        self.run_worker(self._render_subtasks(), exclusive=True)

    def _result(self, force_complete: bool = False) -> Optional[EditResult]:
        error = self.query_one("#edit-error", Static)
        text = self.query_one("#edit-text", Input).value.strip()
        priority_value = str(self.query_one("#edit-priority", Select).value)
        status_value = str(self.query_one("#edit-status", Select).value)
        pinned = str(self.query_one("#edit-pinned", Select).value) == "yes"
        assignees = _split_people(self.query_one("#edit-assignees", Input).value)
        subtasks = list(self.subtasks) if self.allow_subtasks else []

        if not text:
            error.update("[red]Task text is required.[/red]")
            return None

        try:
            priority = Priority(priority_value)
        except ValueError:
            choices = ", ".join(priority.value for priority in Priority)
            error.update(f"[red]Priority must be one of: {choices}[/red]")
            return None

        if force_complete:
            status = TodoStatus.COMPLETED
        else:
            try:
                status = TodoStatus(status_value)
            except ValueError:
                choices = ", ".join(status.value for status in TodoStatus)
                error.update(f"[red]Status must be one of: {choices}[/red]")
                return None

        return EditResult(
            project=self.entry.project,
            todo_id=self.entry.todo.id,
            text=text,
            priority=priority,
            status=status,
            due_date=self.due_date,
            start_date=self.start_date,
            assignees=assignees,
            pinned=pinned,
            subtasks=subtasks,
        )


class TodoDashboardApp(App[None]):
    """Interactive full-screen dashboard."""

    TITLE = "Productivity Ninja CLI"

    CSS = """
    Screen {
        background: #1f232c;
        color: #f0f0f0;
    }

    #brand-banner {
        height: 5;
        background: #242936;
        padding: 0 1;
        border-bottom: solid #5865f2;
    }

    #brand-art {
        height: 3;
        content-align: center middle;
        color: #2d8fd3;
        text-style: bold;
    }

    #brand-subtitle {
        height: 1;
        content-align: center middle;
        color: #7aa2f7;
        text-style: bold;
    }

    #getting-started {
        height: 8;
        border: round #52616b;
        padding: 0 2;
        color: #f0f0f0;
    }

    #panels {
        height: 1fr;
        padding: 1 0;
    }

    .panel-row {
        height: 1fr;
        min-height: 10;
        margin-bottom: 1;
    }

    .task-panel {
        width: 1fr;
        height: 100%;
        border: round #52616b;
        margin: 0 1;
    }

    .panel-title {
        height: 1;
        padding: 0 1;
        text-style: bold;
        color: #7aa2f7;
    }

    .task-list {
        height: 1fr;
    }

    .task-row {
        height: 1;
        padding: 0 1;
    }

    .task-row:hover {
        background: #2f3546;
    }

    .empty-panel {
        height: 1fr;
        content-align: center middle;
        color: #7d8590;
    }

    #summary {
        height: 3;
        border: round #7aa2f7;
        padding: 0 1;
        content-align: left middle;
    }

    EditTodoScreen {
        align: center middle;
    }

    #edit-dialog {
        width: 80%;
        height: 80%;
        max-width: 110;
        border: thick #7aa2f7;
        background: #242936;
        padding: 1 2;
    }

    #edit-title {
        text-style: bold;
        color: #bb9af7;
        height: 1;
    }

    #edit-dialog Input,
    #edit-dialog Select {
        background: #1f232c;
        color: #f0f0f0;
        border: round #52616b;
    }

    #edit-dialog Input:focus,
    #edit-dialog Select:focus {
        border: round #7aa2f7;
        background: #2f3546;
    }

    .edit-row {
        height: 5;
    }

    .edit-field {
        width: 1fr;
        margin-right: 1;
    }

    .edit-field Select {
        width: 100%;
    }

    .wide-field {
        width: 100%;
    }

    #subtask-list {
        height: 1fr;
        min-height: 6;
        border: round #52616b;
        background: #1f232c;
        padding: 0 1;
    }

    #subtask-actions {
        height: 3;
    }

    #subtask-actions Button {
        width: 24;
        margin-top: 1;
        color: #f0f0f0;
        text-style: bold;
        border: round #52616b;
        background: #2f3546;
    }

    .subtask-row {
        height: 1;
        padding: 0 1;
    }

    .subtask-row:hover {
        background: #2f3546;
    }

    .empty-subtasks {
        height: 1fr;
        content-align: center middle;
        color: #7d8590;
    }

    #edit-error {
        height: 1;
    }

    #edit-actions {
        height: 3;
    }

    #edit-actions Button {
        width: 1fr;
        margin-right: 1;
        color: #f0f0f0;
        text-style: bold;
        border: round #52616b;
        background: #2f3546;
    }

    #edit-save {
        background: #365a6d;
        border: round #7aa2f7;
    }

    #edit-complete {
        background: #3f5f46;
        border: round #8bd649;
    }

    #edit-cancel {
        background: #3a3f4b;
        border: round #7d8590;
    }

    #edit-actions Button:focus {
        background: #414868;
        border: round #bb9af7;
    }

    #edit-dialog {
        layers: base overlay;
    }

    #date-picker-slot {
        position: absolute;
        offset: 42 6;
        width: 38;
        height: 0;
        layer: overlay;
    }

    .date-picker-overlay {
        width: 38;
        height: 12;
        border: round #7aa2f7;
        background: #242936;
        padding: 0 1;
    }

    #date-picker-title {
        height: 1;
    }

    #date-picker-nav,
    .date-week,
    .date-choice-row {
        height: 1;
    }

    .date-weekdays {
        height: 1;
    }

    .date-action {
        width: 8;
        margin-right: 0;
    }

    .date-title-action {
        width: 1fr;
        margin-right: 0;
    }

    .date-day,
    .date-empty,
    .date-weekday {
        width: 5;
        margin-right: 0;
    }

    .date-choice {
        width: 9;
        margin-right: 0;
    }

    .date-action,
    .date-title-action,
    .date-choice,
    .date-day {
        background: #2f3546;
        color: #f0f0f0;
        content-align: center middle;
    }

    .selected-day {
        background: #365a6d;
        text-style: bold;
    }

    .date-action:hover,
    .date-title-action:hover,
    .date-choice:hover,
    .date-day:hover {
        background: #414868;
    }

    .date-weekday {
        content-align: center middle;
        color: #7aa2f7;
        text-style: bold;
    }
    """

    BINDINGS = [
        ("q", "quit", "Quit"),
        ("r", "reload", "Reload"),
    ]

    def __init__(self, config: Optional[ConfigModel] = None, storage: Optional[Storage] = None) -> None:
        self.config = config or get_config()
        self.storage = storage or Storage(self.config)
        self.task_index: dict[str, TaskEntry] = {}
        self._drag_state: Optional[DragState] = None
        self._suppress_next_select = False
        super().__init__()

    def compose(self) -> ComposeResult:
        with Container(id="brand-banner"):
            yield Static(TUI_COMPACT_TITLE, id="brand-art")
            yield Static("⚡ Master Your Tasks. Unleash Your Potential. ⚡  v1.0.0", id="brand-subtitle")
        getting_started = Static(TUI_GETTING_STARTED, id="getting-started")
        getting_started.border_title = "Getting Started"
        yield getting_started
        yield VerticalScroll(id="panels")
        yield Static("", id="summary")
        yield Footer()

    async def on_mount(self) -> None:
        await self.refresh_dashboard()

    async def action_reload(self) -> None:
        await self.refresh_dashboard()

    async def refresh_dashboard(self) -> None:
        tasks = self._load_tasks()
        panels = self.query_one("#panels", VerticalScroll)
        await panels.remove_children()

        self.task_index = {}
        columns = self._columns()
        visible_panels = _ordered_panels(self.config)
        panel_rows = [
            visible_panels[index:index + columns]
            for index in range(0, len(visible_panels), columns)
        ]

        option_counter = 0
        for row_panels in panel_rows:
            row_widgets = []
            for panel_key in row_panels:
                entries = _panel_tasks(panel_key, tasks)
                option_ids = []
                for entry in entries:
                    option_id = f"task-{option_counter}"
                    option_counter += 1
                    self.task_index[option_id] = entry
                    option_ids.append(option_id)
                row_widgets.append(TaskPanel(panel_key, entries, option_ids))
            row = Horizontal(*row_widgets, classes="panel-row")
            await panels.mount(row)

        self._update_summary(tasks)

    def open_task_editor(self, option_id: str) -> None:
        if self._suppress_next_select:
            self._suppress_next_select = False
            return
        if option_id is None or option_id not in self.task_index:
            return
        entry = self.task_index[option_id]
        self.push_screen(
            EditTodoScreen(entry, self.config, self._subtask_drafts(entry)),
            self._handle_edit_result,
        )

    def _start_drag(self, option_id: str, screen_x: int, screen_y: int) -> None:
        self._drag_state = DragState(option_id=option_id, start_x=screen_x, start_y=screen_y)

    def _finish_drag(self, screen_x: int, screen_y: int) -> None:
        if self._drag_state is None:
            return
        drag_state = self._drag_state
        self._drag_state = None
        if abs(screen_x - drag_state.start_x) + abs(screen_y - drag_state.start_y) < 3:
            return

        panel = self._panel_at(screen_x, screen_y)
        if panel is None:
            return

        self._move_option_to_panel(drag_state.option_id, panel.panel_key)
        self._suppress_next_select = True

    def _handle_edit_result(self, result: Optional[EditResult]) -> None:
        if result is None:
            return
        try:
            self._save_edit_result(result)
        except Exception as exc:
            self.notify(f"Could not save task: {exc}", severity="error")
            return
        self.run_worker(self.refresh_dashboard(), exclusive=True)

    def _save_edit_result(self, result: EditResult) -> None:
        project, todos = self.storage.load_project(result.project)
        if project is None:
            project = Project(name=result.project)

        for todo in todos:
            if todo.id != result.todo_id:
                continue
            self._apply_edit_result(todo, result)
            todo.modified = now_utc()
            todo._normalize_state()
            self._sync_subtasks(todos, result.project, result.todo_id, result.subtasks)
            self.storage.save_project(project, todos)
            return

        raise ValueError(f"Task {result.todo_id} not found in project '{result.project}'.")

    def _apply_edit_result(self, todo: Todo, result: EditResult) -> None:
        todo.text = result.text
        todo.priority = result.priority
        todo.due_date = result.due_date
        todo.start_date = result.start_date
        todo.assignees = result.assignees
        todo.pinned = result.pinned
        self._set_status(todo, result.status)

    def _save_task_change(self, project_name: str, todo_id: int, update) -> None:
        project, todos = self.storage.load_project(project_name)
        if project is None:
            project = Project(name=project_name)

        for todo in todos:
            if todo.id != todo_id:
                continue
            update(todo)
            todo.modified = now_utc()
            todo._normalize_state()
            self.storage.save_project(project, todos)
            return

        raise ValueError(f"Task {todo_id} not found in project '{project_name}'.")

    def _set_status(self, todo: Todo, status: TodoStatus) -> None:
        todo.status = status
        todo.completed = status == TodoStatus.COMPLETED
        if todo.completed:
            todo.completed_date = todo.completed_date or now_utc()
            todo.progress = 1.0
        else:
            todo.completed_date = None
            if todo.progress >= 1.0:
                todo.progress = 0.0

    def _move_option_to_panel(self, option_id: str, panel_key: str) -> None:
        entry = self.task_index.get(option_id)
        if entry is None:
            return
        self._move_task_to_panel(entry.project, entry.todo.id, panel_key)
        self.run_worker(self.refresh_dashboard(), exclusive=True)

    def _move_task_to_panel(self, project_name: str, todo_id: int, panel_key: str) -> None:
        self._save_task_change(
            project_name,
            todo_id,
            lambda todo: self._apply_panel_move(todo, panel_key),
        )

    def _apply_panel_move(self, todo: Todo, panel_key: str) -> None:
        if panel_key == "pinned":
            todo.pinned = True
            return

        if panel_key == "overdue":
            todo.due_date = now_utc() - timedelta(days=1)
            self._set_status(todo, TodoStatus.PENDING)
            return

        if panel_key == "today":
            todo.due_date = now_utc()
            self._set_status(todo, TodoStatus.PENDING)
            return

        if panel_key == "upcoming":
            todo.due_date = now_utc() + timedelta(days=7)
            self._set_status(todo, TodoStatus.PENDING)
            return

        if panel_key == "backlog":
            todo.due_date = None
            self._set_status(todo, TodoStatus.PENDING)
            return

        if panel_key == "in_progress":
            self._set_status(todo, TodoStatus.IN_PROGRESS)
            return

        if panel_key == "blocked":
            self._set_status(todo, TodoStatus.BLOCKED)

    def _toggle_pin_from_option(self, option_id: str) -> None:
        entry = self.task_index.get(option_id)
        if entry is None:
            return
        self._toggle_pin(entry.project, entry.todo.id)
        self.run_worker(self.refresh_dashboard(), exclusive=True)

    def _toggle_pin(self, project_name: str, todo_id: int) -> None:
        self._save_task_change(project_name, todo_id, lambda todo: setattr(todo, "pinned", not todo.pinned))

    def _subtask_drafts(self, entry: TaskEntry) -> list[SubtaskDraft]:
        _, todos = self.storage.load_project(entry.project)
        return [
            _subtask_from_todo(todo)
            for todo in todos
            if todo.parent_id == entry.todo.id and not todo.archived
        ]

    def _sync_subtasks(self, todos: list[Todo], project_name: str, parent_id: int, subtasks: list[SubtaskDraft]) -> None:
        existing = [todo for todo in todos if todo.parent_id == parent_id]
        existing_by_id = {todo.id: todo for todo in existing}
        retained_ids = {draft.id for draft in subtasks if draft.id is not None}
        next_id = max((todo.id for todo in todos), default=0) + 1

        for draft in subtasks:
            child = existing_by_id.get(draft.id) if draft.id is not None else None
            if child is None:
                child = Todo(id=next_id, text=draft.text, project=project_name, parent_id=parent_id)
                todos.append(child)
                next_id += 1

            child.text = draft.text
            child.priority = draft.priority
            child.due_date = draft.due_date
            child.start_date = draft.start_date
            child.assignees = list(draft.assignees)
            child.pinned = draft.pinned
            self._set_status(child, draft.status)
            child.modified = now_utc()
            child.archived = False

        for child in existing:
            if child.id not in retained_ids:
                todos.remove(child)

    def _panel_at(self, screen_x: int, screen_y: int) -> Optional[TaskPanel]:
        try:
            widget, _ = self.screen.get_widget_at(screen_x, screen_y)
        except Exception:
            return None
        if isinstance(widget, TaskPanel):
            return widget
        try:
            return widget.query_ancestor(TaskPanel, TaskPanel)
        except NoMatches:
            return None

    def _load_tasks(self) -> list[TaskEntry]:
        entries: list[TaskEntry] = []
        projects = self.storage.list_projects() or [self.config.default_project]
        for project_name in projects:
            _, todos = self.storage.load_project(project_name)
            entries.extend(TaskEntry(project=project_name, todo=todo) for todo in todos)
        return entries

    def _columns(self) -> int:
        try:
            columns = int(self.config.dashboard_grid_columns)
        except (TypeError, ValueError):
            columns = 2
        return max(1, min(columns, 3))

    def _update_summary(self, tasks: list[TaskEntry]) -> None:
        total = len(tasks)
        active = sum(1 for entry in tasks if entry.todo.is_active())
        completed = sum(1 for entry in tasks if entry.todo.completed)
        overdue = sum(1 for entry in tasks if entry.todo.is_overdue())
        self.query_one("#summary", Static).update(
            f"Total: {total}    Active: {active}    Completed: {completed}    Overdue: {overdue}"
        )
