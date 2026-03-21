"""Evernote adapter for app synchronization.

This module provides integration with the Evernote API for bidirectional
synchronization of todo items using notes as tasks.
"""

import httpx
import logging
import re
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


class EvernoteAPI:
    """Evernote API v1 client."""

    BASE_URL = "https://api.evernote.com/"

    def __init__(self, token: str):
        """Initialize Evernote API client.

        Args:
            token: Evernote OAuth token
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
        """Make HTTP request to Evernote API.

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
                raise AuthenticationError("Invalid Evernote token")
            elif response.status_code == 403:
                raise AuthenticationError("Evernote API access forbidden")
            elif response.status_code == 404:
                raise NetworkError(f"Evernote resource not found: {endpoint}")
            elif response.status_code == 422:
                raise ValidationError(f"Evernote validation error: {response.text}")
            elif response.status_code == 429:
                raise RateLimitError("Evernote API rate limit exceeded")
            elif response.status_code >= 400:
                raise NetworkError(f"Evernote API error {response.status_code}: {response.text}")

            if response.status_code == 204:
                return {}

            return response.json()

        except httpx.TimeoutException:
            raise NetworkError("Evernote API request timed out")
        except httpx.RequestError as e:
            raise NetworkError(f"Evernote API request failed: {e}")

    # --- Authentication ---

    async def get_user(self) -> Dict[str, Any]:
        """Get authenticated user information."""
        return await self._make_request("GET", "users/me")

    # --- Notebooks ---

    async def get_notebooks(self) -> List[Dict[str, Any]]:
        """Get all notebooks for the authenticated user."""
        return await self._make_request("GET", "notebooks")

    # --- Notes ---

    async def find_notes(
        self,
        notebook_guid: Optional[str] = None,
        filter: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Find notes, optionally filtered by notebook.

        Args:
            notebook_guid: Optional notebook GUID to filter by
            filter: Optional additional filter parameters

        Returns:
            Dictionary with 'notes' key containing list of note objects
        """
        params: Dict[str, Any] = {}
        if notebook_guid:
            params["notebookGuid"] = notebook_guid
        if filter:
            params.update(filter)
        return await self._make_request("GET", "notes", params=params)

    async def get_note(self, note_guid: str) -> Dict[str, Any]:
        """Get a specific note by GUID.

        Args:
            note_guid: The note GUID

        Returns:
            Note object
        """
        return await self._make_request("GET", f"notes/{note_guid}")

    async def create_note(
        self,
        notebook_guid: str,
        data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Create a new note in a notebook.

        Args:
            notebook_guid: The notebook GUID
            data: Note data (title, content, tags, etc.)

        Returns:
            Created note object
        """
        payload = {**data, "notebookGuid": notebook_guid}
        return await self._make_request("POST", "notes", data=payload)

    async def update_note(
        self,
        note_guid: str,
        data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Update an existing note.

        Args:
            note_guid: The note GUID
            data: Updated note data

        Returns:
            Updated note object
        """
        return await self._make_request("PUT", f"notes/{note_guid}", data=data)

    async def delete_note(self, note_guid: str) -> Dict[str, Any]:
        """Delete a note.

        Args:
            note_guid: The note GUID

        Returns:
            Empty dict on success
        """
        return await self._make_request("DELETE", f"notes/{note_guid}")


class EvernoteAdapter(SyncAdapter):
    """Evernote adapter for app synchronization."""

    def __init__(self, config: AppSyncConfig):
        """Initialize Evernote adapter.

        Args:
            config: App sync configuration
        """
        super().__init__(config)
        self.evernote_token = config.get_credential("evernote_token")
        self.notebook_guid: str = config.get_setting("evernote_notebook_guid", "")
        self.api: Optional[EvernoteAPI] = None

    def get_required_credentials(self) -> List[str]:
        return ["evernote_token"]

    def get_supported_features(self) -> List[str]:
        return [
            "create", "read", "update", "delete",
            "projects", "tags", "due_dates",
            "descriptions",
        ]

    # ------------------------------------------------------------------
    # Authentication
    # ------------------------------------------------------------------

    async def authenticate(self) -> bool:
        """Authenticate with Evernote API using the OAuth token."""
        if not self.evernote_token:
            raise AuthenticationError("No Evernote token provided")

        try:
            async with EvernoteAPI(self.evernote_token) as api:
                user_info = await api.get_user()
                if user_info and user_info.get("username"):
                    self.logger.info(
                        f"Authenticated with Evernote as {user_info['username']}"
                    )
                    return True
                return False
        except AuthenticationError:
            self.logger.error("Evernote authentication failed - invalid token")
            raise
        except Exception as e:
            self.logger.error(f"Evernote authentication failed: {e}")
            raise AuthenticationError(f"Failed to authenticate with Evernote: {e}")

    async def test_connection(self) -> bool:
        """Test connection to Evernote API."""
        try:
            return await self.authenticate()
        except Exception:
            return False

    # ------------------------------------------------------------------
    # CRUD operations
    # ------------------------------------------------------------------

    async def fetch_items(self, since: Optional[datetime] = None) -> List[ExternalTodoItem]:
        """Fetch notes from Evernote as todo items."""
        await self.ensure_authenticated()

        try:
            async with EvernoteAPI(self.evernote_token) as api:
                filter_params = None
                if since:
                    filter_params = {"updatedAfter": since.isoformat()}

                result = await api.find_notes(
                    notebook_guid=self.notebook_guid or None,
                    filter=filter_params,
                )
                notes = result.get("notes", [])

                external_items: List[ExternalTodoItem] = []
                for note in notes:
                    try:
                        item = self.map_external_to_todo(note)
                        external_items.append(item)
                    except Exception as e:
                        self.logger.warning(
                            f"Failed to map Evernote note {note.get('guid')}: {e}"
                        )

                self.logger.info(f"Fetched {len(external_items)} notes from Evernote")
                return external_items

        except (AuthenticationError, RateLimitError, ValidationError):
            raise
        except Exception as e:
            self.logger.error(f"Failed to fetch Evernote notes: {e}")
            raise NetworkError(f"Failed to fetch from Evernote: {e}")

    async def create_item(self, todo: Todo) -> str:
        """Create a new note in Evernote from a Todo."""
        await self.ensure_authenticated()

        try:
            async with EvernoteAPI(self.evernote_token) as api:
                payload = self.map_todo_to_external(todo)
                notebook = self.notebook_guid or payload.pop("notebookGuid", "default")
                created = await api.create_note(notebook, payload)
                note_guid = created["guid"]
                self.log_sync_operation("create", f"Created note {note_guid}: {todo.text}")
                return note_guid

        except (AuthenticationError, RateLimitError, ValidationError):
            raise
        except Exception as e:
            self.logger.error(f"Failed to create Evernote note: {e}")
            raise NetworkError(f"Failed to create in Evernote: {e}")

    async def update_item(self, external_id: str, todo: Todo) -> bool:
        """Update an existing Evernote note from a Todo."""
        await self.ensure_authenticated()

        try:
            async with EvernoteAPI(self.evernote_token) as api:
                payload = self.map_todo_to_external(todo)
                await api.update_note(external_id, payload)
                self.log_sync_operation("update", f"Updated note {external_id}: {todo.text}")
                return True

        except (AuthenticationError, RateLimitError, ValidationError):
            raise
        except Exception as e:
            self.logger.error(f"Failed to update Evernote note {external_id}: {e}")
            raise NetworkError(f"Failed to update in Evernote: {e}")

    async def delete_item(self, external_id: str) -> bool:
        """Delete an Evernote note."""
        await self.ensure_authenticated()

        try:
            async with EvernoteAPI(self.evernote_token) as api:
                await api.delete_note(external_id)
                self.log_sync_operation("delete", f"Deleted note {external_id}")
                return True

        except (AuthenticationError, RateLimitError, ValidationError):
            raise
        except Exception as e:
            self.logger.error(f"Failed to delete Evernote note {external_id}: {e}")
            return False

    async def fetch_projects(self) -> Dict[str, str]:
        """Fetch notebooks as projects."""
        await self.ensure_authenticated()

        try:
            async with EvernoteAPI(self.evernote_token) as api:
                notebooks = await api.get_notebooks()
                project_map: Dict[str, str] = {}
                for nb in notebooks:
                    name = nb.get("name", nb.get("guid", ""))
                    guid = nb.get("guid", "")
                    if name and guid:
                        project_map[name] = guid
                return project_map
        except Exception as e:
            self.logger.error(f"Failed to fetch Evernote notebooks: {e}")
            return {}

    # ------------------------------------------------------------------
    # Field mapping
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_plain_text(content: str) -> str:
        """Extract plain text from Evernote ENML content."""
        if not content:
            return ""
        # Strip XML/HTML tags
        text = re.sub(r"<[^>]+>", "", content)
        # Decode common entities
        text = text.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
        text = text.replace("&nbsp;", " ").replace("&quot;", '"')
        return text.strip()

    def map_todo_to_external(self, todo: Todo) -> Dict[str, Any]:
        """Map a local Todo to Evernote note creation/update payload."""
        payload: Dict[str, Any] = {
            "title": todo.text,
        }

        # Description -> content
        if todo.description:
            payload["content"] = todo.description

        # Tags
        if todo.tags:
            payload["tagNames"] = list(todo.tags)

        # Due date -> reminderTime
        if todo.due_date:
            payload["reminderTime"] = todo.due_date.isoformat()

        # Completed -> reminderDoneTime
        if todo.completed:
            payload["reminderDoneTime"] = (
                todo.completed_date.isoformat()
                if todo.completed_date
                else now_utc().isoformat()
            )

        # Project -> notebook mapping
        if todo.project and todo.project != "inbox":
            mapped = self.apply_project_mapping(todo.project)
            if mapped:
                payload["notebookGuid"] = mapped

        return payload

    def map_external_to_todo(self, external_data: Dict[str, Any]) -> ExternalTodoItem:
        """Map Evernote note data to ExternalTodoItem."""
        note = external_data

        title = note.get("title", "")
        content_raw = note.get("content", "")
        description = self._extract_plain_text(content_raw)

        # Tags
        tags: List[str] = []
        for tag in note.get("tagNames", note.get("tags", [])):
            if isinstance(tag, str):
                tags.append(tag)
            elif isinstance(tag, dict):
                tags.append(tag.get("name", ""))

        # Notebook -> project
        project: Optional[str] = None
        notebook_guid = note.get("notebookGuid")
        if notebook_guid:
            project = self.apply_reverse_project_mapping(notebook_guid)

        # Reminder -> due_date
        due_date: Optional[datetime] = None
        if note.get("reminderTime"):
            try:
                due_date = ensure_aware(
                    datetime.fromisoformat(
                        str(note["reminderTime"]).replace("Z", "+00:00")
                    )
                )
            except Exception:
                pass

        # Completed: reminderDoneTime is set
        completed = bool(note.get("reminderDoneTime"))
        completed_at: Optional[datetime] = None
        if completed and note.get("reminderDoneTime"):
            try:
                completed_at = ensure_aware(
                    datetime.fromisoformat(
                        str(note["reminderDoneTime"]).replace("Z", "+00:00")
                    )
                )
            except Exception:
                pass

        # Timestamps
        created_at: Optional[datetime] = None
        if note.get("created"):
            try:
                created_at = ensure_aware(
                    datetime.fromisoformat(
                        str(note["created"]).replace("Z", "+00:00")
                    )
                )
            except Exception:
                created_at = now_utc()
        else:
            created_at = now_utc()

        updated_at: Optional[datetime] = None
        if note.get("updated"):
            try:
                updated_at = ensure_aware(
                    datetime.fromisoformat(
                        str(note["updated"]).replace("Z", "+00:00")
                    )
                )
            except Exception:
                updated_at = created_at
        else:
            updated_at = created_at

        return ExternalTodoItem(
            external_id=note.get("guid", ""),
            provider=AppSyncProvider.EVERNOTE,
            title=title,
            description=description,
            tags=tags,
            project=project,
            due_date=due_date,
            completed=completed,
            completed_at=completed_at,
            created_at=created_at,
            updated_at=updated_at,
            url=note.get("webApiUrlPrefix", ""),
            raw_data=note,
        )
