# jobs.py
# Shared in-memory job store for the standalone (non-Docker) version.
# Since the entire app runs in a single process, a module-level dict is
# safe and accessible from both main.py and worker.py.

from typing import Dict, Any

JOB_STORE: Dict[str, Any] = {}
