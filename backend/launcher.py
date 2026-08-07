"""
launcher.py — Entry point for the standalone Captions by RegulaVitae desktop app.

This script:
  1. Adds the bundled bin/ directory to PATH so ffmpeg.exe is found automatically.
  2. Dynamically finds an available open port (starting at 8000).
  3. Starts the FastAPI server (uvicorn) in a background thread.
  4. Waits for the server to become ready.
  5. Opens the app in a native OS window via pywebview (or default browser fallback).
  6. When the window is closed, the process exits cleanly.
"""
import os
import sys
import time
import socket
import threading
import logging
import traceback
import urllib.request

# ---------------------------------------------------------------------------
# Logging configuration — writes to log file in executable directory
# ---------------------------------------------------------------------------
if getattr(sys, "frozen", False):
    _log_dir = os.path.dirname(sys.executable)
else:
    _log_dir = os.path.dirname(os.path.abspath(__file__))

_log_path = os.path.join(_log_dir, "regulavitae_launcher.log")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(_log_path, mode="w", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)
logger.info(f"Launcher started. Log file: {_log_path}")

APP_TITLE = "Captions by RegulaVitae"
HOST = "127.0.0.1"


# ---------------------------------------------------------------------------
# Dynamic Free Port Discovery
# ---------------------------------------------------------------------------
def _find_free_port(start_port: int = 8000) -> int:
    """Find the first available TCP port starting from start_port."""
    for port in range(start_port, start_port + 50):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind((HOST, port))
                return port
            except OSError:
                continue
    return start_port


PORT = _find_free_port(8000)
URL = f"http://{HOST}:{PORT}"
logger.info(f"Selected port: {PORT} (URL: {URL})")

# Track thread status
_SERVER_ERROR = None
_SERVER_STARTED = False


# ---------------------------------------------------------------------------
# Windows native error dialog
# ---------------------------------------------------------------------------
def _show_error(title: str, message: str):
    try:
        import ctypes
        ctypes.windll.user32.MessageBoxW(0, message, title, 0x10)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Add bundled bin/ (ffmpeg.exe) to PATH
# ---------------------------------------------------------------------------
def _add_bundled_bin_to_path():
    if getattr(sys, "frozen", False):
        bin_dir = os.path.join(sys._MEIPASS, "bin")
    else:
        bin_dir = os.path.join(os.path.dirname(__file__), "bin")

    if os.path.isdir(bin_dir):
        os.environ["PATH"] = bin_dir + os.pathsep + os.environ.get("PATH", "")
        logger.info(f"Added to PATH: {bin_dir}")
    else:
        logger.warning(f"bin/ directory not found at {bin_dir}. FFmpeg burn-in may fail.")


# ---------------------------------------------------------------------------
# Uvicorn background server thread
# ---------------------------------------------------------------------------
def _start_uvicorn():
    global _SERVER_ERROR, _SERVER_STARTED
    try:
        import uvicorn
        import uvicorn.logging
        from main import app  # noqa: E402
        logger.info(f"Starting uvicorn server on {HOST}:{PORT}")
        _SERVER_STARTED = True
        uvicorn.run(app, host=HOST, port=PORT, log_config=None)
    except Exception as exc:
        _SERVER_ERROR = str(exc)
        logger.error(f"Uvicorn server crashed: {exc}\n{traceback.format_exc()}")


def _wait_for_server(timeout: float = 30.0) -> bool:
    """Poll server URL until it responds or error/timeout occurs."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if _SERVER_ERROR is not None:
            logger.error(f"Server thread failed early: {_SERVER_ERROR}")
            return False
        try:
            req = urllib.request.Request(URL, headers={"User-Agent": "RegulaVitaeLauncher/1.0"})
            with urllib.request.urlopen(req, timeout=2) as resp:
                if resp.status in (200, 301, 302, 307, 404):
                    return True
        except urllib.error.HTTPError:
            # HTTP response from server means server is listening!
            return True
        except Exception:
            time.sleep(0.3)
    return False


# ---------------------------------------------------------------------------
# Native Window Launcher
# ---------------------------------------------------------------------------
def _launch_window() -> bool:
    """Try launching pywebview native window; returns True if launched successfully."""
    try:
        import webview
        logger.info("Initializing pywebview native window...")
        window = webview.create_window(
            title=APP_TITLE,
            url=URL,
            width=1280,
            height=860,
            min_size=(1024, 700),
            resizable=True,
            confirm_close=True,
            background_color="#050504",
        )
        webview.start(debug=False)
        return True
    except Exception as exc:
        logger.warning(f"pywebview native window unavailable or closed with error: {exc}")
        return False


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    logger.info("=" * 60)
    logger.info(f"  {APP_TITLE} — Starting Application")
    logger.info(f"  URL: {URL}")
    logger.info("=" * 60)

    # 1. Setup PATH
    _add_bundled_bin_to_path()

    # 2. Start server thread
    server_thread = threading.Thread(target=_start_uvicorn, daemon=True)
    server_thread.start()

    # 3. Wait for server
    logger.info("Waiting for local API server to respond...")
    if not _wait_for_server(timeout=30.0):
        err_detail = _SERVER_ERROR if _SERVER_ERROR else "Server timed out after 30 seconds."
        msg = (
            f"{APP_TITLE} could not start its internal server.\n\n"
            f"Reason: {err_detail}\n\n"
            f"Log file: {_log_path}"
        )
        logger.error(msg)
        _show_error(f"{APP_TITLE} — Startup Error", msg)
        sys.exit(1)

    logger.info("Server is ready.")

    # 4. Open native UI window (or fallback to browser)
    success = _launch_window()
    if not success:
        logger.info("Opening application in default web browser...")
        import webbrowser
        webbrowser.open(URL)
        logger.info("App is running. Close this terminal or kill the process to stop.")
        try:
            server_thread.join()
        except KeyboardInterrupt:
            pass

    logger.info("Application closed. Exiting.")
    sys.exit(0)
