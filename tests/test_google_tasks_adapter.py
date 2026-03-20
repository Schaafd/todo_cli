"""Tests for the Google Tasks sync adapter."""

import json
import pytest
import httpx
import respx
from datetime import datetime, timezone

from todo_cli.sync.providers.google_tasks_adapter import (
    GoogleTasksAPI,
    GoogleTasksAdapter,
    _encode_metadata,
    _decode_metadata,
    _parse_rfc3339,
    _to_rfc3339,
)
from todo_cli.sync.app_sync_adapter import (
    AuthenticationError,
    NetworkError,
    RateLimitError,
)
from todo_cli.sync.app_sync_models import AppSyncConfig, AppSyncProvider, ExternalTodoItem
from todo_cli.domain import Todo, Priority, TodoStatus


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

BASE = "https://tasks.googleapis.com/tasks/v1/"


def _make_config(
    access_token: str = "test-token",
    tasklist_id: str = "@default",
) -> AppSyncConfig:
    return AppSyncConfig(
        provider=AppSyncProvider.GOOGLE_TASKS,
        credentials={"google_access_token": access_token},
        settings={"google_tasklist_id": tasklist_id},
    )


def _sample_task(
    task_id: str = "task1",
    title: str = "Buy milk",
    notes: str | None = None,
    status: str = "needsAction",
    due: str | None = None,
    completed: str | None = None,
    updated: str | None = "2025-06-01T12:00:00.000Z",
) -> dict:
    t: dict = {"id": task_id, "title": title, "status": status, "updated": updated}
    if notes is not None:
        t["notes"] = notes
    if due is not None:
        t["due"] = due
    if completed is not None:
        t["completed"] = completed
    return t


def _sample_tasklist(list_id: str = "list1", title: str = "My Tasks") -> dict:
    return {"id": list_id, "title": title}


# ---------------------------------------------------------------------------
# GoogleTasksAPI tests
# ---------------------------------------------------------------------------


class TestGoogleTasksAPI:
    """Tests for the low-level API client."""

    @respx.mock
    @pytest.mark.asyncio
    async def test_list_tasklists(self):
        route = respx.get(BASE + "users/@me/lists").mock(
            return_value=httpx.Response(
                200, json={"items": [_sample_tasklist()]}
            )
        )
        async with GoogleTasksAPI("tok") as api:
            result = await api.list_tasklists()
        assert len(result) == 1
        assert result[0]["title"] == "My Tasks"
        assert route.called

    @respx.mock
    @pytest.mark.asyncio
    async def test_list_tasks(self):
        route = respx.get(BASE + "lists/@default/tasks").mock(
            return_value=httpx.Response(
                200, json={"items": [_sample_task()]}
            )
        )
        async with GoogleTasksAPI("tok") as api:
            result = await api.list_tasks("@default")
        assert len(result) == 1
        assert result[0]["title"] == "Buy milk"

    @respx.mock
    @pytest.mark.asyncio
    async def test_get_task(self):
        route = respx.get(BASE + "lists/@default/tasks/task1").mock(
            return_value=httpx.Response(200, json=_sample_task())
        )
        async with GoogleTasksAPI("tok") as api:
            result = await api.get_task("@default", "task1")
        assert result["id"] == "task1"

    @respx.mock
    @pytest.mark.asyncio
    async def test_create_task(self):
        route = respx.post(BASE + "lists/@default/tasks").mock(
            return_value=httpx.Response(200, json=_sample_task(task_id="new1"))
        )
        async with GoogleTasksAPI("tok") as api:
            result = await api.create_task("@default", {"title": "New task"})
        assert result["id"] == "new1"

    @respx.mock
    @pytest.mark.asyncio
    async def test_update_task(self):
        route = respx.patch(BASE + "lists/@default/tasks/task1").mock(
            return_value=httpx.Response(200, json=_sample_task(title="Updated"))
        )
        async with GoogleTasksAPI("tok") as api:
            result = await api.update_task("@default", "task1", {"title": "Updated"})
        assert result["title"] == "Updated"

    @respx.mock
    @pytest.mark.asyncio
    async def test_delete_task(self):
        route = respx.delete(BASE + "lists/@default/tasks/task1").mock(
            return_value=httpx.Response(204)
        )
        async with GoogleTasksAPI("tok") as api:
            result = await api.delete_task("@default", "task1")
        assert result == {}

    @respx.mock
    @pytest.mark.asyncio
    async def test_auth_error_401(self):
        respx.get(BASE + "users/@me/lists").mock(
            return_value=httpx.Response(401, json={"error": "unauthorized"})
        )
        async with GoogleTasksAPI("bad") as api:
            with pytest.raises(AuthenticationError):
                await api.list_tasklists()

    @respx.mock
    @pytest.mark.asyncio
    async def test_auth_error_403(self):
        respx.get(BASE + "users/@me/lists").mock(
            return_value=httpx.Response(403, json={"error": "forbidden"})
        )
        async with GoogleTasksAPI("bad") as api:
            with pytest.raises(AuthenticationError):
                await api.list_tasklists()

    @respx.mock
    @pytest.mark.asyncio
    async def test_rate_limit_429(self):
        respx.get(BASE + "users/@me/lists").mock(
            return_value=httpx.Response(429, json={"error": "rate limited"})
        )
        async with GoogleTasksAPI("tok") as api:
            with pytest.raises(RateLimitError):
                await api.list_tasklists()

    @respx.mock
    @pytest.mark.asyncio
    async def test_network_error_500(self):
        respx.get(BASE + "users/@me/lists").mock(
            return_value=httpx.Response(500, text="Internal Server Error")
        )
        async with GoogleTasksAPI("tok") as api:
            with pytest.raises(NetworkError):
                await api.list_tasklists()

    @pytest.mark.asyncio
    async def test_client_not_initialized(self):
        api = GoogleTasksAPI("tok")
        with pytest.raises(NetworkError, match="not initialized"):
            await api.list_tasklists()


