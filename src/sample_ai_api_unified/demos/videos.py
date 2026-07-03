"""Video generation demos: blocking flow, explicit job control, frame extraction."""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

from .. import paths, runner, samples, state, ui
from ..guard import provider_errors

CAPABILITY = "videos"


def _open_file(path: Path) -> None:
    if sys.platform == "darwin":
        subprocess.run(["open", str(path)], check=False)
    else:
        ui.info(f"Saved: {path}")


def _confirm_cost() -> bool:
    return ui.confirm(
        "Video generation can take several minutes and bills real provider credits. Continue?",
        default=True,
    )


def _report(result) -> None:
    ui.info(f"Job {result.job.job_id} status: {result.job.status}")
    for artifact in result.artifacts:
        if artifact.file_path:
            ui.success(f"Artifact: {artifact.file_path}")
            _open_file(Path(artifact.file_path))
        elif artifact.remote_uri:
            ui.success(f"Artifact (remote): {artifact.remote_uri}")


def _blocking(prompt: str) -> None:
    if not state.ensure_capability_ready(CAPABILITY) or not _confirm_cost():
        return
    engine = state.current_engine(CAPABILITY)
    with provider_errors():
        from ai_api_unified import AIBaseVideoProperties, AIFactory

        client = AIFactory.get_ai_video_client()
        properties = AIBaseVideoProperties(
            output_dir=paths.VIDEOS_OUTPUT_DIR, timeout_seconds=1200, poll_interval_seconds=10
        )
        result = runner.run_call(
            f"Generating video via {engine} (blocking)",
            lambda: client.generate_video(prompt, properties),
        )
        _report(result)


def _job_control(prompt: str) -> None:
    """submit → poll with visible status transitions → download."""
    if not state.ensure_capability_ready(CAPABILITY) or not _confirm_cost():
        return
    engine = state.current_engine(CAPABILITY)
    with provider_errors():
        from ai_api_unified import AIBaseVideoProperties, AIFactory

        client = AIFactory.get_ai_video_client()
        properties = AIBaseVideoProperties(output_dir=paths.VIDEOS_OUTPUT_DIR)
        job = client.submit_video_generation(prompt, properties)
        ui.success(f"Submitted job {job.job_id} (provider id: {job.provider_job_id})")

        terminal = {"completed", "failed", "cancelled"}
        while str(job.status).split(".")[-1].lower() not in terminal:
            progress = f" {job.progress_percent}%" if job.progress_percent is not None else ""
            ui.info(f"Status: {job.status}{progress} — polling again in 10s")
            time.sleep(10)
            job = client.get_video_generation_job(job)

        ui.info(f"Terminal status: {job.status}")
        if str(job.status).split(".")[-1].lower() == "completed":
            result = runner.run_call(
                f"Downloading result via {engine}",
                lambda: client.download_video_result(job),
            )
            _report(result)
        elif job.error_message:
            ui.error(job.error_message)


def _latest_video() -> Path | None:
    candidates = sorted(
        paths.VIDEOS_OUTPUT_DIR.rglob("*.mp4"), key=lambda p: p.stat().st_mtime, reverse=True
    )
    return candidates[0] if candidates else None


def _extract_frames() -> None:
    latest = _latest_video()
    raw = ui.ask("Path to an .mp4 video", default=str(latest) if latest else "")
    video_path = Path(raw).expanduser()
    if not raw or not video_path.exists():
        ui.error("No video file found — generate one first.")
        return
    with provider_errors():
        from ai_api_unified import AIBaseVideos

        frames = runner.run_call(
            "Extracting frames at 0s, 1s, 2s",
            lambda: AIBaseVideos.extract_image_frames_from_video_buffer(
                video_path.read_bytes(), time_offsets_seconds=[0.0, 1.0, 2.0]
            ),
        )
        saved = AIBaseVideos.save_image_buffers_as_files(frames, output_dir=paths.FRAMES_OUTPUT_DIR)
        for frame_path in saved:
            ui.success(f"Frame: {frame_path}")
        if saved:
            _open_file(saved[0])


def run() -> None:
    while True:
        ui.header(
            "Video generation",
            f"engine: {state.current_engine(CAPABILITY) or 'unset'}  "
            f"model: {state.current_model(CAPABILITY) or 'default'}",
        )
        picked = ui.choose(
            "Video generation demos",
            [
                ui.MenuOption("Generate (blocking convenience call)", "blocking"),
                ui.MenuOption(
                    "Generate with explicit job control", "jobs", "submit → poll → download"
                ),
                ui.MenuOption("Extract frames from a generated video", "frames"),
                ui.MenuOption("Switch engine", "engine"),
                ui.MenuOption("Switch model", "model"),
            ],
        )
        if picked is None:
            return
        if picked.value in ("blocking", "jobs"):
            prompt = ui.choose_value("Pick a prompt", list(samples.VIDEO_GEN_PROMPTS))
            if not prompt:
                continue
            if picked.value == "blocking":
                _blocking(prompt)
            else:
                _job_control(prompt)
        elif picked.value == "frames":
            _extract_frames()
        elif picked.value == "engine":
            state.switch_engine_menu(CAPABILITY)
        elif picked.value == "model":
            state.switch_model_menu(CAPABILITY)
