"""Wrapper around the content-generation LLM used by every content stage
(ideation, research synthesis, script writing, metadata copy).

Centralizing it here means retries, JSON-extraction, and model selection are
defined once instead of duplicated per stage. Supports Anthropic (default)
or Gemini, chosen via ``providers.llm`` in ``config/settings.yaml`` -- pick
Gemini if you'd rather use one API key across scripting, images, and voice.
"""
from __future__ import annotations

import json
import re
from typing import Any

from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from ..config import Settings
from ..exceptions import ConfigurationError, ProviderError
from ..logging_utils import get_logger

log = get_logger(__name__)

_JSON_BLOCK_RE = re.compile(r"\{.*\}|\[.*\]", re.DOTALL)


class LLMClient:
    """Provider-agnostic chat/JSON completion client used by every content
    stage. The constructor is the single seam for adding another provider
    without touching every stage that calls :meth:`complete_json`."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._provider = settings.providers.llm
        self._model = settings.providers.llm_model

        if self._provider == "anthropic":
            self._init_anthropic()
        elif self._provider == "gemini":
            self._init_gemini()
        else:
            raise ConfigurationError(f"Unknown LLM provider: {self._provider!r}")

    def _init_anthropic(self) -> None:
        api_key = self.settings.secrets.anthropic_api_key
        if not api_key:
            raise ConfigurationError(
                "ANTHROPIC_API_KEY is not set. Add it to your .env file "
                "(see .env.example)."
            )
        try:
            import anthropic
        except ImportError as exc:  # pragma: no cover
            raise ConfigurationError(
                "The 'anthropic' package is required. Run: pip install anthropic"
            ) from exc
        self._client = anthropic.Anthropic(api_key=api_key)

    def _init_gemini(self) -> None:
        api_key = self.settings.secrets.gemini_api_key
        if not api_key:
            raise ConfigurationError(
                "GEMINI_API_KEY is not set. Add it to your .env file "
                "(see .env.example)."
            )
        try:
            from google import genai
        except ImportError as exc:  # pragma: no cover
            raise ConfigurationError("pip install google-genai to use the Gemini LLM provider") from exc
        self._client = genai.Client(api_key=api_key)

    @retry(
        reraise=True,
        stop=stop_after_attempt(4),
        wait=wait_exponential(multiplier=1, min=2, max=20),
        retry=retry_if_exception_type(ProviderError),
    )
    def complete_text(self, system: str, prompt: str, *, max_tokens: int = 4096) -> str:
        if self._provider == "anthropic":
            return self._complete_text_anthropic(system, prompt, max_tokens)
        return self._complete_text_gemini(system, prompt, max_tokens)

    def _complete_text_anthropic(self, system: str, prompt: str, max_tokens: int) -> str:
        try:
            response = self._client.messages.create(
                model=self._model,
                max_tokens=max_tokens,
                system=system,
                messages=[{"role": "user", "content": prompt}],
            )
        except Exception as exc:  # noqa: BLE001 - normalize every SDK error
            raise ProviderError(f"Anthropic request failed: {exc}") from exc

        return "".join(
            block.text for block in response.content if getattr(block, "type", None) == "text"
        ).strip()

    def _complete_text_gemini(self, system: str, prompt: str, max_tokens: int) -> str:
        from google.genai import types

        try:
            response = self._client.models.generate_content(
                model=self._model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=system,
                    max_output_tokens=max_tokens,
                ),
            )
        except Exception as exc:  # noqa: BLE001
            raise ProviderError(f"Gemini request failed: {exc}") from exc

        if not response.text:
            raise ProviderError(f"Gemini returned no text; response: {response!r}")
        return response.text.strip()

    @retry(
        reraise=True,
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=20),
        retry=retry_if_exception_type(ProviderError),
    )
    def complete_json(
        self, system: str, prompt: str, *, max_tokens: int = 4096
    ) -> dict[str, Any] | list[Any]:
        """Call the model and parse its reply as JSON, tolerating minor
        formatting drift (code fences, leading prose) by extracting the
        first ``{...}`` / ``[...]`` block. Retries on malformed JSON too --
        a truncated or broken response is usually a one-off sampling issue,
        not a persistent failure."""
        text = self.complete_text(
            system=system + "\n\nRespond with ONLY valid JSON. No prose, no markdown fences.",
            prompt=prompt,
            max_tokens=max_tokens,
        )
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            match = _JSON_BLOCK_RE.search(text)
            if not match:
                raise ProviderError(f"LLM did not return parseable JSON: {text[:500]!r}")
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError as exc:
                raise ProviderError(
                    f"LLM returned malformed JSON ({exc}); response was {len(text)} chars, "
                    f"likely truncated by max_tokens={max_tokens}"
                ) from exc
