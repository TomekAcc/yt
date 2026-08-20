from __future__ import annotations

from pathlib import Path

from yt_engine.models import ProjectState, Scene, Script, Stage, SubFormat, TopicIdea
from yt_engine.storage import ProjectStore


def test_stage_order_and_next():
    order = Stage.order()
    assert order[0] == Stage.IDEATION
    assert order[-1] == Stage.DONE
    assert Stage.IDEATION.next() == Stage.RESEARCH
    assert Stage.DONE.next() == Stage.DONE  # terminal


def test_project_state_advance_and_fail():
    state = ProjectState(stage=Stage.RESEARCH)
    state.advance()
    assert state.stage == Stage.SCRIPTING

    state.mark_failed("boom")
    # stage deliberately stays put -- a failure must be retryable, not a
    # dead end that silently no-ops on the next `run()` call
    assert state.stage == Stage.SCRIPTING
    assert state.error == "boom"

    state.advance()
    assert state.stage == Stage.COMPLIANCE_REVIEW
    assert state.error is None  # cleared once the retried stage succeeds


def test_project_store_recovers_legacy_failed_stage_on_load(tmp_path):
    """Regression test: state.json files written before the resumability fix
    have a literal "failed" stage baked in permanently (mark_failed() used to
    overwrite the real stage). Loading one of those must infer the real
    in-progress stage from what work is actually done, not crash with a
    missing handler for the dead FAILED stage."""
    store = ProjectStore(tmp_path / "workspace")
    topic = TopicIdea(
        title="The Collapse of Acme Corp",
        sub_format=SubFormat.COMPANY_CASE_STUDY,
        logline="A cautionary tale.",
        era_or_setting="1990s USA",
        hook="How did nobody see it coming?",
    )
    state = ProjectState(topic=topic, stage=Stage.IMAGE_GENERATION)
    state.script = Script(
        title="The Collapse of Acme Corp",
        thesis="Bad governance, not bad luck, sank Acme.",
        sub_format=SubFormat.COMPANY_CASE_STUDY,
        scenes=[
            Scene(index=0, narration="It started quietly.", image_prompt="a quiet office", image_path=Path("scene_000.png")),
            Scene(index=1, narration="Then it all fell apart.", image_prompt="a burning ledger", image_path=Path("scene_001.png")),
        ],
        sources=[],
    )
    state.stage = Stage.FAILED  # simulate a state.json written by the old buggy code
    store.save(state)

    reloaded = store.load(state.project_id)
    # every scene already has an image, none has audio yet -> real stage is NARRATION
    assert reloaded.stage == Stage.NARRATION
    assert reloaded.error is not None


def test_project_store_roundtrip(tmp_path):
    store = ProjectStore(tmp_path / "workspace")
    topic = TopicIdea(
        title="The Collapse of Acme Corp",
        sub_format=SubFormat.COMPANY_CASE_STUDY,
        logline="A cautionary tale.",
        era_or_setting="1990s USA",
        hook="How did nobody see it coming?",
    )
    state = ProjectState(topic=topic, stage=Stage.RESEARCH)
    store.save(state)

    reloaded = store.load(state.project_id)
    assert reloaded.project_id == state.project_id
    assert reloaded.topic.title == topic.title
    assert reloaded.stage == Stage.RESEARCH
    assert state.project_id in store.list_projects()
