"""
Export System for Todo CLI

This module provides comprehensive export functionality supporting multiple formats
including JSON, CSV, Markdown, iCal, and custom formats for integration and backup.
"""

import csv
import json
import os
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from io import StringIO
from typing import List, Dict, Any, Optional, Union
from enum import Enum

from ..domain import Todo, Priority, TodoStatus, Project


class ExportFormat(Enum):
    """Supported export formats"""
    JSON = "json"
    CSV = "csv"
    MARKDOWN = "markdown"
    TSV = "tsv"
    ICAL = "ical"  # iCalendar format
    XML = "xml"
    YAML = "yaml"
    HTML = "html"
    PDF = "pdf"


class BaseExporter(ABC):
    """Abstract base class for exporters"""
    
    @abstractmethod
    def export_todos(self, todos: List[Todo], **kwargs) -> str:
        """Export todos to string format"""
        pass
    
    @abstractmethod
    def export_projects(self, projects: List[Dict[str, Any]], **kwargs) -> str:
        """Export projects to string format"""
        pass
    
    @abstractmethod
    def get_file_extension(self) -> str:
        """Get recommended file extension"""
        pass


class JSONExporter(BaseExporter):
    """Export to JSON format"""
    
    def export_todos(self, todos: List[Todo], **kwargs) -> str:
        """Export todos to JSON"""
        include_completed = kwargs.get('include_completed', True)
        include_metadata = kwargs.get('include_metadata', True)
        
        todos_data = []
        for todo in todos:
            if not include_completed and todo.completed:
                continue
                
            todo_dict = {
                'id': todo.id,
                'text': todo.text,
                'completed': todo.completed,
                'project': todo.project,
                'priority': todo.priority.value if todo.priority else None,
                'status': todo.status.value if todo.status else None,
                'tags': todo.tags,
                'context': todo.context,
                'assignees': todo.assignees,
                'stakeholders': todo.stakeholders,
                'due_date': todo.due_date.isoformat() if todo.due_date else None,
                'created': todo.created.isoformat() if todo.created else None,
            }
            
            if include_metadata:
                todo_dict.update({
                    'description': todo.description,
                    'effort': todo.effort,
                    'energy_level': todo.energy_level,
                    'time_estimate': todo.time_estimate,
                    'time_spent': todo.time_spent,
                    'progress': todo.progress,
                    'pinned': todo.pinned,
                    'waiting_for': todo.waiting_for,
                    'url': todo.url,
                    'recurrence': todo.recurrence,
                    'parent_recurring_id': todo.parent_recurring_id,
                    'modified': todo.modified.isoformat() if todo.modified else None,
                    'completed_date': todo.completed_date.isoformat() if todo.completed_date else None,
                })
            
            todos_data.append(todo_dict)
        
        export_data = {
            'export_timestamp': datetime.now().isoformat(),
            'export_format': 'json',
            'todos_count': len(todos_data),
            'todos': todos_data
        }
        
        return json.dumps(export_data, indent=2, ensure_ascii=False)
    
    def export_projects(self, projects: List[Dict[str, Any]], **kwargs) -> str:
        """Export projects to JSON"""
        export_data = {
            'export_timestamp': datetime.now().isoformat(),
            'export_format': 'json',
            'projects_count': len(projects),
            'projects': projects
        }
        
        return json.dumps(export_data, indent=2, ensure_ascii=False)
    
    def get_file_extension(self) -> str:
        return "json"


