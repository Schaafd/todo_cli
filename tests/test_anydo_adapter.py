"""Tests for the Any.do sync adapter."""

import pytest
import httpx
import respx
from datetime import datetime, timezone

from todo_cli.sync.providers.anydo_adapter import (
    AnyDoAPI,
    AnyDoAdapter,
    ANYDO_PRIORITY_MAP,
    ANYDO_PRIORITY_REVERSE,
    PRIORITY_ENUM_TO_ANYDO,
)
from todo_cli.sync.app_sync_adapter import (
    AuthenticationError,
    NetworkError,
    RateLimitError,
    ValidationError,
)
from todo_cli.sync.app_sync_models import (
    AppSyncProvider,
    AppSyncConfig,
    ExternalTodoItem,
)
from todo_cli.domain import Todo, Priority, TodoStatus


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_config(**overrides) -> AppSyncConfig:
    """Create a minimal AppSyncConfig for Any.do."""
    defaults = dict(
        provider=AppSyncProvider.ANY_DO,
        credentials={"anydo_token": "anydo_test_token_123"},
        settings={},
    )
    defaults.update(overrides)
    return AppSyncConfig(**defaults)


def _make_task(
    task_id: str = "task-001",
    title: str = "Test task",
    note: str = "Task description",
    status: str = "UNCHECKED",
    priority: str = "Normal",
    category_id: str = "cat-001",
    labels: list | None = None,
    due_date: int | None = None,
    created_date: int = 1704067200000,  # 2024-01-01 00:00:00 UTC in ms
    last_update_date: int = 1704153600000,  # 2024-01-02 00:00:00 UTC in ms
    completion_date: int | None = None,
) -> dict:
    """Build a fake Any.do task payload."""
    task: dict = {
        "id": task_id,
        "title": title,
        "note": note,
        "status": status,
        "priority": priority,
        "categoryId": category_id,
        "labels": labels or [],
        "createdDate": created_date,
        "lastUpdateDate": last_update_date,
    }
    if due_date is not None:
        task["dueDate"] = due_date
    if completion_date is not None:
        task["completionDate"] = completion_date
    return task


def _make_todo(**overrides) -> Todo:
    defaults = dict(
        id=1,
        text="Buy groceries",
        description="Milk and eggs",
        status=TodoStatus.PENDING,
        completed=False,
        project="inbox",
        tags=["shopping"],
        priority=Priority.HIGH,
    )
    defaults.update(overrides)
    return Todo(**defaults)


@pytest.fixture
def config():
    return _make_config()


@pytest.fixture
def adapter(config):
    return AnyDoAdapter(config)


# ---------------------------------------------------------------------------
# AnyDoAPI -- authentication
# ---------------------------------------------------------------------------

class TestAnyDoAPIAuthentication:

    @respx.mock
    @pytest.mark.asyncio
    async def test_get_user_success(self):
        respx.get("https://sm-prod2.any.do/me").mock(
            return_value=httpx.Response(200, json={"email": "test@example.com", "name": "Test"})
        )
        async with AnyDoAPI("anydo_test") as api:
            user = await api.get_user()
        assert user["email"] == "test@example.com"

    @respx.mock
    @pytest.mark.asyncio
    async def test_get_user_401(self):
        respx.get("https://sm-prod2.any.do/me").mock(
            return_value=httpx.Response(401, json={"message": "Unauthorized"})
        )
        async with AnyDoAPI("bad_token") as api:
            with pytest.raises(AuthenticationError):
                await api.get_user()

    @respx.mock
    @pytest.mark.asyncio
    async def test_get_user_403(self):
        respx.get("https://sm-prod2.any.do/me").mock(
            return_value=httpx.Response(403, json={"message": "Forbidden"})
        )
        async with AnyDoAPI("anydo_test") as api:
            with pytest.raises(AuthenticationError):
                await api.get_user()

    @respx.mock
    @pytest.mark.asyncio
    async def test_rate_limit_429(self):
        respx.get("https://sm-prod2.any.do/me").mock(
            return_value=httpx.Response(429, json={"message": "rate limit"})
        )
        async with AnyDoAPI("anydo_test") as api:
            with pytest.raises(RateLimitError):
                await api.get_user()


# ---------------------------------------------------------------------------
# AnyDoAPI -- tasks CRUD
# ---------------------------------------------------------------------------

