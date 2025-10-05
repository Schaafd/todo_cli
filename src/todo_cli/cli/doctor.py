"""Doctor command for Todo CLI maintenance and diagnostics.

This module provides diagnostic and repair commands for the Todo CLI,
including datetime timezone fixes, data validation, and integrity checks.
"""

import click
import json
from datetime import datetime, timezone
from typing import List, Dict, Any, Tuple, Optional
from pathlib import Path

from ..config import get_config
from ..storage import Storage
from ..domain import Todo, Project
from ..utils.datetime import ensure_aware, now_utc, to_iso_string


@click.group()
def doctor():
    """Diagnostic and maintenance commands for Todo CLI."""
    pass


@doctor.command()
@click.option('--fix', is_flag=True, help='Fix timezone issues automatically')
@click.option('--verbose', '-v', is_flag=True, help='Show detailed information')
def fix_datetimes(fix: bool, verbose: bool):
    """Scan for and fix datetime timezone issues.
    
    This command identifies todos and projects with naive datetime fields
    and converts them to timezone-aware UTC datetimes.
    """
    config = get_config()
    storage = Storage(config)
    
    click.echo("🔍 Scanning for datetime timezone issues...")
    
    issues_found = []
    todos_fixed = 0
    projects_fixed = 0
    
    # Check all projects
    project_names = storage.list_projects()
    
    if not project_names:
        project_names = [config.default_project]
    
    for project_name in project_names:
        if verbose:
            click.echo(f"  Checking project: {project_name}")
        
        try:
            project, todos = storage.load_project(project_name)
            if not project:
                continue
            
            project_issues = _check_project_datetimes(project, verbose)
            todo_issues = _check_todos_datetimes(todos, verbose)
            
            if project_issues or todo_issues:
                issues_found.append({
                    'project': project_name,
                    'project_issues': project_issues,
                    'todo_issues': todo_issues,
                    'project_obj': project,
                    'todos_obj': todos
                })
        
        except Exception as e:
            click.echo(f"  ❌ Error loading project {project_name}: {e}")
            continue
    
    # Report findings
    total_issues = sum(len(p['project_issues']) + len(p['todo_issues']) for p in issues_found)
    
    if total_issues == 0:
        click.echo("✅ No timezone issues found! All datetimes are properly timezone-aware.")
        return
    
    click.echo(f"\n📊 Found {total_issues} timezone issues across {len(issues_found)} projects:")
    
    for project_data in issues_found:
        project_name = project_data['project']
        project_issues = project_data['project_issues']
        todo_issues = project_data['todo_issues']
        
        click.echo(f"\n  📁 Project: {project_name}")
        
        if project_issues:
            click.echo(f"    🗂️  Project issues: {len(project_issues)}")
            for issue in project_issues:
                click.echo(f"      - {issue}")
        
        if todo_issues:
            click.echo(f"    📝 Todo issues: {len(todo_issues)}")
            for issue in todo_issues:
                click.echo(f"      - {issue}")
    
    if not fix:
        click.echo(f"\n💡 Run with --fix to automatically repair {total_issues} timezone issues.")
        return
    
    # Apply fixes
    click.echo(f"\n🔧 Fixing {total_issues} timezone issues...")
    
    for project_data in issues_found:
        project_name = project_data['project']
        project = project_data['project_obj']
        todos = project_data['todos_obj']
        
        # Fix project datetimes
        if project_data['project_issues']:
            _fix_project_datetimes(project)
            projects_fixed += 1
            if verbose:
                click.echo(f"  ✅ Fixed project {project_name}")
        
        # Fix todo datetimes
        todos_fixed_in_project = 0
        for todo in todos:
            if _fix_todo_datetimes(todo):
                todos_fixed_in_project += 1
        
        if todos_fixed_in_project > 0:
            todos_fixed += todos_fixed_in_project
            if verbose:
                click.echo(f"  ✅ Fixed {todos_fixed_in_project} todos in {project_name}")
        
        # Save the project with fixed data
        try:
            success = storage.save_project(project, todos)
            if not success:
                click.echo(f"  ❌ Failed to save fixed project {project_name}")
        except Exception as e:
            click.echo(f"  ❌ Error saving project {project_name}: {e}")
    
    click.echo(f"\n✅ Timezone fixes complete!")
    click.echo(f"   Projects fixed: {projects_fixed}")
    click.echo(f"   Todos fixed: {todos_fixed}")
    click.echo("   All datetimes are now timezone-aware UTC.")


