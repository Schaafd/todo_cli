"""
Simple PDF generator for Todo CLI without heavy external dependencies.

This module provides a lightweight PDF generation approach that doesn't
rely on complex external libraries like weasyprint.
"""

import io
import datetime
from typing import List, Dict, Any, Optional
from ..domain import Todo, Priority, TodoStatus


def sanitize_text_for_pdf(text: str) -> str:
    """
    Sanitize text for PDF generation by replacing problematic Unicode characters
    with latin-1 compatible alternatives.
    """
    # Common Unicode character replacements for latin-1 compatibility
    replacements = {
        '\u2019': "'",  # Right single quotation mark
        '\u2018': "'",  # Left single quotation mark
        '\u201c': '"',  # Left double quotation mark
        '\u201d': '"',  # Right double quotation mark
        '\u2013': '-',  # En dash
        '\u2014': '-',  # Em dash
        '\u2026': '...',  # Horizontal ellipsis
        '\u2022': '*',  # Bullet
        '\u00a0': ' ',  # Non-breaking space
    }
    
    # Apply replacements
    for unicode_char, replacement in replacements.items():
        text = text.replace(unicode_char, replacement)
    
    # As a fallback, encode to latin-1 and decode back, replacing errors
    try:
        text.encode('latin-1')
        return text
    except UnicodeEncodeError:
        return text.encode('latin-1', errors='replace').decode('latin-1')


