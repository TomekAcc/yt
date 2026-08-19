from __future__ import annotations

from pathlib import Path

import requests
from tenacity import retry, stop_after_attempt, wait_exponential

from ...exceptions import ConfigurationError, ProviderError
from .base import ImageProvider

_STABILITY_ENDPOINT = "https://api.stability.ai/v2beta/stable-image/generate/core"


class StabilityImageProvider(ImageProvider):
    """Stability AI's image generation REST API. Alternative to OpenAI when
    the channel style guide calls for a distinct painterly model, or as a
    fallback provider."""

    def __init__(self, api_key: str) -> None:
        if not api_key:
            raise ConfigurationError("STABILITY_API_KEY is not set for the image provider.")
        self._api_key = api_key

    @retry(reraise=True, stop=stop_after_attempt(4), wait=wait_exponential(multiplier=1, min=2, max=30))
    def generate(self, prompt: str, out_path: Path, *, width: int = 1920, height: int = 1080) -> Path:
        aspect_ratio = "16:9" if width >= height else "9:16"
        try:
            response = requests.post(
                _STABILITY_ENDPOINT,
                headers={"authorization": f"Bearer {self._api_key}", "accept": "image/*"},
                files={"none": ""},
                data={"prompt": prompt, "aspect_ratio": aspect_ratio, "output_format": "png"},
                timeout=120,
            )
        except requests.RequestException as exc:
            raise ProviderError(f"Stability image request failed: {exc}") from exc

        if response.status_code != 200:
            raise ProviderError(f"Stability image generation failed ({response.status_code}): {response.text[:300]}")

        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(response.content)
        return out_path
