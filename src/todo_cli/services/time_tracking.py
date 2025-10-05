"""Time Tracking and Productivity Analytics for Todo CLI.

This module provides comprehensive time tracking capabilities including:
- Time spent analysis by project, tag, and context
- Productivity heatmaps and work pattern visualization
- Time estimation accuracy tracking
- Work-life balance analysis
- Pomodoro technique integration
- Detailed time reports and insights
"""

import os
import json
import statistics
from datetime import datetime, timedelta, timezone, time
from typing import List, Dict, Any, Optional, Tuple, Set
from dataclasses import dataclass, field
from pathlib import Path
from enum import Enum
from collections import defaultdict, Counter
import calendar

from ..domain import Todo, Priority, TodoStatus
from .analytics import AnalyticsTimeframe, ProductivityAnalyzer
from ..config import get_config


class TimeTrackingType(Enum):
    """Types of time tracking entries"""
    TASK_WORK = "task_work"  # Time spent on specific tasks
    PROJECT_WORK = "project_work"  # Time spent on project in general
    BREAK = "break"  # Break time
    MEETING = "meeting"  # Meeting time
    OVERHEAD = "overhead"  # Administrative/overhead time
    LEARNING = "learning"  # Learning/training time


class WorkPattern(Enum):
    """Identified work patterns"""
    EARLY_BIRD = "early_bird"
    NIGHT_OWL = "night_owl"  
    TRADITIONAL = "traditional"
    FLEXIBLE = "flexible"
    INCONSISTENT = "inconsistent"


@dataclass
class TimeEntry:
    """Individual time tracking entry"""
    id: str
    start_time: datetime
    end_time: Optional[datetime] = None
    duration_minutes: Optional[int] = None
    
    # Associated data
    todo_id: Optional[int] = None
    project: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    context: Optional[str] = None
    
    # Time tracking details
    tracking_type: TimeTrackingType = TimeTrackingType.TASK_WORK
    description: str = ""
    notes: str = ""
    
    # Quality metrics
    focus_level: Optional[int] = None  # 1-10 scale
    energy_level: Optional[int] = None  # 1-10 scale
    interruptions: int = 0
    
    # Metadata
    created: datetime = field(default_factory=datetime.now)
    device: Optional[str] = None
    location: Optional[str] = None
    
    def __post_init__(self):
        """Calculate duration if not provided"""
        if self.end_time and not self.duration_minutes:
            duration = self.end_time - self.start_time
            self.duration_minutes = int(duration.total_seconds() / 60)
    
    def is_active(self) -> bool:
        """Check if time entry is currently active (no end time)"""
        return self.end_time is None
    
    def get_duration_hours(self) -> float:
        """Get duration in hours"""
        if self.duration_minutes:
            return self.duration_minutes / 60
        elif self.end_time:
            duration = self.end_time - self.start_time
            return duration.total_seconds() / 3600
        else:
            # Active entry - calculate current duration
            duration = datetime.now() - self.start_time
            return duration.total_seconds() / 3600
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'id': self.id,
            'start_time': self.start_time.isoformat(),
            'end_time': self.end_time.isoformat() if self.end_time else None,
            'duration_minutes': self.duration_minutes,
            'todo_id': self.todo_id,
            'project': self.project,
            'tags': self.tags,
            'context': self.context,
            'tracking_type': self.tracking_type.value,
            'description': self.description,
            'notes': self.notes,
            'focus_level': self.focus_level,
            'energy_level': self.energy_level,
            'interruptions': self.interruptions,
            'created': self.created.isoformat(),
            'device': self.device,
            'location': self.location
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'TimeEntry':
        """Create from dictionary"""
        return cls(
            id=data['id'],
            start_time=datetime.fromisoformat(data['start_time']),
            end_time=datetime.fromisoformat(data['end_time']) if data.get('end_time') else None,
            duration_minutes=data.get('duration_minutes'),
            todo_id=data.get('todo_id'),
            project=data.get('project'),
            tags=data.get('tags', []),
            context=data.get('context'),
            tracking_type=TimeTrackingType(data.get('tracking_type', 'task_work')),
            description=data.get('description', ''),
            notes=data.get('notes', ''),
            focus_level=data.get('focus_level'),
            energy_level=data.get('energy_level'),
            interruptions=data.get('interruptions', 0),
            created=datetime.fromisoformat(data.get('created', datetime.now().isoformat())),
            device=data.get('device'),
            location=data.get('location')
        )


