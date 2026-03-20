"""Tests for Microsoft Todo sync adapter."""

import pytest
import httpx
import respx
from datetime import datetime, timezone

from todo_cli.sync.providers.microsoft_todo_adapter import (
    MicrosoftGraphAPI,
    MicrosoftTodoAdapter,
    _MS_IMPORTANCE_TO_PRIORITY,
    _PRIORITY_ENUM_TO_MS_IMPORTANCE,
    _MS_STATUS_TO_STATUS,
    _STATUS_TO_MS_STATUS,
)
from todo_cli.sync.app_sync_adapter import (
    AuthenticationError,
    NetworkError,
    RateLimitError,
)
from todo_cli.sync.app_sync_models import (
    AppSyncProvider,
    AppSyncConfig,
    ExternalTodoItem,
)
from todo_cli.domain import Todo, Priority, TodoStatus


BASE_URL = "https://graph.microsoft.com/v1.0/"
TASK_LIST_ID = "list-abc-123"
TASK_ID = "task-xyz-456"


def _make_config(**overrides):
    """Create a test AppSyncConfig for Microsoft Todo."""
    defaults = dict(
        provider=AppSyncProvider.MICROSOFT_TODO,
        credentials={"ms_access_token": "test-token-123"},
        settings={"ms_task_list_id": TASK_LIST_ID},
    )
    defaults.update(overrides)
    return AppSyncConfig(**defaults)


def _sample_ms_task(
    task_id=TASK_ID,
    title="Buy groceries",
    status="notStarted",
    importance="normal",
    body_content="Milk, eggs, bread",
    categories=None,
    due=None,
    created="2025-01-15T10:00:00Z",
    modified="2025-01-15T12:00:00Z",
    completed_dt=None,
):
    """Build a sample Microsoft Todo task dict."""
    task = {
        "id": task_id,
        "title": title,
        "status": status,
        "importance": importance,
        "body": {"content": body_content, "contentType": "text"},
        "categories": categories or [],
        "createdDateTime": created,
        "lastModifiedDateTime": modified,
    }
    if due:
        task["dueDateTime"] = {"dateTime": due, "timeZone": "UTC"}
    if completed_dt:
        task["completedDateTime"] = {
            "dateTime": completed_dt,
            "timeZone": "UTC",
        }
    return task


def _sample_todo(**overrides):
    """Create a sample local Todo."""
    defaults = dict(
        id=1,
        text="Buy groceries",
        description="Milk, eggs, bread",
        priority=Priority.MEDIUM,
        status=TodoStatus.PENDING,
        tags=["shopping", "errands"],
        due_date=datetime(2025, 3, 1, 12, 0, 0, tzinfo=timezone.utc),
    )
    defaults.update(overrides)
    return Todo(**defaults)


# ---------------------------------------------------------------------------
# MicrosoftGraphAPI unit tests
# ---------------------------------------------------------------------------