class CSVExporter(BaseExporter):
    """Export to CSV format"""
    
    def export_todos(self, todos: List[Todo], **kwargs) -> str:
        """Export todos to CSV"""
        include_completed = kwargs.get('include_completed', True)
        include_metadata = kwargs.get('include_metadata', False)
        delimiter = kwargs.get('delimiter', ',')
        
        output = StringIO()
        
        # Define fields
        basic_fields = [
            'id', 'text', 'completed', 'project', 'priority', 'status',
            'tags', 'context', 'assignees', 'due_date', 'created'
        ]
        
        metadata_fields = [
            'description', 'effort', 'energy_level', 'time_estimate',
            'time_spent', 'progress', 'pinned', 'waiting_for', 'url'
        ]
        
        fields = basic_fields + (metadata_fields if include_metadata else [])
        
        writer = csv.DictWriter(output, fieldnames=fields, delimiter=delimiter)
        writer.writeheader()
        
        for todo in todos:
            if not include_completed and todo.completed:
                continue
            
            row = {
                'id': todo.id,
                'text': todo.text,
                'completed': todo.completed,
                'project': todo.project,
                'priority': todo.priority.value if todo.priority else '',
                'status': todo.status.value if todo.status else '',
                'tags': ';'.join(todo.tags),
                'context': ';'.join(todo.context),
                'assignees': ';'.join(todo.assignees),
                'due_date': todo.due_date.isoformat() if todo.due_date else '',
                'created': todo.created.isoformat() if todo.created else '',
            }
            
            if include_metadata:
                row.update({
                    'description': todo.description,
                    'effort': todo.effort,
                    'energy_level': todo.energy_level,
                    'time_estimate': todo.time_estimate or '',
                    'time_spent': todo.time_spent,
                    'progress': todo.progress,
                    'pinned': todo.pinned,
                    'waiting_for': ';'.join(todo.waiting_for) if todo.waiting_for else '',
                    'url': todo.url or '',
                })
            
            writer.writerow(row)
        
        return output.getvalue()
    
    def export_projects(self, projects: List[Dict[str, Any]], **kwargs) -> str:
        """Export projects to CSV"""
        output = StringIO()
        delimiter = kwargs.get('delimiter', ',')
        
        if not projects:
            return ""
        
        # Get all possible fields from projects
        all_fields = set()
        for project in projects:
            all_fields.update(project.keys())
        
        fields = sorted(all_fields)
        writer = csv.DictWriter(output, fieldnames=fields, delimiter=delimiter)
        writer.writeheader()
        
        for project in projects:
            # Flatten nested dictionaries
            row = {}
            for key, value in project.items():
                if isinstance(value, (list, dict)):
                    row[key] = json.dumps(value)
                else:
                    row[key] = value
            writer.writerow(row)
        
        return output.getvalue()
    
    def get_file_extension(self) -> str:
        return "csv"


class MarkdownExporter(BaseExporter):
    """Export to Markdown format"""
    
    def export_todos(self, todos: List[Todo], **kwargs) -> str:
        """Export todos to Markdown"""
        include_completed = kwargs.get('include_completed', True)
        group_by_project = kwargs.get('group_by_project', True)
        include_metadata = kwargs.get('include_metadata', True)
        
        output = []
        output.append(f"# Todo Export")
        output.append(f"*Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*")
        output.append("")
        
        # Filter todos
        filtered_todos = [t for t in todos if include_completed or not t.completed]
        
        if group_by_project:
            # Group by project
            projects = {}
            for todo in filtered_todos:
                project = todo.project or "Uncategorized"
                if project not in projects:
                    projects[project] = []
                projects[project].append(todo)
            
            for project_name, project_todos in sorted(projects.items()):
                output.append(f"## {project_name}")
                output.append("")
                
                for todo in sorted(project_todos, key=lambda t: (t.completed, t.id)):
                    checkbox = "☑️" if todo.completed else "☐"
                    priority_emoji = self._get_priority_emoji(todo.priority)
                    
                    line = f"- {checkbox} {priority_emoji} {todo.text}"
                    
                    if todo.due_date:
                        line += f" (due: {todo.due_date.strftime('%Y-%m-%d')})"
                    
                    if todo.tags:
                        line += f" #{' #'.join(todo.tags)}"
                    
                    output.append(line)
                    
                    if include_metadata and (todo.description or todo.assignees or todo.waiting_for):
                        if todo.description:
                            output.append(f"  > {todo.description}")
                        if todo.assignees:
                            output.append(f"  > Assigned to: {', '.join(todo.assignees)}")
                        if todo.waiting_for:
                            output.append(f"  > Waiting for: {', '.join(todo.waiting_for)}")
                
                output.append("")
        else:
            # Simple list
            output.append("## All Todos")
            output.append("")
            
            for todo in sorted(filtered_todos, key=lambda t: (t.completed, t.priority.value if t.priority else 'medium', t.id)):
                checkbox = "☑️" if todo.completed else "☐"
                priority_emoji = self._get_priority_emoji(todo.priority)
                
                line = f"- {checkbox} {priority_emoji} **{todo.text}**"
                
                if todo.project:
                    line += f" *({todo.project})*"
                
                if todo.due_date:
                    line += f" - Due: {todo.due_date.strftime('%Y-%m-%d')}"
                
                output.append(line)
        
        return "\n".join(output)
    
    def export_projects(self, projects: List[Dict[str, Any]], **kwargs) -> str:
        """Export projects to Markdown"""
        output = []
        output.append("# Projects Export")
        output.append(f"*Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*")
        output.append("")
        
        for project in projects:
            output.append(f"## {project.get('name', 'Unknown Project')}")
            
            if project.get('description'):
                output.append(f"{project['description']}")
                output.append("")
            
            # Stats
            if 'stats' in project:
                stats = project['stats']
                output.append("### Statistics")
                for key, value in stats.items():
                    output.append(f"- **{key.replace('_', ' ').title()}**: {value}")
                output.append("")
            
            # Team members
            if project.get('team_members'):
                output.append("### Team Members")
                for member in project['team_members']:
                    output.append(f"- {member}")
                output.append("")
        
        return "\n".join(output)
    
    def _get_priority_emoji(self, priority: Optional[Priority]) -> str:
        """Get emoji for priority"""
        if not priority:
            return "📋"
        
        priority_emojis = {
            Priority.CRITICAL: "🔥",
            Priority.HIGH: "❗",
            Priority.MEDIUM: "📋", 
            Priority.LOW: "📝"
        }
        
        return priority_emojis.get(priority, "📋")
    
    def get_file_extension(self) -> str:
        return "md"


