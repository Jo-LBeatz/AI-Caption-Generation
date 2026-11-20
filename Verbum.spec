# Verbum.spec
# PyInstaller spec file for Verbum — AI Caption Software.
#
# Usage (from project root, with venv active):
#   pyinstaller Verbum.spec
#
# Output: dist/Verbum/ — a folder containing Verbum.exe and all dependencies.

import sys
import os
from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs, collect_submodules

block_cipher = None

# Collect whisper's data files (tokenizer assets, mel filters, etc.)
whisper_datas = collect_data_files("whisper")

# Collect tiktoken encoder data
tiktoken_datas = collect_data_files("tiktoken")

# Collect faster-whisper data files (tokenizer assets)
try:
    faster_whisper_datas = collect_data_files("faster_whisper")
except Exception:
    faster_whisper_datas = []

# Collect ctranslate2 dynamic libraries
try:
    ctranslate2_libs = collect_dynamic_libs("ctranslate2")
except Exception:
    ctranslate2_libs = []

# Collect pywebview data files, dynamic libraries and submodules
try:
    webview_datas = collect_data_files("webview")
    webview_libs = collect_dynamic_libs("webview")
    webview_submodules = [s for s in collect_submodules("webview") if "android" not in s]
except Exception:
    webview_datas = []
    webview_libs = []
    webview_submodules = []

try:
    pythonnet_datas = collect_data_files("pythonnet")
    pythonnet_libs = collect_dynamic_libs("pythonnet")
    pythonnet_submodules = collect_submodules("pythonnet")
except Exception:
    pythonnet_datas = []
    pythonnet_libs = []
    pythonnet_submodules = []

try:
    clr_loader_datas = collect_data_files("clr_loader")
    clr_loader_libs = collect_dynamic_libs("clr_loader")
except Exception:
    clr_loader_datas = []
    clr_loader_libs = []

a = Analysis(
    ["backend/launcher.py"],
    pathex=[
        os.path.abspath("backend"),
    ],
    binaries=[
        # Bundle ffmpeg.exe into the bin/ subdirectory of the package
        ("backend/bin/ffmpeg.exe", "bin"),
    ] + ctranslate2_libs + webview_libs + pythonnet_libs + clr_loader_libs,
    datas=[
        # React production build
        ("frontend/dist", "frontend_dist"),
        # Backend Python modules
        ("backend/database.py",    "."),
        ("backend/jobs.py",        "."),
        ("backend/morality.py",    "."),
        ("backend/moderation.py",  "."),
        ("backend/video_utils.py", "."),
        ("backend/worker.py",      "."),
        ("backend/main.py",        "."),
    ] + whisper_datas + tiktoken_datas + faster_whisper_datas + webview_datas + pythonnet_datas + clr_loader_datas,
    hiddenimports=[
        # Entry point modules
        "main",
        "worker",
        "jobs",
        "database",
        "morality",
        "moderation",
        "video_utils",
        # Whisper / PyTorch
        "whisper",
        "whisper.audio",
        "whisper.decoding",
        "whisper.model",
        "whisper.tokenizer",
        "whisper.transcribe",
        "torch",
        "torchaudio",
        # Faster-whisper / CTranslate2
        "faster_whisper",
        "ctranslate2",
        "tokenizers",
        # .NET runtime and webview
        "clr",
        "clr_loader",
        "pythonnet",
        "webview",
        "webview.platforms",
        "webview.platforms.winforms",
        "webview.platforms.edgechromium",
        # FastAPI / Uvicorn
        "uvicorn",
        "uvicorn.logging",
        "uvicorn.loops",
        "uvicorn.loops.auto",
        "uvicorn.protocols",
        "uvicorn.protocols.http",
        "uvicorn.protocols.http.auto",
        "uvicorn.protocols.http.h11_impl",
        "uvicorn.protocols.http.httptools_impl",
        "uvicorn.protocols.websockets",
        "uvicorn.protocols.websockets.auto",
        "uvicorn.lifespan",
        "uvicorn.lifespan.on",
        "fastapi",
        "fastapi.staticfiles",
        "starlette",
        "starlette.staticfiles",
        "starlette.responses",
        "starlette.routing",
        "starlette.middleware",
        "starlette.middleware.cors",
        "pydantic",
        "pydantic.deprecated",
        "pydantic.deprecated.decorator",
        "pydantic_core",
        # Networking / Multipart / Encoding
        "python_multipart",
        "multipart",
        "aiofiles",
        "anyio",
        "anyio._backends",
        "anyio._backends._asyncio",
        "sniffio",
        "h11",
        "httpcore",
        "httpx",
        "PIL",
        "PIL.Image",
    ] + webview_submodules + pythonnet_submodules,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "tkinter",
        "matplotlib",
        "scipy",
        "pandas",
        "pytest",
        "IPython",
        "jupyter",
        "notebook",
        "ipykernel",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Verbum",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon="icon.ico",
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="Verbum",
)