# ---------------------------------------------------------------------------
# Adapter authentication tests
# ---------------------------------------------------------------------------


class TestGoogleTasksAdapterAuth:

    @respx.mock
    @pytest.mark.asyncio
    async def test_authenticate_success(self):
        respx.get(BASE + "users/@me/lists").mock(
            return_value=httpx.Response(200, json={"items": [_sample_tasklist()]})
        )
        adapter = GoogleTasksAdapter(_make_config())
        result = await adapter.authenticate()
        assert result is True

    @pytest.mark.asyncio
    async def test_authenticate_no_token(self):
        adapter = GoogleTasksAdapter(_make_config(access_token=""))
        with pytest.raises(AuthenticationError, match="No Google access token"):
            await adapter.authenticate()

    @respx.mock
    @pytest.mark.asyncio
    async def test_authenticate_invalid_token(self):
        respx.get(BASE + "users/@me/lists").mock(
            return_value=httpx.Response(401, json={"error": "invalid"})
        )
        adapter = GoogleTasksAdapter(_make_config())
        with pytest.raises(AuthenticationError):
            await adapter.authenticate()

    @respx.mock
    @pytest.mark.asyncio
    async def test_test_connection_success(self):
        respx.get(BASE + "users/@me/lists").mock(
            return_value=httpx.Response(200, json={"items": []})
        )
        adapter = GoogleTasksAdapter(_make_config())
        assert await adapter.test_connection() is True

    @respx.mock
    @pytest.mark.asyncio
    async def test_test_connection_failure(self):
        respx.get(BASE + "users/@me/lists").mock(
            return_value=httpx.Response(401, json={"error": "bad"})
        )
        adapter = GoogleTasksAdapter(_make_config())
        assert await adapter.test_connection() is False


# ---------------------------------------------------------------------------
# Field mapping tests
# ---------------------------------------------------------------------------


