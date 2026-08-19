from __future__ import annotations

import pytest

from yt_engine.config import ProviderConfig, Secrets, Settings
from yt_engine.content.llm_client import LLMClient
from yt_engine.exceptions import ConfigurationError


def _settings(llm: str, **secrets_kwargs) -> Settings:
    return Settings(
        providers=ProviderConfig(llm=llm),
        secrets=Secrets(**secrets_kwargs),
    )


def test_anthropic_provider_requires_key():
    with pytest.raises(ConfigurationError, match="ANTHROPIC_API_KEY"):
        LLMClient(_settings("anthropic"))


def test_gemini_provider_requires_key():
    with pytest.raises(ConfigurationError, match="GEMINI_API_KEY"):
        LLMClient(_settings("gemini"))


def test_gemini_provider_initializes_with_key():
    client = LLMClient(_settings("gemini", gemini_api_key="fake-key"))
    assert client._provider == "gemini"
