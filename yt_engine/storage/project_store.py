"""Filesystem-backed persistence for :class:`~yt_engine.models.ProjectState`.

Every project gets its own directory under ``workspace/<project_id>/`` with
a ``state.json`` snapshot written after *every* stage transition. This is
what makes the pipeline resumable: a crash or an API outage mid-run costs at
most one stage of work, not the whole video.
"""
from __future__ import annotations

from pathlib import Path

from ..models import ProjectState, Stage
from ..exceptions import ResumeError

STATE_FILENAME = "state.json"


def _infer_resumable_stage(state: ProjectState) -> Stage:
    """Best-effort recovery for state files written by a pre-fix version of
    the pipeline, which stamped a terminal FAILED stage over whatever was
    actually in progress, destroying that information. Infers the correct
    stage to resume at from which fields are actually populated, so a legacy
    ``"stage": "failed"`` project doesn't dead-end with a KeyError and doesn't
    lose already-completed work (e.g. generated images) by restarting."""
    if state.upload:
        return Stage.DONE
    if state.metadata:
        return Stage.UPLOAD
    if state.video_path:
        return Stage.METADATA
    if state.script and state.script.scenes:
        if all(s.word_timings for s in state.script.scenes):
            return Stage.ASSEMBLY
        if all(s.audio_path for s in state.script.scenes):
            return Stage.SUBTITLES
        if all(s.image_path for s in state.script.scenes):
            return Stage.NARRATION
        return Stage.IMAGE_GENERATION
    if state.compliance is not None:
        return Stage.COMPLIANCE_REVIEW
    if state.research:
        return Stage.SCRIPTING
    if state.topic:
        return Stage.RESEARCH
    return Stage.IDEATION


class ProjectStore:
    def __init__(self, workspace_dir: Path) -> None:
        self.workspace_dir = Path(workspace_dir)
        self.workspace_dir.mkdir(parents=True, exist_ok=True)

    def project_dir(self, project_id: str) -> Path:
        path = self.workspace_dir / project_id
        path.mkdir(parents=True, exist_ok=True)
        (path / "images").mkdir(exist_ok=True)
        (path / "audio").mkdir(exist_ok=True)
        (path / "subtitles").mkdir(exist_ok=True)
        return path

    def save(self, state: ProjectState) -> Path:
        state.touch()
        path = self.project_dir(state.project_id) / STATE_FILENAME
        path.write_text(state.model_dump_json(indent=2, exclude_none=False))
        return path

    def load(self, project_id: str) -> ProjectState:
        path = self.workspace_dir / project_id / STATE_FILENAME
        if not path.exists():
            raise ResumeError(
                f"No saved state for project {project_id!r} at {path}",
                project_id=project_id,
            )
        state = ProjectState.model_validate_json(path.read_text())
        if state.stage == Stage.FAILED:
            state.stage = _infer_resumable_stage(state)
            state.error = state.error or (
                "recovered from a legacy FAILED state written before stage "
                "preservation was fixed; inferred resume stage from completed work"
            )
        return state

    def list_projects(self) -> list[str]:
        return sorted(
            p.name
            for p in self.workspace_dir.iterdir()
            if p.is_dir() and (p / STATE_FILENAME).exists()
        )
