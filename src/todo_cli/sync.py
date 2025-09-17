"""Multi-device synchronization system for Todo CLI.

Provides cloud storage sync, conflict resolution, and offline mode support
for seamless multi-device todo management.
"""

import os
import json
import hashlib
import tempfile
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional, Tuple, Union
from dataclasses import dataclass, field, asdict
from pathlib import Path
from enum import Enum
import uuid
import subprocess
import shutil

from .todo import Todo, TodoStatus, Priority
from .config import get_config


class SyncProvider(Enum):
    """Supported sync providers"""
    DROPBOX = "dropbox"
    GOOGLE_DRIVE = "google_drive"
    ICLOUD = "icloud"
    ONEDRIVE = "onedrive"
    WEBDAV = "webdav"
    GIT = "git"
    LOCAL_FILE = "local_file"


class ConflictStrategy(Enum):
    """Conflict resolution strategies"""
    LOCAL_WINS = "local_wins"
    REMOTE_WINS = "remote_wins"
    NEWEST_WINS = "newest_wins"
    MANUAL = "manual"
    MERGE = "merge"


class SyncStatus(Enum):
    """Sync operation status"""
    SUCCESS = "success"
    CONFLICT = "conflict"
    ERROR = "error"
    NO_CHANGES = "no_changes"


@dataclass
class SyncEvent:
    """Sync event record"""
    timestamp: datetime
    event_type: str  # "push", "pull", "conflict", "merge"
    status: SyncStatus
    changes_count: int = 0
    conflicts_count: int = 0
    error_message: Optional[str] = None
    device_id: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'timestamp': self.timestamp.isoformat(),
            'event_type': self.event_type,
            'status': self.status.value,
            'changes_count': self.changes_count,
            'conflicts_count': self.conflicts_count,
            'error_message': self.error_message,
            'device_id': self.device_id
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SyncEvent':
        return cls(
            timestamp=datetime.fromisoformat(data['timestamp']),
            event_type=data['event_type'],
            status=SyncStatus(data['status']),
            changes_count=data.get('changes_count', 0),
            conflicts_count=data.get('conflicts_count', 0),
            error_message=data.get('error_message'),
            device_id=data.get('device_id', '')
        )


@dataclass
class TodoConflict:
    """Todo item conflict representation"""
    todo_id: int
    local_todo: Optional[Todo]
    remote_todo: Optional[Todo]
    conflict_type: str  # "modified", "deleted_local", "deleted_remote", "created_both"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'todo_id': self.todo_id,
            'local_todo': self.local_todo.to_dict() if self.local_todo else None,
            'remote_todo': self.remote_todo.to_dict() if self.remote_todo else None,
            'conflict_type': self.conflict_type
        }


@dataclass
class SyncConfig:
    """Synchronization configuration"""
    provider: SyncProvider
    enabled: bool = True
    auto_sync: bool = True
    sync_interval: int = 300  # seconds (5 minutes)
    conflict_strategy: ConflictStrategy = ConflictStrategy.NEWEST_WINS
    
    # Provider-specific settings
    sync_path: Optional[str] = None  # File path or URL
    auth_token: Optional[str] = None
    client_id: Optional[str] = None
    client_secret: Optional[str] = None
    
    # Sync settings
    sync_completed_tasks: bool = True
    sync_archived_tasks: bool = False
    max_history_days: int = 30
    compression_enabled: bool = True
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'provider': self.provider.value,
            'enabled': self.enabled,
            'auto_sync': self.auto_sync,
            'sync_interval': self.sync_interval,
            'conflict_strategy': self.conflict_strategy.value,
            'sync_path': self.sync_path,
            'auth_token': self.auth_token,
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'sync_completed_tasks': self.sync_completed_tasks,
            'sync_archived_tasks': self.sync_archived_tasks,
            'max_history_days': self.max_history_days,
            'compression_enabled': self.compression_enabled
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SyncConfig':
        return cls(
            provider=SyncProvider(data['provider']),
            enabled=data.get('enabled', True),
            auto_sync=data.get('auto_sync', True),
            sync_interval=data.get('sync_interval', 300),
            conflict_strategy=ConflictStrategy(data.get('conflict_strategy', 'newest_wins')),
            sync_path=data.get('sync_path'),
            auth_token=data.get('auth_token'),
            client_id=data.get('client_id'),
            client_secret=data.get('client_secret'),
            sync_completed_tasks=data.get('sync_completed_tasks', True),
            sync_archived_tasks=data.get('sync_archived_tasks', False),
            max_history_days=data.get('max_history_days', 30),
            compression_enabled=data.get('compression_enabled', True)
        )


