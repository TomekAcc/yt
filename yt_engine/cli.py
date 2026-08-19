"""Command-line entry point.

    python -m yt_engine ideate
    python -m yt_engine produce --pick 0
    python -m yt_engine run <project_id>
    python -m yt_engine status <project_id>
    python -m yt_engine list

See README.md for the full walkthrough.
"""
from __future__ import annotations

import argparse
import json
import sys

from .config import Settings
from .exceptions import PipelineError
from .logging_utils import get_logger
from .models import ProjectState, TopicIdea
from .pipeline import Pipeline

log = get_logger(__name__)


def _cli_approval_callback(state: ProjectState) -> bool:
    report = state.compliance
    print(f"\n--- Compliance review: {state.script.title} ---")
    for check in report.checks:
        mark = "PASS" if check.passed else "FAIL"
        print(f"  [{mark}] {check.name}: {check.detail}")
    print(f"\nTHESIS: {state.script.thesis}\n")
    for i, scene in enumerate(state.script.scenes[:3]):
        print(f"  scene {i}: {scene.narration}")
    if len(state.script.scenes) > 3:
        print(f"  ... {len(state.script.scenes) - 3} more scenes")
    answer = input("\nApprove this script for production? [y/N] ").strip().lower()
    return answer == "y"


def _candidates_path(settings: Settings):
    return settings.workspace_dir / "candidates.json"


def cmd_ideate(args, settings: Settings) -> None:
    pipeline = Pipeline(settings)
    topics = pipeline.ideate(count=args.count)
    for i, topic in enumerate(topics):
        print(f"[{i}] ({topic.sub_format.value}) {topic.title}\n     {topic.logline}")
    _candidates_path(settings).write_text(json.dumps([t.model_dump() for t in topics], default=str, indent=2))
    print(f"\nSaved {len(topics)} candidates. Run `produce --pick <N>` to build one.")


def _load_pick(settings: Settings, pick: int) -> TopicIdea:
    path = _candidates_path(settings)
    if not path.exists():
        print("No candidates found. Run `ideate` first.", file=sys.stderr)
        sys.exit(1)
    candidates = json.loads(path.read_text())
    if pick >= len(candidates):
        print(f"Pick {pick} out of range (have {len(candidates)} candidates).", file=sys.stderr)
        sys.exit(1)
    return TopicIdea(**candidates[pick])


def cmd_produce(args, settings: Settings) -> None:
    pipeline = Pipeline(settings)
    topic = _load_pick(settings, args.pick)
    state = pipeline.create_project(topic)
    _run_and_report(pipeline, state, args)


def cmd_run(args, settings: Settings) -> None:
    pipeline = Pipeline(settings)
    state = pipeline.store.load(args.project_id)
    _run_and_report(pipeline, state, args)


def _run_and_report(pipeline: Pipeline, state: ProjectState, args) -> None:
    callback = None if args.auto_approve else _cli_approval_callback
    try:
        state = pipeline.run(state, approval_callback=callback, upload=not args.no_upload)
    except PipelineError as exc:
        print(f"Pipeline failed for {exc.project_id}: {exc}", file=sys.stderr)
        sys.exit(1)

    print(f"\nProject {state.project_id}: stage={state.stage.value}")
    if state.upload:
        print(f"Uploaded: {state.upload.url}")
    elif state.video_path:
        print(f"Rendered video: {state.video_path}")


def cmd_status(args, settings: Settings) -> None:
    pipeline = Pipeline(settings)
    state = pipeline.store.load(args.project_id)
    print(state.model_dump_json(indent=2, exclude={"script"}))


def cmd_list(args, settings: Settings) -> None:
    pipeline = Pipeline(settings)
    for project_id in pipeline.store.list_projects():
        state = pipeline.store.load(project_id)
        title = state.topic.title if state.topic else "(no topic)"
        print(f"{project_id}  [{state.stage.value:20s}]  {title}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="yt_engine")
    parser.add_argument("--settings", default=None, help="Path to settings.yaml")
    sub = parser.add_subparsers(dest="command", required=True)

    p_ideate = sub.add_parser("ideate", help="Generate candidate video topics")
    p_ideate.add_argument("--count", type=int, default=5)
    p_ideate.set_defaults(func=cmd_ideate)

    p_produce = sub.add_parser("produce", help="Create and run a project from a saved candidate")
    p_produce.add_argument("--pick", type=int, required=True, help="Index from the last `ideate` run")
    p_produce.add_argument("--auto-approve", action="store_true", help="Skip the human compliance gate")
    p_produce.add_argument("--no-upload", action="store_true", help="Render but don't upload")
    p_produce.set_defaults(func=cmd_produce)

    p_run = sub.add_parser("run", help="Resume an existing project to completion")
    p_run.add_argument("project_id")
    p_run.add_argument("--auto-approve", action="store_true")
    p_run.add_argument("--no-upload", action="store_true")
    p_run.set_defaults(func=cmd_run)

    p_status = sub.add_parser("status", help="Show a project's saved state")
    p_status.add_argument("project_id")
    p_status.set_defaults(func=cmd_status)

    p_list = sub.add_parser("list", help="List all projects")
    p_list.set_defaults(func=cmd_list)

    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    settings = Settings.load(args.settings)
    args.func(args, settings)


if __name__ == "__main__":
    main()
