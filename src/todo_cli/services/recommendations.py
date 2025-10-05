"""
Smart Task Recommendation Engine for Todo CLI

This module provides intelligent task recommendations based on user patterns,
context, priority, and various other factors.
"""

import math
from collections import defaultdict, Counter
from dataclasses import dataclass
from datetime import datetime, timedelta, date
from typing import List, Dict, Tuple, Optional, Any

from ..domain import Todo, Priority, TodoStatus


@dataclass
class Recommendation:
    """A task recommendation with scoring"""
    todo: Todo
    score: float
    reasons: List[str]
    category: str  # 'urgent', 'contextual', 'energy-match', 'pattern-based'


class TaskRecommendationEngine:
    """Analyzes user patterns and suggests relevant tasks"""
    
    def __init__(self):
        self.context_patterns: Dict[str, List[str]] = {}
        self.time_patterns: Dict[int, List[str]] = {}  # hour -> contexts
        self.completion_patterns: Dict[str, float] = {}  # context -> avg completion time
    
    def analyze_patterns(self, todos: List[Todo]):
        """Analyze user patterns from historical data"""
        self._analyze_context_patterns(todos)
        self._analyze_time_patterns(todos)
        self._analyze_completion_patterns(todos)
    
    def get_recommendations(
        self, 
        todos: List[Todo], 
        current_context: Optional[str] = None,
        current_energy: str = "medium",
        available_time: Optional[int] = None,  # minutes
        limit: int = 10
    ) -> List[Recommendation]:
        """Get personalized task recommendations"""
        
        # Filter to active tasks only
        active_todos = [t for t in todos if t.is_active()]
        
        if not active_todos:
            return []
        
        # Analyze patterns first
        self.analyze_patterns(todos)
        
        # Score all tasks
        recommendations = []
        for todo in active_todos:
            score, reasons = self._score_task(
                todo, 
                todos, 
                current_context, 
                current_energy, 
                available_time
            )
            
            category = self._categorize_recommendation(todo, reasons)
            recommendations.append(Recommendation(todo, score, reasons, category))
        
        # Sort by score descending
        recommendations.sort(key=lambda r: r.score, reverse=True)
        
        return recommendations[:limit]
    
    def _score_task(
        self, 
        todo: Todo, 
        all_todos: List[Todo],
        current_context: Optional[str],
        current_energy: str,
        available_time: Optional[int]
    ) -> Tuple[float, List[str]]:
        """Score a task based on multiple factors"""
        
        score = 0.0
        reasons = []
        
        # Base priority scoring
        priority_scores = {
            Priority.CRITICAL: 100,
            Priority.HIGH: 75,
            Priority.MEDIUM: 50,
            Priority.LOW: 25
        }
        priority_score = priority_scores.get(todo.priority, 50)
        score += priority_score
        
        if todo.priority in [Priority.CRITICAL, Priority.HIGH]:
            reasons.append(f"{todo.priority.value} priority")
        
        # Due date urgency
        if todo.due_date:
            days_until_due = (todo.due_date.date() - date.today()).days
            if days_until_due < 0:
                score += 50  # Overdue boost
                reasons.append("overdue")
            elif days_until_due == 0:
                score += 40  # Due today
                reasons.append("due today")
            elif days_until_due == 1:
                score += 30  # Due tomorrow
                reasons.append("due tomorrow")
            elif days_until_due <= 7:
                score += 20  # Due this week
                reasons.append("due this week")
        
        # Pinned tasks get boost
        if todo.pinned:
            score += 25
            reasons.append("pinned")
        
        # Context matching
        if current_context and current_context in todo.context:
            score += 20
            reasons.append(f"matches current context ({current_context})")
        
        # Energy level matching
        energy_match = self._calculate_energy_match(todo.energy_level, current_energy)
        if energy_match > 0.7:
            score += 15
            reasons.append(f"energy level match ({todo.energy_level})")
        
        # Time availability matching
        if available_time and todo.time_estimate:
            if todo.time_estimate <= available_time:
                score += 10
                reasons.append(f"fits available time ({todo.time_estimate}m)")
            else:
                score -= 10  # Penalize if too long
        
        # Quick wins (short tasks)
        if todo.effort in ["quick", "small"] or (todo.time_estimate and todo.time_estimate <= 15):
            score += 8
            reasons.append("quick win")
        
        # Pattern-based scoring
        pattern_score = self._calculate_pattern_score(todo)
        if pattern_score > 0:
            score += pattern_score
            reasons.append("matches your patterns")
        
        # Dependency scoring - boost if dependencies are complete
        dependency_boost = self._calculate_dependency_score(todo, all_todos)
        if dependency_boost > 0:
            score += dependency_boost
            reasons.append("dependencies ready")
        
        # Staleness penalty - older tasks get slight boost
        if todo.created:
            days_old = (datetime.now() - todo.created).days
            if days_old > 7:
                score += min(days_old * 0.5, 10)  # Cap at 10 points
                reasons.append("been waiting a while")
        
        # Project momentum - boost if other tasks in same project recently completed
        project_momentum = self._calculate_project_momentum(todo, all_todos)
        if project_momentum > 0:
            score += project_momentum
            reasons.append("project momentum")
        
        return score, reasons
    
    def _categorize_recommendation(self, todo: Todo, reasons: List[str]) -> str:
        """Categorize the recommendation type"""
        if "overdue" in reasons or "due today" in reasons:
            return "urgent"
        elif any("context" in reason for reason in reasons):
            return "contextual"
        elif "energy level match" in reasons:
            return "energy-match"
        elif "matches your patterns" in reasons:
            return "pattern-based"
        else:
            return "general"
    
    def _calculate_energy_match(self, task_energy: str, current_energy: str) -> float:
        """Calculate how well task energy requirements match current energy"""
        energy_levels = {"low": 1, "medium": 2, "high": 3}
        
        task_level = energy_levels.get(task_energy, 2)
        current_level = energy_levels.get(current_energy, 2)
        
        # Perfect match = 1.0, adjacent levels = 0.7, opposite = 0.3
        diff = abs(task_level - current_level)
        if diff == 0:
            return 1.0
        elif diff == 1:
            return 0.7
        else:
            return 0.3
    
    def _calculate_pattern_score(self, todo: Todo) -> float:
        """Score based on learned user patterns"""
        score = 0.0
        
        # Context patterns
        for context in todo.context:
            if context in self.context_patterns:
                related_contexts = self.context_patterns[context]
                if set(todo.context) & set(related_contexts):
                    score += 3
        
        # Time-based patterns
        current_hour = datetime.now().hour
        if current_hour in self.time_patterns:
            common_contexts = self.time_patterns[current_hour]
            if set(todo.context) & set(common_contexts):
                score += 5
        
        return score
    
    def _calculate_dependency_score(self, todo: Todo, all_todos: List[Todo]) -> float:
        """Score based on dependency completion"""
        if not todo.depends_on:
            return 0
        
        todo_map = {t.id: t for t in all_todos}
        completed_deps = 0
        total_deps = len(todo.depends_on)
        
        for dep_id in todo.depends_on:
            if dep_id in todo_map and todo_map[dep_id].completed:
                completed_deps += 1
        
        if completed_deps == total_deps:
            return 15  # All dependencies complete
        elif completed_deps > 0:
            return 5   # Some dependencies complete
        else:
            return -5  # No dependencies complete
    
    def _calculate_project_momentum(self, todo: Todo, all_todos: List[Todo]) -> float:
        """Score based on recent activity in the same project"""
        if not todo.project:
            return 0
        
        # Look for recently completed tasks in same project
        week_ago = datetime.now() - timedelta(days=7)
        recent_completions = [
            t for t in all_todos 
            if t.project == todo.project 
            and t.completed 
            and t.completed_date 
            and t.completed_date > week_ago
        ]
        
        return min(len(recent_completions) * 2, 8)  # Cap at 8 points
    
    def _analyze_context_patterns(self, todos: List[Todo]):
        """Learn which contexts are commonly used together"""
        context_pairs = defaultdict(list)
        
        for todo in todos:
            if len(todo.context) > 1:
                for i, context1 in enumerate(todo.context):
                    for context2 in todo.context[i+1:]:
                        context_pairs[context1].append(context2)
                        context_pairs[context2].append(context1)
        
        # Convert to most common associations
        self.context_patterns = {
            context: [item for item, _ in Counter(contexts).most_common(3)]
            for context, contexts in context_pairs.items()
        }
    
    def _analyze_time_patterns(self, todos: List[Todo]):
        """Learn which contexts are worked on at what times"""
        completed_todos = [t for t in todos if t.completed and t.completed_date]
        
        hour_contexts = defaultdict(list)
        for todo in completed_todos:
            hour = todo.completed_date.hour
            for context in todo.context:
                hour_contexts[hour].append(context)
        
        # Get most common contexts per hour
        self.time_patterns = {
            hour: [item for item, _ in Counter(contexts).most_common(3)]
            for hour, contexts in hour_contexts.items()
        }
    
    def _analyze_completion_patterns(self, todos: List[Todo]):
        """Learn average completion times by context"""
        completed_todos = [t for t in todos if t.completed and t.time_estimate]
        
        context_times = defaultdict(list)
        for todo in completed_todos:
            for context in todo.context:
                if todo.time_estimate:
                    context_times[context].append(todo.time_estimate)
        
        # Calculate averages
        self.completion_patterns = {
            context: sum(times) / len(times)
            for context, times in context_times.items()
            if times
        }


