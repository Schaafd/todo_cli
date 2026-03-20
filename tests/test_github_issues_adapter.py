"""Tests for the GitHub Issues sync adapter."""

import pytest
import httpx
import respx
from datetime import datetime, timezone

from todo_cli.sync.providers.github_issues_adapter import (
    GitHubAPI,
    GitHubIssuesAdapter,
    PRIORITY_LABEL_MAP,
    PRIORITY_INT_TO_LABEL,
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
    """Create a minimal AppSyncConfig for GitHub Issues."""
    defaults = dict(
        provider=AppSyncProvider.GITHUB_ISSUES,
        credentials={"github_token": "ghp_test123"},
        settings={"github_repo": "octocat/hello-world"},
    )
    defaults.update(overrides)
    return AppSyncConfig(**defaults)


def _make_issue(
    number: int = 1,
    title: str = "Test issue",
    body: str = "Issue body",
    state: str = "open",
    labels: list | None = None,
    assignees: list | None = None,
    milestone: dict | None = None,
    created_at: str = "2025-01-01T00:00:00Z",
    updated_at: str = "2025-01-02T00:00:00Z",
    closed_at: str | None = None,
    html_url: str | None = None,
) -> dict:
    """Build a fake GitHub issue payload."""
    issue: dict = {
        "number": number,
        "title": title,
        "body": body,
        "state": state,
        "labels": labels or [],
        "assignees": assignees or [],
        "milestone": milestone,
        "created_at": created_at,
        "updated_at": updated_at,
        "closed_at": closed_at,
        "html_url": html_url or f"https://github.com/octocat/hello-world/issues/{number}",
    }
    return issue


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
        assignees=["alice"],
    )
    defaults.update(overrides)
    return Todo(**defaults)


@pytest.fixture
def config():
    return _make_config()


@pytest.fixture
def adapter(config):
    return GitHubIssuesAdapter(config)


# ---------------------------------------------------------------------------
# GitHubAPI – authentication
# ---------------------------------------------------------------------------

class TestGitHubAPIAuthentication:

    @respx.mock
    @pytest.mark.asyncio
    async def test_get_authenticated_user_success(self):
        respx.get("https://api.github.com/user").mock(
            return_value=httpx.Response(200, json={"login": "octocat", "id": 1})
        )
        async with GitHubAPI("ghp_test") as api:
            user = await api.get_authenticated_user()
        assert user["login"] == "octocat"

    @respx.mock
    @pytest.mark.asyncio
    async def test_get_authenticated_user_401(self):
        respx.get("https://api.github.com/user").mock(
            return_value=httpx.Response(401, json={"message": "Bad credentials"})
        )
        async with GitHubAPI("bad_token") as api:
            with pytest.raises(AuthenticationError):
                await api.get_authenticated_user()

    @respx.mock
    @pytest.mark.asyncio
    async def test_rate_limit_403(self):
        respx.get("https://api.github.com/user").mock(
            return_value=httpx.Response(
                403,
                json={"message": "rate limit"},
                headers={"X-RateLimit-Remaining": "0"},
            )
        )
        async with GitHubAPI("ghp_test") as api:
            with pytest.raises(RateLimitError):
                await api.get_authenticated_user()

    @respx.mock
    @pytest.mark.asyncio
    async def test_rate_limit_429(self):
        respx.get("https://api.github.com/user").mock(
            return_value=httpx.Response(429, json={"message": "rate limit"})
        )
        async with GitHubAPI("ghp_test") as api:
            with pytest.raises(RateLimitError):
                await api.get_authenticated_user()

    @respx.mock
    @pytest.mark.asyncio
    async def test_forbidden_not_rate_limit(self):
        """403 without X-RateLimit-Remaining: 0 raises AuthenticationError."""
        respx.get("https://api.github.com/user").mock(
            return_value=httpx.Response(403, json={"message": "forbidden"})
        )
        async with GitHubAPI("ghp_test") as api:
            with pytest.raises(AuthenticationError):
                await api.get_authenticated_user()


# ---------------------------------------------------------------------------
# GitHubAPI – issues CRUD
# ---------------------------------------------------------------------------

