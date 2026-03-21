"""AI/LLM integration service for Todo CLI.

Provides AI-powered task assistance including suggestions, categorization,
natural language querying, and summarization through pluggable AI providers.
"""

import json
import os
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from ..config import get_config
from ..domain.todo import Todo, TodoStatus, Priority


class AIProvider(ABC):
    """Abstract base class for AI providers."""

    @abstractmethod
    def generate(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        """Generate a response from the AI model.

        Args:
            prompt: The user prompt to send.
            system_prompt: Optional system-level instruction.

        Returns:
            The generated text response.
        """

    @abstractmethod
    def is_available(self) -> bool:
        """Check whether this provider is ready to use.

        Returns:
            True if the required SDK is installed and configured.
        """


class OpenAIProvider(AIProvider):
    """AI provider backed by the OpenAI API."""

    def __init__(self, model: str = "gpt-4o-mini", api_key: Optional[str] = None):
        self.model = model
        self._api_key = api_key or os.environ.get("OPENAI_API_KEY")

    def is_available(self) -> bool:
        """Check if the openai package is installed and an API key is set."""
        try:
            import openai  # noqa: F401
        except ImportError:
            return False
        return bool(self._api_key)

    def generate(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        import openai

        client = openai.OpenAI(api_key=self._api_key)
        messages: list[dict[str, str]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        response = client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=0.7,
            max_tokens=1024,
        )
        return response.choices[0].message.content or ""


class OllamaProvider(AIProvider):
    """AI provider backed by a local Ollama instance."""

    def __init__(
        self,
        model: str = "llama3.2",
        host: str = "http://localhost:11434",
    ):
        self.model = model
        self.host = host

    def is_available(self) -> bool:
        """Check if the ollama package is installed."""
        try:
            import ollama  # noqa: F401
        except ImportError:
            return False
        return True

    def generate(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        import ollama

        client = ollama.Client(host=self.host)
        messages: list[dict[str, str]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        response = client.chat(model=self.model, messages=messages)
        return response["message"]["content"]


class TaskAIAssistant:
    """AI-powered task assistance using a pluggable AI provider."""

    SYSTEM_PROMPT = (
        "You are a productivity assistant integrated into a command-line todo application. "
        "Be concise and actionable. When asked to return structured data, respond ONLY with "
        "valid JSON and no extra text."
    )

    def __init__(self, provider: AIProvider):
        self.provider = provider

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------

    def suggest_next_task(self, todos: List[Todo], context: Optional[str] = None) -> str:
        """Analyze pending tasks and suggest what to work on next.

        Args:
            todos: All current tasks.
            context: Optional extra context (e.g. energy level, available time).

        Returns:
            A human-readable suggestion string.
        """
        task_context = self._build_task_context(todos)
        extra = f"\nAdditional context: {context}" if context else ""
        prompt = (
            f"Here are my current tasks:\n{task_context}{extra}\n\n"
            "Based on priority, due dates, and status, suggest which task I should "
            "work on next and briefly explain why."
        )
        return self.provider.generate(prompt, system_prompt=self.SYSTEM_PROMPT)

    def auto_categorize(self, text: str) -> dict:
        """Suggest tags, priority, project, and context for a raw task description.

        Args:
            text: Raw task text to categorize.

        Returns:
            Dict with keys: tags (list[str]), priority (str), project (str), context (str).
        """
        prompt = (
            f'Categorize this task: "{text}"\n\n'
            "Return a JSON object with exactly these keys:\n"
            '  "tags": list of relevant tag strings,\n'
            '  "priority": one of "critical", "high", "medium", "low",\n'
            '  "project": a short project name,\n'
            '  "context": one of "work", "home", "phone", "office", or empty string.\n'
            "Respond ONLY with valid JSON."
        )
        raw = self.provider.generate(prompt, system_prompt=self.SYSTEM_PROMPT)
        return self._parse_json_response(raw, default={
            "tags": [],
            "priority": "medium",
            "project": "inbox",
            "context": "",
        })

    def smart_query(self, question: str, todos: List[Todo]) -> str:
        """Answer a natural-language question about the user's tasks.

        Args:
            question: The question to answer.
            todos: All current tasks for context.

        Returns:
            A human-readable answer.
        """
        task_context = self._build_task_context(todos)
        prompt = (
            f"Here are my current tasks:\n{task_context}\n\n"
            f"Question: {question}\n\n"
            "Answer the question based on the task data above."
        )
        return self.provider.generate(prompt, system_prompt=self.SYSTEM_PROMPT)

    def summarize_tasks(self, todos: List[Todo]) -> str:
        """Generate a human-readable summary of current task status.

        Args:
            todos: All current tasks.

        Returns:
            A summary string.
        """
        task_context = self._build_task_context(todos)
        prompt = (
            f"Here are my current tasks:\n{task_context}\n\n"
            "Provide a concise summary covering: total tasks, completion status, "
            "overdue items, priority distribution, and any notable observations."
        )
        return self.provider.generate(prompt, system_prompt=self.SYSTEM_PROMPT)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_task_context(self, todos: List[Todo]) -> str:
        """Serialize relevant task data into a compact text block for prompts.

        Args:
            todos: List of Todo objects.

        Returns:
            A multi-line string summarising each task.
        """
        if not todos:
            return "(no tasks)"

        lines: list[str] = []
        for t in todos:
            parts = [f"[{t.status.value}]", f"P:{t.priority.value}", t.text]
            if t.due_date:
                parts.append(f"due:{t.due_date.strftime('%Y-%m-%d')}")
            if t.tags:
                parts.append(f"tags:{','.join(t.tags)}")
            if t.project and t.project != "inbox":
                parts.append(f"project:{t.project}")
            if t.context:
                ctx = t.context if isinstance(t.context, list) else [t.context]
                parts.append(f"context:{','.join(ctx)}")
            lines.append(" | ".join(parts))
        return "\n".join(lines)

    @staticmethod
    def _parse_json_response(raw: str, default: dict) -> dict:
        """Attempt to parse a JSON response, returning *default* on failure."""
        # Strip markdown code fences if present
        text = raw.strip()
        if text.startswith("```"):
            lines = text.splitlines()
            # Remove first and last lines (the fences)
            lines = [l for l in lines if not l.strip().startswith("```")]
            text = "\n".join(lines).strip()
        try:
            result = json.loads(text)
            if isinstance(result, dict):
                return result
        except (json.JSONDecodeError, ValueError):
            pass
        return dict(default)


# ---------------------------------------------------------------------------
# Dashboard data source
# ---------------------------------------------------------------------------


class AIInsightsDataSource:
    """Dashboard data source for AI-generated insights.

    Implements the same interface as ``DataSource`` from the dashboard module
    but avoids an import-time dependency so the AI module stays optional.
    """

    def __init__(self, assistant: Optional[TaskAIAssistant] = None):
        self.name = "ai_insights"
        self._assistant = assistant

    def _get_assistant(self) -> Optional[TaskAIAssistant]:
        if self._assistant is not None:
            return self._assistant
        # Attempt to build one from config
        try:
            assistant = create_assistant_from_config()
            if assistant and assistant.provider.is_available():
                self._assistant = assistant
                return assistant
        except Exception:
            pass
        return None

    def fetch_data(self, params: Dict[str, Any]) -> Any:
        """Fetch AI insight data for a dashboard widget."""
        from ..services.dashboard import WidgetData

        metric_type = params.get("metric_type", "ai_suggestion")
        todos: List[Todo] = params.get("todos", [])

        assistant = self._get_assistant()
        if assistant is None:
            return WidgetData(
                value="AI provider not available",
                label="AI Insights",
                icon="🤖",
            )

        try:
            if metric_type == "ai_suggestion":
                suggestion = assistant.suggest_next_task(todos)
                return WidgetData(
                    value=suggestion,
                    label="AI Suggestion",
                    icon="🤖",
                )
            elif metric_type == "task_summary":
                summary = assistant.summarize_tasks(todos)
                return WidgetData(
                    value=summary,
                    label="Task Summary",
                    icon="📋",
                )
            else:
                return WidgetData(value="Unknown metric type", label="AI Insights")
        except Exception as e:
            return WidgetData(
                value=f"Error: {e}",
                label="AI Insights",
                icon="⚠️",
            )

    def get_schema(self) -> Dict[str, Any]:
        """Configuration schema for AI insights data source."""
        return {
            "metric_type": {
                "type": "select",
                "options": ["ai_suggestion", "task_summary"],
                "default": "ai_suggestion",
                "label": "Metric Type",
            }
        }


# ---------------------------------------------------------------------------
# Factory helper
# ---------------------------------------------------------------------------


def create_assistant_from_config() -> Optional[TaskAIAssistant]:
    """Create a ``TaskAIAssistant`` based on the current application config.

    Returns:
        A configured assistant, or ``None`` if no provider is available.
    """
    config = get_config()
    provider_name = getattr(config, "ai_provider", "openai")

    if provider_name == "ollama":
        provider: AIProvider = OllamaProvider(
            model=getattr(config, "ai_ollama_model", "llama3.2"),
            host=getattr(config, "ai_ollama_host", "http://localhost:11434"),
        )
    else:
        api_key = getattr(config, "ai_openai_api_key", None) or os.environ.get("OPENAI_API_KEY")
        provider = OpenAIProvider(
            model=getattr(config, "ai_model", "gpt-4o-mini"),
            api_key=api_key,
        )

    return TaskAIAssistant(provider)
