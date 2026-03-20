"""Tests for the Notion sync adapter."""

import pytest
import httpx
import respx
from datetime import datetime, timezone

from todo_cli.sync.providers.notion_adapter import NotionAPI, NotionAdapter
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

NOTION_BASE = "https://api.notion.com/v1/"
FAKE_TOKEN = "ntn_test_token_123"
FAKE_DB_ID = "db-0000-1111-2222-3333"
FAKE_PAGE_ID = "page-aaaa-bbbb-cccc-dddd"


def _make_config(**overrides) -> AppSyncConfig:
    defaults = dict(
        provider=AppSyncProvider.NOTION,
        credentials={"notion_token": FAKE_TOKEN},
        settings={"notion_database_id": FAKE_DB_ID},
    )
    defaults.update(overrides)
    return AppSyncConfig(**defaults)


def _make_page(
    page_id: str = FAKE_PAGE_ID,
    title: str = "Test task",
    status: str = "Not Started",
    priority: str = "High",
    tags: list | None = None,
    due_date: str | None = None,
    description: str = "",
    assignee: str = "",
    project: str = "",
) -> dict:
    """Build a minimal Notion page object."""
    properties: dict = {
        "Name": {
            "type": "title",
            "title": [{"plain_text": title}],
        },
        "Status": {
            "type": "status",
            "status": {"name": status},
        },
        "Priority": {
            "type": "select",
            "select": {"name": priority},
        },
    }
    if tags:
        properties["Tags"] = {
            "type": "multi_select",
            "multi_select": [{"name": t} for t in tags],
        }
    if due_date:
        properties["Due Date"] = {
            "type": "date",
            "date": {"start": due_date},
        }
    if description:
        properties["Description"] = {
            "type": "rich_text",
            "rich_text": [{"plain_text": description}],
        }
    if assignee:
        properties["Assignee"] = {
            "type": "rich_text",
            "rich_text": [{"plain_text": assignee}],
        }
    if project:
        properties["Project"] = {
            "type": "select",
            "select": {"name": project},
        }

    return {
        "id": page_id,
        "object": "page",
        "created_time": "2025-01-15T10:00:00.000Z",
        "last_edited_time": "2025-01-16T12:00:00.000Z",
        "url": f"https://www.notion.so/{page_id}",
        "properties": properties,
    }


def _make_todo(**overrides) -> Todo:
    defaults = dict(
        id=1,
        text="Buy groceries",
        description="Milk, eggs, bread",
        status=TodoStatus.PENDING,
        priority=Priority.HIGH,
        tags=["shopping", "errands"],
        due_date=datetime(2025, 3, 1, tzinfo=timezone.utc),
        project="personal",
        assignees=["alice"],
    )
    defaults.update(overrides)
    return Todo(**defaults)


# ---------------------------------------------------------------------------
# NotionAPI tests
# ---------------------------------------------------------------------------


class TestNotionAPIAuthentication:
    @respx.mock
    @pytest.mark.asyncio
    async def test_authenticate_success(self):
        respx.get(f"{NOTION_BASE}users/me").mock(
            return_value=httpx.Response(200, json={"type": "bot", "id": "bot-1"})
        )
        async with NotionAPI(FAKE_TOKEN) as api:
            result = await api.get_me()
        assert result["type"] == "bot"

    @respx.mock
    @pytest.mark.asyncio
    async def test_authenticate_invalid_token(self):
        respx.get(f"{NOTION_BASE}users/me").mock(
            return_value=httpx.Response(401, json={"message": "Invalid token"})
        )
        async with NotionAPI(FAKE_TOKEN) as api:
            with pytest.raises(AuthenticationError):
                await api.get_me()

    @respx.mock
    @pytest.mark.asyncio
    async def test_authenticate_forbidden(self):
        respx.get(f"{NOTION_BASE}users/me").mock(
            return_value=httpx.Response(403, json={"message": "Forbidden"})
        )
        async with NotionAPI(FAKE_TOKEN) as api:
            with pytest.raises(AuthenticationError):
                await api.get_me()

    @respx.mock
    @pytest.mark.asyncio
    async def test_rate_limit(self):
        respx.get(f"{NOTION_BASE}users/me").mock(
            return_value=httpx.Response(429, json={"message": "Rate limited"})
        )
        async with NotionAPI(FAKE_TOKEN) as api:
            with pytest.raises(RateLimitError):
                await api.get_me()


