from __future__ import annotations

from dataclasses import dataclass

from yt_engine.media import subtitles
from yt_engine.media.subtitles import _format_timestamp, _group_into_cues, align_words_with_whisper, build_srt
from yt_engine.models import Scene, WordTiming


@dataclass
class _FakeWhisperWord:
    word: str
    start: float
    end: float


class _FakeWhisperSegment:
    def __init__(self, words):
        self.words = words


class _FakeWhisperModel:
    def __init__(self, segments):
        self._segments = segments

    def transcribe(self, audio_path, word_timestamps=True):
        return self._segments, None


def _words(text: str, gap=0.05, word_dur=0.25, start=0.0):
    words = []
    t = start
    for w in text.split():
        words.append(WordTiming(word=w, start_sec=t, end_sec=t + word_dur))
        t += word_dur + gap
    return words


def test_format_timestamp():
    assert _format_timestamp(0) == "00:00:00,000"
    assert _format_timestamp(61.234) == "00:01:01,234"


def test_group_into_cues_respects_char_limit():
    words = _words("the quick brown fox jumps over the lazy dog and then some more words here")
    cues = _group_into_cues(words, max_chars_per_line=20, max_lines=2)
    for cue in cues:
        text = " ".join(w.word for w in cue)
        assert len(text) <= 40


def test_group_into_cues_breaks_on_long_pause():
    words = _words("hello there") + _words("a new sentence begins", start=5.0)
    cues = _group_into_cues(words, max_chars_per_line=100, max_lines=2, pause_break_sec=0.6)
    assert len(cues) == 2


def test_build_srt_uses_global_scene_offsets(tmp_path):
    scene0 = Scene(index=0, narration="hello there", image_prompt="p", word_timings=_words("hello there"))
    scene1 = Scene(index=1, narration="goodbye now", image_prompt="p", word_timings=_words("goodbye now"))
    out = build_srt([scene0, scene1], [0.0, 10.0], tmp_path / "out.srt")

    content = out.read_text()
    assert "hello there" in content
    assert "goodbye now" in content
    # scene1's first cue must start at/after the 10s offset, not at 0s
    lines = content.splitlines()
    goodbye_block_start = next(i for i, l in enumerate(lines) if "goodbye now" in l) - 1
    timestamp_line = lines[goodbye_block_start]
    assert timestamp_line.startswith("00:00:10")


def test_align_words_with_whisper_drops_symbol_only_tokens(monkeypatch):
    fake_words = [
        _FakeWhisperWord(word=" Hello", start=0.0, end=0.3),
        _FakeWhisperWord(word=" ♪", start=0.3, end=0.4),  # non-speech artifact
        _FakeWhisperWord(word=" -", start=0.4, end=0.5),  # punctuation-only artifact
        _FakeWhisperWord(word=" world.", start=0.5, end=0.8),
    ]
    fake_model = _FakeWhisperModel([_FakeWhisperSegment(fake_words)])
    monkeypatch.setattr(subtitles, "_get_whisper_model", lambda: fake_model)

    words = align_words_with_whisper("fake_audio.wav")

    assert [w.word for w in words] == ["Hello", "world."]
