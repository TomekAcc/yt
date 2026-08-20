"""Stage 4: compliance review.

Runs the automated checks from STRATEGY.md §5 against a finished script,
then — by default — blocks the pipeline on a human approval gate before any
money is spent on image/voice generation. This module is the pipeline's
concrete answer to YouTube's 2026 "inauthentic content" policy: it turns
"original value" from a vibe into checks that either pass or don't.
"""
from __future__ import annotations

from collections import Counter

from ..models import ComplianceCheck, ComplianceReport, ResearchBrief, Script

MIN_SOURCES = 2
MIN_KEY_FACTS = 5
MIN_THESIS_WORDS = 8
MIN_DISTINCT_SCENE_LENGTHS = 5
MAX_DOMINANT_SCENE_LENGTH_SHARE = 0.5

# Phrases that turn a documentary into personalized financial advice --
# the exact category STRATEGY.md flags as a monetization risk (YouTube
# scrutinizes "synthetic personas covering sensitive topics like finance"
# more heavily when they read as advice rather than analysis).
ADVICE_LANGUAGE_PATTERNS = [
    "you should invest", "you should buy", "you should sell",
    "guaranteed return", "guaranteed profit", "risk-free investment",
    "buy now", "invest now", "act now before",
]


class ComplianceReviewer:
    def review(
        self,
        script: Script,
        research: ResearchBrief,
        *,
        recent_sub_formats: list[str] | None = None,
    ) -> ComplianceReport:
        checks = [
            _check_multi_sourced(research),
            _check_thesis_present(research),
            _check_key_facts(research),
            _check_scene_variety(script),
            _check_disclaimer(script),
            _check_format_rotation(script, recent_sub_formats or []),
            _check_no_advice_language(script),
        ]
        return ComplianceReport(checks=checks, reviewed_by_human=False, approved=False)

    def approve(self, report: ComplianceReport, *, human_reviewed: bool) -> ComplianceReport:
        """Grant final approval. Only call this after either a human has
        actually looked at the script (``human_reviewed=True``), or the
        channel config explicitly disables the human gate."""
        report.reviewed_by_human = human_reviewed
        report.approved = report.all_automated_checks_passed
        return report


def _check_multi_sourced(research: ResearchBrief) -> ComplianceCheck:
    n = len({s.url or s.title for s in research.sources})
    return ComplianceCheck(
        name="multi_sourced",
        passed=n >= MIN_SOURCES,
        detail=f"{n} distinct source(s), need >= {MIN_SOURCES}",
    )


def _check_thesis_present(research: ResearchBrief) -> ComplianceCheck:
    words = len(research.thesis.split())
    return ComplianceCheck(
        name="thesis_present",
        passed=words >= MIN_THESIS_WORDS,
        detail=f"thesis is {words} words, need >= {MIN_THESIS_WORDS}",
    )


def _check_key_facts(research: ResearchBrief) -> ComplianceCheck:
    n = len(research.key_facts)
    return ComplianceCheck(
        name="sufficient_research_depth",
        passed=n >= MIN_KEY_FACTS,
        detail=f"{n} key facts recorded, need >= {MIN_KEY_FACTS}",
    )


def _check_scene_variety(script: Script) -> ComplianceCheck:
    """Flags scripts where scene length is suspiciously uniform, a
    fingerprint of templated, not-actually-written content.

    Uses two scale-invariant signals instead of a count that scales with
    the number of scenes (which over-penalizes long videos -- natural
    writing paced to a consistent target duration legitimately clusters
    around similar lengths even across 50+ scenes): at least a handful of
    distinct lengths must appear, and no single length may dominate the
    whole script.
    """
    lengths = [len(s.narration.split()) for s in script.scenes]
    if len(lengths) < 2:
        return ComplianceCheck(name="scene_variety", passed=False, detail="fewer than 2 scenes")
    unique_lengths = len(set(lengths))
    dominant_share = max(Counter(lengths).values()) / len(lengths)
    passed = (
        unique_lengths >= min(MIN_DISTINCT_SCENE_LENGTHS, len(lengths))
        and dominant_share <= MAX_DOMINANT_SCENE_LENGTH_SHARE
    )
    return ComplianceCheck(
        name="scene_variety",
        passed=passed,
        detail=(
            f"{unique_lengths} distinct scene lengths across {len(lengths)} scenes, "
            f"most common length covers {dominant_share:.0%} of scenes"
        ),
    )


def _check_disclaimer(script: Script) -> ComplianceCheck:
    return ComplianceCheck(
        name="disclosure_text_present",
        passed=bool(script.disclaimer and len(script.disclaimer) > 10),
        detail="AI-use disclaimer text is set for the description",
    )


def _check_no_advice_language(script: Script) -> ComplianceCheck:
    """This is a documentary/analysis channel, not a personalized-advice
    channel -- see STRATEGY.md §5. Flags narration that crosses into
    directive financial advice ("you should buy...") rather than
    historical analysis."""
    narration = script.full_narration.lower()
    hits = [p for p in ADVICE_LANGUAGE_PATTERNS if p in narration]
    return ComplianceCheck(
        name="no_advice_language",
        passed=not hits,
        detail="no advice-style phrasing found" if not hits else f"found: {', '.join(hits)}",
    )


def _check_format_rotation(script: Script, recent_sub_formats: list[str]) -> ComplianceCheck:
    last_three = recent_sub_formats[-3:]
    repeated = last_three.count(script.sub_format.value) >= 3
    return ComplianceCheck(
        name="format_rotation",
        passed=not repeated,
        detail=f"sub_format={script.sub_format.value}, last 3 uploads={last_three}",
    )
