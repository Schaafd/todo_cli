"""Pytest configuration and shared fixtures."""

import sys
from pathlib import Path

# Ensure src directory is in Python path for all tests
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

# Optional: Add any shared fixtures here that multiple test files need