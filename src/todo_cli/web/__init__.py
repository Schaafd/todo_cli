"""
Todo CLI Web Module

This module provides web interface functionality for the Todo CLI application,
including a Progressive Web App (PWA) and REST API endpoints.
"""

from .server import app, start_server

__all__ = ['app', 'start_server']