from __future__ import annotations

from yt_engine.config import Settings


def test_load_content_rules_reads_the_real_file():
    settings = Settings.load()
    rules = settings.load_content_rules()
    assert "factually accurate" in rules.lower()
    assert "entertaining" in rules.lower()


def test_load_content_rules_returns_empty_string_when_file_missing(tmp_path):
    settings = Settings.load()
    settings.channel.content_rules = str(tmp_path / "does_not_exist.md")
    assert settings.load_content_rules() == ""
