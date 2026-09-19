import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path

DB_PATH = "urls.db"
_lock = threading.Lock()


def init_db():
    """Initialize database schema."""
    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS urls (
                code TEXT PRIMARY KEY,
                long_url TEXT NOT NULL,
                clicks INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_created_at ON urls(created_at)
        """)
        conn.commit()


@contextmanager
def get_connection():
    """Get a thread-safe database connection."""
    with _lock:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()


def create_url(code: str, long_url: str) -> bool:
    """
    Insert a new shortened URL.
    Returns True on success, False if code already exists.
    """
    try:
        with get_connection() as conn:
            conn.execute(
                "INSERT INTO urls (code, long_url, clicks) VALUES (?, ?, ?)",
                (code, long_url, 0),
            )
            conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False


def get_url(code: str) -> dict | None:
    """Fetch URL record by code."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT code, long_url, clicks, created_at FROM urls WHERE code = ?",
            (code,),
        ).fetchone()
    return dict(row) if row else None


def increment_clicks(code: str) -> bool:
    """Increment click counter for a code. Returns True if code existed."""
    with get_connection() as conn:
        cursor = conn.execute(
            "UPDATE urls SET clicks = clicks + 1 WHERE code = ?",
            (code,),
        )
        conn.commit()
    return cursor.rowcount > 0


def url_exists(code: str) -> bool:
    """Check if a short code exists."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT 1 FROM urls WHERE code = ? LIMIT 1",
            (code,),
        ).fetchone()
    return row is not None
