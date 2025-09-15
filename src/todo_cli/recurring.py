"""
Recurring Task System for Todo CLI

This module provides comprehensive recurring task functionality with smart scheduling,
automatic task generation, and flexible recurrence patterns.
"""

import os
import re
import yaml
from dataclasses import dataclass, field
from datetime import datetime, date, timedelta
from enum import Enum
from typing import List, Optional, Dict, Any, Tuple, Union
from calendar import monthrange
import math

from .todo import Todo, Priority, TodoStatus


class RecurrenceType(Enum):
    """Types of recurrence patterns"""
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    YEARLY = "yearly"
    CUSTOM = "custom"  # For complex patterns


@dataclass
class RecurrencePattern:
    """Defines a recurrence pattern for tasks"""
    type: RecurrenceType
    interval: int = 1  # Every N days/weeks/months/years
    days_of_week: List[int] = field(default_factory=list)  # 0=Monday, 6=Sunday
    days_of_month: List[int] = field(default_factory=list)  # 1-31
    months: List[int] = field(default_factory=list)  # 1-12
    end_date: Optional[datetime] = None  # When to stop recurring
    max_occurrences: Optional[int] = None  # Max number of occurrences
    
    # Advanced options
    skip_weekends: bool = False
    skip_holidays: bool = False
    business_days_only: bool = False
    
    def __post_init__(self):
        """Validate pattern after creation"""
        if self.type == RecurrenceType.WEEKLY and not self.days_of_week:
            # Default to same day of week if not specified
            self.days_of_week = [datetime.now().weekday()]
        
        if self.type == RecurrenceType.MONTHLY and not self.days_of_month:
            # Default to same day of month if not specified
            self.days_of_month = [datetime.now().day]


@dataclass
class RecurringTask:
    """A recurring task template that generates actual todos"""
    id: str  # Unique identifier for the recurring task
    template: Todo  # Template todo (without ID, serves as blueprint)
    pattern: RecurrencePattern
    created_at: datetime = field(default_factory=datetime.now)
    last_generated: Optional[datetime] = None
    next_due: Optional[datetime] = None
    occurrence_count: int = 0
    active: bool = True
    
    def __post_init__(self):
        """Initialize next_due if not set"""
        if not self.next_due:
            # This will be set by the RecurringTaskManager when created
            pass


class RecurrenceParser:
    """Parses natural language recurrence patterns"""
    
    PATTERNS = {
        # Simple patterns
        r'^daily$': (RecurrenceType.DAILY, {'interval': 1}),
        r'^every day$': (RecurrenceType.DAILY, {'interval': 1}),
        r'^every (\d+) days?$': (RecurrenceType.DAILY, lambda m: {'interval': int(m.group(1))}),
        
        # Weekly patterns
        r'^weekly$': (RecurrenceType.WEEKLY, {'interval': 1}),
        r'^every week$': (RecurrenceType.WEEKLY, {'interval': 1}),
        r'^every (\d+) weeks?$': (RecurrenceType.WEEKLY, lambda m: {'interval': int(m.group(1))}),
        
        # Day-specific patterns
        r'^every (monday|tuesday|wednesday|thursday|friday|saturday|sunday)$': 
            (RecurrenceType.WEEKLY, lambda m: {'days_of_week': [RecurrenceParser.day_name_to_number(m.group(1))]}),
        
        r'^weekdays$': (RecurrenceType.WEEKLY, {'days_of_week': [0, 1, 2, 3, 4], 'business_days_only': True}),
        r'^weekends$': (RecurrenceType.WEEKLY, {'days_of_week': [5, 6]}),
        
        # Monthly patterns
        r'^monthly$': (RecurrenceType.MONTHLY, {'interval': 1}),
        r'^every month$': (RecurrenceType.MONTHLY, {'interval': 1}),
        r'^every (\d+) months?$': (RecurrenceType.MONTHLY, lambda m: {'interval': int(m.group(1))}),
        r'^monthly on the (\d+)(?:st|nd|rd|th)?$': 
            (RecurrenceType.MONTHLY, lambda m: {'days_of_month': [int(m.group(1))]}),
        
        # Yearly patterns
        r'^yearly$': (RecurrenceType.YEARLY, {'interval': 1}),
        r'^annually$': (RecurrenceType.YEARLY, {'interval': 1}),
        r'^every year$': (RecurrenceType.YEARLY, {'interval': 1}),
        r'^every (\d+) years?$': (RecurrenceType.YEARLY, lambda m: {'interval': int(m.group(1))}),
    }
    
    @staticmethod
    def day_name_to_number(day_name: str) -> int:
        """Convert day name to number (0=Monday)"""
        days = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
        return days.index(day_name.lower())
    
    @classmethod
    def parse(cls, pattern_str: str) -> Optional[RecurrencePattern]:
        """Parse a natural language recurrence pattern"""
        pattern_str = pattern_str.lower().strip()
        
        for regex, (rec_type, params) in cls.PATTERNS.items():
            match = re.match(regex, pattern_str)
            if match:
                if callable(params):
                    params = params(match)
                
                return RecurrencePattern(type=rec_type, **params)
        
        # Try to parse more complex patterns
        return cls._parse_complex_pattern(pattern_str)
    
    @classmethod
    def _parse_complex_pattern(cls, pattern_str: str) -> Optional[RecurrencePattern]:
        """Parse more complex recurrence patterns"""
        # Handle patterns like "every 2nd and 4th monday"
        if "and" in pattern_str and ("monday" in pattern_str or "tuesday" in pattern_str):
            # Complex weekly pattern - for now return None, could be expanded
            return None
        
        # Handle monthly patterns like "first monday of every month"
        if "first" in pattern_str or "last" in pattern_str:
            # Complex monthly pattern - for now return None, could be expanded
            return None
        
        return None


