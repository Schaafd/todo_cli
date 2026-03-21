"""Any.do adapter for app synchronization.

This module provides integration with the Any.do API for bidirectional
synchronization of todo items.
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


# Priority mapping: Any.do priority string -> internal integer
ANYDO_PRIORITY_MAP = {
    "Normal": 1,
    "High": 3,
    "Urgent": 4,
}

ANYDO_PRIORITY_REVERSE = {v: k for k, v in ANYDO_PRIORITY_MAP.items()}

PRIORITY_ENUM_TO_ANYDO = {
    Priority.LOW: "Normal",
    Priority.MEDIUM: "Normal",
    Priority.HIGH: "High",
    Priority.CRITICAL: "Urgent",
}


class AnyDoAPI:
    """Any.do REST API client."""

    BASE_URL = "https://sm-prod2.any.do/"

    def __init__(self, token: str):
        """Initialize Any.do API client.

        Args:
            token: Any.do Bearer token
        """
        self.token = token
        self.headers = {
            "Authorization": f"Bearer {token}",
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

    async def _make_request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict] = None,
        params: Optional[Dict] = None,
    ) -> Any:
        """Make HTTP request to Any.do API.

        Args:
            method: HTTP method
            endpoint: API endpoint (relative to BASE_URL)
            data: JSON body data
            params: Query parameters

        Returns:
            Response data

        Raises:
            AuthenticationError: If authentication fails (401/403)
            RateLimitError: If rate limit is exceeded (429)
            NetworkError: If network request fails
        """
        if self.client is None:
            raise NetworkError("HTTP client not initialized. Use 'async with' context manager.")

        url = f"{self.BASE_URL}{endpoint}"

        try:
            if method.upper() == "GET":
                response = await self.client.get(url, headers=self.headers, params=params)
            elif method.upper() == "POST":
                response = await self.client.post(url, headers=self.headers, json=data)
            elif method.upper() == "PUT":
                response = await self.client.put(url, headers=self.headers, json=data)
            elif method.upper() == "DELETE":
                response = await self.client.delete(url, headers=self.headers)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")

            if response.status_code == 401:
                raise AuthenticationError("Invalid Any.do token")
            elif response.status_code == 403:
                raise AuthenticationError("Any.do API access forbidden")
            elif response.status_code == 404:
                raise NetworkError(f"Any.do resource not found: {endpoint}")
            elif response.status_code == 422:
                raise ValidationError(f"Any.do validation error: {response.text}")
            elif response.status_code == 429:
                raise RateLimitError("Any.do API rate limit exceeded")
            elif response.status_code >= 400:
                raise NetworkError(f"Any.do API error {response.status_code}: {response.text}")

            if response.status_code == 204:
                return {}

            return response.json()

        except httpx.TimeoutException:
            raise NetworkError("Any.do API request timed out")
        except httpx.RequestError as e:
            raise NetworkError(f"Any.do API request failed: {e}")

    # --- Authentication ---

    async def get_user(self) -> Dict[str, Any]:
        """Get authenticated user information."""
        return await self._make_request("GET", "me")

    # --- Tasks ---

    async def get_tasks(
        self,
        category_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Get tasks, optionally filtered by category.

        Args:
            category_id: Optional category ID to filter by

        Returns:
            List of task objects
        """
        params: Dict[str, Any] = {}
        if category_id:
            params["categoryId"] = category_id
        return await self._make_request("GET", "tasks", params=params)

    async def create_task(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new task.

        Args:
            data: Task data

        Returns:
            Created task object
        """
        return await self._make_request("POST", "tasks", data=data)

    async def update_task(
        self,
        task_id: str,
        data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Update an existing task.

        Args:
            task_id: The task ID
            data: Updated task data

        Returns:
            Updated task object
        """
        return await self._make_request("PUT", f"tasks/{task_id}", data=data)

    async def delete_task(self, task_id: str) -> Dict[str, Any]:
        """Delete a task.

        Args:
            task_id: The task ID

        Returns:
            Empty dict on success
        """
        return await self._make_request("DELETE", f"tasks/{task_id}")

    # --- Categories ---

    async def get_categories(self) -> List[Dict[str, Any]]:
        """Get all categories (projects/lists)."""
        return await self._make_request("GET", "categories")


class AnyDoAdapter(SyncAdapter):
    """Any.do adapter for app synchronization."""

    def __init__(self, config: AppSyncConfig):
        """Initialize Any.do adapter.

        Args:
            config: App sync configuration
        """
        super().__init__(config)
        self.anydo_token = config.get_credential("anydo_token")
        self.api: Optional[AnyDoAPI] = None
        self._categories_cache: Dict[str, str] = {}  # id -> name

    def get_required_credentials(self) -> List[str]:
        return ["anydo_token"]

    def get_supported_features(self) -> List[str]:
        return [
            "create", "read", "update", "delete",
            "projects", "tags", "due_dates", "priorities",
            "descriptions",
        ]

    # ------------------------------------------------------------------
    # Authentication
    # ------------------------------------------------------------------

    async def authenticate(self) -> bool:
        """Authenticate with Any.do API using the Bearer token."""
        if not self.anydo_token:
            raise AuthenticationError("No Any.do token provided")

        try:
            async with AnyDoAPI(self.anydo_token) as api:
                user_info = await api.get_user()
                if user_info and user_info.get("email"):
                    self.logger.info(
                        f"Authenticated with Any.do as {user_info['email']}"
                    )
                    return True
                return False
        except AuthenticationError:
            self.logger.error("Any.do authentication failed - invalid token")
            raise
        except Exception as e:
            self.logger.error(f"Any.do authentication failed: {e}")
            raise AuthenticationError(f"Failed to authenticate with Any.do: {e}")

    async def test_connection(self) -> bool:
        """Test connection to Any.do API."""
        try:
            return await self.authenticate()
        except Exception:
            return False

    # ------------------------------------------------------------------
    # CRUD operations
    # ------------------------------------------------------------------

    async def fetch_items(self, since: Optional[datetime] = None) -> List[ExternalTodoItem]:
        """Fetch tasks from Any.do."""
        await self.ensure_authenticated()

        try:
            async with AnyDoAPI(self.anydo_token) as api:
                raw_tasks = await api.get_tasks()

                # Filter by updated time if since is provided
                if since:
                    since_ts = int(since.timestamp() * 1000)
                    raw_tasks = [
                        t for t in raw_tasks
                        if t.get("lastUpdateDate", 0) >= since_ts
                    ]

                external_items: List[ExternalTodoItem] = []
                for task_data in raw_tasks:
                    try:
                        item = self.map_external_to_todo(task_data)
                        external_items.append(item)
                    except Exception as e:
                        self.logger.warning(
                            f"Failed to map Any.do task {task_data.get('id')}: {e}"
                        )

                self.logger.info(f"Fetched {len(external_items)} tasks from Any.do")
                return external_items

        except (AuthenticationError, RateLimitError, ValidationError):
            raise
        except Exception as e:
            self.logger.error(f"Failed to fetch Any.do tasks: {e}")
            raise NetworkError(f"Failed to fetch from Any.do: {e}")

    async def create_item(self, todo: Todo) -> str:
        """Create a new task in Any.do from a Todo."""
        await self.ensure_authenticated()

        try:
            async with AnyDoAPI(self.anydo_token) as api:
                payload = self.map_todo_to_external(todo)
                created = await api.create_task(payload)
                task_id = created["id"]
                self.log_sync_operation("create", f"Created task {task_id}: {todo.text}")
                return task_id

        except (AuthenticationError, RateLimitError, ValidationError):
            raise
        except Exception as e:
            self.logger.error(f"Failed to create Any.do task: {e}")
            raise NetworkError(f"Failed to create in Any.do: {e}")

    async def update_item(self, external_id: str, todo: Todo) -> bool:
        """Update an existing Any.do task from a Todo."""
        await self.ensure_authenticated()

        try:
            async with AnyDoAPI(self.anydo_token) as api:
                payload = self.map_todo_to_external(todo)
                await api.update_task(external_id, payload)
                self.log_sync_operation("update", f"Updated task {external_id}: {todo.text}")
                return True

        except (AuthenticationError, RateLimitError, ValidationError):
            raise
        except Exception as e:
            self.logger.error(f"Failed to update Any.do task {external_id}: {e}")
            raise NetworkError(f"Failed to update in Any.do: {e}")

    async def delete_item(self, external_id: str) -> bool:
        """Delete an Any.do task."""
        await self.ensure_authenticated()

        try:
            async with AnyDoAPI(self.anydo_token) as api:
                await api.delete_task(external_id)
                self.log_sync_operation("delete", f"Deleted task {external_id}")
                return True

        except (AuthenticationError, RateLimitError, ValidationError):
            raise
        except Exception as e:
            self.logger.error(f"Failed to delete Any.do task {external_id}: {e}")
            return False

    async def fetch_projects(self) -> Dict[str, str]:
        """Fetch categories as projects."""
        await self.ensure_authenticated()

        try:
            async with AnyDoAPI(self.anydo_token) as api:
                categories = await api.get_categories()
                project_map: Dict[str, str] = {}
                for cat in categories:
                    name = cat.get("name", "")
                    cat_id = cat.get("id", "")
                    if name and cat_id:
                        project_map[name] = cat_id
                        self._categories_cache[cat_id] = name
                return project_map
        except Exception as e:
            self.logger.error(f"Failed to fetch Any.do categories: {e}")
            return {}

    # ------------------------------------------------------------------
    # Field mapping
    # ------------------------------------------------------------------

    def map_todo_to_external(self, todo: Todo) -> Dict[str, Any]:
        """Map a local Todo to Any.do task creation/update payload."""
        payload: Dict[str, Any] = {
            "title": todo.text,
        }

        # Description -> note
        if todo.description:
            payload["note"] = todo.description

        # Priority
        if todo.priority:
            anydo_priority = PRIORITY_ENUM_TO_ANYDO.get(todo.priority, "Normal")
            payload["priority"] = anydo_priority

        # Tags -> labels
        if todo.tags:
            payload["labels"] = list(todo.tags)

        # Due date -> dueDate (timestamp in ms)
        if todo.due_date:
            payload["dueDate"] = int(todo.due_date.timestamp() * 1000)

        # Status
        if todo.completed:
            payload["status"] = "CHECKED"
        else:
            payload["status"] = "UNCHECKED"

        # Project -> categoryId
        if todo.project and todo.project != "inbox":
            mapped = self.apply_project_mapping(todo.project)
            if mapped:
                payload["categoryId"] = mapped

        return payload

    def map_external_to_todo(self, external_data: Dict[str, Any]) -> ExternalTodoItem:
        """Map Any.do task data to ExternalTodoItem."""
        task = external_data

        title = task.get("title", "")
        description = task.get("note", "")

        # Priority mapping
        priority_str = task.get("priority", "Normal")
        priority_int = ANYDO_PRIORITY_MAP.get(priority_str)

        # Tags/labels
        tags: List[str] = []
        for label in task.get("labels", []):
            if isinstance(label, str):
                tags.append(label)
            elif isinstance(label, dict):
                tags.append(label.get("name", ""))

        # Category -> project
        project: Optional[str] = None
        category_id = task.get("categoryId")
        if category_id:
            project = self._categories_cache.get(
                category_id,
                self.apply_reverse_project_mapping(category_id),
            )

        # Due date (timestamp in ms)
        due_date: Optional[datetime] = None
        if task.get("dueDate"):
            try:
                ts = task["dueDate"]
                if isinstance(ts, (int, float)):
                    due_date = datetime.fromtimestamp(ts / 1000, tz=timezone.utc)
                else:
                    due_date = ensure_aware(
                        datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
                    )
            except Exception:
                pass

        # Status
        completed = task.get("status") == "CHECKED"
        completed_at: Optional[datetime] = None
        if completed and task.get("completionDate"):
            try:
                ts = task["completionDate"]
                if isinstance(ts, (int, float)):
                    completed_at = datetime.fromtimestamp(ts / 1000, tz=timezone.utc)
                else:
                    completed_at = ensure_aware(
                        datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
                    )
            except Exception:
                pass

        # Timestamps
        created_at: Optional[datetime] = None
        if task.get("createdDate"):
            try:
                ts = task["createdDate"]
                if isinstance(ts, (int, float)):
                    created_at = datetime.fromtimestamp(ts / 1000, tz=timezone.utc)
                else:
                    created_at = ensure_aware(
                        datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
                    )
            except Exception:
                created_at = now_utc()
        else:
            created_at = now_utc()

        updated_at: Optional[datetime] = None
        if task.get("lastUpdateDate"):
            try:
                ts = task["lastUpdateDate"]
                if isinstance(ts, (int, float)):
                    updated_at = datetime.fromtimestamp(ts / 1000, tz=timezone.utc)
                else:
                    updated_at = ensure_aware(
                        datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
                    )
            except Exception:
                updated_at = created_at
        else:
            updated_at = created_at

        return ExternalTodoItem(
            external_id=str(task.get("id", "")),
            provider=AppSyncProvider.ANY_DO,
            title=title,
            description=description,
            priority=priority_int,
            tags=tags,
            project=project,
            due_date=due_date,
            completed=completed,
            completed_at=completed_at,
            created_at=created_at,
            updated_at=updated_at,
            raw_data=task,
        )