class TestMicrosoftGraphAPI:
    """Tests for the low-level Graph API client."""

    @respx.mock
    @pytest.mark.asyncio
    async def test_get_me(self):
        respx.get(f"{BASE_URL}me").mock(
            return_value=httpx.Response(
                200, json={"id": "user-1", "displayName": "Test User"}
            )
        )
        async with MicrosoftGraphAPI("tok") as api:
            result = await api.get_me()
        assert result["id"] == "user-1"

    @respx.mock
    @pytest.mark.asyncio
    async def test_get_task_lists(self):
        respx.get(f"{BASE_URL}me/todo/lists").mock(
            return_value=httpx.Response(
                200,
                json={
                    "value": [
                        {"id": "l1", "displayName": "Tasks"},
                        {"id": "l2", "displayName": "Work"},
                    ]
                },
            )
        )
        async with MicrosoftGraphAPI("tok") as api:
            lists = await api.get_task_lists()
        assert len(lists) == 2
        assert lists[0]["displayName"] == "Tasks"

    @respx.mock
    @pytest.mark.asyncio
    async def test_get_tasks(self):
        respx.get(f"{BASE_URL}me/todo/lists/{TASK_LIST_ID}/tasks").mock(
            return_value=httpx.Response(
                200, json={"value": [_sample_ms_task()]}
            )
        )
        async with MicrosoftGraphAPI("tok") as api:
            tasks = await api.get_tasks(TASK_LIST_ID)
        assert len(tasks) == 1
        assert tasks[0]["title"] == "Buy groceries"

    @respx.mock
    @pytest.mark.asyncio
    async def test_create_task(self):
        respx.post(f"{BASE_URL}me/todo/lists/{TASK_LIST_ID}/tasks").mock(
            return_value=httpx.Response(
                201, json={"id": "new-task", "title": "New task"}
            )
        )
        async with MicrosoftGraphAPI("tok") as api:
            result = await api.create_task(
                TASK_LIST_ID, {"title": "New task"}
            )
        assert result["id"] == "new-task"

    @respx.mock
    @pytest.mark.asyncio
    async def test_update_task(self):
        respx.patch(
            f"{BASE_URL}me/todo/lists/{TASK_LIST_ID}/tasks/{TASK_ID}"
        ).mock(
            return_value=httpx.Response(
                200, json={"id": TASK_ID, "title": "Updated"}
            )
        )
        async with MicrosoftGraphAPI("tok") as api:
            result = await api.update_task(
                TASK_LIST_ID, TASK_ID, {"title": "Updated"}
            )
        assert result["title"] == "Updated"

    @respx.mock
    @pytest.mark.asyncio
    async def test_delete_task(self):
        respx.delete(
            f"{BASE_URL}me/todo/lists/{TASK_LIST_ID}/tasks/{TASK_ID}"
        ).mock(return_value=httpx.Response(204))
        async with MicrosoftGraphAPI("tok") as api:
            result = await api.delete_task(TASK_LIST_ID, TASK_ID)
        assert result == {}

    @respx.mock
    @pytest.mark.asyncio
    async def test_auth_error_401(self):
        respx.get(f"{BASE_URL}me").mock(
            return_value=httpx.Response(401, json={"error": "unauthorized"})
        )
        async with MicrosoftGraphAPI("bad-tok") as api:
            with pytest.raises(AuthenticationError):
                await api.get_me()

    @respx.mock
    @pytest.mark.asyncio
    async def test_rate_limit_429(self):
        respx.get(f"{BASE_URL}me").mock(
            return_value=httpx.Response(429, json={"error": "rate limited"})
        )
        async with MicrosoftGraphAPI("tok") as api:
            with pytest.raises(RateLimitError):
                await api.get_me()

    @respx.mock
    @pytest.mark.asyncio
    async def test_network_error_500(self):
        respx.get(f"{BASE_URL}me").mock(
            return_value=httpx.Response(500, text="Internal Server Error")
        )
        async with MicrosoftGraphAPI("tok") as api:
            with pytest.raises(NetworkError):
                await api.get_me()


# ---------------------------------------------------------------------------
# MicrosoftTodoAdapter tests
# ---------------------------------------------------------------------------


class TestMicrosoftTodoAdapterCredentials:
    """Test credential and config handling."""

    def test_get_required_credentials(self):
        adapter = MicrosoftTodoAdapter(_make_config())
        assert adapter.get_required_credentials() == ["ms_access_token"]

    def test_access_token_read_from_config(self):
        adapter = MicrosoftTodoAdapter(_make_config())
        assert adapter.access_token == "test-token-123"

    def test_task_list_id_from_settings(self):
        adapter = MicrosoftTodoAdapter(_make_config())
        assert adapter.task_list_id == TASK_LIST_ID


