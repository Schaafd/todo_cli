"""Advanced Analytics and Productivity Insights Engine for Todo CLI.

This module provides comprehensive analytics capabilities including:
- Task completion patterns and trends
- Productivity scoring and benchmarking
- Time management effectiveness analysis
- Project velocity and burndown tracking
- Predictive insights and recommendations
"""

import os
import json
import statistics
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any, Optional, Tuple, Set, Union
from dataclasses import dataclass, field
from pathlib import Path
from enum import Enum
from collections import defaultdict, Counter
import math
from ..utils.datetime import now_utc, ensure_aware

from ..domain import Todo, Priority, TodoStatus
from ..config import get_config


class AnalyticsTimeframe(Enum):
    """Time frames for analytics analysis"""
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    YEARLY = "yearly"
    ALL_TIME = "all_time"


class ProductivityMetric(Enum):
    """Key productivity metrics"""
    COMPLETION_RATE = "completion_rate"
    VELOCITY = "velocity"
    FOCUS_SCORE = "focus_score"
    ESTIMATION_ACCURACY = "estimation_accuracy"
    TIME_TO_COMPLETION = "time_to_completion"
    PRIORITY_ADHERENCE = "priority_adherence"
    PROCRASTINATION_INDEX = "procrastination_index"
    CONSISTENCY_SCORE = "consistency_score"


@dataclass
class ProductivityScore:
    """Comprehensive productivity scoring"""
    overall_score: float  # 0-100
    completion_rate: float
    velocity_score: float
    focus_score: float
    consistency_score: float
    time_management_score: float
    priority_adherence_score: float
    
    # Additional metrics
    tasks_completed: int
    tasks_created: int
    average_completion_time: Optional[float]  # hours
    estimation_accuracy: Optional[float]  # percentage
    
    # Trends (positive/negative change from previous period)
    completion_rate_trend: Optional[float] = None
    velocity_trend: Optional[float] = None
    consistency_trend: Optional[float] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            'overall_score': self.overall_score,
            'completion_rate': self.completion_rate,
            'velocity_score': self.velocity_score,
            'focus_score': self.focus_score,
            'consistency_score': self.consistency_score,
            'time_management_score': self.time_management_score,
            'priority_adherence_score': self.priority_adherence_score,
            'tasks_completed': self.tasks_completed,
            'tasks_created': self.tasks_created,
            'average_completion_time': self.average_completion_time,
            'estimation_accuracy': self.estimation_accuracy,
            'completion_rate_trend': self.completion_rate_trend,
            'velocity_trend': self.velocity_trend,
            'consistency_trend': self.consistency_trend
        }


@dataclass
class TaskPattern:
    """Identified task pattern"""
    pattern_type: str  # "peak_hours", "project_preference", "priority_bias", etc.
    description: str
    confidence: float  # 0-1
    frequency: int
    recommendation: Optional[str] = None
    data_points: List[Any] = field(default_factory=list)


@dataclass
class ProductivityInsight:
    """Individual productivity insight"""
    insight_type: str  # "strength", "weakness", "opportunity", "trend"
    title: str
    description: str
    impact_level: str  # "high", "medium", "low"
    confidence: float  # 0-1
    actionable_recommendation: Optional[str] = None
    supporting_data: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'insight_type': self.insight_type,
            'title': self.title,
            'description': self.description,
            'impact_level': self.impact_level,
            'confidence': self.confidence,
            'actionable_recommendation': self.actionable_recommendation,
            'supporting_data': self.supporting_data
        }


@dataclass
class StatisticalAnalysis:
    """Summary statistics for analytics calculations"""
    mean_completion_time: Optional[float] = None  # hours
    completion_time_variance: float = 0.0
    productivity_trend_slope: float = 0.0


