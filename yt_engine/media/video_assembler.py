"""Stage 7: video assembly.

Combines each scene's still image (animated with a Ken Burns pan/zoom) and
narration audio into one continuous video, then burns the subtitle track
from Stage 6 in a second ffmpeg pass. Kept as two passes (render, then burn)
so a subtitle-only re-render never re-does the (expensive) Ken Burns
compositing.
"""
from __future__ import annotations

import itertools
import os
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image

from ..config import VideoConfig
from ..exceptions import ProviderError
from ..logging_utils import get_logger
from ..models import Script

log = get_logger(__name__)

_PAN_DIRECTIONS = {
    "center": (0.0, 0.0),
    "left_to_right": (1.0, 0.0),
    "right_to_left": (-1.0, 0.0),
    "top_to_bottom": (0.0, 1.0),
    "bottom_to_top": (0.0, -1.0),
}


def _cover_crop(img: Image.Image, target_ratio: float) -> Image.Image:
    """Crops ``img`` to exactly ``target_ratio`` (center crop) so the Ken
    Burns pan/zoom always has a consistent-aspect source to work from,
    regardless of what size the image provider actually returned."""
    w, h = img.size
    ratio = w / h
    if ratio > target_ratio:
        new_w = int(h * target_ratio)
        x0 = (w - new_w) // 2
        return img.crop((x0, 0, x0 + new_w, h))
    new_h = int(w / target_ratio)
    y0 = (h - new_h) // 2
    return img.crop((0, y0, w, y0 + new_h))


def make_ken_burns_clip(
    image_path: Path,
    duration: float,
    target_size: tuple[int, int],
    *,
    zoom_range: tuple[float, float],
    pan: str = "center",
    zoom_in: bool = True,
):
    """Returns a moviepy ``VideoClip`` that pans/zooms across ``image_path``
    over ``duration`` seconds, rendered at a constant ``target_size``.

    Implemented as a raw frame function (crop + resize per frame) rather
    than composing moviepy's ``resized``/``cropped`` effects, so the crop
    window is always computed against the true source resolution and never
    drifts out of bounds.
    """
    from moviepy import VideoClip

    target_w, target_h = target_size
    target_ratio = target_w / target_h

    base_img = _cover_crop(Image.open(image_path).convert("RGB"), target_ratio)
    base_w, base_h = base_img.size
    dx_dir, dy_dir = _PAN_DIRECTIONS.get(pan, (0.0, 0.0))
    zoom_lo, zoom_hi = zoom_range
    if not zoom_in:
        zoom_lo, zoom_hi = zoom_hi, zoom_lo

    def frame_function(t: float):
        progress = 0.0 if duration <= 0 else min(t / duration, 1.0)
        scale = zoom_lo + (zoom_hi - zoom_lo) * progress
        crop_w = base_w / scale
        crop_h = base_h / scale
        max_dx = max(base_w - crop_w, 0.0)
        max_dy = max(base_h - crop_h, 0.0)
        x0 = (max_dx / 2) + dx_dir * (max_dx / 2) * (2 * progress - 1)
        y0 = (max_dy / 2) + dy_dir * (max_dy / 2) * (2 * progress - 1)
        x0 = min(max(x0, 0.0), max_dx)
        y0 = min(max(y0, 0.0), max_dy)
        # BICUBIC rather than LANCZOS: this crop+resize runs once per output
        # frame (tens of thousands of times for a full-length video), and
        # LANCZOS's extra sharpness is imperceptible on a panning/zooming
        # shot that YouTube re-encodes on upload anyway -- BICUBIC renders
        # several times faster for the same visual result here.
        crop = base_img.crop((x0, y0, x0 + crop_w, y0 + crop_h)).resize(
            (target_w, target_h), Image.BICUBIC
        )
        return np.asarray(crop)

    return VideoClip(frame_function=frame_function, duration=duration)


def audio_duration(path: Path) -> float:
    from moviepy import AudioFileClip

    with AudioFileClip(str(path)) as clip:
        return clip.duration