class TestAuthentication:
    """Test authentication flows."""

    @respx.mock
    @pytest.mark.asyncio
    async def test_authenticate_success(self):
        respx.get(f"{BASE_URL}me").mock(
            return_value=httpx.Response(
                200, json={"id": "u1", "displayName": "Alice"}
            )
        )
        adapter = MicrosoftTodoAdapter(_make_config())
        result = await adapter.authenticate()
        assert result is True

    @respx.mock
    @pytest.mark.asyncio
    async def test_authenticate_failure(self):
        respx.get(f"{BASE_URL}me").mock(
            return_value=httpx.Response(401, json={"error": "bad"})
        )
        adapter = MicrosoftTodoAdapter(_make_config())
        with pytest.raises(AuthenticationError):
            await adapter.authenticate()

    @pytest.mark.asyncio
    async def test_authenticate_no_token(self):
        config = _make_config(credentials={})
        adapter = MicrosoftTodoAdapter(config)
        with pytest.raises(AuthenticationError):
            await adapter.authenticate()

    @respx.mock
    @pytest.mark.asyncio
    async def test_test_connection_success(self):
        respx.get(f"{BASE_URL}me").mock(
            return_value=httpx.Response(
                200, json={"id": "u1", "displayName": "Alice"}
            )
        )
        adapter = MicrosoftTodoAdapter(_make_config())
        assert await adapter.test_connection() is True

    @respx.mock
    @pytest.mark.asyncio
    async def test_test_connection_failure(self):
        respx.get(f"{BASE_URL}me").mock(
            return_value=httpx.Response(401, json={"error": "bad"})
        )
        adapter = MicrosoftTodoAdapter(_make_config())
        assert await adapter.test_connection() is False


class TestFetchItems:
    """Test fetching tasks from Microsoft Todo."""

    def _mock_auth(self):
        respx.get(f"{BASE_URL}me").mock(
            return_value=httpx.Response(
                200, json={"id": "u1", "displayName": "Alice"}
            )
        )

    @respx.mock
    @pytest.mark.asyncio
    async def test_fetch_items(self):
        self._mock_auth()
        tasks = [
            _sample_ms_task(task_id="t1", title="Task 1"),
            _sample_ms_task(task_id="t2", title="Task 2"),
        ]
        respx.get(f"{BASE_URL}me/todo/lists/{TASK_LIST_ID}/tasks").mock(
            return_value=httpx.Response(200, json={"value": tasks})
        )
        adapter = MicrosoftTodoAdapter(_make_config())
        items = await adapter.fetch_items()
        assert len(items) == 2
        assert items[0].external_id == "t1"
        assert items[1].title == "Task 2"

    @respx.mock
    @pytest.mark.asyncio
    async def test_fetch_items_empty(self):
        self._mock_auth()
        respx.get(f"{BASE_URL}me/todo/lists/{TASK_LIST_ID}/tasks").mock(
            return_value=httpx.Response(200, json={"value": []})
        )
        adapter = MicrosoftTodoAdapter(_make_config())
        items = await adapter.fetch_items()
        assert items == []


class TestCreateItem:
    """Test creating tasks in Microsoft Todo."""

    def _mock_auth(self):
        respx.get(f"{BASE_URL}me").mock(
            return_value=httpx.Response(
                200, json={"id": "u1", "displayName": "Alice"}
            )
        )

    @respx.mock
    @pytest.mark.asyncio
    async def test_create_item(self):
        self._mock_auth()
        respx.post(f"{BASE_URL}me/todo/lists/{TASK_LIST_ID}/tasks").mock(
            return_value=httpx.Response(
                201, json={"id": "new-id", "title": "Buy groceries"}
            )
        )
        adapter = MicrosoftTodoAdapter(_make_config())
        todo = _sample_todo()
        task_id = await adapter.create_item(todo)
        assert task_id == "new-id"


class TestUpdateItem:
    """Test updating tasks in Microsoft Todo."""

    def _mock_auth(self):
        respx.get(f"{BASE_URL}me").mock(
            return_value=httpx.Response(
                200, json={"id": "u1", "displayName": "Alice"}
            )
        )

    @respx.mock
    @pytest.mark.asyncio
    async def test_update_item(self):
        self._mock_auth()
        respx.patch(
            f"{BASE_URL}me/todo/lists/{TASK_LIST_ID}/tasks/{TASK_ID}"
        ).mock(
            return_value=httpx.Response(
                200, json={"id": TASK_ID, "title": "Updated"}
            )
        )
        adapter = MicrosoftTodoAdapter(_make_config())
        todo = _sample_todo(text="Updated")
        result = await adapter.update_item(TASK_ID, todo)
        assert result is True


