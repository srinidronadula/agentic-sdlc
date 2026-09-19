import secrets
import string
import logging
from urllib.parse import urlparse
from typing import Optional

from shortener import db
from shortener import alias_validator

# Configure logger
logger = logging.getLogger(__name__)


class InvalidURLError(Exception):
    """Raised when URL validation fails."""
    pass


class CodeGenerationError(Exception):
    """Raised when unable to generate unique code."""
    pass


class AliasValidationError(Exception):
    """Raised when alias validation fails."""
    pass


def validate_url(url: str) -> None:
    """
    Validate that URL has http or https scheme and is well-formed.
    
    Raises:
        InvalidURLError: If URL is invalid
    """
    if not url:
        logger.warning("URL validation failed: empty URL")
        raise InvalidURLError("URL cannot be empty")
    
    if not isinstance(url, str):
        logger.warning(f"URL validation failed: not a string, type={type(url)}")
        raise InvalidURLError("URL must be a string")
    
    # Check length to prevent DoS
    if len(url) > 2048:
        logger.warning(f"URL validation failed: too long (length={len(url)})")
        raise InvalidURLError("URL is too long (max 2048 characters)")
    
    try:
        parsed = urlparse(url)
        
        if not parsed.scheme:
            logger.warning("URL validation failed: no scheme provided")
            raise InvalidURLError("Invalid URL: must be http or https")
        
        if parsed.scheme not in ("http", "https"):
            logger.warning(f"URL validation failed: invalid scheme={parsed.scheme}")
            raise InvalidURLError("Invalid URL: must be http or https")
        
        if not parsed.netloc:
            logger.warning("URL validation failed: missing domain")
            raise InvalidURLError("Invalid URL: missing domain")
        
        logger.debug(f"URL validation passed: {parsed.scheme}://{parsed.netloc}...")
        
    except InvalidURLError:
        raise
    except Exception as e:
        logger.error(f"URL validation error: {str(e)}")
        raise InvalidURLError(f"Invalid URL: {str(e)}")


def generate_code(length: int = 6) -> str:
    """Generate a random alphanumeric code."""
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


def create_short_url(
    long_url: str,
    alias: Optional[str] = None,
    base_url: str = "http://localhost:5000"
) -> dict:
    """
    Create a shortened URL entry with retry logic for collisions.

    Args:
        long_url: The original URL to shorten
        alias: Optional custom alias for the short link
        base_url: Base URL for short links (for response)

    Returns:
        Dict with code, alias, short_url, long_url, created_at

    Raises:
        InvalidURLError: URL validation failed
        AliasValidationError: Alias validation failed
        CodeGenerationError: Cannot generate unique code
    """
    validate_url(long_url)
    logger.info(f"Creating short URL for: {long_url[:50]}...")

    # Validate alias if provided
    if alias is not None:
        is_valid, error_msg, error_code = alias_validator.validate_alias(alias)
        if not is_valid:
            logger.warning(f"Alias validation failed: {error_msg}")
            raise AliasValidationError(error_msg)

    # Use alias as code if provided, otherwise generate random code
    if alias:
        code = alias
        logger.debug(f"Using alias as code: {code}")
        if not db.create_url(code, long_url, alias=alias):
            # Alias already taken
            logger.warning(f"Alias already taken: {alias}")
            raise AliasValidationError("Alias already taken")
    else:
        # Try to generate a unique code (up to 10 retries with exponential backoff)
        max_retries = 10
        code = None
        for attempt in range(max_retries):
            generated_code = generate_code()
            logger.debug(f"Collision retry attempt {attempt + 1}/{max_retries}, code={generated_code}")
            
            if db.create_url(generated_code, long_url, alias=None):
                code = generated_code
                logger.info(f"Successfully created short URL with code: {code}")
                break
        
        if code is None:
            logger.error(f"Failed to generate unique code after {max_retries} retries")
            raise CodeGenerationError("Failed to generate unique code after retries")

    # Fetch the record to get created_at
    try:
        url_record = db.get_url(code)
        if not url_record:
            logger.error(f"Created URL record not found: {code}")
            raise CodeGenerationError("Failed to retrieve created URL record")
        
        short_url = f"{base_url}/{code}"
        result = {
            "code": code,
            "alias": url_record["alias"],
            "short_url": short_url,
            "long_url": long_url,
            "created_at": url_record["created_at"],
        }
        logger.debug(f"Returning short URL result: {result}")
        return result
    except Exception as e:
        logger.error(f"Error retrieving created URL: {str(e)}")
        raise CodeGenerationError(f"Error retrieving created URL: {str(e)}")


def get_redirect_url(code: str) -> str | None:
    """
    Get original URL and increment click counter.

    Args:
        code: The short code or alias

    Returns:
        Original URL if code/alias exists, None otherwise
    """
    try:
        url_record = db.get_url(code)
        if url_record:
            db.increment_clicks(code)
            logger.debug(f"Incremented clicks for code: {code}")
            return url_record["long_url"]
        logger.debug(f"Code not found: {code}")
        return None
    except Exception as e:
        logger.error(f"Error getting redirect URL for {code}: {str(e)}")
        return None


def get_stats(code: str) -> dict | None:
    """
    Get stats for a short code or alias.

    Args:
        code: The short code or alias

    Returns:
        Dict with code, alias, long_url, clicks, created_at, or None if not found
    """
    try:
        url_record = db.get_url(code)
        if url_record:
            result = {
                "code": url_record["code"],
                "alias": url_record["alias"],
                "long_url": url_record["long_url"],
                "clicks": url_record["clicks"],
                "created_at": url_record["created_at"],
            }
            logger.debug(f"Retrieved stats for code: {code}")
            return result
        logger.debug(f"Code not found for stats: {code}")
        return None
    except Exception as e:
        logger.error(f"Error getting stats for {code}: {str(e)}")
        return None