@doctor.command(name="validate-runtime")
@click.option('--strict', is_flag=True, help='Use strict validation mode (raise exceptions)')
@click.option('--verbose', '-v', is_flag=True, help='Show detailed validation information')
def validate_runtime(strict: bool, verbose: bool):
    """Validate datetime fields at runtime with comprehensive checking.
    
    This command performs live validation of all Todo and Project objects,
    checking timezone awareness and offering auto-fixes for issues found.
    """
    from ..utils.validation import DateTimeValidator, DateTimeValidationError
    
    config = get_config()
    storage = Storage(config)
    validator = DateTimeValidator(strict_mode=strict)
    
    click.echo("🔍 Runtime datetime validation started...")
    
    validation_results = {
        'projects_validated': 0,
        'todos_validated': 0,
        'projects_fixed': 0,
        'todos_fixed': 0,
        'total_errors': 0,
        'total_warnings': 0
    }
    
    # Get all projects
    project_names = storage.list_projects()
    
    if not project_names:
        project_names = [config.default_project]
    
    try:
        for project_name in project_names:
            if verbose:
                click.echo(f"  Validating project: {project_name}")
            
            try:
                project, todos = storage.load_project(project_name)
                if not project:
                    continue
                
                # Validate project
                project_result = validator.validate_project_datetimes(project)
                validation_results['projects_validated'] += 1
                
                if project_result['fixed_fields']:
                    validation_results['projects_fixed'] += 1
                    if verbose:
                        click.echo(f"    ✅ Fixed {len(project_result['fixed_fields'])} project fields")
                
                validation_results['total_errors'] += len(project_result['errors'])
                validation_results['total_warnings'] += len(project_result['warnings'])
                
                # Validate todos
                for todo in todos:
                    todo_result = validator.validate_todo_datetimes(todo)
                    validation_results['todos_validated'] += 1
                    
                    if todo_result['fixed_fields']:
                        validation_results['todos_fixed'] += 1
                        if verbose:
                            click.echo(f"    ✅ Fixed {len(todo_result['fixed_fields'])} fields in todo {todo.id}")
                    
                    validation_results['total_errors'] += len(todo_result['errors'])
                    validation_results['total_warnings'] += len(todo_result['warnings'])
                
                # Save project if any fixes were applied
                if project_result['fixed_fields'] or any(validator.validate_todo_datetimes(t)['fixed_fields'] for t in todos):
                    if storage.save_project(project, todos):
                        if verbose:
                            click.echo(f"    💾 Saved fixes for project {project_name}")
                    else:
                        click.echo(f"    ❌ Failed to save fixes for project {project_name}")
                
            except DateTimeValidationError as e:
                click.echo(f"  ❌ Validation failed for {project_name}: {e}")
                if e.suggestions:
                    for suggestion in e.suggestions:
                        click.echo(f"     💡 {suggestion}")
                validation_results['total_errors'] += 1
                if strict:
                    raise
            except Exception as e:
                click.echo(f"  ❌ Error validating project {project_name}: {e}")
                validation_results['total_errors'] += 1
                continue
        
        # Show summary
        click.echo(f"\n📊 Runtime Validation Results:")
        click.echo(f"   Projects validated: {validation_results['projects_validated']}")
        click.echo(f"   Todos validated: {validation_results['todos_validated']}")
        click.echo(f"   Projects with fixes: {validation_results['projects_fixed']}")
        click.echo(f"   Todos with fixes: {validation_results['todos_fixed']}")
        click.echo(f"   Total errors: {validation_results['total_errors']}")
        click.echo(f"   Total warnings: {validation_results['total_warnings']}")
        
        if validation_results['total_errors'] == 0:
            click.echo("✅ All datetime validations passed!")
        else:
            click.echo("⚠️  Some validation issues were found")
            if not strict:
                click.echo("   Run with --strict to see detailed error messages")
        
        if validation_results['projects_fixed'] > 0 or validation_results['todos_fixed'] > 0:
            click.echo("🔧 Auto-fixes have been applied and saved")
    
    except KeyboardInterrupt:
        click.echo("\n⚠️ Validation interrupted by user")
    except Exception as e:
        click.echo(f"\n❌ Validation failed with error: {e}")
        if strict:
            raise


