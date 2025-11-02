"""Authentication middleware for FastAPI."""

from typing import Optional, Callable
from fastapi import Request, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import logging

from ..auth import AuthService, get_auth_service
from ..models import User


logger = logging.getLogger(__name__)


# HTTP Bearer token scheme
security = HTTPBearer(auto_error=False)


async def get_current_user(
    request: Request,
    auth_service: AuthService = None
) -> Optional[User]:
    """Get current authenticated user from request.
    
    Args:
        request: FastAPI request
        auth_service: Auth service instance (optional)
        
    Returns:
        User instance or None if not authenticated
    """
    if auth_service is None:
        auth_service = get_auth_service()
    
    # Try to get token from Authorization header
    auth_header = request.headers.get("authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return None
    
    access_token = auth_header[7:]
    
    # Get user from token
    user = auth_service.get_current_user(access_token)
    return user


async def require_auth(request: Request) -> User:
    """Require authentication for a route.
    
    Args:
        request: FastAPI request
        
    Returns:
        Authenticated User instance
        
    Raises:
        HTTPException: If not authenticated
    """
    user = await get_current_user(request)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is disabled"
        )
    
    return user


async def optional_auth(request: Request) -> Optional[User]:
    """Optional authentication for a route.
    
    Args:
        request: FastAPI request
        
    Returns:
        User instance or None if not authenticated
    """
    return await get_current_user(request)


def get_user_id_from_request(request: Request) -> Optional[int]:
    """Extract user ID from authenticated request.
    
    Args:
        request: FastAPI request
        
    Returns:
        User ID or None if not authenticated
    """
    # Check if user is already in request state
    if hasattr(request.state, "user"):
        return request.state.user.id
    
    # Try to get from token
    auth_service = get_auth_service()
    auth_header = request.headers.get("authorization")
    
    if not auth_header or not auth_header.startswith("Bearer "):
        return None
    
    access_token = auth_header[7:]
    payload = auth_service.verify_token(access_token)
    
    if not payload:
        return None
    
    return int(payload.get('sub'))


class AuthMiddleware:
    """Middleware to inject user into request state."""
    
    def __init__(self, app):
        """Initialize middleware.
        
        Args:
            app: FastAPI application
        """
        self.app = app
    
    async def __call__(self, request: Request, call_next: Callable):
        """Process request and inject user if authenticated.
        
        Args:
            request: FastAPI request
            call_next: Next middleware/route handler
            
        Returns:
            Response from next handler
        """
        # Try to get current user
        user = await get_current_user(request)
        
        # Inject user into request state
        request.state.user = user
        
        # Call next handler
        response = await call_next(request)
        
        return response