class TestAnyDoAPITasks:

    @respx.mock
    @pytest.mark.asyncio
    async def test_get_tasks(self):
        tasks = [_make_task(task_id="t1"), _make_task(task_id="t2")]
        respx.get("https://sm-prod2.any.do/tasks").mock(
            return_value=httpx.Response(200, json=tasks)
        )
        async with AnyDoAPI("anydo_test") as api:
            result = await api.get_tasks()
        assert len(result) == 2

    @respx.mock
    @pytest.mark.asyncio
    async def test_get_tasks_with_category(self):
        tasks = [_make_task()]
        route = respx.get("https://sm-prod2.any.do/tasks").mock(
            return_value=httpx.Response(200, json=tasks)
        )
        async with AnyDoAPI("anydo_test") as api:
            result = await api.get_tasks(category_id="cat-001")
        assert route.called
        assert "categoryId" in str(route.calls[0].request.url)

    @respx.mock
    @pytest.mark.asyncio
    async def test_create_task(self):
        created = _make_task(task_id="new-task")
        respx.post("https://sm-prod2.any.do/tasks").mock(
            return_value=httpx.Response(201, json=created)
        )
        async with AnyDoAPI("anydo_test") as api:
            result = await api.create_task({"title": "New task"})
        assert result["id"] == "new-task"

    @respx.mock
    @pytest.mark.asyncio
    async def test_update_task(self):
        updated = _make_task(task_id="t1", title="Updated")
        respx.put("https://sm-prod2.any.do/tasks/t1").mock(
            return_value=httpx.Response(200, json=updated)
        )
        async with AnyDoAPI("anydo_test") as api:
            result = await api.update_task("t1", {"title": "Updated"})
        assert result["title"] == "Updated"

    @respx.mock
    @pytest.mark.asyncio
    async def test_delete_task(self):
        respx.delete("https://sm-prod2.any.do/tasks/t1").mock(
            return_value=httpx.Response(204)
        )
        async with AnyDoAPI("anydo_test") as api:
            result = await api.delete_task("t1")
        assert result == {}

    @respx.mock
    @pytest.mark.asyncio
    async def test_get_categories(self):
        cats = [{"id": "cat-1", "name": "Work"}, {"id": "cat-2", "name": "Personal"}]
        respx.get("https://sm-prod2.any.do/categories").mock(
            return_value=httpx.Response(200, json=cats)
        )
        async with AnyDoAPI("anydo_test") as api:
            result = await api.get_categories()
        assert len(result) == 2

    @respx.mock
    @pytest.mark.asyncio
    async def test_404_raises_network_error(self):
        respx.get("https://sm-prod2.any.do/tasks").mock(
            return_value=httpx.Response(404, json={"message": "Not Found"})
        )
        async with AnyDoAPI("anydo_test") as api:
            with pytest.raises(NetworkError):
                await api.get_tasks()

    @respx.mock
    @pytest.mark.asyncio
    async def test_422_raises_validation_error(self):
        respx.post("https://sm-prod2.any.do/tasks").mock(
            return_value=httpx.Response(422, json={"message": "Validation Failed"})
        )
        async with AnyDoAPI("anydo_test") as api:
            with pytest.raises(ValidationError):
                await api.create_task({"title": ""})


# ---------------------------------------------------------------------------
# Adapter -- authenticate / test_connection
# ---------------------------------------------------------------------------

class TestAnyDoAdapterAuthentication:

    @respx.mock
    @pytest.mark.asyncio
    async def test_authenticate_success(self, adapter):
        respx.get("https://sm-prod2.any.do/me").mock(
            return_value=httpx.Response(200, json={"email": "test@example.com", "name": "Test"})
        )
        result = await adapter.authenticate()
        assert result is True

    @respx.mock
    @pytest.mark.asyncio
    async def test_authenticate_failure(self, adapter):
        respx.get("https://sm-prod2.any.do/me").mock(
            return_value=httpx.Response(401, json={"message": "Unauthorized"})
        )
        with pytest.raises(AuthenticationError):
            await adapter.authenticate()

    @respx.mock
    @pytest.mark.asyncio
    async def test_authenticate_no_token(self, config):
        config.credentials = {}
        adapter = AnyDoAdapter(config)
        with pytest.raises(AuthenticationError, match="No Any.do token"):
            await adapter.authenticate()

    @respx.mock
    @pytest.mark.asyncio
    async def test_test_connection_success(self, adapter):
        respx.get("https://sm-prod2.any.do/me").mock(
            return_value=httpx.Response(200, json={"email": "test@example.com", "name": "Test"})
        )
        assert await adapter.test_connection() is True

    @respx.mock
    @pytest.mark.asyncio
    async def test_test_connection_failure(self, adapter):
        respx.get("https://sm-prod2.any.do/me").mock(
            return_value=httpx.Response(401, json={"message": "Unauthorized"})
        )
        assert await adapter.test_connection() is False

    def test_get_required_credentials(self, adapter):
        assert adapter.get_required_credentials() == ["anydo_token"]


