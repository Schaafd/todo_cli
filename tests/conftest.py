"""Pytest configuration and shared fixtures."""

import sys
import asyncio
import inspect
from pathlib import Path

import pytest

# Ensure src directory is in Python path for all tests
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


@pytest.fixture
def isolated_cli_config(tmp_path, monkeypatch):
    """Provide a CLI config path that cannot touch the user's real ~/.todo."""
    monkeypatch.setenv("HOME", str(tmp_path / "home"))

    from todo_cli.config import Config, ConfigModel
    from todo_cli.storage import reset_storage

    Config._instance = None
    reset_storage()

    data_dir = tmp_path / "todo-data"
    backup_dir = tmp_path / "todo-backups"
    config = ConfigModel(data_dir=str(data_dir), backup_dir=str(backup_dir))
    config_path = tmp_path / "config.yaml"
    config_path.write_text(config.to_yaml(), encoding="utf-8")

    yield config_path, data_dir, backup_dir

    Config._instance = None
    reset_storage()


@pytest.hookimpl(tryfirst=True)
def pytest_pyfunc_call(pyfuncitem):
    """Execute async tests without external plugins."""
    testfunction = pyfuncitem.obj
    if inspect.iscoroutinefunction(testfunction):
        loop = asyncio.new_event_loop()
        try:
            asyncio.set_event_loop(loop)
            sig = inspect.signature(testfunction)
            call_kwargs = {name: pyfuncitem.funcargs[name] for name in sig.parameters}
            loop.run_until_complete(testfunction(**call_kwargs))
        finally:
            asyncio.set_event_loop(None)
            loop.close()
        return True
    return None
