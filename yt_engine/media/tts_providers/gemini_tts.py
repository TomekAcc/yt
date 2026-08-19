from __future__ import annotations

import re
import wave
from pathlib import Path

from tenacity import retry, stop_after_attempt, wait_exponential

from ...exceptions import ConfigurationError, ProviderError
from .base import TTSProvider, TTSResult

# Prebuilt Gemini TTS voices; "Kore" reads as a calm, neutral narrator voice
# well suited to documentary narration. Override via providers.tts_voice.
_VOICE_MAP = {"narrator": "Kore"}
_RATE_RE = re.compile(r"rate=(\d+)")


class GeminiTTSProvider(TTSProvider):
    """Google's native Gemini text-to-speech models, via the same
    ``google-genai`` SDK/API key already used for image generation -- one
    Google AI Studio key covers both providers.

    Gemini TTS returns raw PCM audio (no container, no word-level
    timestamps), so this wraps the PCM in a WAV header and lets the
    subtitle stage's faster-whisper forced alignment supply word timings,
    same as the OpenAI TTS provider.
    """

    file_extension = "wav"

    def __init__(self, api_key: str, voice: str = "narrator", model: str = "gemini-2.5-flash-tts") -> None:
        if not api_key:
            raise ConfigurationError("GEMINI_API_KEY is not set for the TTS provider.")
        try:
            from google import genai
        except ImportError as exc:  # pragma: no cover
            raise ConfigurationError("pip install google-genai to use GeminiTTSProvider") from exc

        self._client = genai.Client(api_key=api_key)
        self._voice = _VOICE_MAP.get(voice, voice)
        self._model = model

    @retry(reraise=True, stop=stop_after_attempt(4), wait=wait_exponential(multiplier=1, min=2, max=30))
    def synthesize(self, text: str, out_path: Path) -> TTSResult:
        from google.genai import types

        try:
            response = self._client.models.generate_content(
                model=self._model,
                contents=text,
                config=types.GenerateContentConfig(
                    response_modalities=["AUDIO"],
                    speech_config=types.SpeechConfig(
                        voice_config=types.VoiceConfig(
                            prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=self._voice)
                        )
                    ),
                ),
            )
        except Exception as exc:  # noqa: BLE001
            raise ProviderError(f"Gemini TTS generation failed: {exc}") from exc

        pcm_bytes, mime_type = _first_audio_part(response)
        if pcm_bytes is None:
            raise ProviderError(f"Gemini TTS returned no audio data; response: {response!r}")

        out_path.parent.mkdir(parents=True, exist_ok=True)
        _write_wav(pcm_bytes, out_path, sample_rate=_sample_rate_from_mime(mime_type))
        return TTSResult(audio_path=out_path, word_timings=None)


def _first_audio_part(response) -> tuple[bytes | None, str | None]:
    for part in response.parts or []:
        if part.inline_data and part.inline_data.data:
            return part.inline_data.data, part.inline_data.mime_type
    return None, None


def _sample_rate_from_mime(mime_type: str | None, default: int = 24000) -> int:
    if not mime_type:
        return default
    match = _RATE_RE.search(mime_type)
    return int(match.group(1)) if match else default


def _write_wav(pcm_data: bytes, out_path: Path, *, sample_rate: int, sample_width: int = 2, channels: int = 1) -> None:
    with wave.open(str(out_path), "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(sample_width)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm_data)
