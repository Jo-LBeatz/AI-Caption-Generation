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

if sys.platform == "win32":
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        if hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# ---------------------------------------------------------------------------
# Logging configuration — writes to log file in a user-writable directory
# ---------------------------------------------------------------------------
def _get_app_data_dir() -> str:
    """
    Return a user-writable directory for app data.
    On Windows installed builds this is %APPDATA%\RegulaVitae Captions\
    so we never try to write into the read-only Program Files folder.
    """
    if getattr(sys, "frozen", False):
        # Installed app — use %APPDATA% (always user-writable)
        appdata = os.environ.get("APPDATA") or os.path.expanduser("~")
        app_dir = os.path.join(appdata, "Verbum")
    else:
        # Development — keep files next to this script
        app_dir = os.path.dirname(os.path.abspath(__file__))
    os.makedirs(app_dir, exist_ok=True)
    return app_dir


_app_data_dir = _get_app_data_dir()
_log_path = os.path.join(_app_data_dir, "verbum_launcher.log")

_stream_handler = logging.StreamHandler(sys.stdout)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(_log_path, mode="w", encoding="utf-8"),
        _stream_handler,
    ],
)
logger = logging.getLogger(__name__)
logger.info(f"Launcher started. Log file: {_log_path}")

APP_TITLE = "Verbum — AI Caption Software"
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
        logger.info(f"Starting uvicorn server on 0.0.0.0:{PORT}")
        _SERVER_STARTED = True
        uvicorn.run(app, host="0.0.0.0", port=PORT, log_config=None)
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
class WebViewApi:
    """
    Python API exposed to the JavaScript frontend via window.pywebview.api.
    This enables native OS capabilities (file dialogs, etc.) that are blocked
    in a sandboxed webview environment.
    """

    def save_srt(self, job_id: str, suggested_filename: str = "captions.srt") -> dict:
        """
        Show a native Save File dialog and write the SRT to the user-chosen path.
        Called from JavaScript: await window.pywebview.api.save_srt(jobId, filename)
        Returns {"success": True, "path": "..."} or {"success": False, "error": "..."}
        """
        return self._save_file_to_disk(
            job_id, suggested_filename,
            endpoint=f"{URL}/download-srt-to-disk/{job_id}",
            file_types=("SubRip Captions (*.srt)", "All Files (*.*)"),
            default_ext=".srt",
        )

    def save_video(self, job_id: str, suggested_filename: str = "video_captioned.mp4") -> dict:
        """
        Show a native Save File dialog and write the captioned video to the user-chosen path.
        Called from JavaScript: await window.pywebview.api.save_video(jobId, filename)
        """
        return self._save_file_to_disk(
            job_id, suggested_filename,
            endpoint=f"{URL}/download-video-to-disk/{job_id}",
            file_types=("MP4 Video (*.mp4)", "All Files (*.*)"),
            default_ext=".mp4",
        )

    def _save_file_to_disk(self, job_id: str, suggested_filename: str,
                           endpoint: str, file_types: tuple, default_ext: str) -> dict:
        """Internal helper: show save dialog then POST to backend to write the file."""
        try:
            import webview
            windows = webview.windows
            if not windows:
                return {"success": False, "error": "No webview window found."}

            result = windows[0].create_file_dialog(
                webview.SAVE_DIALOG,
                save_filename=suggested_filename,
                file_types=file_types,
            )

            if not result:
                return {"success": False, "error": "cancelled"}

            save_path = result[0] if isinstance(result, (list, tuple)) else result
            if not save_path.lower().endswith(default_ext):
                save_path += default_ext

            import urllib.request
            import urllib.parse
            import urllib.error

            encoded_path = urllib.parse.quote(save_path, safe="")
            api_url = f"{endpoint}?dest_path={encoded_path}"
            req = urllib.request.Request(
                api_url,
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=120) as resp:
                if resp.status == 200:
                    return {"success": True, "path": save_path}
                return {"success": False, "error": f"Server returned {resp.status}"}

        except urllib.error.HTTPError as e:
            err = e.read().decode("utf-8", errors="replace")
            logger.error(f"_save_file_to_disk HTTP error: {e.code} {err}")
            return {"success": False, "error": f"HTTP {e.code}: {err}"}
        except Exception as exc:
            logger.error(f"_save_file_to_disk error: {exc}")
            return {"success": False, "error": str(exc)}


_webview_api = WebViewApi()


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
            js_api=_webview_api,
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
