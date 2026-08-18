from __future__ import annotations

import pytest

from yt_engine.exceptions import ConfigurationError
from yt_engine.media.image_providers.gemini_images import GeminiImageProvider, _nearest_aspect_ratio


@pytest.mark.parametrize(
    "size,expected",
    [
        ((1920, 1080), "16:9"),
        ((1080, 1920), "9:16"),
        ((1024, 1024), "1:1"),
        ((1280, 960), "4:3"),
    ],
)
def test_nearest_aspect_ratio(size, expected):
    assert _nearest_aspect_ratio(*size) == expected


def test_missing_api_key_raises_configuration_error():
    with pytest.raises(ConfigurationError):
        GeminiImageProvider(api_key=None)
