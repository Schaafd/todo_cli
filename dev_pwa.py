#!/usr/bin/env python3
"""
Development script for Todo CLI PWA.

This script provides utilities for PWA development including:
- Starting the development server
- Watching for file changes
- Running tests
- Building for production
"""

import os
import sys
import subprocess
import argparse
from pathlib import Path


def start_dev_server(host="127.0.0.1", port=8000, debug=True):
    """Start the PWA development server."""
    print(f"🚀 Starting Todo CLI PWA development server...")
    print(f"📍 Server: http://{host}:{port}")
    print(f"🔧 Debug mode: {debug}")
    print(f"📁 PWA files: src/todo_cli/web/")
    print()
    print("💡 Development tips:")
    print(f"   - Add ?debug=true to URL for enhanced logging")
    print(f"   - API endpoints available at http://{host}:{port}/api/")
    print(f"   - Health check: http://{host}:{port}/health")
    print()
    
    # Start server with development settings
    env = os.environ.copy()
    if debug:
        env["PYTHONUNBUFFERED"] = "1"
    
    cmd = [
        sys.executable, "-m", "uvicorn", 
        "todo_cli.web.server:app",
        "--host", host,
        "--port", str(port),
        "--reload",
        "--reload-dir", "src/todo_cli/web",
        "--log-level", "info"
    ]
    
    if debug:
        cmd.extend(["--access-log"])
    
    try:
        subprocess.run(cmd, env=env)
    except KeyboardInterrupt:
        print("\n👋 Development server stopped")


def check_health(host="127.0.0.1", port=8000):
    """Check if the PWA server is healthy."""
    import requests
    
    try:
        response = requests.get(f"http://{host}:{port}/health", timeout=5)
        if response.status_code == 200:
            data = response.json()
            print("✅ Server is healthy")
            print(f"   Status: {data.get('status')}")
            print(f"   Version: {data.get('version')}")
            print(f"   Total tasks: {data.get('total_tasks')}")
            print(f"   Total projects: {data.get('total_projects')}")
            return True
        else:
            print(f"❌ Server returned status {response.status_code}")
            return False
    except requests.exceptions.RequestException as e:
        print(f"❌ Server is not reachable: {e}")
        return False


def run_tests():
    """Run PWA-related tests."""
    print("🧪 Running PWA tests...")
    
    # Run API contract tests
    result = subprocess.run([
        sys.executable, "-m", "pytest", 
        "tests/test_api_contracts.py",
        "-v"
    ])
    
    return result.returncode == 0


def validate_files():
    """Validate PWA files exist and are properly structured."""
    print("🔍 Validating PWA files...")
    
    base_dir = Path("src/todo_cli/web")
    required_files = [
        "server.py",
        "static/js/config.js",
        "static/js/api.js",
        "static/js/ui.js", 
        "static/js/app.js",
        "static/css/main.css",
        "static/manifest.json",
        "static/sw.js",
        "templates/index.html"
    ]
    
    missing_files = []
    for file_path in required_files:
        if not (base_dir / file_path).exists():
            missing_files.append(file_path)
    
    if missing_files:
        print("❌ Missing required files:")
        for file_path in missing_files:
            print(f"   - {file_path}")
        return False
    
    print("✅ All required PWA files are present")
    return True


def main():
    parser = argparse.ArgumentParser(description="Todo CLI PWA Development Tools")
    parser.add_argument("--host", default="127.0.0.1", help="Server host")
    parser.add_argument("--port", type=int, default=8000, help="Server port")
    parser.add_argument("--no-debug", action="store_true", help="Disable debug mode")
    
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Start server command
    start_parser = subparsers.add_parser("start", help="Start development server")
    
    # Health check command
    health_parser = subparsers.add_parser("health", help="Check server health")
    
    # Test command
    test_parser = subparsers.add_parser("test", help="Run tests")
    
    # Validate command
    validate_parser = subparsers.add_parser("validate", help="Validate PWA files")
    
    args = parser.parse_args()
    
    if args.command == "start":
        start_dev_server(args.host, args.port, not args.no_debug)
    elif args.command == "health":
        success = check_health(args.host, args.port)
        sys.exit(0 if success else 1)
    elif args.command == "test":
        success = run_tests()
        sys.exit(0 if success else 1)
    elif args.command == "validate":
        success = validate_files()
        sys.exit(0 if success else 1)
    else:
        # Default to start server
        start_dev_server(args.host, args.port, not args.no_debug)


if __name__ == "__main__":
    main()