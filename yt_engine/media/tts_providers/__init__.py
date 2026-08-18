from ...config import Settings
from ...exceptions import ConfigurationError
from .base import TTSProvider, TTSResult
from .elevenlabs_tts import ElevenLabsTTSProvider
from .gemini_tts import GeminiTTSProvider
from .openai_tts import OpenAITTSProvider

__all__ = [
    "TTSProvider",
    "TTSResult",
    "ElevenLabsTTSProvider",
    "GeminiTTSProvider",
    "OpenAITTSProvider",
    "build_tts_provider",
]


def build_tts_provider(settings: Settings) -> TTSProvider:
    provider = settings.providers.tts
    voice = settings.providers.tts_voice
    if provider == "elevenlabs":
        return ElevenLabsTTSProvider(settings.secrets.elevenlabs_api_key, voice=voice)
    if provider == "gemini":
        return GeminiTTSProvider(settings.secrets.gemini_api_key, voice=voice)
    if provider == "openai":
        return OpenAITTSProvider(settings.secrets.openai_api_key, voice=voice)
    raise ConfigurationError(f"Unknown TTS provider: {provider!r}")
