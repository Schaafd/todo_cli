"""Authentication API routes."""

from typing import Optional
from fastapi import APIRouter, HTTPException, Depends, Response, Request, status
from pydantic import BaseModel, EmailStr, Field
import logging

from ..auth import AuthService, AuthenticationError, get_auth_service
from ..models import User


logger = logging.getLogger(__name__)


# Request/Response models
class RegisterRequest(BaseModel):
    """User registration request."""
    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)


class LoginRequest(BaseModel):
    """User login request."""
    username_or_email: str = Field(..., min_length=3)
    password: str = Field(..., min_length=8, max_length=128)


class TokenResponse(BaseModel):
    """Token response."""
    access_token: str
    refresh_token: str
    token_type: str = "Bearer"
    expires_in: int


class UserResponse(BaseModel):
    """User information response."""
    id: int
    username: str
    email: str
    created_at: str
    last_login: Optional[str] = None
    is_active: bool


class MessageResponse(BaseModel):
    """Simple message response."""
    message: str


# Router
router = APIRouter(prefix="/api/auth", tags=["authentication"])


def get_device_info(request: Request) -> str:
    """Extract device info from request headers.
    
    Args:
        request: FastAPI request object
        
    Returns:
        Device info string
    """
    user_agent = request.headers.get("user-agent", "unknown")
    return user_agent[:200]  # Limit length


def get_client_ip(request: Request) -> str:
    """Extract client IP from request.
    
    Args:
        request: FastAPI request object
        
    Returns:
        Client IP address
    """
    # Check for proxied headers first
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    
    real_ip = request.headers.get("x-real-ip")
    if real_ip:
        return real_ip
    
    # Fallback to direct client
    if request.client:
        return request.client.host
    
    return "unknown"


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(
    request: Request,
    body: RegisterRequest,
    response: Response,
    auth_service: AuthService = Depends(get_auth_service)
):
    """Register a new user.
    
    Args:
        request: FastAPI request
        body: Registration data
        response: FastAPI response
        auth_service: Auth service dependency
        
    Returns:
        Token pair for new user
        
    Raises:
        HTTPException: If registration fails
    """
    try:
        # Register user
        user = auth_service.register_user(
            username=body.username,
            email=body.email,
            password=body.password
        )
        
        # Create tokens
        device_info = get_device_info(request)
        ip_address = get_client_ip(request)
        tokens = auth_service.create_tokens(user, device_info, ip_address)
        
        # Set refresh token in httpOnly cookie
        response.set_cookie(
            key="refresh_token",
            value=tokens.refresh_token,
            httponly=True,
            secure=True,  # Enable in production with HTTPS
            samesite="strict",
            max_age=tokens.refresh_expires_in
        )
        
        logger.info(f"User registered: {user.username}")
        
        return TokenResponse(
            access_token=tokens.access_token,
            refresh_token=tokens.refresh_token,
            token_type=tokens.token_type,
            expires_in=tokens.access_expires_in
        )
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Registration failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Registration failed"
        )