@dataclass
class AnalyticsReport:
    """Comprehensive analytics report"""
    timeframe: AnalyticsTimeframe
    start_date: datetime
    end_date: datetime
    productivity_score: ProductivityScore
    insights: List[ProductivityInsight]
    patterns: List[TaskPattern]
    
    # Detailed breakdowns
    completion_by_day: Dict[str, int] = field(default_factory=dict)
    completion_by_priority: Dict[str, int] = field(default_factory=dict)
    completion_by_project: Dict[str, int] = field(default_factory=dict)
    completion_by_hour: Dict[int, int] = field(default_factory=dict)
    
    # Time analysis
    average_task_duration: Optional[float] = None
    peak_productivity_hours: List[int] = field(default_factory=list)
    least_productive_hours: List[int] = field(default_factory=list)
    
    # Project analysis
    most_active_projects: List[str] = field(default_factory=list)
    stalled_projects: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            'timeframe': self.timeframe.value,
            'start_date': self.start_date.isoformat(),
            'end_date': self.end_date.isoformat(),
            'productivity_score': self.productivity_score.to_dict(),
            'insights': [insight.to_dict() for insight in self.insights],
            'patterns': [
                {
                    'pattern_type': p.pattern_type,
                    'description': p.description,
                    'confidence': p.confidence,
                    'frequency': p.frequency,
                    'recommendation': p.recommendation,
                    'data_points': p.data_points
                } for p in self.patterns
            ],
            'completion_by_day': self.completion_by_day,
            'completion_by_priority': self.completion_by_priority,
            'completion_by_project': self.completion_by_project,
            'completion_by_hour': self.completion_by_hour,
            'average_task_duration': self.average_task_duration,
            'peak_productivity_hours': self.peak_productivity_hours,
            'least_productive_hours': self.least_productive_hours,
            'most_active_projects': self.most_active_projects,
            'stalled_projects': self.stalled_projects
        }


