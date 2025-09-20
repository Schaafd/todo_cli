"""Configuration system for app sync settings and provider management.

This module extends the existing config system to handle app synchronization
configurations, provider settings, and sync preferences.
"""

import os
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone

import yaml
from pydantic import BaseModel, Field, validator
from pydantic_settings import BaseSettings

from .app_sync_models import (
    AppSyncProvider, 
    AppSyncConfig, 
    ConflictStrategy, 
    SyncDirection
)
from .config import get_config_dir


logger = logging.getLogger(__name__)


class ProviderSettings(BaseModel):
    """Settings for a specific sync provider."""
    
    enabled: bool = True
    auto_sync: bool = False
    sync_interval: int = 300  # seconds
    sync_direction: SyncDirection = SyncDirection.BIDIRECTIONAL
    conflict_strategy: ConflictStrategy = ConflictStrategy.NEWEST_WINS
    
    # Sync filters
    sync_completed_tasks: bool = True
    sync_archived_tasks: bool = False
    max_history_days: int = 30
    
    # Project and tag mappings
    project_mappings: Dict[str, str] = Field(default_factory=dict)  # local -> remote
    tag_mappings: Dict[str, str] = Field(default_factory=dict)      # local -> remote
    
    # Provider-specific settings
    settings: Dict[str, Any] = Field(default_factory=dict)
    
    # Rate limiting and performance
    max_retries: int = 3
    timeout_seconds: int = 30
    rate_limit_requests_per_minute: int = 50
    batch_size: int = 100
    
    @validator('sync_interval')
    def validate_sync_interval(cls, v):
        if v < 60:
            raise ValueError('Sync interval must be at least 60 seconds')
        return v
    
    @validator('rate_limit_requests_per_minute')
    def validate_rate_limit(cls, v):
        if v < 1 or v > 1000:
            raise ValueError('Rate limit must be between 1 and 1000 requests per minute')
        return v


class GlobalSyncSettings(BaseModel):
    """Global app sync configuration."""
    
    # Global sync preferences
    sync_on_startup: bool = False
    sync_on_exit: bool = False
    auto_resolve_conflicts: bool = False
    default_conflict_strategy: ConflictStrategy = ConflictStrategy.MANUAL
    
    # Notification settings
    notify_on_sync_completion: bool = True
    notify_on_conflicts: bool = True
    notify_on_errors: bool = True
    
    # Performance and reliability
    max_concurrent_syncs: int = 3
    sync_timeout_seconds: int = 300
    offline_mode: bool = False
    
    # Data retention
    keep_sync_history_days: int = 90
    cleanup_resolved_conflicts_days: int = 30
    
    # Logging and debugging
    log_sync_operations: bool = True
    debug_mode: bool = False
    
    @validator('max_concurrent_syncs')
    def validate_concurrent_syncs(cls, v):
        if v < 1 or v > 10:
            raise ValueError('Max concurrent syncs must be between 1 and 10')
        return v


