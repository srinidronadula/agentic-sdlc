import sqlite3
import threading
import logging
from contextlib import contextmanager
from pathlib import Path

logger = logging.getLogger(__name__)

DB_PATH = "urls.db"
_lock = threading.Lock()


def init_db():
    """Initialize database schema with proper constraints."""
    try:
        with get_connection() as conn:
            # Create table with all necessary constraints
            conn.execute("""
                CREATE TABLE IF NOT EXISTS urls (
                    code TEXT PRIMARY KEY,
                    long_url TEXT NOT NULL,
                    alias TEXT UNIQUE NULL DEFAULT NULL,
                    clicks INTEGER DEFAULT 0 CHECK (clicks >= 0),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create indexes for performance
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_created_at ON urls(created_at)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_alias ON urls(alias) WHERE alias IS NOT NULL
            """)
            
            conn.commit()
            logger.info("Database initialized successfully")
    except sqlite3.Error as e:
        logger.error(f"Database initialization failed: {str(e)}")
        raise


@contextmanager
def get_connection():
    """
    Get a thread-safe database connection with proper error handling.
    
    Uses a lock to serialize access (appropriate for SQLite).
    Ensures rows are returned as dictionaries.
    """
    with _lock:
        try:
            conn = sqlite3.connect(DB_PATH, timeout=10.0)
            conn.row_factory = sqlite3.Row
            # Enable foreign keys if needed in the future
            conn.execute("PRAGMA foreign_keys = ON")
            try:
                yield conn
            except sqlite3.Error as e:
                logger.error(f"Database error: {str(e)}")
                conn.rollback()
                raise
            finally:
                conn.close()
        except sqlite3.Error as e:
            logger.error(f"Failed to establish database connection: {str(e)}")
            raise


def create_url(code: str, long_url: str, alias: str | None = None) -> bool:
    """
    Insert a new shortened URL with transaction safety.
    
    Args:
        code: The short code (must be unique)
        long_url: The original URL to store
        alias: Optional custom alias (must be unique if provided)
    
    Returns:
        True on success, False if code or alias already exists.
    """
    if not code or not isinstance(code, str):
        logger.warning(f"Invalid code: {code}")
        return False
    
    if not long_url or not isinstance(long_url, str):
        logger.warning(f"Invalid long_url for code {code}")
        return False
    
    try:
        with get_connection() as conn:
            conn.execute(
                """INSERT INTO urls (code, long_url, alias, clicks) 
                   VALUES (?, ?, ?, ?)""",
                (code, long_url, alias, 0),
            )
            conn.commit()
            logger.debug(f"Created URL record: code={code}, alias={alias}")
            return True
    except sqlite3.IntegrityError as e:
        # Expected when code or alias already exists
        logger.debug(f"Integrity constraint violation (expected on collision): {str(e)}")
        return False
    except sqlite3.Error as e:
        logger.error(f"Database error while creating URL: {str(e)}")
        return False


def get_url(code: str) -> dict | None:
    """
    Fetch URL record by code or alias.
    
    Args:
        code: The short code or alias to look up
    
    Returns:
        Dict with url record fields or None if not found
    """
    if not code or not isinstance(code, str):
        logger.warning(f"Invalid code for lookup: {code}")
        return None
    
    try:
        with get_connection() as conn:
            row = conn.execute(
                """SELECT code, long_url, alias, clicks, created_at 
                   FROM urls 
                   WHERE code = ? OR alias = ?
                   LIMIT 1""",
                (code, code),
            ).fetchone()
        return dict(row) if row else None
    except sqlite3.Error as e:
        logger.error(f"Database error while fetching URL: {str(e)}")
        return None


def increment_clicks(code: str) -> bool:
    """
    Increment click counter for a code or alias atomically.
    
    Args:
        code: The short code or alias to increment
    
    Returns:
        True if code existed and was updated, False otherwise.
    """
    if not code or not isinstance(code, str):
        logger.warning(f"Invalid code for increment: {code}")
        return False
    
    try:
        with get_connection() as conn:
            cursor = conn.execute(
                """UPDATE urls 
                   SET clicks = clicks + 1 
                   WHERE code = ? OR alias = ?""",
                (code, code),
            )
            conn.commit()
            success = cursor.rowcount > 0
            if success:
                logger.debug(f"Incremented clicks for code: {code}")
            return success
    except sqlite3.Error as e:
        logger.error(f"Database error while incrementing clicks: {str(e)}")
        return False


def url_exists(code: str) -> bool:
    """
    Check if a short code or alias exists.
    
    Args:
        code: The short code or alias to check
    
    Returns:
        True if code/alias exists, False otherwise.
    """
    if not code or not isinstance(code, str):
        return False
    
    try:
        with get_connection() as conn:
            row = conn.execute(
                "SELECT 1 FROM urls WHERE code = ? OR alias = ? LIMIT 1",
                (code, code),
            ).fetchone()
        return row is not None
    except sqlite3.Error as e:
        logger.error(f"Database error while checking URL existence: {str(e)}")
        return False


def alias_exists(alias: str) -> bool:
    """
    Check if an alias exists in the database.
    
    Args:
        alias: The alias to check
    
    Returns:
        True if alias exists, False otherwise.
    """
    if not alias or not isinstance(alias, str):
        return False
    
    try:
        with get_connection() as conn:
            row = conn.execute(
                "SELECT 1 FROM urls WHERE alias = ? LIMIT 1",
                (alias,),
            ).fetchone()
        return row is not None
    except sqlite3.Error as e:
        logger.error(f"Database error while checking alias existence: {str(e)}")
        return False
