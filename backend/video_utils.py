import ffmpeg
import os
import sys
import logging

logger = logging.getLogger(__name__)


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


def embed_subtitles(video_path, srt_path, output_path):
    """
    Burn subtitles (.srt) into a video (.mp4) using FFmpeg.
    Optimized for Windows path escaping, ultrafast x264 encoding, and multi-threading.
    """
    try:
        logger.info(f"Burning subtitles from {srt_path} into {video_path}")
        ffmpeg_bin = get_ffmpeg_bin()

        # FFmpeg subtitle filter string on Windows requires forward slashes and escaped colons
        # e.g., C:\Users\name\...\file.srt -> C\:/Users/name/.../file.srt
        clean_srt = os.path.abspath(srt_path).replace("\\", "/")
        escaped_srt = clean_srt.replace(":", "\\:")

        # Fast encoding options:
        # - preset: ultrafast for maximum re-encoding speed
        # - threads: 0 for utilizing all available CPU logical cores
        # - vcodec: libx264, pix_fmt: yuv420p for max compatibility across players
        (
            ffmpeg
            .input(video_path)
            .output(
                output_path,
                vf=f"subtitles='{escaped_srt}'",
                vcodec="libx264",
                acodec="copy",
                preset="ultrafast",
                threads=0,
                pix_fmt="yuv420p"
            )
            .run(cmd=ffmpeg_bin, overwrite_output=True, quiet=True)
        )

        logger.info(f"Subtitles burned successfully. Output: {output_path}")
        return True
    except ffmpeg.Error as e:
        stderr_msg = e.stderr.decode("utf-8", errors="ignore") if hasattr(e, "stderr") and e.stderr else str(e)
        logger.error(f"FFmpeg burn-in error: {stderr_msg}")
        return False
    except Exception as e:
        logger.error(f"Error burning subtitles: {e}")
        return False

