"""Jira adapter for app synchronization.

This module provides integration with the Jira REST API v3 for bidirectional
synchronization of todo items, projects, priorities, and issue statuses.
"""

import httpx
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from urllib.parse import urljoin

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


# ---------------------------------------------------------------------------
# Priority mapping helpers
# ---------------------------------------------------------------------------

# Jira priority name -> internal numeric priority (0-4 scale used by ExternalTodoItem)
JIRA_PRIORITY_TO_INT: Dict[str, int] = {
    "Highest": 4,
    "High": 3,
    "Medium": 2,
    "Low": 1,
    "Lowest": 0,
}

INT_TO_JIRA_PRIORITY: Dict[int, str] = {v: k for k, v in JIRA_PRIORITY_TO_INT.items()}

# Jira priority name -> Todo Priority enum
JIRA_PRIORITY_TO_TODO: Dict[str, Priority] = {
    "Highest": Priority.CRITICAL,
    "High": Priority.HIGH,
    "Medium": Priority.MEDIUM,
    "Low": Priority.LOW,
    "Lowest": Priority.LOW,
}

TODO_PRIORITY_TO_JIRA: Dict[Priority, str] = {
    Priority.CRITICAL: "Highest",
    Priority.HIGH: "High",
    Priority.MEDIUM: "Medium",
    Priority.LOW: "Low",
}

# Jira status name -> TodoStatus
JIRA_STATUS_TO_TODO: Dict[str, TodoStatus] = {
    "To Do": TodoStatus.PENDING,
    "Open": TodoStatus.PENDING,
    "In Progress": TodoStatus.IN_PROGRESS,
    "Done": TodoStatus.COMPLETED,
    "Closed": TodoStatus.COMPLETED,
    "Resolved": TodoStatus.COMPLETED,
}


class JiraAPI:
    """Jira REST API v3 client."""

    def __init__(
        self,
        base_url: str,
        email: Optional[str] = None,
        token: Optional[str] = None,
        bearer_token: Optional[str] = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.api_url = f"{self.base_url}/rest/api/3/"
        self.email = email
        self.token = token
        self.bearer_token = bearer_token
        self.client: Optional[httpx.AsyncClient] = None
        self.logger = logging.getLogger(__name__)

    async def __aenter__(self):
        auth = None
        headers: Dict[str, str] = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if self.bearer_token:
            headers["Authorization"] = f"Bearer {self.bearer_token}"
        elif self.email and self.token:
            auth = httpx.BasicAuth(self.email, self.token)
        self.client = httpx.AsyncClient(timeout=30.0, auth=auth, headers=headers)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.client is not None:
            await self.client.aclose()
            self.client = None

    # ------------------------------------------------------------------
    # Low-level request helper
    # ------------------------------------------------------------------

    async def _request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict] = None,
        params: Optional[Dict] = None,
    ) -> Any:
        if self.client is None:
            raise NetworkError("HTTP client not initialized. Use 'async with' context manager.")

        url = urljoin(self.api_url, endpoint)

        try:
            response = await self.client.request(method, url, json=data, params=params)
        except httpx.TimeoutException:
            raise NetworkError("Jira API request timed out")
        except httpx.RequestError as e:
            raise NetworkError(f"Jira API request failed: {e}")

        if response.status_code == 401:
            raise AuthenticationError("Invalid Jira credentials")
        if response.status_code == 403:
            raise AuthenticationError("Jira API access forbidden")
        if response.status_code == 429:
            raise RateLimitError("Jira API rate limit exceeded")
        if response.status_code >= 400:
            raise NetworkError(f"Jira API error {response.status_code}: {response.text}")
        if response.status_code == 204:
            return {}
        return response.json()

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------

    async def get_myself(self) -> Dict[str, Any]:
        """Return the current authenticated user."""
        return await self._request("GET", "myself")

    async def search_issues(self, jql: str, max_results: int = 50, start_at: int = 0) -> Dict[str, Any]:
        params = {"jql": jql, "maxResults": max_results, "startAt": start_at}
        return await self._request("GET", "search", params=params)

    async def create_issue(self, fields: Dict[str, Any]) -> Dict[str, Any]:
        return await self._request("POST", "issue", data={"fields": fields})

    async def update_issue(self, issue_key: str, fields: Dict[str, Any]) -> Dict[str, Any]:
        return await self._request("PUT", f"issue/{issue_key}", data={"fields": fields})

    async def transition_issue(self, issue_key: str, transition_id: str) -> Dict[str, Any]:
        return await self._request(
            "POST",
            f"issue/{issue_key}/transitions",
            data={"transition": {"id": transition_id}},
        )

    async def get_transitions(self, issue_key: str) -> List[Dict[str, Any]]:
        result = await self._request("GET", f"issue/{issue_key}/transitions")
        return result.get("transitions", [])

    async def get_projects(self) -> List[Dict[str, Any]]:
        return await self._request("GET", "project")

    async def get_priorities(self) -> List[Dict[str, Any]]:
        return await self._request("GET", "priority")

    async def delete_issue(self, issue_key: str) -> Dict[str, Any]:
        return await self._request("DELETE", f"issue/{issue_key}")


