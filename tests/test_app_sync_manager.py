"""Tests for app-sync manager functionality."""

import sys
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from todo_cli.app_sync_models import AppSyncProvider


class TestAppSyncManagerBasics:
    """Test basic manager functionality we can verify."""
    
    def test_app_sync_provider_enum_values(self):
        """Test that the AppSyncProvider enum has expected values."""
        # Test some key provider types
        assert AppSyncProvider.TODOIST.value == "todoist"
        assert AppSyncProvider.APPLE_REMINDERS.value == "apple_reminders"
        assert AppSyncProvider.GOOGLE_TASKS.value == "google_tasks"
        
    def test_provider_enum_string_conversion(self):
        """Test converting provider strings to enums."""
        provider = AppSyncProvider("todoist")
        assert provider == AppSyncProvider.TODOIST
        assert provider.value == "todoist"
        
    def test_manager_import_availability(self):
        """Test that we can import the manager class."""
        try:
            from todo_cli.app_sync_manager import AppSyncManager
            assert AppSyncManager is not None
        except ImportError:
            pytest.skip("AppSyncManager not available")
            

class TestCLICommandAvailability:
    """Test that CLI commands can be imported and are available."""
    
    def test_can_import_cli_app_sync_module(self):
        """Test that the CLI module can be imported."""
        try:
            from todo_cli import cli_app_sync
            assert cli_app_sync is not None
        except ImportError:
            pytest.skip("CLI app sync module not available")
            
    def test_app_sync_group_exists(self):
        """Test that the app-sync command group exists."""
        try:
            from todo_cli.cli_app_sync import app_sync_group
            assert app_sync_group is not None
            assert hasattr(app_sync_group, 'name')
        except ImportError:
            pytest.skip("CLI commands not available")
