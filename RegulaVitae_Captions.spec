# RegulaVitae_Captions.spec
# PyInstaller spec file for Captions by RegulaVitae.
#
# Usage (from project root, with venv active):
#   pyinstaller RegulaVitae_Captions.spec
#
# Output: dist/RegulaVitae_Captions/   — a folder containing the .exe and all dependencies.

import sys
import os
from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs

block_cipher = None

# Collect whisper's data files (tokenizer assets, mel filters, etc.)
whisper_datas = collect_data_files("whisper")

# Collect tiktoken encoder data
tiktoken_datas = collect_data_files("tiktoken")

# Collect pywebview data files if present
try:
    webview_datas = collect_data_files("webview")
except Exception:
    webview_datas = []

a = Analysis(
    ["backend/launcher.py"],
    pathex=[
        os.path.abspath("backend"),
    ],
    binaries=[
        # Bundle ffmpeg.exe into the bin/ subdirectory of the package
        ("backend/bin/ffmpeg.exe", "bin"),
    ],
    datas=[
        # React production build
        ("frontend/dist", "frontend_dist"),
        # Backend Python modules that are not auto-detected
        ("backend/database.py",    "."),
        ("backend/jobs.py",        "."),
        ("backend/moderation.py",  "."),   # stub — always passes, moderation disabled
        ("backend/video_utils.py", "."),
        ("backend/worker.py",      "."),
        ("backend/main.py",        "."),
    ] + whisper_datas + tiktoken_datas + webview_datas,
    hiddenimports=[
        # ── Entry point modules (same process, must be importable) ──────────
        "main",
        "worker",
        "jobs",
        "database",
        "moderation",
        "video_utils",
        # ── Whisper / PyTorch ────────────────────────────────────────────────
        "whisper",
        "whisper.audio",
        "whisper.decoding",
        "whisper.model",
        "whisper.tokenizer",
        "whisper.transcribe",
        "whisper.utils",
        "tiktoken",
        "tiktoken_ext",
        "tiktoken_ext.openai_public",
        # ── Uvicorn internals (dynamically loaded, never auto-detected) ───────
        "uvicorn",
        "uvicorn.logging",
        "uvicorn.loops",
        "uvicorn.loops.auto",
        "uvicorn.loops.asyncio",
        "uvicorn.protocols",
        "uvicorn.protocols.http",
        "uvicorn.protocols.http.auto",
        "uvicorn.protocols.http.h11_impl",
        "uvicorn.protocols.http.httptools_impl",
        "uvicorn.protocols.websockets",
        "uvicorn.protocols.websockets.auto",
        "uvicorn.protocols.websockets.websockets_impl",
        "uvicorn.lifespan",
        "uvicorn.lifespan.on",
        "uvicorn.main",
        "uvicorn.config",
        "uvicorn.server",
        # ── FastAPI / Starlette ──────────────────────────────────────────────
        "fastapi",
        "fastapi.routing",
        "fastapi.middleware.cors",
        "fastapi.staticfiles",
        "fastapi.responses",
        "fastapi.security",
        "starlette",
        "starlette.routing",
        "starlette.middleware",
        "starlette.middleware.cors",
        "starlette.staticfiles",
        "starlette.responses",
        "starlette.requests",
        "starlette.background",
        "starlette.concurrency",
        "starlette.datastructures",
        "starlette.formparsers",
        "starlette.types",
        "anyio",
        "anyio.abc",
        "anyio._backends._asyncio",
        "h11",
        # ── Auth ─────────────────────────────────────────────────────────────
        "passlib",
        "passlib.context",
        "passlib.handlers",
        "passlib.handlers.bcrypt",
        "passlib.utils",
        "passlib.utils.binary",
        "passlib.utils.pbkdf2",
        "jose",
        "jose.jwt",
        "jose.jws",
        "jose.jwk",
        "jose.backends",
        "jose.backends.cryptography_backend",
        "cryptography",
        "cryptography.hazmat.primitives.asymmetric",
        "cryptography.hazmat.primitives.asymmetric.rsa",
        # ── Email / DNS validation ───────────────────────────────────────────
        "email_validator",
        "dns",
        "dns.resolver",
        "dns.rdatatype",
        "dns.rdataclass",
        "dns.name",
        "dns.query",
        "dns.message",
        # ── Pydantic v2 ──────────────────────────────────────────────────────
        "pydantic",
        "pydantic.networks",
        "pydantic._internal",
        "pydantic_core",
        # ── Standard / misc ──────────────────────────────────────────────────
        "aiofiles",
        "multipart",
        "multipart.multipart",
        "sqlite3",
        "python_multipart",
        # ── PyTorch CUDA (must be included — torch imports it at startup) ───
        "torch.cuda",
        "torch.cuda.amp",
        "torch.backends",
        "torch.backends.cuda",
        "torch.backends.cudnn",
        # ── pywebview (native desktop window) ────────────────
        "webview",
        "webview.platforms",
        "webview.platforms.winforms",
        "webview.platforms.edgechromium",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # unconditionally at startup regardless of GPU availability.
        # Excluding it causes an immediate ModuleNotFoundError crash.
        "torchvision",
        "torchaudio",
        # Celery / Redis no longer used
        "celery",
        "redis",
        "kombu",
        "amqp",
        "billiard",
        # Other unneeded packages
        "matplotlib",
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
    name="RegulaVitae_Captions",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,               # Compress with UPX if available (reduces size ~20%)
    console=False,          # No console window — errors logged to regulavitae_launcher.log
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,              # Add an .ico path here to set a custom icon
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="RegulaVitae_Captions",
)
