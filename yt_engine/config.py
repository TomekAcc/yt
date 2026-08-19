"""Central configuration.

Secrets (API keys) come from the environment / ``.env`` (see
``.env.example``). Non-secret run parameters (niche, style guide, video
length targets) come from a YAML file, defaulting to
``config/settings.yaml``. Keeping these separate means the settings file is
safe to commit while ``.env`` never is.
"""
from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SETTINGS_PATH = REPO_ROOT / "config" / "settings.yaml"


class Secrets(BaseSettings):
    """API credentials, loaded from environment variables / .env.

    Every field is optional at the settings-object level because a given
    run only needs the providers it's configured to use (e.g. skip
    ``elevenlabs_api_key`` if the TTS provider is ``openai``) — validation
    that a *required* key is present happens lazily, at the provider that
    needs it, so importing config never fails in an unrelated environment.
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    anthropic_api_key: str | None = Field(default=None)
    openai_api_key: str | None = Field(default=None)
    stability_api_key: str | None = Field(default=None)
    gemini_api_key: str | None = Field(default=None)
    elevenlabs_api_key: str | None = Field(default=None)
    tavily_api_key: str | None = Field(default=None)

    youtube_client_secrets_file: str | None = Field(default=None)
    youtube_token_file: str = Field(default=".secrets/youtube_token.json")


class ProviderConfig(BaseSettings):
    llm: Literal["anthropic"] = "anthropic"
    llm_model: str = "claude-sonnet-4-5"
    image: Literal["openai", "stability", "gemini"] = "gemini"
    image_model: str = "gemini-2.5-flash-image"
    tts: Literal["elevenlabs", "gemini", "openai"] = "elevenlabs"
    tts_voice: str = "narrator"


class VideoConfig(BaseSettings):
    target_minutes: tuple[float, float] = (10.0, 18.0)
    resolution: tuple[int, int] = (1920, 1080)
    fps: int = 30
    ken_burns_zoom_range: tuple[float, float] = (1.0, 1.06)
    scene_min_duration_sec: float = 6.0
    scene_max_duration_sec: float = 14.0
    subtitle_font: str = "Arial"
    subtitle_max_chars_per_line: int = 42


class ChannelConfig(BaseSettings):
    name: str = "The Ledger"
    niche: str = "financial_history"
    style_guide: str = "config/style_guides/financial_history.yaml"
    require_human_approval: bool = True
    default_privacy_status: Literal["private", "unlisted", "public"] = "private"


class Settings(BaseSettings):
    secrets: Secrets = Field(default_factory=Secrets)
    providers: ProviderConfig = Field(default_factory=ProviderConfig)
    video: VideoConfig = Field(default_factory=VideoConfig)
    channel: ChannelConfig = Field(default_factory=ChannelConfig)
    workspace_dir: Path = Field(default=REPO_ROOT / "workspace")

    @classmethod
    def load(cls, path: Path | str | None = None) -> "Settings":
        settings_path = Path(path) if path else DEFAULT_SETTINGS_PATH
        data: dict = {}
        if settings_path.exists():
            data = yaml.safe_load(settings_path.read_text()) or {}
        settings = cls(
            providers=ProviderConfig(**data.get("providers", {})),
            video=VideoConfig(**data.get("video", {})),
            channel=ChannelConfig(**data.get("channel", {})),
            workspace_dir=Path(data.get("workspace_dir", REPO_ROOT / "workspace")),
        )
        settings.workspace_dir.mkdir(parents=True, exist_ok=True)
        return settings

    def style_guide_path(self) -> Path:
        return REPO_ROOT / self.channel.style_guide

    def load_style_guide(self) -> dict:
        path = self.style_guide_path()
        if not path.exists():
            return {}
        return yaml.safe_load(path.read_text()) or {}
