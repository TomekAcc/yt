from __future__ import annotations

from pathlib import Path

from tenacity import retry, stop_after_attempt, wait_exponential

from ...exceptions import ConfigurationError, ProviderError
from .base import TTSProvider, TTSResult

_VOICE_MAP = {"narrator": "onyx"}


class OpenAITTSProvider(TTSProvider):
    """No native word-level timestamps -- the subtitle stage forced-aligns
    this provider's output with faster-whisper."""

    def __init__(self, api_key: str, voice: str = "narrator", model: str = "gpt-4o-mini-tts") -> None:
        if not api_key:
            raise ConfigurationError("OPENAI_API_KEY is not set for the TTS provider.")
        try:
            import openai
        except ImportError as exc:  # pragma: no cover
            raise ConfigurationError("pip install openai to use OpenAITTSProvider") from exc
        self._client = openai.OpenAI(api_key=api_key)
        self._voice = _VOICE_MAP.get(voice, voice)
        self._model = model

    @retry(reraise=True, stop=stop_after_attempt(4), wait=wait_exponential(multiplier=1, min=2, max=30))
    def synthesize(self, text: str, out_path: Path) -> TTSResult:
        try:
            response = self._client.audio.speech.create(
                model=self._model, voice=self._voice, input=text, response_format="mp3"
            )
        except Exception as exc:  # noqa: BLE001
            raise ProviderError(f"OpenAI TTS failed: {exc}") from exc

        out_path.parent.mkdir(parents=True, exist_ok=True)
        response.write_to_file(out_path)
        return TTSResult(audio_path=out_path, word_timings=None)
