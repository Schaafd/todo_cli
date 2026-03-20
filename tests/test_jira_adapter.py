"""Tests for the Jira sync adapter."""

import httpx
import pytest
import respx
from datetime import datetime, timezone
from typing import Dict, Any

from todo_cli.sync.providers.jira_adapter import (
    JiraAPI,
    JiraAdapter,
    JIRA_PRIORITY_TO_INT,
    JIRA_PRIORITY_TO_TODO,
    TODO_PRIORITY_TO_JIRA,
    JIRA_STATUS_TO_TODO,
    INT_TO_JIRA_PRIORITY,
)
from todo_cli.sync.app_sync_adapter import AuthenticationError, NetworkError
from todo_cli.sync.app_sync_models import AppSyncProvider, AppSyncConfig, ExternalTodoItem
from todo_cli.domain import Todo, Priority, TodoStatus


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

JIRA_BASE = "https://test.atlassian.net"
API_BASE = f"{JIRA_BASE}/rest/api/3/"


def _make_config(**overrides) -> AppSyncConfig:
    defaults = dict(
        provider=AppSyncProvider.JIRA,
        credentials={"jira_email": "user@example.com", "jira_token": "tok123"},
        settings={"jira_base_url": JIRA_BASE, "jira_project_key": "TEST"},
    )
    defaults.update(overrides)
    return AppSyncConfig(**defaults)


def _make_issue(
    key: str = "TEST-1",
    summary: str = "Fix the bug",
    description: Any = None,
    priority: str = "High",
    labels: list | None = None,
    status: str = "To Do",
    assignee: str | None = None,
    created: str = "2025-06-01T10:00:00.000+0000",
    updated: str = "2025-06-02T12:00:00.000+0000",
    duedate: str | None = None,
    resolution_date: str | None = None,
) -> Dict[str, Any]:
    fields: Dict[str, Any] = {
        "summary": summary,
        "priority": {"name": priority},
        "labels": labels or [],
        "status": {"name": status},
        "created": created,
        "updated": updated,
        "project": {"key": "TEST", "id": "10000"},
    }
    if description is not None:
        fields["description"] = description
    if assignee:
        fields["assignee"] = {"displayName": assignee, "accountId": "abc123"}
    if duedate:
        fields["duedate"] = duedate
    if resolution_date:
        fields["resolutiondate"] = resolution_date
    return {"key": key, "id": "10001", "fields": fields}


def _adf_description(text: str) -> Dict[str, Any]:
    return {
        "type": "doc",
        "version": 1,
        "content": [
            {
                "type": "paragraph",
                "content": [{"type": "text", "text": text}],
            }
        ],
    }


@pytest.fixture
def config():
    return _make_config()


@pytest.fixture
def adapter(config):
    return JiraAdapter(config)


# ---------------------------------------------------------------------------
# Authentication tests
# ---------------------------------------------------------------------------


class TestAuthentication:
    @respx.mock
    @pytest.mark.asyncio
    async def test_authenticate_success(self, adapter):
        respx.get(f"{API_BASE}myself").mock(
            return_value=httpx.Response(200, json={"accountId": "abc", "displayName": "Test User"})
        )
        result = await adapter.authenticate()
        assert result is True

    @respx.mock
    @pytest.mark.asyncio
    async def test_authenticate_invalid_credentials(self, adapter):
        respx.get(f"{API_BASE}myself").mock(return_value=httpx.Response(401))
        with pytest.raises(AuthenticationError):
            await adapter.authenticate()

    @pytest.mark.asyncio
    async def test_authenticate_missing_credentials(self):
        cfg = _make_config(credentials={})
        adp = JiraAdapter(cfg)
        with pytest.raises(AuthenticationError, match="Missing Jira email"):
            await adp.authenticate()

    @respx.mock
    @pytest.mark.asyncio
    async def test_test_connection_success(self, adapter):
        respx.get(f"{API_BASE}myself").mock(
            return_value=httpx.Response(200, json={"accountId": "abc", "displayName": "Test"})
        )
        assert await adapter.test_connection() is True

    @respx.mock
    @pytest.mark.asyncio
    async def test_test_connection_failure(self, adapter):
        respx.get(f"{API_BASE}myself").mock(return_value=httpx.Response(401))
        assert await adapter.test_connection() is False


