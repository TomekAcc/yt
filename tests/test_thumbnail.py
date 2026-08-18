from __future__ import annotations

from PIL import Image

from tests.conftest import write_dummy_image
from yt_engine.media.thumbnail import THUMBNAIL_SIZE, build_thumbnail


def test_build_thumbnail_produces_correct_size(tmp_path):
    src = write_dummy_image(tmp_path / "src.png", size=(1920, 1080))
    out = build_thumbnail(src, "The Collapse of a 233 Year Old Bank", tmp_path / "thumb.jpg")

    assert out.exists()
    with Image.open(out) as img:
        assert img.size == THUMBNAIL_SIZE
