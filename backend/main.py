"""
main.py — Standalone API for Verbum (AI Caption Software with Catholic Ambiance).

Key features:
  - No Sign-In / Auth required: upload and process videos directly.
  - No Redis: job state lives in an in-memory dict (jobs.py → JOB_STORE).
  - No Celery: transcription runs via FastAPI BackgroundTasks / daemon threads.
  - Serves the React build as static files.
  - Native OS window handled by launcher.py via pywebview.
  - Real-time estimated time countdown (ETA in seconds).
  - Moral Law analysis based on Moses' 10 Commandments and Christ's 2 Commandments.
  - Automatically produces .SRT along with burnt-in video.
"""

import os
import sys
import uuid
import socket
import logging
import threading
from typing import Optional

from fastapi import FastAPI, APIRouter, UploadFile, File, HTTPException, Query, BackgroundTasks
from fastapi.responses import FileResponse, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import shutil
import re
import aiofiles

from jobs import JOB_STORE
from video_utils import STYLE_PRESETS
from worker import (
    transcribe_video,
    transcribe_confirmed,
    resume_after_warning,
    cancel_job,
    get_upload_dir,
)

if sys.platform == "win32":
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        if hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# App init
# ---------------------------------------------------------------------------
app = FastAPI(title="Verbum API", description="AI Caption Generation Engine with Catholic Ambiance")
router = APIRouter()

# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Upload directory
# ---------------------------------------------------------------------------
UPLOAD_DIR = get_upload_dir()


