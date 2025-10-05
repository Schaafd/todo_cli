"""Project Analytics Dashboard for Todo CLI.

This module provides comprehensive project-level analytics including:
- Burndown and burnup charts
- Velocity tracking and forecasting
- Resource allocation analysis
- Project health scoring and risk assessment
- Timeline and milestone tracking
- Team productivity insights
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

from ..domain import Todo, Priority, TodoStatus
from .analytics import AnalyticsTimeframe, ProductivityAnalyzer, ProductivityScore
from .time_tracking import TimeTracker, TimeAnalyzer, TimeEntry
from ..config import get_config


class ProjectHealth(Enum):
    """Project health status"""
    EXCELLENT = "excellent"
    GOOD = "good"
    WARNING = "warning"
    CRITICAL = "critical"
    STALLED = "stalled"


class ProjectPhase(Enum):
    """Project lifecycle phases"""
    PLANNING = "planning"
    ACTIVE = "active"
    REVIEW = "review"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    ON_HOLD = "on_hold"


class RiskLevel(Enum):
    """Risk assessment levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class Milestone:
    """Project milestone"""
    id: str
    name: str
    target_date: datetime
    completed_date: Optional[datetime] = None
    description: str = ""
    todos: List[int] = field(default_factory=list)  # Todo IDs
    
    @property
    def is_completed(self) -> bool:
        return self.completed_date is not None
    
    @property
    def is_overdue(self) -> bool:
        return not self.is_completed and datetime.now() > self.target_date
    
    @property
    def days_until_due(self) -> int:
        if self.is_completed:
            return 0
        return (self.target_date.date() - datetime.now().date()).days
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'name': self.name,
            'target_date': self.target_date.isoformat(),
            'completed_date': self.completed_date.isoformat() if self.completed_date else None,
            'description': self.description,
            'todos': self.todos,
            'is_completed': self.is_completed,
            'is_overdue': self.is_overdue,
            'days_until_due': self.days_until_due
        }


@dataclass
class BurndownData:
    """Burndown chart data point"""
    date: datetime
    remaining_work: float  # hours or story points
    completed_work: float
    ideal_remaining: float  # ideal burndown line
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'date': self.date.date().isoformat(),
            'remaining_work': self.remaining_work,
            'completed_work': self.completed_work,
            'ideal_remaining': self.ideal_remaining
        }


@dataclass
class VelocityData:
    """Velocity tracking data"""
    period_start: datetime
    period_end: datetime
    tasks_completed: int
    story_points_completed: float
    hours_worked: float
    
    @property
    def tasks_per_day(self) -> float:
        days = max(1, (self.period_end - self.period_start).days)
        return self.tasks_completed / days
    
    @property
    def story_points_per_day(self) -> float:
        days = max(1, (self.period_end - self.period_start).days)
        return self.story_points_completed / days
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'period_start': self.period_start.date().isoformat(),
            'period_end': self.period_end.date().isoformat(),
            'tasks_completed': self.tasks_completed,
            'story_points_completed': self.story_points_completed,
            'hours_worked': self.hours_worked,
            'tasks_per_day': self.tasks_per_day,
            'story_points_per_day': self.story_points_per_day
        }


@dataclass
class ResourceAllocation:
    """Resource allocation analysis"""
    total_hours: float
    allocation_by_person: Dict[str, float]  # person -> hours
    allocation_by_role: Dict[str, float]    # role -> hours
    allocation_by_task_type: Dict[str, float]  # task type -> hours
    
    # Percentages
    person_percentages: Dict[str, float] = field(default_factory=dict)
    role_percentages: Dict[str, float] = field(default_factory=dict)
    task_type_percentages: Dict[str, float] = field(default_factory=dict)
    
    def __post_init__(self):
        """Calculate percentages"""
        if self.total_hours > 0:
            self.person_percentages = {
                k: (v / self.total_hours) * 100 
                for k, v in self.allocation_by_person.items()
            }
            self.role_percentages = {
                k: (v / self.total_hours) * 100 
                for k, v in self.allocation_by_role.items()
            }
            self.task_type_percentages = {
                k: (v / self.total_hours) * 100 
                for k, v in self.allocation_by_task_type.items()
            }
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'total_hours': self.total_hours,
            'allocation_by_person': self.allocation_by_person,
            'allocation_by_role': self.allocation_by_role,
            'allocation_by_task_type': self.allocation_by_task_type,
            'person_percentages': self.person_percentages,
            'role_percentages': self.role_percentages,
            'task_type_percentages': self.task_type_percentages
        }


