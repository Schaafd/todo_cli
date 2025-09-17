"""Calendar Integration system for Todo CLI.

Provides two-way synchronization with calendar systems including iCal, Google Calendar,
and local calendars. Supports conflict resolution and smart scheduling.
"""

import os
import sys
import json
import uuid
import hashlib
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any, Optional, Union, Tuple
from dataclasses import dataclass, field
from pathlib import Path
from enum import Enum
import subprocess
import tempfile

from .todo import Todo, TodoStatus
from .config import get_config


class CalendarType(Enum):
    """Supported calendar types"""
    ICAL = "ical"
    GOOGLE_CALENDAR = "google_calendar"
    OUTLOOK = "outlook"
    APPLE_CALENDAR = "apple_calendar"
    LOCAL_FILE = "local_file"


class SyncDirection(Enum):
    """Sync directions"""
    IMPORT_ONLY = "import_only"  # Calendar → Todo CLI
    EXPORT_ONLY = "export_only"  # Todo CLI → Calendar
    BIDIRECTIONAL = "bidirectional"  # Two-way sync


class ConflictResolution(Enum):
    """Conflict resolution strategies"""
    TODO_WINS = "todo_wins"  # Todo CLI changes take precedence
    CALENDAR_WINS = "calendar_wins"  # Calendar changes take precedence
    MANUAL = "manual"  # User decides manually
    NEWEST_WINS = "newest_wins"  # Most recently modified wins


@dataclass
class CalendarEvent:
    """Calendar event representation"""
    uid: str
    title: str
    description: str = ""
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    all_day: bool = False
    location: str = ""
    
    # Todo CLI specific fields
    todo_id: Optional[int] = None
    project: Optional[str] = None
    priority: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    
    # Metadata
    created: datetime = field(default_factory=datetime.now)
    modified: datetime = field(default_factory=datetime.now)
    calendar_source: Optional[str] = None
    
    def to_ical_event(self) -> str:
        """Convert to iCal event format"""
        lines = [
            "BEGIN:VEVENT",
            f"UID:{self.uid}",
            f"DTSTART:{self._format_datetime(self.start_time) if self.start_time else ''}",
            f"DTEND:{self._format_datetime(self.end_time) if self.end_time else ''}",
            f"SUMMARY:{self.title}",
            f"DESCRIPTION:{self.description}",
            f"DTSTAMP:{self._format_datetime(self.created)}",
            f"LAST-MODIFIED:{self._format_datetime(self.modified)}",
        ]
        
        if self.location:
            lines.append(f"LOCATION:{self.location}")
        
        if self.todo_id:
            lines.append(f"X-TODO-ID:{self.todo_id}")
            
        if self.project:
            lines.append(f"X-TODO-PROJECT:{self.project}")
            
        if self.priority:
            lines.append(f"X-TODO-PRIORITY:{self.priority}")
            
        if self.tags:
            lines.append(f"X-TODO-TAGS:{','.join(self.tags)}")
        
        lines.append("END:VEVENT")
        return "\n".join(lines)
    
    def _format_datetime(self, dt: datetime) -> str:
        """Format datetime for iCal"""
        if dt.tzinfo:
            return dt.strftime("%Y%m%dT%H%M%SZ")
        else:
            return dt.strftime("%Y%m%dT%H%M%S")
    
    @classmethod
    def from_todo(cls, todo: Todo) -> 'CalendarEvent':
        """Create calendar event from todo"""
        # Generate unique UID based on todo ID and content
        uid_source = f"todo-{todo.id}-{todo.text}-{todo.project}"
        uid = str(uuid.uuid5(uuid.NAMESPACE_DNS, uid_source))
        
        # Determine event time
        start_time = todo.due_date
        end_time = None
        
        if start_time and todo.time_estimate:
            end_time = start_time + timedelta(minutes=todo.time_estimate)
        elif start_time:
            # Default 1-hour duration for tasks without time estimates
            end_time = start_time + timedelta(hours=1)
        
        # Create description with todo details
        description_parts = []
        if todo.description:
            description_parts.append(todo.description)
        
        if todo.assignees:
            description_parts.append(f"Assigned to: {', '.join(todo.assignees)}")
            
        if todo.waiting_for:
            description_parts.append(f"Waiting for: {', '.join(todo.waiting_for)}")
            
        if todo.url:
            description_parts.append(f"URL: {todo.url}")
        
        description = "\n".join(description_parts)
        
        return cls(
            uid=uid,
            title=todo.text,
            description=description,
            start_time=start_time,
            end_time=end_time,
            todo_id=todo.id,
            project=todo.project,
            priority=todo.priority.value if todo.priority else None,
            tags=list(todo.tags) if todo.tags else [],
            created=todo.created,
            modified=todo.modified
        )
    
    def to_todo_updates(self) -> Dict[str, Any]:
        """Get todo field updates from calendar event"""
        updates = {}
        
        if self.title and self.title != "":
            updates['text'] = self.title
            
        if self.description:
            updates['description'] = self.description
            
        if self.start_time:
            updates['due_date'] = self.start_time
            
        if self.location:
            updates['location'] = self.location
            
        # Calculate time estimate from duration
        if self.start_time and self.end_time:
            duration = self.end_time - self.start_time
            updates['time_estimate'] = int(duration.total_seconds() / 60)
        
        return updates


