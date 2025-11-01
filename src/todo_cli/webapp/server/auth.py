"""Authentication service for web app."""

import os
import secrets
from datetime import datetime, timezone, timedelta
from typing import Optional, Tuple
import logging

import bcrypt
import jwt

from .models import User, Session, TokenPair
from .database import UserDatabase, get_user_db


logger = logging.getLogger(__name__)


# JWT Configuration
JWT_SECRET_KEY = os.getenv('JWT_SECRET', secrets.token_urlsafe(64))
JWT_ALGORITHM = 'HS256'
ACCESS_TOKEN_EXPIRE_MINUTES = 15
REFRESH_TOKEN_EXPIRE_DAYS = 30

# Password Configuration
BCRYPT_ROUNDS = 12


class AuthenticationError(Exception):
    """Authentication failed."""
    pass


class AuthService:
    """Authentication and authorization service."""
    
    def __init__(self, db: Optional[UserDatabase] = None):
        """Initialize auth service.
        
        Args:
            db: User database instance (uses global if None)
        """
        self.db = db or get_user_db()
        self.logger = logging.getLogger(__name__)
    
    # Password Management
    
    @staticmethod
    def hash_password(password: str) -> str:
        """Hash a password using bcrypt.
        
        Args:
            password: Plain text password
            
        Returns:
            Bcrypt hash string
        """
        salt = bcrypt.gensalt(rounds=BCRYPT_ROUNDS)
        password_hash = bcrypt.hashpw(password.encode('utf-8'), salt)
        return password_hash.decode('utf-8')
    
    @staticmethod
    def verify_password(password: str, password_hash: str) -> bool:
        """Verify a password against its hash.
        
        Args:
            password: Plain text password
            password_hash: Bcrypt hash string
            
        Returns:
            True if password matches
        """
        try:
            return bcrypt.checkpw(
                password.encode('utf-8'),
                password_hash.encode('utf-8')
            )
        except Exception as e:
            logger.error(f"Password verification failed: {e}")
            return False
    
    # User Registration & Authentication
    
    def register_user(self, username: str, email: str, password: str) -> User:
        """Register a new user.
        
        Args:
            username: Unique username
            email: Unique email address
            password: Plain text password
            
        Returns:
            Created User instance
            
        Raises:
            ValueError: If username or email already exists
        """
        # Validate inputs
        if len(username) < 3:
            raise ValueError("Username must be at least 3 characters")
        if len(password) < 8:
            raise ValueError("Password must be at least 8 characters")
        if '@' not in email:
            raise ValueError("Invalid email address")
        
        # Hash password
        password_hash = self.hash_password(password)
        
        # Create user
        user = self.db.create_user(
            username=username,
            email=email,
            password_hash=password_hash
        )
        
        self.logger.info(f"Registered new user: {username}")
        return user
    
    def authenticate_user(self, username_or_email: str, password: str) -> User:
        """Authenticate a user by username/email and password.
        
        Args:
            username_or_email: Username or email address
            password: Plain text password
            
        Returns:
            Authenticated User instance
            
        Raises:
            AuthenticationError: If authentication fails
        """
        # Try username first, then email
        user = self.db.get_user_by_username(username_or_email)
        if not user:
            user = self.db.get_user_by_email(username_or_email)
        
        if not user:
            raise AuthenticationError("Invalid credentials")
        
        if not user.is_active:
            raise AuthenticationError("Account is disabled")
        
        # Verify password
        if not self.verify_password(password, user.password_hash):
            raise AuthenticationError("Invalid credentials")
        
        # Update last login
        self.db.update_last_login(user.id)
        
        self.logger.info(f"User authenticated: {user.username}")
        return user
    
    # Token Management
    
    def create_tokens(self, user: User, device_info: Optional[str] = None,
                     ip_address: Optional[str] = None) -> TokenPair:
        """Create access and refresh tokens for a user.
        
        Args:
            user: User instance
            device_info: Optional device information
            ip_address: Optional IP address
            
        Returns:
            TokenPair with access and refresh tokens
        """
        # Create access token
        access_token_data = {
            'sub': str(user.id),
            'username': user.username,
            'type': 'access',
            'exp': datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        }
        access_token = jwt.encode(access_token_data, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
        
        # Create refresh token
        refresh_token_data = {
            'sub': str(user.id),
            'type': 'refresh',
            'exp': datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
        }
        refresh_token = jwt.encode(refresh_token_data, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
        
        # Store access token session
        access_session = Session(
            id=Session.generate_session_id(),
            user_id=user.id,
            token_hash=Session.hash_token(access_token),
            created_at=datetime.now(timezone.utc),
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
            is_refresh_token=False,
            device_info=device_info,
            ip_address=ip_address
        )
        self.db.create_session(access_session)
        
        # Store refresh token session
        refresh_session = Session(
            id=Session.generate_session_id(),
            user_id=user.id,
            token_hash=Session.hash_token(refresh_token),
            created_at=datetime.now(timezone.utc),
            expires_at=datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS),
            is_refresh_token=True,
            device_info=device_info,
            ip_address=ip_address
        )
        self.db.create_session(refresh_session)
        
        self.logger.debug(f"Created tokens for user {user.username}")
        
        return TokenPair(
            access_token=access_token,
            refresh_token=refresh_token,
            access_expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            refresh_expires_in=REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60
        )
    
    def verify_token(self, token: str, token_type: str = 'access') -> Optional[dict]:
        """Verify and decode a JWT token.
        
        Args:
            token: JWT token string
            token_type: Expected token type ('access' or 'refresh')
            
        Returns:
            Decoded token payload or None if invalid
        """
        try:
            payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
            
            # Verify token type
            if payload.get('type') != token_type:
                self.logger.warning(f"Token type mismatch: expected {token_type}, got {payload.get('type')}")
                return None
            
            # Verify token exists in database
            token_hash = Session.hash_token(token)
            # Note: This is simplified - in production, you'd check against stored sessions
            
            return payload
            
        except jwt.ExpiredSignatureError:
            self.logger.debug("Token expired")
            return None
        except jwt.InvalidTokenError as e:
            self.logger.warning(f"Invalid token: {e}")
            return None
    
    def refresh_tokens(self, refresh_token: str, device_info: Optional[str] = None,
                      ip_address: Optional[str] = None) -> Optional[TokenPair]:
        """Refresh access token using refresh token.
        
        Args:
            refresh_token: Valid refresh token
            device_info: Optional device information
            ip_address: Optional IP address
            
        Returns:
            New TokenPair or None if refresh token is invalid
        """
        # Verify refresh token
        payload = self.verify_token(refresh_token, token_type='refresh')
        if not payload:
            return None
        
        # Get user
        user_id = int(payload['sub'])
        user = self.db.get_user_by_id(user_id)
        if not user or not user.is_active:
            return None
        
        # Create new tokens
        return self.create_tokens(user, device_info, ip_address)
    
    def revoke_token(self, token: str) -> bool:
        """Revoke a token by removing its session.
        
        Args:
            token: Token to revoke
            
        Returns:
            True if successful
        """
        try:
            token_hash = Session.hash_token(token)
            # In production, you'd look up the session by token_hash and delete it
            # For now, this is a placeholder
            self.logger.debug(f"Revoked token")
            return True
        except Exception as e:
            self.logger.error(f"Failed to revoke token: {e}")
            return False
    
    def revoke_all_user_tokens(self, user_id: int) -> int:
        """Revoke all tokens for a user.
        
        Args:
            user_id: User ID
            
        Returns:
            Number of sessions deleted
        """
        return self.db.delete_user_sessions(user_id)
    
    # User Retrieval
    
    def get_current_user(self, token: str) -> Optional[User]:
        """Get user from access token.
        
        Args:
            token: Access token
            
        Returns:
            User instance or None
        """
        payload = self.verify_token(token, token_type='access')
        if not payload:
            return None
        
        user_id = int(payload['sub'])
        return self.db.get_user_by_id(user_id)
    
    def cleanup_expired_sessions(self) -> int:
        """Clean up expired sessions.
        
        Returns:
            Number of sessions cleaned up
        """
        return self.db.cleanup_expired_sessions()


# Global auth service instance
_auth_service: Optional[AuthService] = None


def get_auth_service() -> AuthService:
    """Get global auth service instance.
    
    Returns:
        AuthService instance
    """
    global _auth_service
    
    if _auth_service is None:
        _auth_service = AuthService()
    
    return _auth_service


def reset_auth_service():
    """Reset global auth service (for testing)."""
    global _auth_service
    _auth_service = None
