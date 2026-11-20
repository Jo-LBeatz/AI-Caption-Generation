import ffmpeg
import os
import sys
import logging
try:
    import torch
except ImportError:
    torch = None

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
from typing import Optional, Dict, Any

# ---------------------------------------------------------------------------
# Caption Style & Aesthetic Definitions
# Matches high-level AI captions software presets with authentic subtitle sizing
# ---------------------------------------------------------------------------
def hex_to_ass_color(hex_str: str, alpha: int = 0) -> str:
    """
    Converts a standard web hex color string (#RRGGBB) to ASS color format (&HAABBGGRR).
    Alpha is 0 for 100% opaque, 255 (0xFF) for 100% transparent.
    """
    if not hex_str:
        return f"&H{alpha:02X}FFFFFF"
    clean = hex_str.lstrip("#")
    if len(clean) == 3:
        clean = "".join([c * 2 for c in clean])
    if len(clean) == 6:
        r, g, b = clean[0:2], clean[2:4], clean[4:6]
        return f"&H{alpha:02X}{b.upper()}{g.upper()}{r.upper()}"
    return f"&H{alpha:02X}FFFFFF"


STYLE_PRESETS: Dict[str, Dict[str, Any]] = {
    "classic": {
        "name": "Classic Subtitle",
        "font_name": "Arial",
        "font_size": 13,             # Proper subtitle size: restrained, clear, unobtrusive
        "primary_color": "#FFFFFF",
        "outline_color": "#000000",
        "outline_width": 1.2,
        "border_style": 1,           # Outline + drop shadow
        "shadow_depth": 0.8,
        "back_color": "#000000",
        "back_opacity": 0.0,
        "bold": False,
        "italic": False,
        "alignment": 2,              # Bottom center
        "margin_v": 24,
    },
    "sacred_gold": {
        "name": "Sacred Gold",
        "font_name": "Georgia",
        "font_size": 13,
        "primary_color": "#FFD700",  # Sacred golden amber
        "outline_color": "#1A0F00",
        "outline_width": 1.2,
        "border_style": 1,
        "shadow_depth": 0.8,
        "back_color": "#000000",
        "back_opacity": 0.0,
        "bold": False,
        "italic": False,
        "alignment": 2,
        "margin_v": 24,
    },
    "cinematic_box": {
        "name": "Cinematic Box",
        "font_name": "Arial",
        "font_size": 12,             # Clean Netflix/Prime streaming style
        "primary_color": "#FFFFFF",
        "outline_color": "#000000",
        "outline_width": 0.0,
        "border_style": 3,           # Translucent bounding box
        "shadow_depth": 0.0,
        "back_color": "#000000",
        "back_opacity": 0.60,        # 60% translucent dark pill box
        "bold": False,
        "italic": False,
        "alignment": 2,
        "margin_v": 24,
    },
    "yellow_pop": {
        "name": "Yellow Pop",
        "font_name": "Trebuchet MS",
        "font_size": 13,
        "primary_color": "#FFF000",  # High-visibility yellow
        "outline_color": "#000000",
        "outline_width": 1.4,
        "border_style": 1,
        "shadow_depth": 0.8,
        "back_color": "#000000",
        "back_opacity": 0.0,
        "bold": False,
        "italic": False,
        "alignment": 2,
        "margin_v": 24,
    },
    "bold_impact": {
        "name": "Bold Modern",
        "font_name": "Trebuchet MS",
        "font_size": 13,
        "primary_color": "#FFFFFF",
        "outline_color": "#000000",
        "outline_width": 1.6,
        "border_style": 1,
        "shadow_depth": 1.0,
        "back_color": "#000000",
        "back_opacity": 0.0,
        "bold": True,
        "italic": False,
        "alignment": 2,
        "margin_v": 24,
    },
    "minimalist": {
        "name": "Minimalist White",
        "font_name": "Segoe UI",
        "font_size": 12,
        "primary_color": "#F1F5F9",
        "outline_color": "#0F172A",
        "outline_width": 0.8,
        "border_style": 1,
        "shadow_depth": 0.0,
        "back_color": "#000000",
        "back_opacity": 0.0,
        "bold": False,
        "italic": False,
        "alignment": 2,
        "margin_v": 22,
    },
}