class SyncAdapter:
    """Base class for sync adapters"""
    
    def __init__(self, config: SyncConfig):
        self.config = config
        
    def is_available(self) -> bool:
        """Check if sync provider is available"""
        raise NotImplementedError
        
    def upload_data(self, data: str, filename: str) -> bool:
        """Upload data to sync provider"""
        raise NotImplementedError
        
    def download_data(self, filename: str) -> Optional[str]:
        """Download data from sync provider"""
        raise NotImplementedError
        
    def list_files(self) -> List[str]:
        """List available files"""
        raise NotImplementedError
        
    def delete_file(self, filename: str) -> bool:
        """Delete file from sync provider"""
        raise NotImplementedError


class LocalFileAdapter(SyncAdapter):
    """Local file system sync adapter"""
    
    def is_available(self) -> bool:
        """Check if local sync path is accessible"""
        if not self.config.sync_path:
            return False
        
        sync_dir = Path(self.config.sync_path)
        return sync_dir.exists() or sync_dir.parent.exists()
    
    def upload_data(self, data: str, filename: str) -> bool:
        """Save data to local file"""
        try:
            sync_path = Path(self.config.sync_path)
            sync_path.mkdir(parents=True, exist_ok=True)
            
            file_path = sync_path / filename
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(data)
            
            return True
        except Exception as e:
            print(f"Error uploading to local file: {e}")
            return False
    
    def download_data(self, filename: str) -> Optional[str]:
        """Read data from local file"""
        try:
            file_path = Path(self.config.sync_path) / filename
            if file_path.exists():
                with open(file_path, 'r', encoding='utf-8') as f:
                    return f.read()
            return None
        except Exception as e:
            print(f"Error downloading from local file: {e}")
            return None
    
    def list_files(self) -> List[str]:
        """List files in sync directory"""
        try:
            sync_path = Path(self.config.sync_path)
            if sync_path.exists():
                return [f.name for f in sync_path.iterdir() if f.is_file()]
            return []
        except Exception as e:
            print(f"Error listing files: {e}")
            return []
    
    def delete_file(self, filename: str) -> bool:
        """Delete file from sync directory"""
        try:
            file_path = Path(self.config.sync_path) / filename
            if file_path.exists():
                file_path.unlink()
            return True
        except Exception as e:
            print(f"Error deleting file: {e}")
            return False


