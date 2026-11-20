"""
worker.py — High-Performance Transcription & Theological Morality Engine for Verbum.

Features:
  - Uses `faster-whisper` (CTranslate2 C++ engine) with 'large-v3-turbo' by default
    for maximum multilingual precision and speed, with automatic graceful fallback to 'small' / 'base'.
  - Anti-hallucination parameters (condition_on_previous_text=False, hallucination_silence_threshold,
    no_speech_threshold, compression_ratio_threshold, Silero VAD) to eliminate ghost captions.
  - Accurate, real-time estimated time to completion (ETA in seconds) based on actual video duration
    and live measured speech processing rates.
  - Full theological morality check based on the Ten Commandments of Moses (bpr1_catholic_prayer_book.pdf pp. 98-100)
    and the Two Commandments of Christ (The Two Commandments of Christ.pdf).
  - Both .SRT subtitles and burned-in .MP4 video produced simultaneously when burning is selected.
"""

import os
import sys
import time
import threading
import subprocess
import ffmpeg
import logging
import re
from typing import Optional, Dict, Any, List
import numpy as np
try:
    import torch
except ImportError:
    torch = None

def sanitize_caption_text(text: str) -> str:
    """
    Post-process transcribed text to ensure strict capitalization rules:
      - 'God', 'God's', 'Gods' must start with capital 'G'
      - 'satan', 'satan's', 'satanic' must start with lowercase 's'
    """
    if not text:
        return ""
    # Capitalize God / God's / Gods / Lord
    text = re.sub(r"\bgod\b", "God", text, flags=re.IGNORECASE)
    text = re.sub(r"\bgod's\b", "God's", text, flags=re.IGNORECASE)
    text = re.sub(r"\bgods\b", "Gods", text, flags=re.IGNORECASE)
    text = re.sub(r"\blord\b", "Lord", text, flags=re.IGNORECASE)

    # Lowercase satan / satan's / satanic
    text = re.sub(r"\bsatan\b", "satan", text, flags=re.IGNORECASE)
    text = re.sub(r"\bsatan's\b", "satan's", text, flags=re.IGNORECASE)
    text = re.sub(r"\bsatanic\b", "satanic", text, flags=re.IGNORECASE)
    return text

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
from video_utils import embed_subtitles, get_video_duration
from morality import evaluate_video_morality, extract_ultimate_video_message

if sys.platform == "win32":
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        if hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Model management
# ---------------------------------------------------------------------------
MODEL_NAME = os.getenv("WHISPER_MODEL", "large-v3-turbo")
_model_dict = None
_model_lock = threading.Lock()


def is_cuda_available() -> bool:
    """Check if CUDA GPU acceleration is available via CTranslate2 or PyTorch."""
    try:
        import ctranslate2
        if ctranslate2.get_cuda_device_count() > 0:
            return True
    except Exception:
        pass
    if torch and hasattr(torch, "cuda") and torch.cuda.is_available():
        return True
    return False