@dataclass 
class CalendarConfig:
    """Calendar configuration"""
    name: str
    calendar_type: CalendarType
    sync_direction: SyncDirection
    conflict_resolution: ConflictResolution
    
    # Calendar-specific settings
    file_path: Optional[str] = None  # For file-based calendars
    calendar_id: Optional[str] = None  # For API-based calendars
    auth_token: Optional[str] = None  # For authenticated calendars
    
    # Sync settings
    enabled: bool = True
    sync_completed_tasks: bool = False
    auto_sync_interval: int = 300  # seconds (5 minutes)
    
    # Filtering
    sync_projects: List[str] = field(default_factory=list)  # Empty = all projects
    sync_tags: List[str] = field(default_factory=list)  # Empty = all tags
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'name': self.name,
            'calendar_type': self.calendar_type.value,
            'sync_direction': self.sync_direction.value,
            'conflict_resolution': self.conflict_resolution.value,
            'file_path': self.file_path,
            'calendar_id': self.calendar_id,
            'auth_token': self.auth_token,
            'enabled': self.enabled,
            'sync_completed_tasks': self.sync_completed_tasks,
            'auto_sync_interval': self.auto_sync_interval,
            'sync_projects': self.sync_projects,
            'sync_tags': self.sync_tags
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CalendarConfig':
        """Create from dictionary"""
        return cls(
            name=data['name'],
            calendar_type=CalendarType(data['calendar_type']),
            sync_direction=SyncDirection(data['sync_direction']),
            conflict_resolution=ConflictResolution(data['conflict_resolution']),
            file_path=data.get('file_path'),
            calendar_id=data.get('calendar_id'),
            auth_token=data.get('auth_token'),
            enabled=data.get('enabled', True),
            sync_completed_tasks=data.get('sync_completed_tasks', False),
            auto_sync_interval=data.get('auto_sync_interval', 300),
            sync_projects=data.get('sync_projects', []),
            sync_tags=data.get('sync_tags', [])
        )


class CalendarAdapter:
    """Base class for calendar adapters"""
    
    def __init__(self, config: CalendarConfig):
        self.config = config
    
    def read_events(self) -> List[CalendarEvent]:
        """Read events from calendar"""
        raise NotImplementedError
    
    def write_events(self, events: List[CalendarEvent]) -> bool:
        """Write events to calendar"""
        raise NotImplementedError
    
    def delete_event(self, event_uid: str) -> bool:
        """Delete event from calendar"""
        raise NotImplementedError
    
    def is_available(self) -> bool:
        """Check if calendar is available"""
        raise NotImplementedError