@dataclass
class ProjectRisk:
    """Identified project risk"""
    risk_type: str  # "schedule", "resource", "quality", "scope"
    level: RiskLevel
    title: str
    description: str
    impact: str  # "high", "medium", "low"
    probability: str  # "high", "medium", "low"
    mitigation: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'risk_type': self.risk_type,
            'level': self.level.value,
            'title': self.title,
            'description': self.description,
            'impact': self.impact,
            'probability': self.probability,
            'mitigation': self.mitigation
        }


@dataclass
class ProjectHealthScore:
    """Comprehensive project health assessment"""
    overall_health: ProjectHealth
    overall_score: float  # 0-100
    
    # Component scores
    schedule_score: float    # On-time delivery
    quality_score: float     # Task completion quality
    resource_score: float    # Resource utilization
    velocity_score: float    # Productivity trends
    scope_score: float       # Scope management
    
    # Metrics
    completion_percentage: float
    on_time_percentage: float
    budget_utilization: float
    team_satisfaction: Optional[float] = None
    
    # Trends
    health_trend: Optional[str] = None  # "improving", "declining", "stable"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'overall_health': self.overall_health.value,
            'overall_score': self.overall_score,
            'schedule_score': self.schedule_score,
            'quality_score': self.quality_score,
            'resource_score': self.resource_score,
            'velocity_score': self.velocity_score,
            'scope_score': self.scope_score,
            'completion_percentage': self.completion_percentage,
            'on_time_percentage': self.on_time_percentage,
            'budget_utilization': self.budget_utilization,
            'team_satisfaction': self.team_satisfaction,
            'health_trend': self.health_trend
        }


@dataclass
class ProjectForecast:
    """Project completion forecasting"""
    estimated_completion_date: datetime
    confidence_level: float  # 0-1
    remaining_work_estimate: float  # hours
    current_velocity: float
    
    # Scenarios
    optimistic_date: datetime
    pessimistic_date: datetime
    most_likely_date: datetime
    
    # Risk factors
    schedule_risk: RiskLevel = RiskLevel.LOW
    resource_risk: RiskLevel = RiskLevel.LOW
    scope_risk: RiskLevel = RiskLevel.LOW
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'estimated_completion_date': self.estimated_completion_date.date().isoformat(),
            'confidence_level': self.confidence_level,
            'remaining_work_estimate': self.remaining_work_estimate,
            'current_velocity': self.current_velocity,
            'optimistic_date': self.optimistic_date.date().isoformat(),
            'pessimistic_date': self.pessimistic_date.date().isoformat(),
            'most_likely_date': self.most_likely_date.date().isoformat(),
            'schedule_risk': self.schedule_risk.value,
            'resource_risk': self.resource_risk.value,
            'scope_risk': self.scope_risk.value
        }


@dataclass
class ProjectDashboard:
    """Comprehensive project analytics dashboard"""
    project_name: str
    timeframe: AnalyticsTimeframe
    start_date: datetime
    end_date: datetime
    
    # Core metrics
    health_score: ProjectHealthScore
    burndown_chart: List[BurndownData]
    velocity_data: List[VelocityData]
    resource_allocation: ResourceAllocation
    forecast: ProjectForecast
    
    # Additional analysis
    milestones: List[Milestone] = field(default_factory=list)
    risks: List[ProjectRisk] = field(default_factory=list)
    
    # Summary stats
    total_tasks: int = 0
    completed_tasks: int = 0
    overdue_tasks: int = 0
    blocked_tasks: int = 0
    
    # Team metrics
    active_contributors: int = 0
    average_task_completion_time: Optional[float] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'project_name': self.project_name,
            'timeframe': self.timeframe.value,
            'start_date': self.start_date.isoformat(),
            'end_date': self.end_date.isoformat(),
            'health_score': self.health_score.to_dict(),
            'burndown_chart': [point.to_dict() for point in self.burndown_chart],
            'velocity_data': [v.to_dict() for v in self.velocity_data],
            'resource_allocation': self.resource_allocation.to_dict(),
            'forecast': self.forecast.to_dict(),
            'milestones': [m.to_dict() for m in self.milestones],
            'risks': [r.to_dict() for r in self.risks],
            'total_tasks': self.total_tasks,
            'completed_tasks': self.completed_tasks,
            'overdue_tasks': self.overdue_tasks,
            'blocked_tasks': self.blocked_tasks,
            'active_contributors': self.active_contributors,
            'average_task_completion_time': self.average_task_completion_time
        }


