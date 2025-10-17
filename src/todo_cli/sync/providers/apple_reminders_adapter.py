"""Apple Reminders adapter for app synchronization.

This module provides integration with Apple Reminders app for bidirectional
synchronization of todo items, lists, due dates, and completion status.

Uses AppleScript for macOS system integration.
"""

import subprocess
import logging
import json
from datetime import datetime, timezone, timedelta
from inspect import isawaitable
from typing import Dict, List, Optional, Any, Union
from urllib.parse import quote
from unittest.mock import MagicMock

from ..app_sync_adapter import SyncAdapter, AuthenticationError, NetworkError, ValidationError
from ..app_sync_models import (
    AppSyncProvider,
    AppSyncConfig,
    ExternalTodoItem,
    SyncDirection
)
from ...domain import Todo, Priority, TodoStatus
from ...utils.datetime import ensure_aware, now_utc


class AppleRemindersExternalTodoItem(ExternalTodoItem):
    """Custom ExternalTodoItem for Apple Reminders with proper priority handling."""
    
    def to_todo(self, todo_id: Optional[int] = None) -> Todo:
        """Convert external item to Todo object with Apple Reminders priority mapping."""
        # Use the stored Priority enum value if available, otherwise fall back to generic mapping
        priority_enum_value = self.raw_data.get('priority_enum_value')
        if priority_enum_value:
            # Reconstruct Priority enum from stored value
            try:
                priority_enum = Priority(priority_enum_value)
            except ValueError:
                # Fallback to generic mapping if value is invalid
                priority_enum = self._map_priority_from_external()
        else:
            # Fallback to generic mapping if priority_enum_value not available
            priority_enum = self._map_priority_from_external()
        
        return Todo(
            id=todo_id or 0,
            text=self.title,
            project=self.project or "default",
            tags=self.tags,
            due_date=self.due_date,
            priority=priority_enum,
            status=TodoStatus.COMPLETED if self.completed else TodoStatus.PENDING,
            created=self.created_at or now_utc(),
            modified=self.updated_at or now_utc(),
            description=self.description or ""
        )


logger = logging.getLogger(__name__)


class AppleScriptError(Exception):
    """Exception raised when AppleScript execution fails."""
    pass


