"""OmniFocus adapter for app synchronization.

This adapter communicates with a local OmniFocus automation bridge server
that exposes OmniFocus data via a REST API. OmniFocus does not provide an
official public REST API, so a local automation bridge (e.g. based on
OmniFocus Automation / JXA scripting) must be running and accessible at the
configured base URL.

Required credentials:
    omnifocus_api_key: API key for the local automation bridge.

Required settings:
    omnifocus_base_url: Base URL of the automation bridge
                        (default ``http://localhost:8080``).

Field mapping:
    task.name      -> Todo.text
    task.note      -> Todo.description
    task.flagged   -> Todo.priority  (flagged = HIGH)
    task.tags      -> Todo.tags
    task.project   -> Todo.project
    task.dueDate   -> Todo.due_date
    task.completed -> Todo.completed / Todo.status
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

# OmniFocus uses flagged (boolean) as a priority indicator.
# We map flagged=True to HIGH, unflagged to MEDIUM.
OMNIFOCUS_FLAGGED_PRIORITY = Priority.HIGH
OMNIFOCUS_UNFLAGGED_PRIORITY = Priority.MEDIUM

INTERNAL_PRIORITY_TO_FLAGGED = {
    Priority.LOW: False,
    Priority.MEDIUM: False,
    Priority.HIGH: True,
    Priority.CRITICAL: True,
}


class OmniFocusAPI:
    """REST client for a local OmniFocus automation bridge.

    The automation bridge should expose endpoints at the configured base URL
    that proxy OmniFocus data over HTTP/JSON.

    Default base URL: ``http://localhost:8080``
    """

    DEFAULT_BASE_URL = "http://localhost:8080"

    def __init__(self, api_key: str, base_url: Optional[str] = None):
        """Initialize OmniFocus API client.

        Args:
            api_key: API key for authentication with the bridge.
            base_url: Base URL of the automation bridge.
        """
        self.api_key = api_key
        self.base_url = (base_url or self.DEFAULT_BASE_URL).rstrip("/") + "/"
        self.headers = {
            "Authorization": f"Bearer {api_key}",
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
        """Make HTTP request to the OmniFocus automation bridge.

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
                raise AuthenticationError("Invalid OmniFocus API key")
            elif response.status_code == 403:
                raise AuthenticationError("OmniFocus API access forbidden")
            elif response.status_code == 429:
                raise RateLimitError("OmniFocus API rate limit exceeded")
            elif response.status_code >= 400:
                raise NetworkError(
                    f"OmniFocus API error {response.status_code}: {response.text}"
                )

            if response.status_code == 204:
                return {}

            return response.json()

        except httpx.TimeoutException:
            raise NetworkError("OmniFocus API request timed out")
        except httpx.RequestError as e:
            raise NetworkError(f"OmniFocus API request failed: {e}")

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
        params: Dict[str, str] = {}
        if project_id:
            params["projectId"] = project_id
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

    # ---- Tags ----

    async def get_tags(self) -> List[Dict[str, Any]]:
        """Get all tags.

        Returns:
            List of tag dictionaries.
        """
        result = await self._make_request("GET", "tags")
        return result if isinstance(result, list) else result.get("tags", [])


