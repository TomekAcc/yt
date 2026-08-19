"""Stage 6: subtitles.

Produces a single, globally-timed SRT file for the whole video from
per-scene word timings. Timings come from the TTS provider when it supports
them (ElevenLabs); otherwise this module forced-aligns the narration against
the rendered audio with faster-whisper so subtitle pacing still tracks the
actual voiceover instead of an estimated words-per-minute guess.
"""
from __future__ import annotations

import textwrap
from pathlib import Path

from ..models import Scene, WordTiming
from ..logging_utils import get_logger

log = get_logger(__name__)

_whisper_model = None  # lazy-loaded singleton; forced alignment is only needed for non-timestamped TTS


def _get_whisper_model():
    global _whisper_model
    if _whisper_model is None:
        from faster_whisper import WhisperModel

        _whisper_model = WhisperModel("base.en", device="cpu", compute_type="int8")
    return _whisper_model


def align_words_with_whisper(audio_path: Path) -> list[WordTiming]:
    model = _get_whisper_model()
    segments, _info = model.transcribe(str(audio_path), word_timestamps=True)
    words: list[WordTiming] = []
    for segment in segments:
        for w in segment.words or []:
            words.append(WordTiming(word=w.word.strip(), start_sec=w.start, end_sec=w.end))
    return words


def ensure_scene_word_timings(scene: Scene) -> list[WordTiming]:
    """Returns the scene's word timings, computing them via forced
    alignment if the TTS provider didn't supply any."""
    if scene.word_timings:
        return scene.word_timings
    if not scene.audio_path or not Path(scene.audio_path).exists():
        raise ValueError(f"Scene {scene.index} has no audio to align subtitles against")
    log.info("Scene %d: no native word timings, forced-aligning with whisper", scene.index)
    scene.word_timings = align_words_with_whisper(Path(scene.audio_path))
    return scene.word_timings


def _group_into_cues(
    words: list[WordTiming], *, max_chars_per_line: int, max_lines: int = 2,
    max_cue_seconds: float = 6.0, max_words: int = 14, pause_break_sec: float = 0.6,
) -> list[list[WordTiming]]:
    max_chars = max_chars_per_line * max_lines
    cues: list[list[WordTiming]] = []
    current: list[WordTiming] = []
    for w in words:
        if current:
            projected_chars = sum(len(x.word) for x in current) + len(current) + len(w.word)
            projected_duration = w.end_sec - current[0].start_sec
            gap = w.start_sec - current[-1].end_sec
            if (
                projected_chars > max_chars
                or projected_duration > max_cue_seconds
                or gap > pause_break_sec
                or len(current) >= max_words
            ):
                cues.append(current)
                current = []
        current.append(w)
    if current:
        cues.append(current)
    return cues


def _format_timestamp(seconds: float) -> str:
    millis = round(seconds * 1000)
    hours, millis = divmod(millis, 3_600_000)
    minutes, millis = divmod(millis, 60_000)
    secs, millis = divmod(millis, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def build_srt(
    scenes: list[Scene],
    scene_offsets_sec: list[float],
    out_path: Path,
    *,
    max_chars_per_line: int = 42,
) -> Path:
    """``scene_offsets_sec[i]`` is when scene ``i``'s audio starts in the
    final assembled timeline (see video_assembler.compute_scene_offsets)."""
    if len(scenes) != len(scene_offsets_sec):
        raise ValueError("scenes and scene_offsets_sec must be the same length")

    entries: list[str] = []
    index = 1
    for scene, offset in zip(scenes, scene_offsets_sec):
        words = ensure_scene_word_timings(scene)
        for cue_words in _group_into_cues(words, max_chars_per_line=max_chars_per_line):
            start = offset + cue_words[0].start_sec
            end = offset + cue_words[-1].end_sec
            text = " ".join(w.word for w in cue_words)
            wrapped = "\n".join(textwrap.wrap(text, width=max_chars_per_line, max_lines=2))
            entries.append(
                f"{index}\n{_format_timestamp(start)} --> {_format_timestamp(end)}\n{wrapped}\n"
            )
            index += 1

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(entries), encoding="utf-8")
    return out_path
