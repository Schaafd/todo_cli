"""User and authentication models for web app."""

from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any
from dataclasses import dataclass, field
import secrets
import hashlib


@dataclass
class User:
    """User model for authentication and profile."""
    
    id: int
    username: str
    email: str
    password_hash: str
    created_at: datetime
    last_login: Optional[datetime] = None
    is_active: bool = True
    settings: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self, include_sensitive: bool = False) -> Dict[str, Any]:
        """Convert user to dictionary.
        
        Args:
            include_sensitive: Include password hash in output
            
        Returns:
            Dictionary representation of user
        """
        data = {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'created_at': self.created_at.isoformat(),
            'last_login': self.last_login.isoformat() if self.last_login else None,
            'is_active': self.is_active,
            'settings': self.settings
        }
        
        if include_sensitive:
            data['password_hash'] = self.password_hash
        
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'User':
        """Create user from dictionary.
        
        Args:
            data: Dictionary with user data
            
        Returns:
            User instance
        """
        return cls(
            id=data['id'],
            username=data['username'],
            email=data['email'],
            password_hash=data['password_hash'],
            created_at=datetime.fromisoformat(data['created_at']) if isinstance(data['created_at'], str) else data['created_at'],
            last_login=datetime.fromisoformat(data['last_login']) if data.get('last_login') and isinstance(data['last_login'], str) else data.get('last_login'),
            is_active=data.get('is_active', True),
            settings=data.get('settings', {})
        )


@dataclass
class Session:
    """User session model for authentication tokens."""
    
    id: str
    user_id: int
    token_hash: str
    created_at: datetime
    expires_at: datetime
    is_refresh_token: bool = False
    device_info: Optional[str] = None
    ip_address: Optional[str] = None
    
    def is_expired(self) -> bool:
        """Check if session has expired.
        
        Returns:
            True if session is expired
        """
        return datetime.now(timezone.utc) > self.expires_at.replace(tzinfo=timezone.utc)
    
    def is_valid(self) -> bool:
        """Check if session is valid (not expired).
        
        Returns:
            True if session is valid
        """
        return not self.is_expired()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert session to dictionary.
        
        Returns:
            Dictionary representation of session
        """
        return {
            'id': self.id,
            'user_id': self.user_id,
            'token_hash': self.token_hash,
            'created_at': self.created_at.isoformat(),
            'expires_at': self.expires_at.isoformat(),
            'is_refresh_token': self.is_refresh_token,
            'device_info': self.device_info,
            'ip_address': self.ip_address
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Session':
        """Create session from dictionary.
        
        Args:
            data: Dictionary with session data
            
        Returns:
            Session instance
        """
        return cls(
            id=data['id'],
            user_id=data['user_id'],
            token_hash=data['token_hash'],
            created_at=datetime.fromisoformat(data['created_at']) if isinstance(data['created_at'], str) else data['created_at'],
            expires_at=datetime.fromisoformat(data['expires_at']) if isinstance(data['expires_at'], str) else data['expires_at'],
            is_refresh_token=data.get('is_refresh_token', False),
            device_info=data.get('device_info'),
            ip_address=data.get('ip_address')
        )
    
    @staticmethod
    def generate_session_id() -> str:
        """Generate unique session ID.
        
        Returns:
            Random session ID
        """
        return secrets.token_urlsafe(32)
    
    @staticmethod
    def hash_token(token: str) -> str:
        """Hash a token for storage.
        
        Args:
            token: Token to hash
            
        Returns:
            SHA-256 hash of token
        """
        return hashlib.sha256(token.encode()).hexdigest()


@dataclass
class TokenPair:
    """Pair of access and refresh tokens."""
    
    access_token: str
    refresh_token: str
    access_expires_in: int  # seconds
    refresh_expires_in: int  # seconds
    token_type: str = "Bearer"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert token pair to dictionary.
        
        Returns:
            Dictionary representation suitable for API response
        """
        return {
            'access_token': self.access_token,
            'refresh_token': self.refresh_token,
            'token_type': self.token_type,
            'expires_in': self.access_expires_in
        }
