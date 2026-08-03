"""
main.py — Standalone version of the Captions by REGULA API.

Key differences from the Docker version:
  - No Redis: job state lives in an in-memory dict (jobs.py → JOB_STORE)
  - No Celery: transcription runs via FastAPI BackgroundTasks (background thread)
  - No Redis auth store: user credentials are persisted in SQLite (database.py)
  - Serves the React build as static files so no separate nginx is needed
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
import csv
import io
import threading
from datetime import datetime, timedelta
from typing import Optional

from fastapi import FastAPI, UploadFile, File, HTTPException, Depends, Header, Query, BackgroundTasks
from fastapi.responses import FileResponse, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, EmailStr
from passlib.context import CryptContext
from jose import JWTError, jwt
import shutil
import dns.resolver

import database
from jobs import JOB_STORE
from worker import (
    transcribe_video,
    transcribe_confirmed,
    get_upload_dir,
)

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# App init + DB init
# ---------------------------------------------------------------------------
app = FastAPI(title="Captions by REGULA API", description="AI Caption Generation Engine")
database.init_db()

# ---------------------------------------------------------------------------
# CORS  (still useful when running in dev mode without the static mount)
# ---------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Auth configuration
# ---------------------------------------------------------------------------
SECRET_KEY = os.getenv("JWT_SECRET", "SACRED_HEART_OF_JESUS_AUTHENTICATION_KEY")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_DAYS = 30
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# ---------------------------------------------------------------------------
# Upload directory
# ---------------------------------------------------------------------------
UPLOAD_DIR = get_upload_dir()


# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------
class UserAuth(BaseModel):
    email: EmailStr
    password: str


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=ACCESS_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def validate_email_domain(email: str) -> bool:
    """Confirm the email domain has MX records (can receive mail)."""
    try:
        domain = email.split("@")[1]
        dns.resolver.resolve(domain, "MX")
        return True
    except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer, dns.exception.DNSException):
        return False


async def get_current_user(
    authorization: Optional[str] = Header(None),
    token: Optional[str] = Query(None),
    auth_query: Optional[str] = Query(None, alias="authorization"),
) -> str:
    jwt_token = None
    if authorization and authorization.startswith("Bearer "):
        jwt_token = authorization.split(" ")[1]
    elif token:
        jwt_token = token.replace("Bearer ", "").strip()
    elif auth_query:
        jwt_token = auth_query.replace("Bearer ", "").strip()

    if not jwt_token:
        raise HTTPException(status_code=401, detail="Unauthorized")

    try:
        payload = jwt.decode(jwt_token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise HTTPException(status_code=401, detail="Invalid token")
        return email
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")


# ---------------------------------------------------------------------------
# Admin endpoints
# ---------------------------------------------------------------------------
@app.get("/admin/users/export")
async def export_users_csv(secret: Optional[str] = None):
    admin_secret = os.getenv("ADMIN_SECRET", "1234")
    if secret != admin_secret:
        raise HTTPException(status_code=401, detail="Unauthorized")

    users = database.get_all_users()
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=["email", "joined_at"])
    writer.writeheader()
    for u in users:
        writer.writerow(u)

    response = Response(content=output.getvalue())
    response.headers["Content-Disposition"] = "attachment; filename=regula_users.csv"
    response.headers["Content-Type"] = "text/csv"
    return response


# ---------------------------------------------------------------------------
# Auth endpoints
# ---------------------------------------------------------------------------
@app.post("/auth/signup")
async def signup(user: UserAuth):
    email = user.email.lower()

    if not validate_email_domain(email):
        raise HTTPException(
            status_code=400,
            detail="This email address doesn't appear to be valid. Please use a real email.",
        )

    if database.get_user(email):
        raise HTTPException(status_code=400, detail="Account already exists for this email.")

    hashed_pwd = get_password_hash(user.password)
    database.create_user(email, hashed_pwd)

    token = create_access_token(data={"sub": email})
    return {"token": token, "email": email}


@app.post("/auth/login")
async def login(user: UserAuth):
    email = user.email.lower()
    user_data = database.get_user(email)
    if not user_data:
        raise HTTPException(status_code=400, detail="Account not found. Please sign up.")

    if not verify_password(user.password, user_data["password"]):
        raise HTTPException(status_code=400, detail="Incorrect credentials.")

    token = create_access_token(data={"sub": email})
    return {"token": token, "email": email}


# ---------------------------------------------------------------------------
# Core endpoints
# ---------------------------------------------------------------------------
@app.post("/upload")
async def upload_video(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    embed_captions: bool = False,
    user_email: str = Depends(get_current_user),
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
        "user_email": user_email,
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
    user_email: str = Depends(get_current_user),
):
    """
    Stage 2: User confirms (or overrides) the detected language and selects
    an accent. Triggers full transcription in a background thread.
    """
    job_data = JOB_STORE.get(job_id)
    if not job_data:
        raise HTTPException(status_code=404, detail="Job not found")
    if job_data.get("user_email") != user_email:
        raise HTTPException(status_code=403, detail="Access denied")
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

    # Launch Stage 2 in a daemon thread (BackgroundTasks only available in endpoint scope)
    t = threading.Thread(
        target=transcribe_confirmed,
        args=(job_id, body.language, body.accent_id),
        daemon=True,
    )
    t.start()

    return {"status": "transcription_started", "language": body.language, "accent_id": body.accent_id}


@app.get("/status/{job_id}")
async def get_status(job_id: str, user_email: str = Depends(get_current_user)):
    job_data = JOB_STORE.get(job_id)
    if not job_data:
        raise HTTPException(status_code=404, detail="Job not found")

    if job_data.get("user_email") != user_email:
        raise HTTPException(status_code=403, detail="Access denied")

    # Return safe subset (exclude internal file paths)
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
async def download_srt(job_id: str, user_email: str = Depends(get_current_user)):
    job_data = JOB_STORE.get(job_id)
    if not job_data:
        raise HTTPException(status_code=404, detail="Job not found")
    if job_data.get("user_email") != user_email:
        raise HTTPException(status_code=403, detail="Access denied")

    srt_path = os.path.abspath(os.path.join(UPLOAD_DIR, f"{job_id}.srt"))
    if os.path.exists(srt_path):
        return FileResponse(srt_path, filename=f"captions_{job_id[:8]}.srt", media_type="application/x-subrip")
    raise HTTPException(status_code=404, detail="SRT file generation in progress or failed.")


@app.get("/download-video/{job_id}")
async def download_burned_video(job_id: str, user_email: str = Depends(get_current_user)):
    job_data = JOB_STORE.get(job_id)
    if not job_data:
        raise HTTPException(status_code=404, detail="Job not found")
    if job_data.get("user_email") != user_email:
        raise HTTPException(status_code=403, detail="Access denied")

    video_path = os.path.abspath(os.path.join(UPLOAD_DIR, f"{job_id}_burned.mp4"))
    if os.path.exists(video_path):
        original_name = os.path.splitext(job_data.get("filename", "video"))[0]
        return FileResponse(video_path, filename=f"{original_name}_captioned.mp4", media_type="video/mp4")
    raise HTTPException(status_code=404, detail="Processed video not found.")


@app.get("/srt/{job_id}")
async def get_srt_content(job_id: str, user_email: str = Depends(get_current_user)):
    job_data = JOB_STORE.get(job_id)
    if not job_data:
        raise HTTPException(status_code=404, detail="Job not found")
    if job_data.get("user_email") != user_email:
        raise HTTPException(status_code=403, detail="Access denied")

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
    # Dev: dist lives at frontend/dist relative to repo root
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    candidates.append(os.path.join(repo_root, "frontend", "dist"))
    # Also check next to this file (for non-frozen builds that copied dist here)
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