@dataclass
class ProductivityHeatmap:
    """Productivity heatmap data"""
    timeframe: AnalyticsTimeframe
    data: Dict[str, Dict[str, float]]  # date -> hour -> productivity_score
    peak_hours: List[int]
    peak_days: List[str]
    least_productive_hours: List[int]
    least_productive_days: List[str]
    work_pattern: WorkPattern
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'timeframe': self.timeframe.value,
            'data': self.data,
            'peak_hours': self.peak_hours,
            'peak_days': self.peak_days,
            'least_productive_hours': self.least_productive_hours,
            'least_productive_days': self.least_productive_days,
            'work_pattern': self.work_pattern.value
        }


@dataclass
class TimeAllocation:
    """Time allocation analysis"""
    total_tracked_hours: float
    project_breakdown: Dict[str, float]  # project -> hours
    tag_breakdown: Dict[str, float]      # tag -> hours
    context_breakdown: Dict[str, float]  # context -> hours
    type_breakdown: Dict[str, float]     # tracking_type -> hours
    
    # Percentages
    project_percentages: Dict[str, float] = field(default_factory=dict)
    tag_percentages: Dict[str, float] = field(default_factory=dict)
    context_percentages: Dict[str, float] = field(default_factory=dict)
    type_percentages: Dict[str, float] = field(default_factory=dict)
    
    def __post_init__(self):
        """Calculate percentages"""
        if self.total_tracked_hours > 0:
            self.project_percentages = {
                k: (v / self.total_tracked_hours) * 100 
                for k, v in self.project_breakdown.items()
            }
            self.tag_percentages = {
                k: (v / self.total_tracked_hours) * 100 
                for k, v in self.tag_breakdown.items()
            }
            self.context_percentages = {
                k: (v / self.total_tracked_hours) * 100 
                for k, v in self.context_breakdown.items()
            }
            self.type_percentages = {
                k: (v / self.total_tracked_hours) * 100 
                for k, v in self.type_breakdown.items()
            }
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'total_tracked_hours': self.total_tracked_hours,
            'project_breakdown': self.project_breakdown,
            'tag_breakdown': self.tag_breakdown,
            'context_breakdown': self.context_breakdown,
            'type_breakdown': self.type_breakdown,
            'project_percentages': self.project_percentages,
            'tag_percentages': self.tag_percentages,
            'context_percentages': self.context_percentages,
            'type_percentages': self.type_percentages
        }


@dataclass
class EstimationAccuracy:
    """Time estimation accuracy analysis"""
    total_tasks_with_estimates: int
    accurate_estimates: int  # Within 25% of actual
    underestimated_tasks: int
    overestimated_tasks: int
    
    accuracy_percentage: float
    average_estimation_error: float  # Percentage
    median_estimation_error: float
    
    # By category
    accuracy_by_project: Dict[str, float] = field(default_factory=dict)
    accuracy_by_priority: Dict[str, float] = field(default_factory=dict)
    accuracy_by_tag: Dict[str, float] = field(default_factory=dict)
    
    # Improvement metrics
    estimation_trend: Optional[str] = None  # "improving", "declining", "stable"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'total_tasks_with_estimates': self.total_tasks_with_estimates,
            'accurate_estimates': self.accurate_estimates,
            'underestimated_tasks': self.underestimated_tasks,
            'overestimated_tasks': self.overestimated_tasks,
            'accuracy_percentage': self.accuracy_percentage,
            'average_estimation_error': self.average_estimation_error,
            'median_estimation_error': self.median_estimation_error,
            'accuracy_by_project': self.accuracy_by_project,
            'accuracy_by_priority': self.accuracy_by_priority,
            'accuracy_by_tag': self.accuracy_by_tag,
            'estimation_trend': self.estimation_trend
        }