# ---------------------------------------------------------------------------
# Adapter -- fetch_items
# ---------------------------------------------------------------------------

class TestAnyDoAdapterFetchItems:

    @respx.mock
    @pytest.mark.asyncio
    async def test_fetch_items_basic(self, adapter):
        respx.get("https://sm-prod2.any.do/me").mock(
            return_value=httpx.Response(200, json={"email": "test@example.com"})
        )
        tasks = [_make_task(task_id="t1", title="First"), _make_task(task_id="t2", title="Second")]
        respx.get("https://sm-prod2.any.do/tasks").mock(
            return_value=httpx.Response(200, json=tasks)
        )
        items = await adapter.fetch_items()
        assert len(items) == 2
        assert items[0].title == "First"
        assert items[1].title == "Second"

    @respx.mock
    @pytest.mark.asyncio
    async def test_fetch_items_with_since_filters(self, adapter):
        respx.get("https://sm-prod2.any.do/me").mock(
            return_value=httpx.Response(200, json={"email": "test@example.com"})
        )
        # One task updated before 'since', one after
        old_task = _make_task(task_id="t1", last_update_date=1700000000000)
        new_task = _make_task(task_id="t2", last_update_date=1750000000000)
        respx.get("https://sm-prod2.any.do/tasks").mock(
            return_value=httpx.Response(200, json=[old_task, new_task])
        )
        # since = 2025-01-01 => 1735689600000 ms
        since = datetime(2025, 1, 1, tzinfo=timezone.utc)
        items = await adapter.fetch_items(since=since)
        assert len(items) == 1
        assert items[0].external_id == "t2"


# ---------------------------------------------------------------------------
# Adapter -- create_item
# ---------------------------------------------------------------------------

class TestAnyDoAdapterCreateItem:

    @respx.mock
    @pytest.mark.asyncio
    async def test_create_item(self, adapter):
        respx.get("https://sm-prod2.any.do/me").mock(
            return_value=httpx.Response(200, json={"email": "test@example.com"})
        )
        respx.post("https://sm-prod2.any.do/tasks").mock(
            return_value=httpx.Response(201, json={"id": "new-task", "title": "Buy groceries"})
        )
        todo = _make_todo()
        result = await adapter.create_item(todo)
        assert result == "new-task"


# ---------------------------------------------------------------------------
# Adapter -- update_item
# ---------------------------------------------------------------------------

class TestAnyDoAdapterUpdateItem:

    @respx.mock
    @pytest.mark.asyncio
    async def test_update_item(self, adapter):
        respx.get("https://sm-prod2.any.do/me").mock(
            return_value=httpx.Response(200, json={"email": "test@example.com"})
        )
        respx.put("https://sm-prod2.any.do/tasks/t1").mock(
            return_value=httpx.Response(200, json=_make_task(task_id="t1", title="Updated"))
        )
        todo = _make_todo(text="Updated")
        result = await adapter.update_item("t1", todo)
        assert result is True


# ---------------------------------------------------------------------------
# Adapter -- delete_item
# ---------------------------------------------------------------------------

class TestAnyDoAdapterDeleteItem:

    @respx.mock
    @pytest.mark.asyncio
    async def test_delete_item_success(self, adapter):
        respx.get("https://sm-prod2.any.do/me").mock(
            return_value=httpx.Response(200, json={"email": "test@example.com"})
        )
        respx.delete("https://sm-prod2.any.do/tasks/t1").mock(
            return_value=httpx.Response(204)
        )
        result = await adapter.delete_item("t1")
        assert result is True

    @respx.mock
    @pytest.mark.asyncio
    async def test_delete_item_failure(self, adapter):
        respx.get("https://sm-prod2.any.do/me").mock(
            return_value=httpx.Response(200, json={"email": "test@example.com"})
        )
        respx.delete("https://sm-prod2.any.do/tasks/t1").mock(
            return_value=httpx.Response(500, json={"message": "Server error"})
        )
        result = await adapter.delete_item("t1")
        assert result is False