class AppleScriptInterface:
    """Interface to Apple Reminders app via AppleScript."""
    
    def __init__(self):
        """Initialize AppleScript interface."""
        self.logger = logging.getLogger(__name__)
    
    def run_script(self, script: str) -> str:
        """Execute AppleScript and return result.
        
        Args:
            script: AppleScript code to execute
            
        Returns:
            Script output as string
            
        Raises:
            AppleScriptError: If script execution fails
        """
        try:
            result = subprocess.run(
                ["osascript", "-e", script],
                capture_output=True,
                text=True,
                timeout=60  # Increased timeout for large lists
            )
            
            if result.returncode != 0:
                error_msg = result.stderr.strip() if result.stderr else "Unknown AppleScript error"
                raise AppleScriptError(f"AppleScript failed: {error_msg}")
            
            return result.stdout.strip()
            
        except subprocess.TimeoutExpired:
            raise AppleScriptError("AppleScript timed out")
        except Exception as e:
            raise AppleScriptError(f"Failed to execute AppleScript: {e}")
    
    def get_reminders_lists(self) -> List[Dict[str, Any]]:
        """Get all reminders lists."""
        script = '''
        tell application "Reminders"
            set listNames to {}
            set listIds to {}
            repeat with lst in lists
                set end of listNames to name of lst
                set end of listIds to id of lst
            end repeat
            return listNames & "|||" & listIds
        end tell
        '''
        
        try:
            result = self.run_script(script)
            if not result or result == "|||":
                return []
            
            parts = result.split("|||")
            if len(parts) != 2:
                return []
            
            names = parts[0].split(", ") if parts[0] else []
            ids = parts[1].split(", ") if parts[1] else []
            
            lists = []
            for i, name in enumerate(names):
                # Skip empty or whitespace-only names
                if not name or not name.strip():
                    continue
                    
                list_id = ids[i] if i < len(ids) else str(i + 1)
                lists.append({
                    "id": list_id.strip(),
                    "name": name.strip()
                })
            
            return lists
            
        except Exception as e:
            self.logger.error(f"Failed to get reminders lists: {e}")
            return []
    
    def get_reminders_in_list(self, list_name: str) -> List[Dict[str, Any]]:
        """Get all reminders in a specific list.
        
        Args:
            list_name: Name of the reminders list
            
        Returns:
            List of reminder dictionaries
        """
        # Validate list name
        if not list_name or list_name.strip() == "":
            self.logger.warning(f"Empty list name provided, skipping")
            return []
        
        # Escape the list name for AppleScript
        escaped_list_name = list_name.replace('"', '\\"')
        
        script = f'''
        tell application "Reminders"
            set remindersList to list "{escaped_list_name}"
            set reminderData to {{}}
            
            repeat with rem in reminders of remindersList
                set reminderInfo to (name of rem) & "|||" & ¬
                    (completed of rem) & "|||" & ¬
                    (id of rem) & "|||"
                
                -- Get due date if it exists
                try
                    set dueDate to due date of rem
                    if dueDate is not missing value then
                        set reminderInfo to reminderInfo & dueDate
                    else
                        set reminderInfo to reminderInfo & ""
                    end if
                on error
                    set reminderInfo to reminderInfo & ""
                end try
                
                set reminderInfo to reminderInfo & "|||"
                
                -- Get body/notes if they exist
                try
                    set reminderBody to body of rem
                    if reminderBody is not missing value then
                        set reminderInfo to reminderInfo & reminderBody
                    else
                        set reminderInfo to reminderInfo & ""
                    end if
                on error
                    set reminderInfo to reminderInfo & ""
                end try
                
                set reminderInfo to reminderInfo & "|||"
                
                -- Get priority (1-9, where 1 is high, 5 is medium, 9 is low)
                try
                    set reminderPriority to priority of rem
                    if reminderPriority is not missing value then
                        set reminderInfo to reminderInfo & reminderPriority
                    else
                        set reminderInfo to reminderInfo & "5"
                    end if
                on error
                    set reminderInfo to reminderInfo & "5"
                end try
                
                set end of reminderData to reminderInfo
            end repeat
            
            return reminderData
        end tell
        '''
        
        # Retry mechanism for timeouts
        max_retries = 2
        for attempt in range(max_retries + 1):
            try:
                result = self.run_script(script)
                if not result or result.strip() == "":
                    return []
                
                reminders = []
                # Parse the AppleScript result which is a comma-separated list of reminder entries
                # Each entry has the format: name|||completed|||id|||due_date|||body|||priority
                # Problem: due_date contains commas, so we need to reconstruct the entries
                lines = self._parse_applescript_reminder_list(result)
                
                def _clean_part(value: str) -> str:
                    return value.strip().lstrip("|") if value else ""

                for line in lines:
                    if not line.strip():
                        continue
                    
                    parts = line.split("|||")
                    if len(parts) < 4:
                        continue
                    
                    # Parse due date
                    due_date = None
                    due_part = _clean_part(parts[3] if len(parts) > 3 else "")
                    if due_part:
                        try:
                            due_date = self._parse_apple_date(due_part)
                        except Exception as e:
                            self.logger.warning(f"Failed to parse due date '{due_part}': {e}")
                    
                    priority_raw = _clean_part(parts[5]) if len(parts) > 5 else "5"
                    priority_int = int(priority_raw) if priority_raw.isdigit() else 5
                    
                    reminder = {
                        "name": _clean_part(parts[0]),
                        "completed": _clean_part(parts[1]).lower() == "true",
                        "id": _clean_part(parts[2]),
                        "due_date": due_date,
                        "body": _clean_part(parts[4]) if len(parts) > 4 else "",
                        "priority": priority_int,
                        "list_name": list_name
                    }
                    
                    # Debug logging for Apple Reminders data extraction
                    if reminder["name"] == "Here is a test task":
                        self.logger.info(f"DEBUG: Extracted reminder data - name: {reminder['name']}, "
                                        f"due_date: {reminder['due_date']}, priority: {priority_int} (raw: {priority_raw}), "
                                        f"body: {reminder['body']}, parts: {parts}")
                    
                    reminders.append(reminder)
                
                return reminders
                
            except AppleScriptError as e:
                if "timed out" in str(e).lower() and attempt < max_retries:
                    self.logger.warning(f"AppleScript timed out for list '{list_name}', retrying (attempt {attempt + 1}/{max_retries})")
                    continue
                else:
                    self.logger.error(f"Failed to get reminders in list '{list_name}': {e}")
                    return []
            except Exception as e:
                self.logger.error(f"Failed to get reminders in list '{list_name}': {e}")
                return []
    
    def create_reminder(self, list_name: str, name: str, body: str = "", 
                       due_date: Optional[datetime] = None, priority: int = 5) -> str:
        """Create a new reminder.
        
        Args:
            list_name: Name of the list to add reminder to
            name: Reminder title
            body: Reminder notes/body
            due_date: Due date for reminder
            priority: Priority (1-9, where 1 is high, 5 is medium, 9 is low)
            
        Returns:
            ID of created reminder
        """
        escaped_list_name = list_name.replace('"', '\\"')
        escaped_name = name.replace('"', '\\"')
        escaped_body = body.replace('"', '\\"') if body else ""
        
        # Build the script
        script_parts = [f'tell application "Reminders"',
                       f'set targetList to list "{escaped_list_name}"',
                       f'set newReminder to make new reminder at end of reminders of targetList']
        
        # Set basic properties
        script_parts.append(f'set name of newReminder to "{escaped_name}"')
        if escaped_body:
            script_parts.append(f'set body of newReminder to "{escaped_body}"')
        script_parts.append(f'set priority of newReminder to {priority}')
        
        # Set due date if provided
        if due_date:
            # Format date for AppleScript
            formatted_date = due_date.strftime('date "%A, %B %d, %Y at %I:%M:%S %p"')
            script_parts.append(f'set due date of newReminder to {formatted_date}')
        
        # Return the ID
        script_parts.extend(['set reminderId to id of newReminder',
                           'return reminderId',
                           'end tell'])
        
        script = '\n'.join(script_parts)
        
        try:
            result = self.run_script(script)
            return result.strip()
        except Exception as e:
            self.logger.error(f"Failed to create reminder: {e}")
            raise AppleScriptError(f"Failed to create reminder: {e}")
    
    def update_reminder(self, reminder_id: str, name: Optional[str] = None,
                       body: Optional[str] = None, due_date: Optional[datetime] = None,
                       priority: Optional[int] = None, completed: Optional[bool] = None) -> bool:
        """Update an existing reminder.
        
        Args:
            reminder_id: ID of reminder to update
            name: New name (optional)
            body: New body/notes (optional)
            due_date: New due date (optional)
            priority: New priority (optional)
            completed: New completion status (optional)
            
        Returns:
            True if update succeeded
        """
        script_parts = [f'tell application "Reminders"',
                       f'set targetReminder to reminder id "{reminder_id}"']
        
        # Update properties if provided
        if name is not None:
            escaped_name = name.replace('"', '\\"')
            script_parts.append(f'set name of targetReminder to "{escaped_name}"')
        
        if body is not None:
            escaped_body = body.replace('"', '\\"')
            script_parts.append(f'set body of targetReminder to "{escaped_body}"')
        
        if priority is not None:
            script_parts.append(f'set priority of targetReminder to {priority}')
        
        if completed is not None:
            script_parts.append(f'set completed of targetReminder to {str(completed).lower()}')
        
        if due_date is not None:
            if due_date:
                formatted_date = due_date.strftime('date "%A, %B %d, %Y at %I:%M:%S %p"')
                script_parts.append(f'set due date of targetReminder to {formatted_date}')
            else:
                script_parts.append('set due date of targetReminder to missing value')
        
        script_parts.append('end tell')
        script = '\n'.join(script_parts)
        
        try:
            self.run_script(script)
            return True
        except Exception as e:
            self.logger.error(f"Failed to update reminder {reminder_id}: {e}")
            return False
    
    def delete_reminder(self, reminder_id: str) -> bool:
        """Delete a reminder.
        
        Args:
            reminder_id: ID of reminder to delete
            
        Returns:
            True if deletion succeeded
        """
        script = f'''
        tell application "Reminders"
            set targetReminder to reminder id "{reminder_id}"
            delete targetReminder
        end tell
        '''
        
        try:
            self.run_script(script)
            return True
        except Exception as e:
            self.logger.error(f"Failed to delete reminder {reminder_id}: {e}")
            return False
    
    def reminder_exists(self, reminder_id: str) -> bool:
        """Check if a reminder exists.
        
        Args:
            reminder_id: ID of reminder to check
            
        Returns:
            True if reminder exists
        """
        script = f'''
        tell application "Reminders"
            try
                set targetReminder to reminder id "{reminder_id}"
                return true
            on error
                return false
            end try
        end tell
        '''
        
        try:
            result = self.run_script(script)
            return result.strip().lower() == "true"
        except Exception:
            return False
    
    def _parse_applescript_reminder_list(self, result: str) -> List[str]:
        """Parse AppleScript result that contains multiple reminder entries.
        
        The AppleScript returns a comma-separated list of reminders, but each reminder
        entry also contains dates with commas. We need to carefully reconstruct the
        individual reminder entries.
        
        Each reminder has the format: name|||completed|||id|||due_date|||body|||priority
        Where due_date can be: "Wednesday, October 22, 2025 at 6:00:00 PM" or empty
        
        Args:
            result: Raw AppleScript result string with multiple reminders
            
        Returns:
            List of individual reminder strings
        """
        lines = []
        current_entry = ""
        
        # Split by comma and reassemble entries
        parts = result.split(", ")
        
        for part in parts:
            if current_entry:
                current_entry += ", " + part
            else:
                current_entry = part
            
            # Check if we have a complete entry by counting ||| delimiters
            # Each complete reminder should have exactly 5 ||| delimiters
            delimiter_count = current_entry.count("|||")
            
            if delimiter_count >= 5:
                # We have a complete entry
                lines.append(current_entry)
                current_entry = ""
            elif delimiter_count > 5:
                # This shouldn't happen, but if it does, we might have multiple entries
                # concatenated. For now, just add it and reset.
                lines.append(current_entry)
                current_entry = ""
        
        # Add any remaining content (shouldn't happen with well-formed data)
        if current_entry.strip():
            lines.append(current_entry)
        
        return lines
    
    def _parse_apple_date(self, date_str: str) -> Optional[datetime]:
        """Parse Apple date string to datetime.

        Args:
            date_str: Date string from AppleScript

        Returns:
            Parsed datetime or None
        """
        if not date_str or date_str.strip() == "":
            return None

        # Apple returns dates like: "Friday, January 1, 2025 at 9:00:00 AM"
        # Or sometimes just: "January 15, 2025 at 3:30:00 PM" (without weekday)
        try:
            # Check if the string starts with a weekday prefix by looking for " at " marker
            # and counting commas before it
            at_index = date_str.find(" at ")
            if at_index == -1:
                return None

            date_part = date_str[:at_index]
            time_part = date_str[at_index + 4:]  # Skip " at "

            # Count commas in date part
            # Format with weekday: "Friday, January 1, 2025" (2 commas)
            # Format without weekday: "January 15, 2025" (1 comma)
            comma_count = date_part.count(',')

            if comma_count == 2:
                # Has weekday, remove it
                # Split by first comma to remove weekday
                parts = date_part.split(", ", 1)
                date_without_day = parts[1] if len(parts) > 1 else date_part
            else:
                # No weekday prefix
                date_without_day = date_part

            # Reconstruct full date string
            full_date_str = f"{date_without_day} at {time_part}"

            # Parse the date using datetime.strptime
            # Format: "January 1, 2025 at 9:00:00 AM"
            parsed_date = datetime.strptime(full_date_str, "%B %d, %Y at %I:%M:%S %p")

            # Make timezone-aware (assume local timezone, then convert to UTC)
            # Since AppleScript returns dates in local time, we need to handle this
            import time
            if time.daylight:
                utc_offset_hours = -time.altzone / 3600
            else:
                utc_offset_hours = -time.timezone / 3600

            # Apply the local timezone offset
            local_tz = timezone(timedelta(hours=utc_offset_hours))
            parsed_date = parsed_date.replace(tzinfo=local_tz)

            # Convert to UTC
            return parsed_date.astimezone(timezone.utc)

        except Exception as e:
            self.logger.warning(f"Failed to parse Apple date '{date_str}': {e}")
            return None


