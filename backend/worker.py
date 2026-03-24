import os
import whisper
import ffmpeg
import redis
import json
import logging
from celery import Celery

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Setup Celery and Redis
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
celery = Celery("tasks", broker=REDIS_URL, backend=REDIS_URL)
r = redis.from_url(REDIS_URL)

MODEL_NAME = os.getenv("WHISPER_MODEL", "base")
# Model is lazy-loaded to avoid memory issues on worker startup if many workers spawn
_model = None

def get_model():
    global _model
    if _model is None:
        logger.info(f"Loading Whisper model: {MODEL_NAME}")
        _model = whisper.load_model(MODEL_NAME)
    return _model

def format_timestamp(seconds: float):
    td = float(seconds)
    hours = int(td // 3600)
    minutes = int((td % 3600) // 60)
    secs = int(td % 60)
    milliseconds = int(round((td - (hours * 3600 + minutes * 60 + secs)) * 1000))
    if milliseconds == 1000: # Rounding overflow
        secs += 1
        milliseconds = 0
    return f"{hours:02}:{minutes:02}:{secs:02},{milliseconds:03}"

from video_utils import embed_subtitles
from moderation import analyze_content

@celery.task(name="transcribe_video")
def transcribe_video(job_id, video_path, embed_captions=False):
    try:
        # Get current job data to preserve filename
        current_data = json.loads(r.get(f"job:{job_id}") or "{}")
        
        # Update status
        current_data.update({"status": "extracting_audio", "progress": 10})
        r.set(f"job:{job_id}", json.dumps(current_data))
        logger.info(f"Processing Job {job_id}: Extracting audio from {video_path}")
        
        # 1. Extract Audio
        audio_path = f"{video_path}.wav"
        try:
            ffmpeg.input(video_path).output(
                audio_path, 
                acodec='pcm_s16le', 
                ac=1, 
                ar='16k'
            ).run(overwrite_output=True, quiet=True)
        except Exception as e:
            logger.error(f"FFmpeg error: {e}")
            current_data.update({"status": "failed", "error": f"FFmpeg error: {str(e)}"})
            r.set(f"job:{job_id}", json.dumps(current_data))
            return

        current_data.update({"status": "transcribing", "progress": 30})
        r.set(f"job:{job_id}", json.dumps(current_data))
        logger.info(f"Job {job_id}: Starting transcription")
        
        # 2. Transcribe
        model = get_model()
        result = model.transcribe(audio_path, verbose=False)
        
        # 3. Generate SRT
        srt_segments = []
        full_text = []
        for i, segment in enumerate(result['segments']):
            start = format_timestamp(segment['start'])
            end = format_timestamp(segment['end'])
            text = segment['text'].strip()
            srt_segments.append(f"{i+1}\n{start} --> {end}\n{text}\n")
            full_text.append(text)
        
        srt_content = "\n".join(srt_segments)
        srt_path = f"{os.path.splitext(video_path)[0]}.srt"
        
        # 4. MODERATION: Catholic Friendly Check
        current_data.update({"status": "checking_faith_alignment", "progress": 70})
        r.set(f"job:{job_id}", json.dumps(current_data))
        
        is_aligned, message = analyze_content(" ".join(full_text))
        if not is_aligned:
             logger.warning(f"Job {job_id}: CONTENT REJECTED. Violation: {message}")
             # Cleanup immediately
             for p in [audio_path, video_path]:
                 if os.path.exists(p): os.remove(p)
             
             current_data.update({"status": "failed", "error": f"CATHOLIC CONTENT POLICY: {message}"})
             r.set(f"job:{job_id}", json.dumps(current_data))
             return

        # 5. Save SRT
        with open(srt_path, "w", encoding="utf-8") as f:
            f.write(srt_content)
            
        # Optional: Burn subtitles into video
        burning_successful = False
        burned_video_path = None
        if embed_captions:
            current_data.update({"status": "embedding_captions", "progress": 85})
            r.set(f"job:{job_id}", json.dumps(current_data))
            logger.info(f"Job {job_id}: Starting subtitle embedding (burn-in)")
            
            burned_video_path = f"{os.path.splitext(video_path)[0]}_burned.mp4"
            if embed_subtitles(video_path, srt_path, burned_video_path):
                burning_successful = True
                logger.info(f"Job {job_id}: Burn-in successful at {burned_video_path}")
            else:
                logger.error(f"Job {job_id}: Burn-in failed")

        current_data.update({
            "status": "completed", 
            "progress": 100, 
            "video_burned": burning_successful,
            "burned_video_filename": os.path.basename(burned_video_path) if burning_successful else None
        })
        r.set(f"job:{job_id}", json.dumps(current_data))
        logger.info(f"Job {job_id}: Completed. SRT saved at {srt_path}")
        
        # Cleanup audio & original video
        if os.path.exists(audio_path): os.remove(audio_path)
            
        if not embed_captions or burning_successful:
             if os.path.exists(video_path):
                 os.remove(video_path)
            
    except Exception as e:
        logger.error(f"Worker Error: {e}")
        try:
            current_data = json.loads(r.get(f"job:{job_id}") or "{}")
            current_data.update({"status": "failed", "error": str(e)})
            r.set(f"job:{job_id}", json.dumps(current_data))
        except:
             r.set(f"job:{job_id}", json.dumps({"status": "failed", "error": str(e)}))
