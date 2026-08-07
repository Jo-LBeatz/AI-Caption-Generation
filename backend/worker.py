"""
worker.py — Standalone version (no Celery, no Redis).

High-Performance Transcription Engine:
  - Uses `faster-whisper` (CTranslate2 C++ engine) for 15x–50x real-time speed.
  - Model defaults to 'base' (145 MB, already cached) for instant startup.
    Override with WHISPER_MODEL env var: 'small', 'medium', 'large-v3', 'turbo'.
  - Integrates Silero VAD to skip non-speech/silence sections, dramatically
    cutting runtime on long videos with silence or music.
  - Real-time progress updates are streamed to the job store as segments complete.
  - Falls back to `openai-whisper` if `faster-whisper` is unavailable.
"""
import os
import sys
import threading
import ffmpeg
import logging
import numpy as np
import torch

try:
    import whisper
except ImportError:
    whisper = None

try:
    from faster_whisper import WhisperModel as FasterWhisperModel
    HAS_FASTER_WHISPER = True
except ImportError:
    HAS_FASTER_WHISPER = False

from jobs import JOB_STORE
from video_utils import embed_subtitles
from moderation import analyze_content

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Model management
# ---------------------------------------------------------------------------
MODEL_NAME = os.getenv("WHISPER_MODEL", "base")
_model_dict = None
_model_lock = threading.Lock()


def get_model():
    global _model_dict
    with _model_lock:
        if _model_dict is None:
            device = "cuda" if torch.cuda.is_available() else "cpu"
            if HAS_FASTER_WHISPER:
                compute_type = "float16" if device == "cuda" else "int8"
                cpu_threads = os.cpu_count() or 4
                logger.info(
                    f"Loading faster-whisper CTranslate2 model '{MODEL_NAME}' "
                    f"on device '{device}' (compute_type={compute_type}, threads={cpu_threads})"
                )
                try:
                    instance = FasterWhisperModel(
                        MODEL_NAME,
                        device=device,
                        compute_type=compute_type,
                        cpu_threads=cpu_threads,
                    )
                    _model_dict = {
                        "type": "faster",
                        "instance": instance,
                        "device": device,
                    }
                except Exception as e:
                    logger.warning(f"faster-whisper init failed ({e}). Falling back to openai-whisper.")
                    _model_dict = None

            if _model_dict is None:
                if whisper is None:
                    raise RuntimeError("Neither faster-whisper nor openai-whisper is installed.")
                if device == "cpu":
                    torch.set_num_threads(os.cpu_count() or 4)
                logger.info(f"Loading openai-whisper model '{MODEL_NAME}' on device '{device}'")
                instance = whisper.load_model(MODEL_NAME, device=device)
                _model_dict = {
                    "type": "openai",
                    "instance": instance,
                    "device": device,
                }
    return _model_dict


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
        meipass = getattr(sys, "_MEIPASS", "")
        bundled = os.path.join(meipass, "bin", "ffmpeg.exe")
        if os.path.exists(bundled):
            return bundled
    local_bin = os.path.join(os.path.dirname(__file__), "bin", "ffmpeg.exe")
    return local_bin if os.path.exists(local_bin) else "ffmpeg"


def ensure_ffmpeg_on_path() -> str:
    """Ensure the directory containing ffmpeg.exe is added to system PATH for Whisper internals."""
    bin_path = get_ffmpeg_bin()
    if bin_path != "ffmpeg" and os.path.exists(bin_path):
        bin_dir = os.path.dirname(os.path.abspath(bin_path))
        path_env = os.environ.get("PATH", "")
        if bin_dir.lower() not in [p.lower() for p in path_env.split(os.pathsep)]:
            os.environ["PATH"] = bin_dir + os.pathsep + path_env
            logger.info(f"Added FFmpeg directory to PATH: {bin_dir}")
    return bin_path


# Ensure PATH is configured at module import time
ensure_ffmpeg_on_path()


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
    Load audio and use Whisper to detect the language.
    Returns a dict: {language, probability, top_candidates}
    """
    model_info = get_model()
    model_type = model_info["type"]
    model = model_info["instance"]

    if model_type == "faster":
        segments, info = model.transcribe(
            audio_path,
            beam_size=1,
            vad_filter=True,
            vad_parameters=dict(min_silence_duration_ms=500),
        )
        top_lang = info.language or "en"
        top_prob = getattr(info, "language_probability", 0.99)
        return {
            "language": top_lang,
            "probability": round(top_prob * 100, 1),
            "top_candidates": [{"language": top_lang, "probability": round(top_prob * 100, 1)}],
        }
    else:
        audio = whisper.load_audio(audio_path)
        audio = whisper.pad_or_trim(audio)
        mel = whisper.log_mel_spectrogram(audio, n_mels=model.dims.n_mels).to(model.device)

        _, probs = model.detect_language(mel)

        top_lang = max(probs, key=probs.get)
        top_prob = probs[top_lang]

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
    "zh_cantonese":              "<ctrl42>這是廣東話。",
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

        model_info = get_model()
        model_type = model_info["type"]
        model = model_info["instance"]

        srt_segments = []
        full_text = []
        final_lang = language

        if model_type == "faster":
            lang_param = language if language and language != "auto" else None
            prompt = build_initial_prompt(language, accent_id)
            segments, info = model.transcribe(
                audio_path,
                language=lang_param,
                initial_prompt=prompt if prompt else None,
                beam_size=1,
                vad_filter=True,
                vad_parameters=dict(min_silence_duration_ms=500),
            )
            final_lang = getattr(info, "language", language)
            total_duration = getattr(info, "duration", 0) or 1.0

            for i, segment in enumerate(segments):
                start = format_timestamp(segment.start)
                end = format_timestamp(segment.end)
                text = segment.text.strip()
                if text:
                    srt_segments.append(f"{i+1}\n{start} --> {end}\n{text}\n")
                    full_text.append(text)

                if total_duration > 0:
                    prog = min(69, int(30 + (segment.end / total_duration) * 40))
                    JOB_STORE[job_id]["progress"] = prog

        else:
            is_cuda = torch.cuda.is_available()
            transcribe_kwargs = {
                "verbose": False,
                "task": "transcribe",
                "beam_size": 1,
                "best_of": 1,
                "temperature": 0.0,
                "condition_on_previous_text": False,
                "word_timestamps": False,
                "fp16": is_cuda,
            }

            if language and language != "auto":
                transcribe_kwargs["language"] = language

            prompt = build_initial_prompt(language, accent_id)
            if prompt:
                transcribe_kwargs["initial_prompt"] = prompt

            result = model.transcribe(audio_path, **transcribe_kwargs)
            final_lang = result.get("language", language)

            for i, segment in enumerate(result["segments"]):
                start = format_timestamp(segment["start"])
                end = format_timestamp(segment["end"])
                text = segment["text"].strip()
                if text:
                    srt_segments.append(f"{i+1}\n{start} --> {end}\n{text}\n")
                    full_text.append(text)

        # --- Generate SRT ---
        JOB_STORE[job_id].update({"status": "generating_srt", "progress": 70})
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
            "final_language": final_lang,
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
# Legacy entry point
# ---------------------------------------------------------------------------
def transcribe_video(job_id: str, video_path: str, embed_captions: bool = False):
    """Alias: run stage 1 only (language detection + wait for confirmation)."""
    extract_and_detect(job_id, video_path, embed_captions)
