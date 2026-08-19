"""Orchestrator: wires every stage together against one resumable
:class:`~yt_engine.models.ProjectState`.

Design goals, straight from the task brief:

* **Resumable.** State is saved to disk after every stage (see
  :class:`~yt_engine.storage.ProjectStore`), so a crashed or interrupted run
  picks back up at the next stage instead of re-spending API budget on
  finished work.
* **Compliance-gated.** The pipeline physically cannot reach image/voice
  generation without passing the compliance stage (STRATEGY.md §5), and by
  default that stage blocks for a human approval callback rather than
  auto-continuing.
"""
from __future__ import annotations

from functools import cached_property
from pathlib import Path
from typing import Callable

from .config import Settings
from .content.compliance import ComplianceReviewer
from .content.ideation import TopicIdeator
from .content.llm_client import LLMClient
from .content.research import ResearchAgent
from .content.script_writer import ScriptWriter
from .content.search import build_search_provider
from .exceptions import ComplianceError, PipelineError
from .logging_utils import get_logger
from .media import build_image_provider, build_tts_provider, thumbnail, video_assembler
from .media.subtitles import ensure_scene_word_timings
from .models import ProjectState, Stage, TopicIdea
from .publish.metadata import MetadataGenerator
from .publish.youtube_uploader import YouTubeUploader
from .storage import ProjectStore

log = get_logger(__name__)

ApprovalCallback = Callable[[ProjectState], bool]