class ICalExporter(BaseExporter):
    """Export to iCalendar format for calendar integration"""
    
    def export_todos(self, todos: List[Todo], **kwargs) -> str:
        """Export todos to iCal format"""
        include_completed = kwargs.get('include_completed', False)  # Usually don't include completed in calendar
        
        output = []
        output.append("BEGIN:VCALENDAR")
        output.append("VERSION:2.0")
        output.append("PRODID:-//Todo CLI//Todo Export//EN")
        output.append("CALSCALE:GREGORIAN")
        output.append("METHOD:PUBLISH")
        output.append("")
        
        for todo in todos:
            if not include_completed and todo.completed:
                continue
            
            if not todo.due_date:
                continue  # Skip todos without due dates for calendar export
            
            output.append("BEGIN:VTODO")
            output.append(f"UID:todo-{todo.id}@todoapp")
            output.append(f"DTSTAMP:{datetime.now().strftime('%Y%m%dT%H%M%SZ')}")
            output.append(f"CREATED:{todo.created.strftime('%Y%m%dT%H%M%SZ') if todo.created else datetime.now().strftime('%Y%m%dT%H%M%SZ')}")
            output.append(f"LAST-MODIFIED:{todo.modified.strftime('%Y%m%dT%H%M%SZ') if todo.modified else datetime.now().strftime('%Y%m%dT%H%M%SZ')}")
            output.append(f"SUMMARY:{todo.text}")
            
            if todo.description:
                newline_replacement = '\\n'
                output.append(f"DESCRIPTION:{todo.description.replace(chr(10), newline_replacement)}")
            
            output.append(f"DUE:{todo.due_date.strftime('%Y%m%dT%H%M%SZ')}")
            
            # Priority mapping (iCal uses 1-9, where 1 is highest)
            priority_map = {
                Priority.CRITICAL: "1",
                Priority.HIGH: "3", 
                Priority.MEDIUM: "5",
                Priority.LOW: "7"
            }
            if todo.priority:
                output.append(f"PRIORITY:{priority_map.get(todo.priority, '5')}")
            
            # Status mapping
            if todo.completed:
                output.append("STATUS:COMPLETED")
                if todo.completed_date:
                    output.append(f"COMPLETED:{todo.completed_date.strftime('%Y%m%dT%H%M%SZ')}")
                output.append("PERCENT-COMPLETE:100")
            elif todo.status == TodoStatus.IN_PROGRESS:
                output.append("STATUS:IN-PROCESS")
                output.append(f"PERCENT-COMPLETE:{int(todo.progress * 100)}")
            else:
                output.append("STATUS:NEEDS-ACTION")
            
            # Categories (tags)
            if todo.tags:
                output.append(f"CATEGORIES:{','.join(todo.tags)}")
            
            output.append("END:VTODO")
            output.append("")
        
        output.append("END:VCALENDAR")
        return "\n".join(output)
    
    def export_projects(self, projects: List[Dict[str, Any]], **kwargs) -> str:
        """Export projects as iCal events (project milestones, etc.)"""
        # For now, just return empty calendar as projects don't map well to iCal
        output = []
        output.append("BEGIN:VCALENDAR")
        output.append("VERSION:2.0")
        output.append("PRODID:-//Todo CLI//Project Export//EN")
        output.append("CALSCALE:GREGORIAN")
        output.append("METHOD:PUBLISH")
        output.append("END:VCALENDAR")
        return "\n".join(output)
    
    def get_file_extension(self) -> str:
        return "ics"


