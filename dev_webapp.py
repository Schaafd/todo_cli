#!/usr/bin/env python3
"""
Development script for Todo CLI Web App.

This script provides utilities for web app development including:
- Starting the development server
- Database management
- User management
"""

import sys
import argparse
import logging
from pathlib import Path


def start_server(host: str = "127.0.0.1", port: int = 8080, reload: bool = True):
    """Start the web app development server.
    
    Args:
        host: Server host
        port: Server port
        reload: Enable auto-reload on code changes
    """
    import uvicorn
    
    print(f"🚀 Starting Todo CLI Web App development server...")
    print(f"📍 Server: http://{host}:{port}")
    print(f"📚 API Docs: http://{host}:{port}/docs")
    print(f"🔧 Auto-reload: {reload}")
    print()
    print("💡 Development tips:")
    print(f"   - API documentation: http://{host}:{port}/docs")
    print(f"   - Health check: http://{host}:{port}/health")
    print(f"   - Auth endpoints: http://{host}:{port}/api/auth")
    print()
    
    try:
        uvicorn.run(
            "todo_cli.webapp.server.app:app",
            host=host,
            port=port,
            reload=reload,
            reload_dirs=["src/todo_cli/webapp"] if reload else None,
            log_level="info"
        )
    except KeyboardInterrupt:
        print("\n👋 Development server stopped")


def db_info():
    """Display database information."""
    from todo_cli.webapp.server.database import get_user_db
    
    db = get_user_db()
    print(f"📊 Database Information")
    print(f"   Location: {db.db_path}")
    print(f"   Exists: {db.db_path.exists()}")
    
    if db.db_path.exists():
        users = db.list_users(limit=10)
        print(f"   Users: {len(users)}")
        
        if users:
            print("\n👥 Recent Users:")
            for user in users[:5]:
                print(f"   - {user.username} ({user.email})")
                print(f"     Created: {user.created_at}")
                print(f"     Active: {user.is_active}")


def create_user(username: str, email: str, password: str):
    """Create a new user.
    
    Args:
        username: Username
        email: Email address
        password: Password
    """
    from todo_cli.webapp.server.auth import get_auth_service
    
    try:
        auth_service = get_auth_service()
        user = auth_service.register_user(username, email, password)
        print(f"✅ User created successfully!")
        print(f"   ID: {user.id}")
        print(f"   Username: {user.username}")
        print(f"   Email: {user.email}")
    except ValueError as e:
        print(f"❌ Failed to create user: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        sys.exit(1)


def cleanup_sessions():
    """Clean up expired sessions."""
    from todo_cli.webapp.server.auth import get_auth_service
    
    auth_service = get_auth_service()
    cleaned = auth_service.cleanup_expired_sessions()
    print(f"🧹 Cleaned up {cleaned} expired sessions")


def main():
    parser = argparse.ArgumentParser(description="Todo CLI Web App Development Tools")
    parser.add_argument("--host", default="127.0.0.1", help="Server host")
    parser.add_argument("--port", type=int, default=8080, help="Server port")
    parser.add_argument("--no-reload", action="store_true", help="Disable auto-reload")
    
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Start server command (default)
    start_parser = subparsers.add_parser("start", help="Start development server")
    
    # Database info command
    db_parser = subparsers.add_parser("db-info", help="Show database information")
    
    # Create user command
    user_parser = subparsers.add_parser("create-user", help="Create a new user")
    user_parser.add_argument("username", help="Username")
    user_parser.add_argument("email", help="Email address")
    user_parser.add_argument("password", help="Password")
    
    # Cleanup sessions command
    cleanup_parser = subparsers.add_parser("cleanup", help="Clean up expired sessions")
    
    args = parser.parse_args()
    
    if args.command == "start":
        start_server(args.host, args.port, not args.no_reload)
    elif args.command == "db-info":
        db_info()
    elif args.command == "create-user":
        create_user(args.username, args.email, args.password)
    elif args.command == "cleanup":
        cleanup_sessions()
    else:
        # Default to start server
        start_server(args.host, args.port, not args.no_reload)


if __name__ == "__main__":
    main()
