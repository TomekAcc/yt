"""Lightweight stand-ins for provider clients, used so content/pipeline
tests never hit a real network or require an API key. They only need to
satisfy the duck-typed interface each real client exposes.
"""
from __future__ import annotations

from pathlib import Path

from yt_engine.media.image_providers.base import ImageProvider
from yt_engine.media.tts_providers.base import TTSProvider, TTSResult
from yt_engine.models import UploadResult, WordTiming, YouTubeMetadata


class FakeLLMClient:
    def __init__(self, responses: list):
        self._responses = list(responses)

    def complete_json(self, system: str, prompt: str, *, max_tokens: int = 4096):
        if not self._responses:
            raise AssertionError("FakeLLMClient ran out of queued responses")
        return self._responses.pop(0)

    def complete_text(self, system: str, prompt: str, *, max_tokens: int = 4096) -> str:
        return self.complete_json(system, prompt, max_tokens=max_tokens)


class FakeImageProvider(ImageProvider):
    def generate(self, prompt: str, out_path: Path, *, width: int = 1920, height: int = 1080) -> Path:
        import numpy as np
        from PIL import Image

        out_path.parent.mkdir(parents=True, exist_ok=True)
        Image.fromarray((np.random.rand(min(height, 90), min(width, 160), 3) * 255).astype("uint8")).save(
            out_path
        )
        return out_path


class FakeTTSProvider(TTSProvider):
    def synthesize(self, text: str, out_path: Path) -> TTSResult:
        from tests.conftest import write_silent_wav

        duration = max(0.5, len(text.split()) * 0.2)
        write_silent_wav(out_path, seconds=duration)
        words = text.split()
        timings = [
            WordTiming(word=w, start_sec=i * 0.2, end_sec=i * 0.2 + 0.15) for i, w in enumerate(words)
        ]
        return TTSResult(audio_path=out_path, word_timings=timings)


class FakeUploader:
    def __init__(self) -> None:
        self.uploaded_with: tuple[Path, YouTubeMetadata] | None = None

    def upload(self, video_path: Path, metadata: YouTubeMetadata) -> UploadResult:
        self.uploaded_with = (video_path, metadata)
        return UploadResult(video_id="fake123", url="https://youtu.be/fake123")