class TestDeleteItem:
    """Test deleting tasks from Microsoft Todo."""

    def _mock_auth(self):
        respx.get(f"{BASE_URL}me").mock(
            return_value=httpx.Response(
                200, json={"id": "u1", "displayName": "Alice"}
            )
        )

    @respx.mock
    @pytest.mark.asyncio
    async def test_delete_item(self):
        self._mock_auth()
        respx.delete(
            f"{BASE_URL}me/todo/lists/{TASK_LIST_ID}/tasks/{TASK_ID}"
        ).mock(return_value=httpx.Response(204))
        adapter = MicrosoftTodoAdapter(_make_config())
        result = await adapter.delete_item(TASK_ID)
        assert result is True

    @respx.mock
    @pytest.mark.asyncio
    async def test_delete_item_failure(self):
        self._mock_auth()
        respx.delete(
            f"{BASE_URL}me/todo/lists/{TASK_LIST_ID}/tasks/{TASK_ID}"
        ).mock(return_value=httpx.Response(500, text="error"))
        adapter = MicrosoftTodoAdapter(_make_config())
        result = await adapter.delete_item(TASK_ID)
        assert result is False


class TestFetchProjects:
    """Test fetching task lists (projects) from Microsoft Todo."""

    def _mock_auth(self):
        respx.get(f"{BASE_URL}me").mock(
            return_value=httpx.Response(
                200, json={"id": "u1", "displayName": "Alice"}
            )
        )

    @respx.mock
    @pytest.mark.asyncio
    async def test_fetch_projects(self):
        self._mock_auth()
        respx.get(f"{BASE_URL}me/todo/lists").mock(
            return_value=httpx.Response(
                200,
                json={
                    "value": [
                        {"id": "l1", "displayName": "Tasks"},
                        {"id": "l2", "displayName": "Work"},
                    ]
                },
            )
        )
        adapter = MicrosoftTodoAdapter(_make_config())
        projects = await adapter.fetch_projects()
        assert projects == {"Tasks": "l1", "Work": "l2"}


# ---------------------------------------------------------------------------
# Field mapping tests
# ---------------------------------------------------------------------------


class TestPriorityMapping:
    """Test priority mapping in both directions."""

    def test_ms_importance_to_priority_int(self):
        assert _MS_IMPORTANCE_TO_PRIORITY["low"] == 1
        assert _MS_IMPORTANCE_TO_PRIORITY["normal"] == 2
        assert _MS_IMPORTANCE_TO_PRIORITY["high"] == 3

    def test_priority_enum_to_ms_importance(self):
        assert _PRIORITY_ENUM_TO_MS_IMPORTANCE[Priority.LOW] == "low"
        assert _PRIORITY_ENUM_TO_MS_IMPORTANCE[Priority.MEDIUM] == "normal"
        assert _PRIORITY_ENUM_TO_MS_IMPORTANCE[Priority.HIGH] == "high"
        assert _PRIORITY_ENUM_TO_MS_IMPORTANCE[Priority.CRITICAL] == "high"

    def test_map_todo_to_external_priority(self):
        adapter = MicrosoftTodoAdapter(_make_config())
        for prio, expected_imp in [
            (Priority.LOW, "low"),
            (Priority.MEDIUM, "normal"),
            (Priority.HIGH, "high"),
            (Priority.CRITICAL, "high"),
        ]:
            todo = _sample_todo(priority=prio)
            data = adapter.map_todo_to_external(todo)
            assert data["importance"] == expected_imp, f"Failed for {prio}"

    def test_map_external_to_todo_priority(self):
        adapter = MicrosoftTodoAdapter(_make_config())
        for imp, expected_int in [
            ("low", 1),
            ("normal", 2),
            ("high", 3),
        ]:
            task = _sample_ms_task(importance=imp)
            item = adapter.map_external_to_todo(task)
            assert item.priority == expected_int, f"Failed for {imp}"


