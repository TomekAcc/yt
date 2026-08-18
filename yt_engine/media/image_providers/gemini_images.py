from __future__ import annotations

from pathlib import Path

from tenacity import retry, stop_after_attempt, wait_exponential

from ...exceptions import ConfigurationError, ProviderError
from .base import ImageProvider

# Gemini 2.5 Flash Image only accepts these ten fixed aspect ratios; we pick
# whichever is numerically closest to the requested width/height instead of
# requiring an exact match (mirrors the size-bucketing the OpenAI provider
# does for the same reason -- image providers don't do arbitrary sizes).
_SUPPORTED_ASPECT_RATIOS: dict[str, float] = {
    "21:9": 21 / 9,
    "16:9": 16 / 9,
    "4:3": 4 / 3,
    "3:2": 3 / 2,
    "1:1": 1.0,
    "9:16": 9 / 16,
    "3:4": 3 / 4,
    "2:3": 2 / 3,
    "5:4": 5 / 4,
    "4:5": 4 / 5,
}


def _nearest_aspect_ratio(width: int, height: int) -> str:
    target = width / height
    return min(_SUPPORTED_ASPECT_RATIOS, key=lambda key: abs(_SUPPORTED_ASPECT_RATIOS[key] - target))


class GeminiImageProvider(ImageProvider):
    """Google's Gemini 2.5 Flash Image ("nano banana") via the ``google-genai``
    SDK. Get a free API key at https://aistudio.google.com/app/apikey and
    set ``GEMINI_API_KEY`` in ``.env``.
    """

    def __init__(self, api_key: str, model: str = "gemini-2.5-flash-image") -> None:
        if not api_key:
            raise ConfigurationError("GEMINI_API_KEY is not set for the image provider.")
        try:
            from google import genai
        except ImportError as exc:  # pragma: no cover
            raise ConfigurationError("pip install google-genai to use GeminiImageProvider") from exc

        self._client = genai.Client(api_key=api_key)
        self._model = model

    @retry(reraise=True, stop=stop_after_attempt(4), wait=wait_exponential(multiplier=1, min=2, max=30))
    def generate(self, prompt: str, out_path: Path, *, width: int = 1920, height: int = 1080) -> Path:
        from google.genai import types

        aspect_ratio = _nearest_aspect_ratio(width, height)
        try:
            response = self._client.models.generate_content(
                model=self._model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_modalities=["IMAGE"],
                    image_config=types.ImageConfig(aspect_ratio=aspect_ratio),
                ),
            )
        except Exception as exc:  # noqa: BLE001
            raise ProviderError(f"Gemini image generation failed: {exc}") from exc

        image_bytes = _first_image_bytes(response)
        if image_bytes is None:
            raise ProviderError(
                "Gemini returned no image data (it may have refused the prompt); "
                f"response: {response!r}"
            )

        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(image_bytes)
        return out_path


def _first_image_bytes(response) -> bytes | None:
    for part in response.parts or []:
        if part.inline_data and part.inline_data.data:
            return part.inline_data.data
    return None
