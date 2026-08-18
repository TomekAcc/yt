"""Stage 2: research.

Produces a :class:`~yt_engine.models.ResearchBrief` — thesis, key facts,
timeline, and sources — that the script writer synthesizes from. This is
the pipeline's primary defense against YouTube's "inauthentic content"
policy: a script written from a researched brief with a stated thesis is
original analysis, not a reworded Wikipedia paraphrase.
"""
from __future__ import annotations

from ..models import ResearchBrief, Source, TopicIdea
from .llm_client import LLMClient
from .search import SearchProvider, NoopSearchProvider

SYSTEM_PROMPT = """You are a meticulous financial historian preparing a \
research brief for a documentary script. You synthesize across multiple \
sources rather than paraphrasing any single one, you are precise about \
dates and figures, and you flag anything uncertain instead of inventing \
specifics."""

USER_PROMPT = """Prepare a research brief for this video topic:

Title: {title}
Setting: {era_or_setting}
Logline: {logline}
Hook: {hook}

{search_context}

Return JSON:
{{
  "thesis": "the video's central, specific argument or insight (not just a summary)",
  "key_facts": ["fact 1", "fact 2", "... at least 8 concrete, checkable facts"],
  "timeline": ["YEAR: event", "... chronological"],
  "sources": [
    {{"title": "book/article/documentary title", "url": "url or null", "note": "why it's relevant"}}
    // at least 3 distinct sources
  ]
}}"""


class ResearchAgent:
    def __init__(self, llm_client: LLMClient, search_provider: SearchProvider | None = None) -> None:
        self._llm = llm_client
        self._search = search_provider or NoopSearchProvider()

    def research(self, topic: TopicIdea) -> ResearchBrief:
        found_sources = self._search.search(f"{topic.title} {topic.era_or_setting}")
        search_context = (
            "Ground your brief in these search results where relevant:\n"
            + "\n".join(f"- {s.title} ({s.url}): {s.note}" for s in found_sources)
            if found_sources
            else "No live search results were provided; draw on well-documented "
            "historical record and name the specific reference works you're "
            "drawing from."
        )
        raw = self._llm.complete_json(
            system=SYSTEM_PROMPT,
            prompt=USER_PROMPT.format(
                title=topic.title,
                era_or_setting=topic.era_or_setting,
                logline=topic.logline,
                hook=topic.hook,
                search_context=search_context,
            ),
            max_tokens=4096,
        )
        sources = [Source(**s) for s in raw.get("sources", [])]
        if found_sources:
            existing = {s.url for s in sources if s.url}
            sources.extend(s for s in found_sources if s.url not in existing)

        return ResearchBrief(
            topic=topic,
            thesis=raw["thesis"],
            key_facts=raw["key_facts"],
            timeline=raw.get("timeline", []),
            sources=sources,
        )
