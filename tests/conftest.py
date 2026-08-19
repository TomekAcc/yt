from __future__ import annotations

import struct
import wave
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from yt_engine.config import ChannelConfig, ProviderConfig, Settings, VideoConfig


def write_silent_wav(path: Path, seconds: float, sample_rate: int = 22050) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    n_samples = int(seconds * sample_rate)
    with wave.open(str(path), "w") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sample_rate)
        for i in range(n_samples):
            value = int(2000 * np.sin(2 * np.pi * 440 * i / sample_rate))
            w.writeframesraw(struct.pack("<h", value))
    return path


def write_dummy_image(path: Path, size: tuple[int, int] = (320, 180)) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    arr = (np.random.rand(size[1], size[0], 3) * 255).astype("uint8")
    Image.fromarray(arr).save(path)
    return path


@pytest.fixture
def tiny_settings(tmp_path: Path) -> Settings:
    return Settings(
        channel=ChannelConfig(require_human_approval=True),
        providers=ProviderConfig(),
        video=VideoConfig(resolution=(320, 180), fps=10),
        workspace_dir=tmp_path / "workspace",
    )