class SimplePDFGenerator:
    """
    A simple PDF generator that creates basic PDF documents without
    heavy dependencies. Uses pure Python with minimal external requirements.
    """
    
    def __init__(self):
        self.page_width = 595  # A4 width in points
        self.page_height = 842  # A4 height in points  
        self.margin = 50
        self.line_height = 14
        
    def generate_todos_pdf(self, todos: List[Todo], **kwargs) -> bytes:
        """Generate a PDF report for todos using a simple approach"""
        include_completed = kwargs.get('include_completed', True)
        project_name = kwargs.get('project_name', 'Todo Export')
        
        # Filter todos if needed
        filtered_todos = todos if include_completed else [t for t in todos if not t.completed]
        
        # Try fpdf2 first (lightweight PDF library)
        try:
            return self._generate_with_fpdf(filtered_todos, project_name, kwargs)
        except ImportError:
            # Fall back to pure text export as "pseudo-PDF"
            return self._generate_text_as_pdf(filtered_todos, project_name, kwargs)
    
    def _generate_with_fpdf(self, todos: List[Todo], title: str, kwargs: Dict) -> bytes:
        """Generate PDF using fpdf2 library (lightweight, pure Python)"""
        try:
            from fpdf import FPDF
        except ImportError:
            raise ImportError(
                "For PDF export with fpdf2, install with: pip install fpdf2\n"
                "This is much lighter than weasyprint and has no system dependencies."
            )
        
        pdf = FPDF()
        pdf.add_page()
        
        # Title
        pdf.set_font('Arial', 'B', 16)
        pdf.cell(0, 10, sanitize_text_for_pdf(title), 0, 1, 'C')
        pdf.ln(5)
        
        # Export info
        pdf.set_font('Arial', '', 10)
        export_time = datetime.datetime.now().strftime('%B %d, %Y at %H:%M')
        pdf.cell(0, 10, sanitize_text_for_pdf(f'Generated on {export_time}'), 0, 1, 'C')
        pdf.ln(10)
        
        # Summary stats
        total = len(todos)
        completed = sum(1 for t in todos if t.completed)
        pending = total - completed
        overdue = sum(1 for t in todos if t.is_overdue() and not t.completed)
        
        pdf.set_font('Arial', 'B', 12)
        pdf.cell(0, 10, 'Summary', 0, 1)
        pdf.set_font('Arial', '', 10)
        
        stats_text = f'Total: {total}  |  Completed: {completed}  |  Pending: {pending}  |  Overdue: {overdue}'
        pdf.cell(0, 10, sanitize_text_for_pdf(stats_text), 0, 1)
        pdf.ln(5)
        
        # Group by status
        status_groups = {}
        for todo in todos:
            status = todo.status.value
            if status not in status_groups:
                status_groups[status] = []
            status_groups[status].append(todo)
        
        status_titles = {
            'pending': 'Pending Tasks',
            'in_progress': 'In Progress',
            'completed': 'Completed Tasks',
            'blocked': 'Blocked Tasks',
            'cancelled': 'Cancelled Tasks'
        }
        
        # Export each status group
        for status in ['pending', 'in_progress', 'completed', 'blocked', 'cancelled']:
            if status in status_groups:
                todos_in_status = status_groups[status]
                
                # Status header
                pdf.set_font('Arial', 'B', 14)
                title = status_titles.get(status, status.title())
                pdf.cell(0, 10, sanitize_text_for_pdf(f'{title} ({len(todos_in_status)})'), 0, 1)
                pdf.ln(2)
                
                # Tasks in this status
                pdf.set_font('Arial', '', 9)
                
                for todo in todos_in_status:
                    # Check for page break
                    if pdf.get_y() > self.page_height - 50:
                        pdf.add_page()
                    
                    # Todo text
                    checkbox = '[X]' if todo.completed else '[ ]'
                    priority_str = f'({todo.priority.value.upper()})' if todo.priority.value != 'medium' else ''
                    
                    main_text = f'{checkbox} {priority_str} {todo.text}'.strip()
                    
                    # Handle long text by wrapping
                    if len(main_text) > 80:
                        main_text = main_text[:77] + '...'
                    
                    pdf.cell(0, 6, sanitize_text_for_pdf(main_text), 0, 1)
                    
                    # Additional info on next line (smaller)
                    info_parts = []
                    
                    if todo.project:
                        info_parts.append(f'Project: {todo.project}')
                    
                    if todo.due_date:
                        due_str = todo.due_date.strftime('%Y-%m-%d')
                        if todo.is_overdue() and not todo.completed:
                            info_parts.append(f'Due: {due_str} (OVERDUE)')
                        else:
                            info_parts.append(f'Due: {due_str}')
                    
                    if todo.tags:
                        info_parts.append(f'Tags: {", ".join(todo.tags)}')
                    
                    if todo.assignees:
                        info_parts.append(f'Assigned: {", ".join(todo.assignees)}')
                    
                    if info_parts:
                        pdf.set_font('Arial', '', 8)
                        info_text = ' | '.join(info_parts)
                        if len(info_text) > 100:
                            info_text = info_text[:97] + '...'
                        pdf.cell(10, 4, '', 0, 0)  # indent
                        pdf.cell(0, 4, sanitize_text_for_pdf(info_text), 0, 1)
                        pdf.set_font('Arial', '', 9)
                    
                    pdf.ln(2)
                
                pdf.ln(5)
        
        # Return PDF as bytes
        pdf_output = pdf.output(dest='S')
        if isinstance(pdf_output, str):
            return pdf_output.encode('latin1')
        else:
            return pdf_output
    
    def _generate_text_as_pdf(self, todos: List[Todo], title: str, kwargs: Dict) -> bytes:
        """
        Fallback: Generate a structured text report that can be saved as .txt
        but return it as bytes for consistency with PDF interface
        """
        lines = []
        lines.append(f"{title}")
        lines.append("=" * len(title))
        lines.append("")
        
        export_time = datetime.datetime.now().strftime('%B %d, %Y at %H:%M')
        lines.append(f"Generated on {export_time}")
        lines.append("")
        
        # Summary
        total = len(todos)
        completed = sum(1 for t in todos if t.completed)
        pending = total - completed
        overdue = sum(1 for t in todos if t.is_overdue() and not t.completed)
        
        lines.append("SUMMARY")
        lines.append("-------")
        lines.append(f"Total Tasks: {total}")
        lines.append(f"Completed: {completed}")
        lines.append(f"Pending: {pending}")
        lines.append(f"Overdue: {overdue}")
        lines.append("")
        
        # Group by status
        status_groups = {}
        for todo in todos:
            status = todo.status.value
            if status not in status_groups:
                status_groups[status] = []
            status_groups[status].append(todo)
        
        status_titles = {
            'pending': 'PENDING TASKS',
            'in_progress': 'IN PROGRESS',
            'completed': 'COMPLETED TASKS',
            'blocked': 'BLOCKED TASKS',
            'cancelled': 'CANCELLED TASKS'
        }
        
        for status in ['pending', 'in_progress', 'completed', 'blocked', 'cancelled']:
            if status in status_groups:
                todos_in_status = status_groups[status]
                
                title = status_titles.get(status, status.upper())
                lines.append(f"{title} ({len(todos_in_status)})")
                lines.append("-" * (len(title) + len(str(len(todos_in_status))) + 3))
                
                for todo in todos_in_status:
                    checkbox = "[X]" if todo.completed else "[ ]"
                    priority_str = f"({todo.priority.value.upper()})" if todo.priority.value != 'medium' else ""
                    
                    main_line = f"{checkbox} {priority_str} {todo.text}".strip()
                    lines.append(main_line)
                    
                    # Additional details indented
                    if todo.project:
                        lines.append(f"    Project: {todo.project}")
                    
                    if todo.due_date:
                        due_str = todo.due_date.strftime('%Y-%m-%d')
                        if todo.is_overdue() and not todo.completed:
                            lines.append(f"    Due: {due_str} (OVERDUE!)")
                        else:
                            lines.append(f"    Due: {due_str}")
                    
                    if todo.tags:
                        lines.append(f"    Tags: {', '.join(todo.tags)}")
                    
                    if todo.assignees:
                        lines.append(f"    Assigned to: {', '.join(todo.assignees)}")
                    
                    if todo.description:
                        # Wrap long descriptions
                        desc = todo.description
                        if len(desc) > 70:
                            desc = desc[:67] + "..."
                        lines.append(f"    Note: {desc}")
                    
                    lines.append("")  # blank line between todos
                
                lines.append("")  # blank line between sections
        
        # Footer
        lines.append("")
        lines.append("=" * 60)
        lines.append(f"Generated by Todo CLI - {export_time}")
        
        # Convert to bytes
        text_content = "\n".join(lines)
        return text_content.encode('utf-8')


