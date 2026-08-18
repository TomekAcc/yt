from __future__ import annotations

import numpy as np

from tests.conftest import write_dummy_image, write_silent_wav
from yt_engine.config import VideoConfig
from yt_engine.media import video_assembler as va
from yt_engine.models import Scene, Script, Source, SubFormat, WordTiming


def test_ken_burns_clip_renders_at_target_size(tmp_path):
    img_path = write_dummy_image(tmp_path / "img.png", size=(640, 400))
    clip = va.make_ken_burns_clip(img_path, duration=2.0, target_size=(320, 180), zoom_range=(1.0, 1.1))
    frame_start = clip.get_frame(0.0)
    frame_end = clip.get_frame(1.99)
    assert frame_start.shape == (180, 320, 3)
    assert frame_end.shape == (180, 320, 3)
    # zoom should change the crop, so start/end frames should differ
    assert not np.array_equal(frame_start, frame_end)


def test_audio_duration_matches_written_wav(tmp_path):
    wav_path = write_silent_wav(tmp_path / "a.wav", seconds=1.5)
    assert abs(va.audio_duration(wav_path) - 1.5) < 0.05


def test_compute_scene_offsets_accumulates_durations(tmp_path):
    a0 = write_silent_wav(tmp_path / "a0.wav", seconds=1.0)
    a1 = write_silent_wav(tmp_path / "a1.wav", seconds=2.0)
    scenes = [
        Scene(index=0, narration="x", image_prompt="p", audio_path=a0),
        Scene(index=1, narration="y", image_prompt="p", audio_path=a1),
    ]
    offsets = va.compute_scene_offsets(scenes)
    assert offsets[0] == 0.0
    assert abs(offsets[1] - 1.0) < 0.05


def test_render_produces_playable_video_with_burned_subtitles(tmp_path):
    img0 = write_dummy_image(tmp_path / "img0.png")
    img1 = write_dummy_image(tmp_path / "img1.png")
    a0 = write_silent_wav(tmp_path / "a0.wav", seconds=1.0)
    a1 = write_silent_wav(tmp_path / "a1.wav", seconds=0.8)

    scenes = [
        Scene(
            index=0, narration="Markets opened calm.", image_prompt="p",
            image_path=img0, audio_path=a0,
            word_timings=[WordTiming(word=w, start_sec=i * 0.2, end_sec=i * 0.2 + 0.15)
                          for i, w in enumerate(["Markets", "opened", "calm."])],
        ),
        Scene(
            index=1, narration="Then panic hit.", image_prompt="p",
            image_path=img1, audio_path=a1,
            word_timings=[WordTiming(word=w, start_sec=i * 0.2, end_sec=i * 0.2 + 0.15)
                          for i, w in enumerate(["Then", "panic", "hit."])],
        ),
    ]
    script = Script(
        title="Test Video", sub_format=SubFormat.CURRENCY_CRISIS, thesis="t",
        scenes=scenes, sources=[Source(title="s")],
    )
    video_config = VideoConfig(resolution=(320, 180), fps=10)

    final_path = va.render(script, tmp_path, video_config)

    assert final_path.exists()
    assert final_path.stat().st_size > 1000
    assert (tmp_path / "subtitles" / "captions.srt").exists()
