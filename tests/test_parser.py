"""Tests for natural language parser."""

import pytest
from datetime import datetime, timedelta
from src.todo_cli.parser import (
    NaturalLanguageParser, SmartDateParser, TaskBuilder, ParsedTask,
    parse_task_input
)
from src.todo_cli.config import ConfigModel
from src.todo_cli.todo import Priority


class TestSmartDateParser:
    """Test the smart date parser."""
    
    def setup_method(self):
        self.parser = SmartDateParser()
    
    def test_parse_today(self):
        """Test parsing 'today'."""
        result = self.parser.parse("today")
        assert result is not None
        assert result.date() == datetime.now().date()
        assert result.hour == 23 and result.minute == 59
    
    def test_parse_tomorrow(self):
        """Test parsing 'tomorrow'."""
        result = self.parser.parse("tomorrow")
        assert result is not None
        expected_date = (datetime.now() + timedelta(days=1)).date()
        assert result.date() == expected_date
    
    def test_parse_next_week(self):
        """Test parsing 'next week'."""
        result = self.parser.parse("next week")
        assert result is not None
        expected_date = (datetime.now() + timedelta(weeks=1)).date()
        assert result.date() == expected_date
    
    def test_parse_iso_date(self):
        """Test parsing ISO date format."""
        result = self.parser.parse("2024-12-25")
        assert result is not None
        assert result.year == 2024
        assert result.month == 12
        assert result.day == 25
    
    def test_parse_us_date(self):
        """Test parsing US date format."""
        result = self.parser.parse("12/25/2024")
        assert result is not None
        assert result.year == 2024
        assert result.month == 12
        assert result.day == 25
    
    def test_parse_invalid_date(self):
        """Test parsing invalid date."""
        result = self.parser.parse("invalid-date")
        assert result is None
    
    def test_parse_empty_string(self):
        """Test parsing empty string."""
        result = self.parser.parse("")
        assert result is None


