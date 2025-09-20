#!/usr/bin/env python3
"""Test script for the improved interactive setup."""

import subprocess
import sys
import os

def test_setup_modes():
    """Test different setup modes."""
    
    api_token = os.getenv('TODOIST_API_TOKEN')
    if not api_token:
        print("❌ TODOIST_API_TOKEN environment variable not set")
        print("Please set it with: export TODOIST_API_TOKEN='your_token_here'")
        return
    
    print(f"🚀 Testing improved setup modes...")
    print(f"✅ API token available: {api_token[:8]}...")
    
    # Test 1: Non-interactive mode (should work without hanging)
    print("\n📝 Test 1: Non-interactive setup")
    print("Command: uv run todo app-sync setup todoist --no-interactive")
    
    if input("Run this test? (y/n): ").lower() == 'y':
        try:
            result = subprocess.run([
                "uv", "run", "todo", "app-sync", "setup", "todoist", 
                "--no-interactive", "--api-token", api_token
            ], timeout=120, capture_output=True, text=True)
            
            print(f"Exit code: {result.returncode}")
            if result.stdout:
                print(f"Output: {result.stdout}")
            if result.stderr:
                print(f"Error: {result.stderr}")
        except subprocess.TimeoutExpired:
            print("❌ Test timed out after 2 minutes!")
        except Exception as e:
            print(f"❌ Test failed: {e}")
    
    # Test 2: Interactive mode with skip mapping
    print("\n📝 Test 2: Interactive setup with skip mapping")
    print("Command: uv run todo app-sync setup todoist --interactive --skip-mapping")
    
    if input("Run this test? (y/n): ").lower() == 'y':
        try:
            result = subprocess.run([
                "uv", "run", "todo", "app-sync", "setup", "todoist", 
                "--interactive", "--skip-mapping", "--api-token", api_token
            ], timeout=120, capture_output=True, text=True)
            
            print(f"Exit code: {result.returncode}")
            if result.stdout:
                print(f"Output: {result.stdout}")
            if result.stderr:
                print(f"Error: {result.stderr}")
        except subprocess.TimeoutExpired:
            print("❌ Test timed out after 2 minutes!")
        except Exception as e:
            print(f"❌ Test failed: {e}")
    
    # Test 3: Check status after setup
    print("\n📝 Test 3: Check app-sync status")
    print("Command: uv run todo app-sync status")
    
    if input("Run this test? (y/n): ").lower() == 'y':
        try:
            result = subprocess.run([
                "uv", "run", "todo", "app-sync", "status"
            ], timeout=30, capture_output=True, text=True)
            
            print(f"Exit code: {result.returncode}")
            if result.stdout:
                print(f"Output: {result.stdout}")
            if result.stderr:
                print(f"Error: {result.stderr}")
        except subprocess.TimeoutExpired:
            print("❌ Test timed out!")
        except Exception as e:
            print(f"❌ Test failed: {e}")
    
    print("\n✅ Testing completed!")

if __name__ == "__main__":
    test_setup_modes()