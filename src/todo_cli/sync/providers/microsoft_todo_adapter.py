"""Microsoft Todo adapter for app synchronization.

This module provides integration with the Microsoft Graph API for bidirectional
synchronization of todo items, task lists, and related metadata.
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


class MicrosoftGraphAPI:
    """Microsoft Graph API client for Todo operations."""

    BASE_URL = "https://graph.microsoft.com/v1.0/"

    def __init__(self, access_token: str):
        """Initialize Microsoft Graph API client.

        Args:
            access_token: OAuth2 access token for Microsoft Graph
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
    ) -> Any:
        """Make HTTP request to Microsoft Graph API.

        Args:
            method: HTTP method
            endpoint: API endpoint (relative to BASE_URL)
            data: Request body data

        Returns:
            Response data

        Raises:
            AuthenticationError: If authentication fails
            RateLimitError: If rate limit is exceeded
            NetworkError: If network request fails
        """
        if self.client is None:
            raise NetworkError(
                "HTTP client not initialized. Use 'async with' context manager."
            )

        url = f"{self.BASE_URL}{endpoint}"

        try:
            if method.upper() == "GET":
                response = await self.client.get(
                    url, headers=self.headers, params=data
                )
            elif method.upper() == "POST":
                response = await self.client.post(
                    url, headers=self.headers, json=data
                )
            elif method.upper() == "PATCH":
                response = await self.client.patch(
                    url, headers=self.headers, json=data
                )
            elif method.upper() == "DELETE":
                response = await self.client.delete(url, headers=self.headers)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")

            if response.status_code == 401:
                raise AuthenticationError("Invalid or expired Microsoft access token")
            elif response.status_code == 403:
                raise AuthenticationError("Microsoft Graph API access forbidden")
            elif response.status_code == 429:
                raise RateLimitError("Microsoft Graph API rate limit exceeded")
            elif response.status_code >= 400:
                error_msg = (
                    f"Microsoft Graph API error {response.status_code}: {response.text}"
                )
                raise NetworkError(error_msg)

            if response.status_code == 204:
                return {}

            return response.json()

        except httpx.TimeoutException:
            raise NetworkError("Microsoft Graph API request timed out")
        except httpx.RequestError as e:
            raise NetworkError(f"Microsoft Graph API request failed: {e}")

    # User info

    async def get_me(self) -> Dict[str, Any]:
        """Get current user profile information."""
        return await self._make_request("GET", "me")

    # Task Lists

    async def get_task_lists(self) -> List[Dict[str, Any]]:
        """Get all task lists."""
        result = await self._make_request("GET", "me/todo/lists")
        return result.get("value", [])

    # Tasks

    async def get_tasks(self, list_id: str) -> List[Dict[str, Any]]:
        """Get all tasks in a task list.

        Args:
            list_id: The task list ID
        """
        result = await self._make_request(
            "GET", f"me/todo/lists/{list_id}/tasks"
        )
        return result.get("value", [])

    async def create_task(
        self, list_id: str, data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Create a new task in a task list.

        Args:
            list_id: The task list ID
            data: Task data
        """
        return await self._make_request(
            "POST", f"me/todo/lists/{list_id}/tasks", data
        )

    async def update_task(
        self, list_id: str, task_id: str, data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Update a task in a task list.

        Args:
            list_id: The task list ID
            task_id: The task ID
            data: Updated task data
        """
        return await self._make_request(
            "PATCH", f"me/todo/lists/{list_id}/tasks/{task_id}", data
        )

    async def delete_task(self, list_id: str, task_id: str) -> Dict[str, Any]:
        """Delete a task from a task list.

        Args:
            list_id: The task list ID
            task_id: The task ID
        """
        return await self._make_request(
            "DELETE", f"me/todo/lists/{list_id}/tasks/{task_id}"
        )


# Priority mapping: Microsoft Todo importance -> internal priority integer
_MS_IMPORTANCE_TO_PRIORITY = {
    "low": 1,
    "normal": 2,
    "high": 3,
}

# Internal priority integer -> Microsoft Todo importance
_PRIORITY_TO_MS_IMPORTANCE = {
    1: "low",
    2: "normal",
    3: "high",
}

# Priority enum -> Microsoft Todo importance
_PRIORITY_ENUM_TO_MS_IMPORTANCE = {
    Priority.LOW: "low",
    Priority.MEDIUM: "normal",
    Priority.HIGH: "high",
    Priority.CRITICAL: "high",
}

# Microsoft Todo importance -> Priority enum
_MS_IMPORTANCE_TO_PRIORITY_ENUM = {
    "low": Priority.LOW,
    "normal": Priority.MEDIUM,
    "high": Priority.HIGH,
}

# TodoStatus -> Microsoft Todo status
_STATUS_TO_MS_STATUS = {
    TodoStatus.PENDING: "notStarted",
    TodoStatus.IN_PROGRESS: "inProgress",
    TodoStatus.COMPLETED: "completed",
    TodoStatus.CANCELLED: "notStarted",
    TodoStatus.BLOCKED: "notStarted",
}

# Microsoft Todo status -> TodoStatus
_MS_STATUS_TO_STATUS = {
    "notStarted": TodoStatus.PENDING,
    "inProgress": TodoStatus.IN_PROGRESS,
    "completed": TodoStatus.COMPLETED,
}


class MicrosoftTodoAdapter(SyncAdapter):
    """Microsoft Todo adapter for app synchronization via Microsoft Graph API."""

    def __init__(self, config: AppSyncConfig):
        """Initialize Microsoft Todo adapter.

        Args:
            config: App sync configuration
        """
        super().__init__(config)
        self.access_token = config.get_credential("ms_access_token")
        self.task_list_id = config.get_setting("ms_task_list_id", "")
        self.api: Optional[MicrosoftGraphAPI] = None

    def get_required_credentials(self) -> List[str]:
        """Get required credentials for Microsoft Todo."""
        return ["ms_access_token"]

    def get_supported_features(self) -> List[str]:
        """Get features supported by Microsoft Todo adapter."""
        return [
            "create",
            "read",
            "update",
            "delete",
            "projects",
            "tags",
            "due_dates",
            "priorities",
            "descriptions",
        ]

    async def authenticate(self) -> bool:
        """Authenticate with Microsoft Graph API."""
        if not self.access_token:
            raise AuthenticationError("No Microsoft access token provided")

        try:
            async with MicrosoftGraphAPI(self.access_token) as api:
                user_info = await api.get_me()
                if user_info and "id" in user_info:
                    self.logger.info(
                        f"Authenticated with Microsoft as "
                        f"{user_info.get('displayName', 'Unknown User')}"
                    )
                    return True
                return False

        except AuthenticationError:
            self.logger.error(
                "Microsoft authentication failed - invalid access token"
            )
            raise
        except Exception as e:
            self.logger.error(f"Microsoft authentication failed: {e}")
            raise AuthenticationError(
                f"Failed to authenticate with Microsoft: {e}"
            )

    async def test_connection(self) -> bool:
        """Test connection to Microsoft Graph API."""
        try:
            return await self.authenticate()
        except Exception:
            return False

    async def fetch_items(
        self, since: Optional[datetime] = None
    ) -> List[ExternalTodoItem]:
        """Fetch todo items from Microsoft Todo."""
        await self.ensure_authenticated()

        if not self.task_list_id:
            raise ValidationError(
                "No task list ID configured. Set 'ms_task_list_id' in settings."
            )

        try:
            async with MicrosoftGraphAPI(self.access_token) as api:
                tasks = await api.get_tasks(self.task_list_id)

                external_items = []
                for task in tasks:
                    try:
                        external_item = self.map_external_to_todo(task)
                        external_items.append(external_item)
                    except Exception as e:
                        self.logger.warning(
                            f"Failed to map Microsoft Todo task "
                            f"{task.get('id')}: {e}"
                        )
                        continue

                self.logger.info(
                    f"Fetched {len(external_items)} tasks from Microsoft Todo"
                )
                return external_items

        except (AuthenticationError, ValidationError):
            raise
        except Exception as e:
            self.logger.error(f"Failed to fetch Microsoft Todo items: {e}")
            raise NetworkError(f"Failed to fetch from Microsoft Todo: {e}")

    async def create_item(self, todo: Todo) -> str:
        """Create a new item in Microsoft Todo."""
        await self.ensure_authenticated()

        if not self.task_list_id:
            raise ValidationError(
                "No task list ID configured. Set 'ms_task_list_id' in settings."
            )

        try:
            async with MicrosoftGraphAPI(self.access_token) as api:
                task_data = self.map_todo_to_external(todo)
                created_task = await api.create_task(
                    self.task_list_id, task_data
                )
                task_id = created_task["id"]

                self.log_sync_operation(
                    "create", f"Created task {task_id}: {todo.text}"
                )
                return task_id

        except (AuthenticationError, ValidationError):
            raise
        except Exception as e:
            self.logger.error(f"Failed to create Microsoft Todo task: {e}")
            raise NetworkError(f"Failed to create in Microsoft Todo: {e}")

    async def update_item(self, external_id: str, todo: Todo) -> bool:
        """Update an existing item in Microsoft Todo."""
        await self.ensure_authenticated()

        if not self.task_list_id:
            raise ValidationError(
                "No task list ID configured. Set 'ms_task_list_id' in settings."
            )

        try:
            async with MicrosoftGraphAPI(self.access_token) as api:
                task_data = self.map_todo_to_external(todo)
                await api.update_task(
                    self.task_list_id, external_id, task_data
                )

                self.log_sync_operation(
                    "update", f"Updated task {external_id}: {todo.text}"
                )
                return True

        except (AuthenticationError, ValidationError):
            raise
        except Exception as e:
            self.logger.error(
                f"Failed to update Microsoft Todo task {external_id}: {e}"
            )
            raise NetworkError(f"Failed to update in Microsoft Todo: {e}")

    async def delete_item(self, external_id: str) -> bool:
        """Delete an item from Microsoft Todo."""
        await self.ensure_authenticated()

        if not self.task_list_id:
            raise ValidationError(
                "No task list ID configured. Set 'ms_task_list_id' in settings."
            )

        try:
            async with MicrosoftGraphAPI(self.access_token) as api:
                await api.delete_task(self.task_list_id, external_id)
                self.log_sync_operation(
                    "delete", f"Deleted task {external_id}"
                )
                return True

        except (AuthenticationError, ValidationError):
            raise
        except Exception as e:
            self.logger.error(
                f"Failed to delete Microsoft Todo task {external_id}: {e}"
            )
            return False

    async def fetch_projects(self) -> Dict[str, str]:
        """Fetch available task lists from Microsoft Todo."""
        await self.ensure_authenticated()

        try:
            async with MicrosoftGraphAPI(self.access_token) as api:
                task_lists = await api.get_task_lists()

                project_map = {}
                for task_list in task_lists:
                    project_map[task_list["displayName"]] = task_list["id"]

                return project_map

        except Exception as e:
            self.logger.error(
                f"Failed to fetch Microsoft Todo task lists: {e}"
            )
            return {}

    def map_todo_to_external(self, todo: Todo) -> Dict[str, Any]:
        """Map a local Todo to Microsoft Todo task format."""
        task_data: Dict[str, Any] = {
            "title": todo.text,
        }

        # Description / body
        if todo.description:
            task_data["body"] = {
                "content": todo.description,
                "contentType": "text",
            }

        # Importance / priority
        importance = _PRIORITY_ENUM_TO_MS_IMPORTANCE.get(
            todo.priority, "normal"
        )
        task_data["importance"] = importance

        # Status
        status = _STATUS_TO_MS_STATUS.get(todo.status, "notStarted")
        task_data["status"] = status

        # Due date
        if todo.due_date:
            task_data["dueDateTime"] = {
                "dateTime": todo.due_date.strftime("%Y-%m-%dT%H:%M:%S.0000000"),
                "timeZone": "UTC",
            }

        # Tags / categories
        if todo.tags:
            task_data["categories"] = list(todo.tags)

        return task_data

    def map_external_to_todo(
        self, external_data: Dict[str, Any]
    ) -> ExternalTodoItem:
        """Map Microsoft Todo task data to ExternalTodoItem."""
        task = external_data

        # Parse due date
        due_date = None
        if task.get("dueDateTime"):
            try:
                due_info = task["dueDateTime"]
                date_str = due_info.get("dateTime", "")
                if date_str:
                    parsed = datetime.fromisoformat(
                        date_str.replace("Z", "+00:00")
                    )
                    due_date = ensure_aware(parsed)
            except Exception as e:
                self.logger.warning(
                    f"Failed to parse due date from Microsoft Todo task: {e}"
                )

        # Map importance to priority integer
        importance = task.get("importance", "normal")
        priority = _MS_IMPORTANCE_TO_PRIORITY.get(importance, 2)

        # Map status
        ms_status = task.get("status", "notStarted")
        todo_status = _MS_STATUS_TO_STATUS.get(ms_status, TodoStatus.PENDING)
        completed = todo_status == TodoStatus.COMPLETED

        # Completed datetime
        completed_at = None
        if completed and task.get("completedDateTime"):
            try:
                comp_info = task["completedDateTime"]
                date_str = comp_info.get("dateTime", "")
                if date_str:
                    parsed = datetime.fromisoformat(
                        date_str.replace("Z", "+00:00")
                    )
                    completed_at = ensure_aware(parsed)
            except Exception as e:
                self.logger.warning(
                    f"Failed to parse completedDateTime: {e}"
                )

        # Created datetime
        created_at = None
        if task.get("createdDateTime"):
            try:
                parsed = datetime.fromisoformat(
                    task["createdDateTime"].replace("Z", "+00:00")
                )
                created_at = ensure_aware(parsed)
            except Exception as e:
                self.logger.warning(
                    f"Failed to parse createdDateTime: {e}"
                )
        if created_at is None:
            created_at = now_utc()

        # Updated datetime
        updated_at = None
        if task.get("lastModifiedDateTime"):
            try:
                parsed = datetime.fromisoformat(
                    task["lastModifiedDateTime"].replace("Z", "+00:00")
                )
                updated_at = ensure_aware(parsed)
            except Exception as e:
                self.logger.warning(
                    f"Failed to parse lastModifiedDateTime: {e}"
                )
        if updated_at is None:
            updated_at = created_at

        # Body / description
        description = ""
        if task.get("body"):
            description = task["body"].get("content", "")

        # Categories / tags
        tags = task.get("categories", [])

        return ExternalTodoItem(
            external_id=str(task["id"]),
            provider=AppSyncProvider.MICROSOFT_TODO,
            title=task.get("title", ""),
            description=description,
            due_date=due_date,
            priority=priority,
            tags=tags,
            project=None,
            project_id=None,
            completed=completed,
            completed_at=completed_at,
            created_at=created_at,
            updated_at=updated_at,
            raw_data=task,
        )
