"""Database layer for web app user management."""

import sqlite3
import json
import logging
from pathlib import Path
from typing import Optional, List
from datetime import datetime, timezone

from .models import User, Session


logger = logging.getLogger(__name__)


class UserDatabase:
    """SQLite database for user management."""
    
    def __init__(self, db_path: Optional[Path] = None):
        """Initialize user database.
        
        Args:
            db_path: Path to SQLite database file
        """
        if db_path is None:
            from ...config import get_config_dir
            config_dir = get_config_dir()
            config_dir.mkdir(exist_ok=True)
            db_path = config_dir / "webapp.db"
        
        self.db_path = db_path
        self.logger = logging.getLogger(__name__)
        self._init_database()
    
    def _init_database(self):
        """Initialize database schema."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("PRAGMA foreign_keys = ON")
                
                # Users table
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS users (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        username TEXT UNIQUE NOT NULL,
                        email TEXT UNIQUE NOT NULL,
                        password_hash TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        last_login TEXT,
                        is_active BOOLEAN DEFAULT TRUE,
                        settings TEXT DEFAULT '{}'
                    )
                """)
                
                # Sessions table
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS sessions (
                        id TEXT PRIMARY KEY,
                        user_id INTEGER NOT NULL,
                        token_hash TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        expires_at TEXT NOT NULL,
                        is_refresh_token BOOLEAN DEFAULT FALSE,
                        device_info TEXT,
                        ip_address TEXT,
                        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                    )
                """)
                
                # Indexes
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_users_email 
                    ON users(email)
                """)
                
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_users_username 
                    ON users(username)
                """)
                
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_sessions_user_id 
                    ON sessions(user_id)
                """)
                
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_sessions_expires 
                    ON sessions(expires_at)
                """)
                
                conn.commit()
                self.logger.debug(f"Initialized user database at {self.db_path}")
                
        except Exception as e:
            self.logger.error(f"Failed to initialize database: {e}")
            raise
    
    # User Operations
    
    def create_user(self, username: str, email: str, password_hash: str, 
                   settings: Optional[dict] = None) -> User:
        """Create a new user.
        
        Args:
            username: Unique username
            email: Unique email address
            password_hash: Hashed password
            settings: Optional user settings
            
        Returns:
            Created User instance
            
        Raises:
            ValueError: If username or email already exists
        """
        try:
            created_at = datetime.now(timezone.utc)
            settings_json = json.dumps(settings or {})
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("""
                    INSERT INTO users (username, email, password_hash, created_at, settings)
                    VALUES (?, ?, ?, ?, ?)
                """, (username, email, password_hash, created_at.isoformat(), settings_json))
                
                conn.commit()
                user_id = cursor.lastrowid
                
                self.logger.info(f"Created user: {username} (id={user_id})")
                
                return User(
                    id=user_id,
                    username=username,
                    email=email,
                    password_hash=password_hash,
                    created_at=created_at,
                    settings=settings or {}
                )
                
        except sqlite3.IntegrityError as e:
            if 'username' in str(e):
                raise ValueError(f"Username '{username}' already exists")
            elif 'email' in str(e):
                raise ValueError(f"Email '{email}' already exists")
            raise
    
    def get_user_by_id(self, user_id: int) -> Optional[User]:
        """Get user by ID.
        
        Args:
            user_id: User ID
            
        Returns:
            User instance or None if not found
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute("""
                    SELECT * FROM users WHERE id = ?
                """, (user_id,))
                
                row = cursor.fetchone()
                if row:
                    return self._row_to_user(row)
                return None
                
        except Exception as e:
            self.logger.error(f"Failed to get user by id {user_id}: {e}")
            return None
    
    def get_user_by_username(self, username: str) -> Optional[User]:
        """Get user by username.
        
        Args:
            username: Username
            
        Returns:
            User instance or None if not found
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute("""
                    SELECT * FROM users WHERE username = ?
                """, (username,))
                
                row = cursor.fetchone()
                if row:
                    return self._row_to_user(row)
                return None
                
        except Exception as e:
            self.logger.error(f"Failed to get user by username {username}: {e}")
            return None
    
    def get_user_by_email(self, email: str) -> Optional[User]:
        """Get user by email.
        
        Args:
            email: Email address
            
        Returns:
            User instance or None if not found
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute("""
                    SELECT * FROM users WHERE email = ?
                """, (email,))
                
                row = cursor.fetchone()
                if row:
                    return self._row_to_user(row)
                return None
                
        except Exception as e:
            self.logger.error(f"Failed to get user by email {email}: {e}")
            return None
    
    def update_user(self, user: User) -> bool:
        """Update user information.
        
        Args:
            user: User instance with updated data
            
        Returns:
            True if successful
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    UPDATE users 
                    SET username = ?, email = ?, password_hash = ?, 
                        last_login = ?, is_active = ?, settings = ?
                    WHERE id = ?
                """, (
                    user.username,
                    user.email,
                    user.password_hash,
                    user.last_login.isoformat() if user.last_login else None,
                    user.is_active,
                    json.dumps(user.settings),
                    user.id
                ))
                
                conn.commit()
                self.logger.debug(f"Updated user {user.username} (id={user.id})")
                return True
                
        except Exception as e:
            self.logger.error(f"Failed to update user {user.id}: {e}")
            return False
    
    def update_last_login(self, user_id: int) -> bool:
        """Update user's last login timestamp.
        
        Args:
            user_id: User ID
            
        Returns:
            True if successful
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    UPDATE users SET last_login = ? WHERE id = ?
                """, (datetime.now(timezone.utc).isoformat(), user_id))
                
                conn.commit()
                return True
                
        except Exception as e:
            self.logger.error(f"Failed to update last login for user {user_id}: {e}")
            return False
    
    def list_users(self, limit: int = 100, offset: int = 0) -> List[User]:
        """List all users with pagination.
        
        Args:
            limit: Maximum number of users to return
            offset: Number of users to skip
            
        Returns:
            List of User instances
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute("""
                    SELECT * FROM users 
                    ORDER BY created_at DESC
                    LIMIT ? OFFSET ?
                """, (limit, offset))
                
                return [self._row_to_user(row) for row in cursor.fetchall()]
                
        except Exception as e:
            self.logger.error(f"Failed to list users: {e}")
            return []
    
    def _row_to_user(self, row: sqlite3.Row) -> User:
        """Convert database row to User instance.
        
        Args:
            row: SQLite row
            
        Returns:
            User instance
        """
        return User(
            id=row['id'],
            username=row['username'],
            email=row['email'],
            password_hash=row['password_hash'],
            created_at=datetime.fromisoformat(row['created_at']),
            last_login=datetime.fromisoformat(row['last_login']) if row['last_login'] else None,
            is_active=bool(row['is_active']),
            settings=json.loads(row['settings'])
        )
    
    # Session Operations
    
    def create_session(self, session: Session) -> bool:
        """Create a new session.
        
        Args:
            session: Session instance
            
        Returns:
            True if successful
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    INSERT INTO sessions 
                    (id, user_id, token_hash, created_at, expires_at, 
                     is_refresh_token, device_info, ip_address)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    session.id,
                    session.user_id,
                    session.token_hash,
                    session.created_at.isoformat(),
                    session.expires_at.isoformat(),
                    session.is_refresh_token,
                    session.device_info,
                    session.ip_address
                ))
                
                conn.commit()
                self.logger.debug(f"Created session {session.id} for user {session.user_id}")
                return True
                
        except Exception as e:
            self.logger.error(f"Failed to create session: {e}")
            return False
    
    def get_session(self, session_id: str) -> Optional[Session]:
        """Get session by ID.
        
        Args:
            session_id: Session ID
            
        Returns:
            Session instance or None if not found
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute("""
                    SELECT * FROM sessions WHERE id = ?
                """, (session_id,))
                
                row = cursor.fetchone()
                if row:
                    return self._row_to_session(row)
                return None
                
        except Exception as e:
            self.logger.error(f"Failed to get session {session_id}: {e}")
            return None
    
    def get_user_sessions(self, user_id: int) -> List[Session]:
        """Get all active sessions for a user.
        
        Args:
            user_id: User ID
            
        Returns:
            List of Session instances
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute("""
                    SELECT * FROM sessions 
                    WHERE user_id = ? AND expires_at > ?
                    ORDER BY created_at DESC
                """, (user_id, datetime.now(timezone.utc).isoformat()))
                
                return [self._row_to_session(row) for row in cursor.fetchall()]
                
        except Exception as e:
            self.logger.error(f"Failed to get sessions for user {user_id}: {e}")
            return []
    
    def delete_session(self, session_id: str) -> bool:
        """Delete a session.
        
        Args:
            session_id: Session ID
            
        Returns:
            True if successful
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    DELETE FROM sessions WHERE id = ?
                """, (session_id,))
                
                conn.commit()
                self.logger.debug(f"Deleted session {session_id}")
                return True
                
        except Exception as e:
            self.logger.error(f"Failed to delete session {session_id}: {e}")
            return False
    
    def delete_user_sessions(self, user_id: int) -> int:
        """Delete all sessions for a user.
        
        Args:
            user_id: User ID
            
        Returns:
            Number of sessions deleted
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("""
                    DELETE FROM sessions WHERE user_id = ?
                """, (user_id,))
                
                conn.commit()
                deleted_count = cursor.rowcount
                self.logger.debug(f"Deleted {deleted_count} sessions for user {user_id}")
                return deleted_count
                
        except Exception as e:
            self.logger.error(f"Failed to delete sessions for user {user_id}: {e}")
            return 0
    
    def cleanup_expired_sessions(self) -> int:
        """Delete all expired sessions.
        
        Returns:
            Number of sessions deleted
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("""
                    DELETE FROM sessions WHERE expires_at < ?
                """, (datetime.now(timezone.utc).isoformat(),))
                
                conn.commit()
                deleted_count = cursor.rowcount
                if deleted_count > 0:
                    self.logger.info(f"Cleaned up {deleted_count} expired sessions")
                return deleted_count
                
        except Exception as e:
            self.logger.error(f"Failed to cleanup expired sessions: {e}")
            return 0
    
    def _row_to_session(self, row: sqlite3.Row) -> Session:
        """Convert database row to Session instance.
        
        Args:
            row: SQLite row
            
        Returns:
            Session instance
        """
        return Session(
            id=row['id'],
            user_id=row['user_id'],
            token_hash=row['token_hash'],
            created_at=datetime.fromisoformat(row['created_at']),
            expires_at=datetime.fromisoformat(row['expires_at']),
            is_refresh_token=bool(row['is_refresh_token']),
            device_info=row['device_info'],
            ip_address=row['ip_address']
        )
    
    def close(self):
        """Close database connection (cleanup)."""
        # SQLite connections are managed per-operation
        pass


# Global database instance
_db_instance: Optional[UserDatabase] = None


def get_user_db() -> UserDatabase:
    """Get global user database instance.
    
    Returns:
        UserDatabase instance
    """
    global _db_instance
    
    if _db_instance is None:
        _db_instance = UserDatabase()
    
    return _db_instance


def reset_user_db():
    """Reset global database instance (for testing)."""
    global _db_instance
    _db_instance = None
