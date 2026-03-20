"""Tests for the voice input service and CLI commands."""

import pytest
from unittest.mock import patch, MagicMock
from click.testing import CliRunner

from todo_cli.services.voice_input import (
    TranscriptionResult,
    LocalTranscriber,
    CloudTranscriber,
    AudioRecorder,
    VoiceToTask,
    VoiceTranscriber,
)


class TestTranscriptionResult:
    """Test the TranscriptionResult dataclass."""

    def test_creation(self):
        result = TranscriptionResult(
            text="buy groceries tomorrow",
            confidence=0.85,
            language="en-us",
            duration_seconds=3.2,
        )
        assert result.text == "buy groceries tomorrow"
        assert result.confidence == 0.85
        assert result.language == "en-us"
        assert result.duration_seconds == 3.2

    def test_empty_text(self):
        result = TranscriptionResult(text="", confidence=0.0, language="en", duration_seconds=0.0)
        assert result.text == ""
        assert result.confidence == 0.0


class TestLocalTranscriber:
    """Test local (Vosk) transcriber."""

    def test_is_available_returns_false_without_vosk(self):
        transcriber = LocalTranscriber()
        # vosk is not installed in the test environment
        assert transcriber.is_available() is False

    def test_default_language(self):
        transcriber = LocalTranscriber()
        assert transcriber.language == "en-us"

    def test_custom_model_path(self):
        transcriber = LocalTranscriber(model_path="/tmp/my-model", language="de")
        assert transcriber.model_path == "/tmp/my-model"
        assert transcriber.language == "de"


class TestCloudTranscriber:
    """Test cloud (OpenAI Whisper) transcriber."""

    def test_is_available_returns_false_without_api_key(self):
        transcriber = CloudTranscriber(api_key=None)
        assert transcriber.is_available() is False

    def test_is_available_returns_false_without_openai(self):
        # Even with an API key, if openai isn't installed it should be False
        transcriber = CloudTranscriber(api_key="sk-test-key")
        # openai is not installed in test env
        assert transcriber.is_available() is False

    def test_default_language(self):
        transcriber = CloudTranscriber()
        assert transcriber.language == "en"


class TestAudioRecorder:
    """Test audio recorder."""

    def test_is_available_returns_false_without_sounddevice(self):
        recorder = AudioRecorder()
        # sounddevice is not installed in the test environment
        assert recorder.is_available() is False

    def test_default_settings(self):
        recorder = AudioRecorder()
        assert recorder.sample_rate == 16000
        assert recorder.channels == 1

    def test_custom_settings(self):
        recorder = AudioRecorder(sample_rate=44100, channels=2)
        assert recorder.sample_rate == 44100
        assert recorder.channels == 2


class TestVoiceToTask:
    """Test the VoiceToTask orchestrator."""

    def test_get_available_transcriber_returns_none_when_nothing_available(self):
        voice = VoiceToTask()
        result = voice.get_available_transcriber()
        assert result is None

    def test_get_available_transcriber_returns_none_with_config(self):
        config = MagicMock()
        config.voice_openai_api_key = None
        config.voice_model_path = None
        config.voice_language = "en-us"
        voice = VoiceToTask()
        result = voice.get_available_transcriber(config)
        assert result is None

    def test_get_available_transcriber_uses_injected_transcriber(self):
        mock_transcriber = MagicMock(spec=VoiceTranscriber)
        mock_transcriber.is_available.return_value = True
        voice = VoiceToTask(transcriber=mock_transcriber)
        result = voice.get_available_transcriber()
        assert result is mock_transcriber

    def test_transcribe_audio_with_mock_transcriber(self):
        mock_transcriber = MagicMock(spec=VoiceTranscriber)
        mock_transcriber.is_available.return_value = True
        mock_transcriber.transcribe.return_value = TranscriptionResult(
            text="hello world",
            confidence=0.9,
            language="en-us",
            duration_seconds=2.0,
        )
        voice = VoiceToTask(transcriber=mock_transcriber)
        result = voice.transcribe_audio(b"\x00" * 32000)
        assert result is not None
        assert result.text == "hello world"
        assert result.confidence == 0.9

    def test_transcribe_audio_returns_none_without_transcriber(self):
        voice = VoiceToTask()
        result = voice.transcribe_audio(b"\x00" * 100)
        assert result is None

    def test_record_and_transcribe_returns_none_without_recorder(self):
        voice = VoiceToTask()
        # recorder.is_available() will be False since sounddevice isn't installed
        result = voice.record_and_transcribe()
        assert result is None

    def test_record_and_transcribe_returns_none_without_transcriber(self):
        mock_recorder = MagicMock(spec=AudioRecorder)
        mock_recorder.is_available.return_value = True
        voice = VoiceToTask(recorder=mock_recorder)
        # No transcriber set
        result = voice.record_and_transcribe()
        assert result is None

    def test_record_and_transcribe_full_pipeline(self):
        mock_recorder = MagicMock(spec=AudioRecorder)
        mock_recorder.is_available.return_value = True
        mock_recorder.sample_rate = 16000
        mock_recorder.record_seconds.return_value = b"\x00" * 32000

        mock_transcriber = MagicMock(spec=VoiceTranscriber)
        mock_transcriber.is_available.return_value = True
        mock_transcriber.transcribe.return_value = TranscriptionResult(
            text="buy milk tomorrow",
            confidence=0.8,
            language="en-us",
            duration_seconds=1.0,
        )

        voice = VoiceToTask(transcriber=mock_transcriber, recorder=mock_recorder)
        result = voice.record_and_transcribe(duration=2.0)

        assert result is not None
        assert result.text == "buy milk tomorrow"
        mock_recorder.record_seconds.assert_called_once_with(2.0)
        mock_transcriber.transcribe.assert_called_once()


class TestVoiceCLICommands:
    """Test voice CLI commands output correct messages when deps are missing."""

    def test_voice_status_shows_unavailable(self):
        from todo_cli.cli.voice_commands import voice_group

        runner = CliRunner()
        result = runner.invoke(voice_group, ["status"])
        # Since sounddevice/vosk/openai are not installed:
        assert "Not available" in result.output or "Not installed" in result.output or "not available" in result.output.lower()

    def test_voice_add_shows_missing_deps(self):
        from todo_cli.cli.voice_commands import voice_group

        runner = CliRunner()
        result = runner.invoke(voice_group, ["add"])
        assert "requires audio dependencies" in result.output or "not available" in result.output.lower()

    def test_voice_test_shows_missing_deps(self):
        from todo_cli.cli.voice_commands import voice_group

        runner = CliRunner()
        result = runner.invoke(voice_group, ["test"])
        assert "not available" in result.output.lower() or "Install" in result.output

    def test_voice_group_help(self):
        from todo_cli.cli.voice_commands import voice_group

        runner = CliRunner()
        result = runner.invoke(voice_group, ["--help"])
        assert result.exit_code == 0
        assert "Voice input" in result.output

    def test_voice_add_help(self):
        from todo_cli.cli.voice_commands import voice_group

        runner = CliRunner()
        result = runner.invoke(voice_group, ["add", "--help"])
        assert result.exit_code == 0
        assert "Recording duration" in result.output or "duration" in result.output.lower()