# ---------------------------------------------------------------------------
# Fetch issues
# ---------------------------------------------------------------------------


class TestFetchItems:
    @respx.mock
    @pytest.mark.asyncio
    async def test_fetch_issues_maps_to_external_items(self, adapter):
        # Auth
        respx.get(f"{API_BASE}myself").mock(
            return_value=httpx.Response(200, json={"accountId": "abc", "displayName": "Test"})
        )
        # Search
        issues = [
            _make_issue(key="TEST-1", summary="First issue", priority="High", status="To Do"),
            _make_issue(key="TEST-2", summary="Second issue", priority="Low", status="In Progress"),
        ]
        respx.get(f"{API_BASE}search").mock(
            return_value=httpx.Response(200, json={"issues": issues, "total": 2})
        )

        items = await adapter.fetch_items()
        assert len(items) == 2
        assert items[0].external_id == "TEST-1"
        assert items[0].title == "First issue"
        assert items[0].provider == AppSyncProvider.JIRA
        assert items[1].external_id == "TEST-2"

    @respx.mock
    @pytest.mark.asyncio
    async def test_fetch_issues_with_since(self, adapter):
        respx.get(f"{API_BASE}myself").mock(
            return_value=httpx.Response(200, json={"accountId": "abc", "displayName": "Test"})
        )
        respx.get(f"{API_BASE}search").mock(
            return_value=httpx.Response(200, json={"issues": [], "total": 0})
        )
        since = datetime(2025, 6, 1, tzinfo=timezone.utc)
        items = await adapter.fetch_items(since=since)
        assert items == []
        # Verify JQL contained the updated filter
        call = respx.calls[-1]
        assert "updated" in str(call.request.url)


# ---------------------------------------------------------------------------
# Create issue
# ---------------------------------------------------------------------------


class TestCreateItem:
    @respx.mock
    @pytest.mark.asyncio
    async def test_create_issue(self, adapter):
        respx.get(f"{API_BASE}myself").mock(
            return_value=httpx.Response(200, json={"accountId": "abc", "displayName": "Test"})
        )
        respx.post(f"{API_BASE}issue").mock(
            return_value=httpx.Response(201, json={"id": "10001", "key": "TEST-42"})
        )

        todo = Todo(id=1, text="New task", priority=Priority.HIGH, project="myproject")
        key = await adapter.create_item(todo)
        assert key == "TEST-42"


# ---------------------------------------------------------------------------
# Update issue
# ---------------------------------------------------------------------------


class TestUpdateItem:
    @respx.mock
    @pytest.mark.asyncio
    async def test_update_issue(self, adapter):
        respx.get(f"{API_BASE}myself").mock(
            return_value=httpx.Response(200, json={"accountId": "abc", "displayName": "Test"})
        )
        respx.put(f"{API_BASE}issue/TEST-1").mock(
            return_value=httpx.Response(204)
        )

        todo = Todo(id=1, text="Updated task", priority=Priority.MEDIUM)
        result = await adapter.update_item("TEST-1", todo)
        assert result is True

    @respx.mock
    @pytest.mark.asyncio
    async def test_update_issue_with_completion_transition(self, adapter):
        respx.get(f"{API_BASE}myself").mock(
            return_value=httpx.Response(200, json={"accountId": "abc", "displayName": "Test"})
        )
        respx.put(f"{API_BASE}issue/TEST-1").mock(
            return_value=httpx.Response(204)
        )
        respx.get(f"{API_BASE}issue/TEST-1/transitions").mock(
            return_value=httpx.Response(
                200,
                json={"transitions": [{"id": "31", "name": "Done"}, {"id": "21", "name": "In Progress"}]},
            )
        )
        respx.post(f"{API_BASE}issue/TEST-1/transitions").mock(
            return_value=httpx.Response(204)
        )

        todo = Todo(id=1, text="Done task", status=TodoStatus.COMPLETED, completed=True)
        result = await adapter.update_item("TEST-1", todo)
        assert result is True