class YAMLExporter(BaseExporter):
    """Export to YAML format"""
    
    def export_todos(self, todos: List[Todo], **kwargs) -> str:
        """Export todos to YAML"""
        import yaml
        
        include_completed = kwargs.get('include_completed', True)
        include_metadata = kwargs.get('include_metadata', True)
        
        todos_data = []
        for todo in todos:
            if not include_completed and todo.completed:
                continue
                
            todo_dict = {
                'id': todo.id,
                'text': todo.text,
                'completed': todo.completed,
                'project': todo.project,
                'priority': todo.priority.value if todo.priority else None,
                'status': todo.status.value if todo.status else None,
                'tags': todo.tags,
                'context': todo.context,
                'assignees': todo.assignees,
                'stakeholders': todo.stakeholders,
                'due_date': todo.due_date.isoformat() if todo.due_date else None,
                'created': todo.created.isoformat() if todo.created else None,
            }
            
            if include_metadata:
                todo_dict.update({
                    'description': todo.description,
                    'effort': todo.effort,
                    'energy_level': todo.energy_level,
                    'time_estimate': todo.time_estimate,
                    'time_spent': todo.time_spent,
                    'progress': todo.progress,
                    'pinned': todo.pinned,
                    'waiting_for': todo.waiting_for,
                    'url': todo.url,
                })
            
            todos_data.append(todo_dict)
        
        export_data = {
            'export_timestamp': datetime.now().isoformat(),
            'export_format': 'yaml',
            'todos_count': len(todos_data),
            'todos': todos_data
        }
        
        return yaml.dump(export_data, default_flow_style=False, allow_unicode=True)
    
    def export_projects(self, projects: List[Dict[str, Any]], **kwargs) -> str:
        """Export projects to YAML"""
        import yaml
        
        export_data = {
            'export_timestamp': datetime.now().isoformat(),
            'export_format': 'yaml',
            'projects_count': len(projects),
            'projects': projects
        }
        
        return yaml.dump(export_data, default_flow_style=False, allow_unicode=True)
    
    def get_file_extension(self) -> str:
        return "yaml"