@router.post("/login", response_model=TokenResponse)
async def login(
    request: Request,
    body: LoginRequest,
    response: Response,
    auth_service: AuthService = Depends(get_auth_service)
):
    """Authenticate user and return tokens.
    
    Args:
        request: FastAPI request
        body: Login credentials
        response: FastAPI response
        auth_service: Auth service dependency
        
    Returns:
        Token pair for authenticated user
        
    Raises:
        HTTPException: If authentication fails
    """
    try:
        # Authenticate user
        user = auth_service.authenticate_user(
            username_or_email=body.username_or_email,
            password=body.password
        )
        
        # Create tokens
        device_info = get_device_info(request)
        ip_address = get_client_ip(request)
        tokens = auth_service.create_tokens(user, device_info, ip_address)
        
        # Set refresh token in httpOnly cookie
        response.set_cookie(
            key="refresh_token",
            value=tokens.refresh_token,
            httponly=True,
            secure=True,  # Enable in production with HTTPS
            samesite="strict",
            max_age=tokens.refresh_expires_in
        )
        
        logger.info(f"User logged in: {user.username}")
        
        return TokenResponse(
            access_token=tokens.access_token,
            refresh_token=tokens.refresh_token,
            token_type=tokens.token_type,
            expires_in=tokens.access_expires_in
        )
        
    except AuthenticationError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"}
        )
    except Exception as e:
        logger.error(f"Login failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Login failed"
        )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    request: Request,
    response: Response,
    auth_service: AuthService = Depends(get_auth_service)
):
    """Refresh access token using refresh token.
    
    Args:
        request: FastAPI request
        response: FastAPI response
        auth_service: Auth service dependency
        
    Returns:
        New token pair
        
    Raises:
        HTTPException: If refresh fails
    """
    try:
        # Get refresh token from cookie or Authorization header
        refresh_token = request.cookies.get("refresh_token")
        
        if not refresh_token:
            # Try Authorization header
            auth_header = request.headers.get("authorization")
            if auth_header and auth_header.startswith("Bearer "):
                refresh_token = auth_header[7:]
        
        if not refresh_token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="No refresh token provided",
                headers={"WWW-Authenticate": "Bearer"}
            )
        
        # Refresh tokens
        device_info = get_device_info(request)
        ip_address = get_client_ip(request)
        tokens = auth_service.refresh_tokens(refresh_token, device_info, ip_address)
        
        if not tokens:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired refresh token",
                headers={"WWW-Authenticate": "Bearer"}
            )
        
        # Set new refresh token in httpOnly cookie
        response.set_cookie(
            key="refresh_token",
            value=tokens.refresh_token,
            httponly=True,
            secure=True,
            samesite="strict",
            max_age=tokens.refresh_expires_in
        )
        
        logger.debug("Tokens refreshed")
        
        return TokenResponse(
            access_token=tokens.access_token,
            refresh_token=tokens.refresh_token,
            token_type=tokens.token_type,
            expires_in=tokens.access_expires_in
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Token refresh failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Token refresh failed"
        )


@router.post("/logout", response_model=MessageResponse)
async def logout(
    request: Request,
    response: Response,
    auth_service: AuthService = Depends(get_auth_service)
):
    """Logout user by revoking tokens.
    
    Args:
        request: FastAPI request
        response: FastAPI response
        auth_service: Auth service dependency
        
    Returns:
        Success message
    """
    try:
        # Get access token from Authorization header
        auth_header = request.headers.get("authorization")
        if auth_header and auth_header.startswith("Bearer "):
            access_token = auth_header[7:]
            auth_service.revoke_token(access_token)
        
        # Get refresh token from cookie
        refresh_token = request.cookies.get("refresh_token")
        if refresh_token:
            auth_service.revoke_token(refresh_token)
        
        # Clear refresh token cookie
        response.delete_cookie(
            key="refresh_token",
            httponly=True,
            secure=True,
            samesite="strict"
        )
        
        logger.debug("User logged out")
        
        return MessageResponse(message="Successfully logged out")
        
    except Exception as e:
        logger.error(f"Logout failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Logout failed"
        )


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    request: Request,
    auth_service: AuthService = Depends(get_auth_service)
):
    """Get current user information.
    
    Args:
        request: FastAPI request
        auth_service: Auth service dependency
        
    Returns:
        Current user information
        
    Raises:
        HTTPException: If not authenticated
    """
    try:
        # Get access token from Authorization header
        auth_header = request.headers.get("authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Not authenticated",
                headers={"WWW-Authenticate": "Bearer"}
            )
        
        access_token = auth_header[7:]
        
        # Get user from token
        user = auth_service.get_current_user(access_token)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token",
                headers={"WWW-Authenticate": "Bearer"}
            )
        
        return UserResponse(
            id=user.id,
            username=user.username,
            email=user.email,
            created_at=user.created_at.isoformat(),
            last_login=user.last_login.isoformat() if user.last_login else None,
            is_active=user.is_active
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get current user failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get user information"
        )