class TestFieldMapping:

    def test_map_todo_to_external_basic(self):
        adapter = GoogleTasksAdapter(_make_config())
        todo = Todo(id=1, text="Buy groceries")
        data = adapter.map_todo_to_external(todo)
        assert data["title"] == "Buy groceries"
        assert data["status"] == "needsAction"

    def test_map_todo_to_external_completed(self):
        adapter = GoogleTasksAdapter(_make_config())
        todo = Todo(
            id=1,
            text="Done task",
            status=TodoStatus.COMPLETED,
            completed=True,
            completed_date=datetime(2025, 6, 1, tzinfo=timezone.utc),
        )
        data = adapter.map_todo_to_external(todo)
        assert data["status"] == "completed"
        assert "completed" in data

    def test_map_todo_to_external_with_due_date(self):
        adapter = GoogleTasksAdapter(_make_config())
        due = datetime(2025, 12, 25, 10, 0, 0, tzinfo=timezone.utc)
        todo = Todo(id=1, text="Christmas task", due_date=due)
        data = adapter.map_todo_to_external(todo)
        assert data["due"] == "2025-12-25T10:00:00.000Z"

    def test_map_todo_to_external_with_description(self):
        adapter = GoogleTasksAdapter(_make_config())
        todo = Todo(id=1, text="Task", description="Some notes here")
        data = adapter.map_todo_to_external(todo)
        assert "Some notes here" in data["notes"]

    def test_map_todo_to_external_with_tags_and_priority(self):
        adapter = GoogleTasksAdapter(_make_config())
        todo = Todo(
            id=1,
            text="Task",
            tags=["urgent", "work"],
            priority=Priority.HIGH,
        )
        data = adapter.map_todo_to_external(todo)
        assert "notes" in data
        meta = _decode_metadata(data["notes"])
        assert meta["tags"] == ["urgent", "work"]
        assert meta["priority"] == Priority.HIGH

    def test_map_external_to_todo_basic(self):
        adapter = GoogleTasksAdapter(_make_config())
        task = _sample_task()
        item = adapter.map_external_to_todo(task)
        assert isinstance(item, ExternalTodoItem)
        assert item.external_id == "task1"
        assert item.title == "Buy milk"
        assert item.provider == AppSyncProvider.GOOGLE_TASKS
        assert item.completed is False

    def test_map_external_to_todo_completed(self):
        adapter = GoogleTasksAdapter(_make_config())
        task = _sample_task(
            status="completed",
            completed="2025-06-01T15:00:00.000Z",
        )
        item = adapter.map_external_to_todo(task)
        assert item.completed is True
        assert item.completed_at is not None
        assert item.completed_at.year == 2025

    def test_map_external_to_todo_with_due(self):
        adapter = GoogleTasksAdapter(_make_config())
        task = _sample_task(due="2025-12-25T00:00:00.000Z")
        item = adapter.map_external_to_todo(task)
        assert item.due_date is not None
        assert item.due_date.month == 12
        assert item.due_date.day == 25

    def test_map_external_to_todo_with_notes(self):
        adapter = GoogleTasksAdapter(_make_config())
        task = _sample_task(notes="Remember to get skim")
        item = adapter.map_external_to_todo(task)
        assert item.description == "Remember to get skim"

    def test_map_external_to_todo_with_metadata_in_notes(self):
        adapter = GoogleTasksAdapter(_make_config())
        meta = _encode_metadata(
            priority=Priority.HIGH,
            tags=["shopping"],
        )
        task = _sample_task(notes="Get organic" + meta)
        item = adapter.map_external_to_todo(task)
        assert item.description == "Get organic"
        assert item.tags == ["shopping"]
        assert item.priority == 3  # HIGH maps to 3


# ---------------------------------------------------------------------------
# Status mapping tests
# ---------------------------------------------------------------------------


class TestStatusMapping:

    def test_pending_maps_to_needs_action(self):
        adapter = GoogleTasksAdapter(_make_config())
        todo = Todo(id=1, text="T", status=TodoStatus.PENDING)
        assert adapter.map_todo_to_external(todo)["status"] == "needsAction"

    def test_in_progress_maps_to_needs_action(self):
        adapter = GoogleTasksAdapter(_make_config())
        todo = Todo(id=1, text="T", status=TodoStatus.IN_PROGRESS)
        assert adapter.map_todo_to_external(todo)["status"] == "needsAction"

    def test_completed_maps_to_completed(self):
        adapter = GoogleTasksAdapter(_make_config())
        todo = Todo(id=1, text="T", status=TodoStatus.COMPLETED, completed=True)
        assert adapter.map_todo_to_external(todo)["status"] == "completed"

    def test_needs_action_maps_to_not_completed(self):
        adapter = GoogleTasksAdapter(_make_config())
        item = adapter.map_external_to_todo(_sample_task(status="needsAction"))
        assert item.completed is False

    def test_completed_status_maps_to_completed(self):
        adapter = GoogleTasksAdapter(_make_config())
        item = adapter.map_external_to_todo(
            _sample_task(status="completed", completed="2025-01-01T00:00:00.000Z")
        )
        assert item.completed is True


# ---------------------------------------------------------------------------
# Fetch / create / update / delete via adapter (integration-level)
# ---------------------------------------------------------------------------