@dataclass
class TimeReport:
    """Comprehensive time tracking report"""
    timeframe: AnalyticsTimeframe
    start_date: datetime
    end_date: datetime
    
    # Core metrics
    time_allocation: TimeAllocation
    productivity_heatmap: ProductivityHeatmap
    estimation_accuracy: EstimationAccuracy
    
    # Summary stats
    total_work_hours: float
    average_daily_hours: float
    most_productive_day: Optional[str] = None
    least_productive_day: Optional[str] = None
    work_pattern: WorkPattern = WorkPattern.TRADITIONAL
    
    # Work-life balance
    work_hours_per_day: Dict[str, float] = field(default_factory=dict)
    overtime_days: List[str] = field(default_factory=list)
    weekend_work_hours: float = 0.0
    
    # Focus and energy
    average_focus_level: Optional[float] = None
    average_energy_level: Optional[float] = None
    total_interruptions: int = 0
    deep_work_hours: float = 0.0  # Hours with focus >= 8
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'timeframe': self.timeframe.value,
            'start_date': self.start_date.isoformat(),
            'end_date': self.end_date.isoformat(),
            'time_allocation': self.time_allocation.to_dict(),
            'productivity_heatmap': self.productivity_heatmap.to_dict(),
            'estimation_accuracy': self.estimation_accuracy.to_dict(),
            'total_work_hours': self.total_work_hours,
            'average_daily_hours': self.average_daily_hours,
            'most_productive_day': self.most_productive_day,
            'least_productive_day': self.least_productive_day,
            'work_pattern': self.work_pattern.value,
            'work_hours_per_day': self.work_hours_per_day,
            'overtime_days': self.overtime_days,
            'weekend_work_hours': self.weekend_work_hours,
            'average_focus_level': self.average_focus_level,
            'average_energy_level': self.average_energy_level,
            'total_interruptions': self.total_interruptions,
            'deep_work_hours': self.deep_work_hours
        }


