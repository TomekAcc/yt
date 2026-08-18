from ...config import Settings
from ...exceptions import ConfigurationError
from .base import ImageProvider
from .openai_images import OpenAIImageProvider
from .stability_images import StabilityImageProvider

__all__ = ["ImageProvider", "OpenAIImageProvider", "StabilityImageProvider", "build_image_provider"]


def build_image_provider(settings: Settings) -> ImageProvider:
    provider = settings.providers.image
    if provider == "openai":
        return OpenAIImageProvider(settings.secrets.openai_api_key, model=settings.providers.image_model)
    if provider == "stability":
        return StabilityImageProvider(settings.secrets.stability_api_key)
    raise ConfigurationError(f"Unknown image provider: {provider!r}")
