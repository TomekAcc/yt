"""Pluggable web search used by :class:`~yt_engine.content.research.ResearchAgent`
to ground scripts in multiple independent sources (the compliance signal
YouTube's 2026 "inauthentic content" policy checks for).

Ships with a no-op default so the pipeline runs without an extra API key;
set ``TAVILY_API_KEY`` to enable real source gathering.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from ..models import Source


class SearchProvider(ABC):
    @abstractmethod
    def search(self, query: str, max_results: int = 5) -> list[Source]:
        ...


class NoopSearchProvider(SearchProvider):
    """Falls back to the LLM's own knowledge; the research stage still
    requires the model to name multiple distinct reference works so the
    multi-source check has something real to validate."""

    def search(self, query: str, max_results: int = 5) -> list[Source]:
        return []


class TavilySearchProvider(SearchProvider):
    def __init__(self, api_key: str) -> None:
        try:
            from tavily import TavilyClient
        except ImportError as exc:  # pragma: no cover
            raise ImportError("pip install tavily-python to use TavilySearchProvider") from exc
        self._client = TavilyClient(api_key=api_key)

    def search(self, query: str, max_results: int = 5) -> list[Source]:
        result = self._client.search(query=query, max_results=max_results)
        return [
            Source(title=item.get("title", query), url=item.get("url"), note=item.get("content"))
            for item in result.get("results", [])
        ]


def build_search_provider(tavily_api_key: str | None) -> SearchProvider:
    if tavily_api_key:
        return TavilySearchProvider(tavily_api_key)
    return NoopSearchProvider()
