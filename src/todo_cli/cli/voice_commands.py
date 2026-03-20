"""CLI commands for voice input."""

import click
from rich.console import Console
from rich.panel import Panel
from rich.text import Text


@click.group("voice")
def voice_group():
    """Voice input for task creation."""
    pass


@voice_group.command("add")
@click.option("--duration", "-d", default=5.0, help="Recording duration in seconds")
@click.option("--provider", "-p", type=click.Choice(["local", "cloud"]), default="local",
              help="Transcription provider")
def voice_add(duration, provider):
    """Create a task using voice input.

    Records audio from your microphone and transcribes it into a task.
    Requires voice dependencies: pip install todo-cli[voice]
    """
    from ..services.voice_input import VoiceToTask, LocalTranscriber, CloudTranscriber, AudioRecorder
    from ..config import get_config
    from ..storage import Storage
    from ..domain import parse_task_input, TaskBuilder

    console = Console()
    config = get_config()

    # Check dependencies
    recorder = AudioRecorder()
    if not recorder.is_available():
        console.print("[red]Voice input requires audio dependencies.[/red]")
        console.print("Install with: [bold]pip install todo-cli\\[voice][/bold]")
        return

    # Set up transcriber
    if provider == "cloud":
        api_key = getattr(config, 'voice_openai_api_key', None)
        if not api_key:
            console.print("[red]Cloud transcription requires an OpenAI API key.[/red]")
            console.print("Set voice_openai_api_key in your config.")
            return
        transcriber = CloudTranscriber(api_key=api_key)
    else:
        transcriber = LocalTranscriber(
            model_path=getattr(config, 'voice_model_path', None),
            language=getattr(config, 'voice_language', 'en-us')
        )

    if not transcriber.is_available():
        console.print(f"[red]{provider} transcriber is not available.[/red]")
        console.print("Install voice dependencies: [bold]pip install todo-cli\\[voice][/bold]")
        return

    voice = VoiceToTask(transcriber=transcriber, recorder=recorder)

    # Record
    console.print(Panel(
        f"[bold green]Recording for {duration} seconds...[/bold green]\n"
        "Speak your task now!",
        title="Voice Input",
        border_style="green"
    ))

    result = voice.record_and_transcribe(duration=duration)

    if not result or not result.text.strip():
        console.print("[yellow]No speech detected. Please try again.[/yellow]")
        return

    # Show transcription
    console.print(f"\n[bold]Transcription:[/bold] {result.text}")
    console.print(f"[dim]Confidence: {result.confidence:.0%} | Duration: {result.duration_seconds:.1f}s[/dim]")

    # Parse as task
    parsed, errors, suggestions = parse_task_input(result.text, config)
    console.print(f"\n[bold]Parsed task:[/bold] {parsed.text}")
    if parsed.tags:
        console.print(f"  Tags: {', '.join(parsed.tags)}")
    if parsed.due_date:
        console.print(f"  Due: {parsed.due_date}")
    if parsed.priority:
        console.print(f"  Priority: {parsed.priority.value}")

    # Confirm
    if click.confirm("\nCreate this task?", default=True):
        storage = Storage(config)
        target_project = parsed.project or config.default_project
        proj, existing_todos = storage.load_project(target_project)

        if existing_todos:
            next_id = max(todo.id for todo in existing_todos) + 1
        else:
            next_id = 1

        builder = TaskBuilder(config)
        todo = builder.build(parsed, next_id)
        todo.project = target_project

        existing_todos.append(todo)
        if storage.save_project(proj, existing_todos):
            console.print("[bold green]Task created successfully![/bold green]")
        else:
            console.print("[red]Failed to save task.[/red]")
    else:
        console.print("[yellow]Task creation cancelled.[/yellow]")


@voice_group.command("status")
def voice_status():
    """Check voice input availability and configuration."""
    from ..services.voice_input import AudioRecorder, LocalTranscriber, CloudTranscriber
    from ..config import get_config

    console = Console()
    config = get_config()

    console.print(Panel("[bold]Voice Input Status[/bold]", border_style="blue"))

    # Check audio recording
    recorder = AudioRecorder()
    if recorder.is_available():
        console.print("[green]Audio recording: Available[/green]")
    else:
        console.print("[red]Audio recording: Not available[/red]")
        console.print("  Install: [bold]pip install todo-cli\\[voice][/bold]")

    # Check local transcription
    local = LocalTranscriber()
    if local.is_available():
        console.print("[green]Local transcription (Vosk): Available[/green]")
    else:
        console.print("[yellow]Local transcription (Vosk): Not installed[/yellow]")
        console.print("  Install: [bold]pip install todo-cli\\[voice][/bold]")

    # Check cloud transcription
    api_key = getattr(config, 'voice_openai_api_key', None)
    cloud = CloudTranscriber(api_key=api_key)
    if cloud.is_available():
        console.print("[green]Cloud transcription (OpenAI Whisper): Available[/green]")
    else:
        if api_key:
            console.print("[yellow]Cloud transcription: OpenAI package not installed[/yellow]")
        else:
            console.print("[yellow]Cloud transcription: No API key configured[/yellow]")
        console.print("  Install: [bold]pip install todo-cli\\[voice-cloud][/bold]")
        console.print("  Set voice_openai_api_key in config")


@voice_group.command("test")
@click.option("--duration", "-d", default=3.0, help="Recording duration in seconds")
def voice_test(duration):
    """Test voice recording and transcription without creating a task."""
    from ..services.voice_input import VoiceToTask, LocalTranscriber, CloudTranscriber, AudioRecorder
    from ..config import get_config

    console = Console()
    config = get_config()

    recorder = AudioRecorder()
    if not recorder.is_available():
        console.print("[red]Audio recording not available. Install: pip install todo-cli\\[voice][/red]")
        return

    # Try to find any available transcriber
    voice = VoiceToTask(recorder=recorder)
    transcriber = voice.get_available_transcriber(config)

    if not transcriber:
        console.print("[red]No transcription backend available.[/red]")
        console.print("Install voice or voice-cloud dependencies.")
        return

    voice.transcriber = transcriber

    console.print(f"[bold]Recording for {duration} seconds...[/bold]")
    result = voice.record_and_transcribe(duration=duration)

    if result and result.text:
        console.print(f"\n[green]Transcription:[/green] {result.text}")
        console.print(f"[dim]Confidence: {result.confidence:.0%} | Duration: {result.duration_seconds:.1f}s[/dim]")
    else:
        console.print("[yellow]No speech detected.[/yellow]")
