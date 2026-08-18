"""Filesystem-backed persistence for :class:`~yt_engine.models.ProjectState`.

Every project gets its own directory under ``workspace/<project_id>/`` with
a ``state.json`` snapshot written after *every* stage transition. This is
what makes the pipeline resumable: a crash or an API outage mid-run costs at
most one stage of work, not the whole video.
"""
from __future__ import annotations

from pathlib import Path

from ..models import ProjectState
from ..exceptions import ResumeError

STATE_FILENAME = "state.json"


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
        return ProjectState.model_validate_json(path.read_text())

    def list_projects(self) -> list[str]:
        return sorted(
            p.name
            for p in self.workspace_dir.iterdir()
            if p.is_dir() and (p / STATE_FILENAME).exists()
        )