# ---------------------------------------------------------------------------
# NotionAPI database / page tests
# ---------------------------------------------------------------------------


class TestNotionAPIDatabaseAndPages:
    @respx.mock
    @pytest.mark.asyncio
    async def test_query_database(self):
        pages = [_make_page()]
        respx.post(f"{NOTION_BASE}databases/{FAKE_DB_ID}/query").mock(
            return_value=httpx.Response(200, json={"results": pages, "has_more": False})
        )
        async with NotionAPI(FAKE_TOKEN) as api:
            result = await api.query_database(FAKE_DB_ID)
        assert len(result["results"]) == 1

    @respx.mock
    @pytest.mark.asyncio
    async def test_query_database_with_filter(self):
        route = respx.post(f"{NOTION_BASE}databases/{FAKE_DB_ID}/query").mock(
            return_value=httpx.Response(200, json={"results": [], "has_more": False})
        )
        async with NotionAPI(FAKE_TOKEN) as api:
            await api.query_database(FAKE_DB_ID, filter={"property": "Status", "status": {"equals": "Done"}})
        assert route.called
        sent_json = route.calls[0].request.content
        assert b"filter" in sent_json

    @respx.mock
    @pytest.mark.asyncio
    async def test_create_page(self):
        respx.post(f"{NOTION_BASE}pages").mock(
            return_value=httpx.Response(200, json=_make_page())
        )
        async with NotionAPI(FAKE_TOKEN) as api:
            result = await api.create_page(FAKE_DB_ID, {"Name": {"title": [{"text": {"content": "New"}}]}})
        assert result["id"] == FAKE_PAGE_ID

    @respx.mock
    @pytest.mark.asyncio
    async def test_update_page(self):
        respx.patch(f"{NOTION_BASE}pages/{FAKE_PAGE_ID}").mock(
            return_value=httpx.Response(200, json=_make_page(title="Updated"))
        )
        async with NotionAPI(FAKE_TOKEN) as api:
            result = await api.update_page(FAKE_PAGE_ID, {"Name": {"title": [{"text": {"content": "Updated"}}]}})
        assert result["id"] == FAKE_PAGE_ID

    @respx.mock
    @pytest.mark.asyncio
    async def test_archive_page(self):
        respx.patch(f"{NOTION_BASE}pages/{FAKE_PAGE_ID}").mock(
            return_value=httpx.Response(200, json={**_make_page(), "archived": True})
        )
        async with NotionAPI(FAKE_TOKEN) as api:
            result = await api.archive_page(FAKE_PAGE_ID)
        assert result["archived"] is True

    @respx.mock
    @pytest.mark.asyncio
    async def test_get_page(self):
        respx.get(f"{NOTION_BASE}pages/{FAKE_PAGE_ID}").mock(
            return_value=httpx.Response(200, json=_make_page())
        )
        async with NotionAPI(FAKE_TOKEN) as api:
            result = await api.get_page(FAKE_PAGE_ID)
        assert result["id"] == FAKE_PAGE_ID

    @respx.mock
    @pytest.mark.asyncio
    async def test_search_databases(self):
        db_obj = {
            "id": FAKE_DB_ID,
            "object": "database",
            "title": [{"plain_text": "Tasks DB"}],
        }
        respx.post(f"{NOTION_BASE}search").mock(
            return_value=httpx.Response(200, json={"results": [db_obj]})
        )
        async with NotionAPI(FAKE_TOKEN) as api:
            result = await api.search_databases()
        assert len(result["results"]) == 1
        assert result["results"][0]["id"] == FAKE_DB_ID

    @respx.mock
    @pytest.mark.asyncio
    async def test_not_found(self):
        respx.get(f"{NOTION_BASE}pages/missing-id").mock(
            return_value=httpx.Response(404, json={"message": "Not found"})
        )
        async with NotionAPI(FAKE_TOKEN) as api:
            with pytest.raises(NetworkError):
                await api.get_page("missing-id")