class TestStatusMapping:
    """Test status mapping in both directions."""

    def test_ms_status_to_todo_status(self):
        assert _MS_STATUS_TO_STATUS["notStarted"] == TodoStatus.PENDING
        assert _MS_STATUS_TO_STATUS["inProgress"] == TodoStatus.IN_PROGRESS
        assert _MS_STATUS_TO_STATUS["completed"] == TodoStatus.COMPLETED

    def test_todo_status_to_ms_status(self):
        assert _STATUS_TO_MS_STATUS[TodoStatus.PENDING] == "notStarted"
        assert _STATUS_TO_MS_STATUS[TodoStatus.IN_PROGRESS] == "inProgress"
        assert _STATUS_TO_MS_STATUS[TodoStatus.COMPLETED] == "completed"

    def test_map_todo_to_external_status(self):
        adapter = MicrosoftTodoAdapter(_make_config())
        for status, expected_ms in [
            (TodoStatus.PENDING, "notStarted"),
            (TodoStatus.IN_PROGRESS, "inProgress"),
            (TodoStatus.COMPLETED, "completed"),
        ]:
            todo = _sample_todo(status=status)
            data = adapter.map_todo_to_external(todo)
            assert data["status"] == expected_ms

    def test_map_external_to_todo_completed(self):
        adapter = MicrosoftTodoAdapter(_make_config())
        task = _sample_ms_task(status="completed")
        item = adapter.map_external_to_todo(task)
        assert item.completed is True

    def test_map_external_to_todo_not_started(self):
        adapter = MicrosoftTodoAdapter(_make_config())
        task = _sample_ms_task(status="notStarted")
        item = adapter.map_external_to_todo(task)
        assert item.completed is False


class TestFieldMapping:
    """Test full field mapping in both directions."""

    def test_map_todo_to_external_all_fields(self):
        adapter = MicrosoftTodoAdapter(_make_config())
        todo = _sample_todo()
        data = adapter.map_todo_to_external(todo)

        assert data["title"] == "Buy groceries"
        assert data["body"] == {
            "content": "Milk, eggs, bread",
            "contentType": "text",
        }
        assert data["importance"] == "normal"
        assert data["status"] == "notStarted"
        assert data["categories"] == ["shopping", "errands"]
        assert "dueDateTime" in data
        assert data["dueDateTime"]["timeZone"] == "UTC"

    def test_map_todo_to_external_no_description(self):
        adapter = MicrosoftTodoAdapter(_make_config())
        todo = _sample_todo(description="")
        data = adapter.map_todo_to_external(todo)
        assert "body" not in data

    def test_map_todo_to_external_no_due_date(self):
        adapter = MicrosoftTodoAdapter(_make_config())
        todo = _sample_todo(due_date=None)
        data = adapter.map_todo_to_external(todo)
        assert "dueDateTime" not in data

    def test_map_todo_to_external_no_tags(self):
        adapter = MicrosoftTodoAdapter(_make_config())
        todo = _sample_todo(tags=[])
        data = adapter.map_todo_to_external(todo)
        assert "categories" not in data

    def test_map_external_to_todo_all_fields(self):
        adapter = MicrosoftTodoAdapter(_make_config())
        task = _sample_ms_task(
            due="2025-03-01T12:00:00.0000000",
            categories=["shopping", "errands"],
        )
        item = adapter.map_external_to_todo(task)

        assert item.external_id == TASK_ID
        assert item.provider == AppSyncProvider.MICROSOFT_TODO
        assert item.title == "Buy groceries"
        assert item.description == "Milk, eggs, bread"
        assert item.priority == 2
        assert item.tags == ["shopping", "errands"]
        assert item.due_date is not None
        assert item.due_date.year == 2025
        assert item.due_date.month == 3
        assert item.created_at is not None
        assert item.updated_at is not None
        assert item.raw_data == task

    def test_map_external_to_todo_no_body(self):
        adapter = MicrosoftTodoAdapter(_make_config())
        task = _sample_ms_task()
        task.pop("body")
        item = adapter.map_external_to_todo(task)
        assert item.description == ""

    def test_map_external_to_todo_completed_datetime(self):
        adapter = MicrosoftTodoAdapter(_make_config())
        task = _sample_ms_task(
            status="completed",
            completed_dt="2025-02-15T14:30:00.0000000",
        )
        item = adapter.map_external_to_todo(task)
        assert item.completed is True
        assert item.completed_at is not None
        assert item.completed_at.month == 2
        assert item.completed_at.day == 15

    def test_roundtrip_title(self):
        """Title survives a local->external->local round trip."""
        adapter = MicrosoftTodoAdapter(_make_config())
        todo = _sample_todo(text="Round trip test")
        data = adapter.map_todo_to_external(todo)
        # Simulate the API returning the data it received
        task = _sample_ms_task(title=data["title"])
        item = adapter.map_external_to_todo(task)
        assert item.title == "Round trip test"
