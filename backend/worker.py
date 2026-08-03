"""
worker.py — Standalone version (no Celery, no Redis).

The transcription pipeline runs as a plain Python function in a background
thread managed by FastAPI's BackgroundTasks. Job state is tracked via
the shared in-memory JOB_STORE dict in jobs.py.

Two-stage flow:
  Stage 1: Extract audio + detect language  → status: awaiting_user_confirmation
  Stage 2: Called by /confirm-language      → status: transcribing → completed
"""
import os
import sys
import threading
import whisper
import ffmpeg
import logging
import numpy as np

from jobs import JOB_STORE
from video_utils import embed_subtitles
from moderation import analyze_content

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Model management
# ---------------------------------------------------------------------------
MODEL_NAME = os.getenv("WHISPER_MODEL", "large-v3")
_model = None
_model_lock = threading.Lock()


def get_model():
    global _model
    with _model_lock:
        if _model is None:
            logger.info(f"Loading Whisper model: {MODEL_NAME}")
            _model = whisper.load_model(MODEL_NAME)
    return _model


# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------
def get_ffmpeg_bin() -> str:
    """
    Return the path to the bundled ffmpeg executable.
    In a PyInstaller bundle, binaries land in sys._MEIPASS/bin/.
    In development, look for backend/bin/ffmpeg.exe (or rely on system PATH).
    """
    if getattr(sys, "frozen", False):
        return os.path.join(sys._MEIPASS, "bin", "ffmpeg.exe")
    local_bin = os.path.join(os.path.dirname(__file__), "bin", "ffmpeg.exe")
    return local_bin if os.path.exists(local_bin) else "ffmpeg"


def get_upload_dir() -> str:
    """Return the correct uploads directory in both dev and frozen modes."""
    if getattr(sys, "frozen", False):
        base = os.path.dirname(sys.executable)
        uploads = os.path.join(base, "uploads")
    else:
        base = os.path.join(os.path.dirname(__file__), "..", "uploads")
        uploads = os.path.abspath(base)
    os.makedirs(uploads, exist_ok=True)
    return uploads