class GitAdapter(SyncAdapter):
    """Git repository sync adapter"""
    
    def is_available(self) -> bool:
        """Check if git is available and repo exists"""
        if not self.config.sync_path:
            return False
        
        try:
            # Check if git is installed
            subprocess.run(['git', '--version'], capture_output=True, timeout=5)
            
            # Check if sync path is a git repo
            repo_path = Path(self.config.sync_path)
            git_dir = repo_path / '.git'
            return git_dir.exists() or repo_path.suffix == '.git'
        except:
            return False
    
    def upload_data(self, data: str, filename: str) -> bool:
        """Commit and push data to git repository"""
        try:
            repo_path = Path(self.config.sync_path)
            file_path = repo_path / filename
            
            # Write file
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(data)
            
            # Git add, commit, and push
            commands = [
                ['git', '-C', str(repo_path), 'add', filename],
                ['git', '-C', str(repo_path), 'commit', '-m', f'Update {filename}'],
                ['git', '-C', str(repo_path), 'push']
            ]
            
            for cmd in commands:
                result = subprocess.run(cmd, capture_output=True, timeout=30)
                if result.returncode != 0 and 'nothing to commit' not in result.stdout.decode():
                    print(f"Git error: {result.stderr.decode()}")
                    return False
            
            return True
        except Exception as e:
            print(f"Error uploading to git: {e}")
            return False
    
    def download_data(self, filename: str) -> Optional[str]:
        """Pull and read data from git repository"""
        try:
            repo_path = Path(self.config.sync_path)
            
            # Git pull first
            result = subprocess.run(['git', '-C', str(repo_path), 'pull'], 
                                  capture_output=True, timeout=30)
            if result.returncode != 0:
                print(f"Git pull error: {result.stderr.decode()}")
            
            # Read file
            file_path = repo_path / filename
            if file_path.exists():
                with open(file_path, 'r', encoding='utf-8') as f:
                    return f.read()
            return None
        except Exception as e:
            print(f"Error downloading from git: {e}")
            return None
    
    def list_files(self) -> List[str]:
        """List files in git repository"""
        try:
            repo_path = Path(self.config.sync_path)
            result = subprocess.run(['git', '-C', str(repo_path), 'ls-files'], 
                                  capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0:
                return result.stdout.strip().split('\n') if result.stdout.strip() else []
            return []
        except Exception as e:
            print(f"Error listing git files: {e}")
            return []
    
    def delete_file(self, filename: str) -> bool:
        """Remove file from git repository"""
        try:
            repo_path = Path(self.config.sync_path)
            
            commands = [
                ['git', '-C', str(repo_path), 'rm', filename],
                ['git', '-C', str(repo_path), 'commit', '-m', f'Remove {filename}'],
                ['git', '-C', str(repo_path), 'push']
            ]
            
            for cmd in commands:
                result = subprocess.run(cmd, capture_output=True, timeout=30)
                if result.returncode != 0:
                    print(f"Git error: {result.stderr.decode()}")
                    return False
            
            return True
        except Exception as e:
            print(f"Error deleting from git: {e}")
            return False


class SyncManager:
    """Main synchronization manager"""
    
    def __init__(self, todo_manager=None):
        self.todo_manager = todo_manager
        self.config_obj = get_config()
        self.sync_config: Optional[SyncConfig] = None
        self.adapter: Optional[SyncAdapter] = None
        
        # Sync state files
        self.sync_dir = Path(self.config_obj.data_dir) / "sync"
        self.sync_dir.mkdir(parents=True, exist_ok=True)
        
        self.sync_history_file = self.sync_dir / "sync_history.json"
        self.conflicts_file = self.sync_dir / "conflicts.json"
        self.device_id_file = self.sync_dir / "device_id.txt"
        
        # Load or generate device ID
        self.device_id = self._load_or_create_device_id()
        
        # Load sync history
        self.sync_history = self._load_sync_history()
        
        # Load pending conflicts
        self.pending_conflicts = self._load_conflicts()
    
    def _load_or_create_device_id(self) -> str:
        """Load existing device ID or create a new one"""
        if self.device_id_file.exists():
            try:
                with open(self.device_id_file, 'r') as f:
                    return f.read().strip()
            except:
                pass
        
        # Create new device ID
        device_id = str(uuid.uuid4())
        try:
            with open(self.device_id_file, 'w') as f:
                f.write(device_id)
        except:
            pass
        
        return device_id
    
    def _load_sync_history(self) -> List[SyncEvent]:
        """Load sync history from file"""
        if self.sync_history_file.exists():
            try:
                with open(self.sync_history_file, 'r') as f:
                    data = json.load(f)
                return [SyncEvent.from_dict(event) for event in data]
            except:
                pass
        return []
    
    def _save_sync_history(self):
        """Save sync history to file"""
        try:
            data = [event.to_dict() for event in self.sync_history]
            with open(self.sync_history_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"Error saving sync history: {e}")
    
    def _load_conflicts(self) -> List[TodoConflict]:
        """Load pending conflicts from file"""
        if self.conflicts_file.exists():
            try:
                with open(self.conflicts_file, 'r') as f:
                    data = json.load(f)
                conflicts = []
                for conflict_data in data:
                    local_todo = None
                    remote_todo = None
                    
                    if conflict_data.get('local_todo'):
                        local_todo = Todo.from_dict(conflict_data['local_todo'])
                    if conflict_data.get('remote_todo'):
                        remote_todo = Todo.from_dict(conflict_data['remote_todo'])
                    
                    conflicts.append(TodoConflict(
                        todo_id=conflict_data['todo_id'],
                        local_todo=local_todo,
                        remote_todo=remote_todo,
                        conflict_type=conflict_data['conflict_type']
                    ))
                return conflicts
            except:
                pass
        return []
    
    def _save_conflicts(self):
        """Save pending conflicts to file"""
        try:
            data = [conflict.to_dict() for conflict in self.pending_conflicts]
            with open(self.conflicts_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"Error saving conflicts: {e}")
    
    def configure_sync(self, sync_config: SyncConfig) -> bool:
        """Configure synchronization settings"""
        self.sync_config = sync_config
        
        # Create appropriate adapter
        if sync_config.provider == SyncProvider.LOCAL_FILE:
            self.adapter = LocalFileAdapter(sync_config)
        elif sync_config.provider == SyncProvider.GIT:
            self.adapter = GitAdapter(sync_config)
        else:
            print(f"Sync provider {sync_config.provider} not yet implemented")
            return False
        
        return self.adapter.is_available()
    
    def sync_up(self) -> SyncStatus:
        """Push local changes to remote"""
        if not self._check_sync_ready():
            return SyncStatus.ERROR
        
        try:
            # Get all todos
            todos = self.todo_manager.get_todos()
            
            # Filter todos based on config
            filtered_todos = self._filter_todos_for_sync(todos)
            
            # Create sync data
            sync_data = {
                'device_id': self.device_id,
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'todos': [todo.to_dict() for todo in filtered_todos],
                'version': '1.0'
            }
            
            # Serialize and upload
            data_json = json.dumps(sync_data, indent=2)
            filename = f"todos_{self.device_id}.json"
            
            if self.adapter.upload_data(data_json, filename):
                # Record sync event
                event = SyncEvent(
                    timestamp=datetime.now(timezone.utc),
                    event_type="push",
                    status=SyncStatus.SUCCESS,
                    changes_count=len(filtered_todos),
                    device_id=self.device_id
                )
                self.sync_history.append(event)
                self._save_sync_history()
                
                return SyncStatus.SUCCESS
            else:
                return SyncStatus.ERROR
                
        except Exception as e:
            print(f"Sync up error: {e}")
            return SyncStatus.ERROR
    
    def sync_down(self) -> SyncStatus:
        """Pull remote changes and merge"""
        if not self._check_sync_ready():
            return SyncStatus.ERROR
        
        try:
            # List available files
            files = self.adapter.list_files()
            todo_files = [f for f in files if f.startswith('todos_') and f.endswith('.json')]
            
            conflicts = []
            total_changes = 0
            
            # Process each remote device's data
            for filename in todo_files:
                remote_device_id = filename.replace('todos_', '').replace('.json', '')
                if remote_device_id == self.device_id:
                    continue  # Skip our own file
                
                data = self.adapter.download_data(filename)
                if data:
                    remote_data = json.loads(data)
                    device_conflicts, changes = self._merge_remote_todos(remote_data)
                    conflicts.extend(device_conflicts)
                    total_changes += changes
            
            # Handle conflicts
            status = SyncStatus.SUCCESS
            if conflicts:
                self.pending_conflicts.extend(conflicts)
                self._save_conflicts()
                
                if self.sync_config.conflict_strategy == ConflictStrategy.MANUAL:
                    status = SyncStatus.CONFLICT
                else:
                    # Auto-resolve conflicts
                    resolved = self._auto_resolve_conflicts(conflicts)
                    if not resolved:
                        status = SyncStatus.CONFLICT
            
            # Record sync event
            event = SyncEvent(
                timestamp=datetime.now(timezone.utc),
                event_type="pull",
                status=status,
                changes_count=total_changes,
                conflicts_count=len(conflicts),
                device_id=self.device_id
            )
            self.sync_history.append(event)
            self._save_sync_history()
            
            return status
            
        except Exception as e:
            print(f"Sync down error: {e}")
            return SyncStatus.ERROR
    
    def full_sync(self) -> SyncStatus:
        """Perform full bidirectional sync"""
        if not self._check_sync_ready():
            return SyncStatus.ERROR
        
        # First pull remote changes
        down_status = self.sync_down()
        
        # Then push our changes
        up_status = self.sync_up()
        
        # Return worst status
        if down_status == SyncStatus.ERROR or up_status == SyncStatus.ERROR:
            return SyncStatus.ERROR
        elif down_status == SyncStatus.CONFLICT or up_status == SyncStatus.CONFLICT:
            return SyncStatus.CONFLICT
        else:
            return SyncStatus.SUCCESS
    
    def _check_sync_ready(self) -> bool:
        """Check if sync is properly configured and available"""
        if not self.sync_config or not self.adapter:
            print("Sync not configured")
            return False
        
        if not self.sync_config.enabled:
            print("Sync is disabled")
            return False
        
        if not self.adapter.is_available():
            print("Sync provider not available")
            return False
        
        return True
    
    def _filter_todos_for_sync(self, todos: List[Todo]) -> List[Todo]:
        """Filter todos based on sync configuration"""
        filtered = todos
        
        # Filter by completion status
        if not self.sync_config.sync_completed_tasks:
            filtered = [t for t in filtered if not t.completed]
        
        # Filter by archive status
        if not self.sync_config.sync_archived_tasks:
            filtered = [t for t in filtered if not getattr(t, 'archived', False)]
        
        # Filter by age
        if self.sync_config.max_history_days > 0:
            cutoff = datetime.now(timezone.utc) - timedelta(days=self.sync_config.max_history_days)
            # Handle timezone-aware comparison
            filtered_by_age = []
            for t in filtered:
                if t.created:
                    # Make created datetime timezone-aware if it isn't already
                    created_dt = t.created
                    if created_dt.tzinfo is None:
                        created_dt = created_dt.replace(tzinfo=timezone.utc)
                    if created_dt >= cutoff:
                        filtered_by_age.append(t)
                else:
                    filtered_by_age.append(t)  # Include todos with no creation date
            filtered = filtered_by_age
        
        return filtered
    
    def _merge_remote_todos(self, remote_data: Dict[str, Any]) -> Tuple[List[TodoConflict], int]:
        """Merge remote todos with local todos"""
        conflicts = []
        changes_count = 0
        
        remote_todos = [Todo.from_dict(todo_data) for todo_data in remote_data['todos']]
        local_todos = self.todo_manager.get_todos()
        
        # Create lookup for local todos
        local_by_id = {todo.id: todo for todo in local_todos}
        
        # Process remote todos
        for remote_todo in remote_todos:
            local_todo = local_by_id.get(remote_todo.id)
            
            if local_todo is None:
                # New todo from remote
                try:
                    self.todo_manager.add_todo(
                        remote_todo.text,
                        project=remote_todo.project,
                        priority=remote_todo.priority,
                        due_date=remote_todo.due_date,
                        tags=remote_todo.tags,
                        description=remote_todo.description
                    )
                    changes_count += 1
                except:
                    pass  # Skip if adding fails
            else:
                # Check for conflicts
                if self._todos_conflict(local_todo, remote_todo):
                    conflict = TodoConflict(
                        todo_id=remote_todo.id,
                        local_todo=local_todo,
                        remote_todo=remote_todo,
                        conflict_type="modified"
                    )
                    conflicts.append(conflict)
                elif remote_todo.modified > local_todo.modified:
                    # Remote is newer, update local
                    self._update_local_todo(local_todo.id, remote_todo)
                    changes_count += 1
        
        return conflicts, changes_count
    
    def _todos_conflict(self, local_todo: Todo, remote_todo: Todo) -> bool:
        """Check if two todos have conflicting changes"""
        # Both modified since last sync, but with different content
        if local_todo.modified != remote_todo.modified:
            # Check if actual content differs
            local_hash = self._todo_content_hash(local_todo)
            remote_hash = self._todo_content_hash(remote_todo)
            return local_hash != remote_hash
        return False
    
    def _todo_content_hash(self, todo: Todo) -> str:
        """Generate hash of todo content for conflict detection"""
        content = f"{todo.text}|{todo.project}|{todo.priority}|{todo.due_date}|{todo.completed}|{todo.description}"
        return hashlib.md5(content.encode()).hexdigest()
    
    def _update_local_todo(self, todo_id: int, remote_todo: Todo):
        """Update local todo with remote data"""
        self.todo_manager.update_todo(
            todo_id,
            text=remote_todo.text,
            project=remote_todo.project,
            priority=remote_todo.priority,
            due_date=remote_todo.due_date,
            completed=remote_todo.completed,
            description=remote_todo.description,
            tags=remote_todo.tags
        )
    
    def _auto_resolve_conflicts(self, conflicts: List[TodoConflict]) -> bool:
        """Auto-resolve conflicts based on strategy"""
        strategy = self.sync_config.conflict_strategy
        
        for conflict in conflicts:
            try:
                if strategy == ConflictStrategy.LOCAL_WINS:
                    # Keep local version, do nothing
                    pass
                elif strategy == ConflictStrategy.REMOTE_WINS:
                    # Use remote version
                    if conflict.remote_todo:
                        self._update_local_todo(conflict.todo_id, conflict.remote_todo)
                elif strategy == ConflictStrategy.NEWEST_WINS:
                    # Use whichever was modified more recently
                    if (conflict.remote_todo and conflict.local_todo and 
                        conflict.remote_todo.modified > conflict.local_todo.modified):
                        self._update_local_todo(conflict.todo_id, conflict.remote_todo)
                
                # Remove from pending conflicts
                self.pending_conflicts = [c for c in self.pending_conflicts 
                                        if c.todo_id != conflict.todo_id]
            except Exception as e:
                print(f"Error resolving conflict for todo {conflict.todo_id}: {e}")
                return False
        
        self._save_conflicts()
        return True
    
    def resolve_conflict_manually(self, todo_id: int, resolution: str) -> bool:
        """Manually resolve a specific conflict"""
        conflict = next((c for c in self.pending_conflicts if c.todo_id == todo_id), None)
        
        if not conflict:
            return False
        
        try:
            if resolution == "local":
                # Keep local version
                pass
            elif resolution == "remote":
                # Use remote version
                if conflict.remote_todo:
                    self._update_local_todo(todo_id, conflict.remote_todo)
            elif resolution == "merge":
                # Custom merge logic could go here
                pass
            
            # Remove from pending conflicts
            self.pending_conflicts = [c for c in self.pending_conflicts if c.todo_id != todo_id]
            self._save_conflicts()
            
            return True
        except Exception as e:
            print(f"Error resolving conflict manually: {e}")
            return False
    
    def get_sync_status(self) -> Dict[str, Any]:
        """Get current sync status"""
        last_sync = None
        if self.sync_history:
            last_sync = self.sync_history[-1].to_dict()
        
        return {
            'configured': self.sync_config is not None,
            'enabled': self.sync_config.enabled if self.sync_config else False,
            'provider': self.sync_config.provider.value if self.sync_config else None,
            'available': self.adapter.is_available() if self.adapter else False,
            'last_sync': last_sync,
            'pending_conflicts': len(self.pending_conflicts),
            'device_id': self.device_id
        }
    
    def get_pending_conflicts(self) -> List[Dict[str, Any]]:
        """Get list of pending conflicts"""
        return [conflict.to_dict() for conflict in self.pending_conflicts]
    
    def get_sync_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get sync history"""
        recent_history = self.sync_history[-limit:] if len(self.sync_history) > limit else self.sync_history
        return [event.to_dict() for event in recent_history]