def get_model():
    global _model_dict
    with _model_lock:
        if _model_dict is None:
            cuda_ok = is_cuda_available()
            preferred_device = "cuda" if cuda_ok else "cpu"
            if HAS_FASTER_WHISPER:
                cpu_threads = os.cpu_count() or 4
                
                # Priority list of models to try
                candidate_models = [MODEL_NAME]
                if MODEL_NAME != "small":
                    candidate_models.append("small")
                if MODEL_NAME != "base":
                    candidate_models.append("base")

                for candidate in candidate_models:
                    # Try CUDA first if available, then fallback to CPU
                    device_attempts = [preferred_device]
                    if preferred_device == "cuda":
                        device_attempts.append("cpu")

                    loaded = False
                    for dev in device_attempts:
                        compute_type = "float16" if dev == "cuda" else "int8"
                        try:
                            logger.info(
                                f"Loading faster-whisper CTranslate2 model '{candidate}' "
                                f"on device '{dev}' (compute_type={compute_type}, threads={cpu_threads})"
                            )
                            instance = FasterWhisperModel(
                                candidate,
                                device=dev,
                                compute_type=compute_type,
                                cpu_threads=cpu_threads,
                                num_workers=2,
                            )
                            _model_dict = {
                                "type": "faster",
                                "instance": instance,
                                "device": dev,
                                "model_name": candidate,
                            }
                            logger.info(f"Successfully initialized faster-whisper with '{candidate}' on {dev.upper()}")
                            loaded = True
                            break
                        except Exception as e:
                            logger.warning(f"Could not load faster-whisper model '{candidate}' on '{dev}': {e}")
                    if loaded:
                        break

            if _model_dict is None and whisper is not None:
                device = "cuda" if (torch and torch.cuda.is_available()) else "cpu"
                if device == "cpu" and torch:
                    torch.set_num_threads(os.cpu_count() or 4)
                logger.info(f"Loading openai-whisper model '{MODEL_NAME}' on device '{device}'")
                try:
                    instance = whisper.load_model(MODEL_NAME, device=device)
                    _model_dict = {
                        "type": "openai",
                        "instance": instance,
                        "device": device,
                        "model_name": MODEL_NAME,
                    }
                except Exception as e:
                    logger.warning(f"Could not load openai-whisper model: {e}")

            if _model_dict is None:
                groq_key = os.getenv("GROQ_API_KEY")
                openai_key = os.getenv("OPENAI_API_KEY")
                if groq_key or openai_key:
                    _model_dict = {
                        "type": "cloud",
                        "provider": "groq" if groq_key else "openai",
                        "device": "cloud",
                        "model_name": "whisper-large-v3-turbo" if groq_key else "whisper-1",
                    }
                    logger.info(f"Initialized cloud transcription via {_model_dict['provider'].upper()} Whisper API")
                else:
                    raise RuntimeError(
                        "No local Whisper engine (faster-whisper/openai-whisper) found. "
                        "For cloud deployment on Vercel, set GROQ_API_KEY or OPENAI_API_KEY in your Vercel project environment variables. "
                        "For offline on-device processing, run the Verbum desktop application."
                    )
    return _model_dict


# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------
def get_ffmpeg_bin() -> str:
    """Return the path to the bundled ffmpeg executable."""
    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", "")
        bundled = os.path.join(meipass, "bin", "ffmpeg.exe")
        if os.path.exists(bundled):
            return bundled
    local_bin = os.path.join(os.path.dirname(__file__), "bin", "ffmpeg.exe")
    return local_bin if os.path.exists(local_bin) else "ffmpeg"


def ensure_ffmpeg_on_path() -> str:
    bin_path = get_ffmpeg_bin()
    if os.path.exists(bin_path):
        bin_dir = os.path.dirname(os.path.abspath(bin_path))
        if bin_dir not in os.environ.get("PATH", ""):
            os.environ["PATH"] = bin_dir + os.pathsep + os.environ.get("PATH", "")
            logger.info(f"Injected {bin_dir} into PATH")
    return bin_path


def get_upload_dir() -> str:
    upload_dir = os.getenv("UPLOAD_DIR")
    if not upload_dir:
        upload_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "uploads"))
    os.makedirs(upload_dir, exist_ok=True)
    return upload_dir


# ---------------------------------------------------------------------------
# Timestamp formatting
# ---------------------------------------------------------------------------
def format_timestamp(seconds: float) -> str:
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    milliseconds = int(round((seconds - int(seconds)) * 1000))
    if milliseconds >= 1000:
        secs += 1
        milliseconds = 0
    return f"{hours:02}:{minutes:02}:{secs:02},{milliseconds:03}"


