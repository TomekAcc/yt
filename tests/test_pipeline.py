from __future__ import annotations

import yt_engine.pipeline as pipeline_module
from tests.fakes import FakeImageProvider, FakeLLMClient, FakeTTSProvider, FakeUploader
from yt_engine.models import Stage, SubFormat, TopicIdea
from yt_engine.pipeline import Pipeline

TOPIC = TopicIdea(
    title="The Fall of Barings Bank",
    sub_format=SubFormat.COMPANY_CASE_STUDY,
    logline="A rogue trader sinks Britain's oldest bank.",
    era_or_setting="Singapore, 1995",
    hook="How did one trader bankrupt a 233-year-old bank?",
)

RESEARCH_RESPONSE = {
    "thesis": "Weak internal risk controls, not one rogue trader alone, sank Barings.",
    "key_facts": [f"fact {i}" for i in range(6)],
    "timeline": ["1995: Barings collapses"],
    "sources": [
        {"title": "Rogue Trader (book)", "url": "https://example.com/a", "note": "primary account"},
        {"title": "Financial Times retrospective", "url": "https://example.com/b", "note": "secondary"},
    ],
}
SCRIPT_RESPONSE = {
    "scenes": [
        {"narration": "It began quietly on the trading floor.", "image_prompt": "a quiet 1990s trading floor"},
        {"narration": "Then the hidden losses mounted fast and could not be contained.", "image_prompt": "a red ticker tape climbing"},
        {"narration": "Within days, the 233 year old bank was gone.", "image_prompt": "an empty marble bank lobby"},
    ]
}
METADATA_RESPONSE = {
    "title": "The 233-Year-Old Bank Killed By One Trader",
    "description": "A deep dive into the collapse. Sources: Rogue Trader.\n\nThis video uses AI...",
    "tags": ["finance", "history", "barings"],
}


def _patch_providers(monkeypatch):
    monkeypatch.setattr(pipeline_module, "build_image_provider", lambda settings: FakeImageProvider())
    monkeypatch.setattr(pipeline_module, "build_tts_provider", lambda settings: FakeTTSProvider())


def test_pipeline_blocks_on_compliance_gate_without_callback(tiny_settings, monkeypatch):
    _patch_providers(monkeypatch)
    pipeline = Pipeline(tiny_settings)
    pipeline.llm = FakeLLMClient([RESEARCH_RESPONSE, SCRIPT_RESPONSE, METADATA_RESPONSE])

    state = pipeline.create_project(TOPIC)
    state = pipeline.run(state)  # no approval_callback -> should block

    assert state.stage == Stage.COMPLIANCE_REVIEW
    assert state.compliance is not None
    assert state.compliance.approved is False


def test_pipeline_runs_to_completion_after_approval(tiny_settings, monkeypatch):
    _patch_providers(monkeypatch)
    pipeline = Pipeline(tiny_settings)
    pipeline.llm = FakeLLMClient([RESEARCH_RESPONSE, SCRIPT_RESPONSE, METADATA_RESPONSE])
    fake_uploader = FakeUploader()
    pipeline.uploader = fake_uploader

    state = pipeline.create_project(TOPIC)
    state = pipeline.run(state)
    assert state.stage == Stage.COMPLIANCE_REVIEW

    pipeline.approve(state, approved=True)
    state = pipeline.run(state)

    assert state.stage == Stage.DONE
    assert state.video_path is not None and state.video_path.exists()
    assert state.upload is not None
    assert state.upload.video_id == "fake123"
    assert fake_uploader.uploaded_with[0] == state.video_path


def test_pipeline_resumes_from_saved_state_without_repeating_llm_calls(tiny_settings, monkeypatch):
    _patch_providers(monkeypatch)

    # First process: run through research + scripting only, then "crash"
    # (simulated by just building a fresh Pipeline against the same
    # workspace, as a new process would).
    pipeline1 = Pipeline(tiny_settings)
    pipeline1.llm = FakeLLMClient([RESEARCH_RESPONSE, SCRIPT_RESPONSE])
    state = pipeline1.create_project(TOPIC)
    state = pipeline1.run(state)  # blocks at compliance, research+scripting already persisted
    assert state.script is not None

    # Second process: only the metadata-stage LLM call should still be
    # needed -- if resumption re-ran research/scripting it would exhaust
    # this smaller fake queue and raise.
    pipeline2 = Pipeline(tiny_settings)
    pipeline2.llm = FakeLLMClient([METADATA_RESPONSE])
    pipeline2.uploader = FakeUploader()

    resumed = pipeline2.store.load(state.project_id)
    pipeline2.approve(resumed, approved=True)
    resumed = pipeline2.run(resumed)

    assert resumed.stage == Stage.DONE
    assert resumed.script.title == state.script.title
