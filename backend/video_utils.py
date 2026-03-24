import ffmpeg
import os
import logging

logger = logging.getLogger(__name__)

def embed_subtitles(video_path, srt_path, output_path):
    """
    Burn subtitles (.srt) into a video (.mp4) using FFmpeg.
    Uses the 'subtitles' filter which requires the .srt file path.
    """
    try:
        logger.info(f"Burning subtitles from {srt_path} into {video_path}")
        
        # FFmpeg command to burn subtitles
        # Note: The 'subtitles' filter filename must be escaped properly for FFmpeg if it contains special characters
        # For simplicity in this env, we assume the path is clean but we use the filter as a string
        # command: ffmpeg -i input.mp4 -vf "subtitles=subs.srt" -c:a copy output.mp4
        
        (
            ffmpeg
            .input(video_path)
            .output(output_path, vf=f"subtitles={srt_path}", acodec='copy')
            .run(overwrite_output=True, quiet=True)
        )
        
        logger.info(f"Subtitles burned successfully. Output: {output_path}")
        return True
    except Exception as e:
        logger.error(f"Error burning subtitles: {e}")
        return False
