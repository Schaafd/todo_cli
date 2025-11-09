"""
Database layer for user and session management

This module provides SQLite-based storage for users and sessions with:
- User CRUD operations with password hashing
- Session management with automatic cleanup
- Database migrations and initialization
- Thread-safe connection pooling
"""

import sqlite3
import secrets
import bcrypt
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, asdict


def hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    if not isinstance(password, str):
        raise ValueError("password must be a string")
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


# ============================================================================
# Configuration
# ============================================================================

def get_db_path() -> Path:
    """Get database file path"""
    todo_dir = Path.home() / ".todo"
    todo_dir.mkdir(exist_ok=True)
    return todo_dir / "webapp.db"


# ============================================================================
# Data Models
# ============================================================================

@dataclass
class User:
    """User data model"""
    id: str
    username: str
    email: str
    password_hash: str
    created_at: datetime
    updated_at: datetime
    is_active: bool = True
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        data = asdict(self)
        data['created_at'] = self.created_at.isoformat()
        data['updated_at'] = self.updated_at.isoformat()
        return data


@dataclass
class Session:
    """Session data model"""
    id: str
    user_id: str
    token: str
    created_at: datetime
    expires_at: datetime
    is_valid: bool = True
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        data = asdict(self)
        data['created_at'] = self.created_at.isoformat()
        data['expires_at'] = self.expires_at.isoformat()
        return data
    
    def is_expired(self) -> bool:
        """Check if session is expired"""
        return datetime.utcnow() > self.expires_at


# ============================================================================
# Database Manager
# ============================================================================

