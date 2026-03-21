"""Tests for the Pomodoro/Focus Timer service."""

import json
import time
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from todo_cli.services.pomodoro import (
    PomodoroConfig,
    PomodoroSession,
    PomodoroStats,
    PomodoroTimer,
    TimerState,
)


@pytest.fixture
def tmp_data_dir(tmp_path):
    """Provide an isolated data directory for each test."""
    return tmp_path / "pomodoro_data"


@pytest.fixture
def timer(tmp_data_dir):
    """Provide a fresh PomodoroTimer backed by a temp directory."""
    return PomodoroTimer(data_dir=tmp_data_dir)


# ---- PomodoroConfig defaults ----


def test_config_defaults():
    cfg = PomodoroConfig()
    assert cfg.focus_minutes == 25
    assert cfg.short_break_minutes == 5
    assert cfg.long_break_minutes == 15
    assert cfg.sessions_before_long_break == 4
    assert cfg.auto_start_breaks is True
    assert cfg.auto_start_focus is False
    assert cfg.notify_on_state_change is True
    assert cfg.sound_enabled is True


def test_config_custom():
    cfg = PomodoroConfig(focus_minutes=50, short_break_minutes=10)
    assert cfg.focus_minutes == 50
    assert cfg.short_break_minutes == 10


# ---- State machine: idle -> focus -> break -> focus ----


def test_initial_state(timer):
    assert timer.state == TimerState.IDLE
    assert timer.current_session is None
    assert timer.session_count == 0


def test_start_focus(timer):
    session = timer.start_focus(task_id="42", task_text="Write tests")
    assert timer.state == TimerState.FOCUS
    assert session.state == TimerState.FOCUS
    assert session.task_id == "42"
    assert session.task_text == "Write tests"
    assert session.started_at is not None
    assert session.planned_minutes == 25


def test_complete_focus_then_break(timer):
    timer.start_focus()
    completed = timer.complete_session()
    assert completed is not None
    assert completed.completed is True
    assert completed.actual_minutes >= 0
    assert timer.state == TimerState.IDLE
    assert timer.session_count == 1

    # Starting a break after 1 session => short break
    break_session = timer.start_break()
    assert timer.state == TimerState.SHORT_BREAK
    assert break_session.planned_minutes == 5

    timer.complete_session()
    assert timer.state == TimerState.IDLE


def test_focus_break_cycle(timer):
    """Full cycle: focus -> short break -> focus -> ... -> long break."""
    for i in range(1, 5):
        timer.start_focus()
        timer.complete_session()
        assert timer.session_count == i

        timer.start_break()
        if i % timer.config.sessions_before_long_break == 0:
            assert timer.state == TimerState.LONG_BREAK
            assert timer.current_session.planned_minutes == timer.config.long_break_minutes
        else:
            assert timer.state == TimerState.SHORT_BREAK
            assert timer.current_session.planned_minutes == timer.config.short_break_minutes
        timer.complete_session()


# ---- Session completion and history ----


def test_session_history_grows(timer):
    assert len(timer.history) == 0
    timer.start_focus()
    timer.complete_session()
    assert len(timer.history) == 1
    assert timer.history[0].completed is True


def test_complete_no_session_returns_none(timer):
    assert timer.complete_session() is None


# ---- Session interruption ----


def test_interrupt_session(timer):
    timer.start_focus(task_id="1", task_text="Interrupted task")
    session = timer.interrupt_session()
    assert session is not None
    assert session.interrupted is True
    assert session.completed is False
    assert timer.state == TimerState.IDLE
    assert timer.current_session is None
    assert len(timer.history) == 1


def test_interrupt_no_session_returns_none(timer):
    assert timer.interrupt_session() is None


# ---- Pause / Resume ----


def test_pause_and_resume(timer):
    timer.start_focus()
    assert timer.state == TimerState.FOCUS

    timer.pause()
    assert timer.state == TimerState.PAUSED

    timer.resume()
    assert timer.state == TimerState.FOCUS


def test_pause_during_break(timer):
    # Complete a focus session first
    timer.start_focus()
    timer.complete_session()

    timer.start_break()
    assert timer.state == TimerState.SHORT_BREAK

    timer.pause()
    assert timer.state == TimerState.PAUSED

    timer.resume()
    assert timer.state == TimerState.SHORT_BREAK


def test_pause_when_idle_does_nothing(timer):
    timer.pause()
    assert timer.state == TimerState.IDLE


def test_resume_when_not_paused_does_nothing(timer):
    timer.start_focus()
    timer.resume()
    assert timer.state == TimerState.FOCUS


# ---- Stats calculation ----


def test_stats_empty(timer):
    stats = timer.get_stats()
    assert stats.total_sessions == 0
    assert stats.completed_sessions == 0
    assert stats.interrupted_sessions == 0
    assert stats.average_focus_minutes == 0.0
    assert stats.current_streak == 0
    assert stats.best_streak == 0


def test_stats_with_completed_sessions(timer):
    for _ in range(3):
        timer.start_focus()
        timer.complete_session()

    stats = timer.get_stats()
    assert stats.total_sessions == 3
    assert stats.completed_sessions == 3
    assert stats.interrupted_sessions == 0
    assert stats.current_streak == 3
    assert stats.best_streak == 3
    assert stats.average_focus_minutes >= 0


