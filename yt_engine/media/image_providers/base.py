"""Provider interface for AI image generation. Concrete providers only need
to implement :meth:`generate`; retries and file I/O are handled by callers
against this common contract."""
from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path


class ImageProvider(ABC):
    @abstractmethod
    def generate(self, prompt: str, out_path: Path, *, width: int = 1920, height: int = 1080) -> Path:
        """Generate one image for ``prompt`` and write it to ``out_path``.
        Returns ``out_path`` for chaining."""
