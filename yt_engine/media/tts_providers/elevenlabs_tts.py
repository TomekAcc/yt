from __future__ import annotations

import base64
from pathlib import Path

import requests
from tenacity import retry, stop_after_attempt, wait_exponential

from ...exceptions import ConfigurationError, ProviderError
from ...models import WordTiming
from .base import TTSProvider, TTSResult

_ENDPOINT = "https://api.elevenlabs.io/v1/text-to-speech/{voice_id}/with-timestamps"

# Curated narrator voices; override via config/settings.yaml providers.tts_voice
# -- any value not listed here is passed straight through as a raw ElevenLabs
# voice ID, so you can pick anything from your own Voice Library too.
_VOICE_IDS = {
    "narrator": "21m00Tcm4TlvDq8ikWAM",  # "Rachel" - calm, neutral female documentary read
    "narrator_deep": "pNInz6obpgDQGcFmaJgB",  # "Adam" - deep, resonant male documentary read
}


class ElevenLabsTTSProvider(TTSProvider):
    """Uses ElevenLabs' timestamped TTS endpoint so subtitle timing comes
    directly from the same request as the audio -- no separate forced
    alignment pass needed."""

    def __init__(self, api_key: str, voice: str = "narrator") -> None:
        if not api_key:
            raise ConfigurationError("ELEVENLABS_API_KEY is not set for the TTS provider.")
        self._api_key = api_key
        self._voice_id = _VOICE_IDS.get(voice, voice)  # allow passing a raw voice ID

    @retry(reraise=True, stop=stop_after_attempt(4), wait=wait_exponential(multiplier=1, min=2, max=30))
    def synthesize(self, text: str, out_path: Path) -> TTSResult:
        try:
            response = requests.post(
                _ENDPOINT.format(voice_id=self._voice_id),
                headers={"xi-api-key": self._api_key, "content-type": "application/json"},
                json={
                    "text": text,
                    "model_id": "eleven_multilingual_v2",
                    "voice_settings": {"stability": 0.55, "similarity_boost": 0.8},
                },
                timeout=180,
            )
        except requests.RequestException as exc:
            raise ProviderError(f"ElevenLabs request failed: {exc}") from exc

        if response.status_code != 200:
            raise ProviderError(f"ElevenLabs TTS failed ({response.status_code}): {response.text[:300]}")

        payload = response.json()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(base64.b64decode(payload["audio_base64"]))

        word_timings = _characters_to_words(payload.get("alignment", {}))
        return TTSResult(audio_path=out_path, word_timings=word_timings)


def _characters_to_words(alignment: dict) -> list[WordTiming]:
    chars = alignment.get("characters", [])
    starts = alignment.get("character_start_times_seconds", [])
    ends = alignment.get("character_end_times_seconds", [])
    if not chars:
        return []

    words: list[WordTiming] = []
    buf, buf_start = "", None
    for ch, start, end in zip(chars, starts, ends):
        if ch.isspace():
            if buf:
                words.append(WordTiming(word=buf, start_sec=buf_start, end_sec=prev_end))
                buf, buf_start = "", None
            continue
        if buf_start is None:
            buf_start = start
        buf += ch
        prev_end = end
    if buf:
        words.append(WordTiming(word=buf, start_sec=buf_start, end_sec=prev_end))
    return words