@doctor.command()
@click.option('--verbose', '-v', is_flag=True, help='Show detailed information')
def validate(verbose: bool):
    """Validate data integrity and consistency.
    
    Checks for duplicate IDs, orphaned mappings, invalid references,
    and other data consistency issues.
    """
    config = get_config()
    storage = Storage(config)
    
    click.echo("🔍 Validating data integrity...")
    
    issues = []
    total_todos = 0
    total_projects = 0
    
    # Check all projects
    project_names = storage.list_projects()
    
    if not project_names:
        project_names = [config.default_project]
    
    all_todo_ids = set()
    
    for project_name in project_names:
        if verbose:
            click.echo(f"  Validating project: {project_name}")
        
        try:
            project, todos = storage.load_project(project_name)
            if not project:
                continue
            
            total_projects += 1
            total_todos += len(todos)
            
            # Check for duplicate IDs within project
            project_todo_ids = [t.id for t in todos]
            if len(project_todo_ids) != len(set(project_todo_ids)):
                duplicates = [id for id in project_todo_ids if project_todo_ids.count(id) > 1]
                issues.append(f"Project {project_name}: Duplicate todo IDs {set(duplicates)}")
            
            # Check for global duplicate IDs
            for todo_id in project_todo_ids:
                if todo_id in all_todo_ids:
                    issues.append(f"Global duplicate todo ID {todo_id} in project {project_name}")
                all_todo_ids.add(todo_id)
            
            # Validate project fields
            if not project.name:
                issues.append(f"Project {project_name}: Missing name field")
            
            if not isinstance(project.created, datetime):
                issues.append(f"Project {project_name}: Invalid created date type")
            elif project.created.tzinfo is None:
                issues.append(f"Project {project_name}: Naive created datetime")
            
            if not isinstance(project.modified, datetime):
                issues.append(f"Project {project_name}: Invalid modified date type")
            elif project.modified.tzinfo is None:
                issues.append(f"Project {project_name}: Naive modified datetime")
            
            # Validate todos
            for todo in todos:
                if not todo.text.strip():
                    issues.append(f"Todo {todo.id} in {project_name}: Empty text")
                
                if todo.created and todo.created.tzinfo is None:
                    issues.append(f"Todo {todo.id} in {project_name}: Naive created datetime")
                
                if todo.modified and todo.modified.tzinfo is None:
                    issues.append(f"Todo {todo.id} in {project_name}: Naive modified datetime")
                
                if todo.due_date and todo.due_date.tzinfo is None:
                    issues.append(f"Todo {todo.id} in {project_name}: Naive due_date datetime")
                
                if todo.start_date and todo.start_date.tzinfo is None:
                    issues.append(f"Todo {todo.id} in {project_name}: Naive start_date datetime")
                
                if todo.completed_date and todo.completed_date.tzinfo is None:
                    issues.append(f"Todo {todo.id} in {project_name}: Naive completed_date datetime")
        
        except Exception as e:
            issues.append(f"Project {project_name}: Failed to load - {e}")
            continue
    
    # Report results
    click.echo(f"\n📊 Validation complete:")
    click.echo(f"   Projects scanned: {total_projects}")
    click.echo(f"   Todos scanned: {total_todos}")
    click.echo(f"   Issues found: {len(issues)}")
    
    if issues:
        click.echo(f"\n❌ Issues found:")
        for issue in issues:
            click.echo(f"   - {issue}")
        click.echo(f"\n💡 Consider running 'doctor fix-datetimes --fix' to resolve timezone issues.")
    else:
        click.echo("✅ No validation issues found! Data integrity looks good.")


@doctor.command()
@click.option('--verbose', '-v', is_flag=True, help='Show detailed information')
def stats(verbose):
    """Show system statistics and health information."""
    config = get_config()
    storage = Storage(config)
    
    click.echo("📈 Todo CLI System Statistics")
    click.echo("=" * 40)
    
    # Basic counts
    project_names = storage.list_projects()
    total_projects = len(project_names)
    total_todos = 0
    completed_todos = 0
    overdue_todos = 0
    
    # Timezone analysis
    timezone_aware_todos = 0
    timezone_naive_todos = 0
    timezone_aware_projects = 0
    timezone_naive_projects = 0
    
    if not project_names:
        project_names = [config.default_project]
    
    for project_name in project_names:
        try:
            project, todos = storage.load_project(project_name)
            if not project:
                continue
                
            total_todos += len(todos)
            completed_todos += sum(1 for t in todos if t.completed)
            overdue_todos += sum(1 for t in todos if t.is_overdue() and not t.completed)
            
            # Analyze project timezone awareness
            project_tz_aware = True
            if project.created and project.created.tzinfo is None:
                project_tz_aware = False
            if project.modified and project.modified.tzinfo is None:
                project_tz_aware = False
            if project.deadline and project.deadline.tzinfo is None:
                project_tz_aware = False
            
            if project_tz_aware:
                timezone_aware_projects += 1
            else:
                timezone_naive_projects += 1
            
            # Analyze todo timezone awareness
            for todo in todos:
                todo_tz_aware = True
                for dt_field in [todo.created, todo.modified, todo.due_date, todo.start_date, todo.completed_date]:
                    if dt_field and dt_field.tzinfo is None:
                        todo_tz_aware = False
                        break
                
                if todo_tz_aware:
                    timezone_aware_todos += 1
                else:
                    timezone_naive_todos += 1
        
        except Exception:
            continue
    
    # Display statistics
    click.echo(f"Projects: {total_projects}")
    click.echo(f"Todos: {total_todos}")
    click.echo(f"  Completed: {completed_todos} ({completed_todos/max(1, total_todos)*100:.1f}%)")
    click.echo(f"  Overdue: {overdue_todos} ({overdue_todos/max(1, total_todos)*100:.1f}%)")
    
    click.echo(f"\n⏰ Timezone Awareness:")
    click.echo(f"  Projects with timezone-aware dates: {timezone_aware_projects}/{total_projects}")
    click.echo(f"  Todos with timezone-aware dates: {timezone_aware_todos}/{total_todos}")
    
    if timezone_naive_projects > 0 or timezone_naive_todos > 0:
        click.echo(f"\n⚠️  Found timezone issues:")
        if timezone_naive_projects > 0:
            click.echo(f"    Projects with naive datetimes: {timezone_naive_projects}")
        if timezone_naive_todos > 0:
            click.echo(f"    Todos with naive datetimes: {timezone_naive_todos}")
        click.echo(f"  💡 Run 'doctor fix-datetimes --fix' to resolve these issues.")
    else:
        click.echo("✅ All datetimes are timezone-aware!")


