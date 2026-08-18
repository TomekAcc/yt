"""Thin wrapper around the Anthropic Messages API used by every content
stage (ideation, research synthesis, script writing, metadata copy).

Centralizing it here means retries, JSON-extraction, and model selection are
defined once instead of duplicated per stage.
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
    """Provider-agnostic chat/JSON completion client.

    Only Anthropic is wired up today (``providers.llm: anthropic`` in
    ``config/settings.yaml``); the constructor is the single seam to add
    another provider (OpenAI, etc.) without touching every stage that calls
    :meth:`complete_json`.
    """

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        api_key = settings.secrets.anthropic_api_key
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
        self._model = settings.providers.llm_model

    @retry(
        reraise=True,
        stop=stop_after_attempt(4),
        wait=wait_exponential(multiplier=1, min=2, max=20),
        retry=retry_if_exception_type(ProviderError),
    )
    def complete_text(self, system: str, prompt: str, *, max_tokens: int = 4096) -> str:
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

    def complete_json(
        self, system: str, prompt: str, *, max_tokens: int = 4096
    ) -> dict[str, Any] | list[Any]:
        """Call the model and parse its reply as JSON, tolerating minor
        formatting drift (code fences, leading prose) by extracting the
        first ``{...}`` / ``[...]`` block."""
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
            return json.loads(match.group(0))