class JiraAdapter(SyncAdapter):
    """Jira adapter for app synchronization."""

    def __init__(self, config: AppSyncConfig):
        super().__init__(config)
        self.jira_email = config.get_credential("jira_email")
        self.jira_token = config.get_credential("jira_token")
        self.jira_base_url: str = config.get_setting("jira_base_url", "")
        self.jira_project_key: str = config.get_setting("jira_project_key", "")
        self._projects_cache: Dict[str, str] = {}
        self._priorities_cache: Dict[str, str] = {}

    # ------------------------------------------------------------------
    # Required credentials
    # ------------------------------------------------------------------

    def get_required_credentials(self) -> List[str]:
        return ["jira_email", "jira_token"]

    def get_supported_features(self) -> List[str]:
        return [
            "create", "read", "update", "delete",
            "projects", "tags", "due_dates", "priorities",
            "descriptions", "statuses", "assignees",
        ]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _make_api(self) -> JiraAPI:
        return JiraAPI(
            base_url=self.jira_base_url,
            email=self.jira_email,
            token=self.jira_token,
        )

    # ------------------------------------------------------------------
    # SyncAdapter interface
    # ------------------------------------------------------------------

    async def authenticate(self) -> bool:
        if not self.jira_email or not self.jira_token:
            raise AuthenticationError("Missing Jira email or API token")
        if not self.jira_base_url:
            raise AuthenticationError("Missing Jira base URL")

        try:
            async with self._make_api() as api:
                user = await api.get_myself()
                if user and "accountId" in user:
                    self.logger.info(f"Authenticated with Jira as {user.get('displayName', 'Unknown')}")
                    return True
                return False
        except AuthenticationError:
            raise
        except Exception as e:
            raise AuthenticationError(f"Failed to authenticate with Jira: {e}")

    async def test_connection(self) -> bool:
        try:
            return await self.authenticate()
        except Exception:
            return False

    async def fetch_items(self, since: Optional[datetime] = None) -> List[ExternalTodoItem]:
        await self.ensure_authenticated()

        try:
            async with self._make_api() as api:
                jql = f"project = {self.jira_project_key}"
                if since:
                    since_str = since.strftime("%Y-%m-%d %H:%M")
                    jql += f" AND updated >= '{since_str}'"
                jql += " ORDER BY updated DESC"

                result = await api.search_issues(jql)
                issues = result.get("issues", [])

                items: List[ExternalTodoItem] = []
                for issue in issues:
                    try:
                        items.append(self.map_external_to_todo(issue))
                    except Exception as e:
                        self.logger.warning(f"Failed to map Jira issue {issue.get('key')}: {e}")
                self.logger.info(f"Fetched {len(items)} issues from Jira")
                return items
        except AuthenticationError:
            raise
        except Exception as e:
            raise NetworkError(f"Failed to fetch from Jira: {e}")

    async def create_item(self, todo: Todo) -> str:
        await self.ensure_authenticated()

        try:
            async with self._make_api() as api:
                fields = self.map_todo_to_external(todo)
                created = await api.create_issue(fields)
                issue_key = created.get("key", created.get("id", ""))
                self.log_sync_operation("create", f"Created issue {issue_key}: {todo.text}")
                return str(issue_key)
        except Exception as e:
            raise NetworkError(f"Failed to create Jira issue: {e}")

    async def update_item(self, external_id: str, todo: Todo) -> bool:
        await self.ensure_authenticated()

        try:
            async with self._make_api() as api:
                fields = self.map_todo_to_external(todo)
                # Remove project and issuetype – they cannot be changed via update
                fields.pop("project", None)
                fields.pop("issuetype", None)
                await api.update_issue(external_id, fields)

                # Handle completion transitions
                if todo.completed or todo.status == TodoStatus.COMPLETED:
                    await self._transition_to_done(api, external_id)

                self.log_sync_operation("update", f"Updated issue {external_id}: {todo.text}")
                return True
        except Exception as e:
            self.logger.error(f"Failed to update Jira issue {external_id}: {e}")
            raise NetworkError(f"Failed to update Jira issue: {e}")

    async def delete_item(self, external_id: str) -> bool:
        await self.ensure_authenticated()

        try:
            async with self._make_api() as api:
                await api.delete_issue(external_id)
                self.log_sync_operation("delete", f"Deleted issue {external_id}")
                return True
        except Exception as e:
            self.logger.error(f"Failed to delete Jira issue {external_id}: {e}")
            return False

    async def fetch_projects(self) -> Dict[str, str]:
        await self.ensure_authenticated()

        try:
            async with self._make_api() as api:
                projects = await api.get_projects()
                return {p["key"]: p["id"] for p in projects}
        except Exception as e:
            self.logger.error(f"Failed to fetch Jira projects: {e}")
            return {}

    # ------------------------------------------------------------------
    # Mapping
    # ------------------------------------------------------------------

    def map_todo_to_external(self, todo: Todo) -> Dict[str, Any]:
        fields: Dict[str, Any] = {
            "project": {"key": self.jira_project_key},
            "summary": todo.text,
            "issuetype": {"name": "Task"},
        }

        if todo.description:
            fields["description"] = {
                "type": "doc",
                "version": 1,
                "content": [
                    {
                        "type": "paragraph",
                        "content": [{"type": "text", "text": todo.description}],
                    }
                ],
            }

        # Priority
        jira_priority = TODO_PRIORITY_TO_JIRA.get(todo.priority)
        if jira_priority:
            fields["priority"] = {"name": jira_priority}

        # Labels / tags
        if todo.tags:
            fields["labels"] = list(todo.tags)

        # Due date
        if todo.due_date:
            fields["duedate"] = todo.due_date.strftime("%Y-%m-%d")

        # Assignee
        if todo.assignees:
            fields["assignee"] = {"accountId": todo.assignees[0]}

        return fields

    def map_external_to_todo(self, external_data: Dict[str, Any]) -> ExternalTodoItem:
        issue = external_data
        fields = issue.get("fields", {})

        # Key / id
        issue_key = issue.get("key", str(issue.get("id", "")))

        # Summary
        title = fields.get("summary", "")

        # Description – ADF or plain string
        description = self._extract_description(fields.get("description"))

        # Priority
        priority_name = ""
        priority_field = fields.get("priority")
        if priority_field and isinstance(priority_field, dict):
            priority_name = priority_field.get("name", "")
        priority_int = JIRA_PRIORITY_TO_INT.get(priority_name, 2)

        # Labels -> tags
        tags = fields.get("labels", [])

        # Sprint -> project
        project = self._extract_sprint_name(fields)
        if not project:
            project_field = fields.get("project")
            if project_field and isinstance(project_field, dict):
                project = project_field.get("key", "default")
            else:
                project = "default"

        project_id = None
        project_field = fields.get("project")
        if project_field and isinstance(project_field, dict):
            project_id = project_field.get("id")

        # Status
        status_name = ""
        status_field = fields.get("status")
        if status_field and isinstance(status_field, dict):
            status_name = status_field.get("name", "")
        todo_status = JIRA_STATUS_TO_TODO.get(status_name, TodoStatus.PENDING)
        completed = todo_status == TodoStatus.COMPLETED

        # Dates
        created_at = self._parse_jira_datetime(fields.get("created"))
        updated_at = self._parse_jira_datetime(fields.get("updated"))
        due_date = self._parse_jira_date(fields.get("duedate"))
        completed_at = self._parse_jira_datetime(fields.get("resolutiondate")) if completed else None

        # Assignee
        assignee = None
        assignee_field = fields.get("assignee")
        if assignee_field and isinstance(assignee_field, dict):
            assignee = assignee_field.get("displayName") or assignee_field.get("accountId")

        # URL
        url = f"{self.jira_base_url}/browse/{issue_key}"

        return ExternalTodoItem(
            external_id=issue_key,
            provider=AppSyncProvider.JIRA,
            title=title,
            description=description,
            due_date=due_date,
            priority=priority_int,
            tags=tags,
            project=project,
            project_id=project_id,
            completed=completed,
            completed_at=completed_at,
            created_at=created_at or now_utc(),
            updated_at=updated_at or now_utc(),
            url=url,
            assignee=assignee,
            raw_data=issue,
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_description(desc_field: Any) -> str:
        """Extract plain text from Jira ADF description or plain string."""
        if desc_field is None:
            return ""
        if isinstance(desc_field, str):
            return desc_field
        if isinstance(desc_field, dict):
            # Atlassian Document Format – walk content tree
            texts: List[str] = []
            for block in desc_field.get("content", []):
                for inline in block.get("content", []):
                    if inline.get("type") == "text":
                        texts.append(inline.get("text", ""))
            return "\n".join(texts)
        return ""

    @staticmethod
    def _extract_sprint_name(fields: Dict[str, Any]) -> Optional[str]:
        """Extract active sprint name from customfield_10020 (common Jira sprint field)."""
        sprint_field = fields.get("customfield_10020")
        if sprint_field and isinstance(sprint_field, list):
            for sprint in sprint_field:
                if isinstance(sprint, dict) and sprint.get("state") == "active":
                    return sprint.get("name")
        return None

    @staticmethod
    def _parse_jira_datetime(value: Optional[str]) -> Optional[datetime]:
        if not value:
            return None
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return ensure_aware(parsed)
        except Exception:
            return None

    @staticmethod
    def _parse_jira_date(value: Optional[str]) -> Optional[datetime]:
        """Parse a date-only string (YYYY-MM-DD) into a timezone-aware datetime."""
        if not value:
            return None
        try:
            parsed = datetime.strptime(value, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            return parsed
        except Exception:
            return None

    async def _transition_to_done(self, api: JiraAPI, issue_key: str) -> bool:
        """Attempt to transition an issue to a 'Done'-like status."""
        try:
            transitions = await api.get_transitions(issue_key)
            for t in transitions:
                if t.get("name", "").lower() in ("done", "closed", "resolved"):
                    await api.transition_issue(issue_key, t["id"])
                    return True
        except Exception as e:
            self.logger.warning(f"Failed to transition issue {issue_key} to Done: {e}")
        return False
