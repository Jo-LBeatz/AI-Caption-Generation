"""
main.py — Standalone version of the Captions by RegulaVitae API (No Sign-In Required).

Key features:
  - No Sign-In / Auth required: upload and process videos directly
  - No Redis: job state lives in an in-memory dict (jobs.py → JOB_STORE)
  - No Celery: transcription runs via FastAPI BackgroundTasks / daemon threads
  - Serves the React build as static files
  - Native OS window handled by launcher.py via pywebview

Two-stage transcription flow:
  POST /upload          → Stage 1: extract audio + detect language
                          Job status → 'awaiting_user_confirmation'
  POST /confirm-language/{job_id} → Stage 2: transcribe with selected language/accent
                          Job status → 'transcribing' → 'completed'
"""

import os
import sys
import uuid
import logging
import threading
from typing import Optional

from fastapi import FastAPI, UploadFile, File, HTTPException, Query, BackgroundTasks
from fastapi.responses import FileResponse, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import shutil

from jobs import JOB_STORE
from worker import (
    transcribe_video,
    transcribe_confirmed,
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
app = FastAPI(title="Captions by RegulaVitae API", description="AI Caption Generation Engine")

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


# ---------------------------------------------------------------------------
# Core endpoints
# ---------------------------------------------------------------------------
@app.post("/upload")
async def upload_video(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    embed_captions: bool = False,
):
    """
    Stage 1: Save video, extract audio, and auto-detect language.
    Returns job_id. Job pauses at 'awaiting_user_confirmation'.
    Then call POST /confirm-language/{job_id} to proceed.
    """
    job_id = str(uuid.uuid4())
    ext = file.filename.rsplit(".", 1)[-1]
    file_path = os.path.abspath(os.path.join(UPLOAD_DIR, f"{job_id}.{ext}"))

    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save file: {e}")

    # Register the job in the in-memory store
    JOB_STORE[job_id] = {
        "status": "processing",
        "progress": 0,
        "filename": file.filename,
        "embed_captions": embed_captions,
    }

    # Dispatch Stage 1 as a background thread
    background_tasks.add_task(transcribe_video, job_id, file_path, embed_captions)

    return {"job_id": job_id}


class LanguageConfirmation(BaseModel):
    language: str          # e.g. "en", "fr", "ar", "auto"
    accent_id: str = "none"  # e.g. "en_british", "es_mexican"


@app.post("/confirm-language/{job_id}")
async def confirm_language(
    job_id: str,
    body: LanguageConfirmation,
):
    """
    Stage 2: User confirms (or overrides) the detected language and selects
    an accent. Triggers full transcription in a background thread.
    """
    job_data = JOB_STORE.get(job_id)
    if not job_data:
        raise HTTPException(status_code=404, detail="Job not found")
    if job_data.get("status") != "awaiting_user_confirmation":
        raise HTTPException(
            status_code=400,
            detail=f"Job is not awaiting confirmation (status: {job_data.get('status')})",
        )

    # Update job with user's choice
    JOB_STORE[job_id].update({
        "status": "transcribing",
        "progress": 25,
        "confirmed_language": body.language,
        "confirmed_accent_id": body.accent_id,
    })

    # Launch Stage 2 in a daemon thread
    t = threading.Thread(
        target=transcribe_confirmed,
        args=(job_id, body.language, body.accent_id),
        daemon=True,
    )
    t.start()

    return {"status": "transcription_started", "language": body.language, "accent_id": body.accent_id}


@app.get("/status/{job_id}")
async def get_status(job_id: str):
    job_data = JOB_STORE.get(job_id)
    if not job_data:
        raise HTTPException(status_code=404, detail="Job not found")

    return {
        "status": job_data.get("status"),
        "progress": job_data.get("progress", 0),
        "filename": job_data.get("filename"),
        "video_burned": job_data.get("video_burned", False),
        "error": job_data.get("error"),
        "detected_language": job_data.get("detected_language"),
        "detected_probability": job_data.get("detected_probability"),
        "detected_top_candidates": job_data.get("detected_top_candidates", []),
        "final_language": job_data.get("final_language"),
        "confirmed_language": job_data.get("confirmed_language"),
        "confirmed_accent_id": job_data.get("confirmed_accent_id"),
    }


@app.get("/download/{job_id}")
async def download_srt(job_id: str):
    job_data = JOB_STORE.get(job_id)
    if not job_data:
        raise HTTPException(status_code=404, detail="Job not found")

    srt_path = os.path.abspath(os.path.join(UPLOAD_DIR, f"{job_id}.srt"))
    if os.path.exists(srt_path):
        return FileResponse(srt_path, filename=f"captions_{job_id[:8]}.srt", media_type="application/x-subrip")
    raise HTTPException(status_code=404, detail="SRT file generation in progress or failed.")


@app.post("/download-srt-to-disk/{job_id}")
async def download_srt_to_disk(
    job_id: str,
    dest_path: str = Query(..., description="Absolute path where the SRT file should be saved"),
):
    """
    Standalone-only endpoint: write the SRT file directly to a user-chosen path on disk.
    Called by the pywebview JS API after showing a native Save File dialog.
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
        shutil.copy2(srt_path, dest_path)
        logger.info(f"SRT saved to disk: {dest_path}")
        return {"success": True, "saved_to": dest_path}
    except Exception as e:
        logger.error(f"Failed to write SRT to {dest_path}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to save file: {e}")


@app.get("/download-video/{job_id}")
async def download_burned_video(job_id: str):
    job_data = JOB_STORE.get(job_id)
    if not job_data:
        raise HTTPException(status_code=404, detail="Job not found")

    video_path = os.path.abspath(os.path.join(UPLOAD_DIR, f"{job_id}_burned.mp4"))
    if os.path.exists(video_path):
        original_name = os.path.splitext(job_data.get("filename", "video"))[0]
        return FileResponse(video_path, filename=f"{original_name}_captioned.mp4", media_type="video/mp4")
    raise HTTPException(status_code=404, detail="Processed video not found.")


@app.post("/download-video-to-disk/{job_id}")
async def download_video_to_disk(
    job_id: str,
    dest_path: str = Query(..., description="Absolute path where the video should be saved"),
):
    """
    Standalone-only endpoint: write the captioned video directly to a user-chosen path on disk.
    Called by the pywebview JS API after showing a native Save File dialog.
    """
    job_data = JOB_STORE.get(job_id)
    if not job_data:
        raise HTTPException(status_code=404, detail="Job not found")

    video_path = os.path.abspath(os.path.join(UPLOAD_DIR, f"{job_id}_burned.mp4"))
    if not os.path.exists(video_path):
        raise HTTPException(status_code=404, detail="Processed video not found.")

    try:
        dest_path = os.path.abspath(dest_path)
        os.makedirs(os.path.dirname(dest_path), exist_ok=True)
        shutil.copy2(video_path, dest_path)
        logger.info(f"Video saved to disk: {dest_path}")
        return {"success": True, "saved_to": dest_path}
    except Exception as e:
        logger.error(f"Failed to write video to {dest_path}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to save file: {e}")


@app.get("/srt/{job_id}")
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
# Static file serving — React build (MUST be mounted LAST)
# ---------------------------------------------------------------------------
def _get_frontend_dist() -> Optional[str]:
    """
    Find the React dist/ folder in both dev and frozen (PyInstaller) modes.
    Returns None if not found (dev mode without a build).
    """
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
    logger.warning(
        "Frontend dist not found. Run 'npm run build' in the frontend/ folder, "
        "then copy the dist/ output to backend/frontend_dist/ or use the build script."
    )
