"""Things 3 adapter for app synchronization.

This adapter communicates with a local Things automation bridge server
that exposes Things 3 data via a REST API. Things 3 has a URL scheme API
and Things Cloud for reading, but no official public REST API, so a local
automation bridge must be running and accessible at the configured base URL.

Required credentials:
    things_token: API token for the local automation bridge.

Required settings:
    things_base_url: Base URL of the automation bridge
                     (default ``http://localhost:8081``).

Field mapping:
    task.title          -> Todo.text
    task.notes          -> Todo.description
    task.tags           -> Todo.tags
    task.project / area -> Todo.project
    task.dueDate        -> Todo.due_date
    task.status         -> Todo.status  (open / completed / cancelled)
    task.checklist      -> subtask info appended to Todo.description
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

# Things status mapping
THINGS_STATUS_OPEN = "open"
THINGS_STATUS_COMPLETED = "completed"
THINGS_STATUS_CANCELLED = "cancelled"

THINGS_STATUS_TO_TODO_STATUS = {
    THINGS_STATUS_OPEN: TodoStatus.PENDING,
    THINGS_STATUS_COMPLETED: TodoStatus.COMPLETED,
    THINGS_STATUS_CANCELLED: TodoStatus.CANCELLED,
}

TODO_STATUS_TO_THINGS = {
    TodoStatus.PENDING: THINGS_STATUS_OPEN,
    TodoStatus.IN_PROGRESS: THINGS_STATUS_OPEN,
    TodoStatus.COMPLETED: THINGS_STATUS_COMPLETED,
    TodoStatus.CANCELLED: THINGS_STATUS_CANCELLED,
    TodoStatus.BLOCKED: THINGS_STATUS_OPEN,
}


class ThingsAPI:
    """REST client for a local Things 3 automation bridge.

    The automation bridge should expose endpoints at the configured base URL
    that proxy Things 3 data over HTTP/JSON.

    Default base URL: ``http://localhost:8081``
    """

    DEFAULT_BASE_URL = "http://localhost:8081"

    def __init__(self, token: str, base_url: Optional[str] = None):
        """Initialize Things API client.

        Args:
            token: API token for authentication with the bridge.
            base_url: Base URL of the automation bridge.
        """
        self.token = token
        self.base_url = (base_url or self.DEFAULT_BASE_URL).rstrip("/") + "/"
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
        """Make HTTP request to the Things automation bridge.

        Raises:
            AuthenticationError: On 401/403.
            RateLimitError: On 429.
            NetworkError: On other HTTP errors or connection failures.
        """
        if self.client is None:
            raise NetworkError(
                "HTTP client not initialized. Use 'async with' context manager."
            )

        url = urljoin(self.base_url, endpoint)

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
                raise AuthenticationError("Invalid Things API token")
            elif response.status_code == 403:
                raise AuthenticationError("Things API access forbidden")
            elif response.status_code == 429:
                raise RateLimitError("Things API rate limit exceeded")
            elif response.status_code >= 400:
                raise NetworkError(
                    f"Things API error {response.status_code}: {response.text}"
                )

            if response.status_code == 204:
                return {}

            return response.json()

        except httpx.TimeoutException:
            raise NetworkError("Things API request timed out")
        except httpx.RequestError as e:
            raise NetworkError(f"Things API request failed: {e}")

    # ---- Tasks ----

    async def get_tasks(
        self,
        project_id: Optional[str] = None,
        area_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Get tasks, optionally filtered by project or area.

        Args:
            project_id: Optional project ID to filter tasks.
            area_id: Optional area ID to filter tasks.

        Returns:
            List of task dictionaries.
        """
        params: Dict[str, str] = {}
        if project_id:
            params["projectId"] = project_id
        if area_id:
            params["areaId"] = area_id
        result = await self._make_request("GET", "tasks", params=params)
        return result if isinstance(result, list) else result.get("tasks", [])

    async def create_task(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new task.

        Args:
            data: Task data dictionary.

        Returns:
            Created task dictionary.
        """
        return await self._make_request("POST", "tasks", data)

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
        return await self._make_request("PUT", f"tasks/{task_id}", data)

    async def complete_task(self, task_id: str) -> Dict[str, Any]:
        """Mark a task as completed.

        Args:
            task_id: Task ID.

        Returns:
            Response dictionary.
        """
        return await self._make_request("POST", f"tasks/{task_id}/complete")

    async def delete_task(self, task_id: str) -> Dict[str, Any]:
        """Delete a task.

        Args:
            task_id: Task ID.

        Returns:
            Response dictionary.
        """
        return await self._make_request("DELETE", f"tasks/{task_id}")

    # ---- Projects ----

    async def get_projects(self) -> List[Dict[str, Any]]:
        """Get all projects.

        Returns:
            List of project dictionaries.
        """
        result = await self._make_request("GET", "projects")
        return result if isinstance(result, list) else result.get("projects", [])

    # ---- Areas ----

    async def get_areas(self) -> List[Dict[str, Any]]:
        """Get all areas.

        Returns:
            List of area dictionaries.
        """
        result = await self._make_request("GET", "areas")
        return result if isinstance(result, list) else result.get("areas", [])

    # ---- Tags ----

    async def get_tags(self) -> List[Dict[str, Any]]:
        """Get all tags.

        Returns:
            List of tag dictionaries.
        """
        result = await self._make_request("GET", "tags")
        return result if isinstance(result, list) else result.get("tags", [])


class ThingsAdapter(SyncAdapter):
    """Things 3 sync adapter.

    Requires a local Things automation bridge to be running.
    The bridge must expose a REST API at the configured base URL.

    Required credentials:
        things_token: API token for the automation bridge.

    Required settings:
        things_base_url: Base URL (default http://localhost:8081).

    Field mapping:
        task.title          -> Todo.text
        task.notes          -> Todo.description
        task.tags           -> Todo.tags
        task.project / area -> Todo.project
        task.dueDate        -> Todo.due_date
        task.status         -> Todo.status (open/completed/cancelled)
        task.checklist      -> subtask info appended to description
    """

    def __init__(self, config: AppSyncConfig):
        super().__init__(config)
        self.token = config.get_credential("things_token")
        self.base_url = config.get_setting(
            "things_base_url", ThingsAPI.DEFAULT_BASE_URL
        )
        self._projects_cache: Dict[str, str] = {}  # name -> id
        self._projects_id_cache: Dict[str, str] = {}  # id -> name
        self._areas_cache: Dict[str, str] = {}  # name -> id
        self._areas_id_cache: Dict[str, str] = {}  # id -> name

    def _make_api(self) -> ThingsAPI:
        return ThingsAPI(self.token, self.base_url)

    def get_required_credentials(self) -> List[str]:
        return ["things_token"]

    def get_supported_features(self) -> List[str]:
        return [
            "create",
            "read",
            "update",
            "delete",
            "projects",
            "areas",
            "tags",
            "due_dates",
            "checklists",
        ]

    # ------------------------------------------------------------------
    # Authentication
    # ------------------------------------------------------------------

    async def authenticate(self) -> bool:
        """Authenticate with the Things automation bridge."""
        if not self.token:
            raise AuthenticationError("No Things API token provided")

        try:
            async with self._make_api() as api:
                projects = await api.get_projects()
                if isinstance(projects, list):
                    self.logger.info("Authenticated with Things bridge")
                    return True
                return False
        except AuthenticationError:
            self.logger.error("Things authentication failed - invalid token")
            raise
        except Exception as e:
            self.logger.error(f"Things authentication failed: {e}")
            raise AuthenticationError(
                f"Failed to authenticate with Things: {e}"
            )

    async def test_connection(self) -> bool:
        """Test connection to the Things automation bridge."""
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
        """Fetch todo items from Things."""
        await self.ensure_authenticated()

        try:
            async with self._make_api() as api:
                await self._refresh_projects_cache(api)
                await self._refresh_areas_cache(api)
                tasks = await api.get_tasks()

                external_items: List[ExternalTodoItem] = []
                for task in tasks:
                    try:
                        item = self.map_external_to_todo(task)
                        external_items.append(item)
                    except Exception as e:
                        self.logger.warning(
                            f"Failed to map Things task {task.get('id')}: {e}"
                        )

                self.logger.info(
                    f"Fetched {len(external_items)} tasks from Things"
                )
                return external_items

        except (AuthenticationError, RateLimitError):
            raise
        except Exception as e:
            self.logger.error(f"Failed to fetch Things items: {e}")
            raise NetworkError(f"Failed to fetch from Things: {e}")

    async def create_item(self, todo: Todo) -> str:
        """Create a new item in Things."""
        await self.ensure_authenticated()

        try:
            async with self._make_api() as api:
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
            self.logger.error(f"Failed to create Things task: {e}")
            raise NetworkError(f"Failed to create in Things: {e}")

    async def update_item(self, external_id: str, todo: Todo) -> bool:
        """Update an existing item in Things."""
        await self.ensure_authenticated()

        try:
            async with self._make_api() as api:
                await self._refresh_projects_cache(api)
                task_data = self.map_todo_to_external(todo)
                await api.update_task(external_id, task_data)

                if todo.completed:
                    await api.complete_task(external_id)

                self.log_sync_operation(
                    "update", f"Updated task {external_id}: {todo.text}"
                )
                return True
        except (AuthenticationError, RateLimitError):
            raise
        except Exception as e:
            self.logger.error(
                f"Failed to update Things task {external_id}: {e}"
            )
            raise NetworkError(f"Failed to update in Things: {e}")

    async def delete_item(self, external_id: str) -> bool:
        """Delete an item from Things."""
        await self.ensure_authenticated()

        try:
            async with self._make_api() as api:
                await api.delete_task(external_id)
                self.log_sync_operation(
                    "delete", f"Deleted task {external_id}"
                )
                return True
        except (AuthenticationError, RateLimitError):
            raise
        except Exception as e:
            self.logger.error(
                f"Failed to delete Things task {external_id}: {e}"
            )
            return False

    async def fetch_projects(self) -> Dict[str, str]:
        """Fetch available projects from Things."""
        await self.ensure_authenticated()

        try:
            async with self._make_api() as api:
                projects = await api.get_projects()
                return {
                    p["title"]: p["id"]
                    for p in projects
                    if "title" in p and "id" in p
                }
        except Exception as e:
            self.logger.error(f"Failed to fetch Things projects: {e}")
            return {}

    # ------------------------------------------------------------------
    # Mapping
    # ------------------------------------------------------------------

    def map_todo_to_external(self, todo: Todo) -> Dict[str, Any]:
        """Map a local Todo to Things task format."""
        task_data: Dict[str, Any] = {"title": todo.text}

        if todo.description:
            task_data["notes"] = todo.description

        if todo.tags:
            task_data["tags"] = self.apply_tag_mapping(list(todo.tags))

        if todo.due_date:
            task_data["dueDate"] = todo.due_date.isoformat()

        task_data["status"] = TODO_STATUS_TO_THINGS.get(
            todo.status, THINGS_STATUS_OPEN
        )

        # Project
        project_id = self._resolve_project_id(todo.project)
        if project_id:
            task_data["project"] = project_id

        return task_data

    def map_external_to_todo(
        self, external_data: Dict[str, Any]
    ) -> ExternalTodoItem:
        """Map Things task data to ExternalTodoItem."""
        task = external_data

        # Parse due date
        due_date = self._parse_dt(task.get("dueDate"))

        # Things has no priority field; default to MEDIUM (2)
        priority = 2

        # Tags
        raw_tags = task.get("tags") or []
        tags = [
            t.get("title", t) if isinstance(t, dict) else str(t) for t in raw_tags
        ]

        # Status
        status_str = task.get("status", THINGS_STATUS_OPEN)
        completed = status_str == THINGS_STATUS_COMPLETED

        # Timestamps
        created_at = self._parse_dt(task.get("createdDate"))
        updated_at = self._parse_dt(task.get("modifiedDate")) or created_at
        completed_at = (
            self._parse_dt(task.get("completedDate")) if completed else None
        )

        # Project / Area
        project_raw = task.get("project")
        area_raw = task.get("area")
        project_name = ""
        project_id = ""

        if isinstance(project_raw, dict):
            project_name = project_raw.get("title", "")
            project_id = project_raw.get("id", "")
        elif isinstance(project_raw, str):
            project_id = project_raw
            project_name = self._projects_id_cache.get(project_raw, project_raw)
        elif isinstance(area_raw, dict):
            project_name = area_raw.get("title", "")
            project_id = area_raw.get("id", "")
        elif isinstance(area_raw, str):
            project_id = area_raw
            project_name = self._areas_id_cache.get(area_raw, area_raw)

        # Checklist items -> append to description
        description = task.get("notes") or ""
        checklist = task.get("checklist") or []
        if checklist:
            checklist_lines = []
            for item in checklist:
                if isinstance(item, dict):
                    title = item.get("title", "")
                    done = item.get("completed", False)
                    prefix = "[x]" if done else "[ ]"
                    checklist_lines.append(f"  {prefix} {title}")
                else:
                    checklist_lines.append(f"  [ ] {item}")
            if checklist_lines:
                if description:
                    description += "\n\nChecklist:\n"
                else:
                    description = "Checklist:\n"
                description += "\n".join(checklist_lines)

        return ExternalTodoItem(
            external_id=str(task.get("id", "")),
            provider=AppSyncProvider.THINGS,
            title=task.get("title", ""),
            description=description,
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
        """Resolve a project name to a Things project ID."""
        if project_name in self._projects_cache:
            return self._projects_cache[project_name]
        mapped = self.apply_project_mapping(project_name)
        if mapped and mapped in self._projects_cache:
            return self._projects_cache[mapped]
        return None

    async def _refresh_projects_cache(self, api: ThingsAPI):
        """Refresh the projects cache."""
        try:
            projects = await api.get_projects()
            self._projects_cache = {
                p["title"]: p["id"]
                for p in projects
                if "title" in p and "id" in p
            }
            self._projects_id_cache = {
                p["id"]: p["title"]
                for p in projects
                if "title" in p and "id" in p
            }
        except Exception as e:
            self.logger.warning(f"Failed to refresh projects cache: {e}")

    async def _refresh_areas_cache(self, api: ThingsAPI):
        """Refresh the areas cache."""
        try:
            areas = await api.get_areas()
            self._areas_cache = {
                a["title"]: a["id"]
                for a in areas
                if "title" in a and "id" in a
            }
            self._areas_id_cache = {
                a["id"]: a["title"]
                for a in areas
                if "title" in a and "id" in a
            }
        except Exception as e:
            self.logger.warning(f"Failed to refresh areas cache: {e}")
