"""Stage 3: script writing.

Turns a :class:`~yt_engine.models.ResearchBrief` into a scene-by-scene
:class:`~yt_engine.models.Script`: narration text sized to the target video
length, and one AI-image prompt per scene rendered through the channel's
locked style guide (STRATEGY.md §2) so every video shares a visual identity.
"""
from __future__ import annotations

from ..models import ResearchBrief, Scene, Script
from .llm_client import LLMClient

WORDS_PER_MINUTE = 150  # typical measured pace for a calm documentary narrator

BASE_SYSTEM_PROMPT = """You are the staff scriptwriter for a YouTube \
documentary channel about financial and economic history. Follow the house \
content rules below exactly -- they are non-negotiable, not suggestions."""

# Used only if config/content_rules.md is missing, so behavior degrades
# gracefully rather than silently writing unruled scripts.
FALLBACK_CONTENT_RULES = """1. ENTERTAINING, NOT ENCYCLOPEDIC. Open with the \
single most dramatic moment as a cold open hook. Use concrete, specific \
details, not abstract summary. Never use textbook phrasing.
2. 100% FACTUALLY ACCURATE. Every claim must come from the KEY FACTS or \
TIMELINE given to you. Never invent or embellish a fact.
Structure: cold open hook, setup, rising conflict, climax, resolution, \
closing thought. No dialogue, no filler."""

USER_PROMPT = """Write the full narration script for this video, split into \
scenes of roughly {scene_seconds}s each when read aloud at {wpm} words/minute \
(~{words_per_scene} words per scene). Target total length: {target_minutes} \
minutes ({target_words} words).

TITLE: {title}
THESIS: {thesis}
KEY FACTS:
{key_facts}
TIMELINE:
{timeline}

VISUAL STYLE GUIDE (use this to inform each scene's image prompt -- keep \
every prompt consistent with it):
{style_guide}

Return JSON:
{{
  "scenes": [
    {{
      "narration": "1-3 sentences of narration for this scene",
      "image_prompt": "detailed prompt for an AI image generator depicting this \
moment, written in the visual style above, no text/words in the image, \
composed for a 16:9 frame with room at the bottom third for subtitles"
    }}
    // enough scenes to cover the full narration at the pacing above
  ]
}}"""


class ScriptWriter:
    def __init__(self, llm_client: LLMClient) -> None:
        self._llm = llm_client

    def write(
        self,
        brief: ResearchBrief,
        *,
        target_minutes: float = 12.0,
        scene_seconds: float = 18.0,
        style_guide: dict | None = None,
        content_rules: str | None = None,
    ) -> Script:
        target_words = int(target_minutes * WORDS_PER_MINUTE)
        words_per_scene = int(scene_seconds / 60 * WORDS_PER_MINUTE)
        style_text = _format_style_guide(style_guide or {})
        rules_text = content_rules.strip() if content_rules and content_rules.strip() else FALLBACK_CONTENT_RULES
        system_prompt = f"{BASE_SYSTEM_PROMPT}\n\n{rules_text}"

        raw = self._llm.complete_json(
            system=system_prompt,
            prompt=USER_PROMPT.format(
                scene_seconds=scene_seconds,
                wpm=WORDS_PER_MINUTE,
                words_per_scene=max(words_per_scene, 15),
                target_minutes=target_minutes,
                target_words=target_words,
                title=brief.topic.title,
                thesis=brief.thesis,
                key_facts="\n".join(f"- {f}" for f in brief.key_facts),
                timeline="\n".join(f"- {t}" for t in brief.timeline) or "(none given)",
                style_guide=style_text,
            ),
            max_tokens=32768,
        )

        scenes = [
            Scene(index=i, narration=s["narration"], image_prompt=s["image_prompt"])
            for i, s in enumerate(raw["scenes"])
        ]
        if not scenes:
            raise ValueError("Script writer returned zero scenes")

        return Script(
            title=brief.topic.title,
            sub_format=brief.topic.sub_format,
            thesis=brief.thesis,
            scenes=scenes,
            sources=brief.sources,
        )


def _format_style_guide(style_guide: dict) -> str:
    if not style_guide:
        return "Muted, period-accurate cinematic realism. No on-image text."
    lines = []
    for key, value in style_guide.items():
        if isinstance(value, list):
            value = ", ".join(str(v) for v in value)
        lines.append(f"{key}: {value}")
    return "\n".join(lines)
