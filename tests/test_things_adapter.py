"""Tests for the Things 3 sync adapter."""

import pytest
import httpx
import respx
from datetime import datetime, timezone

from todo_cli.sync.providers.things_adapter import (
    ThingsAPI,
    ThingsAdapter,
    THINGS_STATUS_OPEN,
    THINGS_STATUS_COMPLETED,
    THINGS_STATUS_CANCELLED,
    THINGS_STATUS_TO_TODO_STATUS,
    TODO_STATUS_TO_THINGS,
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

BASE = "http://localhost:8081/"


def _make_config(**overrides) -> AppSyncConfig:
    defaults = dict(
        provider=AppSyncProvider.THINGS,
        credentials={"things_token": "test_token"},
        settings={"things_base_url": "http://localhost:8081"},
    )
    defaults.update(overrides)
    return AppSyncConfig(**defaults)


def _make_task(
    task_id: str = "task_1",
    title: str = "Buy milk",
    notes: str = "From the store",
    status: str = "open",
    tags: list | None = None,
    project: str | None = "proj_abc",
    area: str | None = None,
    due_date: str | None = "2025-06-01T10:00:00+00:00",
    created_date: str = "2025-01-01T00:00:00+00:00",
    modified_date: str = "2025-01-02T00:00:00+00:00",
    checklist: list | None = None,
) -> dict:
    result = {
        "id": task_id,
        "title": title,
        "notes": notes,
        "status": status,
        "tags": tags if tags is not None else ["shopping"],
        "project": project,
        "dueDate": due_date,
        "createdDate": created_date,
        "modifiedDate": modified_date,
    }
    if area is not None:
        result["area"] = area
    if checklist is not None:
        result["checklist"] = checklist
    return result


def _make_project(pid: str = "proj_abc", title: str = "Inbox") -> dict:
    return {"id": pid, "title": title}


def _make_area(aid: str = "area_1", title: str = "Personal") -> dict:
    return {"id": aid, "title": title}


def _make_todo(**overrides) -> Todo:
    defaults = dict(
        id=1,
        text="Buy groceries",
        description="Milk and eggs",
        status=TodoStatus.PENDING,
        completed=False,
        project="inbox",
        tags=["shopping"],
        priority=Priority.MEDIUM,
    )
    defaults.update(overrides)
    return Todo(**defaults)


@pytest.fixture
def config():
    return _make_config()


@pytest.fixture
def adapter(config):
    return ThingsAdapter(config)


# ---------------------------------------------------------------------------
# ThingsAPI - authentication
# ---------------------------------------------------------------------------


class TestThingsAPIAuthentication:
    @respx.mock
    @pytest.mark.asyncio
    async def test_auth_success(self):
        respx.get(f"{BASE}projects").mock(
            return_value=httpx.Response(200, json=[_make_project()])
        )
        async with ThingsAPI("good_token") as api:
            projects = await api.get_projects()
            assert len(projects) == 1

    @respx.mock
    @pytest.mark.asyncio
    async def test_auth_invalid_token(self):
        respx.get(f"{BASE}projects").mock(
            return_value=httpx.Response(401, text="Unauthorized")
        )
        async with ThingsAPI("bad_token") as api:
            with pytest.raises(AuthenticationError):
                await api.get_projects()

    @respx.mock
    @pytest.mark.asyncio
    async def test_auth_forbidden(self):
        respx.get(f"{BASE}projects").mock(
            return_value=httpx.Response(403, text="Forbidden")
        )
        async with ThingsAPI("bad_token") as api:
            with pytest.raises(AuthenticationError):
                await api.get_projects()

    @respx.mock
    @pytest.mark.asyncio
    async def test_rate_limit(self):
        respx.get(f"{BASE}projects").mock(
            return_value=httpx.Response(429, text="Too Many Requests")
        )
        async with ThingsAPI("token") as api:
            with pytest.raises(RateLimitError):
                await api.get_projects()


# ---------------------------------------------------------------------------
# ThingsAPI - tasks
# ---------------------------------------------------------------------------


class TestThingsAPITasks:
    @respx.mock
    @pytest.mark.asyncio
    async def test_get_tasks(self):
        respx.get(f"{BASE}tasks").mock(
            return_value=httpx.Response(200, json=[_make_task()])
        )
        async with ThingsAPI("token") as api:
            tasks = await api.get_tasks()
            assert len(tasks) == 1
            assert tasks[0]["title"] == "Buy milk"

    @respx.mock
    @pytest.mark.asyncio
    async def test_get_tasks_with_project(self):
        respx.get(f"{BASE}tasks", params={"projectId": "proj_abc"}).mock(
            return_value=httpx.Response(200, json=[_make_task()])
        )
        async with ThingsAPI("token") as api:
            tasks = await api.get_tasks(project_id="proj_abc")
            assert len(tasks) == 1

    @respx.mock
    @pytest.mark.asyncio
    async def test_get_tasks_with_area(self):
        respx.get(f"{BASE}tasks", params={"areaId": "area_1"}).mock(
            return_value=httpx.Response(200, json=[_make_task()])
        )
        async with ThingsAPI("token") as api:
            tasks = await api.get_tasks(area_id="area_1")
            assert len(tasks) == 1

    @respx.mock
    @pytest.mark.asyncio
    async def test_create_task(self):
        respx.post(f"{BASE}tasks").mock(
            return_value=httpx.Response(
                200, json={"id": "task_new", "title": "New"}
            )
        )
        async with ThingsAPI("token") as api:
            result = await api.create_task({"title": "New"})
            assert result["id"] == "task_new"

    @respx.mock
    @pytest.mark.asyncio
    async def test_update_task(self):
        respx.put(f"{BASE}tasks/task_1").mock(
            return_value=httpx.Response(
                200, json={"id": "task_1", "title": "Updated"}
            )
        )
        async with ThingsAPI("token") as api:
            result = await api.update_task("task_1", {"title": "Updated"})
            assert result["title"] == "Updated"

    @respx.mock
    @pytest.mark.asyncio
    async def test_complete_task(self):
        respx.post(f"{BASE}tasks/task_1/complete").mock(
            return_value=httpx.Response(200, json={})
        )
        async with ThingsAPI("token") as api:
            result = await api.complete_task("task_1")
            assert result == {}

    @respx.mock
    @pytest.mark.asyncio
    async def test_delete_task(self):
        respx.delete(f"{BASE}tasks/task_1").mock(
            return_value=httpx.Response(200, json={})
        )
        async with ThingsAPI("token") as api:
            result = await api.delete_task("task_1")
            assert result == {}

    @respx.mock
    @pytest.mark.asyncio
    async def test_server_error(self):
        respx.post(f"{BASE}tasks").mock(
            return_value=httpx.Response(500, text="Internal Server Error")
        )
        async with ThingsAPI("token") as api:
            with pytest.raises(NetworkError):
                await api.create_task({"title": "Fail"})

    @respx.mock
    @pytest.mark.asyncio
    async def test_get_tags(self):
        respx.get(f"{BASE}tags").mock(
            return_value=httpx.Response(
                200, json=[{"id": "t1", "title": "errand"}]
            )
        )
        async with ThingsAPI("token") as api:
            tags = await api.get_tags()
            assert len(tags) == 1
            assert tags[0]["title"] == "errand"

    @respx.mock
    @pytest.mark.asyncio
    async def test_get_areas(self):
        respx.get(f"{BASE}areas").mock(
            return_value=httpx.Response(
                200, json=[_make_area()]
            )
        )
        async with ThingsAPI("token") as api:
            areas = await api.get_areas()
            assert len(areas) == 1
            assert areas[0]["title"] == "Personal"

    @respx.mock
    @pytest.mark.asyncio
    async def test_204_response(self):
        respx.delete(f"{BASE}tasks/task_1").mock(
            return_value=httpx.Response(204)
        )
        async with ThingsAPI("token") as api:
            result = await api.delete_task("task_1")
            assert result == {}


# ---------------------------------------------------------------------------
# ThingsAPI - projects
# ---------------------------------------------------------------------------


class TestThingsAPIProjects:
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
        async with ThingsAPI("token") as api:
            projects = await api.get_projects()
            assert len(projects) == 2
            assert projects[0]["title"] == "Work"


# ---------------------------------------------------------------------------
# ThingsAdapter - authentication
# ---------------------------------------------------------------------------


class TestThingsAdapterAuth:
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
    async def test_authenticate_no_token(self):
        config = _make_config(credentials={})
        adp = ThingsAdapter(config)
        with pytest.raises(AuthenticationError, match="No Things API token"):
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
        assert adapter.get_required_credentials() == ["things_token"]


# ---------------------------------------------------------------------------
# ThingsAdapter - fetch items & mapping
# ---------------------------------------------------------------------------


class TestThingsAdapterFetch:
    @respx.mock
    @pytest.mark.asyncio
    async def test_fetch_items(self, adapter):
        respx.get(f"{BASE}projects").mock(
            return_value=httpx.Response(
                200, json=[_make_project("proj_abc", "Inbox")]
            )
        )
        respx.get(f"{BASE}areas").mock(
            return_value=httpx.Response(200, json=[])
        )
        respx.get(f"{BASE}tasks").mock(
            return_value=httpx.Response(200, json=[_make_task()])
        )
        items = await adapter.fetch_items()
        assert len(items) == 1
        item = items[0]
        assert item.title == "Buy milk"
        assert item.description == "From the store"
        assert item.provider == AppSyncProvider.THINGS
        assert item.tags == ["shopping"]
        assert item.completed is False

    @respx.mock
    @pytest.mark.asyncio
    async def test_fetch_items_completed(self, adapter):
        respx.get(f"{BASE}projects").mock(
            return_value=httpx.Response(200, json=[_make_project()])
        )
        respx.get(f"{BASE}areas").mock(
            return_value=httpx.Response(200, json=[])
        )
        respx.get(f"{BASE}tasks").mock(
            return_value=httpx.Response(
                200, json=[_make_task(status="completed")]
            )
        )
        items = await adapter.fetch_items()
        assert items[0].completed is True


# ---------------------------------------------------------------------------
# ThingsAdapter - create / update / delete
# ---------------------------------------------------------------------------


class TestThingsAdapterCRUD:
    @respx.mock
    @pytest.mark.asyncio
    async def test_create_item(self, adapter):
        respx.get(f"{BASE}projects").mock(
            return_value=httpx.Response(200, json=[_make_project()])
        )
        respx.post(f"{BASE}tasks").mock(
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
        respx.get(f"{BASE}projects").mock(
            return_value=httpx.Response(200, json=[_make_project()])
        )
        respx.put(f"{BASE}tasks/task_1").mock(
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
# ThingsAdapter - projects
# ---------------------------------------------------------------------------


class TestThingsAdapterProjects:
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
# Status mapping
# ---------------------------------------------------------------------------


class TestStatusMapping:
    def test_open_to_pending(self):
        assert THINGS_STATUS_TO_TODO_STATUS["open"] == TodoStatus.PENDING

    def test_completed_to_completed(self):
        assert THINGS_STATUS_TO_TODO_STATUS["completed"] == TodoStatus.COMPLETED

    def test_cancelled_to_cancelled(self):
        assert THINGS_STATUS_TO_TODO_STATUS["cancelled"] == TodoStatus.CANCELLED

    def test_pending_to_open(self):
        assert TODO_STATUS_TO_THINGS[TodoStatus.PENDING] == "open"

    def test_completed_to_completed_str(self):
        assert TODO_STATUS_TO_THINGS[TodoStatus.COMPLETED] == "completed"

    def test_cancelled_to_cancelled_str(self):
        assert TODO_STATUS_TO_THINGS[TodoStatus.CANCELLED] == "cancelled"


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
        assert data["notes"] == "Milk and eggs"
        assert data["tags"] == ["shopping"]
        assert data["status"] == "open"
        assert "dueDate" in data

    def test_map_todo_to_external_completed(self, adapter):
        todo = _make_todo(completed=True, status=TodoStatus.COMPLETED)
        data = adapter.map_todo_to_external(todo)
        assert data["status"] == "completed"

    def test_map_todo_to_external_cancelled(self, adapter):
        todo = _make_todo(status=TodoStatus.CANCELLED)
        data = adapter.map_todo_to_external(todo)
        assert data["status"] == "cancelled"

    def test_map_todo_to_external_no_description(self, adapter):
        todo = _make_todo(description="")
        data = adapter.map_todo_to_external(todo)
        assert "notes" not in data

    def test_map_external_to_todo(self, adapter):
        task = _make_task()
        item = adapter.map_external_to_todo(task)

        assert isinstance(item, ExternalTodoItem)
        assert item.external_id == "task_1"
        assert item.title == "Buy milk"
        assert item.description == "From the store"
        assert item.tags == ["shopping"]
        assert item.completed is False
        assert item.provider == AppSyncProvider.THINGS

    def test_map_external_to_todo_completed(self, adapter):
        task = _make_task(status="completed")
        item = adapter.map_external_to_todo(task)
        assert item.completed is True

    def test_map_external_to_todo_cancelled(self, adapter):
        task = _make_task(status="cancelled")
        item = adapter.map_external_to_todo(task)
        assert item.completed is False

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
        task = _make_task(project="proj_abc")
        item = adapter.map_external_to_todo(task)
        assert item.project == "My Project"

    def test_map_external_to_todo_project_as_dict(self, adapter):
        task = _make_task()
        task["project"] = {"id": "proj_abc", "title": "Work"}
        item = adapter.map_external_to_todo(task)
        assert item.project == "Work"
        assert item.project_id == "proj_abc"

    def test_map_external_to_todo_area_as_project(self, adapter):
        task = _make_task(project=None, area="area_1")
        adapter._areas_id_cache = {"area_1": "Personal"}
        item = adapter.map_external_to_todo(task)
        assert item.project == "Personal"

    def test_map_external_to_todo_area_as_dict(self, adapter):
        task = _make_task(project=None)
        task["area"] = {"id": "area_1", "title": "Personal"}
        item = adapter.map_external_to_todo(task)
        assert item.project == "Personal"
        assert item.project_id == "area_1"

    def test_map_external_to_todo_checklist(self, adapter):
        task = _make_task(
            checklist=[
                {"title": "Item 1", "completed": False},
                {"title": "Item 2", "completed": True},
            ]
        )
        item = adapter.map_external_to_todo(task)
        assert "Checklist:" in item.description
        assert "[ ] Item 1" in item.description
        assert "[x] Item 2" in item.description

    def test_map_external_to_todo_checklist_no_notes(self, adapter):
        task = _make_task(notes="")
        task["checklist"] = [{"title": "Do this", "completed": False}]
        item = adapter.map_external_to_todo(task)
        assert item.description.startswith("Checklist:")
        assert "[ ] Do this" in item.description

    def test_map_external_to_todo_tags_as_dicts(self, adapter):
        task = _make_task(tags=[{"title": "errand"}, {"title": "home"}])
        item = adapter.map_external_to_todo(task)
        assert item.tags == ["errand", "home"]

    def test_supported_features(self, adapter):
        features = adapter.get_supported_features()
        assert "create" in features
        assert "projects" in features
        assert "areas" in features
        assert "checklists" in features
        assert "tags" in features