# ---------------------------------------------------------------------------
# Adapter -- fetch_projects
# ---------------------------------------------------------------------------

class TestAnyDoAdapterFetchProjects:

    @respx.mock
    @pytest.mark.asyncio
    async def test_fetch_projects(self, adapter):
        respx.get("https://sm-prod2.any.do/me").mock(
            return_value=httpx.Response(200, json={"email": "test@example.com"})
        )
        cats = [
            {"id": "cat-1", "name": "Work"},
            {"id": "cat-2", "name": "Personal"},
        ]
        respx.get("https://sm-prod2.any.do/categories").mock(
            return_value=httpx.Response(200, json=cats)
        )
        projects = await adapter.fetch_projects()
        assert projects == {"Work": "cat-1", "Personal": "cat-2"}


# ---------------------------------------------------------------------------
# Adapter -- mapping
# ---------------------------------------------------------------------------

class TestAnyDoAdapterMapping:

    def test_map_todo_to_external_basic(self, adapter):
        todo = _make_todo()
        payload = adapter.map_todo_to_external(todo)
        assert payload["title"] == "Buy groceries"
        assert payload.get("note") == "Milk and eggs"
        assert payload.get("labels") == ["shopping"]
        assert payload["status"] == "UNCHECKED"
        assert payload["priority"] == "High"

    def test_map_todo_to_external_completed(self, adapter):
        todo = _make_todo(completed=True)
        payload = adapter.map_todo_to_external(todo)
        assert payload["status"] == "CHECKED"

    def test_map_todo_to_external_with_due_date(self, adapter):
        due = datetime(2025, 12, 25, 10, 0, tzinfo=timezone.utc)
        todo = _make_todo(due_date=due)
        payload = adapter.map_todo_to_external(todo)
        assert "dueDate" in payload
        assert isinstance(payload["dueDate"], int)

    def test_map_todo_to_external_priority_mapping(self, adapter):
        for priority, expected_anydo in PRIORITY_ENUM_TO_ANYDO.items():
            todo = _make_todo(priority=priority)
            payload = adapter.map_todo_to_external(todo)
            assert payload["priority"] == expected_anydo

    def test_map_external_to_todo_basic(self, adapter):
        task = _make_task(title="My task", note="Description here")
        item = adapter.map_external_to_todo(task)
        assert isinstance(item, ExternalTodoItem)
        assert item.title == "My task"
        assert item.description == "Description here"
        assert item.provider == AppSyncProvider.ANY_DO
        assert item.external_id == "task-001"

    def test_map_external_to_todo_with_labels(self, adapter):
        task = _make_task(labels=["urgent", "work"])
        item = adapter.map_external_to_todo(task)
        assert item.tags == ["urgent", "work"]

    def test_map_external_to_todo_with_due_date(self, adapter):
        # 2025-12-25 10:00:00 UTC in ms
        due_ms = int(datetime(2025, 12, 25, 10, 0, tzinfo=timezone.utc).timestamp() * 1000)
        task = _make_task(due_date=due_ms)
        item = adapter.map_external_to_todo(task)
        assert item.due_date is not None
        assert item.due_date.year == 2025
        assert item.due_date.month == 12

    def test_map_external_to_todo_checked(self, adapter):
        task = _make_task(status="CHECKED", completion_date=1704067200000)
        item = adapter.map_external_to_todo(task)
        assert item.completed is True
        assert item.completed_at is not None

    def test_map_external_to_todo_unchecked(self, adapter):
        task = _make_task(status="UNCHECKED")
        item = adapter.map_external_to_todo(task)
        assert item.completed is False

    def test_map_external_to_todo_priority(self, adapter):
        for anydo_prio, expected_int in ANYDO_PRIORITY_MAP.items():
            task = _make_task(priority=anydo_prio)
            item = adapter.map_external_to_todo(task)
            assert item.priority == expected_int

    def test_map_external_to_todo_timestamps(self, adapter):
        task = _make_task(
            created_date=1704067200000,
            last_update_date=1704153600000,
        )
        item = adapter.map_external_to_todo(task)
        assert item.created_at is not None
        assert item.updated_at is not None

    def test_get_supported_features(self, adapter):
        features = adapter.get_supported_features()
        assert "create" in features
        assert "priorities" in features
        assert "tags" in features
