from __future__ import annotations

import wave

import pytest

from yt_engine.exceptions import ConfigurationError
from yt_engine.media.tts_providers.gemini_tts import (
    GeminiTTSProvider,
    _sample_rate_from_mime,
    _write_wav,
)


def test_missing_api_key_raises_configuration_error():
    with pytest.raises(ConfigurationError):
        GeminiTTSProvider(api_key=None)


def test_file_extension_is_wav():
    assert GeminiTTSProvider.file_extension == "wav"


@pytest.mark.parametrize(
    "mime_type,expected",
    [
        ("audio/L16;codec=pcm;rate=24000", 24000),
        ("audio/L16;rate=16000", 16000),
        (None, 24000),
        ("audio/L16", 24000),
    ],
)
def test_sample_rate_from_mime(mime_type, expected):
    assert _sample_rate_from_mime(mime_type) == expected


def test_write_wav_round_trips_pcm_bytes(tmp_path):
    pcm = (b"\x00\x01" * 100)
    out = tmp_path / "out.wav"
    _write_wav(pcm, out, sample_rate=24000)

    with wave.open(str(out), "rb") as wf:
        assert wf.getframerate() == 24000
        assert wf.getnchannels() == 1
        assert wf.getsampwidth() == 2
        assert wf.readframes(wf.getnframes()) == pcm