# ---------------------------------------------------------------------------
# NotionAdapter tests
# ---------------------------------------------------------------------------


class TestNotionAdapterAuthentication:
    @respx.mock
    @pytest.mark.asyncio
    async def test_authenticate_success(self):
        respx.get(f"{NOTION_BASE}users/me").mock(
            return_value=httpx.Response(200, json={"type": "bot", "id": "bot-1"})
        )
        adapter = NotionAdapter(_make_config())
        result = await adapter.authenticate()
        assert result is True

    @respx.mock
    @pytest.mark.asyncio
    async def test_authenticate_no_token(self):
        adapter = NotionAdapter(_make_config(credentials={}))
        with pytest.raises(AuthenticationError):
            await adapter.authenticate()

    @respx.mock
    @pytest.mark.asyncio
    async def test_test_connection_success(self):
        respx.get(f"{NOTION_BASE}users/me").mock(
            return_value=httpx.Response(200, json={"type": "bot", "id": "bot-1"})
        )
        adapter = NotionAdapter(_make_config())
        assert await adapter.test_connection() is True

    @respx.mock
    @pytest.mark.asyncio
    async def test_test_connection_failure(self):
        respx.get(f"{NOTION_BASE}users/me").mock(
            return_value=httpx.Response(401, json={"message": "Invalid"})
        )
        adapter = NotionAdapter(_make_config())
        assert await adapter.test_connection() is False

    def test_get_required_credentials(self):
        adapter = NotionAdapter(_make_config())
        assert adapter.get_required_credentials() == ["notion_token"]


class TestNotionAdapterFetchItems:
    @respx.mock
    @pytest.mark.asyncio
    async def test_fetch_items(self):
        # Auth
        respx.get(f"{NOTION_BASE}users/me").mock(
            return_value=httpx.Response(200, json={"type": "bot", "id": "bot-1"})
        )
        # Query
        pages = [
            _make_page(page_id="p1", title="Task A", status="Not Started", priority="High", tags=["work"]),
            _make_page(page_id="p2", title="Task B", status="Done", priority="Low"),
        ]
        respx.post(f"{NOTION_BASE}databases/{FAKE_DB_ID}/query").mock(
            return_value=httpx.Response(200, json={"results": pages, "has_more": False})
        )

        adapter = NotionAdapter(_make_config())
        items = await adapter.fetch_items()

        assert len(items) == 2
        assert items[0].title == "Task A"
        assert items[0].completed is False
        assert items[0].tags == ["work"]
        assert items[1].title == "Task B"
        assert items[1].completed is True

    @respx.mock
    @pytest.mark.asyncio
    async def test_fetch_items_with_since(self):
        respx.get(f"{NOTION_BASE}users/me").mock(
            return_value=httpx.Response(200, json={"type": "bot", "id": "bot-1"})
        )
        route = respx.post(f"{NOTION_BASE}databases/{FAKE_DB_ID}/query").mock(
            return_value=httpx.Response(200, json={"results": [], "has_more": False})
        )

        adapter = NotionAdapter(_make_config())
        since = datetime(2025, 1, 1, tzinfo=timezone.utc)
        await adapter.fetch_items(since=since)

        assert route.called
        sent = route.calls[0].request.content
        assert b"last_edited_time" in sent


class TestNotionAdapterCreateItem:
    @respx.mock
    @pytest.mark.asyncio
    async def test_create_item(self):
        respx.get(f"{NOTION_BASE}users/me").mock(
            return_value=httpx.Response(200, json={"type": "bot", "id": "bot-1"})
        )
        respx.post(f"{NOTION_BASE}pages").mock(
            return_value=httpx.Response(200, json=_make_page(page_id="new-page-id", title="Buy groceries"))
        )

        adapter = NotionAdapter(_make_config())
        todo = _make_todo()
        page_id = await adapter.create_item(todo)

        assert page_id == "new-page-id"


