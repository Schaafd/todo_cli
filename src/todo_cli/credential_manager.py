"""Secure credential manager for app sync providers.

This module provides secure storage and retrieval of API tokens and credentials
using the system keychain/keyring for maximum security.
"""

import os
import logging
from typing import Optional, Dict, List
from pathlib import Path

from .sync.app_sync_models import AppSyncProvider


logger = logging.getLogger(__name__)


class CredentialManager:
    """Secure credential storage using system keyring."""
    
    SERVICE_NAME = "todo_cli_app_sync"
    
    def __init__(self):
        """Initialize the credential manager."""
        self.logger = logging.getLogger(__name__)
        self._keyring = None
        self._fallback_storage = {}  # In-memory fallback if keyring is not available
        
        # Try to import and initialize keyring
        self._init_keyring()
    
    def _init_keyring(self):
        """Initialize keyring with fallback handling."""
        try:
            import keyring
            self._keyring = keyring
            
            # Test keyring functionality
            test_key = f"{self.SERVICE_NAME}_test"
            self._keyring.set_password(self.SERVICE_NAME, test_key, "test_value")
            retrieved = self._keyring.get_password(self.SERVICE_NAME, test_key)
            
            if retrieved == "test_value":
                # Clean up test
                self._keyring.delete_password(self.SERVICE_NAME, test_key)
                self.logger.debug("Keyring initialized successfully")
            else:
                self.logger.warning("Keyring test failed, falling back to environment variables")
                self._keyring = None
                
        except ImportError:
            self.logger.warning("Keyring not available, install with: pip install keyring")
            self._keyring = None
        except Exception as e:
            self.logger.warning(f"Keyring initialization failed: {e}, using fallback storage")
            self._keyring = None
    
    def store_credential(self, provider: AppSyncProvider, key: str, value: str) -> bool:
        """Store a credential securely.
        
        Args:
            provider: The app sync provider
            key: Credential key (e.g., 'api_token', 'client_id')
            value: Credential value
            
        Returns:
            True if stored successfully, False otherwise
        """
        try:
            credential_key = self._make_credential_key(provider, key)
            
            if self._keyring:
                self._keyring.set_password(self.SERVICE_NAME, credential_key, value)
                self.logger.debug(f"Stored credential {key} for {provider.value} in keyring")
                return True
            else:
                # Fallback to environment variable pattern
                env_var = f"TODO_CLI_{provider.value.upper()}_{key.upper()}"
                self._fallback_storage[credential_key] = value
                self.logger.warning(
                    f"Keyring not available. Store credential as environment variable: "
                    f"export {env_var}=\"{value[:8]}...\""
                )
                return True
                
        except Exception as e:
            self.logger.error(f"Failed to store credential {key} for {provider.value}: {e}")
            return False
    
    def get_credential(self, provider: AppSyncProvider, key: str) -> Optional[str]:
        """Retrieve a credential.
        
        Args:
            provider: The app sync provider
            key: Credential key
            
        Returns:
            Credential value if found, None otherwise
        """
        try:
            credential_key = self._make_credential_key(provider, key)
            
            # First try keyring
            if self._keyring:
                value = self._keyring.get_password(self.SERVICE_NAME, credential_key)
                if value:
                    return value
            
            # Try fallback storage
            if credential_key in self._fallback_storage:
                return self._fallback_storage[credential_key]
            
            # Try environment variable
            env_var = f"TODO_CLI_{provider.value.upper()}_{key.upper()}"
            env_value = os.getenv(env_var)
            if env_value:
                self.logger.debug(f"Retrieved credential {key} for {provider.value} from environment")
                return env_value
            
            # Try common environment variable names for API tokens
            if key.lower() in ['api_token', 'token', 'api_key']:
                common_env_vars = [
                    f"{provider.value.upper()}_API_TOKEN",
                    f"{provider.value.upper()}_TOKEN",
                    f"{provider.value.upper()}_API_KEY"
                ]
                
                for env_var in common_env_vars:
                    env_value = os.getenv(env_var)
                    if env_value:
                        self.logger.debug(f"Retrieved credential {key} for {provider.value} from {env_var}")
                        return env_value
            
            return None
            
        except Exception as e:
            self.logger.error(f"Failed to retrieve credential {key} for {provider.value}: {e}")
            return None
    
    def delete_credential(self, provider: AppSyncProvider, key: str) -> bool:
        """Delete a credential.
        
        Args:
            provider: The app sync provider
            key: Credential key
            
        Returns:
            True if deleted successfully, False otherwise
        """
        try:
            credential_key = self._make_credential_key(provider, key)
            deleted = False
            
            # Delete from keyring
            if self._keyring:
                try:
                    self._keyring.delete_password(self.SERVICE_NAME, credential_key)
                    deleted = True
                    self.logger.debug(f"Deleted credential {key} for {provider.value} from keyring")
                except Exception as e:
                    # Password might not exist
                    self.logger.debug(f"Credential {key} not found in keyring: {e}")
            
            # Delete from fallback storage
            if credential_key in self._fallback_storage:
                del self._fallback_storage[credential_key]
                deleted = True
                self.logger.debug(f"Deleted credential {key} for {provider.value} from fallback storage")
            
            return deleted
            
        except Exception as e:
            self.logger.error(f"Failed to delete credential {key} for {provider.value}: {e}")
            return False
    
    def delete_all_credentials(self, provider: AppSyncProvider) -> int:
        """Delete all credentials for a provider.
        
        Args:
            provider: The app sync provider
            
        Returns:
            Number of credentials deleted
        """
        deleted_count = 0
        
        try:
            # Common credential keys to try
            common_keys = [
                'api_token', 'token', 'api_key',
                'client_id', 'client_secret',
                'access_token', 'refresh_token',
                'username', 'password'
            ]
            
            for key in common_keys:
                if self.delete_credential(provider, key):
                    deleted_count += 1
            
            # Also clean up fallback storage
            prefix = f"{provider.value}_"
            keys_to_delete = [k for k in self._fallback_storage.keys() if k.startswith(prefix)]
            for key in keys_to_delete:
                del self._fallback_storage[key]
                deleted_count += 1
            
            if deleted_count > 0:
                self.logger.info(f"Deleted {deleted_count} credentials for {provider.value}")
            
            return deleted_count
            
        except Exception as e:
            self.logger.error(f"Failed to delete all credentials for {provider.value}: {e}")
            return deleted_count
    
    def list_stored_credentials(self, provider: AppSyncProvider) -> List[str]:
        """List stored credential keys for a provider.
        
        Args:
            provider: The app sync provider
            
        Returns:
            List of credential keys that have stored values
        """
        stored_keys = []
        
        try:
            # Common credential keys to check
            common_keys = [
                'api_token', 'token', 'api_key',
                'client_id', 'client_secret',
                'access_token', 'refresh_token',
                'username', 'password'
            ]
            
            for key in common_keys:
                if self.get_credential(provider, key):
                    stored_keys.append(key)
            
            # Check fallback storage for additional keys
            prefix = f"{provider.value}_"
            for stored_key in self._fallback_storage.keys():
                if stored_key.startswith(prefix):
                    key = stored_key[len(prefix):]
                    if key not in stored_keys:
                        stored_keys.append(key)
            
            return stored_keys
            
        except Exception as e:
            self.logger.error(f"Failed to list credentials for {provider.value}: {e}")
            return []
    
    def has_required_credentials(self, provider: AppSyncProvider, required_keys: List[str]) -> bool:
        """Check if all required credentials are available for a provider.
        
        Args:
            provider: The app sync provider
            required_keys: List of required credential keys
            
        Returns:
            True if all required credentials are available
        """
        for key in required_keys:
            if not self.get_credential(provider, key):
                return False
        return True
    
    def get_credentials_status(self, provider: AppSyncProvider) -> Dict[str, bool]:
        """Get status of common credentials for a provider.
        
        Args:
            provider: The app sync provider
            
        Returns:
            Dictionary mapping credential keys to availability status
        """
        status = {}
        
        # Common credential keys to check
        common_keys = [
            'api_token', 'token', 'api_key',
            'client_id', 'client_secret',
            'access_token', 'refresh_token'
        ]
        
        for key in common_keys:
            status[key] = self.get_credential(provider, key) is not None
        
        return status
    
    def _make_credential_key(self, provider: AppSyncProvider, key: str) -> str:
        """Create a unique credential key for storage.
        
        Args:
            provider: The app sync provider
            key: Credential key
            
        Returns:
            Unique credential key for storage
        """
        return f"{provider.value}_{key}"
    
    def export_credentials_as_env_vars(self, provider: AppSyncProvider) -> Dict[str, str]:
        """Export stored credentials as environment variable suggestions.
        
        Args:
            provider: The app sync provider
            
        Returns:
            Dictionary mapping environment variable names to values
        """
        env_vars = {}
        
        try:
            stored_keys = self.list_stored_credentials(provider)
            
            for key in stored_keys:
                value = self.get_credential(provider, key)
                if value:
                    env_var_name = f"TODO_CLI_{provider.value.upper()}_{key.upper()}"
                    env_vars[env_var_name] = value
            
            return env_vars
            
        except Exception as e:
            self.logger.error(f"Failed to export credentials for {provider.value}: {e}")
            return {}
    
    def import_credentials_from_env(self, provider: AppSyncProvider) -> int:
        """Import credentials from environment variables.
        
        Args:
            provider: The app sync provider
            
        Returns:
            Number of credentials imported
        """
        imported_count = 0
        
        try:
            # Common patterns to look for
            provider_upper = provider.value.upper()
            patterns = [
                f"TODO_CLI_{provider_upper}_",
                f"{provider_upper}_",
            ]
            
            # Scan environment variables
            for env_var, value in os.environ.items():
                for pattern in patterns:
                    if env_var.startswith(pattern):
                        # Extract credential key
                        key_part = env_var[len(pattern):].lower()
                        
                        # Skip if already stored
                        if self.get_credential(provider, key_part):
                            continue
                        
                        # Store the credential
                        if self.store_credential(provider, key_part, value):
                            imported_count += 1
                            self.logger.debug(f"Imported credential {key_part} from {env_var}")
                        
                        break
            
            if imported_count > 0:
                self.logger.info(f"Imported {imported_count} credentials for {provider.value} from environment")
            
            return imported_count
            
        except Exception as e:
            self.logger.error(f"Failed to import credentials for {provider.value}: {e}")
            return 0
    
    def is_keyring_available(self) -> bool:
        """Check if keyring is available and working.
        
        Returns:
            True if keyring is available for secure storage
        """
        return self._keyring is not None
    
    def get_storage_info(self) -> Dict[str, any]:
        """Get information about credential storage.
        
        Returns:
            Dictionary with storage information
        """
        return {
            'keyring_available': self.is_keyring_available(),
            'keyring_backend': str(self._keyring.get_keyring()) if self._keyring else None,
            'fallback_credentials_count': len(self._fallback_storage),
            'service_name': self.SERVICE_NAME
        }