def _check_project_datetimes(project: Project, verbose: bool = False) -> List[str]:
    """Check project for timezone issues."""
    issues = []
    
    if project.created and project.created.tzinfo is None:
        issues.append("created field has naive datetime")
        if verbose:
            click.echo(f"    ⚠️  Project created: {project.created} (naive)")
    
    if project.modified and project.modified.tzinfo is None:
        issues.append("modified field has naive datetime")
        if verbose:
            click.echo(f"    ⚠️  Project modified: {project.modified} (naive)")
    
    if project.deadline and project.deadline.tzinfo is None:
        issues.append("deadline field has naive datetime")
        if verbose:
            click.echo(f"    ⚠️  Project deadline: {project.deadline} (naive)")
    
    if project.sync_last_update and project.sync_last_update.tzinfo is None:
        issues.append("sync_last_update field has naive datetime")
        if verbose:
            click.echo(f"    ⚠️  Project sync_last_update: {project.sync_last_update} (naive)")
    
    return issues


def _check_todos_datetimes(todos: List[Todo], verbose: bool = False) -> List[str]:
    """Check todos for timezone issues."""
    issues = []
    
    for todo in todos:
        todo_issues = []
        
        if todo.created and todo.created.tzinfo is None:
            todo_issues.append("created")
        if todo.modified and todo.modified.tzinfo is None:
            todo_issues.append("modified")
        if todo.due_date and todo.due_date.tzinfo is None:
            todo_issues.append("due_date")
        if todo.start_date and todo.start_date.tzinfo is None:
            todo_issues.append("start_date")
        if todo.completed_date and todo.completed_date.tzinfo is None:
            todo_issues.append("completed_date")
        
        if todo_issues:
            issue_desc = f"Todo {todo.id}: naive datetime in {', '.join(todo_issues)}"
            issues.append(issue_desc)
            if verbose:
                click.echo(f"    ⚠️  {issue_desc}")
    
    return issues


def _fix_project_datetimes(project: Project) -> bool:
    """Fix timezone issues in a project."""
    fixed = False
    
    if project.created and project.created.tzinfo is None:
        project.created = ensure_aware(project.created)
        fixed = True
    
    if project.modified and project.modified.tzinfo is None:
        project.modified = ensure_aware(project.modified)
        fixed = True
    
    if project.deadline and project.deadline.tzinfo is None:
        project.deadline = ensure_aware(project.deadline)
        fixed = True
    
    if project.sync_last_update and project.sync_last_update.tzinfo is None:
        project.sync_last_update = ensure_aware(project.sync_last_update)
        fixed = True
    
    return fixed


def _fix_todo_datetimes(todo: Todo) -> bool:
    """Fix timezone issues in a todo."""
    fixed = False
    
    if todo.created and todo.created.tzinfo is None:
        todo.created = ensure_aware(todo.created)
        fixed = True
    
    if todo.modified and todo.modified.tzinfo is None:
        todo.modified = ensure_aware(todo.modified)
        fixed = True
    
    if todo.due_date and todo.due_date.tzinfo is None:
        todo.due_date = ensure_aware(todo.due_date)
        fixed = True
    
    if todo.start_date and todo.start_date.tzinfo is None:
        todo.start_date = ensure_aware(todo.start_date)
        fixed = True
    
    if todo.completed_date and todo.completed_date.tzinfo is None:
        todo.completed_date = ensure_aware(todo.completed_date)
        fixed = True
    
    return fixed


if __name__ == '__main__':
    doctor()