class TextPDFExporter:
    """
    A simple PDF exporter that uses text-based generation instead of HTML conversion.
    This eliminates the need for weasyprint and other heavy dependencies.
    """
    
    def export_todos(self, todos: List[Todo], **kwargs) -> str:
        """Export todos to PDF using simple text-based generation"""
        generator = SimplePDFGenerator()
        
        try:
            pdf_bytes = generator.generate_todos_pdf(todos, **kwargs)
            
            # Check if we got actual PDF bytes or text fallback
            try:
                # Try to decode as text first (this means it's the fallback)
                text_content = pdf_bytes.decode('utf-8')
                # It's text fallback - we'll return it as a text report with a warning
                # The CLI can handle this by changing the file extension
                return f"TEXT_FALLBACK:{text_content}"
            except UnicodeDecodeError:
                # It's actual PDF bytes from fpdf2, encode as base64
                import base64
                return base64.b64encode(pdf_bytes).decode('utf-8')
                
        except ImportError as e:
            if "fpdf2" in str(e):
                # Try text fallback instead of failing completely
                pdf_bytes = generator._generate_text_as_pdf(todos, kwargs.get('project_name', 'Todo Export'), kwargs)
                text_content = pdf_bytes.decode('utf-8')
                return f"TEXT_FALLBACK:{text_content}"
            else:
                raise e
    
    def export_projects(self, projects: List[Dict[str, Any]], **kwargs) -> str:
        """Export projects - simplified implementation"""
        # For now, just create a simple text report
        lines = ["Projects Report", "===============", ""]
        
        for project in projects:
            lines.append(f"Project: {project.get('name', 'Unnamed')}")
            if project.get('description'):
                lines.append(f"Description: {project['description']}")
            if 'stats' in project:
                stats = project['stats']
                lines.append(f"Statistics:")
                for key, value in stats.items():
                    lines.append(f"  - {key.replace('_', ' ').title()}: {value}")
            lines.append("")
        
        text_content = "\n".join(lines)
        return text_content.encode('utf-8')
    
    def get_file_extension(self) -> str:
        return "pdf"