class DatabaseManager:
    """Manages database connections and operations"""
    
    def __init__(self, db_path: Optional[Path] = None):
        """Initialize database manager
        
        Args:
            db_path: Optional custom database path
        """
        self.db_path = db_path or get_db_path()
        self._initialize_db()
    
    @contextmanager
    def get_connection(self):
        """Get database connection with context manager
        
        Yields:
            sqlite3.Connection: Database connection
        """
        conn = sqlite3.connect(
            self.db_path,
            detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES
        )
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
    
    def _initialize_db(self):
        """Initialize database schema"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Create users table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY,
                    username TEXT UNIQUE NOT NULL,
                    email TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    is_active BOOLEAN NOT NULL DEFAULT 1
                )
            """)
            
            # Create sessions table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    token TEXT UNIQUE NOT NULL,
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    expires_at TIMESTAMP NOT NULL,
                    is_valid BOOLEAN NOT NULL DEFAULT 1,
                    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
                )
            """)
            
            # Create indexes
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_users_username ON users (username)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_users_email ON users (email)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_sessions_token ON sessions (token)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON sessions (user_id)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_sessions_expires_at ON sessions (expires_at)"
            )
    
    # ========================================================================
    # User Operations
    # ========================================================================
    
    def create_user(
        self,
        username: str,
        email: str,
        password: str
    ) -> User:
        """Create a new user
        
        Args:
            username: User's username
            email: User's email
            password: Plain text password (will be hashed)
            
        Returns:
            User: Created user object
            
        Raises:
            ValueError: If username or email already exists
        """
        user_id = secrets.token_urlsafe(16)
        password_hash = hash_password(password)
        now = datetime.utcnow()
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            try:
                cursor.execute("""
                    INSERT INTO users (id, username, email, password_hash, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (user_id, username, email, password_hash, now, now))
            except sqlite3.IntegrityError as e:
                if "username" in str(e):
                    raise ValueError(f"Username '{username}' already exists")
                elif "email" in str(e):
                    raise ValueError(f"Email '{email}' already exists")
                raise
            
            return User(
                id=user_id,
                username=username,
                email=email,
                password_hash=password_hash,
                created_at=now,
                updated_at=now,
                is_active=True
            )
    
    def get_user_by_id(self, user_id: str) -> Optional[User]:
        """Get user by ID
        
        Args:
            user_id: User ID
            
        Returns:
            Optional[User]: User object or None
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM users WHERE id = ? AND is_active = 1",
                (user_id,)
            )
            row = cursor.fetchone()
            
            if not row:
                return None
            
            return User(
                id=row['id'],
                username=row['username'],
                email=row['email'],
                password_hash=row['password_hash'],
                created_at=row['created_at'],
                updated_at=row['updated_at'],
                is_active=bool(row['is_active'])
            )
    
    def get_user_by_username(self, username: str) -> Optional[User]:
        """Get user by username
        
        Args:
            username: Username
            
        Returns:
            Optional[User]: User object or None
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM users WHERE username = ? AND is_active = 1",
                (username,)
            )
            row = cursor.fetchone()
            
            if not row:
                return None
            
            return User(
                id=row['id'],
                username=row['username'],
                email=row['email'],
                password_hash=row['password_hash'],
                created_at=row['created_at'],
                updated_at=row['updated_at'],
                is_active=bool(row['is_active'])
            )
    
    def get_user_by_email(self, email: str) -> Optional[User]:
        """Get user by email
        
        Args:
            email: Email address
            
        Returns:
            Optional[User]: User object or None
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM users WHERE email = ? AND is_active = 1",
                (email,)
            )
            row = cursor.fetchone()
            
            if not row:
                return None
            
            return User(
                id=row['id'],
                username=row['username'],
                email=row['email'],
                password_hash=row['password_hash'],
                created_at=row['created_at'],
                updated_at=row['updated_at'],
                is_active=bool(row['is_active'])
            )
    
    def update_user(
        self,
        user_id: str,
        email: Optional[str] = None,
        password: Optional[str] = None
    ) -> bool:
        """Update user information
        
        Args:
            user_id: User ID
            email: New email (optional)
            password: New password (optional, will be hashed)
            
        Returns:
            bool: True if updated successfully
        """
        updates = []
        params = []
        
        if email:
            updates.append("email = ?")
            params.append(email)
        
        if password:
            updates.append("password_hash = ?")
            params.append(hash_password(password))
        
        if not updates:
            return False
        
        updates.append("updated_at = ?")
        params.append(datetime.utcnow())
        params.append(user_id)
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                f"UPDATE users SET {', '.join(updates)} WHERE id = ?",
                params
            )
            return cursor.rowcount > 0
    
    def delete_user(self, user_id: str) -> bool:
        """Soft delete user (mark as inactive)
        
        Args:
            user_id: User ID
            
        Returns:
            bool: True if deleted successfully
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE users SET is_active = 0, updated_at = ? WHERE id = ?",
                (datetime.utcnow(), user_id)
            )
            return cursor.rowcount > 0
    
    def list_users(self, limit: int = 100, offset: int = 0) -> List[User]:
        """List all active users
        
        Args:
            limit: Maximum number of users to return
            offset: Number of users to skip
            
        Returns:
            List[User]: List of user objects
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM users WHERE is_active = 1 ORDER BY created_at DESC LIMIT ? OFFSET ?",
                (limit, offset)
            )
            rows = cursor.fetchall()
            
            return [
                User(
                    id=row['id'],
                    username=row['username'],
                    email=row['email'],
                    password_hash=row['password_hash'],
                    created_at=row['created_at'],
                    updated_at=row['updated_at'],
                    is_active=bool(row['is_active'])
                )
                for row in rows
            ]
    
    # ========================================================================
    # Session Operations
    # ========================================================================
    
    def create_session(
        self,
        user_id: str,
        expires_in_days: int = 7
    ) -> Session:
        """Create a new session
        
        Args:
            user_id: User ID
            expires_in_days: Session expiration in days
            
        Returns:
            Session: Created session object
        """
        session_id = secrets.token_urlsafe(16)
        token = secrets.token_urlsafe(32)
        now = datetime.utcnow()
        expires_at = now + timedelta(days=expires_in_days)
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO sessions (id, user_id, token, created_at, expires_at)
                VALUES (?, ?, ?, ?, ?)
            """, (session_id, user_id, token, now, expires_at))
            
            return Session(
                id=session_id,
                user_id=user_id,
                token=token,
                created_at=now,
                expires_at=expires_at,
                is_valid=True
            )
    
    def get_session_by_token(self, token: str) -> Optional[Session]:
        """Get session by token
        
        Args:
            token: Session token
            
        Returns:
            Optional[Session]: Session object or None
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM sessions WHERE token = ? AND is_valid = 1",
                (token,)
            )
            row = cursor.fetchone()
            
            if not row:
                return None
            
            return Session(
                id=row['id'],
                user_id=row['user_id'],
                token=row['token'],
                created_at=row['created_at'],
                expires_at=row['expires_at'],
                is_valid=bool(row['is_valid'])
            )
    
    def invalidate_session(self, token: str) -> bool:
        """Invalidate a session
        
        Args:
            token: Session token
            
        Returns:
            bool: True if invalidated successfully
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE sessions SET is_valid = 0 WHERE token = ?",
                (token,)
            )
            return cursor.rowcount > 0
    
    def invalidate_user_sessions(self, user_id: str) -> int:
        """Invalidate all sessions for a user
        
        Args:
            user_id: User ID
            
        Returns:
            int: Number of sessions invalidated
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE sessions SET is_valid = 0 WHERE user_id = ?",
                (user_id,)
            )
            return cursor.rowcount
    
    def cleanup_expired_sessions(self) -> int:
        """Remove expired sessions
        
        Returns:
            int: Number of sessions deleted
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM sessions WHERE expires_at < ?",
                (datetime.utcnow(),)
            )
            return cursor.rowcount
    
    def get_user_sessions(self, user_id: str) -> List[Session]:
        """Get all valid sessions for a user
        
        Args:
            user_id: User ID
            
        Returns:
            List[Session]: List of session objects
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM sessions WHERE user_id = ? AND is_valid = 1 ORDER BY created_at DESC",
                (user_id,)
            )
            rows = cursor.fetchall()
            
            return [
                Session(
                    id=row['id'],
                    user_id=row['user_id'],
                    token=row['token'],
                    created_at=row['created_at'],
                    expires_at=row['expires_at'],
                    is_valid=bool(row['is_valid'])
                )
                for row in rows
            ]


# ============================================================================
# Singleton Instance
# ============================================================================

_db_manager: Optional[DatabaseManager] = None


def get_db() -> DatabaseManager:
    """Get singleton database manager instance
    
    Returns:
        DatabaseManager: Database manager instance
    """
    global _db_manager
    if _db_manager is None:
        _db_manager = DatabaseManager()
    return _db_manager


def reset_db():
    """Reset database manager (useful for testing)"""
    global _db_manager
    _db_manager = None