class ProjectAnalyzer:
    """Advanced project analytics engine"""
    
    def __init__(self, time_tracker: Optional[TimeTracker] = None):
        self.config = get_config()
        self.time_tracker = time_tracker
        self.projects_dir = Path(self.config.data_dir) / "project_analytics"
        self.projects_dir.mkdir(parents=True, exist_ok=True)
    
    def generate_project_dashboard(self, project_name: str, todos: List[Todo],
                                 timeframe: AnalyticsTimeframe = AnalyticsTimeframe.MONTHLY,
                                 end_date: Optional[datetime] = None) -> ProjectDashboard:
        """Generate comprehensive project analytics dashboard"""
        
        if end_date is None:
            end_date = datetime.now()
        
        start_date = self._calculate_start_date(timeframe, end_date)
        
        # Filter todos for this project and timeframe
        project_todos = self._filter_project_todos(todos, project_name, start_date, end_date)
        
        # Get time entries if available
        time_entries = []
        if self.time_tracker:
            all_entries = self.time_tracker.get_entries_for_timeframe(timeframe, end_date)
            time_entries = [e for e in all_entries if e.project == project_name]
        
        # Generate components
        health_score = self._calculate_project_health(project_todos, time_entries)
        burndown_chart = self._generate_burndown_chart(project_todos, start_date, end_date)
        velocity_data = self._calculate_velocity_data(project_todos, timeframe, end_date)
        resource_allocation = self._analyze_resource_allocation(project_todos, time_entries)
        forecast = self._generate_project_forecast(project_todos, velocity_data)
        milestones = self._identify_milestones(project_todos)
        risks = self._assess_project_risks(project_todos, health_score, velocity_data)
        
        # Calculate summary stats
        total_tasks = len(project_todos)
        completed_tasks = len([t for t in project_todos if t.completed])
        overdue_tasks = len([t for t in project_todos if t.is_overdue() and not t.completed])
        blocked_tasks = len([t for t in project_todos if t.status == TodoStatus.BLOCKED])
        
        active_contributors = len(set(
            person for todo in project_todos 
            for person in (todo.assignees or [])
        ))
        
        # Average completion time
        completed_with_dates = [
            t for t in project_todos 
            if t.completed and t.completed_date and t.created
        ]
        avg_completion_time = None
        if completed_with_dates:
            completion_times = [
                (t.completed_date - t.created).total_seconds() / 3600
                for t in completed_with_dates
            ]
            avg_completion_time = statistics.mean(completion_times)
        
        return ProjectDashboard(
            project_name=project_name,
            timeframe=timeframe,
            start_date=start_date,
            end_date=end_date,
            health_score=health_score,
            burndown_chart=burndown_chart,
            velocity_data=velocity_data,
            resource_allocation=resource_allocation,
            forecast=forecast,
            milestones=milestones,
            risks=risks,
            total_tasks=total_tasks,
            completed_tasks=completed_tasks,
            overdue_tasks=overdue_tasks,
            blocked_tasks=blocked_tasks,
            active_contributors=active_contributors,
            average_task_completion_time=avg_completion_time
        )
    
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
            base = datetime(2020, 1, 1)
            try:
                from .utils.datetime import ensure_aware
                return ensure_aware(base, tz=end_date.tzinfo)
            except Exception:
                return base
    
    def _filter_project_todos(self, todos: List[Todo], project_name: str, 
                            start_date: datetime, end_date: datetime) -> List[Todo]:
        """Filter todos for specific project and timeframe"""
        return [
            todo for todo in todos
            if todo.project == project_name and (
                (todo.created and start_date <= todo.created <= end_date) or
                (todo.completed_date and start_date <= todo.completed_date <= end_date) or
                (todo.due_date and start_date <= todo.due_date <= end_date) or
                (todo.modified and start_date <= todo.modified <= end_date)
            )
        ]
    
    def _calculate_project_health(self, todos: List[Todo], time_entries: List[TimeEntry]) -> ProjectHealthScore:
        """Calculate comprehensive project health score"""
        
        if not todos:
            return ProjectHealthScore(
                overall_health=ProjectHealth.STALLED,
                overall_score=0,
                schedule_score=0,
                quality_score=0,
                resource_score=0,
                velocity_score=0,
                scope_score=0,
                completion_percentage=0,
                on_time_percentage=0,
                budget_utilization=0
            )
        
        # Schedule Score (based on due date adherence)
        todos_with_due_dates = [t for t in todos if t.due_date]
        if todos_with_due_dates:
            on_time_count = sum(1 for t in todos_with_due_dates 
                              if t.completed and t.completed_date and t.completed_date <= t.due_date)
            on_time_percentage = (on_time_count / len(todos_with_due_dates)) * 100
            schedule_score = on_time_percentage
        else:
            on_time_percentage = 100
            schedule_score = 50  # Neutral if no due dates
        
        # Quality Score (based on task completion without reopening)
        completed_todos = [t for t in todos if t.completed]
        # Simplified quality metric - in reality, this would consider reopened tasks, testing, etc.
        quality_score = 85 if completed_todos else 50
        
        # Resource Score (based on time tracking efficiency)
        resource_score = 75  # Placeholder - would use time tracking data
        if time_entries:
            # Calculate based on productive vs. non-productive time
            productive_entries = [e for e in time_entries if e.focus_level and e.focus_level >= 7]
            if time_entries:
                productive_ratio = len(productive_entries) / len(time_entries)
                resource_score = productive_ratio * 100
        
        # Velocity Score (based on completion trends)
        total_todos = len(todos)
        completed_count = len(completed_todos)
        completion_percentage = (completed_count / total_todos) * 100 if total_todos > 0 else 0
        
        # Simple velocity calculation based on completion rate
        velocity_score = min(100, completion_percentage * 1.2)
        
        # Scope Score (based on scope creep indicators)
        # For now, assume stable scope
        scope_score = 80
        
        # Overall Score (weighted average)
        overall_score = (
            schedule_score * 0.30 +
            quality_score * 0.25 +
            resource_score * 0.20 +
            velocity_score * 0.15 +
            scope_score * 0.10
        )
        
        # Determine overall health
        if overall_score >= 85:
            overall_health = ProjectHealth.EXCELLENT
        elif overall_score >= 70:
            overall_health = ProjectHealth.GOOD
        elif overall_score >= 50:
            overall_health = ProjectHealth.WARNING
        elif overall_score >= 30:
            overall_health = ProjectHealth.CRITICAL
        else:
            overall_health = ProjectHealth.STALLED
        
        return ProjectHealthScore(
            overall_health=overall_health,
            overall_score=overall_score,
            schedule_score=schedule_score,
            quality_score=quality_score,
            resource_score=resource_score,
            velocity_score=velocity_score,
            scope_score=scope_score,
            completion_percentage=completion_percentage,
            on_time_percentage=on_time_percentage,
            budget_utilization=75  # Placeholder
        )
    
    def _generate_burndown_chart(self, todos: List[Todo], start_date: datetime, end_date: datetime) -> List[BurndownData]:
        """Generate burndown chart data"""
        burndown_points = []
        
        # Calculate total work (using time estimates or task count)
        total_work = 0
        for todo in todos:
            if todo.time_estimate:
                total_work += todo.time_estimate / 60  # Convert to hours
            else:
                total_work += 1  # Default 1 hour per task
        
        if total_work == 0:
            return []
        
        # Generate daily data points
        current_date = start_date
        days_total = (end_date - start_date).days
        
        while current_date <= end_date:
            # Calculate remaining work at this date
            completed_at_date = [
                todo for todo in todos
                if todo.completed and todo.completed_date and todo.completed_date.date() <= current_date.date()
            ]
            
            completed_work = 0
            for todo in completed_at_date:
                if todo.time_estimate:
                    completed_work += todo.time_estimate / 60
                else:
                    completed_work += 1
            
            remaining_work = total_work - completed_work
            
            # Calculate ideal remaining work
            days_elapsed = (current_date - start_date).days
            if days_total > 0:
                ideal_remaining = total_work * (1 - days_elapsed / days_total)
            else:
                ideal_remaining = 0
            
            burndown_points.append(BurndownData(
                date=current_date,
                remaining_work=remaining_work,
                completed_work=completed_work,
                ideal_remaining=max(0, ideal_remaining)
            ))
            
            current_date += timedelta(days=1)
        
        return burndown_points
    
    def _calculate_velocity_data(self, todos: List[Todo], timeframe: AnalyticsTimeframe, 
                               end_date: datetime, periods: int = 6) -> List[VelocityData]:
        """Calculate velocity data for multiple periods"""
        velocity_data = []
        
        # Calculate period length
        if timeframe == AnalyticsTimeframe.WEEKLY:
            period_length = timedelta(weeks=1)
        elif timeframe == AnalyticsTimeframe.MONTHLY:
            period_length = timedelta(days=30)
        else:
            period_length = timedelta(weeks=2)  # Default to bi-weekly
        
        for i in range(periods):
            period_end = end_date - timedelta(days=i * period_length.days)
            period_start = period_end - period_length
            
            # Get todos completed in this period
            period_todos = [
                todo for todo in todos
                if todo.completed and todo.completed_date and 
                period_start <= todo.completed_date <= period_end
            ]
            
            tasks_completed = len(period_todos)
            
            # Calculate story points (use time estimates or default values)
            story_points = 0
            hours_worked = 0
            
            for todo in period_todos:
                if todo.time_estimate:
                    hours_worked += todo.time_estimate / 60
                    story_points += todo.time_estimate / 60  # Use hours as story points
                else:
                    hours_worked += 1  # Default 1 hour
                    story_points += 1   # Default 1 story point
            
            velocity_data.append(VelocityData(
                period_start=period_start,
                period_end=period_end,
                tasks_completed=tasks_completed,
                story_points_completed=story_points,
                hours_worked=hours_worked
            ))
        
        return list(reversed(velocity_data))  # Return chronologically
    
    def _analyze_resource_allocation(self, todos: List[Todo], time_entries: List[TimeEntry]) -> ResourceAllocation:
        """Analyze resource allocation"""
        
        # Calculate from time entries if available
        if time_entries:
            total_hours = sum(e.get_duration_hours() for e in time_entries if e.end_time)
            
            # By person (from assignees in time entries or todos)
            person_allocation = defaultdict(float)
            for entry in time_entries:
                if entry.end_time:
                    # For now, distribute equally among assignees
                    # In real implementation, would track who actually worked
                    person_allocation["unassigned"] += entry.get_duration_hours()
            
            # By role - placeholder
            role_allocation = {"developer": total_hours}
            
            # By task type
            type_allocation = defaultdict(float)
            for entry in time_entries:
                if entry.end_time:
                    type_allocation[entry.tracking_type.value] += entry.get_duration_hours()
            
        else:
            # Fallback to todo analysis
            total_hours = 0
            person_allocation = defaultdict(float)
            
            for todo in todos:
                hours = (todo.time_estimate / 60) if todo.time_estimate else 1
                total_hours += hours
                
                if todo.assignees:
                    hours_per_person = hours / len(todo.assignees)
                    for assignee in todo.assignees:
                        person_allocation[assignee] += hours_per_person
                else:
                    person_allocation["unassigned"] += hours
            
            role_allocation = {"developer": total_hours}
            type_allocation = {"task_work": total_hours}
        
        return ResourceAllocation(
            total_hours=total_hours,
            allocation_by_person=dict(person_allocation),
            allocation_by_role=role_allocation,
            allocation_by_task_type=dict(type_allocation)
        )
    
    def _generate_project_forecast(self, todos: List[Todo], velocity_data: List[VelocityData]) -> ProjectForecast:
        """Generate project completion forecast"""
        
        # Calculate remaining work
        remaining_todos = [t for t in todos if not t.completed]
        remaining_work = 0
        for todo in remaining_todos:
            if todo.time_estimate:
                remaining_work += todo.time_estimate / 60
            else:
                remaining_work += 1
        
        # Calculate current velocity from recent periods
        if velocity_data:
            recent_velocity_data = velocity_data[-3:]  # Last 3 periods
            avg_velocity = statistics.mean([v.story_points_per_day for v in recent_velocity_data])
        else:
            avg_velocity = 1  # Default
        
        if avg_velocity <= 0:
            avg_velocity = 0.1  # Minimum to avoid division by zero
        
        # Estimate completion date
        days_remaining = remaining_work / avg_velocity
        estimated_completion = datetime.now() + timedelta(days=days_remaining)
        
        # Calculate scenarios
        optimistic_velocity = avg_velocity * 1.5
        pessimistic_velocity = avg_velocity * 0.7
        
        optimistic_date = datetime.now() + timedelta(days=remaining_work / optimistic_velocity)
        pessimistic_date = datetime.now() + timedelta(days=remaining_work / pessimistic_velocity)
        most_likely_date = estimated_completion
        
        # Assess confidence based on velocity consistency
        if velocity_data and len(velocity_data) >= 2:
            velocities = [v.story_points_per_day for v in velocity_data[-4:]]
            if len(velocities) > 1:
                velocity_std = statistics.stdev(velocities)
                velocity_mean = statistics.mean(velocities)
                cv = velocity_std / velocity_mean if velocity_mean > 0 else 1
                confidence = max(0.3, 1 - cv)  # Lower CV = higher confidence
            else:
                confidence = 0.7
        else:
            confidence = 0.5  # Low confidence without historical data
        
        return ProjectForecast(
            estimated_completion_date=estimated_completion,
            confidence_level=confidence,
            remaining_work_estimate=remaining_work,
            current_velocity=avg_velocity,
            optimistic_date=optimistic_date,
            pessimistic_date=pessimistic_date,
            most_likely_date=most_likely_date
        )
    
    def _identify_milestones(self, todos: List[Todo]) -> List[Milestone]:
        """Identify project milestones from todos"""
        milestones = []
        
        # Group todos by due dates to identify potential milestones
        due_date_groups = defaultdict(list)
        for todo in todos:
            if todo.due_date:
                # Group by week
                week_start = todo.due_date - timedelta(days=todo.due_date.weekday())
                due_date_groups[week_start].append(todo)
        
        # Create milestones for significant due date clusters
        milestone_id = 1
        for week_start, week_todos in due_date_groups.items():
            if len(week_todos) >= 3:  # Significant cluster
                completed_count = sum(1 for t in week_todos if t.completed)
                is_completed = completed_count == len(week_todos)
                
                milestone = Milestone(
                    id=f"milestone_{milestone_id}",
                    name=f"Week of {week_start.strftime('%B %d')}",
                    target_date=week_start + timedelta(days=6),  # End of week
                    completed_date=max(
                        (t.completed_date for t in week_todos if t.completed_date), 
                        default=None
                    ) if is_completed else None,
                    description=f"{len(week_todos)} tasks due this week",
                    todos=[t.id for t in week_todos]
                )
                milestones.append(milestone)
                milestone_id += 1
        
        return milestones
    
    def _assess_project_risks(self, todos: List[Todo], health: ProjectHealthScore, 
                            velocity_data: List[VelocityData]) -> List[ProjectRisk]:
        """Assess project risks"""
        risks = []
        
        # Schedule risk
        if health.schedule_score < 60:
            risks.append(ProjectRisk(
                risk_type="schedule",
                level=RiskLevel.HIGH if health.schedule_score < 30 else RiskLevel.MEDIUM,
                title="Schedule Slippage Risk",
                description=f"On-time delivery rate is {health.schedule_score:.1f}%",
                impact="high",
                probability="high" if health.schedule_score < 30 else "medium",
                mitigation="Consider adjusting scope or adding resources"
            ))
        
        # Resource risk
        overdue_todos = [t for t in todos if t.is_overdue() and not t.completed]
        if len(overdue_todos) > len(todos) * 0.3:  # More than 30% overdue
            risks.append(ProjectRisk(
                risk_type="resource",
                level=RiskLevel.HIGH,
                title="Resource Capacity Risk",
                description=f"{len(overdue_todos)} tasks are overdue",
                impact="high",
                probability="high",
                mitigation="Review resource allocation and priorities"
            ))
        
        # Quality risk
        if health.quality_score < 70:
            risks.append(ProjectRisk(
                risk_type="quality",
                level=RiskLevel.MEDIUM,
                title="Quality Risk",
                description="Quality metrics below expected levels",
                impact="medium",
                probability="medium",
                mitigation="Implement additional quality controls"
            ))
        
        # Velocity risk
        if velocity_data and len(velocity_data) >= 2:
            recent_velocities = [v.tasks_per_day for v in velocity_data[-3:]]
            if len(recent_velocities) > 1:
                velocity_trend = (recent_velocities[-1] - recent_velocities[0]) / len(recent_velocities)
                if velocity_trend < -0.2:  # Declining velocity
                    risks.append(ProjectRisk(
                        risk_type="resource",
                        level=RiskLevel.MEDIUM,
                        title="Declining Velocity",
                        description="Team velocity is declining",
                        impact="medium",
                        probability="high",
                        mitigation="Investigate productivity blockers"
                    ))
        
        return risks
    
    def get_project_insights(self, dashboard: ProjectDashboard) -> List[str]:
        """Generate actionable project insights"""
        insights = []
        
        # Health insights
        if dashboard.health_score.overall_health == ProjectHealth.EXCELLENT:
            insights.append("🎉 Project is in excellent health - maintain momentum!")
        elif dashboard.health_score.overall_health == ProjectHealth.CRITICAL:
            insights.append("🚨 Project health is critical - immediate intervention needed")
        elif dashboard.health_score.overall_health == ProjectHealth.STALLED:
            insights.append("⚠️ Project appears stalled - review and re-energize")
        
        # Velocity insights
        if len(dashboard.velocity_data) >= 2:
            recent_velocity = dashboard.velocity_data[-1].tasks_per_day
            previous_velocity = dashboard.velocity_data[-2].tasks_per_day
            
            if recent_velocity > previous_velocity * 1.2:
                insights.append("📈 Velocity is increasing - great progress!")
            elif recent_velocity < previous_velocity * 0.8:
                insights.append("📉 Velocity is declining - investigate blockers")
        
        # Completion insights
        completion_rate = (dashboard.completed_tasks / dashboard.total_tasks * 100) if dashboard.total_tasks > 0 else 0
        if completion_rate > 80:
            insights.append("🎯 High completion rate - project nearing finish line")
        elif completion_rate < 30:
            insights.append("🚀 Early stage project - establish strong foundations")
        
        # Risk insights
        high_risks = [r for r in dashboard.risks if r.level == RiskLevel.HIGH]
        if high_risks:
            insights.append(f"⚠️ {len(high_risks)} high-priority risks need attention")
        
        # Resource insights
        if dashboard.active_contributors == 1:
            insights.append("👤 Single contributor - consider knowledge sharing")
        elif dashboard.active_contributors > 10:
            insights.append("👥 Large team - ensure good coordination")
        
        return insights
    
    def export_project_data(self, dashboard: ProjectDashboard, format_type: str = "json") -> str:
        """Export project analytics data"""
        if format_type == "json":
            return json.dumps(dashboard.to_dict(), indent=2)
        elif format_type == "csv":
            return self._export_to_csv(dashboard)
        else:
            raise ValueError(f"Unsupported format: {format_type}")
    
    def _export_to_csv(self, dashboard: ProjectDashboard) -> str:
        """Export dashboard to CSV format"""
        import csv
        import io
        
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Project summary
        writer.writerow(["Project Analytics Summary"])
        writer.writerow(["Project", dashboard.project_name])
        writer.writerow(["Health Score", f"{dashboard.health_score.overall_score:.1f}"])
        writer.writerow(["Completion", f"{dashboard.health_score.completion_percentage:.1f}%"])
        writer.writerow(["Total Tasks", dashboard.total_tasks])
        writer.writerow(["Completed Tasks", dashboard.completed_tasks])
        writer.writerow([])
        
        # Velocity data
        writer.writerow(["Velocity Data"])
        writer.writerow(["Period Start", "Period End", "Tasks Completed", "Tasks/Day"])
        for v in dashboard.velocity_data:
            writer.writerow([
                v.period_start.date().isoformat(),
                v.period_end.date().isoformat(),
                v.tasks_completed,
                f"{v.tasks_per_day:.2f}"
            ])
        
        return output.getvalue()