"""Pomodoro/Focus Timer for Todo CLI.

Provides a configurable focus timer with work/break intervals,
auto-logging to the time tracker, and desktop notifications.
"""

import time
import json
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass, field, asdict
from typing import Optional, List, Dict, Any, Callable
from pathlib import Path


class TimerState(Enum):
    IDLE = "idle"
    FOCUS = "focus"
    SHORT_BREAK = "short_break"
    LONG_BREAK = "long_break"
    PAUSED = "paused"


@dataclass
class PomodoroConfig:
    """Pomodoro timer configuration."""
    focus_minutes: int = 25
    short_break_minutes: int = 5
    long_break_minutes: int = 15
    sessions_before_long_break: int = 4
    auto_start_breaks: bool = True
    auto_start_focus: bool = False
    notify_on_state_change: bool = True
    sound_enabled: bool = True


@dataclass
class PomodoroSession:
    """A single pomodoro session record."""
    task_id: Optional[str] = None
    task_text: Optional[str] = None
    state: TimerState = TimerState.FOCUS
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    planned_minutes: int = 25
    actual_minutes: float = 0.0
    completed: bool = False
    interrupted: bool = False
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "task_text": self.task_text,
            "state": self.state.value,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "ended_at": self.ended_at.isoformat() if self.ended_at else None,
            "planned_minutes": self.planned_minutes,
            "actual_minutes": self.actual_minutes,
            "completed": self.completed,
            "interrupted": self.interrupted,
            "notes": self.notes,
        }


@dataclass
class PomodoroStats:
    """Aggregate pomodoro statistics."""
    total_sessions: int = 0
    completed_sessions: int = 0
    interrupted_sessions: int = 0
    total_focus_minutes: float = 0.0
    total_break_minutes: float = 0.0
    average_focus_minutes: float = 0.0
    current_streak: int = 0
    best_streak: int = 0
    sessions_today: int = 0
    focus_minutes_today: float = 0.0


class PomodoroTimer:
    """Manages pomodoro timer state and session history."""

    def __init__(self, config: Optional[PomodoroConfig] = None, data_dir: Optional[Path] = None):
        self.config = config or PomodoroConfig()
        self.data_dir = data_dir or Path.home() / ".todo"
        self.history_file = self.data_dir / "pomodoro_history.json"
        self.state = TimerState.IDLE
        self.current_session: Optional[PomodoroSession] = None
        self.session_count = 0  # sessions completed in current cycle
        self.history: List[PomodoroSession] = []
        self._paused_from: Optional[TimerState] = None
        self._load_history()

    def start_focus(self, task_id: Optional[str] = None, task_text: Optional[str] = None) -> PomodoroSession:
        """Start a focus session."""
        self.state = TimerState.FOCUS
        self.current_session = PomodoroSession(
            task_id=task_id,
            task_text=task_text,
            state=TimerState.FOCUS,
            started_at=datetime.now(),
            planned_minutes=self.config.focus_minutes,
        )
        return self.current_session

    def start_break(self) -> PomodoroSession:
        """Start a break (short or long based on session count)."""
        if self.session_count > 0 and self.session_count % self.config.sessions_before_long_break == 0:
            self.state = TimerState.LONG_BREAK
            minutes = self.config.long_break_minutes
        else:
            self.state = TimerState.SHORT_BREAK
            minutes = self.config.short_break_minutes

        self.current_session = PomodoroSession(
            state=self.state,
            started_at=datetime.now(),
            planned_minutes=minutes,
        )
        return self.current_session

    def complete_session(self) -> Optional[PomodoroSession]:
        """Mark current session as completed."""
        if self.current_session:
            self.current_session.ended_at = datetime.now()
            self.current_session.completed = True
            if self.current_session.started_at:
                delta = self.current_session.ended_at - self.current_session.started_at
                self.current_session.actual_minutes = delta.total_seconds() / 60

            if self.current_session.state == TimerState.FOCUS:
                self.session_count += 1

            self.history.append(self.current_session)
            self._save_history()

            session = self.current_session
            self.current_session = None
            self.state = TimerState.IDLE
            return session
        return None

    def interrupt_session(self) -> Optional[PomodoroSession]:
        """Interrupt/cancel the current session."""
        if self.current_session:
            self.current_session.ended_at = datetime.now()
            self.current_session.interrupted = True
            if self.current_session.started_at:
                delta = self.current_session.ended_at - self.current_session.started_at
                self.current_session.actual_minutes = delta.total_seconds() / 60

            self.history.append(self.current_session)
            self._save_history()

            session = self.current_session
            self.current_session = None
            self.state = TimerState.IDLE
            return session
        return None

    def pause(self):
        """Pause the current session."""
        if self.state in (TimerState.FOCUS, TimerState.SHORT_BREAK, TimerState.LONG_BREAK):
            self._paused_from = self.state
            self.state = TimerState.PAUSED

    def resume(self):
        """Resume a paused session."""
        if self.state == TimerState.PAUSED and self._paused_from is not None:
            self.state = self._paused_from
            self._paused_from = None

    def get_stats(self, days: int = 7) -> PomodoroStats:
        """Calculate pomodoro statistics."""
        stats = PomodoroStats()
        today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

        streak = 0
        best_streak = 0

        for session in self.history:
            if session.state == TimerState.FOCUS:
                stats.total_sessions += 1
                if session.completed:
                    stats.completed_sessions += 1
                    stats.total_focus_minutes += session.actual_minutes
                    streak += 1
                    best_streak = max(best_streak, streak)
                else:
                    stats.interrupted_sessions += 1
                    streak = 0

                if session.started_at and session.started_at >= today_start:
                    stats.sessions_today += 1
                    if session.completed:
                        stats.focus_minutes_today += session.actual_minutes
            elif session.state in (TimerState.SHORT_BREAK, TimerState.LONG_BREAK):
                if session.completed:
                    stats.total_break_minutes += session.actual_minutes

        stats.current_streak = streak
        stats.best_streak = best_streak
        if stats.completed_sessions > 0:
            stats.average_focus_minutes = stats.total_focus_minutes / stats.completed_sessions

        return stats

    def get_remaining_seconds(self) -> float:
        """Get seconds remaining in current session."""
        if not self.current_session or not self.current_session.started_at:
            return 0
        elapsed = (datetime.now() - self.current_session.started_at).total_seconds()
        total = self.current_session.planned_minutes * 60
        return max(0, total - elapsed)

    def _load_history(self):
        """Load session history from file."""
        if self.history_file.exists():
            try:
                with open(self.history_file) as f:
                    data = json.load(f)
                for item in data:
                    session = PomodoroSession(
                        task_id=item.get("task_id"),
                        task_text=item.get("task_text"),
                        state=TimerState(item.get("state", "focus")),
                        planned_minutes=item.get("planned_minutes", 25),
                        actual_minutes=item.get("actual_minutes", 0),
                        completed=item.get("completed", False),
                        interrupted=item.get("interrupted", False),
                        notes=item.get("notes", ""),
                    )
                    if item.get("started_at"):
                        session.started_at = datetime.fromisoformat(item["started_at"])
                    if item.get("ended_at"):
                        session.ended_at = datetime.fromisoformat(item["ended_at"])
                    self.history.append(session)
            except Exception:
                self.history = []

    def _save_history(self):
        """Save session history to file."""
        self.data_dir.mkdir(parents=True, exist_ok=True)
        try:
            data = [s.to_dict() for s in self.history]
            with open(self.history_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception:
            pass