class TestAdapterCRUD:

    def _mock_auth(self):
        """Mock the authentication endpoint."""
        respx.get(BASE + "users/@me/lists").mock(
            return_value=httpx.Response(200, json={"items": [_sample_tasklist()]})
        )

    @respx.mock
    @pytest.mark.asyncio
    async def test_fetch_items(self):
        self._mock_auth()
        respx.get(BASE + "lists/@default/tasks").mock(
            return_value=httpx.Response(
                200,
                json={"items": [_sample_task(), _sample_task(task_id="task2", title="Bread")]},
            )
        )
        adapter = GoogleTasksAdapter(_make_config())
        items = await adapter.fetch_items()
        assert len(items) == 2
        assert items[0].title == "Buy milk"
        assert items[1].title == "Bread"

    @respx.mock
    @pytest.mark.asyncio
    async def test_create_item(self):
        self._mock_auth()
        respx.post(BASE + "lists/@default/tasks").mock(
            return_value=httpx.Response(200, json=_sample_task(task_id="created1"))
        )
        adapter = GoogleTasksAdapter(_make_config())
        todo = Todo(id=1, text="New task")
        ext_id = await adapter.create_item(todo)
        assert ext_id == "created1"

    @respx.mock
    @pytest.mark.asyncio
    async def test_update_item(self):
        self._mock_auth()
        respx.patch(BASE + "lists/@default/tasks/task1").mock(
            return_value=httpx.Response(200, json=_sample_task(title="Updated"))
        )
        adapter = GoogleTasksAdapter(_make_config())
        todo = Todo(id=1, text="Updated")
        result = await adapter.update_item("task1", todo)
        assert result is True

    @respx.mock
    @pytest.mark.asyncio
    async def test_delete_item(self):
        self._mock_auth()
        respx.delete(BASE + "lists/@default/tasks/task1").mock(
            return_value=httpx.Response(204)
        )
        adapter = GoogleTasksAdapter(_make_config())
        result = await adapter.delete_item("task1")
        assert result is True

    @respx.mock
    @pytest.mark.asyncio
    async def test_fetch_projects(self):
        self._mock_auth()
        respx.get(BASE + "users/@me/lists").mock(
            return_value=httpx.Response(
                200,
                json={
                    "items": [
                        _sample_tasklist("l1", "Work"),
                        _sample_tasklist("l2", "Personal"),
                    ]
                },
            )
        )
        adapter = GoogleTasksAdapter(_make_config())
        projects = await adapter.fetch_projects()
        assert projects == {"Work": "l1", "Personal": "l2"}


# ---------------------------------------------------------------------------
# Metadata helpers
# ---------------------------------------------------------------------------


class TestMetadataHelpers:

    def test_encode_decode_roundtrip(self):
        encoded = _encode_metadata(
            priority=Priority.HIGH,
            tags=["a", "b"],
            assignees=["alice"],
        )
        meta = _decode_metadata("User notes" + encoded)
        assert meta["description"] == "User notes"
        assert meta["priority"] == Priority.HIGH
        assert meta["tags"] == ["a", "b"]
        assert meta["assignees"] == ["alice"]

    def test_encode_empty(self):
        assert _encode_metadata() == ""

    def test_decode_no_meta(self):
        meta = _decode_metadata("Just plain notes")
        assert meta["description"] == "Just plain notes"
        assert meta["priority"] is None
        assert meta["tags"] == []

    def test_decode_none(self):
        meta = _decode_metadata(None)
        assert meta["description"] == ""

    def test_parse_rfc3339_valid(self):
        dt = _parse_rfc3339("2025-06-15T14:30:00.000Z")
        assert dt is not None
        assert dt.year == 2025
        assert dt.month == 6
        assert dt.tzinfo is not None

    def test_parse_rfc3339_none(self):
        assert _parse_rfc3339(None) is None

    def test_to_rfc3339_roundtrip(self):
        dt = datetime(2025, 3, 20, 8, 0, 0, tzinfo=timezone.utc)
        s = _to_rfc3339(dt)
        assert s == "2025-03-20T08:00:00.000Z"
        parsed = _parse_rfc3339(s)
        assert parsed == dt


# ---------------------------------------------------------------------------
# Required credentials
# ---------------------------------------------------------------------------


class TestCredentials:

    def test_get_required_credentials(self):
        adapter = GoogleTasksAdapter(_make_config())
        assert adapter.get_required_credentials() == ["google_access_token"]

    def test_default_tasklist_id(self):
        config = AppSyncConfig(
            provider=AppSyncProvider.GOOGLE_TASKS,
            credentials={"google_access_token": "tok"},
        )
        adapter = GoogleTasksAdapter(config)
        assert adapter.tasklist_id == "@default"

    def test_custom_tasklist_id(self):
        adapter = GoogleTasksAdapter(_make_config(tasklist_id="custom_list"))
        assert adapter.tasklist_id == "custom_list"