class ProductivityAnalyzer:
    """Core analytics engine for productivity insights"""
    
    def __init__(self):
        self.config = get_config()
        self.analytics_dir = Path(self.config.data_dir) / "analytics"
        self.analytics_dir.mkdir(parents=True, exist_ok=True)
        self.cache_file = self.analytics_dir / "analytics_cache.json"
        self.cache = self._load_cache()
    
    def _load_cache(self) -> Dict[str, Any]:
        """Load analytics cache"""
        if self.cache_file.exists():
            try:
                with open(self.cache_file, 'r') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                pass
        return {"reports": {}, "metrics": {}, "last_updated": None}
    
    def _save_cache(self):
        """Save analytics cache"""
        try:
            self.cache["last_updated"] = datetime.now().isoformat()
            with open(self.cache_file, 'w') as f:
                json.dump(self.cache, f, indent=2, default=str)
        except Exception as e:
            print(f"Error saving analytics cache: {e}")
    
    def analyze_productivity(self, todos: List[Todo], 
                           timeframe: AnalyticsTimeframe = AnalyticsTimeframe.MONTHLY,
                           end_date: Optional[datetime] = None) -> AnalyticsReport:
        """Generate comprehensive productivity analysis"""
        
        if end_date is None:
            end_date = now_utc()
        else:
            end_date = ensure_aware(end_date)
        
        # Calculate timeframe start date
        start_date = self._calculate_start_date(timeframe, end_date)
        
        # Filter todos by timeframe
        filtered_todos = self._filter_todos_by_timeframe(todos, start_date, end_date)
        
        # Generate core metrics
        productivity_score = self._calculate_productivity_score(filtered_todos, start_date, end_date)
        
        # Identify patterns
        patterns = self._identify_patterns(filtered_todos)
        
        # Generate insights
        insights = self._generate_insights(filtered_todos, productivity_score, patterns)
        
        # Create detailed breakdowns
        completion_by_day = self._analyze_completion_by_day(filtered_todos)
        completion_by_priority = self._analyze_completion_by_priority(filtered_todos)
        completion_by_project = self._analyze_completion_by_project(filtered_todos)
        completion_by_hour = self._analyze_completion_by_hour(filtered_todos)
        
        # Time analysis
        average_duration = self._calculate_average_duration(filtered_todos)
        peak_hours, least_hours = self._analyze_productivity_hours(filtered_todos)
        
        # Project analysis
        active_projects, stalled_projects = self._analyze_projects(filtered_todos)
        
        # Create report
        report = AnalyticsReport(
            timeframe=timeframe,
            start_date=start_date,
            end_date=end_date,
            productivity_score=productivity_score,
            insights=insights,
            patterns=patterns,
            completion_by_day=completion_by_day,
            completion_by_priority=completion_by_priority,
            completion_by_project=completion_by_project,
            completion_by_hour=completion_by_hour,
            average_task_duration=average_duration,
            peak_productivity_hours=peak_hours,
            least_productive_hours=least_hours,
            most_active_projects=active_projects,
            stalled_projects=stalled_projects
        )
        
        # Cache the report
        cache_key = f"{timeframe.value}_{start_date.date()}_{end_date.date()}"
        self.cache["reports"][cache_key] = report.to_dict()
        self._save_cache()
        
        return report
    
    def _calculate_start_date(self, timeframe: AnalyticsTimeframe, end_date: datetime) -> datetime:
        """Calculate start date based on timeframe"""
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
            # Reasonable start date for all-time analysis, with same tz as end_date
            base = datetime(2020, 1, 1)
            return ensure_aware(base, tz=end_date.tzinfo) if hasattr(end_date, 'tzinfo') else base
    
    def _filter_todos_by_timeframe(self, todos: List[Todo], start_date: datetime, end_date: datetime) -> List[Todo]:
        """Filter todos by timeframe"""
        return [
            todo for todo in todos
            if (todo.created and start_date <= todo.created <= end_date) or
               (todo.completed_date and start_date <= todo.completed_date <= end_date) or
               (todo.due_date and start_date <= todo.due_date <= end_date)
        ]
    
    def _calculate_productivity_score(self, todos: List[Todo], start_date: datetime, end_date: datetime) -> ProductivityScore:
        """Calculate comprehensive productivity score"""
        
        completed_todos = [t for t in todos if t.completed]
        total_todos = len(todos)
        completed_count = len(completed_todos)
        
        # Completion Rate (0-100)
        completion_rate = (completed_count / total_todos * 100) if total_todos > 0 else 0
        
        # Velocity Score (tasks per day, normalized to 0-100)
        days_in_period = max(1, (end_date - start_date).days)
        velocity = completed_count / days_in_period
        velocity_score = min(100, velocity * 20)  # Assume 5 tasks/day = 100 score
        
        # Focus Score (based on project/context switching)
        focus_score = self._calculate_focus_score(completed_todos)
        
        # Consistency Score (based on daily completion variance)
        consistency_score = self._calculate_consistency_score(completed_todos, start_date, end_date)
        
        # Time Management Score (based on due date adherence)
        time_management_score = self._calculate_time_management_score(completed_todos)
        
        # Priority Adherence Score
        priority_adherence_score = self._calculate_priority_adherence_score(completed_todos)
        
        # Overall Score (weighted average)
        overall_score = (
            completion_rate * 0.25 +
            velocity_score * 0.20 +
            focus_score * 0.15 +
            consistency_score * 0.15 +
            time_management_score * 0.15 +
            priority_adherence_score * 0.10
        )
        
        # Calculate additional metrics
        avg_completion_time = self._calculate_average_completion_time(completed_todos)
        estimation_accuracy = self._calculate_estimation_accuracy(completed_todos)
        
        return ProductivityScore(
            overall_score=overall_score,
            completion_rate=completion_rate,
            velocity_score=velocity_score,
            focus_score=focus_score,
            consistency_score=consistency_score,
            time_management_score=time_management_score,
            priority_adherence_score=priority_adherence_score,
            tasks_completed=completed_count,
            tasks_created=total_todos,
            average_completion_time=avg_completion_time,
            estimation_accuracy=estimation_accuracy
        )
    
    def _calculate_focus_score(self, todos: List[Todo]) -> float:
        """Calculate focus score based on context switching"""
        if not todos:
            return 0
        
        # Analyze project/context switching
        project_switches = 0
        context_switches = 0
        last_project = None
        last_context = None
        
        # Sort by completion date
        sorted_todos = sorted([t for t in todos if t.completed_date], 
                            key=lambda x: x.completed_date)
        
        for todo in sorted_todos:
            if last_project and todo.project != last_project:
                project_switches += 1
            if last_context and todo.context != last_context:
                context_switches += 1
            
            last_project = todo.project
            last_context = todo.context
        
        if len(sorted_todos) <= 1:
            return 100
        
        # Lower switches = higher focus
        max_switches = len(sorted_todos) - 1
        total_switches = project_switches + context_switches
        focus_ratio = 1 - (total_switches / (max_switches * 2))  # *2 for both types
        
        return max(0, focus_ratio * 100)
    
    def _calculate_consistency_score(self, todos: List[Todo], start_date: datetime, end_date: datetime) -> float:
        """Calculate consistency score based on daily completion variance"""
        if not todos:
            return 0
        
        # Group completions by day
        daily_completions = defaultdict(int)
        completed_todos = [t for t in todos if t.completed_date]
        
        for todo in completed_todos:
            day = todo.completed_date.date()
            daily_completions[day] += 1
        
        if len(daily_completions) <= 1:
            return 100
        
        # Calculate coefficient of variation (lower = more consistent)
        completion_counts = list(daily_completions.values())
        mean_completions = statistics.mean(completion_counts)
        
        if mean_completions == 0:
            return 0
        
        std_dev = statistics.stdev(completion_counts) if len(completion_counts) > 1 else 0
        cv = std_dev / mean_completions
        
        # Convert to score (lower CV = higher score)
        consistency_score = max(0, 100 - (cv * 100))
        return min(100, consistency_score)
    
    def _calculate_time_management_score(self, todos: List[Todo]) -> float:
        """Calculate time management score based on due date adherence"""
        todos_with_due_dates = [t for t in todos if t.due_date and t.completed]
        
        if not todos_with_due_dates:
            return 50  # Neutral score if no due dates
        
        on_time_count = 0
        early_count = 0
        late_count = 0
        
        for todo in todos_with_due_dates:
            if todo.completed_date <= todo.due_date:
                if todo.completed_date.date() < todo.due_date.date():
                    early_count += 1
                else:
                    on_time_count += 1
            else:
                late_count += 1
        
        total = len(todos_with_due_dates)
        on_time_rate = (on_time_count + early_count) / total
        
        # Bonus for early completion
        early_bonus = (early_count / total) * 10
        
        return min(100, (on_time_rate * 100) + early_bonus)
    
    def _calculate_priority_adherence_score(self, todos: List[Todo]) -> float:
        """Calculate how well priorities are followed"""
        if not todos:
            return 0
        
        # Group by priority and check completion order
        priority_order = {
            Priority.CRITICAL: 4,
            Priority.HIGH: 3,
            Priority.MEDIUM: 2,
            Priority.LOW: 1
        }
        
        completed_todos = [t for t in todos if t.completed and t.completed_date]
        completed_todos.sort(key=lambda x: x.completed_date)
        
        adherence_score = 0
        total_comparisons = 0
        
        for i in range(len(completed_todos) - 1):
            current_priority = priority_order.get(completed_todos[i].priority, 2)
            next_priority = priority_order.get(completed_todos[i + 1].priority, 2)
            
            total_comparisons += 1
            if current_priority >= next_priority:  # Higher or equal priority completed first
                adherence_score += 1
        
        if total_comparisons == 0:
            return 50  # Neutral score
        
        return (adherence_score / total_comparisons) * 100
    
    def _calculate_average_completion_time(self, todos: List[Todo]) -> Optional[float]:
        """Calculate average time from creation to completion"""
        completion_times = []
        
        for todo in todos:
            if todo.completed and todo.completed_date and todo.created:
                duration = todo.completed_date - todo.created
                completion_times.append(duration.total_seconds() / 3600)  # Convert to hours
        
        if not completion_times:
            return None
        
        return statistics.mean(completion_times)
    
    def _calculate_estimation_accuracy(self, todos: List[Todo]) -> Optional[float]:
        """Calculate accuracy of time estimates"""
        accurate_estimates = 0
        total_estimates = 0
        
        for todo in todos:
            if todo.time_estimate and todo.time_spent:
                total_estimates += 1
                # Consider within 25% as accurate
                accuracy_threshold = 0.25
                estimated_minutes = todo.time_estimate
                actual_minutes = todo.time_spent
                
                if actual_minutes > 0:
                    error_ratio = abs(estimated_minutes - actual_minutes) / actual_minutes
                    if error_ratio <= accuracy_threshold:
                        accurate_estimates += 1
        
        if total_estimates == 0:
            return None
        
        return (accurate_estimates / total_estimates) * 100
    
    def _identify_patterns(self, todos: List[Todo]) -> List[TaskPattern]:
        """Identify productivity patterns in the data"""
        patterns = []
        
        # Peak productivity hours pattern
        peak_pattern = self._identify_peak_hours_pattern(todos)
        if peak_pattern:
            patterns.append(peak_pattern)
        
        # Project preference pattern
        project_pattern = self._identify_project_preference_pattern(todos)
        if project_pattern:
            patterns.append(project_pattern)
        
        # Priority bias pattern
        priority_pattern = self._identify_priority_bias_pattern(todos)
        if priority_pattern:
            patterns.append(priority_pattern)
        
        # Procrastination pattern
        procrastination_pattern = self._identify_procrastination_pattern(todos)
        if procrastination_pattern:
            patterns.append(procrastination_pattern)
        
        return patterns
    
    def _identify_peak_hours_pattern(self, todos: List[Todo]) -> Optional[TaskPattern]:
        """Identify peak productivity hours"""
        completed_todos = [t for t in todos if t.completed and t.completed_date]
        
        if len(completed_todos) < 5:  # Need sufficient data
            return None
        
        # Count completions by hour
        hour_counts = defaultdict(int)
        for todo in completed_todos:
            hour = todo.completed_date.hour
            hour_counts[hour] += 1
        
        if not hour_counts:
            return None
        
        # Find peak hours (above average)
        mean_completions = statistics.mean(hour_counts.values())
        peak_hours = [hour for hour, count in hour_counts.items() if count > mean_completions * 1.5]
        
        if len(peak_hours) >= 2:
            peak_hours.sort()
            if len(peak_hours) <= 3:
                hours_str = ", ".join(f"{h:02d}:00" for h in peak_hours)
            else:
                hours_str = f"{peak_hours[0]:02d}:00-{peak_hours[-1]:02d}:00"
            
            return TaskPattern(
                pattern_type="peak_hours",
                description=f"Peak productivity during {hours_str}",
                confidence=0.8,
                frequency=len(peak_hours),
                recommendation=f"Schedule important tasks during {hours_str} for maximum efficiency",
                data_points=list(hour_counts.items())
            )
        
        return None
    
    def _identify_project_preference_pattern(self, todos: List[Todo]) -> Optional[TaskPattern]:
        """Identify project completion preferences"""
        completed_todos = [t for t in todos if t.completed and t.project]
        
        if len(completed_todos) < 10:
            return None
        
        project_counts = Counter(t.project for t in completed_todos)
        total_completed = len(completed_todos)
        
        # Find dominant project (>40% of completions)
        for project, count in project_counts.most_common(3):
            percentage = (count / total_completed) * 100
            if percentage > 40:
                return TaskPattern(
                    pattern_type="project_preference",
                    description=f"Strong focus on '{project}' project ({percentage:.1f}% of completions)",
                    confidence=0.7,
                    frequency=count,
                    recommendation=f"Consider balancing attention across other projects",
                    data_points=list(project_counts.items())
                )
        
        return None
    
    def _identify_priority_bias_pattern(self, todos: List[Todo]) -> Optional[TaskPattern]:
        """Identify priority handling patterns"""
        completed_todos = [t for t in todos if t.completed]
        
        if len(completed_todos) < 10:
            return None
        
        priority_counts = Counter(t.priority for t in completed_todos)
        total_completed = len(completed_todos)
        
        # Check for low priority bias (completing too many low priority tasks)
        low_priority_percentage = (priority_counts.get(Priority.LOW, 0) / total_completed) * 100
        high_priority_percentage = (priority_counts.get(Priority.HIGH, 0) / total_completed) * 100
        
        if low_priority_percentage > 50:
            return TaskPattern(
                pattern_type="priority_bias",
                description=f"Tendency to complete low priority tasks ({low_priority_percentage:.1f}%)",
                confidence=0.8,
                frequency=priority_counts.get(Priority.LOW, 0),
                recommendation="Focus more on high-priority tasks to increase impact",
                data_points=[(p.value, c) for p, c in priority_counts.items()]
            )
        
        return None
    
    def _identify_procrastination_pattern(self, todos: List[Todo]) -> Optional[TaskPattern]:
        """Identify procrastination patterns"""
        overdue_completed = [
            t for t in todos 
            if t.completed and t.due_date and t.completed_date and t.completed_date > t.due_date
        ]
        
        todos_with_due_dates = [t for t in todos if t.due_date and t.completed]
        
        if len(todos_with_due_dates) < 5:
            return None
        
        overdue_percentage = (len(overdue_completed) / len(todos_with_due_dates)) * 100
        
        if overdue_percentage > 25:  # More than 25% completed late
            avg_delay = statistics.mean([
                (t.completed_date - t.due_date).days 
                for t in overdue_completed
                if t.completed_date > t.due_date
            ])
            
            return TaskPattern(
                pattern_type="procrastination",
                description=f"Frequent late completion ({overdue_percentage:.1f}% overdue)",
                confidence=0.9,
                frequency=len(overdue_completed),
                recommendation=f"Consider earlier due dates or break large tasks into smaller ones. Average delay: {avg_delay:.1f} days",
                data_points=[("overdue_count", len(overdue_completed)), ("total_due", len(todos_with_due_dates))]
            )
        
        return None
    
    def _generate_insights(self, todos: List[Todo], score: ProductivityScore, 
                          patterns: List[TaskPattern]) -> List[ProductivityInsight]:
        """Generate actionable productivity insights"""
        insights = []
        
        # Score-based insights
        if score.completion_rate >= 80:
            insights.append(ProductivityInsight(
                insight_type="strength",
                title="Excellent Task Completion",
                description=f"You have a {score.completion_rate:.1f}% completion rate, which is excellent!",
                impact_level="high",
                confidence=0.9,
                actionable_recommendation="Maintain this momentum and consider taking on more challenging projects",
                supporting_data={"completion_rate": score.completion_rate}
            ))
        elif score.completion_rate < 50:
            insights.append(ProductivityInsight(
                insight_type="weakness",
                title="Low Task Completion Rate",
                description=f"Your completion rate of {score.completion_rate:.1f}% suggests room for improvement",
                impact_level="high",
                confidence=0.9,
                actionable_recommendation="Consider breaking tasks into smaller, more manageable pieces or reviewing your task load",
                supporting_data={"completion_rate": score.completion_rate}
            ))
        
        # Velocity insights
        daily_velocity = score.tasks_completed / max(1, 7)  # Assume weekly analysis
        if daily_velocity < 1:
            insights.append(ProductivityInsight(
                insight_type="opportunity",
                title="Low Task Velocity",
                description=f"You're completing {daily_velocity:.1f} tasks per day on average",
                impact_level="medium",
                confidence=0.8,
                actionable_recommendation="Consider time-boxing techniques or identifying bottlenecks in your workflow",
                supporting_data={"daily_velocity": daily_velocity}
            ))
        
        # Focus insights
        if score.focus_score < 60:
            insights.append(ProductivityInsight(
                insight_type="weakness",
                title="Frequent Context Switching",
                description=f"Focus score of {score.focus_score:.1f} suggests frequent switching between projects/contexts",
                impact_level="medium",
                confidence=0.8,
                actionable_recommendation="Try batching similar tasks together or dedicating specific time blocks to single projects",
                supporting_data={"focus_score": score.focus_score}
            ))
        
        # Time management insights
        if score.time_management_score < 60:
            insights.append(ProductivityInsight(
                insight_type="weakness",
                title="Due Date Management",
                description=f"Time management score of {score.time_management_score:.1f} indicates difficulty meeting deadlines",
                impact_level="high",
                confidence=0.9,
                actionable_recommendation="Consider setting earlier personal deadlines and using time estimation techniques",
                supporting_data={"time_management_score": score.time_management_score}
            ))
        
        # Pattern-based insights
        for pattern in patterns:
            if pattern.pattern_type == "peak_hours":
                insights.append(ProductivityInsight(
                    insight_type="strength",
                    title="Identified Peak Productivity Hours",
                    description=pattern.description,
                    impact_level="medium",
                    confidence=pattern.confidence,
                    actionable_recommendation=pattern.recommendation,
                    supporting_data={"pattern": pattern.pattern_type, "data": pattern.data_points}
                ))
            elif pattern.pattern_type == "procrastination":
                insights.append(ProductivityInsight(
                    insight_type="weakness",
                    title="Procrastination Pattern Detected",
                    description=pattern.description,
                    impact_level="high",
                    confidence=pattern.confidence,
                    actionable_recommendation=pattern.recommendation,
                    supporting_data={"pattern": pattern.pattern_type, "frequency": pattern.frequency}
                ))
        
        return insights
    
    def _analyze_completion_by_day(self, todos: List[Todo]) -> Dict[str, int]:
        """Analyze completions by day of week"""
        day_counts = defaultdict(int)
        completed_todos = [t for t in todos if t.completed and t.completed_date]
        
        for todo in completed_todos:
            day_name = todo.completed_date.strftime('%A')
            day_counts[day_name] += 1
        
        return dict(day_counts)
    
    def _analyze_completion_by_priority(self, todos: List[Todo]) -> Dict[str, int]:
        """Analyze completions by priority"""
        priority_counts = defaultdict(int)
        completed_todos = [t for t in todos if t.completed]
        
        for todo in completed_todos:
            priority_counts[todo.priority.value] += 1
        
        return dict(priority_counts)
    
    def _analyze_completion_by_project(self, todos: List[Todo]) -> Dict[str, int]:
        """Analyze completions by project"""
        project_counts = defaultdict(int)
        completed_todos = [t for t in todos if t.completed and t.project]
        
        for todo in completed_todos:
            project_counts[todo.project] += 1
        
        return dict(project_counts)
    
    def _analyze_completion_by_hour(self, todos: List[Todo]) -> Dict[int, int]:
        """Analyze completions by hour of day"""
        hour_counts = defaultdict(int)
        completed_todos = [t for t in todos if t.completed and t.completed_date]
        
        for todo in completed_todos:
            hour = todo.completed_date.hour
            hour_counts[hour] += 1
        
        return dict(hour_counts)
    
    def _calculate_average_duration(self, todos: List[Todo]) -> Optional[float]:
        """Calculate average task duration"""
        durations = []
        completed_todos = [t for t in todos if t.completed and t.completed_date and t.created]
        
        for todo in completed_todos:
            duration = todo.completed_date - todo.created
            durations.append(duration.total_seconds() / 3600)  # Convert to hours
        
        if not durations:
            return None
        
        return statistics.mean(durations)
    
    def _analyze_productivity_hours(self, todos: List[Todo]) -> Tuple[List[int], List[int]]:
        """Analyze peak and least productive hours"""
        hour_counts = self._analyze_completion_by_hour(todos)
        
        if not hour_counts:
            return [], []
        
        # Sort by completion count
        sorted_hours = sorted(hour_counts.items(), key=lambda x: x[1], reverse=True)
        
        # Get top 3 and bottom 3 hours
        peak_hours = [hour for hour, _ in sorted_hours[:3]]
        least_hours = [hour for hour, _ in sorted_hours[-3:] if hour_counts[hour] > 0]
        
        return peak_hours, least_hours
    
    def _analyze_projects(self, todos: List[Todo]) -> Tuple[List[str], List[str]]:
        """Analyze most active and stalled projects"""
        project_activity = defaultdict(lambda: {"total": 0, "completed": 0, "recent": 0})
        cutoff_date = now_utc() - timedelta(days=7)
        
        for todo in todos:
            if todo.project:
                project_activity[todo.project]["total"] += 1
                if todo.completed:
                    project_activity[todo.project]["completed"] += 1
                if todo.modified and todo.modified >= cutoff_date:
                    project_activity[todo.project]["recent"] += 1
        
        # Sort by recent activity
        active_projects = sorted(
            project_activity.keys(),
            key=lambda p: project_activity[p]["recent"],
            reverse=True
        )[:5]
        
        # Identify stalled projects (no recent activity, low completion rate)
        stalled_projects = []
        for project, stats in project_activity.items():
            if stats["recent"] == 0 and stats["total"] >= 3:
                completion_rate = stats["completed"] / stats["total"] if stats["total"] > 0 else 0
                if completion_rate < 0.3:  # Less than 30% completion
                    stalled_projects.append(project)
        
        return active_projects, stalled_projects[:5]
    
    def get_cached_report(self, timeframe: AnalyticsTimeframe, 
                         end_date: Optional[datetime] = None) -> Optional[AnalyticsReport]:
        """Get cached analytics report if available"""
        if end_date is None:
            end_date = now_utc()
        
        start_date = self._calculate_start_date(timeframe, end_date)
        cache_key = f"{timeframe.value}_{start_date.date()}_{end_date.date()}"
        
        if cache_key in self.cache["reports"]:
            # TODO: Reconstruct AnalyticsReport from cached data
            return None  # For now, always generate fresh reports
        
        return None
    
    def _calculate_statistical_analysis(self, todos: List[Todo]) -> StatisticalAnalysis:
        """Calculate statistical measures over the provided todos.
        - mean_completion_time: average hours from creation to completion
        - completion_time_variance: variance of completion times (hours^2)
        - productivity_trend_slope: simple linear trend of daily completions over time
        """
        # Completion times in hours
        completion_hours: List[float] = []
        for t in todos:
            try:
                created_dt = getattr(t, 'created', None) or getattr(t, 'created_at', None)
                completed_dt = getattr(t, 'completed_date', None) or getattr(t, 'completed_at', None)
                if t.completed and created_dt and completed_dt:
                    completion_hours.append((completed_dt - created_dt).total_seconds() / 3600.0)
            except Exception:
                continue
        
        mean_ct: Optional[float] = statistics.mean(completion_hours) if completion_hours else None
        var_ct: float = statistics.pvariance(completion_hours) if len(completion_hours) > 1 else 0.0
        
        # Productivity trend: count completions per day and compute slope via simple linear regression
        daily_counts: Dict[datetime, int] = defaultdict(int)
        for t in todos:
            dt = getattr(t, 'completed_date', None) or getattr(t, 'completed_at', None)
            if t.completed and dt:
                day = dt.date()
                # Use datetime for indexing
                daily_counts[datetime.combine(day, datetime.min.time())] += 1
        
        slope = 0.0
        if len(daily_counts) > 1:
            # Sort by date
            items = sorted(daily_counts.items(), key=lambda x: x[0])
            xs = list(range(len(items)))
            ys = [count for _, count in items]
            # Compute slope = cov(x,y)/var(x)
            mean_x = statistics.mean(xs)
            mean_y = statistics.mean(ys)
            num = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
            den = sum((x - mean_x) ** 2 for x in xs) or 1.0
            slope = num / den
        
        return StatisticalAnalysis(
            mean_completion_time=mean_ct,
            completion_time_variance=var_ct,
            productivity_trend_slope=float(slope)
        )

    def get_productivity_trends(self, todos: List[Todo], 
                              periods: int = 4) -> List[ProductivityScore]:
        """Get productivity trends over multiple periods"""
        trends = []
        end_date = now_utc()
        
        for i in range(periods):
            period_end = end_date - timedelta(weeks=i*4)  # 4-week periods
            period_start = period_end - timedelta(weeks=4)
            
            period_todos = self._filter_todos_by_timeframe(todos, period_start, period_end)
            score = self._calculate_productivity_score(period_todos, period_start, period_end)
            trends.append(score)
        
        # Calculate trends
        if len(trends) > 1:
            for i in range(len(trends) - 1):
                current = trends[i]
                previous = trends[i + 1]
                
                current.completion_rate_trend = current.completion_rate - previous.completion_rate
                current.velocity_trend = current.velocity_score - previous.velocity_score
                current.consistency_trend = current.consistency_score - previous.consistency_score
        
        return trends