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

SYSTEM_PROMPT = """You are a YouTube SEO and thumbnail specialist for a \
financial-history documentary channel. You write titles, descriptions, and \
thumbnail text that are accurate, compelling, and keyword-rich WITHOUT \
being clickbait or misleading -- every word must be a claim the video \
actually supports. High click-through rate comes from genuine intrigue \
(a real number, a real stake, a real question the video answers), never \
from exaggeration, fake urgency, or a claim the content doesn't back up. \
Misleading thumbnails/titles get channels penalized and demonetized, so \
"technically true but exaggerated" is not acceptable -- it must be \
straightforwardly true."""

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
  "tags": ["10-15 relevant search tags, no hashtags, no duplicates"],
  "thumbnail_text": "2-5 words, ALL CAPS, punchy enough to stop a scroll -- \
a number, a stake, or a question, e.g. '$18 BILLION LIE' or 'HE FLED THE \
COUNTRY' -- must be a specific true fact from the story, never a vague \
tease like 'YOU WON'T BELIEVE THIS'"
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
            thumbnail_text=raw.get("thumbnail_text", "")[:40],
            contains_synthetic_media=True,
        )