class TestGitHubAPIIssues:

    @respx.mock
    @pytest.mark.asyncio
    async def test_get_issues(self):
        issues = [_make_issue(number=1), _make_issue(number=2)]
        respx.get("https://api.github.com/repos/octocat/hello-world/issues").mock(
            return_value=httpx.Response(200, json=issues)
        )
        async with GitHubAPI("ghp_test") as api:
            result = await api.get_issues("octocat", "hello-world")
        assert len(result) == 2

    @respx.mock
    @pytest.mark.asyncio
    async def test_create_issue(self):
        respx.post("https://api.github.com/repos/octocat/hello-world/issues").mock(
            return_value=httpx.Response(201, json=_make_issue(number=42, title="New"))
        )
        async with GitHubAPI("ghp_test") as api:
            result = await api.create_issue("octocat", "hello-world", title="New", body="desc")
        assert result["number"] == 42

    @respx.mock
    @pytest.mark.asyncio
    async def test_update_issue(self):
        respx.patch("https://api.github.com/repos/octocat/hello-world/issues/1").mock(
            return_value=httpx.Response(200, json=_make_issue(number=1, title="Updated"))
        )
        async with GitHubAPI("ghp_test") as api:
            result = await api.update_issue("octocat", "hello-world", 1, title="Updated")
        assert result["title"] == "Updated"

    @respx.mock
    @pytest.mark.asyncio
    async def test_close_issue(self):
        respx.patch("https://api.github.com/repos/octocat/hello-world/issues/5").mock(
            return_value=httpx.Response(200, json=_make_issue(number=5, state="closed"))
        )
        async with GitHubAPI("ghp_test") as api:
            result = await api.close_issue("octocat", "hello-world", 5)
        assert result["state"] == "closed"

    @respx.mock
    @pytest.mark.asyncio
    async def test_get_repos(self):
        repos = [{"full_name": "octocat/hello-world", "id": 123}]
        respx.get("https://api.github.com/user/repos").mock(
            return_value=httpx.Response(200, json=repos)
        )
        async with GitHubAPI("ghp_test") as api:
            result = await api.get_repos()
        assert result[0]["full_name"] == "octocat/hello-world"

    @respx.mock
    @pytest.mark.asyncio
    async def test_get_labels(self):
        labels = [{"name": "bug"}, {"name": "enhancement"}]
        respx.get("https://api.github.com/repos/octocat/hello-world/labels").mock(
            return_value=httpx.Response(200, json=labels)
        )
        async with GitHubAPI("ghp_test") as api:
            result = await api.get_labels("octocat", "hello-world")
        assert len(result) == 2

    @respx.mock
    @pytest.mark.asyncio
    async def test_404_raises_network_error(self):
        respx.get("https://api.github.com/repos/octocat/hello-world/issues").mock(
            return_value=httpx.Response(404, json={"message": "Not Found"})
        )
        async with GitHubAPI("ghp_test") as api:
            with pytest.raises(NetworkError):
                await api.get_issues("octocat", "hello-world")

    @respx.mock
    @pytest.mark.asyncio
    async def test_422_raises_validation_error(self):
        respx.post("https://api.github.com/repos/octocat/hello-world/issues").mock(
            return_value=httpx.Response(422, json={"message": "Validation Failed"})
        )
        async with GitHubAPI("ghp_test") as api:
            with pytest.raises(ValidationError):
                await api.create_issue("octocat", "hello-world", title="")


# ---------------------------------------------------------------------------
# Adapter – authenticate / test_connection
# ---------------------------------------------------------------------------

class TestAdapterAuthentication:

    @respx.mock
    @pytest.mark.asyncio
    async def test_authenticate_success(self, adapter):
        respx.get("https://api.github.com/user").mock(
            return_value=httpx.Response(200, json={"login": "octocat", "id": 1})
        )
        result = await adapter.authenticate()
        assert result is True

    @respx.mock
    @pytest.mark.asyncio
    async def test_authenticate_failure(self, adapter):
        respx.get("https://api.github.com/user").mock(
            return_value=httpx.Response(401, json={"message": "Bad credentials"})
        )
        with pytest.raises(AuthenticationError):
            await adapter.authenticate()

    @respx.mock
    @pytest.mark.asyncio
    async def test_authenticate_no_token(self, config):
        config.credentials = {}
        adapter = GitHubIssuesAdapter(config)
        with pytest.raises(AuthenticationError, match="No GitHub token"):
            await adapter.authenticate()

    @respx.mock
    @pytest.mark.asyncio
    async def test_test_connection_success(self, adapter):
        respx.get("https://api.github.com/user").mock(
            return_value=httpx.Response(200, json={"login": "octocat", "id": 1})
        )
        assert await adapter.test_connection() is True

    @respx.mock
    @pytest.mark.asyncio
    async def test_test_connection_failure(self, adapter):
        respx.get("https://api.github.com/user").mock(
            return_value=httpx.Response(401, json={"message": "Bad credentials"})
        )
        assert await adapter.test_connection() is False


