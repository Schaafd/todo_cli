"""Storage layer for sync mappings and conflicts.

This module provides persistent storage for sync mappings between local todos
and external items, as well as sync conflicts that need resolution.
"""

import sqlite3
import json
import logging
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Dict, Any
from pathlib import Path

from .app_sync_models import (
    AppSyncProvider,
    SyncMapping,
    SyncConflict,
    ConflictType
)
from ..config import get_config_dir


logger = logging.getLogger(__name__)


class SyncMappingStore:
    """Persistent storage for sync mappings and conflicts."""
    
    def __init__(self, db_path: Optional[Path] = None):
        """Initialize the mapping store.
        
        Args:
            db_path: Optional custom database path
        """
        if db_path is None:
            config_dir = get_config_dir()
            config_dir.mkdir(exist_ok=True)
            db_path = config_dir / "sync_mappings.db"
        
        self.db_path = db_path
        self.logger = logging.getLogger(__name__)
        
        # Initialize database
        self._init_database()
    
    def _init_database(self):
        """Initialize the SQLite database with required tables."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("PRAGMA foreign_keys = ON")
                
                # Create sync_mappings table
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS sync_mappings (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        todo_id INTEGER NOT NULL,
                        external_id TEXT NOT NULL,
                        provider TEXT NOT NULL,
                        last_synced TEXT NOT NULL,
                        sync_hash TEXT NOT NULL,
                        local_hash TEXT,
                        remote_hash TEXT,
                        created_at TEXT NOT NULL,
                        sync_count INTEGER DEFAULT 0,
                        last_error TEXT,
                        UNIQUE(todo_id, provider),
                        UNIQUE(external_id, provider)
                    )
                """)
                
                # Create sync_conflicts table
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS sync_conflicts (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        todo_id INTEGER NOT NULL,
                        provider TEXT NOT NULL,
                        conflict_type TEXT NOT NULL,
                        local_todo TEXT,  -- JSON serialized Todo
                        remote_item TEXT, -- JSON serialized ExternalTodoItem
                        local_changes TEXT, -- JSON serialized dict
                        remote_changes TEXT, -- JSON serialized dict
                        detected_at TEXT NOT NULL,
                        resolved BOOLEAN DEFAULT FALSE,
                        resolution TEXT,
                        resolved_at TEXT,
                        UNIQUE(todo_id, provider)
                    )
                """)
                
                # Create indexes for better performance
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_mappings_todo_id 
                    ON sync_mappings(todo_id)
                """)
                
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_mappings_provider 
                    ON sync_mappings(provider)
                """)
                
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_mappings_external_id 
                    ON sync_mappings(external_id, provider)
                """)
                
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_conflicts_todo_id 
                    ON sync_conflicts(todo_id)
                """)
                
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_conflicts_provider 
                    ON sync_conflicts(provider)
                """)
                
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_conflicts_resolved 
                    ON sync_conflicts(resolved)
                """)
                
                conn.commit()
                self.logger.debug(f"Initialized sync mapping database at {self.db_path}")
                
        except Exception as e:
            self.logger.error(f"Failed to initialize database: {e}")
            raise
    
    # Sync Mapping Operations
    
    async def save_mapping(self, mapping: SyncMapping):
        """Save a sync mapping to the database.
        
        Args:
            mapping: SyncMapping to save
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO sync_mappings 
                    (todo_id, external_id, provider, last_synced, sync_hash, 
                     local_hash, remote_hash, created_at, sync_count, last_error)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    mapping.todo_id,
                    mapping.external_id,
                    mapping.provider.value,
                    mapping.last_synced.isoformat(),
                    mapping.sync_hash,
                    mapping.local_hash,
                    mapping.remote_hash,
                    mapping.created_at.isoformat(),
                    mapping.sync_count,
                    mapping.last_error
                ))
                conn.commit()
                self.logger.debug(f"Saved mapping for todo {mapping.todo_id} -> {mapping.external_id}")
                
        except Exception as e:
            self.logger.error(f"Failed to save mapping: {e}")
            raise
    
    async def get_mapping(self, todo_id: int, provider: AppSyncProvider) -> Optional[SyncMapping]:
        """Get sync mapping for a specific todo and provider.
        
        Args:
            todo_id: Local todo ID
            provider: Sync provider
            
        Returns:
            SyncMapping if found, None otherwise
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute("""
                    SELECT * FROM sync_mappings 
                    WHERE todo_id = ? AND provider = ?
                """, (todo_id, provider.value))
                
                row = cursor.fetchone()
                if row:
                    return self._row_to_mapping(row)
                return None
                
        except Exception as e:
            self.logger.error(f"Failed to get mapping: {e}")
            return None
    
    async def get_mapping_by_external_id(self, external_id: str, provider: AppSyncProvider) -> Optional[SyncMapping]:
        """Get sync mapping by external ID and provider.
        
        Args:
            external_id: External item ID
            provider: Sync provider
            
        Returns:
            SyncMapping if found, None otherwise
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute("""
                    SELECT * FROM sync_mappings 
                    WHERE external_id = ? AND provider = ?
                """, (external_id, provider.value))
                
                row = cursor.fetchone()
                if row:
                    return self._row_to_mapping(row)
                return None
                
        except Exception as e:
            self.logger.error(f"Failed to get mapping by external ID: {e}")
            return None
    
    async def get_mappings_for_provider(self, provider: AppSyncProvider) -> List[SyncMapping]:
        """Get all sync mappings for a provider.
        
        Args:
            provider: Sync provider
            
        Returns:
            List of sync mappings
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute("""
                    SELECT * FROM sync_mappings 
                    WHERE provider = ?
                    ORDER BY last_synced DESC
                """, (provider.value,))
                
                return [self._row_to_mapping(row) for row in cursor.fetchall()]
                
        except Exception as e:
            self.logger.error(f"Failed to get mappings for provider: {e}")
            return []
    
    async def get_mappings_for_todo(self, todo_id: int) -> List[SyncMapping]:
        """Get all sync mappings for a specific todo.
        
        Args:
            todo_id: Local todo ID
            
        Returns:
            List of sync mappings
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute("""
                    SELECT * FROM sync_mappings 
                    WHERE todo_id = ?
                    ORDER BY last_synced DESC
                """, (todo_id,))
                
                return [self._row_to_mapping(row) for row in cursor.fetchall()]
                
        except Exception as e:
            self.logger.error(f"Failed to get mappings for todo: {e}")
            return []
    
    async def delete_mapping(self, todo_id: int, provider: AppSyncProvider) -> bool:
        """Delete a sync mapping.
        
        Args:
            todo_id: Local todo ID
            provider: Sync provider
            
        Returns:
            True if mapping was deleted, False if not found
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("""
                    DELETE FROM sync_mappings 
                    WHERE todo_id = ? AND provider = ?
                """, (todo_id, provider.value))
                
                conn.commit()
                deleted = cursor.rowcount > 0
                if deleted:
                    self.logger.debug(f"Deleted mapping for todo {todo_id}, provider {provider.value}")
                return deleted
                
        except Exception as e:
            self.logger.error(f"Failed to delete mapping: {e}")
            return False
    
    async def delete_mappings_for_todo(self, todo_id: int) -> int:
        """Delete all sync mappings for a todo.
        
        Args:
            todo_id: Local todo ID
            
        Returns:
            Number of mappings deleted
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("""
                    DELETE FROM sync_mappings 
                    WHERE todo_id = ?
                """, (todo_id,))
                
                conn.commit()
                deleted_count = cursor.rowcount
                if deleted_count > 0:
                    self.logger.debug(f"Deleted {deleted_count} mappings for todo {todo_id}")
                return deleted_count
                
        except Exception as e:
            self.logger.error(f"Failed to delete mappings for todo: {e}")
            return 0
    
    def _row_to_mapping(self, row: sqlite3.Row) -> SyncMapping:
        """Convert database row to SyncMapping object."""
        return SyncMapping(
            todo_id=row['todo_id'],
            external_id=row['external_id'],
            provider=AppSyncProvider(row['provider']),
            last_synced=datetime.fromisoformat(row['last_synced']),
            sync_hash=row['sync_hash'],
            local_hash=row['local_hash'],
            remote_hash=row['remote_hash'],
            created_at=datetime.fromisoformat(row['created_at']),
            sync_count=row['sync_count'],
            last_error=row['last_error']
        )
    
    # Sync Conflict Operations
    
    async def save_conflict(self, conflict: SyncConflict):
        """Save a sync conflict to the database.
        
        Args:
            conflict: SyncConflict to save
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO sync_conflicts 
                    (todo_id, provider, conflict_type, local_todo, remote_item,
                     local_changes, remote_changes, detected_at, resolved, 
                     resolution, resolved_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    conflict.todo_id,
                    conflict.provider.value,
                    conflict.conflict_type.value,
                    json.dumps(conflict.local_todo.to_dict()) if conflict.local_todo else None,
                    json.dumps(conflict.remote_item.to_dict()) if conflict.remote_item else None,
                    json.dumps(conflict.local_changes),
                    json.dumps(conflict.remote_changes),
                    conflict.detected_at.isoformat(),
                    conflict.resolved,
                    conflict.resolution,
                    conflict.resolved_at.isoformat() if conflict.resolved_at else None
                ))
                conn.commit()
                self.logger.debug(f"Saved conflict for todo {conflict.todo_id}, provider {conflict.provider.value}")
                
        except Exception as e:
            self.logger.error(f"Failed to save conflict: {e}")
            raise
    
    async def get_conflict(self, todo_id: int, provider: AppSyncProvider) -> Optional[SyncConflict]:
        """Get sync conflict for a specific todo and provider.
        
        Args:
            todo_id: Local todo ID
            provider: Sync provider
            
        Returns:
            SyncConflict if found, None otherwise
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute("""
                    SELECT * FROM sync_conflicts 
                    WHERE todo_id = ? AND provider = ?
                """, (todo_id, provider.value))
                
                row = cursor.fetchone()
                if row:
                    return self._row_to_conflict(row)
                return None
                
        except Exception as e:
            self.logger.error(f"Failed to get conflict: {e}")
            return None
    
    async def get_conflicts_for_provider(self, provider: AppSyncProvider, resolved: Optional[bool] = None) -> List[SyncConflict]:
        """Get sync conflicts for a provider.
        
        Args:
            provider: Sync provider
            resolved: Filter by resolved status (None for all)
            
        Returns:
            List of sync conflicts
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                
                if resolved is None:
                    cursor = conn.execute("""
                        SELECT * FROM sync_conflicts 
                        WHERE provider = ?
                        ORDER BY detected_at DESC
                    """, (provider.value,))
                else:
                    cursor = conn.execute("""
                        SELECT * FROM sync_conflicts 
                        WHERE provider = ? AND resolved = ?
                        ORDER BY detected_at DESC
                    """, (provider.value, resolved))
                
                return [self._row_to_conflict(row) for row in cursor.fetchall()]
                
        except Exception as e:
            self.logger.error(f"Failed to get conflicts for provider: {e}")
            return []
    
    async def get_all_conflicts(self, resolved: Optional[bool] = None) -> List[SyncConflict]:
        """Get all sync conflicts.
        
        Args:
            resolved: Filter by resolved status (None for all)
            
        Returns:
            List of sync conflicts
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                
                if resolved is None:
                    cursor = conn.execute("""
                        SELECT * FROM sync_conflicts 
                        ORDER BY detected_at DESC
                    """)
                else:
                    cursor = conn.execute("""
                        SELECT * FROM sync_conflicts 
                        WHERE resolved = ?
                        ORDER BY detected_at DESC
                    """, (resolved,))
                
                return [self._row_to_conflict(row) for row in cursor.fetchall()]
                
        except Exception as e:
            self.logger.error(f"Failed to get all conflicts: {e}")
            return []
    
    async def delete_conflict(self, todo_id: int, provider: AppSyncProvider) -> bool:
        """Delete a sync conflict.
        
        Args:
            todo_id: Local todo ID
            provider: Sync provider
            
        Returns:
            True if conflict was deleted, False if not found
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("""
                    DELETE FROM sync_conflicts 
                    WHERE todo_id = ? AND provider = ?
                """, (todo_id, provider.value))
                
                conn.commit()
                deleted = cursor.rowcount > 0
                if deleted:
                    self.logger.debug(f"Deleted conflict for todo {todo_id}, provider {provider.value}")
                return deleted
                
        except Exception as e:
            self.logger.error(f"Failed to delete conflict: {e}")
            return False
    
    async def delete_resolved_conflicts(self, older_than_days: int = 30) -> int:
        """Delete resolved conflicts older than specified days.
        
        Args:
            older_than_days: Delete conflicts resolved more than this many days ago
            
        Returns:
            Number of conflicts deleted
        """
        try:
            cutoff_date = datetime.now(timezone.utc).replace(
                hour=0, minute=0, second=0, microsecond=0
            ) - timedelta(days=older_than_days)
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("""
                    DELETE FROM sync_conflicts 
                    WHERE resolved = TRUE AND resolved_at < ?
                """, (cutoff_date.isoformat(),))
                
                conn.commit()
                deleted_count = cursor.rowcount
                if deleted_count > 0:
                    self.logger.debug(f"Deleted {deleted_count} resolved conflicts older than {older_than_days} days")
                return deleted_count
                
        except Exception as e:
            self.logger.error(f"Failed to delete resolved conflicts: {e}")
            return 0
    
    def _row_to_conflict(self, row: sqlite3.Row) -> SyncConflict:
        """Convert database row to SyncConflict object."""
        # Import here to avoid circular imports
        from ..domain import Todo
        from .app_sync_models import ExternalTodoItem
        
        local_todo = None
        if row['local_todo']:
            local_todo_data = json.loads(row['local_todo'])
            local_todo = Todo.from_dict(local_todo_data)
        
        remote_item = None
        if row['remote_item']:
            remote_item_data = json.loads(row['remote_item'])
            remote_item = ExternalTodoItem.from_dict(remote_item_data)
        
        return SyncConflict(
            todo_id=row['todo_id'],
            provider=AppSyncProvider(row['provider']),
            conflict_type=ConflictType(row['conflict_type']),
            local_todo=local_todo,
            remote_item=remote_item,
            local_changes=json.loads(row['local_changes']),
            remote_changes=json.loads(row['remote_changes']),
            detected_at=datetime.fromisoformat(row['detected_at']),
            resolved=bool(row['resolved']),
            resolution=row['resolution'],
            resolved_at=datetime.fromisoformat(row['resolved_at']) if row['resolved_at'] else None
        )
    
    # Utility Methods
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get database statistics.
        
        Returns:
            Dictionary with database statistics
        """
        try:
            stats = {}
            
            with sqlite3.connect(self.db_path) as conn:
                # Mapping counts
                cursor = conn.execute("SELECT COUNT(*) FROM sync_mappings")
                stats['total_mappings'] = cursor.fetchone()[0]
                
                # Mappings by provider
                cursor = conn.execute("""
                    SELECT provider, COUNT(*) 
                    FROM sync_mappings 
                    GROUP BY provider
                """)
                stats['mappings_by_provider'] = dict(cursor.fetchall())
                
                # Conflict counts
                cursor = conn.execute("SELECT COUNT(*) FROM sync_conflicts")
                stats['total_conflicts'] = cursor.fetchone()[0]
                
                cursor = conn.execute("SELECT COUNT(*) FROM sync_conflicts WHERE resolved = FALSE")
                stats['unresolved_conflicts'] = cursor.fetchone()[0]
                
                # Conflicts by provider
                cursor = conn.execute("""
                    SELECT provider, COUNT(*) 
                    FROM sync_conflicts 
                    WHERE resolved = FALSE
                    GROUP BY provider
                """)
                stats['unresolved_conflicts_by_provider'] = dict(cursor.fetchall())
            
            return stats
            
        except Exception as e:
            self.logger.error(f"Failed to get stats: {e}")
            return {}
    
    async def cleanup_orphaned_mappings(self, existing_todo_ids: List[int]) -> int:
        """Clean up mappings for todos that no longer exist.
        
        Args:
            existing_todo_ids: List of todo IDs that currently exist
            
        Returns:
            Number of orphaned mappings deleted
        """
        try:
            if not existing_todo_ids:
                return 0
            
            # Create placeholders for the IN clause
            placeholders = ','.join('?' * len(existing_todo_ids))
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(f"""
                    DELETE FROM sync_mappings 
                    WHERE todo_id NOT IN ({placeholders})
                """, existing_todo_ids)
                
                conn.commit()
                deleted_count = cursor.rowcount
                if deleted_count > 0:
                    self.logger.info(f"Cleaned up {deleted_count} orphaned sync mappings")
                return deleted_count
                
        except Exception as e:
            self.logger.error(f"Failed to cleanup orphaned mappings: {e}")
            return 0
    
    def close(self):
        """Close the database connection (for cleanup)."""
        # SQLite connections are automatically managed in with statements
        pass