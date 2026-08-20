from __future__ import annotations

from yt_engine.content.compliance import ComplianceReviewer
from yt_engine.models import ResearchBrief, Scene, Script, Source, SubFormat, TopicIdea

TOPIC = TopicIdea(
    title="The Fall of Barings Bank",
    sub_format=SubFormat.COMPANY_CASE_STUDY,
    logline="A rogue trader sinks Britain's oldest bank.",
    era_or_setting="Singapore, 1995",
    hook="How did one trader bankrupt a 233-year-old bank?",
)


def _brief(n_sources=3, n_facts=8, thesis_words=12):
    return ResearchBrief(
        topic=TOPIC,
        thesis=" ".join(["word"] * thesis_words),
        key_facts=[f"fact {i}" for i in range(n_facts)],
        sources=[Source(title=f"Source {i}", url=f"https://example.com/{i}") for i in range(n_sources)],
    )


def _script(scene_lengths=(5, 12, 8, 20, 6)):
    scenes = [
        Scene(index=i, narration=" ".join(["w"] * n), image_prompt="p")
        for i, n in enumerate(scene_lengths)
    ]
    return Script(
        title=TOPIC.title,
        sub_format=TOPIC.sub_format,
        thesis="a" * 40,
        scenes=scenes,
        sources=[Source(title="s")],
    )


def test_all_checks_pass_for_healthy_script():
    report = ComplianceReviewer().review(_script(), _brief())
    assert report.all_automated_checks_passed
    assert not report.approved  # not yet approved


def test_single_source_fails_multi_sourced_check():
    report = ComplianceReviewer().review(_script(), _brief(n_sources=1))
    failed = {c.name for c in report.checks if not c.passed}
    assert "multi_sourced" in failed
    assert not report.all_automated_checks_passed


def test_identical_scene_lengths_fail_variety_check():
    report = ComplianceReviewer().review(_script(scene_lengths=(10, 10, 10, 10)), _brief())
    failed = {c.name for c in report.checks if not c.passed}
    assert "scene_variety" in failed


def test_large_scene_count_with_natural_clustering_passes():
    """Regression test: a long, well-paced script naturally clusters scene
    lengths around a target duration -- that used to fail the old
    count-scaled threshold even though it isn't templated content."""
    import random

    rng = random.Random(0)
    scene_lengths = [rng.choice([18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28]) for _ in range(70)]
    report = ComplianceReviewer().review(_script(scene_lengths=scene_lengths), _brief())
    failed = {c.name for c in report.checks if not c.passed}
    assert "scene_variety" not in failed


def test_advice_language_is_flagged():
    script = _script(scene_lengths=(5, 12, 8, 20, 6))
    script.scenes[2].narration = "Analysts warned investors. You should buy this stock immediately."
    report = ComplianceReviewer().review(script, _brief())
    failed = {c.name for c in report.checks if not c.passed}
    assert "no_advice_language" in failed


def test_analytical_language_is_not_flagged_as_advice():
    report = ComplianceReviewer().review(_script(), _brief())
    failed = {c.name for c in report.checks if not c.passed}
    assert "no_advice_language" not in failed


def test_format_rotation_flags_three_in_a_row():
    report = ComplianceReviewer().review(
        _script(),
        _brief(),
        recent_sub_formats=["company_case_study", "company_case_study", "company_case_study"],
    )
    failed = {c.name for c in report.checks if not c.passed}
    assert "format_rotation" in failed


def test_approve_sets_flags_only_when_checks_pass():
    reviewer = ComplianceReviewer()
    good_report = reviewer.review(_script(), _brief())
    reviewer.approve(good_report, human_reviewed=True)
    assert good_report.approved is True
    assert good_report.reviewed_by_human is True

    bad_report = reviewer.review(_script(), _brief(n_sources=1))
    reviewer.approve(bad_report, human_reviewed=True)
    assert bad_report.approved is False