# ---------------------------------------------------------------------------
# Language detection
# ---------------------------------------------------------------------------
def detect_language_from_audio(audio_path: str) -> dict:
    """Load audio and use Whisper to detect language from first 30 seconds."""
    model_info = get_model()
    model_type = model_info["type"]
    model = model_info["instance"]

    sample_audio = f"{audio_path}_sample.wav"
    target_audio = audio_path
    ffmpeg_bin = get_ffmpeg_bin()
    try:
        ffmpeg.input(audio_path).output(sample_audio, t=30, acodec="copy").run(cmd=ffmpeg_bin, overwrite_output=True, quiet=True)
        if os.path.exists(sample_audio):
            target_audio = sample_audio
    except Exception as e:
        logger.warning(f"Could not extract 30s sample for language detection ({e}), using full audio.")

    try:
        if model_type == "cloud":
            return {
                "language": "en",
                "probability": 95.0,
                "top_candidates": [{"language": "en", "probability": 95.0}],
            }
        elif model_type == "faster":
            segments, info = model.transcribe(
                target_audio,
                beam_size=5,
                vad_filter=True,
                vad_parameters=dict(min_silence_duration_ms=600, speech_pad_ms=300),
            )
            top_lang = info.language or "en"
            top_prob = getattr(info, "language_probability", 0.99)
            return {
                "language": top_lang,
                "probability": round(top_prob * 100, 1),
                "top_candidates": [{"language": top_lang, "probability": round(top_prob * 100, 1)}],
            }
        else:
            audio = whisper.load_audio(target_audio)
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
    finally:
        if os.path.exists(sample_audio):
            try:
                os.remove(sample_audio)
            except Exception:
                pass


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
    Stage 1: Extract audio from video, measure total duration, run language detection,
    then pause with status='awaiting_user_confirmation'.
    """
    try:
        # Measure duration
        total_duration = get_video_duration(video_path)
        JOB_STORE[job_id]["duration"] = total_duration

        # Initial ETA for extraction
        JOB_STORE[job_id].update({
            "status": "extracting_audio",
            "progress": 5,
            "eta_seconds": max(3, int(total_duration * 0.05)),
        })
        logger.info(f"Job {job_id}: Extracting audio from {video_path} (Duration: {total_duration:.1f}s)")

        audio_path = f"{video_path}.wav"
        ffmpeg_bin = get_ffmpeg_bin()
        try:
            # Bulletproof audio extraction via direct subprocess
            extract_cmd = [
                ffmpeg_bin, "-y",
                "-i", video_path,
                "-vn",
                "-acodec", "pcm_s16le",
                "-ac", "1",
                "-ar", "16000",
                audio_path,
            ]
            res = subprocess.run(
                extract_cmd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            if res.returncode != 0 or not os.path.exists(audio_path) or os.path.getsize(audio_path) == 0:
                err_text = res.stderr or ""
                if "does not contain any stream" in err_text or "Output file #0" in err_text or "Stream map" in err_text:
                    raise RuntimeError("The uploaded video does not contain an audio track (it is silent). Please upload a video with speech or audio.")
                lines = [l.strip() for l in err_text.strip().splitlines() if l.strip() and not l.startswith("built with") and not l.startswith("configuration:") and not l.startswith("ffmpeg version") and not l.startswith("lib")]
                last_err = " ".join(lines[-2:]) if lines else "Invalid video file or corrupt stream."
                raise RuntimeError(f"Could not extract audio track: {last_err}")
        except Exception as e:
            err_msg = str(e) or "Failed to extract audio from video."
            logger.error(f"Audio extraction error: {err_msg}")
            JOB_STORE[job_id].update({"status": "failed", "error": err_msg})
            return

        # --- Detect Language ---
        JOB_STORE[job_id].update({"status": "detecting_language", "progress": 15, "eta_seconds": 3})
        logger.info(f"Job {job_id}: Detecting language")

        try:
            lang_result = detect_language_from_audio(audio_path)
        except Exception as e:
            logger.warning(f"Job {job_id}: Language detection failed: {e}. Defaulting to auto.")
            lang_result = {"language": "auto", "probability": 0.0, "top_candidates": []}

        # Store parameters in job store for stage 2
        JOB_STORE[job_id].update({
            "status": "awaiting_user_confirmation",
            "progress": 20,
            "eta_seconds": 0,
            "audio_path": audio_path,
            "video_path": video_path,
            "duration": total_duration,
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
# SRT Cue Formatting (Anti-Hallucination & Clean Wrapping)
# ---------------------------------------------------------------------------
HALLUCINATION_BLACKLIST = [
    "subtitles by", "amara.org", "thank you for watching", "thanks for watching",
    "please subscribe", "subscribe to my channel", "like and subscribe",
    "all rights reserved", "[applause]", "[music]", "[laughter]"
]

def format_srt_cues(raw_segments, max_lines: int = 2, max_chars_per_line: int = 40, uppercase: bool = False):
    """
    Format raw transcript segments into clean, accurate SRT blocks.
    Removes hallucination loops and YouTube noise artifacts.
    Supports optional uppercase subtitle transformation.
    """
    word_items = []
    
    for seg in raw_segments:
        seg_text = getattr(seg, "text", "") if not isinstance(seg, dict) else seg.get("text", "")
        clean_text_check = seg_text.strip().lower()
        
        # Suppress common hallucinated filler
        if any(h in clean_text_check for h in HALLUCINATION_BLACKLIST):
            continue

        words = getattr(seg, "words", None) if not isinstance(seg, dict) else seg.get("words", None)
        seg_start = getattr(seg, "start", 0.0) if not isinstance(seg, dict) else seg.get("start", 0.0)
        seg_end = getattr(seg, "end", 0.0) if not isinstance(seg, dict) else seg.get("end", 0.0)
        
        if words and len(words) > 0:
            for w in words:
                w_start = getattr(w, "start", seg_start) if not isinstance(w, dict) else w.get("start", seg_start)
                w_end = getattr(w, "end", seg_end) if not isinstance(w, dict) else w.get("end", seg_end)
                w_word = getattr(w, "word", "") if not isinstance(w, dict) else w.get("word", "")
                w_word = sanitize_caption_text(w_word.strip())
                if w_word:
                    word_items.append({"word": w_word, "start": w_start, "end": w_end})
        else:
            clean_text = sanitize_caption_text(seg_text.strip())
            if not clean_text:
                continue
            words_in_text = clean_text.split()
            if not words_in_text:
                continue
            total_chars = max(1, sum(len(w) for w in words_in_text))
            seg_duration = max(0.1, seg_end - seg_start)
            
            curr_t = seg_start
            for w_word in words_in_text:
                w_dur = seg_duration * (len(w_word) / total_chars)
                word_items.append({
                    "word": sanitize_caption_text(w_word),
                    "start": curr_t,
                    "end": curr_t + w_dur
                })
                curr_t += w_dur

    if not word_items:
        return [], []

    lines = []
    current_line_words = []
    current_line_len = 0

    for item in word_items:
        w_text = item["word"]
        needed_len = len(w_text) if not current_line_words else len(w_text) + 1
        
        if current_line_words and (current_line_len + needed_len > max_chars_per_line):
            line_start = current_line_words[0]["start"]
            line_end = current_line_words[-1]["end"]
            line_text = " ".join(w["word"] for w in current_line_words)
            lines.append({"text": line_text, "start": line_start, "end": line_end})
            
            current_line_words = [item]
            current_line_len = len(w_text)
        else:
            current_line_words.append(item)
            current_line_len += needed_len

    if current_line_words:
        line_start = current_line_words[0]["start"]
        line_end = current_line_words[-1]["end"]
        line_text = " ".join(w["word"] for w in current_line_words)
        lines.append({"text": line_text, "start": line_start, "end": line_end})

    srt_blocks = []
    full_text_list = []
    cue_index = 1
    last_cue_text = ""
    repeat_count = 0

    i = 0
    while i < len(lines):
        cue_lines = lines[i:i+max_lines]
        cue_start = format_timestamp(cue_lines[0]["start"])
        cue_end = format_timestamp(cue_lines[-1]["end"])
        cue_text = "\n".join(l["text"] for l in cue_lines)
        if uppercase:
            cue_text = cue_text.upper()
        
        # Deduplicate consecutive hallucination loops
        if cue_text.lower() == last_cue_text.lower():
            repeat_count += 1
            if repeat_count > 1:
                i += len(cue_lines)
                continue
        else:
            repeat_count = 0
            last_cue_text = cue_text

        srt_blocks.append(f"{cue_index}\n{cue_start} --> {cue_end}\n{cue_text}\n")
        full_text_list.append(" ".join(l["text"] for l in cue_lines))
        
        cue_index += 1
        i += len(cue_lines)

    return srt_blocks, full_text_list


def transcribe_via_cloud_api(
    audio_path: str,
    language: Optional[str] = None,
    accent_id: str = "none",
    provider: str = "groq",
):
    """
    Transcribes audio using a high-speed cloud Whisper API (Groq or OpenAI).
    Used when running in serverless environments like Vercel where local PyTorch is not bundled.
    """
    import httpx
    prompt = build_initial_prompt(language or "en", accent_id)
    if provider == "groq":
        api_key = os.getenv("GROQ_API_KEY")
        url = "https://api.groq.com/openai/v1/audio/transcriptions"
        model = "whisper-large-v3-turbo"
    else:
        api_key = os.getenv("OPENAI_API_KEY")
        url = "https://api.openai.com/v1/audio/transcriptions"
        model = "whisper-1"

    if not api_key:
        raise RuntimeError(
            f"{provider.upper()}_API_KEY environment variable is not set. "
            f"Please set GROQ_API_KEY or OPENAI_API_KEY in your Vercel Project Environment Variables."
        )

    headers = {"Authorization": f"Bearer {api_key}"}
    with open(audio_path, "rb") as f:
        files = {"file": (os.path.basename(audio_path), f, "audio/wav")}
        data = {
            "model": model,
            "response_format": "verbose_json",
        }
        if language and language != "auto":
            data["language"] = language
        if prompt:
            data["prompt"] = prompt

        with httpx.Client(timeout=120.0) as client:
            resp = client.post(url, headers=headers, files=files, data=data)
            if resp.status_code != 200:
                raise RuntimeError(f"Cloud transcription error ({resp.status_code}): {resp.text}")
            result = resp.json()

    final_lang = result.get("language", language or "en")
    raw_segments = result.get("segments", [])
    return raw_segments, final_lang


# ---------------------------------------------------------------------------
# Stage 2: Transcribe with confirmed language + accent
# ---------------------------------------------------------------------------
def transcribe_confirmed(job_id: str, language: str, accent_id: str):
    """
    Stage 2: Transcribes the audio with anti-hallucination settings,
    computes real-time countdown ETA, runs moral law check,
    and produces both .SRT and burned-in .MP4.
    """
    job_data = JOB_STORE.get(job_id)
    if not job_data:
        logger.error(f"transcribe_confirmed: job {job_id} not found in store")
        return

    audio_path = job_data.get("audio_path")
    video_path = job_data.get("video_path")
    embed_captions = job_data.get("embed_captions", False)
    total_duration = job_data.get("duration", 0.0)

    if not total_duration or total_duration <= 0:
        total_duration = get_video_duration(video_path) if video_path else 1.0
        JOB_STORE[job_id]["duration"] = total_duration

    stage2_start = time.time()
    # Initial ETA calculation
    est_transcribe_secs = max(5, int(total_duration / 2.0))
    est_burn_secs = int(total_duration * 0.25) if embed_captions else 0
    initial_eta = est_transcribe_secs + est_burn_secs

    JOB_STORE[job_id].update({
        "status": "transcribing",
        "progress": 25,
        "eta_seconds": max(5, initial_eta),
    })

    try:
        model_info = get_model()
        model_type = model_info["type"]
        model = model_info["instance"]

        raw_segments_list = []
        final_lang = language

        if model_type == "cloud":
            provider = model_info.get("provider", "groq")
            JOB_STORE[job_id].update({"progress": 45, "eta_seconds": 5})
            raw_segments_list, final_lang = transcribe_via_cloud_api(
                audio_path, language=language, accent_id=accent_id, provider=provider
            )
            JOB_STORE[job_id].update({"progress": 72, "eta_seconds": 2})
        elif model_type == "faster":
            lang_param = language if language and language != "auto" else None
            prompt = build_initial_prompt(language, accent_id)

            # High-accuracy, anti-hallucination transcription configuration
            segments, info = model.transcribe(
                audio_path,
                language=lang_param,
                initial_prompt=prompt if prompt else None,
                beam_size=5,
                patience=1.0,
                temperature=0.0,
                condition_on_previous_text=False,          # STOPS repetitive hallucination loops!
                hallucination_silence_threshold=2.0,       # STOPS hallucinating over silence!
                no_speech_threshold=0.6,                   # Discards non-speech audio segments!
                compression_ratio_threshold=2.4,           # Rejects degenerate repetitive loops!
                suppress_blank=True,
                word_timestamps=True,
                vad_filter=True,
                vad_parameters=dict(
                    threshold=0.5,
                    min_silence_duration_ms=500,
                    speech_pad_ms=250,
                ),
            )
            final_lang = getattr(info, "language", language)
            audio_dur = getattr(info, "duration", total_duration) or total_duration

            for segment in segments:
                raw_segments_list.append(segment)
                elapsed = max(0.2, time.time() - stage2_start)
                if segment.end > 0.5:
                    speed = segment.end / elapsed
                    rem_audio = max(0.0, audio_dur - segment.end)
                    eta_transcribe = rem_audio / max(speed, 0.2)
                    burn_est = (audio_dur * 0.22) if embed_captions else 0
                    total_eta = max(1, int(eta_transcribe + burn_est + 1))
                    prog = min(72, int(25 + (segment.end / max(audio_dur, 1.0)) * 47))
                    JOB_STORE[job_id].update({
                        "progress": prog,
                        "eta_seconds": total_eta,
                    })

        else:
            is_cuda = bool(torch and torch.cuda.is_available())
            transcribe_kwargs = {
                "verbose": False,
                "task": "transcribe",
                "beam_size": 5,
                "best_of": 5,
                "temperature": 0.0,
                "condition_on_previous_text": False,
                "word_timestamps": True,
                "fp16": is_cuda,
            }
            if language and language != "auto":
                transcribe_kwargs["language"] = language

            prompt = build_initial_prompt(language, accent_id)
            if prompt:
                transcribe_kwargs["initial_prompt"] = prompt

            result = model.transcribe(audio_path, **transcribe_kwargs)
            final_lang = result.get("language", language)
            raw_segments_list = result.get("segments", [])

        # --- Format SRT Cues (Enforce 2 Lines Max per Cue & Style Case) ---
        caption_style = job_data.get("caption_style") or {}
        is_uppercase = bool(caption_style.get("uppercase", False))
        srt_segments, full_text = format_srt_cues(
            raw_segments_list, max_lines=2, max_chars_per_line=40, uppercase=is_uppercase
        )
        if not srt_segments:
            logger.info(f"Job {job_id}: No distinct speech words parsed, generating fallback cue.")
            srt_segments = ["1\n00:00:00,000 --> 00:00:05,000\n[No spoken speech detected]\n"]
            full_text = ["[No spoken speech detected]"]

        # --- Save SRT File ---
        JOB_STORE[job_id].update({"status": "generating_srt", "progress": 73, "eta_seconds": 3})
        srt_content = "\n".join(srt_segments)
        upload_dir = get_upload_dir()
        srt_path = os.path.abspath(os.path.join(upload_dir, f"{job_id}.srt"))
        with open(srt_path, "w", encoding="utf-8") as f:
            f.write(srt_content)
        JOB_STORE[job_id]["has_srt"] = True
        JOB_STORE[job_id]["final_language"] = final_lang

        # --- Extract Ultimate Video Message & Motto ---
        full_transcript = " ".join(full_text)
        try:
            ultimate_msg = extract_ultimate_video_message(full_transcript)
            JOB_STORE[job_id]["ultimate_message"] = ultimate_msg
            logger.info(f"Job {job_id}: Extracted ultimate message: {ultimate_msg.get('motto')}")
        except Exception as e:
            logger.warning(f"Could not extract ultimate message for job {job_id}: {e}")

        # --- Moral Law Check (Moses' 10 Commandments & Christ's 2 Commandments) ---
        JOB_STORE[job_id].update({"status": "checking_morality", "progress": 74, "eta_seconds": 2})
        morality_result = evaluate_video_morality(full_transcript)

        if morality_result.get("is_evil"):
            logger.warning(f"Job {job_id}: Morality evaluation flagged evil message: {morality_result}")
            # Sound alert on host machine
            if sys.platform == "win32":
                try:
                    import winsound
                    winsound.Beep(1200, 350)
                    winsound.Beep(900, 350)
                    winsound.Beep(1300, 450)
                except Exception:
                    pass

            JOB_STORE[job_id].update({
                "status": "morality_warning",
                "morality_alert": morality_result,
                "progress": 75,
                "eta_seconds": 0,
            })
            # Pause pipeline here and await user decision (Proceed or Cancel)
            return

        # Content is clean -> proceed immediately to completion / burning
        finalize_transcription(job_id)

    except Exception as e:
        logger.error(f"Stage-2 error on job {job_id}: {e}")
        JOB_STORE[job_id].update({"status": "failed", "error": str(e)})


def finalize_transcription(job_id: str):
    """Completes subtitle burning (if requested) and marks job as completed."""
    job_data = JOB_STORE.get(job_id)
    if not job_data:
        return

    video_path = job_data.get("video_path")
    audio_path = job_data.get("audio_path")
    embed_captions = job_data.get("embed_captions", False)
    upload_dir = get_upload_dir()
    srt_path = os.path.abspath(os.path.join(upload_dir, f"{job_id}.srt"))

    burning_successful = False
    burned_video_path = None

    if embed_captions and video_path and os.path.exists(video_path):
        JOB_STORE[job_id].update({"status": "embedding_captions", "progress": 78})
        burned_video_path = os.path.abspath(os.path.join(upload_dir, f"{job_id}_burned.mp4"))

        def _update_burn_prog(p: int):
            if job_id in JOB_STORE:
                JOB_STORE[job_id]["progress"] = p

        def _update_burn_eta(rem_sec: int):
            if job_id in JOB_STORE:
                JOB_STORE[job_id]["eta_seconds"] = max(1, rem_sec)

        caption_style = job_data.get("caption_style")
        if embed_subtitles(video_path, srt_path, burned_video_path,
                           style_config=caption_style,
                           progress_callback=_update_burn_prog,
                           eta_callback=_update_burn_eta):
            burning_successful = True
            logger.info(f"Job {job_id}: Burn-in successful -> {burned_video_path}")
        else:
            logger.error(f"Job {job_id}: Burn-in failed")

    JOB_STORE[job_id].update({
        "status": "completed",
        "progress": 100,
        "eta_seconds": 0,
        "has_srt": os.path.exists(srt_path),
        "video_burned": burning_successful,
        "burned_video_filename": os.path.basename(burned_video_path) if burning_successful else None,
        "srt_filename": f"{job_id}.srt",
    })
    logger.info(f"Job {job_id}: Fully completed. SRT and video ready.")

    # Cleanup temp audio
    if audio_path and os.path.exists(audio_path):
        try:
            os.remove(audio_path)
        except Exception:
            pass


def resume_after_warning(job_id: str) -> bool:
    """Triggered when user explicitly opts to proceed despite moral law warning."""
    job_data = JOB_STORE.get(job_id)
    if not job_data:
        return False
    t = threading.Thread(target=finalize_transcription, args=(job_id,), daemon=True)
    t.start()
    return True


def cancel_job(job_id: str) -> bool:
    """Triggered when user cancels and discards video upon warning."""
    job_data = JOB_STORE.get(job_id)
    if not job_data:
        return False
    upload_dir = get_upload_dir()
    for fname in [f"{job_id}.mp4", f"{job_id}.srt", f"{job_id}_burned.mp4", f"{job_id}.wav"]:
        p = os.path.join(upload_dir, fname)
        if os.path.exists(p):
            try:
                os.remove(p)
            except Exception:
                pass
    JOB_STORE[job_id].update({
        "status": "failed",
        "error": "Process halted by user after moral law warning.",
        "progress": 0,
        "eta_seconds": 0,
    })
    return True


# ---------------------------------------------------------------------------
# Legacy entry point
# ---------------------------------------------------------------------------
def transcribe_video(job_id: str, video_path: str, embed_captions: bool = False):
    """Alias: run stage 1 only (language detection + wait for confirmation)."""
    extract_and_detect(job_id, video_path, embed_captions)