class OmniFocusAdapter(SyncAdapter):
    """OmniFocus sync adapter.

    Requires a local OmniFocus automation bridge to be running.
    The bridge must expose a REST API at the configured base URL.

    Required credentials:
        omnifocus_api_key: API key for the automation bridge.

    Required settings:
        omnifocus_base_url: Base URL (default http://localhost:8080).

    Field mapping:
        task.name      -> Todo.text
        task.note      -> Todo.description
        task.flagged   -> Todo.priority  (flagged = HIGH, unflagged = MEDIUM)
        task.tags      -> Todo.tags
        task.project   -> Todo.project
        task.dueDate   -> Todo.due_date
        task.completed -> Todo.completed / Todo.status
    """

    def __init__(self, config: AppSyncConfig):
        super().__init__(config)
        self.api_key = config.get_credential("omnifocus_api_key")
        self.base_url = config.get_setting(
            "omnifocus_base_url", OmniFocusAPI.DEFAULT_BASE_URL
        )
        self._projects_cache: Dict[str, str] = {}  # name -> id
        self._projects_id_cache: Dict[str, str] = {}  # id -> name

    def _make_api(self) -> OmniFocusAPI:
        return OmniFocusAPI(self.api_key, self.base_url)

    def get_required_credentials(self) -> List[str]:
        return ["omnifocus_api_key"]

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
        """Authenticate with the OmniFocus automation bridge."""
        if not self.api_key:
            raise AuthenticationError("No OmniFocus API key provided")

        try:
            async with self._make_api() as api:
                projects = await api.get_projects()
                if isinstance(projects, list):
                    self.logger.info("Authenticated with OmniFocus bridge")
                    return True
                return False
        except AuthenticationError:
            self.logger.error("OmniFocus authentication failed - invalid key")
            raise
        except Exception as e:
            self.logger.error(f"OmniFocus authentication failed: {e}")
            raise AuthenticationError(
                f"Failed to authenticate with OmniFocus: {e}"
            )

    async def test_connection(self) -> bool:
        """Test connection to the OmniFocus automation bridge."""
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
        """Fetch todo items from OmniFocus."""
        await self.ensure_authenticated()

        try:
            async with self._make_api() as api:
                await self._refresh_projects_cache(api)
                tasks = await api.get_tasks()

                external_items: List[ExternalTodoItem] = []
                for task in tasks:
                    try:
                        item = self.map_external_to_todo(task)
                        external_items.append(item)
                    except Exception as e:
                        self.logger.warning(
                            f"Failed to map OmniFocus task {task.get('id')}: {e}"
                        )

                self.logger.info(
                    f"Fetched {len(external_items)} tasks from OmniFocus"
                )
                return external_items

        except (AuthenticationError, RateLimitError):
            raise
        except Exception as e:
            self.logger.error(f"Failed to fetch OmniFocus items: {e}")
            raise NetworkError(f"Failed to fetch from OmniFocus: {e}")

    async def create_item(self, todo: Todo) -> str:
        """Create a new item in OmniFocus."""
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
            self.logger.error(f"Failed to create OmniFocus task: {e}")
            raise NetworkError(f"Failed to create in OmniFocus: {e}")

    async def update_item(self, external_id: str, todo: Todo) -> bool:
        """Update an existing item in OmniFocus."""
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
                f"Failed to update OmniFocus task {external_id}: {e}"
            )
            raise NetworkError(f"Failed to update in OmniFocus: {e}")

    async def delete_item(self, external_id: str) -> bool:
        """Delete an item from OmniFocus."""
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
                f"Failed to delete OmniFocus task {external_id}: {e}"
            )
            return False

    async def fetch_projects(self) -> Dict[str, str]:
        """Fetch available projects from OmniFocus."""
        await self.ensure_authenticated()

        try:
            async with self._make_api() as api:
                projects = await api.get_projects()
                return {
                    p["name"]: p["id"]
                    for p in projects
                    if "name" in p and "id" in p
                }
        except Exception as e:
            self.logger.error(f"Failed to fetch OmniFocus projects: {e}")
            return {}

    # ------------------------------------------------------------------
    # Mapping
    # ------------------------------------------------------------------

    def map_todo_to_external(self, todo: Todo) -> Dict[str, Any]:
        """Map a local Todo to OmniFocus task format."""
        task_data: Dict[str, Any] = {"name": todo.text}

        if todo.description:
            task_data["note"] = todo.description

        task_data["flagged"] = INTERNAL_PRIORITY_TO_FLAGGED.get(
            todo.priority, False
        )

        if todo.tags:
            task_data["tags"] = self.apply_tag_mapping(list(todo.tags))

        if todo.due_date:
            task_data["dueDate"] = todo.due_date.isoformat()

        task_data["completed"] = todo.completed

        # Project
        project_id = self._resolve_project_id(todo.project)
        if project_id:
            task_data["project"] = project_id

        return task_data

    def map_external_to_todo(
        self, external_data: Dict[str, Any]
    ) -> ExternalTodoItem:
        """Map OmniFocus task data to ExternalTodoItem."""
        task = external_data

        # Parse due date
        due_date = self._parse_dt(task.get("dueDate"))

        # Priority from flagged
        flagged = task.get("flagged", False)
        priority = 3 if flagged else 2  # 3=HIGH, 2=MEDIUM in ExternalTodoItem

        # Tags
        raw_tags = task.get("tags") or []
        tags = [
            t.get("name", t) if isinstance(t, dict) else str(t) for t in raw_tags
        ]

        # Completion
        completed = bool(task.get("completed", False))

        # Timestamps
        created_at = self._parse_dt(task.get("createdDate"))
        updated_at = self._parse_dt(task.get("modifiedDate")) or created_at
        completed_at = (
            self._parse_dt(task.get("completedDate")) if completed else None
        )

        # Project
        project_raw = task.get("project")
        if isinstance(project_raw, dict):
            project_name = project_raw.get("name", "")
            project_id = project_raw.get("id", "")
        elif isinstance(project_raw, str):
            project_id = project_raw
            project_name = self._projects_id_cache.get(project_raw, project_raw)
        else:
            project_name = ""
            project_id = ""

        return ExternalTodoItem(
            external_id=str(task.get("id", "")),
            provider=AppSyncProvider.OMNIFOCUS,
            title=task.get("name", ""),
            description=task.get("note") or "",
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
        """Resolve a project name to an OmniFocus project ID."""
        if project_name in self._projects_cache:
            return self._projects_cache[project_name]
        mapped = self.apply_project_mapping(project_name)
        if mapped and mapped in self._projects_cache:
            return self._projects_cache[mapped]
        return None

    async def _refresh_projects_cache(self, api: OmniFocusAPI):
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