class TimeTracker:
    """Time tracking manager"""
    
    def __init__(self):
        self.config = get_config()
        self.tracking_dir = Path(self.config.data_dir) / "time_tracking"
        self.tracking_dir.mkdir(parents=True, exist_ok=True)
        self.entries_file = self.tracking_dir / "time_entries.json"
        self.active_entry_file = self.tracking_dir / "active_entry.json"
        self.entries = self._load_entries()
        self.active_entry = self._load_active_entry()
    
    def _load_entries(self) -> List[TimeEntry]:
        """Load time entries from file"""
        if self.entries_file.exists():
            try:
                with open(self.entries_file, 'r') as f:
                    data = json.load(f)
                return [TimeEntry.from_dict(entry_data) for entry_data in data]
            except (json.JSONDecodeError, IOError):
                pass
        return []
    
    def _save_entries(self):
        """Save time entries to file"""
        try:
            data = [entry.to_dict() for entry in self.entries]
            with open(self.entries_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"Error saving time entries: {e}")
    
    def _load_active_entry(self) -> Optional[TimeEntry]:
        """Load active time entry"""
        if self.active_entry_file.exists():
            try:
                with open(self.active_entry_file, 'r') as f:
                    data = json.load(f)
                return TimeEntry.from_dict(data)
            except (json.JSONDecodeError, IOError):
                pass
        return None
    
    def _save_active_entry(self, entry: Optional[TimeEntry]):
        """Save active entry to file"""
        try:
            if entry:
                with open(self.active_entry_file, 'w') as f:
                    json.dump(entry.to_dict(), f, indent=2)
            elif self.active_entry_file.exists():
                self.active_entry_file.unlink()
        except Exception as e:
            print(f"Error saving active entry: {e}")
    
    def start_tracking(self, todo: Optional[Todo] = None, 
                      description: str = "",
                      tracking_type: TimeTrackingType = TimeTrackingType.TASK_WORK) -> TimeEntry:
        """Start tracking time"""
        # Stop any current tracking
        if self.active_entry:
            self.stop_tracking()
        
        # Create new entry
        entry_id = f"time_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        entry = TimeEntry(
            id=entry_id,
            start_time=datetime.now(),
            todo_id=todo.id if todo else None,
            project=todo.project if todo else None,
            tags=list(todo.tags) if todo and todo.tags else [],
            context=todo.context[0] if todo and todo.context else None,
            tracking_type=tracking_type,
            description=description or (todo.text if todo else "")
        )
        
        self.active_entry = entry
        self._save_active_entry(entry)
        
        return entry
    
    def stop_tracking(self, focus_level: Optional[int] = None,
                     energy_level: Optional[int] = None,
                     interruptions: int = 0,
                     notes: str = "") -> Optional[TimeEntry]:
        """Stop current time tracking"""
        if not self.active_entry:
            return None
        
        # Complete the entry
        self.active_entry.end_time = datetime.now()
        self.active_entry.focus_level = focus_level
        self.active_entry.energy_level = energy_level
        self.active_entry.interruptions = interruptions
        if notes:
            self.active_entry.notes = notes
        
        # Calculate duration
        self.active_entry.__post_init__()
        
        # Save to entries list
        self.entries.append(self.active_entry)
        completed_entry = self.active_entry
        
        # Clear active entry
        self.active_entry = None
        self._save_active_entry(None)
        self._save_entries()
        
        return completed_entry
    
    def get_current_tracking(self) -> Optional[TimeEntry]:
        """Get currently active time entry"""
        return self.active_entry
    
    def add_manual_entry(self, start_time: datetime, end_time: datetime,
                        todo: Optional[Todo] = None, **kwargs) -> TimeEntry:
        """Add a manual time entry"""
        entry_id = f"manual_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        entry = TimeEntry(
            id=entry_id,
            start_time=start_time,
            end_time=end_time,
            todo_id=todo.id if todo else None,
            project=todo.project if todo else kwargs.get('project'),
            tags=list(todo.tags) if todo and todo.tags else kwargs.get('tags', []),
            context=todo.context[0] if todo and todo.context else kwargs.get('context'),
            **kwargs
        )
        
        self.entries.append(entry)
        self._save_entries()
        
        return entry
    
    def get_entries_for_timeframe(self, timeframe: AnalyticsTimeframe,
                                 end_date: Optional[datetime] = None) -> List[TimeEntry]:
        """Get time entries for a specific timeframe"""
        if end_date is None:
            end_date = datetime.now()
        
        start_date = self._calculate_start_date(timeframe, end_date)
        
        return [
            entry for entry in self.entries
            if start_date <= entry.start_time <= end_date
        ]
    
    def _calculate_start_date(self, timeframe: AnalyticsTimeframe, end_date: datetime) -> datetime:
        """Calculate start date for timeframe"""
        if timeframe == AnalyticsTimeframe.DAILY:
            return end_date.replace(hour=0, minute=0, second=0, microsecond=0)
        elif timeframe == AnalyticsTimeframe.WEEKLY:
            days_back = end_date.weekday()
            return (end_date - timedelta(days=days_back)).replace(hour=0, minute=0, second=0, microsecond=0)
        elif timeframe == AnalyticsTimeframe.MONTHLY:
            return end_date.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        elif timeframe == AnalyticsTimeframe.QUARTERLY:
            quarter_start_month = ((end_date.month - 1) // 3) * 3 + 1
            return end_date.replace(month=quarter_start_month, day=1, hour=0, minute=0, second=0, microsecond=0)
        elif timeframe == AnalyticsTimeframe.YEARLY:
            return end_date.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
        else:  # ALL_TIME
            return datetime(2020, 1, 1)


class TimeAnalyzer:
    """Advanced time tracking analytics"""
    
    def __init__(self, time_tracker: TimeTracker):
        self.time_tracker = time_tracker
        self.config = get_config()
    
    def generate_time_report(self, timeframe: AnalyticsTimeframe = AnalyticsTimeframe.WEEKLY,
                           end_date: Optional[datetime] = None) -> TimeReport:
        """Generate comprehensive time tracking report"""
        if end_date is None:
            end_date = datetime.now()
        
        start_date = self.time_tracker._calculate_start_date(timeframe, end_date)
        entries = self.time_tracker.get_entries_for_timeframe(timeframe, end_date)
        
        # Generate components
        time_allocation = self._analyze_time_allocation(entries)
        productivity_heatmap = self._generate_productivity_heatmap(entries, timeframe)
        estimation_accuracy = self._analyze_estimation_accuracy(entries)
        
        # Calculate summary metrics
        total_work_hours = sum(entry.get_duration_hours() for entry in entries if entry.end_time)
        days_in_period = max(1, (end_date - start_date).days)
        average_daily_hours = total_work_hours / days_in_period
        
        # Work pattern analysis
        work_pattern = self._identify_work_pattern(entries)
        
        # Daily breakdown
        work_hours_per_day = self._calculate_daily_hours(entries)
        most_productive_day = max(work_hours_per_day.keys(), key=lambda k: work_hours_per_day[k]) if work_hours_per_day else None
        least_productive_day = min(work_hours_per_day.keys(), key=lambda k: work_hours_per_day[k]) if work_hours_per_day else None
        
        # Work-life balance metrics
        overtime_days = [day for day, hours in work_hours_per_day.items() if hours > 8]
        weekend_entries = [e for e in entries if e.start_time.weekday() >= 5]
        weekend_work_hours = sum(e.get_duration_hours() for e in weekend_entries if e.end_time)
        
        # Focus and energy metrics
        entries_with_focus = [e for e in entries if e.focus_level is not None and e.end_time]
        average_focus = statistics.mean([e.focus_level for e in entries_with_focus]) if entries_with_focus else None
        
        entries_with_energy = [e for e in entries if e.energy_level is not None and e.end_time]
        average_energy = statistics.mean([e.energy_level for e in entries_with_energy]) if entries_with_energy else None
        
        total_interruptions = sum(e.interruptions for e in entries)
        deep_work_hours = sum(e.get_duration_hours() for e in entries 
                            if e.focus_level and e.focus_level >= 8 and e.end_time)
        
        return TimeReport(
            timeframe=timeframe,
            start_date=start_date,
            end_date=end_date,
            time_allocation=time_allocation,
            productivity_heatmap=productivity_heatmap,
            estimation_accuracy=estimation_accuracy,
            total_work_hours=total_work_hours,
            average_daily_hours=average_daily_hours,
            most_productive_day=most_productive_day,
            least_productive_day=least_productive_day,
            work_pattern=work_pattern,
            work_hours_per_day=work_hours_per_day,
            overtime_days=overtime_days,
            weekend_work_hours=weekend_work_hours,
            average_focus_level=average_focus,
            average_energy_level=average_energy,
            total_interruptions=total_interruptions,
            deep_work_hours=deep_work_hours
        )
    
    def _analyze_time_allocation(self, entries: List[TimeEntry]) -> TimeAllocation:
        """Analyze how time is allocated"""
        completed_entries = [e for e in entries if e.end_time]
        total_hours = sum(e.get_duration_hours() for e in completed_entries)
        
        # Breakdown by category
        project_breakdown = defaultdict(float)
        tag_breakdown = defaultdict(float)
        context_breakdown = defaultdict(float)
        type_breakdown = defaultdict(float)
        
        for entry in completed_entries:
            hours = entry.get_duration_hours()
            
            if entry.project:
                project_breakdown[entry.project] += hours
            
            for tag in entry.tags:
                tag_breakdown[tag] += hours
            
            if entry.context:
                context_breakdown[entry.context] += hours
            
            type_breakdown[entry.tracking_type.value] += hours
        
        return TimeAllocation(
            total_tracked_hours=total_hours,
            project_breakdown=dict(project_breakdown),
            tag_breakdown=dict(tag_breakdown),
            context_breakdown=dict(context_breakdown),
            type_breakdown=dict(type_breakdown)
        )
    
    def _generate_productivity_heatmap(self, entries: List[TimeEntry], 
                                     timeframe: AnalyticsTimeframe) -> ProductivityHeatmap:
        """Generate productivity heatmap"""
        completed_entries = [e for e in entries if e.end_time]
        
        # Group by date and hour
        heatmap_data = defaultdict(lambda: defaultdict(float))
        hour_totals = defaultdict(float)
        day_totals = defaultdict(float)
        
        for entry in completed_entries:
            date_str = entry.start_time.date().isoformat()
            hour = entry.start_time.hour
            hours = entry.get_duration_hours()
            
            # Weight by focus level if available
            productivity_score = hours
            if entry.focus_level:
                productivity_score *= (entry.focus_level / 10)
            
            heatmap_data[date_str][str(hour)] = productivity_score
            hour_totals[hour] += productivity_score
            day_totals[date_str] += productivity_score
        
        # Find peaks
        peak_hours = sorted(hour_totals.keys(), key=lambda h: hour_totals[h], reverse=True)[:3]
        peak_days = sorted(day_totals.keys(), key=lambda d: day_totals[d], reverse=True)[:3]
        
        least_hours = sorted(hour_totals.keys(), key=lambda h: hour_totals[h])[:3]
        least_days = sorted(day_totals.keys(), key=lambda d: day_totals[d])[:3]
        
        # Identify work pattern
        work_pattern = self._identify_work_pattern(entries)
        
        return ProductivityHeatmap(
            timeframe=timeframe,
            data=dict(heatmap_data),
            peak_hours=peak_hours,
            peak_days=peak_days,
            least_productive_hours=least_hours,
            least_productive_days=least_days,
            work_pattern=work_pattern
        )
    
    def _analyze_estimation_accuracy(self, entries: List[TimeEntry]) -> EstimationAccuracy:
        """Analyze time estimation accuracy"""
        # This would require connecting with Todo objects that have estimates
        # For now, return a placeholder
        return EstimationAccuracy(
            total_tasks_with_estimates=0,
            accurate_estimates=0,
            underestimated_tasks=0,
            overestimated_tasks=0,
            accuracy_percentage=0.0,
            average_estimation_error=0.0,
            median_estimation_error=0.0
        )
    
    def _identify_work_pattern(self, entries: List[TimeEntry]) -> WorkPattern:
        """Identify work pattern from time entries"""
        if not entries:
            return WorkPattern.TRADITIONAL
        
        completed_entries = [e for e in entries if e.end_time]
        if not completed_entries:
            return WorkPattern.TRADITIONAL
        
        # Analyze start times
        start_hours = [e.start_time.hour for e in completed_entries]
        
        if not start_hours:
            return WorkPattern.TRADITIONAL
        
        avg_start_hour = statistics.mean(start_hours)
        std_dev = statistics.stdev(start_hours) if len(start_hours) > 1 else 0
        
        # Classify pattern
        if std_dev > 3:
            return WorkPattern.INCONSISTENT
        elif avg_start_hour < 7:
            return WorkPattern.EARLY_BIRD
        elif avg_start_hour > 10:
            return WorkPattern.NIGHT_OWL
        elif 8 <= avg_start_hour <= 10:
            return WorkPattern.TRADITIONAL
        else:
            return WorkPattern.FLEXIBLE
    
    def _calculate_daily_hours(self, entries: List[TimeEntry]) -> Dict[str, float]:
        """Calculate work hours per day"""
        daily_hours = defaultdict(float)
        completed_entries = [e for e in entries if e.end_time]
        
        for entry in completed_entries:
            date_str = entry.start_time.date().isoformat()
            daily_hours[date_str] += entry.get_duration_hours()
        
        return dict(daily_hours)
    
    def get_productivity_insights(self, report: TimeReport) -> List[str]:
        """Generate productivity insights from time report"""
        insights = []
        
        # Work hours insights
        if report.average_daily_hours > 10:
            insights.append("⚠️ High work load detected - consider work-life balance")
        elif report.average_daily_hours < 4:
            insights.append("💡 Low tracked hours - consider tracking more activities")
        
        # Deep work insights
        if report.total_work_hours > 0:
            deep_work_percentage = (report.deep_work_hours / report.total_work_hours) * 100
            if deep_work_percentage > 40:
                insights.append("🎯 Excellent deep work focus - maintain this momentum!")
            elif deep_work_percentage < 20:
                insights.append("📈 Consider scheduling more focused work blocks")
        
        # Weekend work
        if report.weekend_work_hours > 8:
            insights.append("🏠 High weekend work hours - consider rest and recovery")
        
        # Work pattern insights
        if report.work_pattern == WorkPattern.EARLY_BIRD:
            insights.append("🌅 Early bird pattern detected - optimize morning hours")
        elif report.work_pattern == WorkPattern.NIGHT_OWL:
            insights.append("🦉 Night owl pattern - ensure adequate rest")
        elif report.work_pattern == WorkPattern.INCONSISTENT:
            insights.append("📊 Inconsistent work pattern - consider establishing routines")
        
        # Interruption insights
        if report.total_interruptions > 0:
            interruptions_per_hour = report.total_interruptions / max(1, report.total_work_hours)
            if interruptions_per_hour > 2:
                insights.append("🚫 High interruption rate - consider focus techniques")
        
        return insights
    
    def export_time_data(self, timeframe: AnalyticsTimeframe,
                        format_type: str = "csv") -> str:
        """Export time tracking data"""
        entries = self.time_tracker.get_entries_for_timeframe(timeframe)
        
        if format_type == "csv":
            return self._export_to_csv(entries)
        elif format_type == "json":
            return json.dumps([entry.to_dict() for entry in entries], indent=2)
        else:
            raise ValueError(f"Unsupported format: {format_type}")
    
    def _export_to_csv(self, entries: List[TimeEntry]) -> str:
        """Export entries to CSV format"""
        import csv
        import io
        
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Header
        writer.writerow([
            'Date', 'Start Time', 'End Time', 'Duration (hours)',
            'Project', 'Tags', 'Context', 'Type', 'Description',
            'Focus Level', 'Energy Level', 'Interruptions'
        ])
        
        # Data
        for entry in entries:
            writer.writerow([
                entry.start_time.date().isoformat(),
                entry.start_time.time().isoformat(),
                entry.end_time.time().isoformat() if entry.end_time else 'Active',
                f"{entry.get_duration_hours():.2f}",
                entry.project or '',
                ';'.join(entry.tags),
                entry.context or '',
                entry.tracking_type.value,
                entry.description,
                entry.focus_level or '',
                entry.energy_level or '',
                entry.interruptions
            ])
        
        return output.getvalue()