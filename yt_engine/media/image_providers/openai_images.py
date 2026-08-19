from __future__ import annotations

import base64
from pathlib import Path

from tenacity import retry, stop_after_attempt, wait_exponential

from ...exceptions import ConfigurationError, ProviderError
from .base import ImageProvider

_SIZE_MAP = {
    (1920, 1080): "1536x1024",  # nearest supported landscape size; we letterbox/crop on assembly
    (1024, 1024): "1024x1024",
}


class OpenAIImageProvider(ImageProvider):
    def __init__(self, api_key: str, model: str = "gpt-image-1") -> None:
        if not api_key:
            raise ConfigurationError("OPENAI_API_KEY is not set for the image provider.")
        try:
            import openai
        except ImportError as exc:  # pragma: no cover
            raise ConfigurationError("pip install openai to use OpenAIImageProvider") from exc
        self._client = openai.OpenAI(api_key=api_key)
        self._model = model

    @retry(reraise=True, stop=stop_after_attempt(4), wait=wait_exponential(multiplier=1, min=2, max=30))
    def generate(self, prompt: str, out_path: Path, *, width: int = 1920, height: int = 1080) -> Path:
        size = _SIZE_MAP.get((width, height), "1536x1024")
        try:
            response = self._client.images.generate(
                model=self._model,
                prompt=prompt,
                size=size,
                n=1,
            )
        except Exception as exc:  # noqa: BLE001
            raise ProviderError(f"OpenAI image generation failed: {exc}") from exc

        image_b64 = response.data[0].b64_json
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(base64.b64decode(image_b64))
        return out_path