def test_stats_with_interruptions(timer):
    timer.start_focus()
    timer.complete_session()
    timer.start_focus()
    timer.interrupt_session()
    timer.start_focus()
    timer.complete_session()

    stats = timer.get_stats()
    assert stats.total_sessions == 3
    assert stats.completed_sessions == 2
    assert stats.interrupted_sessions == 1
    # Streak resets after interruption
    assert stats.current_streak == 1
    assert stats.best_streak == 1


def test_stats_sessions_today(timer):
    timer.start_focus()
    timer.complete_session()

    stats = timer.get_stats()
    assert stats.sessions_today == 1
    assert stats.focus_minutes_today >= 0


def test_stats_break_minutes(timer):
    # Complete a focus first to allow break
    timer.start_focus()
    timer.complete_session()

    # Now do a break
    timer.start_break()
    timer.complete_session()

    stats = timer.get_stats()
    assert stats.total_break_minutes >= 0


# ---- History persistence (save/load) ----


def test_history_persistence(tmp_data_dir):
    timer1 = PomodoroTimer(data_dir=tmp_data_dir)
    timer1.start_focus(task_id="99", task_text="Persist me")
    timer1.complete_session()
    assert len(timer1.history) == 1

    # Create a new timer pointing at the same directory
    timer2 = PomodoroTimer(data_dir=tmp_data_dir)
    assert len(timer2.history) == 1
    assert timer2.history[0].task_id == "99"
    assert timer2.history[0].task_text == "Persist me"
    assert timer2.history[0].completed is True
    assert timer2.history[0].started_at is not None
    assert timer2.history[0].ended_at is not None


def test_history_file_created(tmp_data_dir):
    timer = PomodoroTimer(data_dir=tmp_data_dir)
    timer.start_focus()
    timer.complete_session()
    assert (tmp_data_dir / "pomodoro_history.json").exists()

    with open(tmp_data_dir / "pomodoro_history.json") as f:
        data = json.load(f)
    assert len(data) == 1
    assert data[0]["completed"] is True


def test_load_corrupted_history(tmp_data_dir):
    """Corrupted JSON should not crash the timer."""
    tmp_data_dir.mkdir(parents=True, exist_ok=True)
    with open(tmp_data_dir / "pomodoro_history.json", "w") as f:
        f.write("NOT VALID JSON{{{")

    timer = PomodoroTimer(data_dir=tmp_data_dir)
    assert timer.history == []


# ---- Remaining seconds ----


def test_remaining_seconds_idle(timer):
    assert timer.get_remaining_seconds() == 0


def test_remaining_seconds_during_focus(timer):
    timer.start_focus()
    remaining = timer.get_remaining_seconds()
    # Should be close to 25 * 60 = 1500 seconds
    assert 0 < remaining <= 25 * 60


def test_remaining_seconds_custom_duration(tmp_data_dir):
    cfg = PomodoroConfig(focus_minutes=10)
    timer = PomodoroTimer(config=cfg, data_dir=tmp_data_dir)
    timer.start_focus()
    remaining = timer.get_remaining_seconds()
    assert 0 < remaining <= 10 * 60


# ---- Long break after N sessions ----


def test_long_break_after_n_sessions(tmp_data_dir):
    cfg = PomodoroConfig(sessions_before_long_break=2)
    timer = PomodoroTimer(config=cfg, data_dir=tmp_data_dir)

    # Session 1
    timer.start_focus()
    timer.complete_session()
    assert timer.session_count == 1

    # Break after session 1 => short break (1 is not divisible by 2)
    timer.start_break()
    assert timer.state == TimerState.SHORT_BREAK
    timer.complete_session()

    # Session 2
    timer.start_focus()
    timer.complete_session()
    assert timer.session_count == 2

    # Break after session 2 => long break (2 is divisible by 2)
    timer.start_break()
    assert timer.state == TimerState.LONG_BREAK
    assert timer.current_session.planned_minutes == cfg.long_break_minutes
    timer.complete_session()


# ---- PomodoroSession.to_dict ----


def test_session_to_dict():
    now = datetime.now()
    session = PomodoroSession(
        task_id="5",
        task_text="Do stuff",
        state=TimerState.FOCUS,
        started_at=now,
        ended_at=now + timedelta(minutes=25),
        planned_minutes=25,
        actual_minutes=25.0,
        completed=True,
        interrupted=False,
        notes="Good session",
    )
    d = session.to_dict()
    assert d["task_id"] == "5"
    assert d["state"] == "focus"
    assert d["completed"] is True
    assert d["notes"] == "Good session"
    assert d["started_at"] == now.isoformat()


# ---- TimerState enum ----


def test_timer_state_values():
    assert TimerState.IDLE.value == "idle"
    assert TimerState.FOCUS.value == "focus"
    assert TimerState.SHORT_BREAK.value == "short_break"
    assert TimerState.LONG_BREAK.value == "long_break"
    assert TimerState.PAUSED.value == "paused"
