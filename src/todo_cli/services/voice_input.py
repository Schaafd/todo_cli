"""Voice input service for speech-to-task creation.

Supports local transcription via Vosk and cloud transcription via OpenAI Whisper.
Voice dependencies are optional — the module gracefully handles missing packages.
"""

import io
import wave
import tempfile
from abc import ABC, abstractmethod
from typing import Optional, Tuple
from dataclasses import dataclass
from pathlib import Path


@dataclass
class TranscriptionResult:
    """Result of a voice transcription."""
    text: str
    confidence: float  # 0.0 to 1.0
    language: str
    duration_seconds: float


class VoiceTranscriber(ABC):
    """Abstract base for voice transcription backends."""

    @abstractmethod
    def transcribe(self, audio_data: bytes, sample_rate: int = 16000) -> TranscriptionResult:
        """Transcribe audio data to text."""
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Check if this transcriber's dependencies are installed."""
        pass


class LocalTranscriber(VoiceTranscriber):
    """Local transcription using Vosk."""

    def __init__(self, model_path: Optional[str] = None, language: str = "en-us"):
        self.model_path = model_path
        self.language = language
        self._model = None

    def is_available(self) -> bool:
        try:
            import vosk  # noqa: F401
            return True
        except ImportError:
            return False

    def _get_model(self):
        if self._model is None:
            import vosk
            if self.model_path:
                self._model = vosk.Model(self.model_path)
            else:
                self._model = vosk.Model(lang=self.language)
        return self._model

    def transcribe(self, audio_data: bytes, sample_rate: int = 16000) -> TranscriptionResult:
        import vosk
        import json

        model = self._get_model()
        recognizer = vosk.KaldiRecognizer(model, sample_rate)

        recognizer.AcceptWaveform(audio_data)
        result = json.loads(recognizer.FinalResult())

        text = result.get("text", "")
        duration = len(audio_data) / (sample_rate * 2)  # 16-bit audio = 2 bytes per sample

        return TranscriptionResult(
            text=text,
            confidence=0.8 if text else 0.0,
            language=self.language,
            duration_seconds=duration
        )


class CloudTranscriber(VoiceTranscriber):
    """Cloud transcription using OpenAI Whisper API."""

    def __init__(self, api_key: Optional[str] = None, language: str = "en"):
        self.api_key = api_key
        self.language = language

    def is_available(self) -> bool:
        try:
            import openai  # noqa: F401
            return self.api_key is not None
        except ImportError:
            return False

    def transcribe(self, audio_data: bytes, sample_rate: int = 16000) -> TranscriptionResult:
        import openai

        # Write audio to a temporary WAV file for the API
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            with wave.open(tmp.name, "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(sample_rate)
                wf.writeframes(audio_data)
            tmp_path = tmp.name

        try:
            client = openai.OpenAI(api_key=self.api_key)
            with open(tmp_path, "rb") as audio_file:
                response = client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file,
                    language=self.language
                )

            text = response.text
            duration = len(audio_data) / (sample_rate * 2)

            return TranscriptionResult(
                text=text,
                confidence=0.9 if text else 0.0,
                language=self.language,
                duration_seconds=duration
            )
        finally:
            Path(tmp_path).unlink(missing_ok=True)


class AudioRecorder:
    """Records audio from the microphone."""

    def __init__(self, sample_rate: int = 16000, channels: int = 1):
        self.sample_rate = sample_rate
        self.channels = channels
        self._recording = False
        self._frames: list = []

    def is_available(self) -> bool:
        """Check if audio recording dependencies are installed."""
        try:
            import sounddevice  # noqa: F401
            return True
        except ImportError:
            return False

    def record_seconds(self, duration: float) -> bytes:
        """Record audio for a fixed number of seconds."""
        import sounddevice as sd
        import numpy as np

        audio = sd.rec(
            int(duration * self.sample_rate),
            samplerate=self.sample_rate,
            channels=self.channels,
            dtype="int16"
        )
        sd.wait()
        return audio.tobytes()

    def start_recording(self) -> None:
        """Start continuous recording (non-blocking)."""
        import sounddevice as sd

        self._frames = []
        self._recording = True

        def callback(indata, frames, time, status):
            if self._recording:
                self._frames.append(indata.copy())

        self._stream = sd.InputStream(
            samplerate=self.sample_rate,
            channels=self.channels,
            dtype="int16",
            callback=callback
        )
        self._stream.start()

    def stop_recording(self) -> bytes:
        """Stop recording and return audio data."""
        import numpy as np

        self._recording = False
        if hasattr(self, '_stream'):
            self._stream.stop()
            self._stream.close()

        if self._frames:
            audio = np.concatenate(self._frames)
            return audio.tobytes()
        return b""


class VoiceToTask:
    """Orchestrates voice recording, transcription, and task creation."""

    def __init__(self, transcriber: Optional[VoiceTranscriber] = None,
                 recorder: Optional[AudioRecorder] = None):
        self.transcriber = transcriber
        self.recorder = recorder or AudioRecorder()

    def get_available_transcriber(self, config=None) -> Optional[VoiceTranscriber]:
        """Get the best available transcriber based on installed dependencies."""
        if self.transcriber and self.transcriber.is_available():
            return self.transcriber

        # Try cloud first if API key is configured
        if config and getattr(config, 'voice_openai_api_key', None):
            cloud = CloudTranscriber(api_key=config.voice_openai_api_key)
            if cloud.is_available():
                return cloud

        # Fall back to local
        local = LocalTranscriber(
            model_path=getattr(config, 'voice_model_path', None) if config else None,
            language=getattr(config, 'voice_language', 'en-us') if config else 'en-us'
        )
        if local.is_available():
            return local

        return None

    def transcribe_audio(self, audio_data: bytes, sample_rate: int = 16000) -> Optional[TranscriptionResult]:
        """Transcribe audio data using the configured transcriber."""
        transcriber = self.transcriber
        if not transcriber or not transcriber.is_available():
            return None
        return transcriber.transcribe(audio_data, sample_rate)

    def record_and_transcribe(self, duration: float = 5.0) -> Optional[TranscriptionResult]:
        """Record audio and transcribe it."""
        if not self.recorder.is_available():
            return None

        transcriber = self.transcriber
        if not transcriber or not transcriber.is_available():
            return None

        audio_data = self.recorder.record_seconds(duration)
        return transcriber.transcribe(audio_data, self.recorder.sample_rate)
