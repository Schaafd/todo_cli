"""
Unit tests for database module
"""

import pytest
import tempfile
from pathlib import Path
from datetime import datetime, timedelta

from src.todo_cli.webapp.database import (
    DatabaseManager,
    User,
    Session,
    get_db_path,
)


@pytest.fixture
def temp_db():
    """Create a temporary database for testing"""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = Path(f.name)
    
    db = DatabaseManager(db_path)
    yield db
    
    # Cleanup
    if db_path.exists():
        db_path.unlink()


@pytest.fixture
def sample_user(temp_db):
    """Create a sample user for testing"""
    return temp_db.create_user(
        username="testuser",
        email="test@example.com",
        password="password123"
    )


class TestDatabaseConfiguration:
    """Test database configuration"""
    
    def test_get_db_path(self):
        """Test getting database path"""
        db_path = get_db_path()
        assert db_path.parent.name == ".todo"
        assert db_path.name == "webapp.db"
    
    def test_custom_db_path(self):
        """Test custom database path"""
        with tempfile.NamedTemporaryFile(suffix=".db") as f:
            custom_path = Path(f.name)
            db = DatabaseManager(custom_path)
            assert db.db_path == custom_path


class TestUserOperations:
    """Test user CRUD operations"""
    
    def test_create_user(self, temp_db):
        """Test creating a new user"""
        user = temp_db.create_user(
            username="john",
            email="john@example.com",
            password="securepass123"
        )
        
        assert user.id is not None
        assert user.username == "john"
        assert user.email == "john@example.com"
        assert user.password_hash != "securepass123"  # Should be hashed
        assert user.is_active is True
        assert isinstance(user.created_at, datetime)
        assert isinstance(user.updated_at, datetime)
    
    def test_create_duplicate_username(self, temp_db, sample_user):
        """Test creating user with duplicate username"""
        with pytest.raises(ValueError, match="Username .* already exists"):
            temp_db.create_user(
                username="testuser",  # Duplicate
                email="different@example.com",
                password="password123"
            )
    
    def test_create_duplicate_email(self, temp_db, sample_user):
        """Test creating user with duplicate email"""
        with pytest.raises(ValueError, match="Email .* already exists"):
            temp_db.create_user(
                username="differentuser",
                email="test@example.com",  # Duplicate
                password="password123"
            )
    
    def test_get_user_by_id(self, temp_db, sample_user):
        """Test getting user by ID"""
        user = temp_db.get_user_by_id(sample_user.id)
        
        assert user is not None
        assert user.id == sample_user.id
        assert user.username == sample_user.username
        assert user.email == sample_user.email
    
    def test_get_nonexistent_user_by_id(self, temp_db):
        """Test getting nonexistent user by ID"""
        user = temp_db.get_user_by_id("nonexistent_id")
        assert user is None
    
    def test_get_user_by_username(self, temp_db, sample_user):
        """Test getting user by username"""
        user = temp_db.get_user_by_username("testuser")
        
        assert user is not None
        assert user.id == sample_user.id
        assert user.username == "testuser"
    
    def test_get_user_by_email(self, temp_db, sample_user):
        """Test getting user by email"""
        user = temp_db.get_user_by_email("test@example.com")
        
        assert user is not None
        assert user.id == sample_user.id
        assert user.email == "test@example.com"
    
    def test_update_user_email(self, temp_db, sample_user):
        """Test updating user email"""
        success = temp_db.update_user(
            sample_user.id,
            email="newemail@example.com"
        )
        
        assert success is True
        
        user = temp_db.get_user_by_id(sample_user.id)
        assert user.email == "newemail@example.com"
        assert user.updated_at > sample_user.updated_at
    
    def test_update_user_password(self, temp_db, sample_user):
        """Test updating user password"""
        old_hash = sample_user.password_hash
        
        success = temp_db.update_user(
            sample_user.id,
            password="newpassword123"
        )
        
        assert success is True
        
        user = temp_db.get_user_by_id(sample_user.id)
        assert user.password_hash != old_hash
        assert user.password_hash != "newpassword123"  # Should be hashed
    
    def test_update_user_no_changes(self, temp_db, sample_user):
        """Test updating user with no changes"""
        success = temp_db.update_user(sample_user.id)
        assert success is False
    
    def test_delete_user(self, temp_db, sample_user):
        """Test soft deleting user"""
        success = temp_db.delete_user(sample_user.id)
        assert success is True
        
        # User should not be retrievable
        user = temp_db.get_user_by_id(sample_user.id)
        assert user is None
    
    def test_list_users(self, temp_db):
        """Test listing users"""
        # Create multiple users
        temp_db.create_user("user1", "user1@example.com", "pass123")
        temp_db.create_user("user2", "user2@example.com", "pass123")
        temp_db.create_user("user3", "user3@example.com", "pass123")
        
        users = temp_db.list_users()
        assert len(users) == 3
        
        # Test pagination
        users_page1 = temp_db.list_users(limit=2, offset=0)
        assert len(users_page1) == 2
        
        users_page2 = temp_db.list_users(limit=2, offset=2)
        assert len(users_page2) == 1
    
    def test_user_to_dict(self, sample_user):
        """Test user to_dict method"""
        user_dict = sample_user.to_dict()
        
        assert user_dict['id'] == sample_user.id
        assert user_dict['username'] == sample_user.username
        assert user_dict['email'] == sample_user.email
        assert isinstance(user_dict['created_at'], str)
        assert isinstance(user_dict['updated_at'], str)


