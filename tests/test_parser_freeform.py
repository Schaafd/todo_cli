"""Freeform date parsing tests for NaturalLanguageParser."""

from datetime import datetime, timedelta

from src.todo_cli.parser import NaturalLanguageParser
from src.todo_cli.config import ConfigModel


class TestFreeformDateParsing:
    def setup_method(self):
        self.config = ConfigModel()
        self.parser = NaturalLanguageParser(self.config)

    def test_freeform_for_tomorrow(self):
        parsed, errors = self.parser.parse("Test todo for tomorrow")
        assert len(errors) == 0
        assert parsed.text == "Test todo"
        assert parsed.due_date is not None
        expected_date = (datetime.now() + timedelta(days=1)).date()
        assert parsed.due_date.date() == expected_date

    def test_freeform_by_monday(self):
        parsed, errors = self.parser.parse("Finish report by Monday")
        assert len(errors) == 0
        assert parsed.text == "Finish report"
        assert parsed.due_date is not None  # exact weekday depends on current date

    def test_freeform_on_numeric_date(self):
        parsed, errors = self.parser.parse("Call mom on 12/25")
        assert len(errors) == 0
        assert parsed.text == "Call mom"
        assert parsed.due_date is not None

    def test_word_boundary_for_at(self):
        # Ensure 'at' inside words (e.g., 'Latest') does not trigger scheduled matching
        parsed, errors = self.parser.parse("Latest release notes")
        assert len(errors) == 0
        assert parsed.text == "Latest release notes"
        assert parsed.scheduled_date is None
