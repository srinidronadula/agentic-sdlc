import secrets
import string
from urllib.parse import urlparse

from shortener import db


class InvalidURLError(Exception):
    """Raised when URL validation fails."""
    pass


class CodeGenerationError(Exception):
    """Raised when unable to generate unique code."""
    pass


def validate_url(url: str) -> None:
    """Validate that URL has http or https scheme."""
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            raise InvalidURLError("Invalid URL: must be http or https")
        if not parsed.netloc:
            raise InvalidURLError("Invalid URL: missing domain")
    except Exception as e:
        if isinstance(e, InvalidURLError):
            raise
        raise InvalidURLError(f"Invalid URL: {str(e)}")


def generate_code(length: int = 6) -> str:
    """Generate a random alphanumeric code."""
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


def create_short_url(long_url: str, base_url: str = "http://localhost:5000") -> dict:
    """
    Create a shortened URL entry.

    Args:
        long_url: The original URL to shorten
        base_url: Base URL for short links (for response)

    Returns:
        Dict with code, short_url, long_url, created_at

    Raises:
        InvalidURLError: URL validation failed
        CodeGenerationError: Cannot generate unique code
    """
    validate_url(long_url)

    # Try to generate a unique code (up to 10 retries)
    max_retries = 10
    for _ in range(max_retries):
        code = generate_code()
        if db.create_url(code, long_url):
            # Success
            short_url = f"{base_url}/{code}"
            url_record = db.get_url(code)
            return {
                "code": code,
                "short_url": short_url,
                "long_url": long_url,
                "created_at": url_record["created_at"],
            }

    raise CodeGenerationError("Failed to generate unique code after retries")


def get_redirect_url(code: str) -> str | None:
    """
    Get original URL and increment click counter.

    Args:
        code: The short code

    Returns:
        Original URL if code exists, None otherwise
    """
    url_record = db.get_url(code)
    if url_record:
        db.increment_clicks(code)
        return url_record["long_url"]
    return None


def get_stats(code: str) -> dict | None:
    """
    Get stats for a short code.

    Args:
        code: The short code

    Returns:
        Dict with code, long_url, clicks, created_at, or None if not found
    """
    url_record = db.get_url(code)
    if url_record:
        return {
            "code": url_record["code"],
            "long_url": url_record["long_url"],
            "clicks": url_record["clicks"],
            "created_at": url_record["created_at"],
        }
    return None