def compute_scene_offsets(scenes) -> list[float]:
    """Global start time (seconds) of each scene once its audio clips are
    concatenated in order -- the same timeline both the video track and
    :func:`yt_engine.media.subtitles.build_srt` must agree on."""
    offsets: list[float] = []
    t = 0.0
    for scene in scenes:
        offsets.append(t)
        t += audio_duration(Path(scene.audio_path))
    return offsets


def assemble_video(script: Script, out_path: Path, *, video_config: VideoConfig) -> Path:
    from moviepy import AudioFileClip, concatenate_audioclips, concatenate_videoclips

    missing = [s.index for s in script.scenes if not s.image_path or not s.audio_path]
    if missing:
        raise ProviderError(f"Scenes {missing} are missing image_path/audio_path before assembly")

    pans = itertools.cycle(["center", "left_to_right", "right_to_left", "top_to_bottom"])
    video_clips, audio_clips = [], []
    for scene, pan in zip(script.scenes, pans):
        duration = audio_duration(Path(scene.audio_path))
        scene.est_duration_sec = duration
        video_clips.append(
            make_ken_burns_clip(
                Path(scene.image_path),
                duration,
                video_config.resolution,
                zoom_range=video_config.ken_burns_zoom_range,
                pan=pan,
                zoom_in=(scene.index % 2 == 0),
            )
        )
        audio_clips.append(AudioFileClip(str(scene.audio_path)))

    video = concatenate_videoclips(video_clips, method="chain")
    narration = concatenate_audioclips(audio_clips)
    video = video.with_audio(narration).with_fps(video_config.fps)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    log.info("Rendering %d scenes (%.1fs) -> %s", len(script.scenes), video.duration, out_path)
    # "veryfast" trades a little compression efficiency for a large encode
    # speedup -- irrelevant here since YouTube re-encodes on upload anyway.
    # threads=cpu_count lets libx264 actually use every core instead of
    # defaulting to one.
    video.write_videofile(
        str(out_path),
        fps=video_config.fps,
        codec="libx264",
        audio_codec="aac",
        preset="veryfast",
        threads=os.cpu_count() or 4,
        logger=None,
    )

    for clip in (*video_clips, *audio_clips, video, narration):
        clip.close()
    return out_path


def burn_subtitles(
    video_path: Path, srt_path: Path, out_path: Path, *, font: str = "Arial", margin_v: int = 40
) -> Path:
    import imageio_ffmpeg

    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
    style = (
        f"FontName={font},FontSize=20,PrimaryColour=&H00FFFFFF,"
        f"OutlineColour=&H80000000,BorderStyle=3,Outline=1,Shadow=0,MarginV={margin_v}"
    )
    # ffmpeg's filtergraph parser treats ':' and other punctuation as
    # argument separators, so the path needs escaping when passed inside a
    # quoted filter option.
    escaped_path = str(srt_path).replace("\\", "/").replace(":", "\\:")
    cmd = [
        ffmpeg_exe,
        "-y",
        "-i",
        str(video_path),
        "-vf",
        f"subtitles='{escaped_path}':force_style='{style}'",
        "-c:a",
        "copy",
        str(out_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise ProviderError(f"ffmpeg subtitle burn failed:\n{result.stderr[-2000:]}")
    return out_path


def render(script: Script, project_dir: Path, video_config: VideoConfig) -> Path:
    """Full stage 7 entry point: assemble the Ken Burns cut, generate the
    global SRT from scene word timings, burn it in, and return the final
    video path."""
    from .subtitles import build_srt

    raw_path = project_dir / "video_raw.mp4"
    final_path = project_dir / "video_final.mp4"
    srt_path = project_dir / "subtitles" / "captions.srt"

    assemble_video(script, raw_path, video_config=video_config)
    offsets = compute_scene_offsets(script.scenes)
    build_srt(
        script.scenes, offsets, srt_path, max_chars_per_line=video_config.subtitle_max_chars_per_line
    )
    burn_subtitles(
        raw_path, srt_path, final_path,
        font=video_config.subtitle_font, margin_v=video_config.subtitle_margin_v,
    )
    return final_path
