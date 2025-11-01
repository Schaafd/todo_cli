"""Pytest configuration and shared fixtures."""

import sys
import asyncio
import inspect
from pathlib import Path

import pytest

# Ensure src directory is in Python path for all tests
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


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