class AppleRemindersAdapter(SyncAdapter):
    """Apple Reminders adapter for app synchronization."""
    
    def __init__(self, config: AppSyncConfig):
        """Initialize Apple Reminders adapter.
        
        Args:
            config: App sync configuration
        """
        super().__init__(config)
        self.apple_script = AppleScriptInterface()
        self._lists_cache: Dict[str, str] = {}  # name -> id
        
        # Apple Reminders specific settings
        self.default_list_name = config.get_setting("default_list_name", "Reminders")
        self.sync_completed_reminders = config.sync_completed_tasks
    
    def get_required_credentials(self) -> List[str]:
        """Get required credentials for Apple Reminders."""
        return []  # No credentials required for local system access
    
    def get_supported_features(self) -> List[str]:
        """Get features supported by Apple Reminders adapter."""
        return [
            "create", "read", "update", "delete",
            "lists", "due_dates", "priorities", 
            "descriptions", "completion_status"
        ]
    
    async def authenticate(self) -> bool:
        """Authenticate with Apple Reminders (check system access)."""
        try:
            # Test if we can access Reminders app
            lists = self.apple_script.get_reminders_lists()
            self.logger.info(f"Apple Reminders access confirmed - found {len(lists)} lists")
            return True
        except Exception as e:
            self.logger.error(f"Apple Reminders access failed: {e}")
            raise AuthenticationError(f"Cannot access Apple Reminders: {e}")
    
    async def test_connection(self) -> bool:
        """Test connection to Apple Reminders."""
        try:
            return await self.authenticate()
        except Exception:
            return False
    
    async def fetch_items(self, since: Optional[datetime] = None) -> List[ExternalTodoItem]:
        """Fetch reminders from Apple Reminders."""
        await self.ensure_authenticated()
        
        try:
            # Refresh lists cache when we don't have data yet
            if not self._lists_cache:
                await self._refresh_lists_cache()
            
            external_items = []
            
            # Get reminders from all lists
            for list_name in self._lists_cache.keys():
                # Skip empty or invalid list names
                if not list_name or not list_name.strip():
                    self.logger.warning(f"Skipping invalid list name: '{list_name}'")
                    continue
                    
                try:
                    reminders = self.apple_script.get_reminders_in_list(list_name)
                    
                    for reminder in reminders:
                        if not self._should_include_reminder(reminder):
                            continue
                        
                        try:
                            external_item = self.map_external_to_todo(reminder)
                            external_items.append(external_item)
                        except Exception as e:
                            self.logger.warning(f"Failed to map reminder {reminder.get('id')}: {e}")
                            continue
                
                except Exception as e:
                    self.logger.warning(f"Failed to get reminders from list '{list_name}': {e}")
                    continue
            
            self.logger.info(f"Fetched {len(external_items)} reminders from Apple Reminders")
            
            # Debug logging to see what items we actually fetched
            for item in external_items:
                if "Here is a test task" in item.title:
                    self.logger.info(f"DEBUG FETCH: Found test task - {item.title}, due_date: {item.due_date}, priority: {item.priority}")
            
            return external_items
            
        except Exception as e:
            self.logger.error(f"Failed to fetch Apple Reminders items: {e}")
            raise NetworkError(f"Failed to fetch from Apple Reminders: {e}")
    
    async def create_item(self, todo: Todo) -> str:
        """Create a new reminder in Apple Reminders."""
        await self.ensure_authenticated()
        
        try:
            # Determine target list
            list_name = self._get_list_name(todo.project)
            
            # Map priority
            apple_priority = self._map_priority_to_apple(todo.priority)
            
            # Create reminder
            reminder_id = self.apple_script.create_reminder(
                list_name=list_name,
                name=todo.text,
                body=todo.description or "",
                due_date=todo.due_date,
                priority=apple_priority
            )
            
            self.log_sync_operation("create", f"Created reminder {reminder_id}: {todo.text}")
            return reminder_id
            
        except Exception as e:
            self.logger.error(f"Failed to create Apple reminder: {e}")
            raise NetworkError(f"Failed to create in Apple Reminders: {e}")
    
    async def update_item(self, external_id: str, todo: Todo) -> bool:
        """Update an existing reminder in Apple Reminders."""
        await self.ensure_authenticated()
        
        try:
            # Check if reminder still exists
            if not self.apple_script.reminder_exists(external_id):
                self.logger.warning(f"Reminder {external_id} no longer exists in Apple Reminders")
                return False
            
            # Map priority
            apple_priority = self._map_priority_to_apple(todo.priority)
            
            # Update reminder
            success = self.apple_script.update_reminder(
                reminder_id=external_id,
                name=todo.text,
                body=todo.description or "",
                due_date=todo.due_date,
                priority=apple_priority,
                completed=todo.completed
            )
            
            if success:
                self.log_sync_operation("update", f"Updated reminder {external_id}: {todo.text}")
            
            return success
            
        except Exception as e:
            self.logger.error(f"Failed to update Apple reminder {external_id}: {e}")
            return False
    
    async def delete_item(self, external_id: str) -> bool:
        """Delete a reminder from Apple Reminders."""
        await self.ensure_authenticated()
        
        try:
            success = self.apple_script.delete_reminder(external_id)
            if success:
                self.log_sync_operation("delete", f"Deleted reminder {external_id}")
            return success
            
        except Exception as e:
            self.logger.error(f"Failed to delete Apple reminder {external_id}: {e}")
            return False
    
    async def verify_item_exists(self, external_id: str) -> bool:
        """Verify if a reminder still exists in Apple Reminders.
        
        Args:
            external_id: The Apple Reminders ID to check
            
        Returns:
            True if the reminder exists, False otherwise
        """
        await self.ensure_authenticated()
        
        try:
            return self.apple_script.reminder_exists(external_id)
        except Exception as e:
            self.logger.warning(f"Error checking reminder {external_id}: {e}")
            return True  # Assume exists to be safe
    
    async def fetch_projects(self) -> Dict[str, str]:
        """Fetch available lists from Apple Reminders."""
        await self.ensure_authenticated()
        
        try:
            lists = self.apple_script.get_reminders_lists()
            return {lst["name"]: lst["id"] for lst in lists}
        except Exception as e:
            self.logger.error(f"Failed to fetch Apple Reminders lists: {e}")
            return {}
    
    def map_todo_to_external(self, todo: Todo) -> Dict[str, Any]:
        """Map a local Todo to Apple Reminders format."""
        return {
            "name": todo.text,
            "body": todo.description or "",
            "due_date": todo.due_date,
            "priority": self._map_priority_to_apple(todo.priority),
            "completed": todo.completed,
            "list_name": self._get_list_name(todo.project)
        }
    
    def map_external_to_todo(self, external_data: Dict[str, Any]) -> ExternalTodoItem:
        """Map Apple Reminders data to ExternalTodoItem."""
        reminder = external_data
        
        # Parse due date - use existing _parse_apple_date method for robustness
        due_date = reminder.get("due_date")
        if due_date:
            if isinstance(due_date, datetime):
                # Already a datetime object
                pass
            elif isinstance(due_date, str):
                # Parse Apple date string using our robust parser
                due_date = self._parse_apple_date(due_date)
            else:
                # Unknown format, log and set to None
                self.logger.warning(f"Unknown due_date format for reminder {reminder.get('id')}: {type(due_date)} {due_date}")
                due_date = None
        
        # Map priority from Apple's 1-9 scale to Priority enum
        apple_priority = reminder.get("priority", 5)
        priority_enum = self._map_priority_from_apple(apple_priority)
        
        # Get list name
        list_name = reminder.get("list_name", self.default_list_name)
        
        # Set timestamps
        created_at = now_utc()  # Apple Reminders doesn't expose creation time
        updated_at = created_at  # Apple Reminders doesn't expose modification time
        
        # Completion info
        completed = reminder.get("completed", False)
        completed_at = now_utc() if completed else None
        
        # Create a custom ExternalTodoItem that directly stores the Priority enum
        external_item = AppleRemindersExternalTodoItem(
            external_id=str(reminder["id"]),
            provider=AppSyncProvider.APPLE_REMINDERS,
            title=reminder["name"],
            description=reminder.get("body", ""),
            due_date=ensure_aware(due_date) if due_date else None,
            priority=apple_priority,  # Store original Apple priority for later use
            tags=[],  # Apple Reminders doesn't have tags
            project=list_name,
            project_id=self._lists_cache.get(list_name),
            completed=completed,
            completed_at=ensure_aware(completed_at) if completed_at else None,
            created_at=ensure_aware(created_at),
            updated_at=ensure_aware(updated_at),
            raw_data=reminder
        )
        
        # Store the mapped Priority enum value in raw_data for to_todo() method
        # Store as string value to avoid JSON serialization issues
        external_item.raw_data['priority_enum_value'] = priority_enum.value
        
        # Debug logging for specific task
        if external_item.title == "Here is a test task":
            self.logger.info(f"DEBUG: Created ExternalTodoItem - title: {external_item.title}, "
                           f"due_date: {external_item.due_date}, priority: {apple_priority}, "
                           f"priority_enum: {priority_enum}, description: {external_item.description}")
        
        return external_item
    
    async def _refresh_lists_cache(self):
        """Refresh the lists cache."""
        try:
            lists = self.apple_script.get_reminders_lists()
            # Filter out empty list names
            self._lists_cache = {
                lst["name"]: lst["id"] for lst in lists 
                if lst.get("name") and lst["name"].strip()
            }
            self.logger.debug(f"Refreshed lists cache: {len(self._lists_cache)} lists")
        except Exception as e:
            self.logger.warning(f"Failed to refresh lists cache: {e}")
    
    def _get_list_name(self, project_name: Optional[str]) -> str:
        """Get Apple Reminders list name from project name."""
        if not project_name or not str(project_name).strip():
            return self.default_list_name

        project_name_str = str(project_name).strip()

        mapped_project = self.config.project_mappings.get(project_name_str)
        if mapped_project and str(mapped_project).strip():
            return str(mapped_project)

        known_lists = {self.default_list_name.lower(), "work", "personal"}
        known_lists.update(name.lower() for name in self._lists_cache.keys())
        known_lists.update(str(value).lower() for value in self.config.project_mappings.values())

        if project_name_str.lower() in known_lists:
            return project_name_str

        return self.default_list_name
    
    def _map_priority_to_apple(self, priority: Priority) -> int:
        """Map Todo priority to Apple Reminders priority (1-9)."""
        if not priority:
            return 5  # Medium
        
        priority_map = {
            Priority.LOW: 7,
            Priority.MEDIUM: 5,
            Priority.HIGH: 3,
            Priority.CRITICAL: 1
        }
        return priority_map.get(priority, 5)
    
    def _map_priority_from_apple(self, apple_priority: int) -> Priority:
        """Map Apple Reminders priority to Todo Priority enum."""
        # Apple: 1 = high, 5 = medium, 9 = low
        # Map to our Priority enum
        if apple_priority <= 2:
            return Priority.CRITICAL
        elif apple_priority <= 4:
            return Priority.HIGH
        elif apple_priority <= 6:
            return Priority.MEDIUM
        else:
            return Priority.LOW
    
    def _should_include_reminder(self, reminder: Dict[str, Any]) -> bool:
        """Check if a reminder should be included in sync."""
        # Skip completed reminders if not configured to sync them
        if reminder.get("completed", False) and not self.sync_completed_reminders:
            return False
        
        return True
    
    async def cleanup_stale_mappings(self, mapping_store) -> int:
        """Clean up sync mappings for reminders that no longer exist in Apple Reminders.
        
        Args:
            mapping_store: The sync mapping store instance
            
        Returns:
            Number of stale mappings cleaned up
        """
        await self.ensure_authenticated()
        cleaned_count = 0
        
        try:
            # Get all mappings for this provider
            mappings_result = mapping_store.get_mappings_for_provider(self.provider)
            mappings = await mappings_result if isawaitable(mappings_result) else mappings_result or []
            
            for mapping in mappings:
                try:
                    # Use the verify method for consistency
                    exists = await self.verify_item_exists(mapping.external_id)
                    if not exists:
                        # Reminder doesn't exist, remove the mapping
                        self.logger.info(f"Cleaning up stale mapping for reminder {mapping.external_id}")
                        delete_result = mapping_store.delete_mapping(mapping.todo_id, self.provider)
                        if isawaitable(delete_result):
                            await delete_result
                        cleaned_count += 1
                except Exception as e:
                    self.logger.warning(f"Error checking reminder {mapping.external_id}: {e}")
            
            if cleaned_count > 0:
                self.logger.info(f"Cleaned up {cleaned_count} stale Apple Reminders mappings")
            
            return cleaned_count
            
        except Exception as e:
            self.logger.error(f"Failed to cleanup stale mappings: {e}")
            return 0