class AppSyncConfigManager:
    """Manages app sync configuration with file-based persistence."""
    
    CONFIG_FILE = "app_sync.yaml"
    
    def __init__(self, config_dir: Optional[Path] = None):
        """Initialize config manager.
        
        Args:
            config_dir: Optional config directory path
        """
        self.config_dir = config_dir or get_config_dir()
        self.config_dir.mkdir(exist_ok=True)
        self.config_file = self.config_dir / self.CONFIG_FILE
        
        self.global_settings = GlobalSyncSettings()
        self.providers: Dict[AppSyncProvider, ProviderSettings] = {}
        
        self.logger = logging.getLogger(__name__)
        
        # Load existing configuration
        self.load()
    
    def load(self):
        """Load configuration from file."""
        if not self.config_file.exists():
            self.logger.debug("No app sync config file found, using defaults")
            return
        
        try:
            with open(self.config_file, 'r') as f:
                data = yaml.safe_load(f)
            
            if not data:
                return
            
            # Load global settings
            if 'global' in data:
                self.global_settings = GlobalSyncSettings(**data['global'])
            
            # Load provider settings
            if 'providers' in data:
                for provider_name, provider_data in data['providers'].items():
                    try:
                        provider = AppSyncProvider(provider_name)
                        self.providers[provider] = ProviderSettings(**provider_data)
                    except ValueError:
                        self.logger.warning(f"Unknown provider in config: {provider_name}")
            
            self.logger.debug(f"Loaded app sync config from {self.config_file}")
            
        except Exception as e:
            self.logger.error(f"Failed to load app sync config: {e}")
            # Continue with defaults
    
    def save(self):
        """Save configuration to file."""
        try:
            data = {
                'global': self.global_settings.dict(),
                'providers': {}
            }
            
            # Convert provider configurations
            for provider, settings in self.providers.items():
                data['providers'][provider.value] = settings.dict()
            
            # Add metadata
            data['_metadata'] = {
                'version': '1.0',
                'updated_at': datetime.now(timezone.utc).isoformat(),
                'generated_by': 'todo_cli_app_sync'
            }
            
            # Ensure config directory exists
            self.config_file.parent.mkdir(parents=True, exist_ok=True)
            
            # Write with atomic operation
            temp_file = self.config_file.with_suffix('.tmp')
            with open(temp_file, 'w') as f:
                yaml.dump(data, f, default_flow_style=False, indent=2, sort_keys=True)
            
            temp_file.rename(self.config_file)
            
            self.logger.debug(f"Saved app sync config to {self.config_file}")
            
        except Exception as e:
            self.logger.error(f"Failed to save app sync config: {e}")
            raise
    
    def get_provider_config(self, provider: AppSyncProvider) -> AppSyncConfig:
        """Get complete configuration for a provider.
        
        Args:
            provider: The sync provider
            
        Returns:
            Complete AppSyncConfig instance
        """
        # Get provider settings or create defaults
        settings = self.providers.get(provider, ProviderSettings())
        
        # Load credentials from credential manager
        from .credential_manager import CredentialManager
        cred_manager = CredentialManager()
        
        # Create AppSyncConfig
        config = AppSyncConfig(
            provider=provider,
            enabled=settings.enabled,
            sync_direction=settings.sync_direction,
            auto_sync=settings.auto_sync,
            sync_interval=settings.sync_interval,
            conflict_strategy=settings.conflict_strategy,
            sync_completed_tasks=settings.sync_completed_tasks,
            sync_archived_tasks=settings.sync_archived_tasks,
            project_mappings=settings.project_mappings.copy(),
            tag_mappings=settings.tag_mappings.copy(),
            max_retries=settings.max_retries,
            timeout_seconds=settings.timeout_seconds,
            rate_limit_requests_per_minute=settings.rate_limit_requests_per_minute,
            batch_size=settings.batch_size
        )
        
        # Copy provider-specific settings
        config.settings.update(settings.settings)
        
        # Load credentials
        stored_credentials = cred_manager.list_stored_credentials(provider)
        for cred_key in stored_credentials:
            cred_value = cred_manager.get_credential(provider, cred_key)
            if cred_value:
                config.credentials[cred_key] = cred_value
        
        return config
    
    def set_provider_settings(self, provider: AppSyncProvider, settings: ProviderSettings):
        """Set provider settings.
        
        Args:
            provider: The sync provider
            settings: Provider settings
        """
        self.providers[provider] = settings
        self.save()
    
    def update_provider_setting(self, provider: AppSyncProvider, key: str, value: Any):
        """Update a single provider setting.
        
        Args:
            provider: The sync provider
            key: Setting key
            value: Setting value
        """
        if provider not in self.providers:
            self.providers[provider] = ProviderSettings()
        
        settings = self.providers[provider]
        
        # Update the setting
        if hasattr(settings, key):
            setattr(settings, key, value)
        else:
            settings.settings[key] = value
        
        self.save()
    
    def add_project_mapping(self, provider: AppSyncProvider, local_project: str, remote_project: str):
        """Add a project mapping for a provider.
        
        Args:
            provider: The sync provider
            local_project: Local project name
            remote_project: Remote project ID or name
        """
        if provider not in self.providers:
            self.providers[provider] = ProviderSettings()
        
        self.providers[provider].project_mappings[local_project] = remote_project
        self.save()
    
    def remove_project_mapping(self, provider: AppSyncProvider, local_project: str):
        """Remove a project mapping for a provider.
        
        Args:
            provider: The sync provider
            local_project: Local project name
        """
        if provider in self.providers:
            self.providers[provider].project_mappings.pop(local_project, None)
            self.save()
    
    def add_tag_mapping(self, provider: AppSyncProvider, local_tag: str, remote_tag: str):
        """Add a tag mapping for a provider.
        
        Args:
            provider: The sync provider
            local_tag: Local tag name
            remote_tag: Remote tag name
        """
        if provider not in self.providers:
            self.providers[provider] = ProviderSettings()
        
        self.providers[provider].tag_mappings[local_tag] = remote_tag
        self.save()
    
    def remove_tag_mapping(self, provider: AppSyncProvider, local_tag: str):
        """Remove a tag mapping for a provider.
        
        Args:
            provider: The sync provider
            local_tag: Local tag name
        """
        if provider in self.providers:
            self.providers[provider].tag_mappings.pop(local_tag, None)
            self.save()
    
    def enable_provider(self, provider: AppSyncProvider):
        """Enable a provider.
        
        Args:
            provider: The sync provider
        """
        if provider not in self.providers:
            self.providers[provider] = ProviderSettings()
        
        self.providers[provider].enabled = True
        self.save()
    
    def disable_provider(self, provider: AppSyncProvider):
        """Disable a provider.
        
        Args:
            provider: The sync provider
        """
        if provider in self.providers:
            self.providers[provider].enabled = False
            self.save()
    
    def get_enabled_providers(self) -> List[AppSyncProvider]:
        """Get list of enabled providers.
        
        Returns:
            List of enabled providers
        """
        return [
            provider for provider, settings in self.providers.items()
            if settings.enabled
        ]
    
    def get_all_providers(self) -> List[AppSyncProvider]:
        """Get list of all configured providers.
        
        Returns:
            List of all configured providers
        """
        return list(self.providers.keys())
    
    def export_config(self, file_path: Path):
        """Export configuration to a file.
        
        Args:
            file_path: Path to export to
        """
        data = {
            'global': self.global_settings.dict(),
            'providers': {}
        }
        
        for provider, settings in self.providers.items():
            # Export settings without sensitive data
            provider_data = settings.dict()
            provider_data.pop('credentials', None)  # Don't export credentials
            data['providers'][provider.value] = provider_data
        
        with open(file_path, 'w') as f:
            yaml.dump(data, f, default_flow_style=False, indent=2)
        
        self.logger.info(f"Exported app sync config to {file_path}")
    
    def import_config(self, file_path: Path, merge: bool = True):
        """Import configuration from a file.
        
        Args:
            file_path: Path to import from
            merge: Whether to merge with existing config or replace
        """
        with open(file_path, 'r') as f:
            data = yaml.safe_load(f)
        
        if not merge:
            self.global_settings = GlobalSyncSettings()
            self.providers.clear()
        
        # Import global settings
        if 'global' in data:
            if merge:
                # Update existing settings
                for key, value in data['global'].items():
                    if hasattr(self.global_settings, key):
                        setattr(self.global_settings, key, value)
            else:
                self.global_settings = GlobalSyncSettings(**data['global'])
        
        # Import provider settings
        if 'providers' in data:
            for provider_name, provider_data in data['providers'].items():
                try:
                    provider = AppSyncProvider(provider_name)
                    
                    if merge and provider in self.providers:
                        # Merge with existing settings
                        existing = self.providers[provider].dict()
                        existing.update(provider_data)
                        self.providers[provider] = ProviderSettings(**existing)
                    else:
                        self.providers[provider] = ProviderSettings(**provider_data)
                        
                except ValueError:
                    self.logger.warning(f"Unknown provider in import: {provider_name}")
        
        self.save()
        self.logger.info(f"Imported app sync config from {file_path}")
    
    def reset_to_defaults(self):
        """Reset configuration to defaults."""
        self.global_settings = GlobalSyncSettings()
        self.providers.clear()
        self.save()
    
    def get_config_summary(self) -> Dict[str, Any]:
        """Get a summary of the current configuration.
        
        Returns:
            Configuration summary
        """
        return {
            'global_settings': {
                'sync_on_startup': self.global_settings.sync_on_startup,
                'auto_resolve_conflicts': self.global_settings.auto_resolve_conflicts,
                'default_conflict_strategy': self.global_settings.default_conflict_strategy.value,
                'max_concurrent_syncs': self.global_settings.max_concurrent_syncs,
                'offline_mode': self.global_settings.offline_mode
            },
            'providers': {
                provider.value: {
                    'enabled': settings.enabled,
                    'auto_sync': settings.auto_sync,
                    'sync_direction': settings.sync_direction.value,
                    'conflict_strategy': settings.conflict_strategy.value,
                    'project_mappings_count': len(settings.project_mappings),
                    'tag_mappings_count': len(settings.tag_mappings)
                }
                for provider, settings in self.providers.items()
            },
            'stats': {
                'total_providers': len(self.providers),
                'enabled_providers': len(self.get_enabled_providers()),
                'total_project_mappings': sum(len(s.project_mappings) for s in self.providers.values()),
                'total_tag_mappings': sum(len(s.tag_mappings) for s in self.providers.values())
            }
        }


# Global instance
_config_manager: Optional[AppSyncConfigManager] = None


def get_app_sync_config_manager() -> AppSyncConfigManager:
    """Get the global app sync configuration manager."""
    global _config_manager
    if _config_manager is None:
        _config_manager = AppSyncConfigManager()
    return _config_manager


def get_provider_config(provider: AppSyncProvider) -> AppSyncConfig:
    """Get configuration for a specific provider.
    
    Args:
        provider: The sync provider
        
    Returns:
        Complete configuration for the provider
    """
    return get_app_sync_config_manager().get_provider_config(provider)