class RecurringTaskManager:
    """Manages recurring tasks and generates actual todos"""
    
    def __init__(self, config_dir: Optional[str] = None):
        self.recurring_tasks: Dict[str, RecurringTask] = {}
        self.holidays: List[date] = []  # Could be loaded from config or API
        self.config_dir = config_dir or os.path.expanduser("~/.todo")
        self.recurring_file = os.path.join(self.config_dir, "recurring_tasks.yaml")
        self._load_recurring_tasks()
    
    def create_recurring_task(
        self, 
        template: Todo, 
        pattern: RecurrencePattern,
        task_id: Optional[str] = None
    ) -> RecurringTask:
        """Create a new recurring task"""
        if not task_id:
            task_id = f"recurring_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # Ensure template is marked as recurring template
        template.recurring_template = True
        template.recurrence = self._pattern_to_string(pattern)
        
        recurring_task = RecurringTask(
            id=task_id,
            template=template,
            pattern=pattern
        )
        
        # Set initial next_due date
        if not recurring_task.next_due:
            recurring_task.next_due = self.calculate_next_occurrence(
                recurring_task.created_at, recurring_task.pattern
            )
        
        self.recurring_tasks[task_id] = recurring_task
        self._save_recurring_tasks()
        return recurring_task
    
    def generate_due_tasks(self, until_date: Optional[datetime] = None) -> List[Todo]:
        """Generate all tasks that are due up to the specified date"""
        if not until_date:
            until_date = datetime.now() + timedelta(days=30)  # Generate a month ahead
        
        generated_tasks = []
        current_time = datetime.now()
        
        for recurring_task in self.recurring_tasks.values():
            if not recurring_task.active:
                continue
            
            while (recurring_task.next_due and 
                   recurring_task.next_due <= until_date and
                   self._should_generate_occurrence(recurring_task)):
                
                # Generate the actual task
                task = self._generate_task_from_template(recurring_task, recurring_task.next_due)
                generated_tasks.append(task)
                
                # Update recurring task state
                recurring_task.last_generated = current_time
                recurring_task.occurrence_count += 1
                recurring_task.next_due = self.calculate_next_occurrence(
                    recurring_task.next_due, recurring_task.pattern
                )
                
                # Check if we should stop recurring
                if self._should_stop_recurring(recurring_task):
                    recurring_task.active = False
                    break
        
        return generated_tasks
    
    def calculate_next_occurrence(
        self, 
        from_date: datetime, 
        pattern: RecurrencePattern
    ) -> Optional[datetime]:
        """Calculate the next occurrence of a recurring task"""
        if pattern.type == RecurrenceType.DAILY:
            return self._next_daily_occurrence(from_date, pattern)
        elif pattern.type == RecurrenceType.WEEKLY:
            return self._next_weekly_occurrence(from_date, pattern)
        elif pattern.type == RecurrenceType.MONTHLY:
            return self._next_monthly_occurrence(from_date, pattern)
        elif pattern.type == RecurrenceType.YEARLY:
            return self._next_yearly_occurrence(from_date, pattern)
        
        return None
    
    def _next_daily_occurrence(self, from_date: datetime, pattern: RecurrencePattern) -> datetime:
        """Calculate next daily occurrence"""
        next_date = from_date + timedelta(days=pattern.interval)
        
        if pattern.skip_weekends:
            # Skip to next weekday if it falls on weekend
            while next_date.weekday() >= 5:  # Saturday or Sunday
                next_date += timedelta(days=1)
        
        if pattern.business_days_only:
            # Ensure it's a business day
            while next_date.weekday() >= 5 or next_date.date() in self.holidays:
                next_date += timedelta(days=1)
        
        return next_date
    
    def _next_weekly_occurrence(self, from_date: datetime, pattern: RecurrencePattern) -> datetime:
        """Calculate next weekly occurrence"""
        if not pattern.days_of_week:
            # Default to same day of week
            return from_date + timedelta(weeks=pattern.interval)
        
        current_weekday = from_date.weekday()
        target_days = sorted(pattern.days_of_week)
        
        # Find next occurrence within current week
        for day in target_days:
            if day > current_weekday:
                days_ahead = day - current_weekday
                return from_date + timedelta(days=days_ahead)
        
        # Move to next week(s) and find first target day
        weeks_ahead = pattern.interval
        days_ahead = (target_days[0] - current_weekday) + (7 * weeks_ahead)
        return from_date + timedelta(days=days_ahead)
    
    def _next_monthly_occurrence(self, from_date: datetime, pattern: RecurrencePattern) -> datetime:
        """Calculate next monthly occurrence"""
        current_year = from_date.year
        current_month = from_date.month
        current_day = from_date.day
        
        # Move to next month(s)
        target_month = current_month + pattern.interval
        target_year = current_year
        
        while target_month > 12:
            target_month -= 12
            target_year += 1
        
        # Determine target day
        if pattern.days_of_month:
            target_day = pattern.days_of_month[0]  # Use first specified day
        else:
            target_day = current_day
        
        # Handle month-end edge cases
        max_day = monthrange(target_year, target_month)[1]
        if target_day > max_day:
            target_day = max_day
        
        return datetime(target_year, target_month, target_day, 
                       from_date.hour, from_date.minute, from_date.second)
    
    def _next_yearly_occurrence(self, from_date: datetime, pattern: RecurrencePattern) -> datetime:
        """Calculate next yearly occurrence"""
        target_year = from_date.year + pattern.interval
        return from_date.replace(year=target_year)
    
    def _should_generate_occurrence(self, recurring_task: RecurringTask) -> bool:
        """Check if we should generate the next occurrence"""
        pattern = recurring_task.pattern
        
        # Check max occurrences
        if pattern.max_occurrences and recurring_task.occurrence_count >= pattern.max_occurrences:
            return False
        
        # Check end date
        if pattern.end_date and recurring_task.next_due and recurring_task.next_due > pattern.end_date:
            return False
        
        return True
    
    def _should_stop_recurring(self, recurring_task: RecurringTask) -> bool:
        """Check if recurring task should be stopped"""
        return not self._should_generate_occurrence(recurring_task)
    
    def _generate_task_from_template(self, recurring_task: RecurringTask, due_date: datetime) -> Todo:
        """Generate an actual task from recurring template"""
        template = recurring_task.template
        
        # Create new task with unique ID
        task = Todo(
            id=0,  # Will be assigned by storage system
            text=template.text,
            description=template.description,
            project=template.project,
            tags=template.tags.copy(),
            context=template.context.copy(),
            due_date=due_date,
            priority=template.priority,
            assignees=template.assignees.copy(),
            stakeholders=template.stakeholders.copy(),
            effort=template.effort,
            energy_level=template.energy_level,
            time_estimate=template.time_estimate,
            parent_recurring_id=int(recurring_task.id.split('_')[1]) if '_' in recurring_task.id else 0,
            recurrence_count=recurring_task.occurrence_count + 1
        )
        
        return task
    
    def _pattern_to_string(self, pattern: RecurrencePattern) -> str:
        """Convert pattern back to string representation"""
        if pattern.type == RecurrenceType.DAILY:
            if pattern.interval == 1:
                return "daily"
            else:
                return f"every {pattern.interval} days"
        elif pattern.type == RecurrenceType.WEEKLY:
            if pattern.interval == 1 and not pattern.days_of_week:
                return "weekly"
            elif pattern.days_of_week:
                day_names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
                days = [day_names[d] for d in pattern.days_of_week]
                return f"every {', '.join(days)}"
            else:
                return f"every {pattern.interval} weeks"
        elif pattern.type == RecurrenceType.MONTHLY:
            if pattern.interval == 1:
                return "monthly"
            else:
                return f"every {pattern.interval} months"
        elif pattern.type == RecurrenceType.YEARLY:
            if pattern.interval == 1:
                return "yearly"
            else:
                return f"every {pattern.interval} years"
        
        return "custom"
    
    def pause_recurring_task(self, task_id: str):
        """Pause a recurring task"""
        if task_id in self.recurring_tasks:
            self.recurring_tasks[task_id].active = False
            self._save_recurring_tasks()
    
    def resume_recurring_task(self, task_id: str):
        """Resume a paused recurring task"""
        if task_id in self.recurring_tasks:
            self.recurring_tasks[task_id].active = True
            self._save_recurring_tasks()
    
    def delete_recurring_task(self, task_id: str):
        """Delete a recurring task"""
        if task_id in self.recurring_tasks:
            del self.recurring_tasks[task_id]
            self._save_recurring_tasks()
    
    def list_recurring_tasks(self) -> List[RecurringTask]:
        """List all recurring tasks"""
        return list(self.recurring_tasks.values())
    
    def get_recurring_task(self, task_id: str) -> Optional[RecurringTask]:
        """Get a specific recurring task"""
        return self.recurring_tasks.get(task_id)
    
    def _load_recurring_tasks(self):
        """Load recurring tasks from file"""
        try:
            if os.path.exists(self.recurring_file):
                with open(self.recurring_file, 'r') as f:
                    data = yaml.safe_load(f)
                    if data and 'recurring_tasks' in data:
                        for task_data in data['recurring_tasks']:
                            task = self._deserialize_recurring_task(task_data)
                            if task:
                                self.recurring_tasks[task.id] = task
        except Exception:
            # If loading fails, start with empty tasks
            pass
    
    def _save_recurring_tasks(self):
        """Save recurring tasks to file"""
        try:
            os.makedirs(self.config_dir, exist_ok=True)
            
            data = {
                'recurring_tasks': [
                    self._serialize_recurring_task(task) 
                    for task in self.recurring_tasks.values()
                ]
            }
            
            with open(self.recurring_file, 'w') as f:
                yaml.dump(data, f, default_flow_style=False)
        except Exception:
            # Silently fail - we don't want to crash on save issues
            pass
    
    def _serialize_recurring_task(self, task: RecurringTask) -> Dict[str, Any]:
        """Convert recurring task to dictionary for storage"""
        return {
            'id': task.id,
            'template': self._serialize_todo(task.template),
            'pattern': self._serialize_pattern(task.pattern),
            'created_at': task.created_at.isoformat(),
            'last_generated': task.last_generated.isoformat() if task.last_generated else None,
            'next_due': task.next_due.isoformat() if task.next_due else None,
            'occurrence_count': task.occurrence_count,
            'active': task.active
        }
    
    def _deserialize_recurring_task(self, data: Dict[str, Any]) -> Optional[RecurringTask]:
        """Convert dictionary to recurring task"""
        try:
            template = self._deserialize_todo(data['template'])
            pattern = self._deserialize_pattern(data['pattern'])
            
            task = RecurringTask(
                id=data['id'],
                template=template,
                pattern=pattern,
                created_at=datetime.fromisoformat(data['created_at']),
                last_generated=datetime.fromisoformat(data['last_generated']) if data.get('last_generated') else None,
                next_due=datetime.fromisoformat(data['next_due']) if data.get('next_due') else None,
                occurrence_count=data.get('occurrence_count', 0),
                active=data.get('active', True)
            )
            
            return task
        except Exception:
            return None
    
    def _serialize_todo(self, todo: Todo) -> Dict[str, Any]:
        """Serialize todo template for storage"""
        return {
            'text': todo.text,
            'description': todo.description,
            'project': todo.project,
            'tags': todo.tags,
            'context': todo.context,
            'priority': todo.priority.value if todo.priority else 'medium',
            'assignees': todo.assignees,
            'stakeholders': todo.stakeholders,
            'effort': todo.effort,
            'energy_level': todo.energy_level,
            'time_estimate': todo.time_estimate,
            'recurrence': todo.recurrence
        }
    
    def _deserialize_todo(self, data: Dict[str, Any]) -> Todo:
        """Deserialize todo template from storage"""
        return Todo(
            id=0,  # Will be assigned when actual tasks are created
            text=data.get('text', ''),
            description=data.get('description', ''),
            project=data.get('project', 'inbox'),
            tags=data.get('tags', []),
            context=data.get('context', []),
            priority=Priority(data.get('priority', 'medium')),
            assignees=data.get('assignees', []),
            stakeholders=data.get('stakeholders', []),
            effort=data.get('effort', ''),
            energy_level=data.get('energy_level', 'medium'),
            time_estimate=data.get('time_estimate'),
            recurrence=data.get('recurrence', ''),
            recurring_template=True
        )
    
    def _serialize_pattern(self, pattern: RecurrencePattern) -> Dict[str, Any]:
        """Serialize recurrence pattern for storage"""
        return {
            'type': pattern.type.value,
            'interval': pattern.interval,
            'days_of_week': pattern.days_of_week,
            'days_of_month': pattern.days_of_month,
            'months': pattern.months,
            'end_date': pattern.end_date.isoformat() if pattern.end_date else None,
            'max_occurrences': pattern.max_occurrences,
            'skip_weekends': pattern.skip_weekends,
            'skip_holidays': pattern.skip_holidays,
            'business_days_only': pattern.business_days_only
        }
    
    def _deserialize_pattern(self, data: Dict[str, Any]) -> RecurrencePattern:
        """Deserialize recurrence pattern from storage"""
        return RecurrencePattern(
            type=RecurrenceType(data.get('type', 'daily')),
            interval=data.get('interval', 1),
            days_of_week=data.get('days_of_week', []),
            days_of_month=data.get('days_of_month', []),
            months=data.get('months', []),
            end_date=datetime.fromisoformat(data['end_date']) if data.get('end_date') else None,
            max_occurrences=data.get('max_occurrences'),
            skip_weekends=data.get('skip_weekends', False),
            skip_holidays=data.get('skip_holidays', False),
            business_days_only=data.get('business_days_only', False)
        )


def create_recurring_task_from_text(text: str, recurrence_pattern: str) -> Tuple[Todo, RecurrencePattern]:
    """Helper to create recurring task from text description and pattern"""
    from .parser import parse_task_input
    from .config import get_config
    
    # Parse the base task
    config = get_config()
    parsed, errors, suggestions = parse_task_input(text, config)
    
    if errors and any(e.severity == "error" for e in errors):
        raise ValueError(f"Task parsing errors: {[e.message for e in errors if e.severity == 'error']}")
    
    # Parse recurrence pattern
    pattern = RecurrenceParser.parse(recurrence_pattern)
    if not pattern:
        raise ValueError(f"Invalid recurrence pattern: {recurrence_pattern}")
    
    # Create template todo
    from .parser import TaskBuilder
    builder = TaskBuilder(config)
    template = builder.build(parsed, 0)  # ID will be assigned later
    
    return template, pattern