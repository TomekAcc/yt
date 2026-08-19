"""Exception hierarchy for the pipeline. Stage-specific errors carry the
project_id so the orchestrator can persist failure state and resume cleanly.
"""
from __future__ import annotations


class PipelineError(Exception):
    """Base class for all pipeline errors."""

    def __init__(self, message: str, *, project_id: str | None = None) -> None:
        super().__init__(message)
        self.project_id = project_id


class ConfigurationError(PipelineError):
    """Missing or invalid configuration (e.g. an unset API key)."""


class ProviderError(PipelineError):
    """A third-party API (LLM, image, TTS, YouTube) returned an error after
    retries were exhausted."""


class ComplianceError(PipelineError):
    """A project failed a monetization/compliance gate and must not proceed
    to rendering or upload."""


class ResumeError(PipelineError):
    """A project's persisted state could not be loaded or is inconsistent
    with the requested resume stage."""