def _get_local_ip() -> str:
    """Detect LAN IP so mobile phones on the same Wi-Fi can connect."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


# ---------------------------------------------------------------------------
# Core endpoints
# ---------------------------------------------------------------------------
@router.get("/server-info")
async def get_server_info():
    """Return local LAN IP and application metadata for phone connectivity."""
    return {
        "app_name": "Verbum",
        "local_ip": _get_local_ip(),
        "version": "2.0.0",
    }


@router.post("/upload")
async def upload_video(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    embed_captions: bool = False,
):
    """
    Stage 1: Save video asynchronously, probe duration, extract audio, and auto-detect language.
    Returns job_id. Job pauses at 'awaiting_user_confirmation'.
    """
    job_id = str(uuid.uuid4())
    raw_filename = file.filename or "video.mp4"
    ext = "mp4"
    if "." in raw_filename:
        ext = raw_filename.rsplit(".", 1)[-1].lower()
    ext = re.sub(r"[^a-z0-9]", "", ext) or "mp4"
    file_path = os.path.abspath(os.path.join(UPLOAD_DIR, f"{job_id}.{ext}"))

    try:
        # Asynchronously stream uploaded chunks to disk (1MB chunks) so the event loop never blocks
        async with aiofiles.open(file_path, "wb") as buffer:
            while chunk := await file.read(1024 * 1024):
                await buffer.write(chunk)
    except Exception as e:
        logger.error(f"Failed to save uploaded video {raw_filename}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to save file on server disk: {e}")

    # Register the job in the in-memory store
    JOB_STORE[job_id] = {
        "status": "processing",
        "progress": 0,
        "eta_seconds": 15,
        "filename": raw_filename,
        "embed_captions": embed_captions,
    }

    # Dispatch Stage 1 as a background thread
    background_tasks.add_task(transcribe_video, job_id, file_path, embed_captions)

    return {
        "job_id": job_id,
        "status": "processing",
        "progress": 0,
        "eta_seconds": 15,
        "filename": raw_filename,
    }


class CaptionStyleConfig(BaseModel):
    preset: Optional[str] = "classic"
    font_name: Optional[str] = "Arial"
    font_size: Optional[int] = 13
    primary_color: Optional[str] = "#FFFFFF"
    outline_color: Optional[str] = "#000000"
    outline_width: Optional[float] = 1.2
    border_style: Optional[int] = 1
    shadow_depth: Optional[float] = 0.8
    back_color: Optional[str] = "#000000"
    back_opacity: Optional[float] = 0.0
    bold: Optional[bool] = False
    italic: Optional[bool] = False
    uppercase: Optional[bool] = False
    alignment: Optional[int] = 2
    margin_v: Optional[int] = 24


class LanguageConfirmation(BaseModel):
    language: str          # e.g. "en", "fr", "ar", "auto"
    accent_id: str = "none"  # e.g. "en_british", "es_mexican"
    caption_style: Optional[CaptionStyleConfig] = None


@router.get("/caption-style-presets")
async def get_caption_style_presets():
    """Return available high-level caption aesthetic presets."""
    return STYLE_PRESETS


@router.post("/confirm-language/{job_id}")
async def confirm_language(
    job_id: str,
    body: LanguageConfirmation,
):
    """
    Stage 2: User confirms (or overrides) the detected language, selects
    an accent, and optionally configures caption aesthetics / styles.
    Triggers full transcription in a background thread.
    """
    job_data = JOB_STORE.get(job_id)
    if not job_data:
        raise HTTPException(status_code=404, detail="Job not found")

    current_status = job_data.get("status")
    # If already transcribing, return idempotent success to avoid race condition / double-click errors
    if current_status == "transcribing":
        return {"status": "transcription_started", "language": body.language, "accent_id": body.accent_id}

    if current_status != "awaiting_user_confirmation":
        raise HTTPException(
            status_code=400,
            detail=f"Job is not awaiting confirmation (status: {current_status})",
        )

    style_dict = None
    if body.caption_style:
        style_dict = (
            body.caption_style.model_dump()
            if hasattr(body.caption_style, "model_dump")
            else body.caption_style.dict()
        )

    # Update job with user's choices
    JOB_STORE[job_id].update({
        "status": "transcribing",
        "progress": 25,
        "confirmed_language": body.language,
        "confirmed_accent_id": body.accent_id,
        "caption_style": style_dict,
    })

    # Launch Stage 2 in a daemon thread
    t = threading.Thread(
        target=transcribe_confirmed,
        args=(job_id, body.language, body.accent_id),
        daemon=True,
    )
    t.start()

    return {"status": "transcription_started", "language": body.language, "accent_id": body.accent_id}


@router.post("/proceed-despite-warning/{job_id}")
async def proceed_despite_warning(job_id: str):
    """
    User acknowledged the moral law warning and elected to proceed anyway.
    Resumes video burning / completion.
    """
    job_data = JOB_STORE.get(job_id)
    if not job_data:
        raise HTTPException(status_code=404, detail="Job not found")

    success = resume_after_warning(job_id)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to resume job.")

    return {"status": "resumed"}


@router.post("/cancel-job/{job_id}")
async def cancel_job_endpoint(job_id: str):
    """
    User chose to cancel and discard the video after moral warning.
    """
    job_data = JOB_STORE.get(job_id)
    if not job_data:
        raise HTTPException(status_code=404, detail="Job not found")

    cancel_job(job_id)
    return {"status": "cancelled"}


@router.get("/status/{job_id}")
async def get_status(job_id: str):
    job_data = JOB_STORE.get(job_id)
    if not job_data:
        raise HTTPException(status_code=404, detail="Job not found")

    return {
        "status": job_data.get("status"),
        "progress": job_data.get("progress", 0),
        "eta_seconds": job_data.get("eta_seconds", 0),
        "duration": job_data.get("duration", 0),
        "filename": job_data.get("filename"),
        "video_burned": job_data.get("video_burned", False),
        "has_srt": job_data.get("has_srt", False),
        "morality_alert": job_data.get("morality_alert"),
        "ultimate_message": job_data.get("ultimate_message"),
        "caption_style": job_data.get("caption_style"),
        "error": job_data.get("error"),
        "detected_language": job_data.get("detected_language"),
        "detected_probability": job_data.get("detected_probability"),
        "detected_top_candidates": job_data.get("detected_top_candidates", []),
        "final_language": job_data.get("final_language"),
        "confirmed_language": job_data.get("confirmed_language"),
        "confirmed_accent_id": job_data.get("confirmed_accent_id"),
    }


def _fast_file_copy(src: str, dst: str):
    """High-speed buffered file copy using 4MB chunks for instant disk writes."""
    with open(src, "rb") as fsrc, open(dst, "wb") as fdst:
        shutil.copyfileobj(fsrc, fdst, length=4 * 1024 * 1024)


@router.get("/download/{job_id}")
async def download_srt(job_id: str):
    job_data = JOB_STORE.get(job_id)
    if not job_data:
        raise HTTPException(status_code=404, detail="Job not found")

    srt_path = os.path.abspath(os.path.join(UPLOAD_DIR, f"{job_id}.srt"))
    if os.path.exists(srt_path):
        base_name = os.path.splitext(job_data.get("filename", "captions"))[0]
        return FileResponse(
            srt_path,
            filename=f"{base_name}.srt",
            media_type="application/x-subrip",
            content_disposition_type="attachment",
        )
    raise HTTPException(status_code=404, detail="SRT file generation in progress or failed.")


@router.post("/download-srt-to-disk/{job_id}")
async def download_srt_to_disk(
    job_id: str,
    dest_path: str = Query(..., description="Absolute path where the SRT file should be saved"),
):
    """
    Standalone-only endpoint: write the SRT file directly to a user-chosen path on disk.
    """
    job_data = JOB_STORE.get(job_id)
    if not job_data:
        raise HTTPException(status_code=404, detail="Job not found")

    srt_path = os.path.abspath(os.path.join(UPLOAD_DIR, f"{job_id}.srt"))
    if not os.path.exists(srt_path):
        raise HTTPException(status_code=404, detail="SRT file not found.")

    try:
        dest_path = os.path.abspath(dest_path)
        os.makedirs(os.path.dirname(dest_path), exist_ok=True)
        _fast_file_copy(srt_path, dest_path)
        logger.info(f"SRT saved to disk: {dest_path}")
        return {"success": True, "saved_to": dest_path}
    except Exception as e:
        logger.error(f"Failed to write SRT to {dest_path}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to save file: {e}")


@router.get("/download-video/{job_id}")
async def download_burned_video(job_id: str):
    job_data = JOB_STORE.get(job_id)
    if not job_data:
        raise HTTPException(status_code=404, detail="Job not found")

    video_path = os.path.abspath(os.path.join(UPLOAD_DIR, f"{job_id}_burned.mp4"))
    if os.path.exists(video_path):
        original_name = os.path.splitext(job_data.get("filename", "video"))[0]
        return FileResponse(
            video_path,
            filename=f"{original_name}_captioned.mp4",
            media_type="video/mp4",
            content_disposition_type="attachment",
            headers={"Accept-Ranges": "bytes"},
        )
    raise HTTPException(status_code=404, detail="Processed video not found.")


@router.post("/download-video-to-disk/{job_id}")
async def download_video_to_disk(
    job_id: str,
    dest_path: str = Query(..., description="Absolute path where the video should be saved"),
):
    """
    Standalone-only endpoint: writes the captioned video to disk AND ALSO
    writes the matching .SRT file in the same directory alongside it.
    """
    job_data = JOB_STORE.get(job_id)
    if not job_data:
        raise HTTPException(status_code=404, detail="Job not found")

    video_path = os.path.abspath(os.path.join(UPLOAD_DIR, f"{job_id}_burned.mp4"))
    if not os.path.exists(video_path):
        raise HTTPException(status_code=404, detail="Processed video not found.")

    try:
        dest_path = os.path.abspath(dest_path)
        dest_dir = os.path.dirname(dest_path)
        os.makedirs(dest_dir, exist_ok=True)
        _fast_file_copy(video_path, dest_path)
        logger.info(f"Video saved to disk: {dest_path}")

        # Also copy matching .SRT file alongside the video!
        srt_path = os.path.abspath(os.path.join(UPLOAD_DIR, f"{job_id}.srt"))
        srt_dest = None
        if os.path.exists(srt_path):
            base_name, _ = os.path.splitext(dest_path)
            srt_dest = f"{base_name}.srt"
            _fast_file_copy(srt_path, srt_dest)
            logger.info(f"Matching SRT saved to disk alongside video: {srt_dest}")

        return {"success": True, "saved_to": dest_path, "srt_saved_to": srt_dest}
    except Exception as e:
        logger.error(f"Failed to write video/SRT to {dest_path}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to save file: {e}")


@router.get("/srt/{job_id}")
async def get_srt_content(job_id: str):
    job_data = JOB_STORE.get(job_id)
    if not job_data:
        raise HTTPException(status_code=404, detail="Job not found")

    srt_path = os.path.abspath(os.path.join(UPLOAD_DIR, f"{job_id}.srt"))
    if os.path.exists(srt_path):
        with open(srt_path, "r", encoding="utf-8") as f:
            return {"content": f.read()}
    raise HTTPException(status_code=404, detail="SRT content not found.")


# ---------------------------------------------------------------------------
# Mount API Router (supports both /api prefix for Vercel/proxies and root)
# ---------------------------------------------------------------------------
app.include_router(router, prefix="/api")
app.include_router(router)


# ---------------------------------------------------------------------------
# Static file serving — React build (MUST be mounted LAST)
# ---------------------------------------------------------------------------
def _get_frontend_dist() -> Optional[str]:
    """Find the React dist/ folder in both dev and frozen modes."""
    candidates = []
    if getattr(sys, "frozen", False):
        candidates.append(os.path.join(sys._MEIPASS, "frontend_dist"))
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    candidates.append(os.path.join(repo_root, "frontend", "dist"))
    candidates.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "frontend_dist"))
    for path in candidates:
        if os.path.isdir(path) and os.path.exists(os.path.join(path, "index.html")):
            return path
    return None


_frontend_dist = _get_frontend_dist()
if _frontend_dist:
    app.mount("/", StaticFiles(directory=_frontend_dist, html=True), name="static")
    logger.info(f"Serving frontend from: {_frontend_dist}")
else:
    logger.warning("Frontend dist not found. Run 'npm run build' in the frontend folder.")
