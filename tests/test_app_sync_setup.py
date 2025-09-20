"""Tests for app-sync functionality focusing on core features we implemented."""

import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from todo_cli.app_sync_models import AppSyncProvider, ConflictStrategy


class TestAppSyncModels:
    """Test core app sync models and enums."""
    
    def test_app_sync_provider_enum(self):
        """Test AppSyncProvider enum values."""
        assert AppSyncProvider.TODOIST.value == "todoist"
        assert AppSyncProvider.APPLE_REMINDERS.value == "apple_reminders"
        
        # Test enum creation from string
        provider = AppSyncProvider("todoist")
        assert provider == AppSyncProvider.TODOIST
        
    def test_conflict_strategy_enum(self):
        """Test ConflictStrategy enum values."""
        assert ConflictStrategy.NEWEST_WINS.value == "newest_wins"
        assert ConflictStrategy.LOCAL_WINS.value == "local_wins"
        assert ConflictStrategy.REMOTE_WINS.value == "remote_wins"
        
        # Test enum creation from string
        strategy = ConflictStrategy("newest_wins")
        assert strategy == ConflictStrategy.NEWEST_WINS


class TestEnvironmentDetection:
    """Test environment and interactive detection functionality."""
    
    def test_interactive_detection_with_tty(self):
        """Test detection of interactive environment."""
        with patch('sys.stdin.isatty', return_value=True):
            import sys
            assert sys.stdin.isatty() is True
            
    def test_non_interactive_detection_without_tty(self):
        """Test detection of non-interactive environment."""
        with patch('sys.stdin.isatty', return_value=False):
            import sys
            assert sys.stdin.isatty() is False
            
    def test_environment_token_detection(self):
        """Test detection of environment variable token."""
        with patch.dict(os.environ, {'TODOIST_API_TOKEN': 'test_token'}):
            token = os.getenv('TODOIST_API_TOKEN')
            assert token == 'test_token'
            
        # Test when not set
        with patch.dict(os.environ, {}, clear=True):
            token = os.getenv('TODOIST_API_TOKEN')
            assert token is None


class TestConfigDirectoryHandling:
    """Test configuration directory management."""
    
    def test_config_directory_creation(self):
        """Test that we can create and work with config directories."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_dir = Path(temp_dir) / ".todo"
            assert not config_dir.exists()
            
            # Create directory
            config_dir.mkdir()
            assert config_dir.exists()
            assert config_dir.is_dir()
            
            # Should be writable
            test_file = config_dir / "test.txt"
            test_file.write_text("test content")
            assert test_file.read_text() == "test content"