class TestNotionAdapterUpdateItem:
    @respx.mock
    @pytest.mark.asyncio
    async def test_update_item(self):
        respx.get(f"{NOTION_BASE}users/me").mock(
            return_value=httpx.Response(200, json={"type": "bot", "id": "bot-1"})
        )
        respx.patch(f"{NOTION_BASE}pages/{FAKE_PAGE_ID}").mock(
            return_value=httpx.Response(200, json=_make_page(title="Updated"))
        )

        adapter = NotionAdapter(_make_config())
        todo = _make_todo(text="Updated")
        result = await adapter.update_item(FAKE_PAGE_ID, todo)

        assert result is True


class TestNotionAdapterDeleteItem:
    @respx.mock
    @pytest.mark.asyncio
    async def test_delete_item_archives(self):
        respx.get(f"{NOTION_BASE}users/me").mock(
            return_value=httpx.Response(200, json={"type": "bot", "id": "bot-1"})
        )
        route = respx.patch(f"{NOTION_BASE}pages/{FAKE_PAGE_ID}").mock(
            return_value=httpx.Response(200, json={**_make_page(), "archived": True})
        )

        adapter = NotionAdapter(_make_config())
        result = await adapter.delete_item(FAKE_PAGE_ID)

        assert result is True
        assert route.called
        assert b"archived" in route.calls[0].request.content


class TestNotionAdapterFetchProjects:
    @respx.mock
    @pytest.mark.asyncio
    async def test_fetch_projects(self):
        respx.get(f"{NOTION_BASE}users/me").mock(
            return_value=httpx.Response(200, json={"type": "bot", "id": "bot-1"})
        )
        db_obj = {
            "id": FAKE_DB_ID,
            "object": "database",
            "title": [{"plain_text": "Tasks DB"}],
        }
        respx.post(f"{NOTION_BASE}search").mock(
            return_value=httpx.Response(200, json={"results": [db_obj]})
        )

        adapter = NotionAdapter(_make_config())
        projects = await adapter.fetch_projects()

        assert "Tasks DB" in projects
        assert projects["Tasks DB"] == FAKE_DB_ID


# ---------------------------------------------------------------------------
# Property mapping tests
# ---------------------------------------------------------------------------


