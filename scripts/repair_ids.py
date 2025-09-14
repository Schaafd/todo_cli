#!/usr/bin/env python3
"""
Script to repair duplicate todo IDs in existing todo projects.

This script loads each project, reassigns IDs sequentially (1, 2, 3, ...),
and saves the project with clean, unique IDs.
"""

import sys
import argparse
from pathlib import Path
from typing import Dict, Any

# Add the src directory to the path so we can import our modules
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from todo_cli.storage import Storage
from todo_cli.config import ConfigModel


def repair_project_ids(
    storage: Storage, project_name: str, dry_run: bool = False
) -> Dict[str, Any]:
    """Repair IDs for a single project.

    Args:
        storage: Storage instance
        project_name: Name of project to repair
        dry_run: If True, only show what would be changed without saving

    Returns:
        Dict with repair results
    """
    try:
        project, todos = storage.load_project(project_name)
        if project is None:
            return {"project": project_name, "changed": False, "reason": "load_failed"}

        if not todos:
            return {"project": project_name, "changed": False, "reason": "no_todos"}

        # Check for duplicate IDs
        original_ids = [t.id for t in todos]
        has_duplicates = len(original_ids) != len(set(original_ids))

        if not has_duplicates:
            return {
                "project": project_name,
                "changed": False,
                "reason": "no_duplicates",
            }

        # Preserve order as parsed, reassign IDs sequentially
        for new_id, todo in enumerate(todos, start=1):
            todo.id = new_id

        new_ids = [t.id for t in todos]

        if dry_run:
            return {
                "project": project_name,
                "changed": True,
                "todo_count": len(todos),
                "original_ids": original_ids,
                "new_ids": new_ids,
                "dry_run": True,
            }

        # Backup before making changes
        if not storage.backup_project(project_name):
            return {
                "project": project_name,
                "changed": False,
                "reason": "backup_failed",
            }

        # Save with new IDs
        if not storage.save_project(project, todos):
            return {"project": project_name, "changed": False, "reason": "save_failed"}

        return {
            "project": project_name,
            "changed": True,
            "todo_count": len(todos),
            "original_ids": original_ids,
            "new_ids": new_ids,
            "dry_run": False,
        }

    except Exception as e:
        return {
            "project": project_name,
            "changed": False,
            "reason": "error",
            "error": str(e),
        }


def repair_all_projects(
    storage: Storage, dry_run: bool = False, verbose: bool = False
) -> Dict[str, Any]:
    """Repair IDs for all projects.

    Args:
        storage: Storage instance
        dry_run: If True, only show what would be changed without saving
        verbose: If True, show detailed output

    Returns:
        Dict with overall results
    """
    project_names = storage.list_projects()
    if not project_names:
        return {"total_projects": 0, "changed_projects": 0, "results": []}

    results = []
    changed_count = 0

    for project_name in sorted(project_names):
        result = repair_project_ids(storage, project_name, dry_run)
        results.append(result)

        if result["changed"]:
            changed_count += 1

        if verbose:
            print(f"\n📁 Project: {project_name}")
            if result["changed"]:
                action = "Would repair" if dry_run else "Repaired"
                print(f"   {action}: {result['todo_count']} todos")
                print(f"   Original IDs: {result['original_ids']}")
                print(f"   New IDs: {result['new_ids']}")
            else:
                reason = result.get("reason", "unknown")
                print(f"   No changes needed: {reason}")

    return {
        "total_projects": len(project_names),
        "changed_projects": changed_count,
        "results": results,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Repair duplicate todo IDs in existing projects"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be changed without saving",
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Show detailed output"
    )
    parser.add_argument(
        "--project",
        help="Repair specific project only (otherwise repairs all projects)",
    )

    args = parser.parse_args()

    # Initialize storage
    try:
        config = ConfigModel()
        storage = Storage(config)
    except Exception as e:
        print(f"❌ Error initializing storage: {e}")
        return 1

    print("🔧 Todo ID Repair Tool")
    print("=" * 50)

    if args.dry_run:
        print("🔍 DRY RUN MODE - No changes will be made")

    # Repair single project or all projects
    if args.project:
        result = repair_project_ids(storage, args.project, args.dry_run)

        print(f"\n📁 Project: {args.project}")
        if result["changed"]:
            action = "Would repair" if args.dry_run else "Repaired"
            print(f"✅ {action}: {result['todo_count']} todos")
            if args.verbose:
                print(f"   Original IDs: {result['original_ids']}")
                print(f"   New IDs: {result['new_ids']}")
        else:
            reason = result.get("reason", "unknown")
            print(f"ℹ️  No changes needed: {reason}")

        return 0 if not result.get("error") else 1

    else:
        # Repair all projects
        summary = repair_all_projects(storage, args.dry_run, args.verbose)

        print(f"\n📊 Summary")
        print(f"   Total projects: {summary['total_projects']}")
        print(f"   Projects needing repair: {summary['changed_projects']}")

        if args.dry_run and summary["changed_projects"] > 0:
            print(f"\n💡 Run without --dry-run to apply these changes")
        elif not args.dry_run and summary["changed_projects"] > 0:
            print(f"✅ Successfully repaired {summary['changed_projects']} projects")

        return 0


if __name__ == "__main__":
    sys.exit(main())
