"""
database.py — SQLite-backed user persistence for the standalone app.
Replaces Redis as the user credential store.
The database file (regulavitae.db) is stored next to the executable when
running as a PyInstaller bundle, or next to this file in development.
"""
import sqlite3
import os
import sys
import logging
from datetime import datetime
from typing import Optional, Dict, List

logger = logging.getLogger(__name__)


def get_db_path() -> str:
    """Return the correct path for the SQLite database in both dev, frozen, and cloud modes."""
    if os.getenv("VERCEL") or os.getenv("AWS_LAMBDA_FUNCTION_NAME") or (os.path.exists("/tmp") and os.access("/tmp", os.W_OK)):
        return "/tmp/regulavitae.db"
    if getattr(sys, "frozen", False):
        # Installed app — use %APPDATA% so we never write into the
        # read-only Program Files directory.
        appdata = os.environ.get("APPDATA") or os.path.expanduser("~")
        app_dir = os.path.join(appdata, "RegulaVitae Captions")
        os.makedirs(app_dir, exist_ok=True)
        base = app_dir
    else:
        # Running in development — store next to this file
        base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, "regulavitae.db")



def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Create tables if they don't exist. Called once on app startup."""
    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                email    TEXT PRIMARY KEY,
                password TEXT NOT NULL,
                joined_at TEXT NOT NULL
            )
        """)
        conn.commit()
    logger.info(f"Database initialised at: {get_db_path()}")


def get_user(email: str) -> Optional[Dict]:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE email = ?", (email.lower(),)
        ).fetchone()
        return dict(row) if row else None


def create_user(email: str, hashed_password: str) -> None:
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO users (email, password, joined_at) VALUES (?, ?, ?)",
            (email.lower(), hashed_password, datetime.utcnow().isoformat()),
        )
        conn.commit()


def get_all_users() -> List[Dict]:
    with get_connection() as conn:
        rows = conn.execute("SELECT email, joined_at FROM users").fetchall()
        return [dict(r) for r in rows]
