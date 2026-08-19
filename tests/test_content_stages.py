from __future__ import annotations

from tests.fakes import FakeLLMClient
from yt_engine.content.ideation import TopicIdeator
from yt_engine.content.research import ResearchAgent
from yt_engine.content.script_writer import ScriptWriter
from yt_engine.content.search import NoopSearchProvider
from yt_engine.models import ResearchBrief, Source, SubFormat, TopicIdea
from yt_engine.publish.metadata import MetadataGenerator


def test_topic_ideator_parses_llm_response():
    llm = FakeLLMClient(
        responses=[
            [
                {
                    "title": "The Weimar Hyperinflation",
                    "sub_format": "currency_crisis",
                    "logline": "Money became worthless overnight.",
                    "era_or_setting": "Germany, 1923",
                    "hook": "How does a wheelbarrow of cash buy one loaf of bread?",
                }
            ]
        ]
    )
    topics = TopicIdeator(llm, channel_name="The Ledger").generate(count=1)
    assert len(topics) == 1
    assert isinstance(topics[0], TopicIdea)
    assert topics[0].sub_format == SubFormat.CURRENCY_CRISIS


def test_research_agent_merges_search_and_llm_sources():
    topic = TopicIdea(
        title="The Fall of Barings Bank",
        sub_format=SubFormat.COMPANY_CASE_STUDY,
        logline="l",
        era_or_setting="1995",
        hook="h",
    )
    llm = FakeLLMClient(
        responses=[
            {
                "thesis": "Poor risk controls, not just one trader, sank the bank.",
                "key_facts": [f"fact {i}" for i in range(6)],
                "timeline": ["1995: bank collapses"],
                "sources": [{"title": "Rogue Trader (book)", "url": None, "note": "primary account"}],
            }
        ]
    )
    brief = ResearchAgent(llm, NoopSearchProvider()).research(topic)
    assert isinstance(brief, ResearchBrief)
    assert brief.thesis.startswith("Poor risk controls")
    assert len(brief.key_facts) == 6


def test_script_writer_injects_content_rules_into_system_prompt():
    topic = TopicIdea(
        title="The Fall of Barings Bank", sub_format=SubFormat.COMPANY_CASE_STUDY,
        logline="l", era_or_setting="1995", hook="h",
    )
    brief = ResearchBrief(
        topic=topic, thesis="t", key_facts=["a"], sources=[Source(title="s")],
    )
    llm = FakeLLMClient(
        responses=[{"scenes": [{"narration": "n", "image_prompt": "p"}]}]
    )
    ScriptWriter(llm).write(brief, content_rules="RULE: never invent a fact, always be entertaining.")
    assert "RULE: never invent a fact" in llm.calls[0]["system"]


def test_script_writer_falls_back_when_no_content_rules_given():
    topic = TopicIdea(
        title="The Fall of Barings Bank", sub_format=SubFormat.COMPANY_CASE_STUDY,
        logline="l", era_or_setting="1995", hook="h",
    )
    brief = ResearchBrief(
        topic=topic, thesis="t", key_facts=["a"], sources=[Source(title="s")],
    )
    llm = FakeLLMClient(
        responses=[{"scenes": [{"narration": "n", "image_prompt": "p"}]}]
    )
    ScriptWriter(llm).write(brief, content_rules=None)
    assert "FACTUALLY ACCURATE" in llm.calls[0]["system"]


def test_script_writer_builds_scenes_from_brief():
    topic = TopicIdea(
        title="The Fall of Barings Bank", sub_format=SubFormat.COMPANY_CASE_STUDY,
        logline="l", era_or_setting="1995", hook="h",
    )
    brief = ResearchBrief(
        topic=topic, thesis="t", key_facts=["a", "b"],
        sources=[Source(title="s1"), Source(title="s2")],
    )
    llm = FakeLLMClient(
        responses=[
            {
                "scenes": [
                    {"narration": "It began quietly.", "image_prompt": "a quiet trading floor"},
                    {"narration": "Then the losses mounted fast.", "image_prompt": "a red ticker tape"},
                ]
            }
        ]
    )
    script = ScriptWriter(llm).write(brief, target_minutes=1, scene_seconds=10)
    assert len(script.scenes) == 2
    assert script.scenes[0].index == 0
    assert script.sub_format == SubFormat.COMPANY_CASE_STUDY


def test_metadata_generator_forces_synthetic_media_disclosure():
    from yt_engine.models import Scene, Script

    script = Script(
        title="The Fall of Barings Bank", sub_format=SubFormat.COMPANY_CASE_STUDY, thesis="t",
        scenes=[Scene(index=0, narration="n", image_prompt="p")],
        sources=[Source(title="s", url="https://example.com")],
    )
    llm = FakeLLMClient(
        responses=[
            {
                "title": "The 233-Year-Old Bank Killed By One Trader",
                "description": "A deep dive. Sources: s.\n\nThis video uses AI-generated narration...",
                "tags": ["finance", "history"],
            }
        ]
    )
    metadata = MetadataGenerator(llm).generate(script)
    assert metadata.contains_synthetic_media is True
    assert "Bank" in metadata.title