# ---------------------------------------------------------------------------
# Adapter – fetch_items
# ---------------------------------------------------------------------------

class TestAdapterFetchItems:

    @respx.mock
    @pytest.mark.asyncio
    async def test_fetch_items_basic(self, adapter):
        # Auth mock
        respx.get("https://api.github.com/user").mock(
            return_value=httpx.Response(200, json={"login": "octocat", "id": 1})
        )
        issues = [
            _make_issue(number=1, title="First issue"),
            _make_issue(number=2, title="Second issue"),
        ]
        respx.get("https://api.github.com/repos/octocat/hello-world/issues").mock(
            return_value=httpx.Response(200, json=issues)
        )

        items = await adapter.fetch_items()
        assert len(items) == 2
        assert items[0].title == "First issue"
        assert items[0].external_id == "1"
        assert items[0].provider == AppSyncProvider.GITHUB_ISSUES

    @respx.mock
    @pytest.mark.asyncio
    async def test_fetch_items_skips_pull_requests(self, adapter):
        respx.get("https://api.github.com/user").mock(
            return_value=httpx.Response(200, json={"login": "octocat", "id": 1})
        )
        issues = [
            _make_issue(number=1, title="Issue"),
            {**_make_issue(number=2, title="PR"), "pull_request": {"url": "..."}},
        ]
        respx.get("https://api.github.com/repos/octocat/hello-world/issues").mock(
            return_value=httpx.Response(200, json=issues)
        )

        items = await adapter.fetch_items()
        assert len(items) == 1
        assert items[0].title == "Issue"


# ---------------------------------------------------------------------------
# Adapter – create_item
# ---------------------------------------------------------------------------

class TestAdapterCreateItem:

    @respx.mock
    @pytest.mark.asyncio
    async def test_create_item(self, adapter):
        respx.get("https://api.github.com/user").mock(
            return_value=httpx.Response(200, json={"login": "octocat", "id": 1})
        )
        respx.post("https://api.github.com/repos/octocat/hello-world/issues").mock(
            return_value=httpx.Response(
                201, json=_make_issue(number=99, title="Buy groceries")
            )
        )

        todo = _make_todo()
        external_id = await adapter.create_item(todo)
        assert external_id == "99"


# ---------------------------------------------------------------------------
# Adapter – update_item
# ---------------------------------------------------------------------------

class TestAdapterUpdateItem:

    @respx.mock
    @pytest.mark.asyncio
    async def test_update_item_open(self, adapter):
        respx.get("https://api.github.com/user").mock(
            return_value=httpx.Response(200, json={"login": "octocat", "id": 1})
        )
        respx.patch("https://api.github.com/repos/octocat/hello-world/issues/10").mock(
            return_value=httpx.Response(200, json=_make_issue(number=10))
        )

        todo = _make_todo(completed=False)
        result = await adapter.update_item("10", todo)
        assert result is True

    @respx.mock
    @pytest.mark.asyncio
    async def test_update_item_closed(self, adapter):
        respx.get("https://api.github.com/user").mock(
            return_value=httpx.Response(200, json={"login": "octocat", "id": 1})
        )
        respx.patch("https://api.github.com/repos/octocat/hello-world/issues/10").mock(
            return_value=httpx.Response(200, json=_make_issue(number=10, state="closed"))
        )

        todo = _make_todo(completed=True, status=TodoStatus.COMPLETED)
        result = await adapter.update_item("10", todo)
        assert result is True


# ---------------------------------------------------------------------------
# Adapter – delete_item (close)
# ---------------------------------------------------------------------------

class TestAdapterDeleteItem:

    @respx.mock
    @pytest.mark.asyncio
    async def test_delete_item(self, adapter):
        respx.get("https://api.github.com/user").mock(
            return_value=httpx.Response(200, json={"login": "octocat", "id": 1})
        )
        respx.patch("https://api.github.com/repos/octocat/hello-world/issues/7").mock(
            return_value=httpx.Response(200, json=_make_issue(number=7, state="closed"))
        )

        result = await adapter.delete_item("7")
        assert result is True


# ---------------------------------------------------------------------------
# Adapter – fetch_projects (repos)
# ---------------------------------------------------------------------------

class TestAdapterFetchProjects:

    @respx.mock
    @pytest.mark.asyncio
    async def test_fetch_projects(self, adapter):
        respx.get("https://api.github.com/user").mock(
            return_value=httpx.Response(200, json={"login": "octocat", "id": 1})
        )
        repos = [
            {"full_name": "octocat/hello-world", "id": 1},
            {"full_name": "octocat/spoon-knife", "id": 2},
        ]
        respx.get("https://api.github.com/user/repos").mock(
            return_value=httpx.Response(200, json=repos)
        )

        projects = await adapter.fetch_projects()
        assert "octocat/hello-world" in projects
        assert projects["octocat/spoon-knife"] == "2"


