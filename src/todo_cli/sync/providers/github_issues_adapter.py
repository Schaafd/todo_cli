"""GitHub Issues adapter for app synchronization.

This module provides integration with the GitHub Issues API for bidirectional
synchronization of todo items using issues, labels, milestones, and assignees.
"""

import httpx
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any

from ..app_sync_adapter import (
    SyncAdapter,
    AuthenticationError,
    NetworkError,
    ValidationError,
    RateLimitError,
)
from ..app_sync_models import (
    AppSyncProvider,
    AppSyncConfig,
    ExternalTodoItem,
)
from ...domain import Todo, Priority, TodoStatus
from ...utils.datetime import ensure_aware, now_utc


logger = logging.getLogger(__name__)


# Mapping from priority label strings to internal priority integers
PRIORITY_LABEL_MAP = {
    "priority:critical": 4,
    "priority:high": 3,
    "priority:medium": 2,
    "priority:low": 1,
}

PRIORITY_INT_TO_LABEL = {v: k for k, v in PRIORITY_LABEL_MAP.items()}

PRIORITY_ENUM_TO_INT = {
    Priority.CRITICAL: 4,
    Priority.HIGH: 3,
    Priority.MEDIUM: 2,
    Priority.LOW: 1,
}

PRIORITY_INT_TO_ENUM = {v: k for k, v in PRIORITY_ENUM_TO_INT.items()}