class TestNaturalLanguageParser:
    """Test the natural language parser."""
    
    def setup_method(self):
        self.config = ConfigModel()
        self.parser = NaturalLanguageParser(self.config)
    
    def test_basic_task_parsing(self):
        """Test basic task text parsing."""
        parsed, errors = self.parser.parse("Buy groceries")
        
        assert parsed.text == "Buy groceries"
        assert len(errors) == 0
        assert parsed.project is None
        assert parsed.tags == []
        assert parsed.priority is None
    
    def test_project_parsing(self):
        """Test project extraction."""
        parsed, errors = self.parser.parse("Review code #webapp")
        
        assert parsed.text == "Review code"
        assert parsed.project == "webapp"
        assert len(errors) == 0
    
    def test_tags_parsing(self):
        """Test tag extraction."""
        parsed, errors = self.parser.parse("Call client @urgent @phone")
        
        assert parsed.text == "Call client"
        assert "urgent" in parsed.tags
        assert "phone" in parsed.context  # phone should be treated as context
        assert len(errors) == 0
    
    def test_context_parsing(self):
        """Test context-aware tag parsing."""
        parsed, errors = self.parser.parse("Fix bug @home @computer @urgent")
        
        assert parsed.text == "Fix bug"
        assert "urgent" in parsed.tags
        assert "home" in parsed.context
        assert "computer" in parsed.context
        assert len(errors) == 0
    
    def test_priority_parsing(self):
        """Test priority extraction."""
        parsed, errors = self.parser.parse("Fix critical bug ~high")
        
        assert parsed.text == "Fix critical bug"
        assert parsed.priority == Priority.HIGH
        assert len(errors) == 0
    
    def test_assignee_parsing(self):
        """Test assignee extraction."""
        parsed, errors = self.parser.parse("Review PR +john +sarah")
        
        assert parsed.text == "Review PR"
        assert "john" in parsed.assignees
        assert "sarah" in parsed.assignees
        assert len(errors) == 0
    
    def test_stakeholder_parsing(self):
        """Test stakeholder extraction."""
        parsed, errors = self.parser.parse("Project update &manager &team")
        
        assert parsed.text == "Project update"
        assert "manager" in parsed.stakeholders
        assert "team" in parsed.stakeholders
        assert len(errors) == 0
    
    def test_effort_parsing(self):
        """Test effort extraction."""
        parsed, errors = self.parser.parse("Write tests *small")
        
        assert parsed.text == "Write tests"
        assert parsed.effort == "small"
        assert len(errors) == 0
    
    def test_recurrence_parsing(self):
        """Test recurrence extraction."""
        parsed, errors = self.parser.parse("Weekly standup %weekly")
        
        assert parsed.text == "Weekly standup"
        assert parsed.recurrence == "weekly"
        assert len(errors) == 0
    
    def test_pinned_parsing(self):
        """Test pinned flag extraction."""
        test_cases = ["Important task [PINNED]", "Task [PIN]", "Task [P]"]
        
        for test_case in test_cases:
            parsed, errors = self.parser.parse(test_case)
            assert parsed.pinned is True
            assert len(errors) == 0
    
    def test_url_parsing(self):
        """Test URL extraction."""
        parsed, errors = self.parser.parse("Check documentation https://example.com/docs")
        
        assert parsed.text == "Check documentation"
        assert parsed.url == "https://example.com/docs"
        assert len(errors) == 0
    
    def test_waiting_for_parsing(self):
        """Test waiting for extraction."""
        parsed, errors = self.parser.parse("Deploy app (waiting: approval, testing)")
        
        assert parsed.text == "Deploy app"
        assert "approval" in parsed.waiting_for
        assert "testing" in parsed.waiting_for
        assert len(errors) == 0
    
    def test_energy_level_parsing(self):
        """Test energy level extraction."""
        parsed, errors = self.parser.parse("Deep work session energy:high")
        
        assert parsed.text == "Deep work session"
        assert parsed.energy_level == "high"
        assert len(errors) == 0
    
    def test_time_estimate_parsing(self):
        """Test time estimate extraction."""
        test_cases = [
            ("Quick task est:30m", 30),
            ("Long meeting est:2h", 120),
            ("Review est:45min", 45),
            ("Workshop est:3hr", 180)
        ]
        
        for input_text, expected_minutes in test_cases:
            parsed, errors = self.parser.parse(input_text)
            assert parsed.time_estimate == expected_minutes
            assert len(errors) == 0
    
    def test_due_date_parsing(self):
        """Test due date extraction."""
        parsed, errors = self.parser.parse("Submit report due tomorrow")
        
        assert parsed.text == "Submit report"
        assert parsed.due_date is not None
        expected_date = (datetime.now() + timedelta(days=1)).date()
        assert parsed.due_date.date() == expected_date
        assert len(errors) == 0
    
    def test_complex_parsing(self):
        """Test parsing complex input with multiple metadata types."""
        input_text = ("Deploy application #webapp @urgent @work ~high "
                     "+devops &manager due tomorrow est:2h [PIN]")
        
        parsed, errors = self.parser.parse(input_text)
        
        assert parsed.text == "Deploy application"
        assert parsed.project == "webapp"
        assert "urgent" in parsed.tags
        assert "work" in parsed.context
        assert parsed.priority == Priority.HIGH
        assert "devops" in parsed.assignees
        assert "manager" in parsed.stakeholders
        assert parsed.due_date is not None
        assert parsed.time_estimate == 120
        assert parsed.pinned is True
        assert len(errors) == 0
    
    def test_invalid_priority_error(self):
        """Test error handling for invalid priority."""
        parsed, errors = self.parser.parse("Task ~invalid")
        
        assert len(errors) == 1
        assert "Invalid priority" in errors[0].message
        assert "critical, high, medium, low" in errors[0].suggestions[0]
    
    def test_empty_text_error(self):
        """Test error for empty task text."""
        parsed, errors = self.parser.parse("")
        
        assert len(errors) == 1
        assert "Empty task text" in errors[0].message
    
    def test_no_description_error(self):
        """Test error when only metadata provided."""
        parsed, errors = self.parser.parse("#project @tag ~high")
        
        assert len(errors) == 1
        assert "No task description found" in errors[0].message


