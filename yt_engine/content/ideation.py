"""Stage 1: topic ideation.

Generates candidate video topics within the channel's four sub-formats
(see STRATEGY.md §1), rotating between them so the channel doesn't drift
into the single repeated template YouTube's inauthentic-content policy
targets.
"""
from __future__ import annotations

from ..models import SubFormat, TopicIdea
from .llm_client import LLMClient

SYSTEM_PROMPT = """You are the lead researcher/producer for a YouTube documentary \
channel about financial and economic history (channel name: "{channel_name}"). \
You pitch video topics that are well-documented, dramatic, and have a clear \
narrative arc (setup, conflict, resolution). You never pitch generic or \
already-oversaturated topics (e.g. "Enron" has been covered thousands of \
times) without a genuinely fresh angle."""

USER_PROMPT = """Pitch {count} NEW video topic ideas for the channel.

Rotate across these sub-formats, using each at least once if count >= 4:
- company_case_study: the rise and fall of a specific company or corporate scandal
- currency_crisis: hyperinflation, bank runs, currency collapses, financial bubbles
- wealth_biography: how a specific historical fortune was built and/or lost
- economic_era: an economic system, regime, or multi-year era explained through its consequences

Avoid topics already produced: {avoid_titles}

Return a JSON array. Each item:
{{
  "title": "punchy, specific video title, <= 70 chars",
  "sub_format": "one of: company_case_study | currency_crisis | wealth_biography | economic_era",
  "logline": "one sentence describing the story",
  "era_or_setting": "time period and place",
  "hook": "the specific dramatic question or tension the video opens on"
}}"""


class TopicIdeator:
    def __init__(self, llm_client: LLMClient, channel_name: str) -> None:
        self._llm = llm_client
        self._channel_name = channel_name

    def generate(self, count: int = 5, avoid_titles: list[str] | None = None) -> list[TopicIdea]:
        avoid = ", ".join(avoid_titles) if avoid_titles else "(none yet)"
        raw = self._llm.complete_json(
            system=SYSTEM_PROMPT.format(channel_name=self._channel_name),
            prompt=USER_PROMPT.format(count=count, avoid_titles=avoid),
        )
        if not isinstance(raw, list):
            raise ValueError(f"Expected a JSON array of topics, got: {type(raw)}")
        return [TopicIdea(**item) for item in raw]