class GitHubAPI:
    """GitHub REST API v3 client."""

    BASE_URL = "https://api.github.com"

    def __init__(self, token: str):
        """Initialize GitHub API client.

        Args:
            token: GitHub Personal Access Token
        """
        self.token = token
        self.headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json",
        }
        self.client: Optional[httpx.AsyncClient] = None
        self.logger = logging.getLogger(__name__)

    async def __aenter__(self):
        if self.client is None:
            self.client = httpx.AsyncClient(timeout=30.0)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.client is not None:
            await self.client.aclose()
            self.client = None

    async def _make_request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict] = None,
        params: Optional[Dict] = None,
    ) -> Any:
        """Make HTTP request to GitHub API.

        Args:
            method: HTTP method
            endpoint: API endpoint (relative to BASE_URL)
            data: JSON body data
            params: Query parameters

        Returns:
            Response data

        Raises:
            AuthenticationError: If authentication fails (401)
            RateLimitError: If rate limit is exceeded (429 or 403 with rate limit)
            NetworkError: If network request fails
            ValidationError: If request data is invalid (422)
        """
        if self.client is None:
            raise NetworkError("HTTP client not initialized. Use 'async with' context manager.")

        url = f"{self.BASE_URL}{endpoint}"

        try:
            if method.upper() == "GET":
                response = await self.client.get(url, headers=self.headers, params=params)
            elif method.upper() == "POST":
                response = await self.client.post(url, headers=self.headers, json=data)
            elif method.upper() == "PATCH":
                response = await self.client.patch(url, headers=self.headers, json=data)
            elif method.upper() == "DELETE":
                response = await self.client.delete(url, headers=self.headers)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")

            if response.status_code == 401:
                raise AuthenticationError("Invalid GitHub token")
            elif response.status_code == 403:
                # Check for rate limiting
                remaining = response.headers.get("X-RateLimit-Remaining", "")
                if remaining == "0":
                    raise RateLimitError("GitHub API rate limit exceeded")
                raise AuthenticationError("GitHub API access forbidden")
            elif response.status_code == 404:
                raise NetworkError(f"GitHub resource not found: {endpoint}")
            elif response.status_code == 422:
                raise ValidationError(f"GitHub validation error: {response.text}")
            elif response.status_code == 429:
                raise RateLimitError("GitHub API rate limit exceeded")
            elif response.status_code >= 400:
                raise NetworkError(f"GitHub API error {response.status_code}: {response.text}")

            if response.status_code == 204:
                return {}

            return response.json()

        except httpx.TimeoutException:
            raise NetworkError("GitHub API request timed out")
        except httpx.RequestError as e:
            raise NetworkError(f"GitHub API request failed: {e}")

    # Authentication

    async def get_authenticated_user(self) -> Dict[str, Any]:
        """Get authenticated user information."""
        return await self._make_request("GET", "/user")

    # Issues

    async def get_issues(
        self,
        owner: str,
        repo: str,
        state: str = "open",
        labels: Optional[str] = None,
        since: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Get issues for a repository.

        Args:
            owner: Repository owner
            repo: Repository name
            state: Issue state filter (open, closed, all)
            labels: Comma-separated label names
            since: ISO 8601 timestamp to filter by updated date
        """
        params: Dict[str, Any] = {"state": state, "per_page": 100}
        if labels:
            params["labels"] = labels
        if since:
            params["since"] = since
        return await self._make_request("GET", f"/repos/{owner}/{repo}/issues", params=params)

    async def create_issue(
        self,
        owner: str,
        repo: str,
        title: str,
        body: Optional[str] = None,
        labels: Optional[List[str]] = None,
        assignees: Optional[List[str]] = None,
        milestone: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Create an issue."""
        data: Dict[str, Any] = {"title": title}
        if body is not None:
            data["body"] = body
        if labels:
            data["labels"] = labels
        if assignees:
            data["assignees"] = assignees
        if milestone is not None:
            data["milestone"] = milestone
        return await self._make_request("POST", f"/repos/{owner}/{repo}/issues", data=data)

    async def update_issue(
        self,
        owner: str,
        repo: str,
        issue_number: int,
        **kwargs,
    ) -> Dict[str, Any]:
        """Update an issue.

        Accepted kwargs: title, body, state, labels, assignees, milestone
        """
        return await self._make_request(
            "PATCH", f"/repos/{owner}/{repo}/issues/{issue_number}", data=kwargs
        )

    async def close_issue(self, owner: str, repo: str, issue_number: int) -> Dict[str, Any]:
        """Close an issue by setting its state to closed."""
        return await self.update_issue(owner, repo, issue_number, state="closed")

    # Repos

    async def get_repos(self, per_page: int = 100) -> List[Dict[str, Any]]:
        """Get repositories for the authenticated user."""
        return await self._make_request("GET", "/user/repos", params={"per_page": per_page})

    # Labels

    async def get_labels(self, owner: str, repo: str) -> List[Dict[str, Any]]:
        """Get labels for a repository."""
        return await self._make_request("GET", f"/repos/{owner}/{repo}/labels", params={"per_page": 100})


class GitHubIssuesAdapter(SyncAdapter):
    """GitHub Issues adapter for app synchronization."""

    def __init__(self, config: AppSyncConfig):
        """Initialize GitHub Issues adapter.

        Args:
            config: App sync configuration
        """
        super().__init__(config)
        self.github_token = config.get_credential("github_token")
        self.github_repo: str = config.get_setting("github_repo", "")
        self.api: Optional[GitHubAPI] = None
        self._milestones_cache: Dict[str, int] = {}  # title -> number

    @property
    def _owner(self) -> str:
        parts = self.github_repo.split("/")
        if len(parts) != 2:
            raise ValidationError(
                f"Invalid github_repo format '{self.github_repo}'. Expected 'owner/repo'."
            )
        return parts[0]

    @property
    def _repo(self) -> str:
        parts = self.github_repo.split("/")
        if len(parts) != 2:
            raise ValidationError(
                f"Invalid github_repo format '{self.github_repo}'. Expected 'owner/repo'."
            )
        return parts[1]

    def get_required_credentials(self) -> List[str]:
        return ["github_token"]

    def get_supported_features(self) -> List[str]:
        return [
            "create", "read", "update", "delete",
            "projects", "tags", "due_dates", "priorities",
            "descriptions", "assignees", "labels",
        ]

    async def authenticate(self) -> bool:
        """Authenticate with GitHub API using a Personal Access Token."""
        if not self.github_token:
            raise AuthenticationError("No GitHub token provided")

        try:
            async with GitHubAPI(self.github_token) as api:
                user_info = await api.get_authenticated_user()
                if user_info and "login" in user_info:
                    self.logger.info(
                        f"Authenticated with GitHub as {user_info['login']}"
                    )
                    return True
                return False
        except AuthenticationError:
            self.logger.error("GitHub authentication failed - invalid token")
            raise
        except Exception as e:
            self.logger.error(f"GitHub authentication failed: {e}")
            raise AuthenticationError(f"Failed to authenticate with GitHub: {e}")

    async def test_connection(self) -> bool:
        """Test connection to GitHub API."""
        try:
            return await self.authenticate()
        except Exception:
            return False

    async def fetch_items(self, since: Optional[datetime] = None) -> List[ExternalTodoItem]:
        """Fetch issues from the configured GitHub repository."""
        await self.ensure_authenticated()

        try:
            async with GitHubAPI(self.github_token) as api:
                since_str = since.isoformat() if since else None
                raw_issues = await api.get_issues(
                    self._owner, self._repo, state="all", since=since_str
                )

                external_items = []
                for issue_data in raw_issues:
                    # Skip pull requests (they also appear in the issues endpoint)
                    if "pull_request" in issue_data:
                        continue
                    try:
                        item = self.map_external_to_todo(issue_data)
                        external_items.append(item)
                    except Exception as e:
                        self.logger.warning(
                            f"Failed to map GitHub issue {issue_data.get('number')}: {e}"
                        )

                self.logger.info(f"Fetched {len(external_items)} issues from GitHub")
                return external_items

        except (AuthenticationError, RateLimitError, ValidationError):
            raise
        except Exception as e:
            self.logger.error(f"Failed to fetch GitHub issues: {e}")
            raise NetworkError(f"Failed to fetch from GitHub: {e}")

    async def create_item(self, todo: Todo) -> str:
        """Create a new issue in the GitHub repository from a Todo."""
        await self.ensure_authenticated()

        try:
            async with GitHubAPI(self.github_token) as api:
                payload = self.map_todo_to_external(todo)
                created = await api.create_issue(
                    self._owner,
                    self._repo,
                    title=payload["title"],
                    body=payload.get("body"),
                    labels=payload.get("labels"),
                    assignees=payload.get("assignees"),
                    milestone=payload.get("milestone"),
                )
                issue_number = str(created["number"])
                self.log_sync_operation("create", f"Created issue #{issue_number}: {todo.text}")
                return issue_number

        except (AuthenticationError, RateLimitError, ValidationError):
            raise
        except Exception as e:
            self.logger.error(f"Failed to create GitHub issue: {e}")
            raise NetworkError(f"Failed to create in GitHub: {e}")

    async def update_item(self, external_id: str, todo: Todo) -> bool:
        """Update an existing GitHub issue from a Todo."""
        await self.ensure_authenticated()

        try:
            async with GitHubAPI(self.github_token) as api:
                payload = self.map_todo_to_external(todo)
                issue_number = int(external_id)

                update_kwargs: Dict[str, Any] = {
                    "title": payload["title"],
                }
                if "body" in payload:
                    update_kwargs["body"] = payload["body"]
                if "labels" in payload:
                    update_kwargs["labels"] = payload["labels"]
                if "assignees" in payload:
                    update_kwargs["assignees"] = payload["assignees"]

                # Map completion status to issue state
                if todo.completed:
                    update_kwargs["state"] = "closed"
                else:
                    update_kwargs["state"] = "open"

                await api.update_issue(self._owner, self._repo, issue_number, **update_kwargs)
                self.log_sync_operation("update", f"Updated issue #{external_id}: {todo.text}")
                return True

        except (AuthenticationError, RateLimitError, ValidationError):
            raise
        except Exception as e:
            self.logger.error(f"Failed to update GitHub issue #{external_id}: {e}")
            raise NetworkError(f"Failed to update in GitHub: {e}")

    async def delete_item(self, external_id: str) -> bool:
        """Close a GitHub issue (GitHub does not allow true deletion via the API)."""
        await self.ensure_authenticated()

        try:
            async with GitHubAPI(self.github_token) as api:
                issue_number = int(external_id)
                await api.close_issue(self._owner, self._repo, issue_number)
                self.log_sync_operation("delete", f"Closed issue #{external_id}")
                return True

        except (AuthenticationError, RateLimitError, ValidationError):
            raise
        except Exception as e:
            self.logger.error(f"Failed to close GitHub issue #{external_id}: {e}")
            return False

    async def fetch_projects(self) -> Dict[str, str]:
        """Fetch repositories as projects."""
        await self.ensure_authenticated()

        try:
            async with GitHubAPI(self.github_token) as api:
                repos = await api.get_repos()
                return {repo["full_name"]: str(repo["id"]) for repo in repos}
        except Exception as e:
            self.logger.error(f"Failed to fetch GitHub repos: {e}")
            return {}

    # ------------------------------------------------------------------
    # Field mapping
    # ------------------------------------------------------------------

    def map_todo_to_external(self, todo: Todo) -> Dict[str, Any]:
        """Map a local Todo to GitHub issue creation/update payload."""
        payload: Dict[str, Any] = {
            "title": todo.text,
        }

        # Description
        if todo.description:
            payload["body"] = todo.description

        # Labels = tags + priority label
        labels: List[str] = list(todo.tags) if todo.tags else []
        if todo.priority and todo.priority in PRIORITY_ENUM_TO_INT:
            pri_int = PRIORITY_ENUM_TO_INT[todo.priority]
            pri_label = PRIORITY_INT_TO_LABEL.get(pri_int)
            if pri_label:
                labels.append(pri_label)
        if labels:
            payload["labels"] = labels

        # Assignees
        if todo.assignees:
            payload["assignees"] = list(todo.assignees)

        # Milestone (from project mapping cache)
        if todo.project and todo.project in self._milestones_cache:
            payload["milestone"] = self._milestones_cache[todo.project]

        return payload

    def map_external_to_todo(self, external_data: Dict[str, Any]) -> ExternalTodoItem:
        """Map GitHub issue data to ExternalTodoItem."""
        issue = external_data

        # Extract labels and identify priority labels
        all_labels = [
            lbl["name"] if isinstance(lbl, dict) else lbl
            for lbl in issue.get("labels", [])
        ]
        priority_int: Optional[int] = None
        tags: List[str] = []
        for label_name in all_labels:
            if label_name.lower() in PRIORITY_LABEL_MAP:
                priority_int = PRIORITY_LABEL_MAP[label_name.lower()]
            else:
                tags.append(label_name)

        # Milestone -> project
        project: Optional[str] = None
        if issue.get("milestone") and issue["milestone"].get("title"):
            project = issue["milestone"]["title"]

        # Assignees
        assignee_logins = [a["login"] for a in issue.get("assignees", []) if "login" in a]
        assignee_str: Optional[str] = ", ".join(assignee_logins) if assignee_logins else None

        # State
        completed = issue.get("state") == "closed"
        closed_at: Optional[datetime] = None
        if completed and issue.get("closed_at"):
            try:
                closed_at = ensure_aware(
                    datetime.fromisoformat(issue["closed_at"].replace("Z", "+00:00"))
                )
            except Exception:
                pass

        # Timestamps
        created_at: Optional[datetime] = None
        if issue.get("created_at"):
            try:
                created_at = ensure_aware(
                    datetime.fromisoformat(issue["created_at"].replace("Z", "+00:00"))
                )
            except Exception:
                created_at = now_utc()
        else:
            created_at = now_utc()

        updated_at: Optional[datetime] = None
        if issue.get("updated_at"):
            try:
                updated_at = ensure_aware(
                    datetime.fromisoformat(issue["updated_at"].replace("Z", "+00:00"))
                )
            except Exception:
                updated_at = created_at
        else:
            updated_at = created_at

        return ExternalTodoItem(
            external_id=str(issue["number"]),
            provider=AppSyncProvider.GITHUB_ISSUES,
            title=issue["title"],
            description=issue.get("body") or "",
            priority=priority_int,
            tags=tags,
            project=project,
            completed=completed,
            completed_at=closed_at,
            created_at=created_at,
            updated_at=updated_at,
            assignee=assignee_str,
            url=issue.get("html_url"),
            raw_data=issue,
        )