# ---------------------------------------------------------------------------
# Field mapping – priority labels
# ---------------------------------------------------------------------------

class TestPriorityLabelMapping:

    def test_priority_label_to_int(self):
        assert PRIORITY_LABEL_MAP["priority:high"] == 3
        assert PRIORITY_LABEL_MAP["priority:low"] == 1
        assert PRIORITY_LABEL_MAP["priority:critical"] == 4
        assert PRIORITY_LABEL_MAP["priority:medium"] == 2

    def test_map_external_to_todo_with_priority_label(self, adapter):
        issue = _make_issue(
            labels=[{"name": "bug"}, {"name": "priority:high"}]
        )
        item = adapter.map_external_to_todo(issue)
        assert item.priority == 3
        # "bug" should be in tags but "priority:high" should not
        assert "bug" in item.tags
        assert "priority:high" not in item.tags

    def test_map_todo_to_external_includes_priority_label(self, adapter):
        todo = _make_todo(priority=Priority.HIGH, tags=["bug"])
        payload = adapter.map_todo_to_external(todo)
        assert "priority:high" in payload["labels"]
        assert "bug" in payload["labels"]


# ---------------------------------------------------------------------------
# Field mapping – both directions
# ---------------------------------------------------------------------------

class TestFieldMapping:

    def test_map_external_to_todo_full(self, adapter):
        issue = _make_issue(
            number=42,
            title="Fix the widget",
            body="Detailed description",
            state="closed",
            labels=[{"name": "enhancement"}, {"name": "priority:low"}],
            assignees=[{"login": "alice"}, {"login": "bob"}],
            milestone={"title": "v1.0", "number": 1},
            created_at="2025-06-01T10:00:00Z",
            updated_at="2025-06-02T12:00:00Z",
            closed_at="2025-06-02T12:00:00Z",
        )
        item = adapter.map_external_to_todo(issue)

        assert item.external_id == "42"
        assert item.title == "Fix the widget"
        assert item.description == "Detailed description"
        assert item.completed is True
        assert item.completed_at is not None
        assert item.priority == 1  # low
        assert "enhancement" in item.tags
        assert item.project == "v1.0"
        assert item.assignee == "alice, bob"
        assert item.provider == AppSyncProvider.GITHUB_ISSUES

    def test_map_todo_to_external_full(self, adapter):
        todo = _make_todo(
            text="Deploy v2",
            description="Roll out version 2",
            tags=["deploy", "infra"],
            priority=Priority.CRITICAL,
            assignees=["bob", "carol"],
        )
        payload = adapter.map_todo_to_external(todo)

        assert payload["title"] == "Deploy v2"
        assert payload["body"] == "Roll out version 2"
        assert "deploy" in payload["labels"]
        assert "infra" in payload["labels"]
        assert "priority:critical" in payload["labels"]
        assert payload["assignees"] == ["bob", "carol"]

    def test_map_external_open_state(self, adapter):
        issue = _make_issue(state="open")
        item = adapter.map_external_to_todo(issue)
        assert item.completed is False
        assert item.completed_at is None

    def test_map_external_no_body(self, adapter):
        issue = _make_issue(body=None)
        item = adapter.map_external_to_todo(issue)
        assert item.description == ""

    def test_map_external_no_milestone(self, adapter):
        issue = _make_issue(milestone=None)
        item = adapter.map_external_to_todo(issue)
        assert item.project is None

    def test_map_todo_no_description(self, adapter):
        todo = _make_todo(description="")
        payload = adapter.map_todo_to_external(todo)
        assert "body" not in payload

    def test_map_todo_no_tags_no_priority(self, adapter):
        todo = _make_todo(tags=[], priority=Priority.MEDIUM)
        payload = adapter.map_todo_to_external(todo)
        # Should still have priority label
        assert payload["labels"] == ["priority:medium"]


# ---------------------------------------------------------------------------
# Adapter – get_required_credentials / get_supported_features
# ---------------------------------------------------------------------------

class TestAdapterMeta:

    def test_required_credentials(self, adapter):
        assert adapter.get_required_credentials() == ["github_token"]

    def test_supported_features(self, adapter):
        features = adapter.get_supported_features()
        for f in ["create", "read", "update", "delete", "projects", "tags", "priorities"]:
            assert f in features
