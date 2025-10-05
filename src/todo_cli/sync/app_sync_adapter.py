"""Abstract base class for app synchronization adapters.

This module defines the interface that all app sync adapters must implement
to provide consistent integration with various todo applications.
"""

import asyncio
import time
import logging
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any, Tuple, Union
from contextlib import asynccontextmanager

from .app_sync_models import (
    AppSyncProvider,
    AppSyncConfig,
    ExternalTodoItem,
    SyncResult,
    SyncStatus,
    ConflictStrategy
)
from ..domain import Todo


logger = logging.getLogger(__name__)


class AppSyncError(Exception):
    """Base exception for app sync operations."""
    pass


class AuthenticationError(AppSyncError):
    """Authentication failed with the external service."""
    pass


class RateLimitError(AppSyncError):
    """Rate limit exceeded."""
    pass


class NetworkError(AppSyncError):
    """Network connectivity issues."""
    pass


class ValidationError(AppSyncError):
    """Data validation failed."""
    pass


class SyncAdapter(ABC):
    """Base class for all app sync adapters.
    
    This abstract class defines the interface that all app sync adapters
    must implement. Each adapter is responsible for connecting to a specific
    external service and translating between the service's data format and
    our internal Todo format.
    """
    
    def __init__(self, config: AppSyncConfig):
        """Initialize the adapter with configuration.
        
        Args:
            config: App sync configuration containing credentials and settings
        """
        self.config = config
        self.provider = config.provider
        self.rate_limiter = RateLimiter(config.rate_limit_requests_per_minute)
        self.retry_handler = RetryHandler(config.max_retries)
        self._authenticated = False
        self._last_auth_check = None
        self.logger = logging.getLogger(f"{self.__class__.__module__}.{self.__class__.__name__}")
    
    @property
    def provider_name(self) -> str:
        """Get human-readable provider name."""
        return self.provider.value.replace('_', ' ').title()
    
    # Abstract methods that must be implemented by subclasses
    
    @abstractmethod
    async def authenticate(self) -> bool:
        """Authenticate with the external service.
        
        Returns:
            True if authentication successful, False otherwise
            
        Raises:
            AuthenticationError: If authentication fails
        """
        pass
    
    @abstractmethod
    async def test_connection(self) -> bool:
        """Test connection to the external service.
        
        Returns:
            True if connection is working, False otherwise
        """
        pass
    
    @abstractmethod
    async def fetch_items(self, since: Optional[datetime] = None) -> List[ExternalTodoItem]:
        """Fetch todo items from the external service.
        
        Args:
            since: Optional datetime to fetch only items modified since this time
            
        Returns:
            List of external todo items
            
        Raises:
            NetworkError: If network request fails
            AuthenticationError: If authentication is invalid
        """
        pass
    
    @abstractmethod
    async def create_item(self, todo: Todo) -> str:
        """Create a new item in the external service.
        
        Args:
            todo: Local todo item to create
            
        Returns:
            External ID of the created item
            
        Raises:
            ValidationError: If todo data is invalid
            NetworkError: If network request fails
        """
        pass
    
    @abstractmethod
    async def update_item(self, external_id: str, todo: Todo) -> bool:
        """Update an existing item in the external service.
        
        Args:
            external_id: ID of the item in the external service
            todo: Updated todo data
            
        Returns:
            True if update successful, False otherwise
            
        Raises:
            ValidationError: If todo data is invalid
            NetworkError: If network request fails
        """
        pass
    
    @abstractmethod
    async def delete_item(self, external_id: str) -> bool:
        """Delete an item from the external service.
        
        Args:
            external_id: ID of the item to delete
            
        Returns:
            True if deletion successful, False otherwise
            
        Raises:
            NetworkError: If network request fails
        """
        pass
    
    @abstractmethod
    async def fetch_projects(self) -> Dict[str, str]:
        """Fetch available projects/lists from the external service.
        
        Returns:
            Dictionary mapping project names to project IDs
        """
        pass
    
    @abstractmethod
    def map_todo_to_external(self, todo: Todo) -> Dict[str, Any]:
        """Map a local Todo to external service format.
        
        Args:
            todo: Local todo item
            
        Returns:
            Dictionary containing external service representation
        """
        pass
    
    @abstractmethod
    def map_external_to_todo(self, external_data: Dict[str, Any]) -> ExternalTodoItem:
        """Map external service data to ExternalTodoItem.
        
        Args:
            external_data: Raw data from external service
            
        Returns:
            ExternalTodoItem instance
        """
        pass
    
    # Optional methods with default implementations
    
    async def validate_config(self) -> Tuple[bool, List[str]]:
        """Validate the adapter configuration.
        
        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        errors = []
        
        # Check required credentials
        required_creds = self.get_required_credentials()
        for cred in required_creds:
            if not self.config.get_credential(cred):
                errors.append(f"Missing required credential: {cred}")
        
        # Test connection if credentials are present
        if not errors:
            try:
                await self.test_connection()
            except Exception as e:
                errors.append(f"Connection test failed: {str(e)}")
        
        return len(errors) == 0, errors
    
    def get_required_credentials(self) -> List[str]:
        """Get list of required credential keys for this adapter.
        
        Returns:
            List of required credential names
        """
        return []
    
    def get_supported_features(self) -> List[str]:
        """Get list of features supported by this adapter.
        
        Returns:
            List of supported feature names
        """
        return [
            "create", "read", "update", "delete",
            "projects", "tags", "due_dates", "priorities"
        ]
    
    async def ensure_authenticated(self):
        """Ensure the adapter is authenticated, re-authenticating if necessary."""
        current_time = datetime.now(timezone.utc)
        
        # Check if we need to re-authenticate (every 30 minutes)
        if (self._last_auth_check is None or 
            (current_time - self._last_auth_check).total_seconds() > 1800 or
            not self._authenticated):
            
            self._authenticated = await self.authenticate()
            self._last_auth_check = current_time
            
            if not self._authenticated:
                raise AuthenticationError(f"Failed to authenticate with {self.provider_name}")
    
    @asynccontextmanager
    async def rate_limited_request(self):
        """Context manager for rate-limited requests."""
        await self.rate_limiter.acquire()
        try:
            yield
        finally:
            pass
    
    async def execute_with_retry(self, coro, *args, **kwargs):
        """Execute a coroutine with retry logic.
        
        Args:
            coro: Coroutine function to execute
            *args: Positional arguments for the coroutine
            **kwargs: Keyword arguments for the coroutine
            
        Returns:
            Result of the coroutine
        """
        return await self.retry_handler.execute_with_retry(coro, *args, **kwargs)
    
    def apply_project_mapping(self, project_name: str) -> Optional[str]:
        """Apply project mapping from local to external.
        
        Args:
            project_name: Local project name
            
        Returns:
            External project ID or name, or None if no mapping
        """
        return self.config.project_mappings.get(project_name, project_name)
    
    def apply_reverse_project_mapping(self, external_project: str) -> str:
        """Apply reverse project mapping from external to local.
        
        Args:
            external_project: External project ID or name
            
        Returns:
            Local project name
        """
        # Find the local project that maps to this external project
        for local, external in self.config.project_mappings.items():
            if external == external_project:
                return local
        return external_project  # Return as-is if no mapping found
    
    def apply_tag_mapping(self, tags: List[str]) -> List[str]:
        """Apply tag mapping from local to external.
        
        Args:
            tags: List of local tags
            
        Returns:
            List of external tags
        """
        return [self.config.tag_mappings.get(tag, tag) for tag in tags]
    
    def apply_reverse_tag_mapping(self, external_tags: List[str]) -> List[str]:
        """Apply reverse tag mapping from external to local.
        
        Args:
            external_tags: List of external tags
            
        Returns:
            List of local tags
        """
        # Create reverse mapping
        reverse_map = {v: k for k, v in self.config.tag_mappings.items()}
        return [reverse_map.get(tag, tag) for tag in external_tags]
    
    def should_sync_todo(self, todo: Todo) -> bool:
        """Check if a todo should be synced based on configuration.
        
        Args:
            todo: Todo to check
            
        Returns:
            True if todo should be synced
        """
        # Check if completed tasks should be synced
        if todo.completed and not self.config.sync_completed_tasks:
            return False
        
        # Check if archived tasks should be synced
        if getattr(todo, 'archived', False) and not self.config.sync_archived_tasks:
            return False
        
        return True
    
    def log_sync_operation(self, operation: str, details: str = ""):
        """Log a sync operation.
        
        Args:
            operation: Type of operation (create, update, delete, etc.)
            details: Additional details about the operation
        """
        self.logger.info(f"{self.provider_name} sync - {operation}: {details}")


class RateLimiter:
    """Rate limiter for API calls."""
    
    def __init__(self, requests_per_minute: int = 60):
        """Initialize rate limiter.
        
        Args:
            requests_per_minute: Maximum requests per minute
        """
        self.rate = requests_per_minute
        self.tokens = requests_per_minute
        self.updated_at = time.time()
        self.lock = asyncio.Lock()
    
    async def acquire(self):
        """Wait if necessary to respect rate limits."""
        async with self.lock:
            await self._refill()
            while self.tokens < 1:
                await asyncio.sleep(0.1)
                await self._refill()
            self.tokens -= 1
    
    async def _refill(self):
        """Refill tokens based on elapsed time."""
        now = time.time()
        elapsed = now - self.updated_at
        
        # Add tokens based on elapsed time
        tokens_to_add = elapsed * (self.rate / 60.0)  # Convert per minute to per second
        self.tokens = min(self.rate, self.tokens + tokens_to_add)
        self.updated_at = now


class RetryHandler:
    """Handles retry logic for failed operations."""
    
    def __init__(self, max_retries: int = 3):
        """Initialize retry handler.
        
        Args:
            max_retries: Maximum number of retry attempts
        """
        self.max_retries = max_retries
    
    async def execute_with_retry(self, coro, *args, **kwargs):
        """Execute a coroutine with exponential backoff retry.
        
        Args:
            coro: Coroutine function to execute
            *args: Positional arguments for the coroutine
            **kwargs: Keyword arguments for the coroutine
            
        Returns:
            Result of the coroutine
            
        Raises:
            The last exception if all retries fail
        """
        last_exception = None
        
        for attempt in range(self.max_retries + 1):
            try:
                return await coro(*args, **kwargs)
            except (NetworkError, RateLimitError) as e:
                last_exception = e
                if attempt < self.max_retries:
                    # Exponential backoff: 1, 2, 4, 8 seconds
                    delay = 2 ** attempt
                    logger.warning(f"Attempt {attempt + 1} failed, retrying in {delay}s: {e}")
                    await asyncio.sleep(delay)
                else:
                    logger.error(f"All {self.max_retries + 1} attempts failed")
                    break
            except Exception as e:
                # Don't retry for non-transient errors
                logger.error(f"Non-retryable error: {e}")
                raise
        
        if last_exception:
            raise last_exception


# Convenience type alias
AppSyncAdapter = SyncAdapter