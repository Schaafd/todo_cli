"""Tests for the AI assistant service and CLI commands."""

import json
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from todo_cli.domain.todo import Todo, TodoStatus, Priority
from todo_cli.services.ai_assistant import (
    AIProvider,
    OpenAIProvider,
    OllamaProvider,
    TaskAIAssistant,
    AIInsightsDataSource,
    create_assistant_from_config,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class MockProvider(AIProvider):
    """Deterministic mock AI provider for testing."""

    def __init__(self, response: str = "mock response"):
        self._response = response

    def is_available(self) -> bool:
        return True

    def generate(self, prompt: str, system_prompt=None) -> str:
        return self._response


def _make_todo(
    id: int = 1,
    text: str = "Test task",
    status: TodoStatus = TodoStatus.PENDING,
    priority: Priority = Priority.MEDIUM,
    project: str = "inbox",
    tags: list | None = None,
    due_date: datetime | None = None,
    context: list | None = None,
) -> Todo:
    return Todo(
        id=id,
        text=text,
        status=status,
        priority=priority,
        project=project,
        tags=tags or [],
        due_date=due_date,
        context=context or [],
    )


# ---------------------------------------------------------------------------
# Provider availability
# ---------------------------------------------------------------------------


class TestProviderAvailability:
    """AIProvider availability checks when deps are not installed."""

    def test_openai_unavailable_no_package(self):
        """OpenAI provider reports unavailable when package is missing."""
        with patch.dict("sys.modules", {"openai": None}):
            provider = OpenAIProvider(api_key="sk-test")
            assert provider.is_available() is False

    def test_openai_unavailable_no_api_key(self):
        """OpenAI provider reports unavailable when no API key is set."""
        provider = OpenAIProvider(api_key=None)
        # Even if the package were installed, no key means not available
        # We patch the import to succeed but key is missing
        mock_openai = MagicMock()
        with patch.dict("sys.modules", {"openai": mock_openai}):
            # Clear env var to make sure
            with patch.dict("os.environ", {}, clear=True):
                prov = OpenAIProvider(api_key=None)
                assert prov.is_available() is False

    def test_ollama_unavailable_no_package(self):
        """Ollama provider reports unavailable when package is missing."""
        with patch.dict("sys.modules", {"ollama": None}):
            provider = OllamaProvider()
            assert provider.is_available() is False

    def test_mock_provider_available(self):
        """MockProvider is always available."""
        provider = MockProvider()
        assert provider.is_available() is True


# ---------------------------------------------------------------------------
# _build_task_context
# ---------------------------------------------------------------------------


class TestBuildTaskContext:
    """Tests for _build_task_context serialisation."""

    def test_empty_list(self):
        assistant = TaskAIAssistant(MockProvider())
        result = assistant._build_task_context([])
        assert result == "(no tasks)"

    def test_basic_task(self):
        assistant = TaskAIAssistant(MockProvider())
        todo = _make_todo(text="Buy milk", priority=Priority.HIGH)
        result = assistant._build_task_context([todo])
        assert "Buy milk" in result
        assert "P:high" in result
        assert "pending" in result

    def test_task_with_metadata(self):
        assistant = TaskAIAssistant(MockProvider())
        due = datetime(2025, 12, 31, tzinfo=timezone.utc)
        todo = _make_todo(
            text="Ship feature",
            tags=["urgent", "backend"],
            project="webapp",
            due_date=due,
            context=["work"],
        )
        result = assistant._build_task_context([todo])
        assert "due:2025-12-31" in result
        assert "tags:urgent,backend" in result
        assert "project:webapp" in result
        assert "context:work" in result

    def test_multiple_tasks(self):
        assistant = TaskAIAssistant(MockProvider())
        todos = [
            _make_todo(id=1, text="Task A"),
            _make_todo(id=2, text="Task B"),
        ]
        result = assistant._build_task_context(todos)
        assert "Task A" in result
        assert "Task B" in result
        # Should have multiple lines
        assert len(result.strip().splitlines()) == 2


# ---------------------------------------------------------------------------
# auto_categorize parsing
# ---------------------------------------------------------------------------


class TestAutoCategorize:
    """Tests for auto_categorize response parsing."""

    def test_valid_json(self):
        json_response = json.dumps({
            "tags": ["grocery", "errand"],
            "priority": "low",
            "project": "personal",
            "context": "home",
        })
        assistant = TaskAIAssistant(MockProvider(response=json_response))
        result = assistant.auto_categorize("buy groceries")
        assert result["tags"] == ["grocery", "errand"]
        assert result["priority"] == "low"
        assert result["project"] == "personal"
        assert result["context"] == "home"

    def test_json_with_markdown_fences(self):
        json_response = '```json\n{"tags": ["dev"], "priority": "high", "project": "api", "context": "work"}\n```'
        assistant = TaskAIAssistant(MockProvider(response=json_response))
        result = assistant.auto_categorize("fix API bug")
        assert result["tags"] == ["dev"]
        assert result["priority"] == "high"

    def test_invalid_json_returns_default(self):
        assistant = TaskAIAssistant(MockProvider(response="this is not json"))
        result = assistant.auto_categorize("some task")
        assert result["tags"] == []
        assert result["priority"] == "medium"
        assert result["project"] == "inbox"
        assert result["context"] == ""


# ---------------------------------------------------------------------------
# suggest_next_task
# ---------------------------------------------------------------------------


class TestSuggestNextTask:
    """Tests for suggest_next_task with mock provider."""

    def test_basic_suggestion(self):
        assistant = TaskAIAssistant(MockProvider(response="Work on task A because it is high priority."))
        todos = [
            _make_todo(id=1, text="Task A", priority=Priority.HIGH),
            _make_todo(id=2, text="Task B", priority=Priority.LOW),
        ]
        result = assistant.suggest_next_task(todos)
        assert "Work on task A" in result

    def test_with_context(self):
        provider = MockProvider(response="Do the quick task.")
        assistant = TaskAIAssistant(provider)
        todos = [_make_todo(text="Quick task")]
        result = assistant.suggest_next_task(todos, context="energy: low, time: 15 minutes")
        assert "quick task" in result.lower()

    def test_no_todos(self):
        provider = MockProvider(response="No tasks to suggest.")
        assistant = TaskAIAssistant(provider)
        result = assistant.suggest_next_task([])
        assert "No tasks" in result


# ---------------------------------------------------------------------------
# smart_query
# ---------------------------------------------------------------------------


class TestSmartQuery:
    """Tests for smart_query with mock provider."""

    def test_basic_query(self):
        assistant = TaskAIAssistant(MockProvider(response="You have 2 overdue tasks."))
        todos = [
            _make_todo(id=1, text="Overdue item"),
            _make_todo(id=2, text="Another overdue"),
        ]
        result = assistant.smart_query("what's overdue?", todos)
        assert "2 overdue" in result

    def test_query_with_empty_todos(self):
        assistant = TaskAIAssistant(MockProvider(response="You have no tasks."))
        result = assistant.smart_query("how many tasks do I have?", [])
        assert "no tasks" in result


# ---------------------------------------------------------------------------
# summarize_tasks
# ---------------------------------------------------------------------------


class TestSummarizeTasks:
    """Tests for summarize_tasks with mock provider."""

    def test_summary(self):
        assistant = TaskAIAssistant(MockProvider(
            response="You have 3 tasks: 1 completed, 2 pending. No overdue items."
        ))
        todos = [
            _make_todo(id=1, text="Done", status=TodoStatus.COMPLETED),
            _make_todo(id=2, text="Pending A"),
            _make_todo(id=3, text="Pending B"),
        ]
        result = assistant.summarize_tasks(todos)
        assert "3 tasks" in result
        assert "completed" in result


# ---------------------------------------------------------------------------
# AIInsightsDataSource
# ---------------------------------------------------------------------------


class TestAIInsightsDataSource:
    """Tests for the dashboard data source."""

    def test_suggestion_metric(self):
        mock_assistant = TaskAIAssistant(MockProvider(response="Focus on task X"))
        ds = AIInsightsDataSource(assistant=mock_assistant)
        data = ds.fetch_data({"metric_type": "ai_suggestion", "todos": []})
        assert "Focus on task X" in str(data.value)

    def test_summary_metric(self):
        mock_assistant = TaskAIAssistant(MockProvider(response="All good!"))
        ds = AIInsightsDataSource(assistant=mock_assistant)
        data = ds.fetch_data({"metric_type": "task_summary", "todos": []})
        assert "All good!" in str(data.value)

    def test_no_assistant_returns_fallback(self):
        ds = AIInsightsDataSource(assistant=None)
        # Patch create_assistant_from_config to return None
        with patch("todo_cli.services.ai_assistant.create_assistant_from_config", return_value=None):
            data = ds.fetch_data({"metric_type": "ai_suggestion", "todos": []})
            assert "not available" in str(data.value).lower()

    def test_schema(self):
        ds = AIInsightsDataSource()
        schema = ds.get_schema()
        assert "metric_type" in schema


# ---------------------------------------------------------------------------
# CLI commands
# ---------------------------------------------------------------------------


class TestAICLICommands:
    """Tests for AI CLI commands output when AI is not available."""

    def _invoke(self, args):
        from todo_cli.cli.ai_commands import ai_group
        runner = CliRunner()
        return runner.invoke(ai_group, args, catch_exceptions=False)

    @patch("todo_cli.cli.ai_commands._get_assistant")
    def test_suggest_not_available(self, mock_get):
        mock_get.return_value = (None, "AI provider (OpenAIProvider) is not available.")
        result = self._invoke(["suggest"])
        assert "not available" in result.output

    @patch("todo_cli.cli.ai_commands._get_assistant")
    def test_ask_not_available(self, mock_get):
        mock_get.return_value = (None, "AI provider is not available.")
        result = self._invoke(["ask", "what is overdue?"])
        assert "not available" in result.output

    @patch("todo_cli.cli.ai_commands._get_assistant")
    def test_categorize_not_available(self, mock_get):
        mock_get.return_value = (None, "AI provider is not available.")
        result = self._invoke(["categorize", "buy milk"])
        assert "not available" in result.output

    @patch("todo_cli.cli.ai_commands._get_assistant")
    def test_summary_not_available(self, mock_get):
        mock_get.return_value = (None, "AI provider is not available.")
        result = self._invoke(["summary"])
        assert "not available" in result.output

    @patch("todo_cli.cli.ai_commands._get_assistant")
    @patch("todo_cli.cli.ai_commands._load_todos")
    def test_suggest_with_mock_provider(self, mock_load, mock_get):
        mock_assistant = TaskAIAssistant(MockProvider(response="Do task X first."))
        mock_get.return_value = (mock_assistant, None)
        mock_load.return_value = [_make_todo(text="Task X", priority=Priority.HIGH)]
        result = self._invoke(["suggest"])
        assert "Do task X first" in result.output

    @patch("todo_cli.cli.ai_commands._get_assistant")
    @patch("todo_cli.cli.ai_commands._load_todos")
    def test_ask_with_mock_provider(self, mock_load, mock_get):
        mock_assistant = TaskAIAssistant(MockProvider(response="You have 1 task."))
        mock_get.return_value = (mock_assistant, None)
        mock_load.return_value = [_make_todo()]
        result = self._invoke(["ask", "how many tasks?"])
        assert "1 task" in result.output

    def test_status_command(self):
        """Status command should run without error and show provider info."""
        with patch("todo_cli.config.get_config") as mock_config:
            mock_cfg = MagicMock()
            mock_cfg.ai_provider = "openai"
            mock_cfg.ai_model = "gpt-4o-mini"
            mock_cfg.ai_openai_api_key = None
            mock_cfg.ai_ollama_host = "http://localhost:11434"
            mock_config.return_value = mock_cfg
            result = self._invoke(["status"])
            assert "openai" in result.output.lower()


# ---------------------------------------------------------------------------
# create_assistant_from_config
# ---------------------------------------------------------------------------


class TestCreateAssistantFromConfig:
    """Tests for the factory function."""

    @patch("todo_cli.services.ai_assistant.get_config")
    def test_creates_openai_assistant(self, mock_config):
        cfg = MagicMock()
        cfg.ai_provider = "openai"
        cfg.ai_model = "gpt-4o-mini"
        cfg.ai_openai_api_key = "sk-test"
        mock_config.return_value = cfg

        assistant = create_assistant_from_config()
        assert assistant is not None
        assert isinstance(assistant.provider, OpenAIProvider)

    @patch("todo_cli.services.ai_assistant.get_config")
    def test_creates_ollama_assistant(self, mock_config):
        cfg = MagicMock()
        cfg.ai_provider = "ollama"
        cfg.ai_ollama_model = "llama3.2"
        cfg.ai_ollama_host = "http://localhost:11434"
        mock_config.return_value = cfg

        assistant = create_assistant_from_config()
        assert assistant is not None
        assert isinstance(assistant.provider, OllamaProvider)
