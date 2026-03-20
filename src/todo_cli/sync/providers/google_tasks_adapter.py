"""Google Tasks adapter for app synchronization.

This module provides integration with the Google Tasks API for bidirectional
synchronization of todo items and task lists.
"""

import json
import logging
import re
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any

import httpx

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

# Metadata markers embedded in Google Tasks notes field
_META_START = "\n---todo_cli_meta---\n"
_META_END = "\n---end_meta---"


class GoogleTasksAPI:
    """Google Tasks REST API client.

    Uses https://tasks.googleapis.com/tasks/v1/ endpoints.
    Auth is via a Bearer OAuth2 access token.
    """

    BASE_URL = "https://tasks.googleapis.com/tasks/v1/"

    def __init__(self, access_token: str):
        self.access_token = access_token
        self.headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
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

    # ---- internal request helper ----

    async def _request(
        self, method: str, path: str, data: Optional[Dict] = None
    ) -> Any:
        """Make an HTTP request to the Google Tasks API.

        Returns parsed JSON (dict or list) on success.
        Raises appropriate sync error classes on failure.
        """
        if self.client is None:
            raise NetworkError(
                "HTTP client not initialized. Use 'async with' context manager."
            )

        url = self.BASE_URL + path

        try:
            if method == "GET":
                response = await self.client.get(
                    url, headers=self.headers, params=data
                )
            elif method == "POST":
                response = await self.client.post(
                    url, headers=self.headers, json=data
                )
            elif method == "PUT":
                response = await self.client.put(
                    url, headers=self.headers, json=data
                )
            elif method == "PATCH":
                response = await self.client.patch(
                    url, headers=self.headers, json=data
                )
            elif method == "DELETE":
                response = await self.client.delete(url, headers=self.headers)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")

            if response.status_code == 401:
                raise AuthenticationError("Invalid or expired Google access token")
            if response.status_code == 403:
                raise AuthenticationError("Google Tasks API access forbidden")
            if response.status_code == 429:
                raise RateLimitError("Google Tasks API rate limit exceeded")
            if response.status_code >= 400:
                raise NetworkError(
                    f"Google Tasks API error {response.status_code}: {response.text}"
                )
            if response.status_code == 204:
                return {}
            return response.json()

        except httpx.TimeoutException:
            raise NetworkError("Google Tasks API request timed out")
        except httpx.RequestError as e:
            raise NetworkError(f"Google Tasks API request failed: {e}")

    # ---- public API methods ----

    async def list_tasklists(self) -> List[Dict[str, Any]]:
        """Return all task lists for the authenticated user."""
        result = await self._request("GET", "users/@me/lists")
        return result.get("items", [])

    async def list_tasks(self, tasklist_id: str = "@default") -> List[Dict[str, Any]]:
        """Return all tasks in a given task list."""
        result = await self._request(
            "GET",
            f"lists/{tasklist_id}/tasks",
            {"showCompleted": "true", "showHidden": "true"},
        )
        return result.get("items", [])

    async def get_task(
        self, tasklist_id: str, task_id: str
    ) -> Dict[str, Any]:
        """Return a single task."""
        return await self._request("GET", f"lists/{tasklist_id}/tasks/{task_id}")

    async def create_task(
        self, tasklist_id: str, data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Create a task in the given list."""
        return await self._request("POST", f"lists/{tasklist_id}/tasks", data)

    async def update_task(
        self, tasklist_id: str, task_id: str, data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Update (PATCH) an existing task."""
        return await self._request(
            "PATCH", f"lists/{tasklist_id}/tasks/{task_id}", data
        )

    async def delete_task(self, tasklist_id: str, task_id: str) -> Dict[str, Any]:
        """Delete a task."""
        return await self._request(
            "DELETE", f"lists/{tasklist_id}/tasks/{task_id}"
        )


# ---- helpers for metadata encoding ----

def _encode_metadata(
    priority: Optional[Priority] = None,
    tags: Optional[List[str]] = None,
    assignees: Optional[List[str]] = None,
) -> str:
    """Encode priority/tags/assignees as a JSON blob for the notes field."""
    meta: Dict[str, Any] = {}
    if priority and priority != Priority.MEDIUM:
        meta["priority"] = priority.value
    if tags:
        meta["tags"] = tags
    if assignees:
        meta["assignees"] = assignees
    if not meta:
        return ""
    return _META_START + json.dumps(meta, sort_keys=True) + _META_END


def _decode_metadata(notes: Optional[str]) -> Dict[str, Any]:
    """Extract metadata dict from the notes field, return remainder text too."""
    if not notes:
        return {"description": "", "priority": None, "tags": [], "assignees": []}
    start = notes.find(_META_START)
    if start == -1:
        return {"description": notes, "priority": None, "tags": [], "assignees": []}
    end = notes.find(_META_END, start)
    if end == -1:
        return {"description": notes, "priority": None, "tags": [], "assignees": []}
    json_str = notes[start + len(_META_START) : end]
    description = notes[:start] + notes[end + len(_META_END) :]
    description = description.strip()
    try:
        meta = json.loads(json_str)
    except json.JSONDecodeError:
        return {"description": notes, "priority": None, "tags": [], "assignees": []}
    priority_str = meta.get("priority")
    priority = None
    if priority_str:
        try:
            priority = Priority(priority_str)
        except ValueError:
            priority = None
    return {
        "description": description,
        "priority": priority,
        "tags": meta.get("tags", []),
        "assignees": meta.get("assignees", []),
    }


def _parse_rfc3339(value: Optional[str]) -> Optional[datetime]:
    """Parse an RFC 3339 datetime string, returning timezone-aware datetime or None."""
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return ensure_aware(dt)
    except (ValueError, TypeError):
        return None


def _to_rfc3339(dt: Optional[datetime]) -> Optional[str]:
    """Format datetime as RFC 3339 string (UTC)."""
    if dt is None:
        return None
    dt = ensure_aware(dt)
    return dt.strftime("%Y-%m-%dT%H:%M:%S.000Z")


class GoogleTasksAdapter(SyncAdapter):
    """Google Tasks adapter for app synchronization."""

    def __init__(self, config: AppSyncConfig):
        super().__init__(config)
        self.access_token = config.get_credential("google_access_token") or ""
        self.tasklist_id = config.get_setting("google_tasklist_id", "@default")
        self.api: Optional[GoogleTasksAPI] = None

    # ---- credentials / features ----

    def get_required_credentials(self) -> List[str]:
        return ["google_access_token"]

    def get_supported_features(self) -> List[str]:
        return [
            "create",
            "read",
            "update",
            "delete",
            "projects",
            "due_dates",
            "descriptions",
        ]

    # ---- authentication ----

    async def authenticate(self) -> bool:
        if not self.access_token:
            raise AuthenticationError("No Google access token provided")
        try:
            async with GoogleTasksAPI(self.access_token) as api:
                lists = await api.list_tasklists()
                if isinstance(lists, list):
                    self.logger.info("Authenticated with Google Tasks")
                    return True
                return False
        except AuthenticationError:
            raise
        except Exception as e:
            raise AuthenticationError(f"Failed to authenticate with Google Tasks: {e}")

    async def test_connection(self) -> bool:
        try:
            return await self.authenticate()
        except Exception:
            return False

    # ---- fetch ----

    async def fetch_items(
        self, since: Optional[datetime] = None
    ) -> List[ExternalTodoItem]:
        await self.ensure_authenticated()
        try:
            async with GoogleTasksAPI(self.access_token) as api:
                tasks = await api.list_tasks(self.tasklist_id)
                items: List[ExternalTodoItem] = []
                for task in tasks:
                    try:
                        item = self.map_external_to_todo(task)
                        if since and item.updated_at and item.updated_at < since:
                            continue
                        items.append(item)
                    except Exception as e:
                        self.logger.warning(
                            f"Failed to map Google task {task.get('id')}: {e}"
                        )
                return items
        except (AuthenticationError, RateLimitError, NetworkError):
            raise
        except Exception as e:
            raise NetworkError(f"Failed to fetch Google Tasks: {e}")

    # ---- create / update / delete ----

    async def create_item(self, todo: Todo) -> str:
        await self.ensure_authenticated()
        data = self.map_todo_to_external(todo)
        try:
            async with GoogleTasksAPI(self.access_token) as api:
                result = await api.create_task(self.tasklist_id, data)
                external_id = result.get("id", "")
                self.log_sync_operation("create", f"Created task {external_id}")
                return external_id
        except (AuthenticationError, RateLimitError, NetworkError):
            raise
        except Exception as e:
            raise NetworkError(f"Failed to create Google Task: {e}")

    async def update_item(self, external_id: str, todo: Todo) -> bool:
        await self.ensure_authenticated()
        data = self.map_todo_to_external(todo)
        try:
            async with GoogleTasksAPI(self.access_token) as api:
                await api.update_task(self.tasklist_id, external_id, data)
                self.log_sync_operation("update", f"Updated task {external_id}")
                return True
        except (AuthenticationError, RateLimitError, NetworkError):
            raise
        except Exception as e:
            raise NetworkError(f"Failed to update Google Task: {e}")

    async def delete_item(self, external_id: str) -> bool:
        await self.ensure_authenticated()
        try:
            async with GoogleTasksAPI(self.access_token) as api:
                await api.delete_task(self.tasklist_id, external_id)
                self.log_sync_operation("delete", f"Deleted task {external_id}")
                return True
        except (AuthenticationError, RateLimitError, NetworkError):
            raise
        except Exception as e:
            raise NetworkError(f"Failed to delete Google Task: {e}")

    # ---- projects (task lists) ----

    async def fetch_projects(self) -> Dict[str, str]:
        await self.ensure_authenticated()
        try:
            async with GoogleTasksAPI(self.access_token) as api:
                lists = await api.list_tasklists()
                return {tl.get("title", ""): tl.get("id", "") for tl in lists}
        except (AuthenticationError, RateLimitError, NetworkError):
            raise
        except Exception as e:
            raise NetworkError(f"Failed to fetch Google Task lists: {e}")

    # ---- mapping ----

    def map_todo_to_external(self, todo: Todo) -> Dict[str, Any]:
        """Convert a local Todo to Google Tasks API format."""
        # Build notes: user description + encoded metadata
        notes_parts: List[str] = []
        if todo.description:
            notes_parts.append(todo.description)
        meta_str = _encode_metadata(
            priority=todo.priority,
            tags=todo.tags,
            assignees=todo.assignees,
        )
        if meta_str:
            notes_parts.append(meta_str)
        notes = "".join(notes_parts) if notes_parts else None

        # Status mapping
        if todo.status == TodoStatus.COMPLETED or todo.completed:
            status = "completed"
        else:
            status = "needsAction"

        data: Dict[str, Any] = {
            "title": todo.text,
            "status": status,
        }
        if notes:
            data["notes"] = notes
        if todo.due_date:
            data["due"] = _to_rfc3339(todo.due_date)
        if status == "completed" and todo.completed_date:
            data["completed"] = _to_rfc3339(todo.completed_date)

        return data

    def map_external_to_todo(self, external_data: Dict[str, Any]) -> ExternalTodoItem:
        """Convert Google Tasks API data to ExternalTodoItem."""
        task_id = external_data.get("id", "")
        title = external_data.get("title", "")
        notes_raw = external_data.get("notes")
        meta = _decode_metadata(notes_raw)

        is_completed = external_data.get("status") == "completed"
        completed_at = _parse_rfc3339(external_data.get("completed"))
        due_date = _parse_rfc3339(external_data.get("due"))
        updated_at = _parse_rfc3339(external_data.get("updated"))

        # Map priority to int for ExternalTodoItem
        priority_val = None
        priority_obj = meta.get("priority")
        if priority_obj is not None:
            _prio_map = {
                Priority.LOW: 1,
                Priority.MEDIUM: 2,
                Priority.HIGH: 3,
                Priority.CRITICAL: 4,
            }
            priority_val = _prio_map.get(priority_obj, 2)

        return ExternalTodoItem(
            external_id=task_id,
            provider=AppSyncProvider.GOOGLE_TASKS,
            title=title,
            description=meta.get("description") or None,
            due_date=due_date,
            priority=priority_val,
            tags=meta.get("tags", []),
            completed=is_completed,
            completed_at=completed_at,
            updated_at=updated_at,
            raw_data=external_data,
        )
