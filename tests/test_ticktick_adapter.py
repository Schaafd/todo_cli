"""Tests for the TickTick sync adapter."""

import pytest
import httpx
import respx
from datetime import datetime, timezone

from todo_cli.sync.providers.ticktick_adapter import (
    TickTickAPI,
    TickTickAdapter,
    TICKTICK_PRIORITY_TO_INTERNAL,
    INTERNAL_PRIORITY_TO_TICKTICK,
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

BASE = "https://api.ticktick.com/open/v1/"


def _make_config(**overrides) -> AppSyncConfig:
    defaults = dict(
        provider=AppSyncProvider.TICKTICK,
        credentials={"ticktick_token": "test_oauth_token"},
        settings={"ticktick_project_id": "proj_abc"},
    )
    defaults.update(overrides)
    return AppSyncConfig(**defaults)


def _make_task(
    task_id: str = "task_1",
    title: str = "Buy milk",
    content: str = "From the store",
    priority: int = 3,
    status: int = 0,
    tags: list | None = None,
    project_id: str = "proj_abc",
    due_date: str | None = "2025-06-01T10:00:00+0000",
    created_date: str = "2025-01-01T00:00:00+0000",
    modified_date: str = "2025-01-02T00:00:00+0000",
) -> dict:
    return {
        "id": task_id,
        "title": title,
        "content": content,
        "priority": priority,
        "status": status,
        "tags": tags or ["shopping"],
        "projectId": project_id,
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
    return TickTickAdapter(config)


# ---------------------------------------------------------------------------
# TickTickAPI - authentication
# ---------------------------------------------------------------------------


class TestTickTickAPIAuthentication:
    @respx.mock
    @pytest.mark.asyncio
    async def test_auth_success(self):
        respx.get(f"{BASE}project").mock(
            return_value=httpx.Response(200, json=[_make_project()])
        )
        async with TickTickAPI("good_token") as api:
            projects = await api.get_projects()
            assert len(projects) == 1

    @respx.mock
    @pytest.mark.asyncio
    async def test_auth_invalid_token(self):
        respx.get(f"{BASE}project").mock(
            return_value=httpx.Response(401, text="Unauthorized")
        )
        async with TickTickAPI("bad_token") as api:
            with pytest.raises(AuthenticationError):
                await api.get_projects()

    @respx.mock
    @pytest.mark.asyncio
    async def test_auth_forbidden(self):
        respx.get(f"{BASE}project").mock(
            return_value=httpx.Response(403, text="Forbidden")
        )
        async with TickTickAPI("bad_token") as api:
            with pytest.raises(AuthenticationError):
                await api.get_projects()

    @respx.mock
    @pytest.mark.asyncio
    async def test_rate_limit(self):
        respx.get(f"{BASE}project").mock(
            return_value=httpx.Response(429, text="Too Many Requests")
        )
        async with TickTickAPI("token") as api:
            with pytest.raises(RateLimitError):
                await api.get_projects()


# ---------------------------------------------------------------------------
# TickTickAPI - tasks
# ---------------------------------------------------------------------------


class TestTickTickAPITasks:
    @respx.mock
    @pytest.mark.asyncio
    async def test_get_tasks_with_project(self):
        respx.get(f"{BASE}project/proj_abc/data").mock(
            return_value=httpx.Response(
                200, json={"tasks": [_make_task()]}
            )
        )
        async with TickTickAPI("token") as api:
            tasks = await api.get_tasks(project_id="proj_abc")
            assert len(tasks) == 1
            assert tasks[0]["title"] == "Buy milk"

    @respx.mock
    @pytest.mark.asyncio
    async def test_get_tasks_all_projects(self):
        respx.get(f"{BASE}project").mock(
            return_value=httpx.Response(200, json=[_make_project()])
        )
        respx.get(f"{BASE}project/proj_abc/data").mock(
            return_value=httpx.Response(
                200, json={"tasks": [_make_task()]}
            )
        )
        async with TickTickAPI("token") as api:
            tasks = await api.get_tasks()
            assert len(tasks) == 1

    @respx.mock
    @pytest.mark.asyncio
    async def test_create_task(self):
        respx.post(f"{BASE}task").mock(
            return_value=httpx.Response(
                200, json={"id": "task_new", "title": "New"}
            )
        )
        async with TickTickAPI("token") as api:
            result = await api.create_task({"title": "New"})
            assert result["id"] == "task_new"

    @respx.mock
    @pytest.mark.asyncio
    async def test_update_task(self):
        respx.post(f"{BASE}task/task_1").mock(
            return_value=httpx.Response(
                200, json={"id": "task_1", "title": "Updated"}
            )
        )
        async with TickTickAPI("token") as api:
            result = await api.update_task("task_1", {"title": "Updated"})
            assert result["title"] == "Updated"

    @respx.mock
    @pytest.mark.asyncio
    async def test_complete_task(self):
        respx.post(
            f"{BASE}project/proj_abc/task/task_1/complete"
        ).mock(return_value=httpx.Response(200, json={}))
        async with TickTickAPI("token") as api:
            result = await api.complete_task("proj_abc", "task_1")
            assert result == {}

    @respx.mock
    @pytest.mark.asyncio
    async def test_delete_task(self):
        respx.delete(
            f"{BASE}project/proj_abc/task/task_1"
        ).mock(return_value=httpx.Response(200, json={}))
        async with TickTickAPI("token") as api:
            result = await api.delete_task("proj_abc", "task_1")
            assert result == {}

    @respx.mock
    @pytest.mark.asyncio
    async def test_server_error(self):
        respx.post(f"{BASE}task").mock(
            return_value=httpx.Response(500, text="Internal Server Error")
        )
        async with TickTickAPI("token") as api:
            with pytest.raises(NetworkError):
                await api.create_task({"title": "Fail"})


# ---------------------------------------------------------------------------
# TickTickAPI - projects
# ---------------------------------------------------------------------------


class TestTickTickAPIProjects:
    @respx.mock
    @pytest.mark.asyncio
    async def test_get_projects(self):
        respx.get(f"{BASE}project").mock(
            return_value=httpx.Response(
                200,
                json=[
                    _make_project("p1", "Work"),
                    _make_project("p2", "Personal"),
                ],
            )
        )
        async with TickTickAPI("token") as api:
            projects = await api.get_projects()
            assert len(projects) == 2
            assert projects[0]["name"] == "Work"


# ---------------------------------------------------------------------------
# TickTickAdapter - authentication
# ---------------------------------------------------------------------------


class TestTickTickAdapterAuth:
    @respx.mock
    @pytest.mark.asyncio
    async def test_authenticate_success(self, adapter):
        respx.get(f"{BASE}project").mock(
            return_value=httpx.Response(200, json=[_make_project()])
        )
        result = await adapter.authenticate()
        assert result is True

    @respx.mock
    @pytest.mark.asyncio
    async def test_authenticate_failure(self, adapter):
        respx.get(f"{BASE}project").mock(
            return_value=httpx.Response(401, text="Unauthorized")
        )
        with pytest.raises(AuthenticationError):
            await adapter.authenticate()

    @pytest.mark.asyncio
    async def test_authenticate_no_token(self):
        config = _make_config(credentials={})
        adp = TickTickAdapter(config)
        with pytest.raises(AuthenticationError, match="No TickTick access token"):
            await adp.authenticate()

    @respx.mock
    @pytest.mark.asyncio
    async def test_test_connection_success(self, adapter):
        respx.get(f"{BASE}project").mock(
            return_value=httpx.Response(200, json=[_make_project()])
        )
        assert await adapter.test_connection() is True

    @respx.mock
    @pytest.mark.asyncio
    async def test_test_connection_failure(self, adapter):
        respx.get(f"{BASE}project").mock(
            return_value=httpx.Response(401, text="Unauthorized")
        )
        assert await adapter.test_connection() is False

    def test_required_credentials(self, adapter):
        assert adapter.get_required_credentials() == ["ticktick_token"]


# ---------------------------------------------------------------------------
# TickTickAdapter - fetch items & mapping
# ---------------------------------------------------------------------------


class TestTickTickAdapterFetch:
    @respx.mock
    @pytest.mark.asyncio
    async def test_fetch_items(self, adapter):
        # authenticate
        respx.get(f"{BASE}project").mock(
            return_value=httpx.Response(
                200, json=[_make_project("proj_abc", "Inbox")]
            )
        )
        # fetch tasks
        respx.get(f"{BASE}project/proj_abc/data").mock(
            return_value=httpx.Response(
                200, json={"tasks": [_make_task()]}
            )
        )
        items = await adapter.fetch_items()
        assert len(items) == 1
        item = items[0]
        assert item.title == "Buy milk"
        assert item.description == "From the store"
        assert item.provider == AppSyncProvider.TICKTICK
        assert item.tags == ["shopping"]
        assert item.completed is False

    @respx.mock
    @pytest.mark.asyncio
    async def test_fetch_items_completed(self, adapter):
        respx.get(f"{BASE}project").mock(
            return_value=httpx.Response(200, json=[_make_project()])
        )
        respx.get(f"{BASE}project/proj_abc/data").mock(
            return_value=httpx.Response(
                200,
                json={
                    "tasks": [_make_task(status=2)]
                },
            )
        )
        items = await adapter.fetch_items()
        assert items[0].completed is True


# ---------------------------------------------------------------------------
# TickTickAdapter - create / update / delete
# ---------------------------------------------------------------------------


class TestTickTickAdapterCRUD:
    @respx.mock
    @pytest.mark.asyncio
    async def test_create_item(self, adapter):
        respx.get(f"{BASE}project").mock(
            return_value=httpx.Response(200, json=[_make_project()])
        )
        respx.post(f"{BASE}task").mock(
            return_value=httpx.Response(
                200, json={"id": "task_new", "title": "Buy groceries"}
            )
        )
        todo = _make_todo()
        task_id = await adapter.create_item(todo)
        assert task_id == "task_new"

    @respx.mock
    @pytest.mark.asyncio
    async def test_update_item(self, adapter):
        respx.get(f"{BASE}project").mock(
            return_value=httpx.Response(200, json=[_make_project()])
        )
        respx.post(f"{BASE}task/task_1").mock(
            return_value=httpx.Response(
                200, json={"id": "task_1", "title": "Updated"}
            )
        )
        todo = _make_todo()
        result = await adapter.update_item("task_1", todo)
        assert result is True

    @respx.mock
    @pytest.mark.asyncio
    async def test_update_item_completed(self, adapter):
        respx.get(f"{BASE}project").mock(
            return_value=httpx.Response(200, json=[_make_project()])
        )
        respx.post(f"{BASE}task/task_1").mock(
            return_value=httpx.Response(200, json={"id": "task_1"})
        )
        respx.post(
            f"{BASE}project/proj_abc/task/task_1/complete"
        ).mock(return_value=httpx.Response(200, json={}))

        todo = _make_todo(completed=True, status=TodoStatus.COMPLETED)
        result = await adapter.update_item("task_1", todo)
        assert result is True

    @respx.mock
    @pytest.mark.asyncio
    async def test_delete_item(self, adapter):
        respx.get(f"{BASE}project").mock(
            return_value=httpx.Response(200, json=[_make_project()])
        )
        respx.delete(f"{BASE}project/proj_abc/task/task_1").mock(
            return_value=httpx.Response(200, json={})
        )
        result = await adapter.delete_item("task_1")
        assert result is True

    @respx.mock
    @pytest.mark.asyncio
    async def test_delete_item_failure(self, adapter):
        respx.get(f"{BASE}project").mock(
            return_value=httpx.Response(200, json=[_make_project()])
        )
        respx.delete(f"{BASE}project/proj_abc/task/task_1").mock(
            return_value=httpx.Response(500, text="Server Error")
        )
        result = await adapter.delete_item("task_1")
        assert result is False


# ---------------------------------------------------------------------------
# TickTickAdapter - projects
# ---------------------------------------------------------------------------


class TestTickTickAdapterProjects:
    @respx.mock
    @pytest.mark.asyncio
    async def test_fetch_projects(self, adapter):
        respx.get(f"{BASE}project").mock(
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
# Priority mapping
# ---------------------------------------------------------------------------


class TestPriorityMapping:
    def test_ticktick_to_internal(self):
        assert TICKTICK_PRIORITY_TO_INTERNAL[0] == Priority.LOW
        assert TICKTICK_PRIORITY_TO_INTERNAL[1] == Priority.LOW
        assert TICKTICK_PRIORITY_TO_INTERNAL[3] == Priority.MEDIUM
        assert TICKTICK_PRIORITY_TO_INTERNAL[5] == Priority.HIGH

    def test_internal_to_ticktick(self):
        assert INTERNAL_PRIORITY_TO_TICKTICK[Priority.LOW] == 1
        assert INTERNAL_PRIORITY_TO_TICKTICK[Priority.MEDIUM] == 3
        assert INTERNAL_PRIORITY_TO_TICKTICK[Priority.HIGH] == 5
        assert INTERNAL_PRIORITY_TO_TICKTICK[Priority.CRITICAL] == 5


# ---------------------------------------------------------------------------
# Field mapping
# ---------------------------------------------------------------------------


class TestFieldMapping:
    def test_map_todo_to_external(self, adapter):
        todo = _make_todo(
            due_date=datetime(2025, 6, 15, 10, 0, tzinfo=timezone.utc)
        )
        data = adapter.map_todo_to_external(todo)

        assert data["title"] == "Buy groceries"
        assert data["content"] == "Milk and eggs"
        assert data["priority"] == 5  # HIGH -> 5
        assert data["tags"] == ["shopping"]
        assert data["status"] == 0  # not completed
        assert "dueDate" in data

    def test_map_todo_to_external_completed(self, adapter):
        todo = _make_todo(completed=True, status=TodoStatus.COMPLETED)
        data = adapter.map_todo_to_external(todo)
        assert data["status"] == 2

    def test_map_todo_to_external_no_description(self, adapter):
        todo = _make_todo(description="")
        data = adapter.map_todo_to_external(todo)
        assert "content" not in data

    def test_map_external_to_todo(self, adapter):
        task = _make_task()
        item = adapter.map_external_to_todo(task)

        assert isinstance(item, ExternalTodoItem)
        assert item.external_id == "task_1"
        assert item.title == "Buy milk"
        assert item.description == "From the store"
        assert item.priority == 3
        assert item.tags == ["shopping"]
        assert item.completed is False
        assert item.provider == AppSyncProvider.TICKTICK
        assert item.project_id == "proj_abc"

    def test_map_external_to_todo_completed(self, adapter):
        task = _make_task(status=2)
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

    def test_map_external_to_todo_project_from_cache(self, adapter):
        adapter._projects_id_cache = {"proj_abc": "My Project"}
        task = _make_task(project_id="proj_abc")
        item = adapter.map_external_to_todo(task)
        assert item.project == "My Project"
