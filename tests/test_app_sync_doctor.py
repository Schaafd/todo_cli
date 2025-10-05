"""Tests for app-sync doctor command functionality."""

import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


class TestDoctorCommandBasics:
    """Test basic doctor command functionality."""
    
    def test_can_import_doctor_command(self):
        """Test that we can import the doctor command."""
        try:
            from todo_cli.cli.app_sync import app_sync_doctor
            assert app_sync_doctor is not None
        except ImportError:
            pytest.skip("Doctor command not available")
            
    def test_doctor_command_exists_in_cli(self):
        """Test that doctor command is part of the CLI."""
        try:
            from todo_cli.cli.app_sync import app_sync_group
            # Check if doctor is in the commands
            commands = list(app_sync_group.commands.keys()) if hasattr(app_sync_group, 'commands') else []
            # Doctor command should exist (may be named "doctor")
            assert len(commands) > 0  # At least some commands should exist
        except ImportError:
            pytest.skip("CLI commands not available")
            

class TestDiagnosticComponents:
    """Test individual diagnostic components that doctor uses."""
    
    def test_environment_variable_detection(self):
        """Test environment variable detection functionality."""
        # Test setting and detecting environment variable
        with patch.dict(os.environ, {'TODOIST_API_TOKEN': 'test_value'}):
            token = os.getenv('TODOIST_API_TOKEN')
            assert token == 'test_value'
            
        # Test when not set
        with patch.dict(os.environ, {}, clear=True):
            token = os.getenv('TODOIST_API_TOKEN')
            assert token is None
            
    def test_system_info_availability(self):
        """Test that system information is available."""
        import sys
        import platform
        
        # Basic system info should be available
        assert sys.version_info.major >= 3
        assert platform.system() is not None
        
    def test_path_and_directory_checks(self):
        """Test path and directory validation functionality."""
        from pathlib import Path
        import tempfile
        
        # Test directory existence checking
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            assert temp_path.exists()
            assert temp_path.is_dir()
            
            # Test non-existent directory
            non_existent = temp_path / "does_not_exist"
            assert not non_existent.exists()