def get_context_suggestions(todos: List[Todo], current_time: Optional[datetime] = None) -> List[str]:
    """Suggest contexts based on current time and patterns"""
    if not current_time:
        current_time = datetime.now()
    
    hour = current_time.hour
    
    # Time-based context suggestions
    time_contexts = {
        (6, 9): ["morning", "planning", "email"],
        (9, 12): ["focus", "development", "meetings"], 
        (12, 14): ["lunch", "quick-tasks", "admin"],
        (14, 17): ["meetings", "collaboration", "review"],
        (17, 19): ["wrap-up", "planning", "email"],
        (19, 22): ["personal", "learning", "side-projects"],
        (22, 24): ["personal", "quick-tasks", "tomorrow-prep"]
    }
    
    for (start, end), contexts in time_contexts.items():
        if start <= hour < end:
            return contexts
    
    return ["general"]


def get_energy_suggestions(current_energy: str) -> Dict[str, List[str]]:
    """Suggest task types based on current energy level"""
    suggestions = {
        "high": [
            "Start challenging projects",
            "Tackle complex problem-solving tasks", 
            "Work on creative initiatives",
            "Handle difficult conversations",
            "Learn new skills"
        ],
        "medium": [
            "Complete routine tasks",
            "Respond to emails",
            "Attend meetings", 
            "Review and approve items",
            "Organize and plan"
        ],
        "low": [
            "Do quick administrative tasks",
            "File and organize documents",
            "Update status reports",
            "Read industry articles",
            "Plan tomorrow's work"
        ]
    }
    
    return {"suggestions": suggestions.get(current_energy, suggestions["medium"])}