def build_ass_force_style(style_config: Optional[dict] = None) -> str:
    """
    Construct the ASS force_style string for FFmpeg subtitles filter.
    Guarantees captions are formatted as genuine subtitles with clean, restrained sizing.
    """
    cfg = dict(STYLE_PRESETS["classic"])
    if style_config:
        preset_key = style_config.get("preset", "classic")
        if preset_key in STYLE_PRESETS:
            cfg.update(STYLE_PRESETS[preset_key])
        for k, v in style_config.items():
            if v is not None:
                cfg[k] = v

    # Enforce subtitle sizing: cap between 10 and 15pt so captions never become oversized
    raw_size = int(cfg.get("font_size", 13))
    font_size = max(10, min(15, raw_size))

    font_name = cfg.get("font_name", "Arial")
    pri_col = hex_to_ass_color(cfg.get("primary_color", "#FFFFFF"), alpha=0)
    out_col = hex_to_ass_color(cfg.get("outline_color", "#000000"), alpha=0)

    # Backing box / shadow color
    back_op = float(cfg.get("back_opacity", 0.0))
    back_alpha = int((1.0 - back_op) * 255)
    back_col = hex_to_ass_color(cfg.get("back_color", "#000000"), alpha=back_alpha)

    border_style = int(cfg.get("border_style", 1))
    outline = float(cfg.get("outline_width", 1.2))
    shadow = float(cfg.get("shadow_depth", 0.8))
    bold = 1 if cfg.get("bold") else 0
    italic = 1 if cfg.get("italic") else 0
    alignment = int(cfg.get("alignment", 2))
    margin_v = int(cfg.get("margin_v", 24))

    style_parts = [
        f"Fontname={font_name}",
        f"FontSize={font_size}",
        f"PrimaryColour={pri_col}",
        f"OutlineColour={out_col}",
        f"BackColour={back_col}",
        f"BorderStyle={border_style}",
        f"Outline={outline}",
        f"Shadow={shadow}",
        f"Bold={bold}",
        f"Italic={italic}",
        f"Alignment={alignment}",
        f"MarginV={margin_v}",
    ]
    return ",".join(style_parts)


_NVENC_AVAILABLE = None

def has_nvenc_encoder(ffmpeg_bin: str) -> bool:
    """
    Probe if NVIDIA NVENC hardware encoder is supported and active.
    Works independently of PyTorch build by directly testing FFmpeg with the NVIDIA GPU driver.
    """
    global _NVENC_AVAILABLE
    if _NVENC_AVAILABLE is not None:
        return _NVENC_AVAILABLE
    try:
        res = subprocess.run(
            [ffmpeg_bin, "-f", "lavfi", "-i", "color=c=black:s=256x256:d=0.04", "-c:v", "h264_nvenc", "-f", "null", "-"],
            capture_output=True,
            text=True,
            timeout=4,
        )
        _NVENC_AVAILABLE = (res.returncode == 0)
    except Exception as e:
        logger.debug(f"NVENC probe failed: {e}")
        _NVENC_AVAILABLE = False
    return _NVENC_AVAILABLE


def embed_subtitles(video_path, srt_path, output_path, style_config=None, progress_callback=None, eta_callback=None):
    """
    Burn subtitles (.srt) into a video (.mp4) using FFmpeg with customizable styles.
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

        force_style_str = build_ass_force_style(style_config)
        sub_filter = f"subtitles='{escaped_srt}':force_style='{force_style_str}'"

        # Try GPU NVENC acceleration first (detected via hardware probe or PyTorch)
        use_nvenc = has_nvenc_encoder(ffmpeg_bin) or bool(torch and torch.cuda.is_available())
        if use_nvenc:
            try:
                logger.info("Using NVIDIA NVENC hardware encoder for high-speed subtitle burning.")
                gpu_cmd = [
                    ffmpeg_bin, "-y",
                    "-i", video_path,
                    "-vf", sub_filter,
                    "-vcodec", "h264_nvenc",
                    "-acodec", "copy",
                    "-preset", "p2",
                    "-rc:v", "vbr",
                    "-cq", "22",
                    "-b:v", "0",
                    "-pix_fmt", "yuv420p",
                    "-progress", "pipe:1",
                    output_path,
                ]
                if run_ffmpeg_cmd(gpu_cmd) and os.path.exists(output_path) and os.path.getsize(output_path) > 1000:
                    logger.info(f"Subtitles burned via GPU NVENC successfully. Output: {output_path}")
                    return True
            except Exception as gpu_err:
                logger.warning(f"GPU NVENC burn-in failed ({gpu_err}). Falling back to CPU ultrafast.")

        # Multi-threaded CPU ultrafast encoding fallback
        logger.info("Using multi-threaded CPU x264 encoding for subtitle burning.")
        cpu_cmd = [
            ffmpeg_bin, "-y",
            "-i", video_path,
            "-vf", sub_filter,
            "-vcodec", "libx264",
            "-acodec", "copy",
            "-preset", "ultrafast",
            "-tune", "fastdecode",
            "-crf", "22",
            "-threads", "0",
            "-pix_fmt", "yuv420p",
            "-progress", "pipe:1",
            output_path,
        ]
        if run_ffmpeg_cmd(cpu_cmd) and os.path.exists(output_path) and os.path.getsize(output_path) > 1000:
            logger.info(f"Subtitles burned successfully. Output: {output_path}")
            return True

        logger.error("FFmpeg burn-in process exited with non-zero code.")
        return False
    except Exception as e:
        logger.error(f"Error burning subtitles: {e}")
        return False

