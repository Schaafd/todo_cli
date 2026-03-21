"""Tests for the Evernote sync adapter."""

import pytest
import httpx
import respx
from datetime import datetime, timezone

from todo_cli.sync.providers.evernote_adapter import (
    EvernoteAPI,
    EvernoteAdapter,
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
    """Create a minimal AppSyncConfig for Evernote."""
    defaults = dict(
        provider=AppSyncProvider.EVERNOTE,
        credentials={"evernote_token": "en_test_token_123"},
        settings={"evernote_notebook_guid": "nb-guid-001"},
    )
    defaults.update(overrides)
    return AppSyncConfig(**defaults)


def _make_note(
    guid: str = "note-guid-001",
    title: str = "Test note",
    content: str = "<en-note>Some content</en-note>",
    notebook_guid: str = "nb-guid-001",
    tag_names: list | None = None,
    reminder_time: str | None = None,
    reminder_done_time: str | None = None,
    created: str = "2025-01-01T00:00:00+00:00",
    updated: str = "2025-01-02T00:00:00+00:00",
) -> dict:
    """Build a fake Evernote note payload."""
    note: dict = {
        "guid": guid,
        "title": title,
        "content": content,
        "notebookGuid": notebook_guid,
        "tagNames": tag_names or [],
        "created": created,
        "updated": updated,
    }
    if reminder_time:
        note["reminderTime"] = reminder_time
    if reminder_done_time:
        note["reminderDoneTime"] = reminder_done_time
    return note


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
    return EvernoteAdapter(config)


# ---------------------------------------------------------------------------
# EvernoteAPI -- authentication
# ---------------------------------------------------------------------------

class TestEvernoteAPIAuthentication:

    @respx.mock
    @pytest.mark.asyncio
    async def test_get_user_success(self):
        respx.get("https://api.evernote.com/users/me").mock(
            return_value=httpx.Response(200, json={"username": "testuser", "id": 1})
        )
        async with EvernoteAPI("en_test") as api:
            user = await api.get_user()
        assert user["username"] == "testuser"

    @respx.mock
    @pytest.mark.asyncio
    async def test_get_user_401(self):
        respx.get("https://api.evernote.com/users/me").mock(
            return_value=httpx.Response(401, json={"message": "Unauthorized"})
        )
        async with EvernoteAPI("bad_token") as api:
            with pytest.raises(AuthenticationError):
                await api.get_user()

    @respx.mock
    @pytest.mark.asyncio
    async def test_get_user_403(self):
        respx.get("https://api.evernote.com/users/me").mock(
            return_value=httpx.Response(403, json={"message": "Forbidden"})
        )
        async with EvernoteAPI("en_test") as api:
            with pytest.raises(AuthenticationError):
                await api.get_user()

    @respx.mock
    @pytest.mark.asyncio
    async def test_rate_limit_429(self):
        respx.get("https://api.evernote.com/users/me").mock(
            return_value=httpx.Response(429, json={"message": "rate limit"})
        )
        async with EvernoteAPI("en_test") as api:
            with pytest.raises(RateLimitError):
                await api.get_user()


# ---------------------------------------------------------------------------
# EvernoteAPI -- notebooks
# ---------------------------------------------------------------------------

class TestEvernoteAPINotebooks:

    @respx.mock
    @pytest.mark.asyncio
    async def test_get_notebooks(self):
        notebooks = [
            {"guid": "nb-1", "name": "Work"},
            {"guid": "nb-2", "name": "Personal"},
        ]
        respx.get("https://api.evernote.com/notebooks").mock(
            return_value=httpx.Response(200, json=notebooks)
        )
        async with EvernoteAPI("en_test") as api:
            result = await api.get_notebooks()
        assert len(result) == 2
        assert result[0]["name"] == "Work"


# ---------------------------------------------------------------------------
# EvernoteAPI -- notes CRUD
# ---------------------------------------------------------------------------

class TestEvernoteAPINotes:

    @respx.mock
    @pytest.mark.asyncio
    async def test_find_notes(self):
        notes_resp = {"notes": [_make_note(guid="n1"), _make_note(guid="n2")]}
        respx.get("https://api.evernote.com/notes").mock(
            return_value=httpx.Response(200, json=notes_resp)
        )
        async with EvernoteAPI("en_test") as api:
            result = await api.find_notes()
        assert len(result["notes"]) == 2

    @respx.mock
    @pytest.mark.asyncio
    async def test_find_notes_with_notebook_filter(self):
        notes_resp = {"notes": [_make_note()]}
        route = respx.get("https://api.evernote.com/notes").mock(
            return_value=httpx.Response(200, json=notes_resp)
        )
        async with EvernoteAPI("en_test") as api:
            result = await api.find_notes(notebook_guid="nb-guid-001")
        assert route.called
        assert "notebookGuid" in str(route.calls[0].request.url)

    @respx.mock
    @pytest.mark.asyncio
    async def test_get_note(self):
        note = _make_note(guid="n1")
        respx.get("https://api.evernote.com/notes/n1").mock(
            return_value=httpx.Response(200, json=note)
        )
        async with EvernoteAPI("en_test") as api:
            result = await api.get_note("n1")
        assert result["guid"] == "n1"

    @respx.mock
    @pytest.mark.asyncio
    async def test_create_note(self):
        created = _make_note(guid="new-guid")
        respx.post("https://api.evernote.com/notes").mock(
            return_value=httpx.Response(201, json=created)
        )
        async with EvernoteAPI("en_test") as api:
            result = await api.create_note("nb-guid-001", {"title": "New note"})
        assert result["guid"] == "new-guid"

    @respx.mock
    @pytest.mark.asyncio
    async def test_update_note(self):
        updated = _make_note(guid="n1", title="Updated title")
        respx.put("https://api.evernote.com/notes/n1").mock(
            return_value=httpx.Response(200, json=updated)
        )
        async with EvernoteAPI("en_test") as api:
            result = await api.update_note("n1", {"title": "Updated title"})
        assert result["title"] == "Updated title"

    @respx.mock
    @pytest.mark.asyncio
    async def test_delete_note(self):
        respx.delete("https://api.evernote.com/notes/n1").mock(
            return_value=httpx.Response(204)
        )
        async with EvernoteAPI("en_test") as api:
            result = await api.delete_note("n1")
        assert result == {}

    @respx.mock
    @pytest.mark.asyncio
    async def test_404_raises_network_error(self):
        respx.get("https://api.evernote.com/notes/missing").mock(
            return_value=httpx.Response(404, json={"message": "Not Found"})
        )
        async with EvernoteAPI("en_test") as api:
            with pytest.raises(NetworkError):
                await api.get_note("missing")

    @respx.mock
    @pytest.mark.asyncio
    async def test_422_raises_validation_error(self):
        respx.post("https://api.evernote.com/notes").mock(
            return_value=httpx.Response(422, json={"message": "Validation Failed"})
        )
        async with EvernoteAPI("en_test") as api:
            with pytest.raises(ValidationError):
                await api.create_note("nb-1", {"title": ""})


# ---------------------------------------------------------------------------
# Adapter -- authenticate / test_connection
# ---------------------------------------------------------------------------

class TestEvernoteAdapterAuthentication:

    @respx.mock
    @pytest.mark.asyncio
    async def test_authenticate_success(self, adapter):
        respx.get("https://api.evernote.com/users/me").mock(
            return_value=httpx.Response(200, json={"username": "testuser", "id": 1})
        )
        result = await adapter.authenticate()
        assert result is True

    @respx.mock
    @pytest.mark.asyncio
    async def test_authenticate_failure(self, adapter):
        respx.get("https://api.evernote.com/users/me").mock(
            return_value=httpx.Response(401, json={"message": "Unauthorized"})
        )
        with pytest.raises(AuthenticationError):
            await adapter.authenticate()

    @respx.mock
    @pytest.mark.asyncio
    async def test_authenticate_no_token(self, config):
        config.credentials = {}
        adapter = EvernoteAdapter(config)
        with pytest.raises(AuthenticationError, match="No Evernote token"):
            await adapter.authenticate()

    @respx.mock
    @pytest.mark.asyncio
    async def test_test_connection_success(self, adapter):
        respx.get("https://api.evernote.com/users/me").mock(
            return_value=httpx.Response(200, json={"username": "testuser", "id": 1})
        )
        assert await adapter.test_connection() is True

    @respx.mock
    @pytest.mark.asyncio
    async def test_test_connection_failure(self, adapter):
        respx.get("https://api.evernote.com/users/me").mock(
            return_value=httpx.Response(401, json={"message": "Unauthorized"})
        )
        assert await adapter.test_connection() is False

    def test_get_required_credentials(self, adapter):
        assert adapter.get_required_credentials() == ["evernote_token"]


# ---------------------------------------------------------------------------
# Adapter -- fetch_items
# ---------------------------------------------------------------------------

class TestEvernoteAdapterFetchItems:

    @respx.mock
    @pytest.mark.asyncio
    async def test_fetch_items_basic(self, adapter):
        respx.get("https://api.evernote.com/users/me").mock(
            return_value=httpx.Response(200, json={"username": "testuser", "id": 1})
        )
        notes = [_make_note(guid="n1", title="First"), _make_note(guid="n2", title="Second")]
        respx.get("https://api.evernote.com/notes").mock(
            return_value=httpx.Response(200, json={"notes": notes})
        )
        items = await adapter.fetch_items()
        assert len(items) == 2
        assert items[0].title == "First"
        assert items[1].title == "Second"

    @respx.mock
    @pytest.mark.asyncio
    async def test_fetch_items_with_since(self, adapter):
        respx.get("https://api.evernote.com/users/me").mock(
            return_value=httpx.Response(200, json={"username": "testuser", "id": 1})
        )
        notes = [_make_note(guid="n1")]
        route = respx.get("https://api.evernote.com/notes").mock(
            return_value=httpx.Response(200, json={"notes": notes})
        )
        since = datetime(2025, 6, 1, tzinfo=timezone.utc)
        items = await adapter.fetch_items(since=since)
        assert len(items) == 1
        assert "updatedAfter" in str(route.calls[0].request.url)


# ---------------------------------------------------------------------------
# Adapter -- create_item
# ---------------------------------------------------------------------------

class TestEvernoteAdapterCreateItem:

    @respx.mock
    @pytest.mark.asyncio
    async def test_create_item(self, adapter):
        respx.get("https://api.evernote.com/users/me").mock(
            return_value=httpx.Response(200, json={"username": "testuser", "id": 1})
        )
        respx.post("https://api.evernote.com/notes").mock(
            return_value=httpx.Response(201, json={"guid": "new-guid", "title": "Buy groceries"})
        )
        todo = _make_todo()
        result = await adapter.create_item(todo)
        assert result == "new-guid"


# ---------------------------------------------------------------------------
# Adapter -- update_item
# ---------------------------------------------------------------------------

class TestEvernoteAdapterUpdateItem:

    @respx.mock
    @pytest.mark.asyncio
    async def test_update_item(self, adapter):
        respx.get("https://api.evernote.com/users/me").mock(
            return_value=httpx.Response(200, json={"username": "testuser", "id": 1})
        )
        respx.put("https://api.evernote.com/notes/n1").mock(
            return_value=httpx.Response(200, json=_make_note(guid="n1", title="Updated"))
        )
        todo = _make_todo(text="Updated")
        result = await adapter.update_item("n1", todo)
        assert result is True


# ---------------------------------------------------------------------------
# Adapter -- delete_item
# ---------------------------------------------------------------------------

class TestEvernoteAdapterDeleteItem:

    @respx.mock
    @pytest.mark.asyncio
    async def test_delete_item_success(self, adapter):
        respx.get("https://api.evernote.com/users/me").mock(
            return_value=httpx.Response(200, json={"username": "testuser", "id": 1})
        )
        respx.delete("https://api.evernote.com/notes/n1").mock(
            return_value=httpx.Response(204)
        )
        result = await adapter.delete_item("n1")
        assert result is True

    @respx.mock
    @pytest.mark.asyncio
    async def test_delete_item_failure(self, adapter):
        respx.get("https://api.evernote.com/users/me").mock(
            return_value=httpx.Response(200, json={"username": "testuser", "id": 1})
        )
        respx.delete("https://api.evernote.com/notes/n1").mock(
            return_value=httpx.Response(500, json={"message": "Server error"})
        )
        result = await adapter.delete_item("n1")
        assert result is False


# ---------------------------------------------------------------------------
# Adapter -- fetch_projects
# ---------------------------------------------------------------------------

class TestEvernoteAdapterFetchProjects:

    @respx.mock
    @pytest.mark.asyncio
    async def test_fetch_projects(self, adapter):
        respx.get("https://api.evernote.com/users/me").mock(
            return_value=httpx.Response(200, json={"username": "testuser", "id": 1})
        )
        notebooks = [
            {"guid": "nb-1", "name": "Work"},
            {"guid": "nb-2", "name": "Personal"},
        ]
        respx.get("https://api.evernote.com/notebooks").mock(
            return_value=httpx.Response(200, json=notebooks)
        )
        projects = await adapter.fetch_projects()
        assert projects == {"Work": "nb-1", "Personal": "nb-2"}


# ---------------------------------------------------------------------------
# Adapter -- mapping
# ---------------------------------------------------------------------------

class TestEvernoteAdapterMapping:

    def test_map_todo_to_external_basic(self, adapter):
        todo = _make_todo()
        payload = adapter.map_todo_to_external(todo)
        assert payload["title"] == "Buy groceries"
        assert payload.get("content") == "Milk and eggs"
        assert payload.get("tagNames") == ["shopping"]

    def test_map_todo_to_external_with_due_date(self, adapter):
        due = datetime(2025, 12, 25, 10, 0, tzinfo=timezone.utc)
        todo = _make_todo(due_date=due)
        payload = adapter.map_todo_to_external(todo)
        assert "reminderTime" in payload

    def test_map_todo_to_external_completed(self, adapter):
        todo = _make_todo(completed=True)
        payload = adapter.map_todo_to_external(todo)
        assert "reminderDoneTime" in payload

    def test_map_external_to_todo_basic(self, adapter):
        note = _make_note(title="My task", content="<en-note>Some desc</en-note>")
        item = adapter.map_external_to_todo(note)
        assert isinstance(item, ExternalTodoItem)
        assert item.title == "My task"
        assert item.description == "Some desc"
        assert item.provider == AppSyncProvider.EVERNOTE
        assert item.external_id == "note-guid-001"

    def test_map_external_to_todo_with_tags(self, adapter):
        note = _make_note(tag_names=["urgent", "work"])
        item = adapter.map_external_to_todo(note)
        assert item.tags == ["urgent", "work"]

    def test_map_external_to_todo_with_reminder(self, adapter):
        note = _make_note(reminder_time="2025-12-25T10:00:00+00:00")
        item = adapter.map_external_to_todo(note)
        assert item.due_date is not None
        assert item.due_date.year == 2025
        assert item.due_date.month == 12

    def test_map_external_to_todo_completed(self, adapter):
        note = _make_note(reminder_done_time="2025-06-15T12:00:00+00:00")
        item = adapter.map_external_to_todo(note)
        assert item.completed is True
        assert item.completed_at is not None

    def test_map_external_to_todo_not_completed(self, adapter):
        note = _make_note()
        item = adapter.map_external_to_todo(note)
        assert item.completed is False

    def test_extract_plain_text(self):
        assert EvernoteAdapter._extract_plain_text("<en-note>Hello <b>world</b></en-note>") == "Hello world"
        assert EvernoteAdapter._extract_plain_text("") == ""
        assert EvernoteAdapter._extract_plain_text("<p>test &amp; done</p>") == "test & done"

    def test_map_external_to_todo_timestamps(self, adapter):
        note = _make_note(
            created="2025-01-01T00:00:00+00:00",
            updated="2025-06-15T12:00:00+00:00",
        )
        item = adapter.map_external_to_todo(note)
        assert item.created_at is not None
        assert item.updated_at is not None
        assert item.created_at.year == 2025
        assert item.updated_at.month == 6

    def test_get_supported_features(self, adapter):
        features = adapter.get_supported_features()
        assert "create" in features
        assert "tags" in features
        assert "due_dates" in features