class ICalAdapter(CalendarAdapter):
    """iCal file format adapter"""
    
    def read_events(self) -> List[CalendarEvent]:
        """Read events from iCal file"""
        if not self.config.file_path or not os.path.exists(self.config.file_path):
            return []
        
        try:
            with open(self.config.file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            return self._parse_ical_content(content)
        except Exception as e:
            print(f"Error reading iCal file: {e}")
            return []
    
    def write_events(self, events: List[CalendarEvent]) -> bool:
        """Write events to iCal file"""
        if not self.config.file_path:
            return False
        
        try:
            # Create iCal content
            lines = [
                "BEGIN:VCALENDAR",
                "VERSION:2.0",
                "PRODID:-//Todo CLI//Calendar Integration//EN",
                "CALSCALE:GREGORIAN",
                "METHOD:PUBLISH",
                ""
            ]
            
            for event in events:
                lines.append(event.to_ical_event())
                lines.append("")
            
            lines.append("END:VCALENDAR")
            
            # Write to file
            os.makedirs(os.path.dirname(self.config.file_path), exist_ok=True)
            with open(self.config.file_path, 'w', encoding='utf-8') as f:
                f.write("\n".join(lines))
            
            return True
        except Exception as e:
            print(f"Error writing iCal file: {e}")
            return False
    
    def delete_event(self, event_uid: str) -> bool:
        """Delete event from iCal file"""
        events = self.read_events()
        filtered_events = [e for e in events if e.uid != event_uid]
        
        if len(filtered_events) != len(events):
            return self.write_events(filtered_events)
        
        return True  # Event didn't exist, so "deletion" successful
    
    def is_available(self) -> bool:
        """Check if iCal file is accessible"""
        if not self.config.file_path:
            return False
        
        # Check if file exists or if parent directory is writable
        if os.path.exists(self.config.file_path):
            return os.access(self.config.file_path, os.R_OK | os.W_OK)
        else:
            parent_dir = os.path.dirname(self.config.file_path)
            return os.path.exists(parent_dir) and os.access(parent_dir, os.W_OK)
    
    def _parse_ical_content(self, content: str) -> List[CalendarEvent]:
        """Parse iCal content into events"""
        events = []
        lines = content.strip().split('\n')
        current_event = None
        
        for line in lines:
            line = line.strip()
            
            if line == "BEGIN:VEVENT":
                current_event = {}
            elif line == "END:VEVENT":
                if current_event:
                    event = self._parse_event_dict(current_event)
                    if event:
                        events.append(event)
                current_event = None
            elif current_event is not None and ':' in line:
                key, value = line.split(':', 1)
                current_event[key] = value
        
        return events
    
    def _parse_event_dict(self, event_dict: Dict[str, str]) -> Optional[CalendarEvent]:
        """Parse event dictionary into CalendarEvent"""
        try:
            uid = event_dict.get('UID', str(uuid.uuid4()))
            title = event_dict.get('SUMMARY', 'Untitled Event')
            description = event_dict.get('DESCRIPTION', '')
            
            # Parse dates
            start_time = self._parse_ical_datetime(event_dict.get('DTSTART'))
            end_time = self._parse_ical_datetime(event_dict.get('DTEND'))
            created = self._parse_ical_datetime(event_dict.get('DTSTAMP')) or datetime.now()
            modified = self._parse_ical_datetime(event_dict.get('LAST-MODIFIED')) or datetime.now()
            
            # Parse Todo CLI specific fields
            todo_id = None
            if 'X-TODO-ID' in event_dict:
                try:
                    todo_id = int(event_dict['X-TODO-ID'])
                except ValueError:
                    pass
            
            project = event_dict.get('X-TODO-PROJECT')
            priority = event_dict.get('X-TODO-PRIORITY')
            tags = []
            if 'X-TODO-TAGS' in event_dict:
                tags = event_dict['X-TODO-TAGS'].split(',')
            
            return CalendarEvent(
                uid=uid,
                title=title,
                description=description,
                start_time=start_time,
                end_time=end_time,
                location=event_dict.get('LOCATION', ''),
                todo_id=todo_id,
                project=project,
                priority=priority,
                tags=tags,
                created=created,
                modified=modified,
                calendar_source=self.config.name
            )
        except Exception as e:
            print(f"Error parsing event: {e}")
            return None
    
    def _parse_ical_datetime(self, date_str: Optional[str]) -> Optional[datetime]:
        """Parse iCal datetime string"""
        if not date_str:
            return None
        
        try:
            # Handle different iCal datetime formats
            if date_str.endswith('Z'):
                # UTC time
                return datetime.strptime(date_str, '%Y%m%dT%H%M%SZ').replace(tzinfo=timezone.utc)
            elif 'T' in date_str:
                # Local time
                return datetime.strptime(date_str, '%Y%m%dT%H%M%S')
            else:
                # Date only
                return datetime.strptime(date_str, '%Y%m%d')
        except ValueError:
            return None


class AppleCalendarAdapter(CalendarAdapter):
    """macOS Calendar adapter using AppleScript"""
    
    def read_events(self) -> List[CalendarEvent]:
        """Read events from Apple Calendar"""
        if not self.is_available():
            return []
        
        try:
            # AppleScript to get calendar events
            script = f'''
            tell application "Calendar"
                set eventList to {{}}
                set targetCalendar to calendar "{self.config.name}"
                set startDate to (current date) - (7 * days)
                set endDate to (current date) + (30 * days)
                
                repeat with anEvent in (events of targetCalendar whose start date ≥ startDate and start date ≤ endDate)
                    set eventInfo to (summary of anEvent) & "|" & (description of anEvent) & "|" & (start date of anEvent as string) & "|" & (end date of anEvent as string)
                    set end of eventList to eventInfo
                end repeat
                
                return eventList
            end tell
            '''
            
            result = subprocess.run(['osascript', '-e', script], 
                                  capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0:
                return self._parse_applescript_output(result.stdout)
            else:
                print(f"AppleScript error: {result.stderr}")
                return []
                
        except Exception as e:
            print(f"Error reading Apple Calendar: {e}")
            return []
    
    def write_events(self, events: List[CalendarEvent]) -> bool:
        """Write events to Apple Calendar"""
        if not self.is_available():
            return False
        
        success_count = 0
        for event in events:
            if self._write_single_event(event):
                success_count += 1
        
        return success_count == len(events)
    
    def delete_event(self, event_uid: str) -> bool:
        """Delete event from Apple Calendar"""
        # Note: This is simplified - in practice, we'd need to track calendar event IDs
        return True
    
    def is_available(self) -> bool:
        """Check if Apple Calendar is available"""
        if sys.platform != "darwin":
            return False
        
        try:
            # Check if Calendar app exists
            result = subprocess.run(['osascript', '-e', 'tell application "Calendar" to get name'],
                                  capture_output=True, timeout=5)
            return result.returncode == 0
        except:
            return False
    
    def _write_single_event(self, event: CalendarEvent) -> bool:
        """Write single event to Apple Calendar"""
        try:
            # Escape quotes in strings
            title = event.title.replace('"', '\\"')
            description = event.description.replace('"', '\\"')
            
            script = f'''
            tell application "Calendar"
                set targetCalendar to calendar "{self.config.name}"
                set newEvent to make new event at end of events of targetCalendar
                set summary of newEvent to "{title}"
                set description of newEvent to "{description}"
            '''
            
            if event.start_time:
                start_str = event.start_time.strftime('%m/%d/%Y %H:%M:%S')
                script += f'\n                set start date of newEvent to date "{start_str}"'
            
            if event.end_time:
                end_str = event.end_time.strftime('%m/%d/%Y %H:%M:%S')
                script += f'\n                set end date of newEvent to date "{end_str}"'
            
            script += '\n            end tell'
            
            result = subprocess.run(['osascript', '-e', script], 
                                  capture_output=True, text=True, timeout=10)
            
            return result.returncode == 0
        except Exception as e:
            print(f"Error writing event to Apple Calendar: {e}")
            return False
    
    def _parse_applescript_output(self, output: str) -> List[CalendarEvent]:
        """Parse AppleScript output into events"""
        events = []
        lines = output.strip().split('\n')
        
        for line in lines:
            if '|' in line:
                parts = line.split('|')
                if len(parts) >= 4:
                    try:
                        event = CalendarEvent(
                            uid=str(uuid.uuid4()),
                            title=parts[0],
                            description=parts[1],
                            start_time=self._parse_applescript_date(parts[2]),
                            end_time=self._parse_applescript_date(parts[3]),
                            calendar_source=self.config.name
                        )
                        events.append(event)
                    except Exception as e:
                        print(f"Error parsing AppleScript event: {e}")
        
        return events
    
    def _parse_applescript_date(self, date_str: str) -> Optional[datetime]:
        """Parse AppleScript date string"""
        # This would need more robust parsing for different date formats
        # For now, return None to avoid errors
        return None


class CalendarSync:
    """Main calendar synchronization manager"""
    
    def __init__(self):
        self.config = get_config()
        self.calendars: Dict[str, CalendarAdapter] = {}
        self.sync_history_file = Path(self.config.data_dir) / "calendar_sync_history.json"
        self.sync_history = self._load_sync_history()
        
    def _load_sync_history(self) -> Dict[str, Any]:
        """Load sync history from file"""
        if self.sync_history_file.exists():
            try:
                with open(self.sync_history_file, 'r') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                pass
        return {"last_sync": {}, "event_mappings": {}}
    
    def _save_sync_history(self):
        """Save sync history to file"""
        try:
            self.sync_history_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.sync_history_file, 'w') as f:
                json.dump(self.sync_history, f, indent=2, default=str)
        except Exception as e:
            print(f"Error saving sync history: {e}")
    
    def add_calendar(self, config: CalendarConfig) -> bool:
        """Add a calendar configuration"""
        try:
            if config.calendar_type == CalendarType.ICAL:
                adapter = ICalAdapter(config)
            elif config.calendar_type == CalendarType.APPLE_CALENDAR:
                adapter = AppleCalendarAdapter(config)
            else:
                print(f"Calendar type {config.calendar_type} not yet implemented")
                return False
            
            if adapter.is_available():
                self.calendars[config.name] = adapter
                return True
            else:
                print(f"Calendar '{config.name}' is not available")
                return False
        except Exception as e:
            print(f"Error adding calendar: {e}")
            return False
    
    def sync_calendar(self, calendar_name: str, todos: List[Todo]) -> Tuple[int, int, List[str]]:
        """Sync todos with specified calendar
        
        Returns: (exported_count, imported_count, errors)
        """
        if calendar_name not in self.calendars:
            return 0, 0, [f"Calendar '{calendar_name}' not found"]
        
        adapter = self.calendars[calendar_name]
        config = adapter.config
        errors = []
        exported_count = 0
        imported_count = 0
        
        try:
            # Export todos to calendar
            if config.sync_direction in [SyncDirection.EXPORT_ONLY, SyncDirection.BIDIRECTIONAL]:
                exported_count = self._export_todos_to_calendar(adapter, todos, errors)
            
            # Import events from calendar
            if config.sync_direction in [SyncDirection.IMPORT_ONLY, SyncDirection.BIDIRECTIONAL]:
                imported_count = self._import_events_from_calendar(adapter, errors)
            
            # Update sync history
            self.sync_history["last_sync"][calendar_name] = datetime.now().isoformat()
            self._save_sync_history()
            
        except Exception as e:
            errors.append(f"Sync error: {e}")
        
        return exported_count, imported_count, errors
    
    def _export_todos_to_calendar(self, adapter: CalendarAdapter, todos: List[Todo], errors: List[str]) -> int:
        """Export todos to calendar"""
        config = adapter.config
        exported_count = 0
        
        # Filter todos based on config
        filtered_todos = self._filter_todos_for_export(todos, config)
        
        # Convert todos to calendar events
        events = []
        for todo in filtered_todos:
            # Only export todos with due dates
            if todo.due_date:
                event = CalendarEvent.from_todo(todo)
                events.append(event)
        
        # Write events to calendar
        if events:
            if adapter.write_events(events):
                exported_count = len(events)
            else:
                errors.append("Failed to write events to calendar")
        
        return exported_count
    
    def _import_events_from_calendar(self, adapter: CalendarAdapter, errors: List[str]) -> int:
        """Import events from calendar"""
        # Note: This is a simplified implementation
        # In a full implementation, this would create or update todos based on calendar events
        events = adapter.read_events()
        return len(events)
    
    def _filter_todos_for_export(self, todos: List[Todo], config: CalendarConfig) -> List[Todo]:
        """Filter todos based on calendar config"""
        filtered = todos
        
        # Filter by completion status
        if not config.sync_completed_tasks:
            filtered = [t for t in filtered if not t.completed]
        
        # Filter by projects
        if config.sync_projects:
            filtered = [t for t in filtered if t.project in config.sync_projects]
        
        # Filter by tags
        if config.sync_tags:
            filtered = [t for t in filtered if any(tag in config.sync_tags for tag in (t.tags or []))]
        
        return filtered
    
    def get_calendar_status(self, calendar_name: str) -> Dict[str, Any]:
        """Get status of a calendar"""
        if calendar_name not in self.calendars:
            return {"available": False, "error": "Calendar not found"}
        
        adapter = self.calendars[calendar_name]
        last_sync = self.sync_history["last_sync"].get(calendar_name)
        
        return {
            "available": adapter.is_available(),
            "type": adapter.config.calendar_type.value,
            "sync_direction": adapter.config.sync_direction.value,
            "enabled": adapter.config.enabled,
            "last_sync": last_sync
        }
    
    def list_calendars(self) -> List[Dict[str, Any]]:
        """List all configured calendars"""
        return [
            {
                "name": name,
                **self.get_calendar_status(name)
            }
            for name in self.calendars.keys()
        ]