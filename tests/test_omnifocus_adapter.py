"""Tests for the OmniFocus sync adapter."""

import pytest
import httpx
import respx
from datetime import datetime, timezone

from todo_cli.sync.providers.omnifocus_adapter import (
    OmniFocusAPI,
    OmniFocusAdapter,
    INTERNAL_PRIORITY_TO_FLAGGED,
    OMNIFOCUS_FLAGGED_PRIORITY,
    OMNIFOCUS_UNFLAGGED_PRIORITY,
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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

BASE = "http://localhost:8080/"


def _make_config(**overrides) -> AppSyncConfig:
    defaults = dict(
        provider=AppSyncProvider.OMNIFOCUS,
        credentials={"omnifocus_api_key": "test_api_key"},
        settings={"omnifocus_base_url": "http://localhost:8080"},
    )
    defaults.update(overrides)
    return AppSyncConfig(**defaults)


def _make_task(
    task_id: str = "task_1",
    name: str = "Buy milk",
    note: str = "From the store",
    flagged: bool = False,
    completed: bool = False,
    tags: list | None = None,
    project: str | None = "proj_abc",
    due_date: str | None = "2025-06-01T10:00:00+00:00",
    created_date: str = "2025-01-01T00:00:00+00:00",
    modified_date: str = "2025-01-02T00:00:00+00:00",
) -> dict:
    return {
        "id": task_id,
        "name": name,
        "note": note,
        "flagged": flagged,
        "completed": completed,
        "tags": tags if tags is not None else ["shopping"],
        "project": project,
        "dueDate": due_date,
        "createdDate": created_date,
        "modifiedDate": modified_date,
    }


def _make_project(pid: str = "proj_abc", name: str = "Inbox") -> dict:
    return {"id": pid, "name": name}


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
    return OmniFocusAdapter(config)


# ---------------------------------------------------------------------------
# OmniFocusAPI - authentication
# ---------------------------------------------------------------------------


class TestOmniFocusAPIAuthentication:
    @respx.mock
    @pytest.mark.asyncio
    async def test_auth_success(self):
        respx.get(f"{BASE}projects").mock(
            return_value=httpx.Response(200, json=[_make_project()])
        )
        async with OmniFocusAPI("good_key") as api:
            projects = await api.get_projects()
            assert len(projects) == 1

    @respx.mock
    @pytest.mark.asyncio
    async def test_auth_invalid_key(self):
        respx.get(f"{BASE}projects").mock(
            return_value=httpx.Response(401, text="Unauthorized")
        )
        async with OmniFocusAPI("bad_key") as api:
            with pytest.raises(AuthenticationError):
                await api.get_projects()

    @respx.mock
    @pytest.mark.asyncio
    async def test_auth_forbidden(self):
        respx.get(f"{BASE}projects").mock(
            return_value=httpx.Response(403, text="Forbidden")
        )
        async with OmniFocusAPI("bad_key") as api:
            with pytest.raises(AuthenticationError):
                await api.get_projects()

    @respx.mock
    @pytest.mark.asyncio
    async def test_rate_limit(self):
        respx.get(f"{BASE}projects").mock(
            return_value=httpx.Response(429, text="Too Many Requests")
        )
        async with OmniFocusAPI("key") as api:
            with pytest.raises(RateLimitError):
                await api.get_projects()


# ---------------------------------------------------------------------------
# OmniFocusAPI - tasks
# ---------------------------------------------------------------------------


class TestOmniFocusAPITasks:
    @respx.mock
    @pytest.mark.asyncio
    async def test_get_tasks(self):
        respx.get(f"{BASE}tasks").mock(
            return_value=httpx.Response(200, json=[_make_task()])
        )
        async with OmniFocusAPI("key") as api:
            tasks = await api.get_tasks()
            assert len(tasks) == 1
            assert tasks[0]["name"] == "Buy milk"

    @respx.mock
    @pytest.mark.asyncio
    async def test_get_tasks_with_project(self):
        respx.get(f"{BASE}tasks", params={"projectId": "proj_abc"}).mock(
            return_value=httpx.Response(200, json=[_make_task()])
        )
        async with OmniFocusAPI("key") as api:
            tasks = await api.get_tasks(project_id="proj_abc")
            assert len(tasks) == 1

    @respx.mock
    @pytest.mark.asyncio
    async def test_create_task(self):
        respx.post(f"{BASE}tasks").mock(
            return_value=httpx.Response(
                200, json={"id": "task_new", "name": "New"}
            )
        )
        async with OmniFocusAPI("key") as api:
            result = await api.create_task({"name": "New"})
            assert result["id"] == "task_new"

    @respx.mock
    @pytest.mark.asyncio
    async def test_update_task(self):
        respx.put(f"{BASE}tasks/task_1").mock(
            return_value=httpx.Response(
                200, json={"id": "task_1", "name": "Updated"}
            )
        )
        async with OmniFocusAPI("key") as api:
            result = await api.update_task("task_1", {"name": "Updated"})
            assert result["name"] == "Updated"

    @respx.mock
    @pytest.mark.asyncio
    async def test_complete_task(self):
        respx.post(f"{BASE}tasks/task_1/complete").mock(
            return_value=httpx.Response(200, json={})
        )
        async with OmniFocusAPI("key") as api:
            result = await api.complete_task("task_1")
            assert result == {}

    @respx.mock
    @pytest.mark.asyncio
    async def test_delete_task(self):
        respx.delete(f"{BASE}tasks/task_1").mock(
            return_value=httpx.Response(200, json={})
        )
        async with OmniFocusAPI("key") as api:
            result = await api.delete_task("task_1")
            assert result == {}

    @respx.mock
    @pytest.mark.asyncio
    async def test_server_error(self):
        respx.post(f"{BASE}tasks").mock(
            return_value=httpx.Response(500, text="Internal Server Error")
        )
        async with OmniFocusAPI("key") as api:
            with pytest.raises(NetworkError):
                await api.create_task({"name": "Fail"})

    @respx.mock
    @pytest.mark.asyncio
    async def test_get_tags(self):
        respx.get(f"{BASE}tags").mock(
            return_value=httpx.Response(
                200, json=[{"id": "t1", "name": "errand"}]
            )
        )
        async with OmniFocusAPI("key") as api:
            tags = await api.get_tags()
            assert len(tags) == 1
            assert tags[0]["name"] == "errand"

    @respx.mock
    @pytest.mark.asyncio
    async def test_204_response(self):
        respx.delete(f"{BASE}tasks/task_1").mock(
            return_value=httpx.Response(204)
        )
        async with OmniFocusAPI("key") as api:
            result = await api.delete_task("task_1")
            assert result == {}


# ---------------------------------------------------------------------------
# OmniFocusAPI - projects
# ---------------------------------------------------------------------------


class TestOmniFocusAPIProjects:
    @respx.mock
    @pytest.mark.asyncio
    async def test_get_projects(self):
        respx.get(f"{BASE}projects").mock(
            return_value=httpx.Response(
                200,
                json=[
                    _make_project("p1", "Work"),
                    _make_project("p2", "Personal"),
                ],
            )
        )
        async with OmniFocusAPI("key") as api:
            projects = await api.get_projects()
            assert len(projects) == 2
            assert projects[0]["name"] == "Work"


# ---------------------------------------------------------------------------
# OmniFocusAdapter - authentication
# ---------------------------------------------------------------------------


class TestOmniFocusAdapterAuth:
    @respx.mock
    @pytest.mark.asyncio
    async def test_authenticate_success(self, adapter):
        respx.get(f"{BASE}projects").mock(
            return_value=httpx.Response(200, json=[_make_project()])
        )
        result = await adapter.authenticate()
        assert result is True

    @respx.mock
    @pytest.mark.asyncio
    async def test_authenticate_failure(self, adapter):
        respx.get(f"{BASE}projects").mock(
            return_value=httpx.Response(401, text="Unauthorized")
        )
        with pytest.raises(AuthenticationError):
            await adapter.authenticate()

    @pytest.mark.asyncio
    async def test_authenticate_no_key(self):
        config = _make_config(credentials={})
        adp = OmniFocusAdapter(config)
        with pytest.raises(AuthenticationError, match="No OmniFocus API key"):
            await adp.authenticate()

    @respx.mock
    @pytest.mark.asyncio
    async def test_test_connection_success(self, adapter):
        respx.get(f"{BASE}projects").mock(
            return_value=httpx.Response(200, json=[_make_project()])
        )
        assert await adapter.test_connection() is True

    @respx.mock
    @pytest.mark.asyncio
    async def test_test_connection_failure(self, adapter):
        respx.get(f"{BASE}projects").mock(
            return_value=httpx.Response(401, text="Unauthorized")
        )
        assert await adapter.test_connection() is False

    def test_required_credentials(self, adapter):
        assert adapter.get_required_credentials() == ["omnifocus_api_key"]


# ---------------------------------------------------------------------------
# OmniFocusAdapter - fetch items & mapping
# ---------------------------------------------------------------------------


class TestOmniFocusAdapterFetch:
    @respx.mock
    @pytest.mark.asyncio
    async def test_fetch_items(self, adapter):
        respx.get(f"{BASE}projects").mock(
            return_value=httpx.Response(
                200, json=[_make_project("proj_abc", "Inbox")]
            )
        )
        respx.get(f"{BASE}tasks").mock(
            return_value=httpx.Response(200, json=[_make_task()])
        )
        items = await adapter.fetch_items()
        assert len(items) == 1
        item = items[0]
        assert item.title == "Buy milk"
        assert item.description == "From the store"
        assert item.provider == AppSyncProvider.OMNIFOCUS
        assert item.tags == ["shopping"]
        assert item.completed is False

    @respx.mock
    @pytest.mark.asyncio
    async def test_fetch_items_completed(self, adapter):
        respx.get(f"{BASE}projects").mock(
            return_value=httpx.Response(200, json=[_make_project()])
        )
        respx.get(f"{BASE}tasks").mock(
            return_value=httpx.Response(
                200, json=[_make_task(completed=True)]
            )
        )
        items = await adapter.fetch_items()
        assert items[0].completed is True


# ---------------------------------------------------------------------------
# OmniFocusAdapter - create / update / delete
# ---------------------------------------------------------------------------


class TestOmniFocusAdapterCRUD:
    @respx.mock
    @pytest.mark.asyncio
    async def test_create_item(self, adapter):
        respx.get(f"{BASE}projects").mock(
            return_value=httpx.Response(200, json=[_make_project()])
        )
        respx.post(f"{BASE}tasks").mock(
            return_value=httpx.Response(
                200, json={"id": "task_new", "name": "Buy groceries"}
            )
        )
        todo = _make_todo()
        task_id = await adapter.create_item(todo)
        assert task_id == "task_new"

    @respx.mock
    @pytest.mark.asyncio
    async def test_update_item(self, adapter):
        respx.get(f"{BASE}projects").mock(
            return_value=httpx.Response(200, json=[_make_project()])
        )
        respx.put(f"{BASE}tasks/task_1").mock(
            return_value=httpx.Response(
                200, json={"id": "task_1", "name": "Updated"}
            )
        )
        todo = _make_todo()
        result = await adapter.update_item("task_1", todo)
        assert result is True

    @respx.mock
    @pytest.mark.asyncio
    async def test_update_item_completed(self, adapter):
        respx.get(f"{BASE}projects").mock(
            return_value=httpx.Response(200, json=[_make_project()])
        )
        respx.put(f"{BASE}tasks/task_1").mock(
            return_value=httpx.Response(200, json={"id": "task_1"})
        )
        respx.post(f"{BASE}tasks/task_1/complete").mock(
            return_value=httpx.Response(200, json={})
        )
        todo = _make_todo(completed=True, status=TodoStatus.COMPLETED)
        result = await adapter.update_item("task_1", todo)
        assert result is True

    @respx.mock
    @pytest.mark.asyncio
    async def test_delete_item(self, adapter):
        respx.get(f"{BASE}projects").mock(
            return_value=httpx.Response(200, json=[_make_project()])
        )
        respx.delete(f"{BASE}tasks/task_1").mock(
            return_value=httpx.Response(200, json={})
        )
        result = await adapter.delete_item("task_1")
        assert result is True

    @respx.mock
    @pytest.mark.asyncio
    async def test_delete_item_failure(self, adapter):
        respx.get(f"{BASE}projects").mock(
            return_value=httpx.Response(200, json=[_make_project()])
        )
        respx.delete(f"{BASE}tasks/task_1").mock(
            return_value=httpx.Response(500, text="Server Error")
        )
        result = await adapter.delete_item("task_1")
        assert result is False


# ---------------------------------------------------------------------------
# OmniFocusAdapter - projects
# ---------------------------------------------------------------------------


class TestOmniFocusAdapterProjects:
    @respx.mock
    @pytest.mark.asyncio
    async def test_fetch_projects(self, adapter):
        respx.get(f"{BASE}projects").mock(
            return_value=httpx.Response(
                200,
                json=[
                    _make_project("p1", "Work"),
                    _make_project("p2", "Personal"),
                ],
            )
        )
        projects = await adapter.fetch_projects()
        assert projects == {"Work": "p1", "Personal": "p2"}


# ---------------------------------------------------------------------------
# Priority / flagged mapping
# ---------------------------------------------------------------------------


class TestPriorityMapping:
    def test_high_is_flagged(self):
        assert INTERNAL_PRIORITY_TO_FLAGGED[Priority.HIGH] is True

    def test_critical_is_flagged(self):
        assert INTERNAL_PRIORITY_TO_FLAGGED[Priority.CRITICAL] is True

    def test_medium_is_not_flagged(self):
        assert INTERNAL_PRIORITY_TO_FLAGGED[Priority.MEDIUM] is False

    def test_low_is_not_flagged(self):
        assert INTERNAL_PRIORITY_TO_FLAGGED[Priority.LOW] is False

    def test_flagged_priority_constant(self):
        assert OMNIFOCUS_FLAGGED_PRIORITY == Priority.HIGH

    def test_unflagged_priority_constant(self):
        assert OMNIFOCUS_UNFLAGGED_PRIORITY == Priority.MEDIUM


# ---------------------------------------------------------------------------
# Field mapping
# ---------------------------------------------------------------------------


class TestFieldMapping:
    def test_map_todo_to_external(self, adapter):
        todo = _make_todo(
            due_date=datetime(2025, 6, 15, 10, 0, tzinfo=timezone.utc)
        )
        data = adapter.map_todo_to_external(todo)

        assert data["name"] == "Buy groceries"
        assert data["note"] == "Milk and eggs"
        assert data["flagged"] is True  # HIGH -> flagged
        assert data["tags"] == ["shopping"]
        assert data["completed"] is False
        assert "dueDate" in data

    def test_map_todo_to_external_completed(self, adapter):
        todo = _make_todo(completed=True, status=TodoStatus.COMPLETED)
        data = adapter.map_todo_to_external(todo)
        assert data["completed"] is True

    def test_map_todo_to_external_no_description(self, adapter):
        todo = _make_todo(description="")
        data = adapter.map_todo_to_external(todo)
        assert "note" not in data

    def test_map_todo_to_external_low_priority(self, adapter):
        todo = _make_todo(priority=Priority.LOW)
        data = adapter.map_todo_to_external(todo)
        assert data["flagged"] is False

    def test_map_external_to_todo(self, adapter):
        task = _make_task()
        item = adapter.map_external_to_todo(task)

        assert isinstance(item, ExternalTodoItem)
        assert item.external_id == "task_1"
        assert item.title == "Buy milk"
        assert item.description == "From the store"
        assert item.tags == ["shopping"]
        assert item.completed is False
        assert item.provider == AppSyncProvider.OMNIFOCUS

    def test_map_external_to_todo_completed(self, adapter):
        task = _make_task(completed=True)
        item = adapter.map_external_to_todo(task)
        assert item.completed is True

    def test_map_external_to_todo_no_due_date(self, adapter):
        task = _make_task(due_date=None)
        item = adapter.map_external_to_todo(task)
        assert item.due_date is None

    def test_map_external_to_todo_with_due_date(self, adapter):
        task = _make_task(due_date="2025-06-01T10:00:00+00:00")
        item = adapter.map_external_to_todo(task)
        assert item.due_date is not None
        assert item.due_date.year == 2025
        assert item.due_date.month == 6

    def test_map_external_to_todo_flagged_priority(self, adapter):
        task = _make_task(flagged=True)
        item = adapter.map_external_to_todo(task)
        assert item.priority == 3  # HIGH

    def test_map_external_to_todo_unflagged_priority(self, adapter):
        task = _make_task(flagged=False)
        item = adapter.map_external_to_todo(task)
        assert item.priority == 2  # MEDIUM

    def test_map_external_to_todo_project_from_cache(self, adapter):
        adapter._projects_id_cache = {"proj_abc": "My Project"}
        task = _make_task(project="proj_abc")
        item = adapter.map_external_to_todo(task)
        assert item.project == "My Project"

    def test_map_external_to_todo_project_as_dict(self, adapter):
        task = _make_task()
        task["project"] = {"id": "proj_abc", "name": "Work"}
        item = adapter.map_external_to_todo(task)
        assert item.project == "Work"
        assert item.project_id == "proj_abc"

    def test_map_external_to_todo_tags_as_dicts(self, adapter):
        task = _make_task(tags=[{"name": "errand"}, {"name": "home"}])
        item = adapter.map_external_to_todo(task)
        assert item.tags == ["errand", "home"]

    def test_supported_features(self, adapter):
        features = adapter.get_supported_features()
        assert "create" in features
        assert "projects" in features
        assert "tags" in features