class TestTaskBuilder:
    """Test the task builder."""
    
    def setup_method(self):
        self.config = ConfigModel()
        self.builder = TaskBuilder(self.config)
    
    def test_basic_build(self):
        """Test building basic todo."""
        parsed = ParsedTask(text="Test task")
        todo = self.builder.build(parsed, 1)
        
        assert todo.id == 1
        assert todo.text == "Test task"
        assert todo.project == self.config.default_project
        assert todo.priority == Priority(self.config.default_priority)
    
    def test_full_build(self):
        """Test building todo with all fields."""
        due_date = datetime.now() + timedelta(days=1)
        
        parsed = ParsedTask(
            text="Complex task",
            project="test-project",
            tags=["urgent"],
            context=["work"],
            priority=Priority.HIGH,
            due_date=due_date,
            assignees=["john"],
            stakeholders=["manager"],
            effort="large",
            pinned=True,
            energy_level="high",
            time_estimate=120
        )
        
        todo = self.builder.build(parsed, 42)
        
        assert todo.id == 42
        assert todo.text == "Complex task"
        assert todo.project == "test-project"
        assert todo.tags == ["urgent"]
        assert todo.context == ["work"]
        assert todo.priority == Priority.HIGH
        # Due date is stored timezone-aware; compare by date component
        assert todo.due_date.date() == due_date.date()
        assert todo.assignees == ["john"]
        assert todo.stakeholders == ["manager"]
        assert todo.effort == "large"
        assert todo.pinned is True
        assert todo.energy_level == "high"
        assert todo.time_estimate == 120


class TestParseTaskInput:
    """Test the main parse_task_input function."""
    
    def setup_method(self):
        self.config = ConfigModel()
    
    def test_basic_parsing(self):
        """Test basic task parsing."""
        parsed, errors, suggestions = parse_task_input("Test task", self.config)
        
        assert parsed.text == "Test task"
        assert len(errors) == 0
        assert len(suggestions) == 0
    
    def test_with_suggestions(self):
        """Test parsing with typo suggestions."""
        available_projects = ["webapp", "mobile"]
        
        parsed, errors, suggestions = parse_task_input(
            "Fix bug #webap",  # Typo in project name
            self.config,
            available_projects=available_projects
        )
        
        assert len(suggestions) > 0
        assert "webapp" in suggestions[0]
    
    def test_project_hint(self):
        """Test parsing with project hint."""
        parsed, errors, suggestions = parse_task_input(
            "Simple task",
            self.config,
            project_hint="custom-project"
        )
        
        assert parsed.project == "custom-project"
        assert len(errors) == 0


class TestIntegration:
    """Integration tests combining parser and builder."""
    
    def setup_method(self):
        self.config = ConfigModel()
    
    def test_end_to_end_parsing(self):
        """Test complete parsing workflow."""
        input_text = "Review PR #webapp @code-review ~high +reviewer due friday est:1h"
        
        parsed, errors, suggestions = parse_task_input(input_text, self.config)
        
        assert len(errors) == 0
        assert parsed.text == "Review PR"
        assert parsed.project == "webapp"
        assert "code-review" in parsed.tags
        assert parsed.priority == Priority.HIGH
        assert "reviewer" in parsed.assignees
        assert parsed.due_date is not None
        assert parsed.time_estimate == 60
        
        # Build the todo
        builder = TaskBuilder(self.config)
        todo = builder.build(parsed, 1)
        
        assert todo.text == "Review PR"
        assert todo.project == "webapp"
        assert "code-review" in todo.tags
        assert todo.priority == Priority.HIGH
        assert "reviewer" in todo.assignees
        assert todo.time_estimate == 60