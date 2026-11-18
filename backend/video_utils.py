import ffmpeg
import os
import sys
import logging
import torch

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


import subprocess
import re

def get_video_duration(video_path: str) -> float:
    """Get the duration of a video in seconds using ffmpeg directly (without requiring ffprobe)."""
    try:
        ffmpeg_bin = get_ffmpeg_bin()
        res = subprocess.run(
            [ffmpeg_bin, "-i", video_path],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        match = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.?\d*)", res.stderr)
        if match:
            h, m, s = match.groups()
            duration = int(h) * 3600 + int(m) * 60 + float(s)
            return duration
    except Exception as e:
        logger.warning(f"Could not probe video duration for {video_path}: {e}")
    return 0.0


import time

def embed_subtitles(video_path, srt_path, output_path, progress_callback=None, eta_callback=None):
    """
    Burn subtitles (.srt) into a video (.mp4) using FFmpeg.
    Optimized for Windows path escaping, GPU NVENC acceleration when available,
    multi-threaded ultrafast CPU encoding fallback, and real-time progress updates.
    """
    try:
        logger.info(f"Burning subtitles from {srt_path} into {video_path}")
        ffmpeg_bin = get_ffmpeg_bin()

        clean_srt = os.path.abspath(srt_path).replace("\\", "/")
        escaped_srt = clean_srt.replace(":", "\\:")

        total_duration = get_video_duration(video_path)
        burn_start_time = time.time()

        def run_ffmpeg_cmd(cmd_list):
            process = subprocess.Popen(
                cmd_list,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                encoding="utf-8",
                errors="replace",
            )
            for line in process.stdout:
                line = line.strip()
                if total_duration > 0 and line.startswith("out_time_ms="):
                    try:
                        us = int(line.split("=")[1])
                        secs = us / 1_000_000.0
                        if progress_callback:
                            prog = min(99, int(80 + (secs / total_duration) * 19))
                            progress_callback(prog)
                        if eta_callback:
                            elapsed = max(0.1, time.time() - burn_start_time)
                            speed = secs / elapsed
                            if speed > 0.05:
                                rem_video = max(0.0, total_duration - secs)
                                eta_secs = int(rem_video / speed)
                                eta_callback(max(1, eta_secs))
                    except ValueError:
                        pass
            process.wait()
            return process.returncode == 0

        sub_filter = (
            f"subtitles='{escaped_srt}':force_style="
            "'FontSize=18,PrimaryColour=&H00FFFFFF,OutlineColour=&H80050504,"
            "BorderStyle=1,Outline=1.5,Shadow=0,MarginV=25,Alignment=2'"
        )

        # Try GPU NVENC acceleration first if CUDA is available
        if torch.cuda.is_available():
            try:
                gpu_cmd = [
                    ffmpeg_bin, "-y",
                    "-i", video_path,
                    "-vf", sub_filter,
                    "-vcodec", "h264_nvenc",
                    "-acodec", "copy",
                    "-preset", "p1",
                    "-pix_fmt", "yuv420p",
                    "-progress", "pipe:1",
                    output_path,
                ]
                if run_ffmpeg_cmd(gpu_cmd) and os.path.exists(output_path):
                    logger.info(f"Subtitles burned via GPU NVENC successfully. Output: {output_path}")
                    return True
            except Exception as gpu_err:
                logger.warning(f"GPU NVENC burn-in failed ({gpu_err}). Falling back to CPU ultrafast.")

        # Multi-threaded CPU ultrafast encoding fallback
        cpu_cmd = [
            ffmpeg_bin, "-y",
            "-i", video_path,
            "-vf", sub_filter,
            "-vcodec", "libx264",
            "-acodec", "copy",
            "-preset", "ultrafast",
            "-tune", "fastdecode",
            "-threads", "0",
            "-pix_fmt", "yuv420p",
            "-progress", "pipe:1",
            output_path,
        ]
        if run_ffmpeg_cmd(cpu_cmd) and os.path.exists(output_path):
            logger.info(f"Subtitles burned successfully. Output: {output_path}")
            return True

        logger.error("FFmpeg burn-in process exited with non-zero code.")
        return False
    except Exception as e:
        logger.error(f"Error burning subtitles: {e}")
        return False