# ---------------------------------------------------------------------------
# Transition (complete) issue
# ---------------------------------------------------------------------------


class TestTransitionIssue:
    @respx.mock
    @pytest.mark.asyncio
    async def test_transition_to_done(self, adapter):
        respx.get(f"{API_BASE}myself").mock(
            return_value=httpx.Response(200, json={"accountId": "abc", "displayName": "Test"})
        )
        respx.put(f"{API_BASE}issue/TEST-5").mock(return_value=httpx.Response(204))
        respx.get(f"{API_BASE}issue/TEST-5/transitions").mock(
            return_value=httpx.Response(
                200,
                json={"transitions": [{"id": "31", "name": "Done"}]},
            )
        )
        respx.post(f"{API_BASE}issue/TEST-5/transitions").mock(
            return_value=httpx.Response(204)
        )

        todo = Todo(id=5, text="Complete me", completed=True, status=TodoStatus.COMPLETED)
        result = await adapter.update_item("TEST-5", todo)
        assert result is True
        # The transitions POST should have been called
        assert respx.calls.call_count >= 3


# ---------------------------------------------------------------------------
# Project listing
# ---------------------------------------------------------------------------


class TestFetchProjects:
    @respx.mock
    @pytest.mark.asyncio
    async def test_fetch_projects(self, adapter):
        respx.get(f"{API_BASE}myself").mock(
            return_value=httpx.Response(200, json={"accountId": "abc", "displayName": "Test"})
        )
        respx.get(f"{API_BASE}project").mock(
            return_value=httpx.Response(
                200,
                json=[
                    {"key": "TEST", "id": "10000", "name": "Test Project"},
                    {"key": "DEV", "id": "10001", "name": "Dev Project"},
                ],
            )
        )

        projects = await adapter.fetch_projects()
        assert projects == {"TEST": "10000", "DEV": "10001"}


# ---------------------------------------------------------------------------
# Priority mapping
# ---------------------------------------------------------------------------


class TestPriorityMapping:
    def test_jira_priority_to_int(self):
        assert JIRA_PRIORITY_TO_INT["Highest"] == 4
        assert JIRA_PRIORITY_TO_INT["High"] == 3
        assert JIRA_PRIORITY_TO_INT["Medium"] == 2
        assert JIRA_PRIORITY_TO_INT["Low"] == 1
        assert JIRA_PRIORITY_TO_INT["Lowest"] == 0

    def test_int_to_jira_priority(self):
        assert INT_TO_JIRA_PRIORITY[4] == "Highest"
        assert INT_TO_JIRA_PRIORITY[0] == "Lowest"

    def test_jira_priority_to_todo(self):
        assert JIRA_PRIORITY_TO_TODO["Highest"] == Priority.CRITICAL
        assert JIRA_PRIORITY_TO_TODO["High"] == Priority.HIGH
        assert JIRA_PRIORITY_TO_TODO["Medium"] == Priority.MEDIUM
        assert JIRA_PRIORITY_TO_TODO["Low"] == Priority.LOW
        assert JIRA_PRIORITY_TO_TODO["Lowest"] == Priority.LOW

    def test_todo_priority_to_jira(self):
        assert TODO_PRIORITY_TO_JIRA[Priority.CRITICAL] == "Highest"
        assert TODO_PRIORITY_TO_JIRA[Priority.HIGH] == "High"
        assert TODO_PRIORITY_TO_JIRA[Priority.MEDIUM] == "Medium"
        assert TODO_PRIORITY_TO_JIRA[Priority.LOW] == "Low"

    def test_map_todo_to_external_priority(self, adapter):
        todo = Todo(id=1, text="Test", priority=Priority.HIGH)
        fields = adapter.map_todo_to_external(todo)
        assert fields["priority"] == {"name": "High"}

    def test_map_external_to_todo_priority(self, adapter):
        issue = _make_issue(priority="Highest")
        item = adapter.map_external_to_todo(issue)
        assert item.priority == 4  # JIRA_PRIORITY_TO_INT["Highest"]


