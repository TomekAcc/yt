"""Shared data models that flow between pipeline stages.

Every model is a pydantic ``BaseModel`` so a :class:`ProjectState` can be
dumped to JSON after each stage and reloaded to resume a failed run without
re-spending money on completed stages (research, images, narration, ...).
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path

from pydantic import BaseModel, Field


def _now() -> datetime:
    return datetime.now(timezone.utc)


def new_project_id() -> str:
    return f"proj_{uuid.uuid4().hex[:12]}"


class SubFormat(str, Enum):
    COMPANY_CASE_STUDY = "company_case_study"
    CURRENCY_CRISIS = "currency_crisis"
    WEALTH_BIOGRAPHY = "wealth_biography"
    ECONOMIC_ERA = "economic_era"


class Stage(str, Enum):
    IDEATION = "ideation"
    RESEARCH = "research"
    SCRIPTING = "scripting"
    COMPLIANCE_REVIEW = "compliance_review"
    IMAGE_GENERATION = "image_generation"
    NARRATION = "narration"
    SUBTITLES = "subtitles"
    ASSEMBLY = "assembly"
    METADATA = "metadata"
    UPLOAD = "upload"
    DONE = "done"
    FAILED = "failed"

    @classmethod
    def order(cls) -> list["Stage"]:
        return [
            cls.IDEATION,
            cls.RESEARCH,
            cls.SCRIPTING,
            cls.COMPLIANCE_REVIEW,
            cls.IMAGE_GENERATION,
            cls.NARRATION,
            cls.SUBTITLES,
            cls.ASSEMBLY,
            cls.METADATA,
            cls.UPLOAD,
            cls.DONE,
        ]

    def next(self) -> "Stage":
        order = Stage.order()
        idx = order.index(self)
        if idx + 1 >= len(order):
            return Stage.DONE
        return order[idx + 1]


class TopicIdea(BaseModel):
    title: str
    sub_format: SubFormat
    logline: str
    era_or_setting: str
    hook: str


class Source(BaseModel):
    title: str
    url: str | None = None
    note: str | None = None


class ResearchBrief(BaseModel):
    topic: TopicIdea
    thesis: str
    key_facts: list[str]
    timeline: list[str] = Field(default_factory=list)
    sources: list[Source]

    @property
    def is_multi_sourced(self) -> bool:
        """Compliance signal: originality requires synthesis across >=2
        independent sources rather than paraphrasing a single one."""
        return len({s.url or s.title for s in self.sources}) >= 2


class Scene(BaseModel):
    index: int
    narration: str
    image_prompt: str
    est_duration_sec: float | None = None
    image_path: Path | None = None
    audio_path: Path | None = None
    word_timings: list["WordTiming"] = Field(default_factory=list)


class WordTiming(BaseModel):
    word: str
    start_sec: float
    end_sec: float


class Script(BaseModel):
    title: str
    sub_format: SubFormat
    thesis: str
    scenes: list[Scene]
    sources: list[Source]
    disclaimer: str = (
        "This video uses AI-generated narration and imagery to visualize "
        "documented historical events. Sources are listed in the "
        "description."
    )

    @property
    def full_narration(self) -> str:
        return "\n".join(s.narration for s in self.scenes)

    @property
    def estimated_word_count(self) -> int:
        return len(self.full_narration.split())


class ComplianceCheck(BaseModel):
    name: str
    passed: bool
    detail: str


class ComplianceReport(BaseModel):
    checks: list[ComplianceCheck]
    reviewed_by_human: bool = False
    approved: bool = False

    @property
    def all_automated_checks_passed(self) -> bool:
        return all(c.passed for c in self.checks)


class YouTubeMetadata(BaseModel):
    title: str
    description: str
    tags: list[str]
    thumbnail_text: str = ""  # short, punchy overlay text -- distinct from the full title
    category_id: str = "27"  # Education
    privacy_status: str = "private"
    contains_synthetic_media: bool = True
    made_for_kids: bool = False
    thumbnail_path: Path | None = None


class UploadResult(BaseModel):
    video_id: str
    url: str
    uploaded_at: datetime = Field(default_factory=_now)


class ProjectState(BaseModel):
    project_id: str = Field(default_factory=new_project_id)
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)
    stage: Stage = Stage.IDEATION
    topic: TopicIdea | None = None
    research: ResearchBrief | None = None
    script: Script | None = None
    compliance: ComplianceReport | None = None
    video_path: Path | None = None
    metadata: YouTubeMetadata | None = None
    upload: UploadResult | None = None
    error: str | None = None

    def touch(self) -> None:
        self.updated_at = _now()

    def mark_failed(self, message: str) -> None:
        """Records the failure but deliberately leaves ``stage`` alone --
        it still points at the stage that was being attempted, so the next
        ``pipeline.run()`` call retries that same stage instead of getting
        stuck (overwriting it with a terminal FAILED value used to make
        every retry a silent no-op)."""
        self.error = message
        self.touch()

    def advance(self) -> None:
        self.stage = self.stage.next()
        self.error = None
        self.touch()