class HTMLExporter(BaseExporter):
    """Export to HTML format"""
    
    def export_todos(self, todos: List[Todo], **kwargs) -> str:
        """Export todos to HTML"""
        include_completed = kwargs.get('include_completed', True)
        project_name = kwargs.get('project_name', 'Todo Export')
        
        # Filter todos if needed
        filtered_todos = todos if include_completed else [t for t in todos if not t.completed]
        
        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{project_name} - Todo Export</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            line-height: 1.6;
            max-width: 1200px;
            margin: 0 auto;
            padding: 2rem;
            color: #333;
        }}
        
        .header {{
            border-bottom: 2px solid #eee;
            margin-bottom: 2rem;
            padding-bottom: 1rem;
        }}
        
        .export-info {{
            color: #666;
            font-size: 0.9em;
            margin-bottom: 1rem;
        }}
        
        .summary {{
            background: #f8f9fa;
            padding: 1rem;
            border-radius: 8px;
            margin-bottom: 2rem;
        }}
        
        .summary-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 1rem;
        }}
        
        .stat {{
            text-align: center;
        }}
        
        .stat-number {{
            font-size: 2em;
            font-weight: bold;
            color: #2563eb;
        }}
        
        .stat-label {{
            font-size: 0.9em;
            color: #666;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}
        
        .status-section {{
            margin-bottom: 3rem;
        }}
        
        .status-header {{
            display: flex;
            align-items: center;
            margin-bottom: 1rem;
            font-size: 1.5em;
            font-weight: bold;
        }}
        
        .task {{
            background: white;
            border: 1px solid #e5e7eb;
            border-radius: 8px;
            padding: 1rem;
            margin-bottom: 0.5rem;
            transition: box-shadow 0.2s;
        }}
        
        .task:hover {{
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }}
        
        .task.completed {{
            background: #f0fdf4;
            border-color: #bbf7d0;
        }}
        
        .task.pinned {{
            border-left: 4px solid #f59e0b;
        }}
        
        .task.overdue {{
            border-left: 4px solid #ef4444;
        }}
        
        .task-title {{
            font-weight: 600;
            margin-bottom: 0.5rem;
        }}
        
        .task-title.completed {{
            text-decoration: line-through;
            color: #6b7280;
        }}
        
        .task-meta {{
            display: flex;
            flex-wrap: wrap;
            gap: 1rem;
            font-size: 0.9em;
            color: #6b7280;
        }}
        
        .badge {{
            display: inline-block;
            padding: 0.2rem 0.5rem;
            border-radius: 4px;
            font-size: 0.8em;
            font-weight: 500;
        }}
        
        .priority-critical {{ background: #fee2e2; color: #dc2626; }}
        .priority-high {{ background: #fef3c7; color: #d97706; }}
        .priority-medium {{ background: #f3f4f6; color: #374151; }}
        .priority-low {{ background: #f0f9ff; color: #0369a1; }}
        
        .tag {{ background: #dbeafe; color: #1d4ed8; }}
        .context {{ background: #ecfdf5; color: #059669; }}
        .assignee {{ background: #fdf4ff; color: #a21caf; }}
        
        .notes {{
            margin-top: 0.5rem;
            padding: 0.5rem;
            background: #f9fafb;
            border-radius: 4px;
            font-style: italic;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>{project_name}</h1>
        <div class="export-info">
            Exported on {datetime.now().strftime('%B %d, %Y at %H:%M')}
        </div>
    </div>
"""
        
        # Summary stats
        total = len(filtered_todos)
        completed = sum(1 for t in filtered_todos if t.completed)
        pending = total - completed
        pinned = sum(1 for t in filtered_todos if t.pinned)
        overdue = sum(1 for t in filtered_todos if t.is_overdue() and not t.completed)
        
        html += f"""
    <div class="summary">
        <h2>Summary</h2>
        <div class="summary-grid">
            <div class="stat">
                <div class="stat-number">{total}</div>
                <div class="stat-label">Total</div>
            </div>
            <div class="stat">
                <div class="stat-number">{completed}</div>
                <div class="stat-label">Completed</div>
            </div>
            <div class="stat">
                <div class="stat-number">{pending}</div>
                <div class="stat-label">Pending</div>
            </div>
            <div class="stat">
                <div class="stat-number">{pinned}</div>
                <div class="stat-label">Pinned</div>
            </div>
            <div class="stat">
                <div class="stat-number">{overdue}</div>
                <div class="stat-label">Overdue</div>
            </div>
        </div>
    </div>
"""
        
        # Group by status
        status_groups = {}
        for todo in filtered_todos:
            status = todo.status.value
            if status not in status_groups:
                status_groups[status] = []
            status_groups[status].append(todo)
        
        status_icons = {
            'pending': '⏳',
            'in_progress': '🔄',
            'completed': '✅',
            'blocked': '🚫',
            'cancelled': '❌'
        }
        
        status_titles = {
            'pending': 'Pending Tasks',
            'in_progress': 'In Progress',
            'completed': 'Completed Tasks',
            'blocked': 'Blocked Tasks',
            'cancelled': 'Cancelled Tasks'
        }
        
        for status in ['pending', 'in_progress', 'completed', 'blocked', 'cancelled']:
            if status in status_groups:
                todos_in_status = status_groups[status]
                icon = status_icons.get(status, '📋')
                title = status_titles.get(status, status.title())
                
                html += f"""
    <div class="status-section">
        <div class="status-header">
            {icon} {title} ({len(todos_in_status)})
        </div>
"""
                
                for todo in todos_in_status:
                    task_classes = ['task']
                    if todo.completed:
                        task_classes.append('completed')
                    if todo.pinned:
                        task_classes.append('pinned')
                    if todo.is_overdue() and not todo.completed:
                        task_classes.append('overdue')
                    
                    title_classes = ['task-title']
                    if todo.completed:
                        title_classes.append('completed')
                    
                    html += f"""
        <div class="{' '.join(task_classes)}">
            <div class="{' '.join(title_classes)}">
                {todo.text}
                {'⭐' if todo.pinned else ''}
            </div>
            <div class="task-meta">
"""
                    
                    # Priority
                    if todo.priority.value != 'medium':
                        html += f'<span class="badge priority-{todo.priority.value}">~{todo.priority.value}</span>'
                    
                    # Tags
                    if todo.tags:
                        for tag in todo.tags:
                            html += f'<span class="badge tag">@{tag}</span>'
                    
                    # Context
                    if todo.context:
                        for ctx in todo.context:
                            html += f'<span class="badge context">@{ctx}</span>'
                    
                    # Assignees
                    if todo.assignees:
                        for assignee in todo.assignees:
                            html += f'<span class="badge assignee">+{assignee}</span>'
                    
                    # Due date
                    if todo.due_date:
                        due_str = todo.due_date.strftime('%Y-%m-%d')
                        if todo.is_overdue() and not todo.completed:
                            html += f'<span style="color: #dc2626; font-weight: bold;">Due: {due_str} ⚠️</span>'
                        else:
                            html += f'<span>Due: {due_str}</span>'
                    
                    # Effort and energy
                    if todo.effort:
                        html += f'<span>Effort: *{todo.effort}</span>'
                    if todo.energy_level and todo.energy_level != 'medium':
                        html += f'<span>Energy: {todo.energy_level}</span>'
                    
                    # Time estimate
                    if todo.time_estimate:
                        hours = todo.time_estimate // 60
                        minutes = todo.time_estimate % 60
                        if hours > 0:
                            html += f'<span>Est: {hours}h {minutes}m</span>'
                        else:
                            html += f'<span>Est: {minutes}m</span>'
                    
                    html += """
            </div>
"""
                    
                    if todo.description or todo.notes:
                        note_text = todo.description or (todo.notes[0] if todo.notes else '')
                        html += f"""
            <div class="notes">{note_text}</div>
"""
                    
                    html += """
        </div>
"""
                
                html += """
    </div>
"""
        
        html += """
</body>
</html>"""
        
        return html
    
    def export_projects(self, projects: List[Dict[str, Any]], **kwargs) -> str:
        """Export projects to HTML"""
        # Simplified project export
        html = """<!DOCTYPE html>
<html>
<head><title>Projects Export</title></head>
<body>
<h1>Projects Export</h1>"""
        
        for project in projects:
            html += f"<h2>{project.get('name', 'Unknown')}</h2>"
            if project.get('description'):
                html += f"<p>{project['description']}</p>"
        
        html += "</body></html>"
        return html
    
    def get_file_extension(self) -> str:
        return "html"


class PDFExporter(BaseExporter):
    """Export to PDF format using lightweight text-based generation"""
    
    def export_todos(self, todos: List[Todo], **kwargs) -> str:
        """Export todos to PDF using simple generation (no heavy dependencies)"""
        from .simple_pdf import TextPDFExporter
        
        pdf_exporter = TextPDFExporter()
        return pdf_exporter.export_todos(todos, **kwargs)
    
    def export_projects(self, projects: List[Dict[str, Any]], **kwargs) -> str:
        """Export projects to PDF using simple generation"""
        from .simple_pdf import TextPDFExporter
        
        pdf_exporter = TextPDFExporter()
        return pdf_exporter.export_projects(projects, **kwargs)
    
    def get_file_extension(self) -> str:
        return "pdf"


class ExportManager:
    """Manages different export formats and operations"""
    
    def __init__(self):
        self.exporters = {
            ExportFormat.JSON: JSONExporter(),
            ExportFormat.CSV: CSVExporter(),
            ExportFormat.TSV: CSVExporter(),  # TSV is CSV with tab delimiter
            ExportFormat.MARKDOWN: MarkdownExporter(),
            ExportFormat.ICAL: ICalExporter(),
            ExportFormat.YAML: YAMLExporter(),
            ExportFormat.HTML: HTMLExporter(),
            ExportFormat.PDF: PDFExporter(),
        }
    
    def export_todos(
        self, 
        todos: List[Todo], 
        format: ExportFormat, 
        output_path: Optional[str] = None,
        **kwargs
    ) -> str:
        """Export todos in specified format"""
        if format not in self.exporters:
            raise ValueError(f"Export format {format.value} not supported")
        
        exporter = self.exporters[format]
        
        # Handle TSV special case
        if format == ExportFormat.TSV:
            kwargs['delimiter'] = '\t'
        
        content = exporter.export_todos(todos, **kwargs)
        
        # Handle text fallback for PDF export
        if format == ExportFormat.PDF and content.startswith("TEXT_FALLBACK:"):
            # Remove the prefix and handle as text
            content = content[14:]  # Remove "TEXT_FALLBACK:" prefix
            if output_path:
                # Change extension to .txt for text fallback
                import os
                base_path = os.path.splitext(output_path)[0]
                text_output_path = base_path + ".txt"
                self._write_to_file(content, text_output_path)
                # Update output_path for return message
                # Note: This might need to be handled by the caller
            return content
        
        if output_path:
            if format == ExportFormat.PDF:
                self._write_pdf_to_file(content, output_path)
            else:
                self._write_to_file(content, output_path)
        
        return content
    
    def export_projects(
        self, 
        projects: List[Dict[str, Any]], 
        format: ExportFormat,
        output_path: Optional[str] = None, 
        **kwargs
    ) -> str:
        """Export projects in specified format"""
        if format not in self.exporters:
            raise ValueError(f"Export format {format.value} not supported")
        
        exporter = self.exporters[format]
        
        # Handle TSV special case
        if format == ExportFormat.TSV:
            kwargs['delimiter'] = '\t'
        
        content = exporter.export_projects(projects, **kwargs)
        
        if output_path:
            if format == ExportFormat.PDF:
                self._write_pdf_to_file(content, output_path)
            else:
                self._write_to_file(content, output_path)
        
        return content
    
    def get_supported_formats(self) -> List[str]:
        """Get list of supported format names"""
        return [fmt.value for fmt in self.exporters.keys()]
    
    def get_file_extension(self, format: ExportFormat) -> str:
        """Get recommended file extension for format"""
        if format not in self.exporters:
            return "txt"
        return self.exporters[format].get_file_extension()
    
    def _write_to_file(self, content: str, file_path: str):
        """Write content to file"""
        dir_path = os.path.dirname(file_path)
        if dir_path:  # Only create directory if there is one
            os.makedirs(dir_path, exist_ok=True)
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
    
    def _write_pdf_to_file(self, base64_content: str, file_path: str):
        """Write base64 PDF content to file"""
        import base64
        dir_path = os.path.dirname(file_path)
        if dir_path:  # Only create directory if there is one
            os.makedirs(dir_path, exist_ok=True)
        pdf_bytes = base64.b64decode(base64_content)
        with open(file_path, 'wb') as f:
            f.write(pdf_bytes)


def create_backup_export(
    todos: List[Todo], 
    projects: List[Dict[str, Any]], 
    backup_dir: str
) -> Dict[str, str]:
    """Create comprehensive backup in multiple formats"""
    manager = ExportManager()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    backup_files = {}
    
    # Export todos in JSON (most complete format)
    todos_json_path = os.path.join(backup_dir, f"todos_backup_{timestamp}.json")
    manager.export_todos(todos, ExportFormat.JSON, todos_json_path, include_metadata=True)
    backup_files['todos_json'] = todos_json_path
    
    # Export todos in CSV (for spreadsheet compatibility)
    todos_csv_path = os.path.join(backup_dir, f"todos_backup_{timestamp}.csv")
    manager.export_todos(todos, ExportFormat.CSV, todos_csv_path, include_metadata=True)
    backup_files['todos_csv'] = todos_csv_path
    
    # Export projects
    projects_json_path = os.path.join(backup_dir, f"projects_backup_{timestamp}.json")
    manager.export_projects(projects, ExportFormat.JSON, projects_json_path)
    backup_files['projects_json'] = projects_json_path
    
    return backup_files