class TestSessionOperations:
    """Test session operations"""
    
    def test_create_session(self, temp_db, sample_user):
        """Test creating a session"""
        session = temp_db.create_session(sample_user.id)
        
        assert session.id is not None
        assert session.user_id == sample_user.id
        assert session.token is not None
        assert len(session.token) > 20  # Should be a long token
        assert session.is_valid is True
        assert isinstance(session.created_at, datetime)
        assert isinstance(session.expires_at, datetime)
        assert session.expires_at > session.created_at
    
    def test_create_session_custom_expiration(self, temp_db, sample_user):
        """Test creating session with custom expiration"""
        session = temp_db.create_session(sample_user.id, expires_in_days=30)
        
        days_diff = (session.expires_at - session.created_at).days
        assert days_diff == 30
    
    def test_get_session_by_token(self, temp_db, sample_user):
        """Test getting session by token"""
        created_session = temp_db.create_session(sample_user.id)
        
        retrieved_session = temp_db.get_session_by_token(created_session.token)
        
        assert retrieved_session is not None
        assert retrieved_session.id == created_session.id
        assert retrieved_session.token == created_session.token
        assert retrieved_session.user_id == sample_user.id
    
    def test_get_nonexistent_session(self, temp_db):
        """Test getting nonexistent session"""
        session = temp_db.get_session_by_token("nonexistent_token")
        assert session is None
    
    def test_session_is_expired(self, temp_db, sample_user):
        """Test checking if session is expired"""
        # Create session that expires immediately
        session = temp_db.create_session(sample_user.id, expires_in_days=0)
        
        # Manually set expiration to past
        with temp_db.get_connection() as conn:
            cursor = conn.cursor()
            past_time = datetime.utcnow() - timedelta(days=1)
            cursor.execute(
                "UPDATE sessions SET expires_at = ? WHERE id = ?",
                (past_time, session.id)
            )
        
        # Retrieve and check
        session = temp_db.get_session_by_token(session.token)
        assert session.is_expired() is True
    
    def test_invalidate_session(self, temp_db, sample_user):
        """Test invalidating a session"""
        session = temp_db.create_session(sample_user.id)
        
        success = temp_db.invalidate_session(session.token)
        assert success is True
        
        # Session should not be retrievable
        retrieved = temp_db.get_session_by_token(session.token)
        assert retrieved is None
    
    def test_invalidate_user_sessions(self, temp_db, sample_user):
        """Test invalidating all user sessions"""
        # Create multiple sessions
        session1 = temp_db.create_session(sample_user.id)
        session2 = temp_db.create_session(sample_user.id)
        session3 = temp_db.create_session(sample_user.id)
        
        count = temp_db.invalidate_user_sessions(sample_user.id)
        assert count == 3
        
        # All sessions should be invalid
        assert temp_db.get_session_by_token(session1.token) is None
        assert temp_db.get_session_by_token(session2.token) is None
        assert temp_db.get_session_by_token(session3.token) is None
    
    def test_cleanup_expired_sessions(self, temp_db, sample_user):
        """Test cleaning up expired sessions"""
        # Create sessions
        session1 = temp_db.create_session(sample_user.id)
        session2 = temp_db.create_session(sample_user.id)
        session3 = temp_db.create_session(sample_user.id)
        
        # Manually expire two sessions
        with temp_db.get_connection() as conn:
            cursor = conn.cursor()
            past_time = datetime.utcnow() - timedelta(days=1)
            cursor.execute(
                "UPDATE sessions SET expires_at = ? WHERE id IN (?, ?)",
                (past_time, session1.id, session2.id)
            )
        
        count = temp_db.cleanup_expired_sessions()
        assert count == 2
        
        # Only valid session should remain
        assert temp_db.get_session_by_token(session1.token) is None
        assert temp_db.get_session_by_token(session2.token) is None
        assert temp_db.get_session_by_token(session3.token) is not None
    
    def test_get_user_sessions(self, temp_db, sample_user):
        """Test getting all user sessions"""
        # Create multiple sessions
        temp_db.create_session(sample_user.id)
        temp_db.create_session(sample_user.id)
        temp_db.create_session(sample_user.id)
        
        sessions = temp_db.get_user_sessions(sample_user.id)
        assert len(sessions) == 3
        
        # All should belong to same user
        for session in sessions:
            assert session.user_id == sample_user.id
            assert session.is_valid is True
    
    def test_session_to_dict(self, temp_db, sample_user):
        """Test session to_dict method"""
        session = temp_db.create_session(sample_user.id)
        session_dict = session.to_dict()
        
        assert session_dict['id'] == session.id
        assert session_dict['user_id'] == session.user_id
        assert session_dict['token'] == session.token
        assert isinstance(session_dict['created_at'], str)
        assert isinstance(session_dict['expires_at'], str)


