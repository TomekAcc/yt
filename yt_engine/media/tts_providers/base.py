from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path

from ...models import WordTiming


@dataclass
class TTSResult:
    audio_path: Path
    # None when the provider doesn't return alignment data natively; the
    # subtitle stage falls back to forced alignment (faster-whisper) in
    # that case.
    word_timings: list[WordTiming] | None = None


class TTSProvider(ABC):
    # Container format this provider writes -- callers (pipeline.py) name
    # the output file with this extension since providers differ (e.g.
    # Gemini returns raw PCM wrapped as .wav; ElevenLabs/OpenAI return .mp3).
    file_extension: str = "mp3"

    @abstractmethod
    def synthesize(self, text: str, out_path: Path) -> TTSResult:
        ...
