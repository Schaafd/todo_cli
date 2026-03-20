"""TickTick adapter for app synchronization.

EXPERIMENTAL: This adapter uses the TickTick Open API (https://developer.ticktick.com/api).
The API may change and this adapter may need updates accordingly.

This module provides integration with the TickTick Open API for bidirectional
synchronization of todo items, projects, tags, priorities, and due dates.
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

# TickTick priority mapping:
#   TickTick: 0=none, 1=low, 3=medium, 5=high
#   Internal: Priority.LOW, Priority.MEDIUM, Priority.HIGH, Priority.CRITICAL
TICKTICK_PRIORITY_TO_INTERNAL = {
    0: Priority.LOW,
    1: Priority.LOW,
    3: Priority.MEDIUM,
    5: Priority.HIGH,
}

INTERNAL_PRIORITY_TO_TICKTICK = {
    Priority.LOW: 1,
    Priority.MEDIUM: 3,
    Priority.HIGH: 5,
    Priority.CRITICAL: 5,
}


class TickTickAPI:
    """TickTick Open API client.

    Uses OAuth2 Bearer token authentication against the TickTick Open API
    (https://developer.ticktick.com/api).

    Base URL: https://api.ticktick.com/open/v1/
    """

    BASE_URL = "https://api.ticktick.com/open/v1/"

    def __init__(self, access_token: str):
        """Initialize TickTick API client.

        Args:
            access_token: OAuth2 access token.
        """
        self.access_token = access_token
        self.headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }
        self.client: Optional[httpx.AsyncClient] = None
        self.logger = logging.getLogger(__name__)

    async def __aenter__(self):
        """Create HTTP client when entering async context."""
        if self.client is None:
            self.client = httpx.AsyncClient(timeout=30.0)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Close HTTP client when exiting async context."""
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
        """Make HTTP request to TickTick API.

        Args:
            method: HTTP method.
            endpoint: API endpoint (relative to BASE_URL).
            data: JSON body for POST/PUT requests.
            params: Query parameters for GET requests.

        Returns:
            Parsed JSON response (dict or list).

        Raises:
            AuthenticationError: If authentication fails (401/403).
            RateLimitError: If rate limit is exceeded (429).
            NetworkError: If network request fails or server error.
        """
        if self.client is None:
            raise NetworkError(
                "HTTP client not initialized. Use 'async with' context manager."
            )

        url = urljoin(self.BASE_URL, endpoint)

        try:
            if method.upper() == "GET":
                response = await self.client.get(
                    url, headers=self.headers, params=params
                )
            elif method.upper() == "POST":
                response = await self.client.post(
                    url, headers=self.headers, json=data
                )
            elif method.upper() == "PUT":
                response = await self.client.put(
                    url, headers=self.headers, json=data
                )
            elif method.upper() == "DELETE":
                response = await self.client.delete(url, headers=self.headers)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")

            if response.status_code == 401:
                raise AuthenticationError("Invalid TickTick access token")
            elif response.status_code == 403:
                raise AuthenticationError("TickTick API access forbidden")
            elif response.status_code == 429:
                raise RateLimitError("TickTick API rate limit exceeded")
            elif response.status_code >= 400:
                error_msg = (
                    f"TickTick API error {response.status_code}: {response.text}"
                )
                raise NetworkError(error_msg)

            if response.status_code == 204:
                return {}

            return response.json()

        except httpx.TimeoutException:
            raise NetworkError("TickTick API request timed out")
        except httpx.RequestError as e:
            raise NetworkError(f"TickTick API request failed: {e}")

    # ---- Tasks ----

    async def get_tasks(
        self, project_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get tasks, optionally filtered by project.

        Args:
            project_id: Optional project ID to filter tasks.

        Returns:
            List of task dictionaries.
        """
        if project_id:
            # TickTick Open API: get tasks for a specific project
            result = await self._make_request(
                "GET", f"project/{project_id}/data"
            )
            return result.get("tasks", []) if isinstance(result, dict) else []
        else:
            # Without a project_id we iterate over all projects
            projects = await self.get_projects()
            all_tasks: List[Dict[str, Any]] = []
            for proj in projects:
                pid = proj.get("id")
                if pid:
                    result = await self._make_request(
                        "GET", f"project/{pid}/data"
                    )
                    tasks = (
                        result.get("tasks", [])
                        if isinstance(result, dict)
                        else []
                    )
                    all_tasks.extend(tasks)
            return all_tasks

    async def create_task(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new task.

        Args:
            data: Task data dictionary.

        Returns:
            Created task dictionary.
        """
        return await self._make_request("POST", "task", data)

    async def update_task(
        self, task_id: str, data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Update an existing task.

        Args:
            task_id: Task ID.
            data: Updated task data.

        Returns:
            Updated task dictionary.
        """
        return await self._make_request("POST", f"task/{task_id}", data)

    async def complete_task(
        self, project_id: str, task_id: str
    ) -> Dict[str, Any]:
        """Mark a task as completed.

        Args:
            project_id: Project ID the task belongs to.
            task_id: Task ID.

        Returns:
            Response dictionary.
        """
        return await self._make_request(
            "POST", f"project/{project_id}/task/{task_id}/complete"
        )

    async def delete_task(
        self, project_id: str, task_id: str
    ) -> Dict[str, Any]:
        """Delete a task.

        Args:
            project_id: Project ID the task belongs to.
            task_id: Task ID.

        Returns:
            Response dictionary.
        """
        return await self._make_request(
            "DELETE", f"project/{project_id}/task/{task_id}"
        )

    # ---- Projects ----

    async def get_projects(self) -> List[Dict[str, Any]]:
        """Get all projects.

        Returns:
            List of project dictionaries.
        """
        result = await self._make_request("GET", "project")
        return result if isinstance(result, list) else []


class TickTickAdapter(SyncAdapter):
    """TickTick sync adapter.

    EXPERIMENTAL: This adapter integrates with the TickTick Open API
    (https://developer.ticktick.com/api). The API surface may change;
    update this adapter accordingly.

    Required credentials:
        ticktick_token: OAuth2 access token.

    Optional settings:
        ticktick_project_id: Default project ID for new tasks.

    Field mapping:
        task.title       -> Todo.text
        task.content     -> Todo.description
        task.priority    -> Todo.priority  (0=none, 1=low, 3=medium, 5=high)
        task.tags        -> Todo.tags
        task.dueDate     -> Todo.due_date
        task.status      -> Todo.completed (0=normal, 2=completed)
        task.projectId   -> Todo.project
    """

    def __init__(self, config: AppSyncConfig):
        super().__init__(config)
        self.access_token = config.get_credential("ticktick_token")
        self.default_project_id = config.get_setting("ticktick_project_id")
        self._projects_cache: Dict[str, str] = {}  # name -> id
        self._projects_id_cache: Dict[str, str] = {}  # id -> name

    def get_required_credentials(self) -> List[str]:
        return ["ticktick_token"]

    def get_supported_features(self) -> List[str]:
        return [
            "create",
            "read",
            "update",
            "delete",
            "projects",
            "tags",
            "due_dates",
            "priorities",
        ]

    # ------------------------------------------------------------------
    # Authentication
    # ------------------------------------------------------------------

    async def authenticate(self) -> bool:
        """Authenticate with TickTick API by fetching projects."""
        if not self.access_token:
            raise AuthenticationError("No TickTick access token provided")

        try:
            async with TickTickAPI(self.access_token) as api:
                projects = await api.get_projects()
                if isinstance(projects, list):
                    self.logger.info("Authenticated with TickTick")
                    return True
                return False
        except AuthenticationError:
            self.logger.error("TickTick authentication failed - invalid token")
            raise
        except Exception as e:
            self.logger.error(f"TickTick authentication failed: {e}")
            raise AuthenticationError(
                f"Failed to authenticate with TickTick: {e}"
            )

    async def test_connection(self) -> bool:
        """Test connection to TickTick API."""
        try:
            return await self.authenticate()
        except Exception:
            return False

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    async def fetch_items(
        self, since: Optional[datetime] = None
    ) -> List[ExternalTodoItem]:
        """Fetch todo items from TickTick."""
        await self.ensure_authenticated()

        try:
            async with TickTickAPI(self.access_token) as api:
                await self._refresh_projects_cache(api)

                project_id = self.default_project_id
                tasks = await api.get_tasks(project_id=project_id)

                external_items: List[ExternalTodoItem] = []
                for task in tasks:
                    try:
                        item = self.map_external_to_todo(task)
                        external_items.append(item)
                    except Exception as e:
                        self.logger.warning(
                            f"Failed to map TickTick task {task.get('id')}: {e}"
                        )

                self.logger.info(
                    f"Fetched {len(external_items)} tasks from TickTick"
                )
                return external_items

        except (AuthenticationError, RateLimitError):
            raise
        except Exception as e:
            self.logger.error(f"Failed to fetch TickTick items: {e}")
            raise NetworkError(f"Failed to fetch from TickTick: {e}")

    async def create_item(self, todo: Todo) -> str:
        """Create a new item in TickTick."""
        await self.ensure_authenticated()

        try:
            async with TickTickAPI(self.access_token) as api:
                await self._refresh_projects_cache(api)
                task_data = self.map_todo_to_external(todo)
                created = await api.create_task(task_data)
                task_id = str(created.get("id", ""))
                self.log_sync_operation(
                    "create", f"Created task {task_id}: {todo.text}"
                )
                return task_id
        except (AuthenticationError, RateLimitError):
            raise
        except Exception as e:
            self.logger.error(f"Failed to create TickTick task: {e}")
            raise NetworkError(f"Failed to create in TickTick: {e}")

    async def update_item(self, external_id: str, todo: Todo) -> bool:
        """Update an existing item in TickTick."""
        await self.ensure_authenticated()

        try:
            async with TickTickAPI(self.access_token) as api:
                await self._refresh_projects_cache(api)
                task_data = self.map_todo_to_external(todo)
                task_data["id"] = external_id

                await api.update_task(external_id, task_data)

                # Handle completion
                if todo.completed:
                    project_id = task_data.get(
                        "projectId", self.default_project_id or ""
                    )
                    if project_id:
                        await api.complete_task(project_id, external_id)

                self.log_sync_operation(
                    "update", f"Updated task {external_id}: {todo.text}"
                )
                return True
        except (AuthenticationError, RateLimitError):
            raise
        except Exception as e:
            self.logger.error(
                f"Failed to update TickTick task {external_id}: {e}"
            )
            raise NetworkError(f"Failed to update in TickTick: {e}")

    async def delete_item(self, external_id: str) -> bool:
        """Delete an item from TickTick."""
        await self.ensure_authenticated()

        try:
            async with TickTickAPI(self.access_token) as api:
                project_id = self.default_project_id or ""
                await api.delete_task(project_id, external_id)
                self.log_sync_operation(
                    "delete", f"Deleted task {external_id}"
                )
                return True
        except (AuthenticationError, RateLimitError):
            raise
        except Exception as e:
            self.logger.error(
                f"Failed to delete TickTick task {external_id}: {e}"
            )
            return False

    async def fetch_projects(self) -> Dict[str, str]:
        """Fetch available projects from TickTick."""
        await self.ensure_authenticated()

        try:
            async with TickTickAPI(self.access_token) as api:
                projects = await api.get_projects()
                return {
                    p["name"]: p["id"]
                    for p in projects
                    if "name" in p and "id" in p
                }
        except Exception as e:
            self.logger.error(f"Failed to fetch TickTick projects: {e}")
            return {}

    # ------------------------------------------------------------------
    # Mapping
    # ------------------------------------------------------------------

    def map_todo_to_external(self, todo: Todo) -> Dict[str, Any]:
        """Map a local Todo to TickTick task format."""
        task_data: Dict[str, Any] = {"title": todo.text}

        if todo.description:
            task_data["content"] = todo.description

        if todo.priority:
            task_data["priority"] = INTERNAL_PRIORITY_TO_TICKTICK.get(
                todo.priority, 0
            )

        if todo.tags:
            task_data["tags"] = list(todo.tags)

        if todo.due_date:
            task_data["dueDate"] = todo.due_date.strftime(
                "%Y-%m-%dT%H:%M:%S+0000"
            )

        # Status: 0=normal, 2=completed
        task_data["status"] = 2 if todo.completed else 0

        # Project
        project_id = self._resolve_project_id(todo.project)
        if project_id:
            task_data["projectId"] = project_id

        return task_data

    def map_external_to_todo(
        self, external_data: Dict[str, Any]
    ) -> ExternalTodoItem:
        """Map TickTick task data to ExternalTodoItem."""
        task = external_data

        # Parse due date
        due_date = None
        raw_due = task.get("dueDate")
        if raw_due:
            try:
                parsed = datetime.fromisoformat(
                    raw_due.replace("Z", "+00:00")
                )
                due_date = ensure_aware(parsed)
            except Exception as e:
                self.logger.warning(f"Failed to parse dueDate: {e}")

        # Priority
        priority = task.get("priority", 0)

        # Tags
        tags = task.get("tags") or []

        # Status: 0=normal, 2=completed
        status_val = task.get("status", 0)
        completed = status_val == 2

        # Timestamps
        created_at = self._parse_dt(task.get("createdDate"))
        updated_at = self._parse_dt(task.get("modifiedDate")) or created_at
        completed_at = self._parse_dt(task.get("completedTime")) if completed else None

        # Project name from cache
        project_id = task.get("projectId") or ""
        project_name = self._projects_id_cache.get(project_id, project_id)

        return ExternalTodoItem(
            external_id=str(task.get("id", "")),
            provider=AppSyncProvider.TICKTICK,
            title=task.get("title", ""),
            description=task.get("content") or "",
            due_date=due_date,
            priority=priority,
            tags=tags,
            project=project_name,
            project_id=project_id,
            completed=completed,
            completed_at=completed_at,
            created_at=created_at or now_utc(),
            updated_at=updated_at or now_utc(),
            url=None,
            raw_data=task,
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _parse_dt(self, value: Optional[str]) -> Optional[datetime]:
        """Parse a datetime string, returning None on failure."""
        if not value:
            return None
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return ensure_aware(parsed)
        except Exception:
            return None

    def _resolve_project_id(self, project_name: str) -> Optional[str]:
        """Resolve a project name to a TickTick project ID."""
        if project_name in self._projects_cache:
            return self._projects_cache[project_name]
        mapped = self.apply_project_mapping(project_name)
        if mapped and mapped in self._projects_cache:
            return self._projects_cache[mapped]
        return self.default_project_id

    async def _refresh_projects_cache(self, api: TickTickAPI):
        """Refresh the projects cache."""
        try:
            projects = await api.get_projects()
            self._projects_cache = {
                p["name"]: p["id"]
                for p in projects
                if "name" in p and "id" in p
            }
            self._projects_id_cache = {
                p["id"]: p["name"]
                for p in projects
                if "name" in p and "id" in p
            }
        except Exception as e:
            self.logger.warning(f"Failed to refresh projects cache: {e}")
