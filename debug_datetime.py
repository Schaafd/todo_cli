#!/usr/bin/env python3

import os
import sys
from datetime import datetime, timezone

# Add the current directory to the path to import todo_cli modules
sys.path.insert(0, './src')

from todo_cli.todo import Todo, Priority
from todo_cli.project import Project
from todo_cli.storage import Storage
from todo_cli.config import ConfigModel

def check_datetime_awareness():
    """Debug datetime timezone awareness issues."""
    
    print("=== Debugging datetime timezone awareness ===")
    
    # Create a test todo with various datetime fields
    test_todo = Todo(
        id=1,
        text="Test todo",
        project="debug",
    )
    
    print(f"Todo created time: {test_todo.created}, timezone: {test_todo.created.tzinfo}")
    print(f"Todo modified time: {test_todo.modified}, timezone: {test_todo.modified.tzinfo}")
    print(f"Todo due_date: {test_todo.due_date}, timezone: {test_todo.due_date.tzinfo if test_todo.due_date else 'None'}")
    print(f"Todo start_date: {test_todo.start_date}, timezone: {test_todo.start_date.tzinfo if test_todo.start_date else 'None'}")
    print(f"Todo completed_date: {test_todo.completed_date}, timezone: {test_todo.completed_date.tzinfo if test_todo.completed_date else 'None'}")
    
    print("\n=== Testing Project creation and stats update ===")
    
    # Create a test project
    test_project = Project(name="debug")
    print(f"Project created: {test_project.created}, timezone: {test_project.created.tzinfo}")
    print(f"Project modified: {test_project.modified}, timezone: {test_project.modified.tzinfo}")
    
    # Try updating stats with the test todo
    print("\n=== Calling project.update_stats([test_todo]) ===")
    try:
        test_project.update_stats([test_todo])
        print("Stats update successful!")
        print(f"Project stats: {test_project.stats}")
    except Exception as e:
        print(f"Error during stats update: {e}")
        print(f"Todo modified: {test_todo.modified}, type: {type(test_todo.modified)}, timezone: {test_todo.modified.tzinfo}")
        print(f"Project created: {test_project.created}, type: {type(test_project.created)}, timezone: {test_project.created.tzinfo}")
    
    # Test with multiple todos
    test_todo2 = Todo(
        id=2,
        text="Test todo 2",
        project="debug",
        due_date=datetime.now(timezone.utc)
    )
    
    print(f"\nSecond todo due_date: {test_todo2.due_date}, timezone: {test_todo2.due_date.tzinfo}")
    
    try:
        test_project.update_stats([test_todo, test_todo2])
        print("Stats update with multiple todos successful!")
    except Exception as e:
        print(f"Error during stats update with multiple todos: {e}")

if __name__ == "__main__":
    check_datetime_awareness()