class TestPropertyMapping:
    """Test map_todo_to_external and map_external_to_todo in both directions."""

    def test_map_todo_to_external_full(self):
        adapter = NotionAdapter(_make_config())
        todo = _make_todo()
        props = adapter.map_todo_to_external(todo)

        # Title
        assert props["Name"]["title"][0]["text"]["content"] == "Buy groceries"
        # Description
        assert props["Description"]["rich_text"][0]["text"]["content"] == "Milk, eggs, bread"
        # Status - pending -> Not Started
        assert props["Status"]["status"]["name"] == "Not Started"
        # Priority
        assert props["Priority"]["select"]["name"] == "High"
        # Tags
        tag_names = [t["name"] for t in props["Tags"]["multi_select"]]
        assert set(tag_names) == {"shopping", "errands"}
        # Due date
        assert "2025-03-01" in props["Due Date"]["date"]["start"]
        # Assignee
        assert "alice" in props["Assignee"]["rich_text"][0]["text"]["content"]
        # Project
        assert props["Project"]["select"]["name"] == "personal"

    def test_map_todo_to_external_completed(self):
        adapter = NotionAdapter(_make_config())
        todo = _make_todo(status=TodoStatus.COMPLETED, completed=True)
        props = adapter.map_todo_to_external(todo)
        assert props["Status"]["status"]["name"] == "Done"

    def test_map_todo_to_external_in_progress(self):
        adapter = NotionAdapter(_make_config())
        todo = _make_todo(status=TodoStatus.IN_PROGRESS)
        props = adapter.map_todo_to_external(todo)
        assert props["Status"]["status"]["name"] == "In Progress"

    def test_map_todo_to_external_inbox_project_omitted(self):
        adapter = NotionAdapter(_make_config())
        todo = _make_todo(project="inbox")
        props = adapter.map_todo_to_external(todo)
        assert "Project" not in props

    def test_map_external_to_todo_full(self):
        adapter = NotionAdapter(_make_config())
        page = _make_page(
            title="Review PR",
            status="Not Started",
            priority="Medium",
            tags=["dev", "review"],
            due_date="2025-06-15",
            description="Check the new feature branch",
            assignee="bob",
            project="work",
        )
        item = adapter.map_external_to_todo(page)

        assert isinstance(item, ExternalTodoItem)
        assert item.external_id == FAKE_PAGE_ID
        assert item.provider == AppSyncProvider.NOTION
        assert item.title == "Review PR"
        assert item.description == "Check the new feature branch"
        assert item.completed is False
        assert item.priority == 2  # medium
        assert item.tags == ["dev", "review"]
        assert item.due_date is not None
        assert item.due_date.year == 2025
        assert item.assignee == "bob"
        assert item.project == "work"
        assert item.url is not None

    def test_map_external_to_todo_completed(self):
        adapter = NotionAdapter(_make_config())
        page = _make_page(status="Done")
        item = adapter.map_external_to_todo(page)
        assert item.completed is True

    def test_map_external_to_todo_completed_variants(self):
        adapter = NotionAdapter(_make_config())
        for status_name in ("Done", "Completed", "Complete", "Closed"):
            page = _make_page(status=status_name)
            item = adapter.map_external_to_todo(page)
            assert item.completed is True, f"Expected completed for status '{status_name}'"

    def test_map_external_to_todo_timestamps(self):
        adapter = NotionAdapter(_make_config())
        page = _make_page()
        item = adapter.map_external_to_todo(page)
        assert item.created_at is not None
        assert item.created_at.tzinfo is not None
        assert item.updated_at is not None
        assert item.updated_at.tzinfo is not None

    def test_map_external_to_todo_no_priority(self):
        adapter = NotionAdapter(_make_config())
        page = _make_page()
        # Remove priority
        page["properties"].pop("Priority", None)
        item = adapter.map_external_to_todo(page)
        assert item.priority is None

    def test_map_external_to_todo_datetime_with_time(self):
        adapter = NotionAdapter(_make_config())
        page = _make_page(due_date="2025-06-15T14:30:00+00:00")
        item = adapter.map_external_to_todo(page)
        assert item.due_date is not None
        assert item.due_date.hour == 14
        assert item.due_date.minute == 30

    def test_roundtrip_title(self):
        """Create a Todo, map to Notion properties, build page, map back."""
        adapter = NotionAdapter(_make_config())
        todo = _make_todo(text="Roundtrip test", tags=["a", "b"], project="myproj")
        props = adapter.map_todo_to_external(todo)

        # Build a fake page from the properties
        page = {
            "id": "roundtrip-id",
            "object": "page",
            "created_time": "2025-01-01T00:00:00.000Z",
            "last_edited_time": "2025-01-01T00:00:00.000Z",
            "url": "https://www.notion.so/roundtrip-id",
            "properties": props,
        }
        # Fix property types for extraction (map_todo_to_external doesn't set "type" keys)
        # Also add plain_text alongside text.content since the API returns plain_text
        page["properties"]["Name"]["type"] = "title"
        for part in page["properties"]["Name"]["title"]:
            part["plain_text"] = part["text"]["content"]
        page["properties"]["Status"]["type"] = "status"
        page["properties"]["Priority"]["type"] = "select"
        page["properties"]["Tags"]["type"] = "multi_select"
        page["properties"]["Due Date"]["type"] = "date"
        page["properties"]["Assignee"]["type"] = "rich_text"
        for part in page["properties"]["Assignee"]["rich_text"]:
            part["plain_text"] = part["text"]["content"]
        page["properties"]["Description"]["type"] = "rich_text"
        for part in page["properties"]["Description"]["rich_text"]:
            part["plain_text"] = part["text"]["content"]
        page["properties"]["Project"]["type"] = "select"

        item = adapter.map_external_to_todo(page)
        assert item.title == "Roundtrip test"
        assert set(item.tags) == {"a", "b"}
        assert item.project == "myproj"