class Pipeline:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.store = ProjectStore(settings.workspace_dir)

    # -- lazily-built, provider clients (only touched by stages that need them) --

    @cached_property
    def llm(self) -> LLMClient:
        return LLMClient(self.settings)

    @cached_property
    def ideator(self) -> TopicIdeator:
        return TopicIdeator(self.llm, channel_name=self.settings.channel.name)

    @cached_property
    def researcher(self) -> ResearchAgent:
        search = build_search_provider(self.settings.secrets.tavily_api_key)
        return ResearchAgent(self.llm, search)

    @cached_property
    def script_writer(self) -> ScriptWriter:
        return ScriptWriter(self.llm)

    @cached_property
    def compliance(self) -> ComplianceReviewer:
        return ComplianceReviewer()

    @cached_property
    def metadata_generator(self) -> MetadataGenerator:
        return MetadataGenerator(self.llm)

    @cached_property
    def uploader(self) -> YouTubeUploader:
        return YouTubeUploader(
            self.settings.secrets.youtube_client_secrets_file,
            self.settings.secrets.youtube_token_file,
        )

    # -- project lifecycle --

    def ideate(self, count: int = 5) -> list[TopicIdea]:
        avoid = self._recent_titles()
        return self.ideator.generate(count=count, avoid_titles=avoid)

    def create_project(self, topic: TopicIdea) -> ProjectState:
        state = ProjectState(topic=topic, stage=Stage.RESEARCH)
        self.store.save(state)
        log.info("Created project %s for %r", state.project_id, topic.title)
        return state

    def run(
        self,
        state: ProjectState,
        *,
        approval_callback: ApprovalCallback | None = None,
        upload: bool = True,
    ) -> ProjectState:
        """Advances ``state`` stage by stage until it's DONE, FAILED, or
        blocked waiting on the compliance approval gate."""
        terminal = {Stage.DONE, Stage.FAILED}
        while state.stage not in terminal:
            if state.stage == Stage.UPLOAD and not upload:
                log.info("Stopping before upload stage (upload=False) for %s", state.project_id)
                break
            try:
                blocked = self._execute_stage(state, approval_callback)
            except Exception as exc:  # noqa: BLE001 - persist failure state before re-raising
                state.mark_failed(str(exc))
                self.store.save(state)
                raise PipelineError(str(exc), project_id=state.project_id) from exc

            self.store.save(state)
            if blocked:
                log.info("Project %s paused at %s awaiting approval", state.project_id, state.stage)
                break
        return state

    def resume(self, project_id: str, **run_kwargs) -> ProjectState:
        state = self.store.load(project_id)
        return self.run(state, **run_kwargs)

    def approve(self, state: ProjectState, approved: bool) -> ProjectState:
        """Explicit approval call for callers that don't pass
        ``approval_callback`` into :meth:`run` (e.g. a review UI)."""
        if not state.compliance:
            raise ComplianceError("No compliance report to approve", project_id=state.project_id)
        self.compliance.approve(state.compliance, human_reviewed=True)
        if not approved:
            state.compliance.approved = False
        self.store.save(state)
        return state

    # -- stage dispatch --

    def _execute_stage(self, state: ProjectState, approval_callback: ApprovalCallback | None) -> bool:
        """Returns True if the run loop should stop (pipeline is blocked)."""
        if state.stage == Stage.COMPLIANCE_REVIEW:
            return self._handle_compliance(state, approval_callback)
        handler = self._HANDLERS[state.stage]
        handler(self, state)
        state.advance()
        return False

    def _handle_ideation(self, state: ProjectState) -> None:
        if state.topic is None:
            raise PipelineError("Project has no topic", project_id=state.project_id)

    def _handle_research(self, state: ProjectState) -> None:
        state.research = self.researcher.research(state.topic)

    def _handle_scripting(self, state: ProjectState) -> None:
        lo, hi = self.settings.video.target_minutes
        style_guide = self.settings.load_style_guide()
        state.script = self.script_writer.write(
            state.research,
            target_minutes=(lo + hi) / 2,
            scene_seconds=self.settings.video.scene_max_duration_sec,
            style_guide=style_guide,
            content_rules=self.settings.load_content_rules(),
        )

    def _handle_compliance(self, state: ProjectState, approval_callback: ApprovalCallback | None) -> bool:
        if state.compliance is None:
            state.compliance = self.compliance.review(
                state.script, state.research, recent_sub_formats=self._recent_sub_formats()
            )

        if not self.settings.channel.require_human_approval:
            self.compliance.approve(state.compliance, human_reviewed=False)
        elif not state.compliance.reviewed_by_human:
            if approval_callback is not None:
                approved = approval_callback(state)
                self.compliance.approve(state.compliance, human_reviewed=True)
                state.compliance.approved = state.compliance.approved and approved
            else:
                return True  # blocked: caller must review and call pipeline.approve()

        if not state.compliance.approved:
            raise ComplianceError(
                "Script did not pass compliance review", project_id=state.project_id
            )
        state.advance()
        return False

    def _handle_images(self, state: ProjectState) -> None:
        provider = build_image_provider(self.settings)
        project_dir = self.store.project_dir(state.project_id)
        width, height = self.settings.video.resolution
        for scene in state.script.scenes:
            out_path = project_dir / "images" / f"scene_{scene.index:03d}.png"
            provider.generate(scene.image_prompt, out_path, width=width, height=height)
            scene.image_path = out_path
            log.info("Project %s: generated image for scene %d", state.project_id, scene.index)

    def _handle_narration(self, state: ProjectState) -> None:
        provider = build_tts_provider(self.settings)
        project_dir = self.store.project_dir(state.project_id)
        for scene in state.script.scenes:
            out_path = project_dir / "audio" / f"scene_{scene.index:03d}.{provider.file_extension}"
            result = provider.synthesize(scene.narration, out_path)
            scene.audio_path = result.audio_path
            if result.word_timings:
                scene.word_timings = result.word_timings
            log.info("Project %s: narrated scene %d", state.project_id, scene.index)

    def _handle_subtitles(self, state: ProjectState) -> None:
        for scene in state.script.scenes:
            ensure_scene_word_timings(scene)

    def _handle_assembly(self, state: ProjectState) -> None:
        project_dir = self.store.project_dir(state.project_id)
        state.video_path = video_assembler.render(state.script, project_dir, self.settings.video)

    def _handle_metadata(self, state: ProjectState) -> None:
        metadata = self.metadata_generator.generate(state.script)
        metadata.privacy_status = self.settings.channel.default_privacy_status
        project_dir = self.store.project_dir(state.project_id)
        thumb_path = project_dir / "thumbnail.jpg"
        first_scene = state.script.scenes[0]
        if first_scene.image_path:
            thumbnail.build_thumbnail(Path(first_scene.image_path), state.script.title, thumb_path)
            metadata.thumbnail_path = thumb_path
        state.metadata = metadata

    def _handle_upload(self, state: ProjectState) -> None:
        state.upload = self.uploader.upload(state.video_path, state.metadata)

    _HANDLERS: dict = {}  # populated below the class body

    # -- history, used by ideation (avoid repeats) and compliance (format rotation) --

    def _recent_projects(self, limit: int = 15) -> list[ProjectState]:
        states = []
        for project_id in reversed(self.store.list_projects()[-limit:]):
            try:
                states.append(self.store.load(project_id))
            except Exception:  # noqa: BLE001 - skip corrupt/partial state files
                continue
        return states

    def _recent_titles(self) -> list[str]:
        return [s.topic.title for s in self._recent_projects() if s.topic]

    def _recent_sub_formats(self) -> list[str]:
        return [
            s.script.sub_format.value
            for s in sorted(self._recent_projects(), key=lambda s: s.created_at)
            if s.script
        ]


Pipeline._HANDLERS = {
    Stage.IDEATION: Pipeline._handle_ideation,
    Stage.RESEARCH: Pipeline._handle_research,
    Stage.SCRIPTING: Pipeline._handle_scripting,
    Stage.IMAGE_GENERATION: Pipeline._handle_images,
    Stage.NARRATION: Pipeline._handle_narration,
    Stage.SUBTITLES: Pipeline._handle_subtitles,
    Stage.ASSEMBLY: Pipeline._handle_assembly,
    Stage.METADATA: Pipeline._handle_metadata,
    Stage.UPLOAD: Pipeline._handle_upload,
}
