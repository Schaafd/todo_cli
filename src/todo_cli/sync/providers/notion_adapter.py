"""Notion adapter for app synchronization.

This module provides integration with the Notion API for bidirectional
synchronization of todo items stored in Notion databases.
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


# Priority mapping: Notion select option name -> internal integer
PRIORITY_NAME_MAP = {
    "critical": 4,
    "high": 3,
    "medium": 2,
    "low": 1,
}

PRIORITY_INT_TO_NAME = {v: k for k, v in PRIORITY_NAME_MAP.items()}

PRIORITY_ENUM_TO_INT = {
    Priority.CRITICAL: 4,
    Priority.HIGH: 3,
    Priority.MEDIUM: 2,
    Priority.LOW: 1,
}

PRIORITY_INT_TO_ENUM = {v: k for k, v in PRIORITY_ENUM_TO_INT.items()}

# Status mapping: Notion status/select values -> completed flag
COMPLETED_STATUSES = {"done", "completed", "complete", "closed"}


class NotionAPI:
    """Notion API v1 client."""

    BASE_URL = "https://api.notion.com/v1/"
    NOTION_VERSION = "2022-06-28"

    def __init__(self, token: str):
        """Initialize Notion API client.

        Args:
            token: Notion Integration Token
        """
        self.token = token
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Notion-Version": self.NOTION_VERSION,
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
        """Make HTTP request to Notion API.

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
            elif method.upper() == "PATCH":
                response = await self.client.patch(url, headers=self.headers, json=data)
            elif method.upper() == "DELETE":
                response = await self.client.delete(url, headers=self.headers)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")

            if response.status_code == 401:
                raise AuthenticationError("Invalid Notion integration token")
            elif response.status_code == 403:
                raise AuthenticationError("Notion API access forbidden")
            elif response.status_code == 404:
                raise NetworkError(f"Notion resource not found: {endpoint}")
            elif response.status_code == 429:
                raise RateLimitError("Notion API rate limit exceeded")
            elif response.status_code >= 400:
                raise NetworkError(f"Notion API error {response.status_code}: {response.text}")

            if response.status_code == 204:
                return {}

            return response.json()

        except httpx.TimeoutException:
            raise NetworkError("Notion API request timed out")
        except httpx.RequestError as e:
            raise NetworkError(f"Notion API request failed: {e}")

    # --- Authentication ---

    async def get_me(self) -> Dict[str, Any]:
        """Get the bot user associated with the integration token."""
        return await self._make_request("GET", "users/me")

    # --- Databases ---

    async def query_database(
        self,
        database_id: str,
        filter: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Query a Notion database.

        Args:
            database_id: The database ID to query
            filter: Optional filter object

        Returns:
            Query results containing pages
        """
        data: Dict[str, Any] = {}
        if filter is not None:
            data["filter"] = filter
        return await self._make_request("POST", f"databases/{database_id}/query", data=data)

    async def search_databases(self) -> Dict[str, Any]:
        """Search for databases the integration has access to."""
        data = {
            "filter": {"value": "database", "property": "object"},
        }
        return await self._make_request("POST", "search", data=data)

    # --- Pages ---

    async def create_page(
        self,
        database_id: str,
        properties: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Create a page in a database.

        Args:
            database_id: Parent database ID
            properties: Page properties

        Returns:
            Created page object
        """
        data = {
            "parent": {"database_id": database_id},
            "properties": properties,
        }
        return await self._make_request("POST", "pages", data=data)

    async def update_page(
        self,
        page_id: str,
        properties: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Update a page's properties.

        Args:
            page_id: The page ID to update
            properties: Properties to update

        Returns:
            Updated page object
        """
        data = {"properties": properties}
        return await self._make_request("PATCH", f"pages/{page_id}", data=data)

    async def archive_page(self, page_id: str) -> Dict[str, Any]:
        """Archive (soft-delete) a page.

        Args:
            page_id: The page ID to archive

        Returns:
            Archived page object
        """
        data = {"archived": True}
        return await self._make_request("PATCH", f"pages/{page_id}", data=data)

    async def get_page(self, page_id: str) -> Dict[str, Any]:
        """Get a page by ID.

        Args:
            page_id: The page ID

        Returns:
            Page object
        """
        return await self._make_request("GET", f"pages/{page_id}")


class NotionAdapter(SyncAdapter):
    """Notion adapter for app synchronization."""

    def __init__(self, config: AppSyncConfig):
        """Initialize Notion adapter.

        Args:
            config: App sync configuration
        """
        super().__init__(config)
        self.notion_token = config.get_credential("notion_token")
        self.database_id: str = config.get_setting("notion_database_id", "")
        self.api: Optional[NotionAPI] = None

    def get_required_credentials(self) -> List[str]:
        return ["notion_token"]

    def get_supported_features(self) -> List[str]:
        return [
            "create", "read", "update", "delete",
            "projects", "tags", "due_dates", "priorities",
            "descriptions", "assignees",
        ]

    # ------------------------------------------------------------------
    # Authentication
    # ------------------------------------------------------------------

    async def authenticate(self) -> bool:
        """Authenticate with Notion API using the integration token."""
        if not self.notion_token:
            raise AuthenticationError("No Notion integration token provided")

        try:
            async with NotionAPI(self.notion_token) as api:
                user_info = await api.get_me()
                if user_info and user_info.get("type") == "bot":
                    self.logger.info("Authenticated with Notion integration")
                    return True
                return False
        except AuthenticationError:
            self.logger.error("Notion authentication failed - invalid token")
            raise
        except Exception as e:
            self.logger.error(f"Notion authentication failed: {e}")
            raise AuthenticationError(f"Failed to authenticate with Notion: {e}")

    async def test_connection(self) -> bool:
        """Test connection to Notion API."""
        try:
            return await self.authenticate()
        except Exception:
            return False

    # ------------------------------------------------------------------
    # CRUD operations
    # ------------------------------------------------------------------

    async def fetch_items(self, since: Optional[datetime] = None) -> List[ExternalTodoItem]:
        """Fetch pages from the configured Notion database."""
        await self.ensure_authenticated()

        try:
            async with NotionAPI(self.notion_token) as api:
                filter_obj = None
                if since:
                    filter_obj = {
                        "timestamp": "last_edited_time",
                        "last_edited_time": {
                            "after": since.isoformat(),
                        },
                    }

                result = await api.query_database(self.database_id, filter=filter_obj)
                pages = result.get("results", [])

                external_items: List[ExternalTodoItem] = []
                for page in pages:
                    try:
                        item = self.map_external_to_todo(page)
                        external_items.append(item)
                    except Exception as e:
                        self.logger.warning(
                            f"Failed to map Notion page {page.get('id')}: {e}"
                        )

                self.logger.info(f"Fetched {len(external_items)} pages from Notion")
                return external_items

        except (AuthenticationError, RateLimitError, ValidationError):
            raise
        except Exception as e:
            self.logger.error(f"Failed to fetch Notion pages: {e}")
            raise NetworkError(f"Failed to fetch from Notion: {e}")

    async def create_item(self, todo: Todo) -> str:
        """Create a new page in the Notion database from a Todo."""
        await self.ensure_authenticated()

        try:
            async with NotionAPI(self.notion_token) as api:
                properties = self.map_todo_to_external(todo)
                created = await api.create_page(self.database_id, properties)
                page_id = created["id"]
                self.log_sync_operation("create", f"Created page {page_id}: {todo.text}")
                return page_id

        except (AuthenticationError, RateLimitError, ValidationError):
            raise
        except Exception as e:
            self.logger.error(f"Failed to create Notion page: {e}")
            raise NetworkError(f"Failed to create in Notion: {e}")

    async def update_item(self, external_id: str, todo: Todo) -> bool:
        """Update an existing Notion page from a Todo."""
        await self.ensure_authenticated()

        try:
            async with NotionAPI(self.notion_token) as api:
                properties = self.map_todo_to_external(todo)
                await api.update_page(external_id, properties)
                self.log_sync_operation("update", f"Updated page {external_id}: {todo.text}")
                return True

        except (AuthenticationError, RateLimitError, ValidationError):
            raise
        except Exception as e:
            self.logger.error(f"Failed to update Notion page {external_id}: {e}")
            raise NetworkError(f"Failed to update in Notion: {e}")

    async def delete_item(self, external_id: str) -> bool:
        """Archive a Notion page (Notion does not support true deletion via API)."""
        await self.ensure_authenticated()

        try:
            async with NotionAPI(self.notion_token) as api:
                await api.archive_page(external_id)
                self.log_sync_operation("delete", f"Archived page {external_id}")
                return True

        except (AuthenticationError, RateLimitError, ValidationError):
            raise
        except Exception as e:
            self.logger.error(f"Failed to archive Notion page {external_id}: {e}")
            return False

    async def fetch_projects(self) -> Dict[str, str]:
        """Fetch databases accessible by the integration as projects."""
        await self.ensure_authenticated()

        try:
            async with NotionAPI(self.notion_token) as api:
                result = await api.search_databases()
                databases = result.get("results", [])
                project_map: Dict[str, str] = {}
                for db in databases:
                    title_parts = db.get("title", [])
                    name = "".join(
                        part.get("plain_text", "") for part in title_parts
                    ) or db["id"]
                    project_map[name] = db["id"]
                return project_map
        except Exception as e:
            self.logger.error(f"Failed to fetch Notion databases: {e}")
            return {}

    # ------------------------------------------------------------------
    # Property helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_title(properties: Dict[str, Any]) -> str:
        """Extract title text from Notion page properties."""
        for key in ("Name", "Title", "name", "title"):
            prop = properties.get(key)
            if prop and prop.get("type") == "title":
                parts = prop.get("title", [])
                return "".join(part.get("plain_text", "") for part in parts)
        # Fallback: find any title-type property
        for prop in properties.values():
            if isinstance(prop, dict) and prop.get("type") == "title":
                parts = prop.get("title", [])
                return "".join(part.get("plain_text", "") for part in parts)
        return ""

    @staticmethod
    def _extract_rich_text(properties: Dict[str, Any], *keys: str) -> str:
        """Extract plain text from a rich_text property."""
        for key in keys:
            prop = properties.get(key)
            if prop and prop.get("type") == "rich_text":
                parts = prop.get("rich_text", [])
                return "".join(part.get("plain_text", "") for part in parts)
        return ""

    @staticmethod
    def _extract_select(properties: Dict[str, Any], key: str) -> Optional[str]:
        """Extract the name of a select or status property."""
        prop = properties.get(key)
        if not prop:
            return None
        ptype = prop.get("type")
        if ptype in ("select", "status"):
            inner = prop.get(ptype)
            if inner:
                return inner.get("name")
        return None

    @staticmethod
    def _extract_multi_select(properties: Dict[str, Any], key: str) -> List[str]:
        """Extract names from a multi_select property."""
        prop = properties.get(key)
        if prop and prop.get("type") == "multi_select":
            return [opt["name"] for opt in prop.get("multi_select", []) if "name" in opt]
        return []

    @staticmethod
    def _extract_date(properties: Dict[str, Any], key: str) -> Optional[datetime]:
        """Extract a datetime from a date property."""
        prop = properties.get(key)
        if prop and prop.get("type") == "date":
            date_obj = prop.get("date")
            if date_obj and date_obj.get("start"):
                date_str = date_obj["start"]
                try:
                    if "T" in date_str:
                        parsed = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                    else:
                        parsed = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
                    return ensure_aware(parsed)
                except Exception:
                    pass
        return None

    @staticmethod
    def _extract_people(properties: Dict[str, Any], key: str) -> List[str]:
        """Extract names/emails from a people property, falling back to rich_text."""
        prop = properties.get(key)
        if not prop:
            return []
        ptype = prop.get("type")
        if ptype == "people":
            names = []
            for person in prop.get("people", []):
                name = person.get("name") or person.get("id", "")
                names.append(name)
            return names
        elif ptype == "rich_text":
            text = "".join(p.get("plain_text", "") for p in prop.get("rich_text", []))
            if text:
                return [t.strip() for t in text.split(",") if t.strip()]
        return []

    # ------------------------------------------------------------------
    # Mapping
    # ------------------------------------------------------------------

    def map_todo_to_external(self, todo: Todo) -> Dict[str, Any]:
        """Map a local Todo to Notion page properties."""
        properties: Dict[str, Any] = {
            "Name": {
                "title": [{"text": {"content": todo.text}}],
            },
        }

        # Description / Notes
        desc = todo.description or ""
        if desc:
            properties["Description"] = {
                "rich_text": [{"text": {"content": desc}}],
            }

        # Status
        status_name = "Done" if todo.completed else "In Progress" if todo.status == TodoStatus.IN_PROGRESS else "Not Started"
        properties["Status"] = {
            "status": {"name": status_name},
        }

        # Priority
        if todo.priority:
            pri_int = PRIORITY_ENUM_TO_INT.get(todo.priority, 2)
            pri_name = PRIORITY_INT_TO_NAME.get(pri_int, "medium")
            properties["Priority"] = {
                "select": {"name": pri_name.capitalize()},
            }

        # Tags
        if todo.tags:
            properties["Tags"] = {
                "multi_select": [{"name": tag} for tag in todo.tags],
            }

        # Due Date
        if todo.due_date:
            properties["Due Date"] = {
                "date": {"start": todo.due_date.isoformat()},
            }

        # Assignees (as rich_text since we can't create people references)
        if todo.assignees:
            properties["Assignee"] = {
                "rich_text": [{"text": {"content": ", ".join(todo.assignees)}}],
            }

        # Project
        if todo.project and todo.project not in ("inbox", "default"):
            properties["Project"] = {
                "select": {"name": todo.project},
            }

        return properties

    def map_external_to_todo(self, external_data: Dict[str, Any]) -> ExternalTodoItem:
        """Map a Notion page to ExternalTodoItem."""
        page = external_data
        props = page.get("properties", {})

        title = self._extract_title(props)
        description = self._extract_rich_text(props, "Description", "Notes", "description", "notes")

        # Status
        status_name = self._extract_select(props, "Status") or ""
        completed = status_name.lower() in COMPLETED_STATUSES

        # Priority
        priority_name = self._extract_select(props, "Priority") or ""
        priority_int = PRIORITY_NAME_MAP.get(priority_name.lower())

        # Tags
        tags = self._extract_multi_select(props, "Tags")

        # Due date
        due_date = self._extract_date(props, "Due Date")

        # Assignees
        assignees = self._extract_people(props, "Assignee")
        assignee_str: Optional[str] = ", ".join(assignees) if assignees else None

        # Project
        project = self._extract_select(props, "Project")

        # Timestamps
        created_at: Optional[datetime] = None
        if page.get("created_time"):
            try:
                created_at = ensure_aware(
                    datetime.fromisoformat(page["created_time"].replace("Z", "+00:00"))
                )
            except Exception:
                created_at = now_utc()
        else:
            created_at = now_utc()

        updated_at: Optional[datetime] = None
        if page.get("last_edited_time"):
            try:
                updated_at = ensure_aware(
                    datetime.fromisoformat(page["last_edited_time"].replace("Z", "+00:00"))
                )
            except Exception:
                updated_at = created_at
        else:
            updated_at = created_at

        return ExternalTodoItem(
            external_id=page["id"],
            provider=AppSyncProvider.NOTION,
            title=title,
            description=description,
            due_date=due_date,
            priority=priority_int,
            tags=tags,
            project=project,
            completed=completed,
            created_at=created_at,
            updated_at=updated_at,
            assignee=assignee_str,
            url=page.get("url"),
            raw_data=page,
        )
