"""Stage 8: SEO metadata.

Generates the title/description/tags YouTube actually indexes on, and sets
the `status.containsSyntheticMedia` disclosure flag that YouTube's Data API
has required since October 2024 for videos with altered/synthetic content
(see STRATEGY.md §5) -- this is set unconditionally to ``True`` here, not
left to the LLM's judgement, since every video from this pipeline uses AI
narration and AI imagery.
"""
from __future__ import annotations

from ..content.llm_client import LLMClient
from ..models import Script, YouTubeMetadata

SYSTEM_PROMPT = """You are a YouTube SEO specialist for a financial-history \
documentary channel. You write titles and descriptions that are accurate, \
compelling, and keyword-rich without being clickbait or misleading -- the \
title must be a claim the video actually supports."""

USER_PROMPT = """Write YouTube metadata for this video.

TITLE (working): {title}
THESIS: {thesis}
KEY SOURCES: {sources}

Return JSON:
{{
  "title": "<= 70 chars, specific, includes the subject name/entity",
  "description": "3-5 paragraphs: hook, what the video covers, a chaptered \
timestamp placeholder note is NOT needed, then a 'Sources' section listing \
the provided sources, then the disclosure sentence verbatim: '{disclaimer}'",
  "tags": ["10-15 relevant search tags, no hashtags, no duplicates"]
}}"""


class MetadataGenerator:
    def __init__(self, llm_client: LLMClient) -> None:
        self._llm = llm_client

    def generate(self, script: Script) -> YouTubeMetadata:
        sources = "; ".join(f"{s.title} ({s.url})" if s.url else s.title for s in script.sources)
        raw = self._llm.complete_json(
            system=SYSTEM_PROMPT,
            prompt=USER_PROMPT.format(
                title=script.title,
                thesis=script.thesis,
                sources=sources,
                disclaimer=script.disclaimer,
            ),
            max_tokens=2048,
        )
        return YouTubeMetadata(
            title=raw["title"][:100],
            description=raw["description"],
            tags=list(raw["tags"])[:500],
            contains_synthetic_media=True,
        )