# ---------------------------------------------------------------------------
# Timestamp formatting
# ---------------------------------------------------------------------------
def format_timestamp(seconds: float) -> str:
    td = float(seconds)
    hours = int(td // 3600)
    minutes = int((td % 3600) // 60)
    secs = int(td % 60)
    milliseconds = int(round((td - (hours * 3600 + minutes * 60 + secs)) * 1000))
    if milliseconds == 1000:
        secs += 1
        milliseconds = 0
    return f"{hours:02}:{minutes:02}:{secs:02},{milliseconds:03}"


# ---------------------------------------------------------------------------
# Language detection
# ---------------------------------------------------------------------------
def detect_language_from_audio(audio_path: str) -> dict:
    """
    Load the first 30 seconds of audio and use Whisper to detect the language.
    Returns a dict: {language, probability, top_languages}
    """
    model = get_model()
    # Load and pad/trim to 30 seconds (whisper expects mel spectrogram)
    audio = whisper.load_audio(audio_path)
    audio = whisper.pad_or_trim(audio)
    mel = whisper.log_mel_spectrogram(audio).to(model.device)

    # Detect language
    _, probs = model.detect_language(mel)

    # Top language by probability
    top_lang = max(probs, key=probs.get)
    top_prob = probs[top_lang]

    # Top 5 candidates for the UI
    sorted_langs = sorted(probs.items(), key=lambda x: x[1], reverse=True)[:5]
    top_candidates = [{"language": lang, "probability": round(prob * 100, 1)} for lang, prob in sorted_langs]

    return {
        "language": top_lang,
        "probability": round(top_prob * 100, 1),
        "top_candidates": top_candidates,
    }


# ---------------------------------------------------------------------------
# Accent hint builder
# ---------------------------------------------------------------------------
# Maps accent IDs to descriptive initial prompt text that biases Whisper's
# decoder vocabulary toward the selected dialect without retraining.
ACCENT_PROMPTS = {
    # English
    "en_american":    "This is American English. The speaker uses American pronunciation and vocabulary.",
    "en_british":     "This is British English. The speaker uses British pronunciation, vocabulary and spelling.",
    "en_australian":  "This is Australian English. The speaker uses Australian pronunciation.",
    "en_indian":      "This is Indian English. The speaker uses Indian English pronunciation and intonation.",
    "en_irish":       "This is Irish English. The speaker uses Irish accent and pronunciation.",
    "en_scottish":    "This is Scottish English. The speaker uses a Scottish accent.",
    "en_south_african": "This is South African English. The speaker uses a South African accent.",
    "en_canadian":    "This is Canadian English. The speaker uses Canadian pronunciation.",
    "en_caribbean":   "This is Caribbean English. The speaker uses Caribbean dialect.",
    # Spanish
    "es_castilian":   "Este es español de España, castellano estándar.",
    "es_mexican":     "Este es español mexicano.",
    "es_argentinian": "Este es español argentino con acento rioplatense.",
    "es_colombian":   "Este es español colombiano.",
    "es_chilean":     "Este es español chileno.",
    # French
    "fr_standard":    "C'est le français standard de France.",
    "fr_canadian":    "C'est le français canadien, québécois.",
    "fr_belgian":     "C'est le français de Belgique.",
    "fr_swiss":       "C'est le français de Suisse.",
    # Arabic
    "ar_msa":         "This is Modern Standard Arabic (Fusha).",
    "ar_egyptian":    "This is Egyptian Arabic dialect.",
    "ar_levantine":   "This is Levantine Arabic dialect.",
    "ar_gulf":        "This is Gulf Arabic dialect.",
    "ar_moroccan":    "This is Moroccan Darija dialect.",
    # Portuguese
    "pt_brazilian":   "Este é português brasileiro.",
    "pt_european":    "Este é português europeu de Portugal.",
    # Chinese
    "zh_mandarin_simplified":    "普通话，简体中文。",
    "zh_mandarin_traditional":   "普通話，繁體中文。",
    "zh_cantonese":              "這是廣東話。",
    # German
    "de_standard":    "Dies ist Hochdeutsch, Standarddeutsch.",
    "de_austrian":    "Dies ist österreichisches Deutsch.",
    "de_swiss":       "Dies ist Schweizerdeutsch.",
    # Hindi
    "hi_standard":    "यह मानक हिन्दी है।",
    "hi_code_switch":  "This speaker uses Hindi mixed with English, Hinglish.",
    # Default (no accent hint)
    "none": "",
}


def build_initial_prompt(language: str, accent_id: str) -> str:
    """Return the accent-biased initial prompt for Whisper transcription."""
    return ACCENT_PROMPTS.get(accent_id, "")


# ---------------------------------------------------------------------------
# Stage 1: Extract audio + detect language
# ---------------------------------------------------------------------------
def extract_and_detect(job_id: str, video_path: str, embed_captions: bool):
    """
    Stage 1: Extract audio from video, run language detection,
    then pause with status='awaiting_user_confirmation'.
    The confirmed language/accent will be applied in stage 2.
    """
    try:
        # --- Extract Audio ---
        JOB_STORE[job_id].update({"status": "extracting_audio", "progress": 5})
        logger.info(f"Job {job_id}: Extracting audio from {video_path}")

        audio_path = f"{video_path}.wav"
        ffmpeg_bin = get_ffmpeg_bin()
        try:
            ffmpeg.input(video_path).output(
                audio_path, acodec="pcm_s16le", ac=1, ar="16k"
            ).run(cmd=ffmpeg_bin, overwrite_output=True, quiet=True)
        except Exception as e:
            logger.error(f"FFmpeg error: {e}")
            JOB_STORE[job_id].update({"status": "failed", "error": f"FFmpeg error: {str(e)}"})
            return

        # --- Detect Language ---
        JOB_STORE[job_id].update({"status": "detecting_language", "progress": 15})
        logger.info(f"Job {job_id}: Detecting language")

        try:
            lang_result = detect_language_from_audio(audio_path)
        except Exception as e:
            logger.warning(f"Job {job_id}: Language detection failed: {e}. Defaulting to auto.")
            lang_result = {"language": "auto", "probability": 0.0, "top_candidates": []}

        # Store audio_path and embed_captions in job store for stage 2
        JOB_STORE[job_id].update({
            "status": "awaiting_user_confirmation",
            "progress": 20,
            "audio_path": audio_path,
            "video_path": video_path,
            "embed_captions": embed_captions,
            "detected_language": lang_result["language"],
            "detected_probability": lang_result["probability"],
            "detected_top_candidates": lang_result["top_candidates"],
        })
        logger.info(
            f"Job {job_id}: Detected language={lang_result['language']} "
            f"({lang_result['probability']}%). Awaiting user confirmation."
        )

    except Exception as e:
        logger.error(f"Stage-1 error on job {job_id}: {e}")
        JOB_STORE[job_id].update({"status": "failed", "error": str(e)})


# ---------------------------------------------------------------------------
# Stage 2: Transcribe with confirmed language + accent
# ---------------------------------------------------------------------------
def transcribe_confirmed(job_id: str, language: str, accent_id: str):
    """
    Stage 2: Perform full transcription using the user-confirmed language
    and accent hint. Called from the /confirm-language endpoint.
    """
    job = JOB_STORE.get(job_id)
    if not job:
        logger.error(f"Job {job_id} not found for transcription.")
        return

    audio_path = job.get("audio_path")
    video_path = job.get("video_path")
    embed_captions = job.get("embed_captions", False)

    if not audio_path or not video_path:
        JOB_STORE[job_id].update({"status": "failed", "error": "Audio/video paths missing from job store."})
        return

    try:
        # --- Transcribe with Whisper ---
        JOB_STORE[job_id].update({"status": "transcribing", "progress": 30})
        logger.info(f"Job {job_id}: Transcribing (language={language}, accent={accent_id})")

        model = get_model()

        # Build transcription kwargs
        transcribe_kwargs = {
            "verbose": False,
            "task": "transcribe",
            "beam_size": 5,
            "best_of": 5,
            "temperature": 0,
            "condition_on_previous_text": True,
            "word_timestamps": False,
            "fp16": False,  # CPU-safe default; GPU will auto-use fp16 if available
        }

        # Apply language selection
        if language and language != "auto":
            transcribe_kwargs["language"] = language

        # Apply accent initial prompt
        initial_prompt = build_initial_prompt(language, accent_id)
        if initial_prompt:
            transcribe_kwargs["initial_prompt"] = initial_prompt

        result = model.transcribe(audio_path, **transcribe_kwargs)

        # --- Generate SRT ---
        JOB_STORE[job_id].update({"status": "generating_srt", "progress": 70})
        srt_segments = []
        full_text = []
        for i, segment in enumerate(result["segments"]):
            start = format_timestamp(segment["start"])
            end = format_timestamp(segment["end"])
            text = segment["text"].strip()
            if text:  # Skip empty segments
                srt_segments.append(f"{i+1}\n{start} --> {end}\n{text}\n")
                full_text.append(text)

        srt_content = "\n".join(srt_segments)
        upload_dir = get_upload_dir()
        srt_path = os.path.abspath(os.path.join(upload_dir, f"{job_id}.srt"))

        # --- Moderation pass ---
        JOB_STORE[job_id].update({"status": "checking_content", "progress": 75})
        is_allowed, message = analyze_content(" ".join(full_text))
        if not is_allowed:
            logger.warning(f"Job {job_id}: Content rejected. Reason: {message}")
            for p in [audio_path, video_path]:
                if os.path.exists(p):
                    os.remove(p)
            JOB_STORE[job_id].update({"status": "failed", "error": f"Content policy: {message}"})
            return

        # --- Save SRT ---
        with open(srt_path, "w", encoding="utf-8") as f:
            f.write(srt_content)

        # --- Burn subtitles (optional) ---
        burning_successful = False
        burned_video_path = None

        if embed_captions:
            JOB_STORE[job_id].update({"status": "embedding_captions", "progress": 85})
            logger.info(f"Job {job_id}: Starting subtitle burn-in")
            burned_video_path = os.path.abspath(
                os.path.join(upload_dir, f"{job_id}_burned.mp4")
            )
            if embed_subtitles(video_path, srt_path, burned_video_path):
                burning_successful = True
                logger.info(f"Job {job_id}: Burn-in successful → {burned_video_path}")
            else:
                logger.error(f"Job {job_id}: Burn-in failed")

        JOB_STORE[job_id].update({
            "status": "completed",
            "progress": 100,
            "video_burned": burning_successful,
            "burned_video_filename": os.path.basename(burned_video_path) if burning_successful else None,
            "final_language": result.get("language", language),
        })
        logger.info(f"Job {job_id}: Completed. SRT saved at {srt_path}")

        # Cleanup temporary audio
        if os.path.exists(audio_path):
            os.remove(audio_path)
        if not embed_captions or burning_successful:
            if os.path.exists(video_path):
                os.remove(video_path)

    except Exception as e:
        logger.error(f"Stage-2 error on job {job_id}: {e}")
        JOB_STORE[job_id].update({"status": "failed", "error": str(e)})
        # Cleanup on error
        for p in [audio_path]:
            if p and os.path.exists(p):
                os.remove(p)


# ---------------------------------------------------------------------------
# Legacy entry point (kept for backward compatibility if needed)
# ---------------------------------------------------------------------------
def transcribe_video(job_id: str, video_path: str, embed_captions: bool = False):
    """Alias: run stage 1 only (language detection + wait for confirmation)."""
    extract_and_detect(job_id, video_path, embed_captions)