class TestDatabaseIntegration:
    """Test database integration scenarios"""
    
    def test_cascade_delete_sessions_on_user_delete(self, temp_db, sample_user):
        """Test that sessions are cleaned when user is deleted"""
        # Create sessions
        session = temp_db.create_session(sample_user.id)
        
        # Delete user (soft delete)
        temp_db.delete_user(sample_user.id)
        
        # Sessions should still exist but user is inactive
        retrieved_session = temp_db.get_session_by_token(session.token)
        assert retrieved_session is not None
        
        # But user lookup should fail
        user = temp_db.get_user_by_id(sample_user.id)
        assert user is None
    
    def test_multiple_users_isolated_sessions(self, temp_db):
        """Test that sessions are isolated between users"""
        user1 = temp_db.create_user("user1", "user1@example.com", "pass123")
        user2 = temp_db.create_user("user2", "user2@example.com", "pass123")
        
        session1 = temp_db.create_session(user1.id)
        session2 = temp_db.create_session(user2.id)
        
        user1_sessions = temp_db.get_user_sessions(user1.id)
        user2_sessions = temp_db.get_user_sessions(user2.id)
        
        assert len(user1_sessions) == 1
        assert len(user2_sessions) == 1
        assert user1_sessions[0].token == session1.token
        assert user2_sessions[0].token == session2.token
    
    def test_connection_rollback_on_error(self, temp_db):
        """Test that connection rolls back on error"""
        # This should fail due to duplicate username
        try:
            with temp_db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO users (id, username, email, password_hash, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
                    ("id1", "user", "email1@example.com", "hash", datetime.utcnow(), datetime.utcnow())
                )
                cursor.execute(
                    "INSERT INTO users (id, username, email, password_hash, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
                    ("id2", "user", "email2@example.com", "hash", datetime.utcnow(), datetime.utcnow())
                )
        except Exception:
            pass
        
        # First user should not exist due to rollback
        user = temp_db.get_user_by_username("user")
        assert user is None