# ---------------------------------------------------------------------------
# Field mapping
# ---------------------------------------------------------------------------


class TestFieldMapping:
    def test_summary_maps_to_title(self, adapter):
        issue = _make_issue(summary="My summary")
        item = adapter.map_external_to_todo(issue)
        assert item.title == "My summary"

    def test_adf_description(self, adapter):
        issue = _make_issue(description=_adf_description("Hello world"))
        item = adapter.map_external_to_todo(issue)
        assert item.description == "Hello world"

    def test_plain_string_description(self, adapter):
        issue = _make_issue(description="Plain text desc")
        item = adapter.map_external_to_todo(issue)
        assert item.description == "Plain text desc"

    def test_no_description(self, adapter):
        issue = _make_issue()
        item = adapter.map_external_to_todo(issue)
        assert item.description == ""

    def test_labels_map_to_tags(self, adapter):
        issue = _make_issue(labels=["bug", "frontend"])
        item = adapter.map_external_to_todo(issue)
        assert item.tags == ["bug", "frontend"]

    def test_status_to_do(self, adapter):
        issue = _make_issue(status="To Do")
        item = adapter.map_external_to_todo(issue)
        assert item.completed is False

    def test_status_open(self, adapter):
        issue = _make_issue(status="Open")
        item = adapter.map_external_to_todo(issue)
        assert item.completed is False

    def test_status_in_progress(self, adapter):
        issue = _make_issue(status="In Progress")
        item = adapter.map_external_to_todo(issue)
        assert item.completed is False

    def test_status_done(self, adapter):
        issue = _make_issue(status="Done", resolution_date="2025-06-10T09:00:00.000+0000")
        item = adapter.map_external_to_todo(issue)
        assert item.completed is True
        assert item.completed_at is not None

    def test_status_closed(self, adapter):
        issue = _make_issue(status="Closed", resolution_date="2025-06-10T09:00:00.000+0000")
        item = adapter.map_external_to_todo(issue)
        assert item.completed is True

    def test_status_resolved(self, adapter):
        issue = _make_issue(status="Resolved", resolution_date="2025-06-10T09:00:00.000+0000")
        item = adapter.map_external_to_todo(issue)
        assert item.completed is True

    def test_assignee_mapping(self, adapter):
        issue = _make_issue(assignee="John Doe")
        item = adapter.map_external_to_todo(issue)
        assert item.assignee == "John Doe"

    def test_due_date_mapping(self, adapter):
        issue = _make_issue(duedate="2025-07-15")
        item = adapter.map_external_to_todo(issue)
        assert item.due_date is not None
        assert item.due_date.year == 2025
        assert item.due_date.month == 7
        assert item.due_date.day == 15

    def test_project_fallback_to_key(self, adapter):
        issue = _make_issue()
        item = adapter.map_external_to_todo(issue)
        assert item.project == "TEST"

    def test_url_constructed(self, adapter):
        issue = _make_issue(key="TEST-99")
        item = adapter.map_external_to_todo(issue)
        assert item.url == f"{JIRA_BASE}/browse/TEST-99"

    def test_map_todo_to_external_fields(self, adapter):
        todo = Todo(
            id=1,
            text="Build feature",
            description="Detailed description",
            priority=Priority.CRITICAL,
            tags=["backend", "urgent"],
            due_date=datetime(2025, 8, 1, tzinfo=timezone.utc),
            assignees=["acc123"],
        )
        fields = adapter.map_todo_to_external(todo)
        assert fields["summary"] == "Build feature"
        assert fields["project"] == {"key": "TEST"}
        assert fields["issuetype"] == {"name": "Task"}
        assert fields["priority"] == {"name": "Highest"}
        assert fields["labels"] == ["backend", "urgent"]
        assert fields["duedate"] == "2025-08-01"
        assert fields["assignee"] == {"accountId": "acc123"}
        assert "description" in fields

    def test_required_credentials(self, adapter):
        assert adapter.get_required_credentials() == ["jira_email", "jira_token"]

    def test_created_and_updated_dates(self, adapter):
        issue = _make_issue(
            created="2025-06-01T10:00:00.000+0000",
            updated="2025-06-02T12:00:00.000+0000",
        )
        item = adapter.map_external_to_todo(issue)
        assert item.created_at is not None
        assert item.updated_at is not None
        assert item.created_at.tzinfo is not None
        assert item.updated_at.tzinfo is not None


