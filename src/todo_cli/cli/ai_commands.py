"""AI-powered CLI commands for Todo CLI."""

import click
from rich.console import Console
from rich.panel import Panel
from rich.text import Text


def _get_console() -> Console:
    """Get a Rich console instance."""
    return Console()


def _get_assistant():
    """Create an AI assistant from config, returning (assistant, error_msg)."""
    try:
        from ..services.ai_assistant import create_assistant_from_config
        assistant = create_assistant_from_config()
        if assistant is None:
            return None, "Could not create AI assistant from configuration."
        if not assistant.provider.is_available():
            provider_name = type(assistant.provider).__name__
            return None, (
                f"AI provider ({provider_name}) is not available. "
                "Install the required package (e.g. `pip install todo-cli[ai]`) "
                "and ensure credentials are configured."
            )
        return assistant, None
    except Exception as e:
        return None, f"Error initialising AI assistant: {e}"


def _load_todos():
    """Load all todos from storage."""
    from ..config import get_config
    from ..storage import Storage

    config = get_config()
    storage = Storage(config)
    return storage.get_all_todos()


@click.group("ai")
def ai_group():
    """AI-powered task assistance."""
    pass


@ai_group.command("suggest")
@click.option("--context", "-c", default=None, help="Current context (e.g., 'work', 'home')")
@click.option("--energy", "-e", type=click.Choice(["high", "medium", "low"]), default=None)
@click.option("--time", "-t", "available_time", type=int, default=None, help="Available minutes")
def suggest(context, energy, available_time):
    """Get AI suggestions for what to work on next."""
    console = _get_console()
    assistant, error = _get_assistant()
    if error:
        console.print(f"[red]{error}[/red]")
        return

    todos = _load_todos()
    if not todos:
        console.print("[yellow]No tasks found.[/yellow]")
        return

    # Build extra context string
    parts = []
    if context:
        parts.append(f"context: {context}")
    if energy:
        parts.append(f"energy level: {energy}")
    if available_time:
        parts.append(f"available time: {available_time} minutes")
    extra_context = ", ".join(parts) if parts else None

    with console.status("[bold green]Thinking..."):
        result = assistant.suggest_next_task(todos, context=extra_context)

    console.print(Panel(result, title="AI Suggestion", border_style="green"))


@ai_group.command("ask")
@click.argument("question")
def ask(question):
    """Ask a question about your tasks in natural language."""
    console = _get_console()
    assistant, error = _get_assistant()
    if error:
        console.print(f"[red]{error}[/red]")
        return

    todos = _load_todos()

    with console.status("[bold green]Thinking..."):
        result = assistant.smart_query(question, todos)

    console.print(Panel(result, title="AI Answer", border_style="blue"))


@ai_group.command("categorize")
@click.argument("text")
def categorize(text):
    """Auto-categorize a task with AI-suggested tags, priority, project."""
    console = _get_console()
    assistant, error = _get_assistant()
    if error:
        console.print(f"[red]{error}[/red]")
        return

    with console.status("[bold green]Categorizing..."):
        result = assistant.auto_categorize(text)

    console.print(Panel.fit(
        f"[bold]Tags:[/bold]     {', '.join(result.get('tags', [])) or '(none)'}\n"
        f"[bold]Priority:[/bold] {result.get('priority', 'medium')}\n"
        f"[bold]Project:[/bold]  {result.get('project', 'inbox')}\n"
        f"[bold]Context:[/bold]  {result.get('context', '') or '(none)'}",
        title="AI Categorization",
        border_style="cyan",
    ))


@ai_group.command("summary")
@click.option("--project", "-p", default=None, help="Summarize a specific project")
def summary(project):
    """Get an AI-generated summary of your task status."""
    console = _get_console()
    assistant, error = _get_assistant()
    if error:
        console.print(f"[red]{error}[/red]")
        return

    todos = _load_todos()
    if project:
        todos = [t for t in todos if t.project == project]

    if not todos:
        console.print("[yellow]No tasks found.[/yellow]")
        return

    with console.status("[bold green]Summarizing..."):
        result = assistant.summarize_tasks(todos)

    title = f"Task Summary — {project}" if project else "Task Summary"
    console.print(Panel(result, title=title, border_style="magenta"))


@ai_group.command("status")
def status():
    """Check AI provider availability."""
    console = _get_console()

    from ..config import get_config
    config = get_config()

    provider_name = getattr(config, "ai_provider", "openai")
    console.print(f"[bold]Configured provider:[/bold] {provider_name}")
    console.print(f"[bold]Model:[/bold] {getattr(config, 'ai_model', 'gpt-4o-mini')}")

    # Check OpenAI
    try:
        from ..services.ai_assistant import OpenAIProvider
        openai_prov = OpenAIProvider(
            api_key=getattr(config, "ai_openai_api_key", None),
        )
        if openai_prov.is_available():
            console.print("[green]OpenAI: available[/green]")
        else:
            console.print("[yellow]OpenAI: not available (missing package or API key)[/yellow]")
    except Exception as e:
        console.print(f"[red]OpenAI: error ({e})[/red]")

    # Check Ollama
    try:
        from ..services.ai_assistant import OllamaProvider
        ollama_prov = OllamaProvider(
            host=getattr(config, "ai_ollama_host", "http://localhost:11434"),
        )
        if ollama_prov.is_available():
            console.print("[green]Ollama: available[/green]")
        else:
            console.print("[yellow]Ollama: not available (missing package)[/yellow]")
    except Exception as e:
        console.print(f"[red]Ollama: error ({e})[/red]")
