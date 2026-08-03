"""
database.py — SQLite-backed user persistence for the standalone app.
Replaces Redis as the user credential store.
The database file (regula.db) is stored next to the executable when
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
    """Return the correct path for the SQLite database in both dev and frozen modes."""
    if getattr(sys, "frozen", False):
        # Running as a PyInstaller bundle — store next to the .exe
        base = os.path.dirname(sys.executable)
    else:
        # Running in development — store next to this file
        base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, "regula.db")


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