# ---------------------------------------------------------------------------
# JiraAPI unit tests
# ---------------------------------------------------------------------------


class TestJiraAPI:
    @respx.mock
    @pytest.mark.asyncio
    async def test_search_issues(self):
        respx.get(f"{API_BASE}search").mock(
            return_value=httpx.Response(200, json={"issues": [], "total": 0})
        )
        async with JiraAPI(JIRA_BASE, email="u@e.com", token="tok") as api:
            result = await api.search_issues("project = TEST")
        assert result["total"] == 0

    @respx.mock
    @pytest.mark.asyncio
    async def test_create_issue(self):
        respx.post(f"{API_BASE}issue").mock(
            return_value=httpx.Response(201, json={"id": "100", "key": "TEST-1"})
        )
        async with JiraAPI(JIRA_BASE, email="u@e.com", token="tok") as api:
            result = await api.create_issue({"summary": "New"})
        assert result["key"] == "TEST-1"

    @respx.mock
    @pytest.mark.asyncio
    async def test_update_issue(self):
        respx.put(f"{API_BASE}issue/TEST-1").mock(return_value=httpx.Response(204))
        async with JiraAPI(JIRA_BASE, email="u@e.com", token="tok") as api:
            result = await api.update_issue("TEST-1", {"summary": "Updated"})
        assert result == {}

    @respx.mock
    @pytest.mark.asyncio
    async def test_transition_issue(self):
        respx.post(f"{API_BASE}issue/TEST-1/transitions").mock(return_value=httpx.Response(204))
        async with JiraAPI(JIRA_BASE, email="u@e.com", token="tok") as api:
            result = await api.transition_issue("TEST-1", "31")
        assert result == {}

    @respx.mock
    @pytest.mark.asyncio
    async def test_get_projects(self):
        respx.get(f"{API_BASE}project").mock(
            return_value=httpx.Response(200, json=[{"key": "A", "id": "1"}])
        )
        async with JiraAPI(JIRA_BASE, email="u@e.com", token="tok") as api:
            projects = await api.get_projects()
        assert len(projects) == 1

    @respx.mock
    @pytest.mark.asyncio
    async def test_get_priorities(self):
        respx.get(f"{API_BASE}priority").mock(
            return_value=httpx.Response(
                200, json=[{"id": "1", "name": "High"}, {"id": "2", "name": "Low"}]
            )
        )
        async with JiraAPI(JIRA_BASE, email="u@e.com", token="tok") as api:
            priorities = await api.get_priorities()
        assert len(priorities) == 2

    @respx.mock
    @pytest.mark.asyncio
    async def test_rate_limit_error(self):
        respx.get(f"{API_BASE}myself").mock(return_value=httpx.Response(429))
        async with JiraAPI(JIRA_BASE, email="u@e.com", token="tok") as api:
            with pytest.raises(Exception, match="rate limit"):
                await api.get_myself()

    @respx.mock
    @pytest.mark.asyncio
    async def test_bearer_token_auth(self):
        route = respx.get(f"{API_BASE}myself").mock(
            return_value=httpx.Response(200, json={"accountId": "abc"})
        )
        async with JiraAPI(JIRA_BASE, bearer_token="mybearer") as api:
            await api.get_myself()
        assert "Bearer mybearer" in str(route.calls[0].request.headers.get("authorization", ""))
