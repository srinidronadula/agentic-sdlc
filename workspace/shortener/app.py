import logging
from fastapi import FastAPI, HTTPException
from fastapi.responses import RedirectResponse

from shortener import db
from shortener.service import (
    create_short_url,
    get_redirect_url,
    get_stats,
    InvalidURLError,
    CodeGenerationError,
    AliasValidationError,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI(title="URL Shortener")


# Initialize database on startup
@app.on_event("startup")
async def startup():
    try:
        db.init_db()
        logger.info("Application startup: database initialized")
    except Exception as e:
        logger.error(f"Startup failed: {str(e)}")
        raise


class ShortenRequest:
    def __init__(self, url: str, alias: str | None = None):
        self.url = url
        self.alias = alias


class ShortenResponse:
    def __init__(
        self,
        code: str,
        alias: str | None,
        short_url: str,
        long_url: str,
        created_at: str,
    ):
        self.code = code
        self.alias = alias
        self.short_url = short_url
        self.long_url = long_url
        self.created_at = created_at


@app.post("/shorten", status_code=201)
async def shorten(request: dict) -> dict:
    """
    Create a shortened URL.

    Request: {"url": "https://example.com/long/path", "alias": "optional-custom-alias"}
    Response: {"code": "abc123", "alias": null, "short_url": "...", "long_url": "...", "created_at": "..."}
    """
    if "url" not in request:
        logger.warning("Shorten request missing 'url' field")
        raise HTTPException(
            status_code=400, detail="Missing required field: url"
        )

    long_url = request["url"]
    alias = request.get("alias")

    try:
        logger.info(f"Processing shorten request for alias={alias}")
        result = create_short_url(long_url, alias=alias)
        logger.info(f"Successfully shortened URL: code={result['code']}")
        return result
    except InvalidURLError as e:
        logger.warning(f"Invalid URL error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except AliasValidationError as e:
        error_msg = str(e)
        # Distinguish between taken (409) and invalid format/reserved (400)
        if "taken" in error_msg.lower():
            logger.warning(f"Alias taken: {alias}")
            raise HTTPException(status_code=409, detail=error_msg)
        else:
            logger.warning(f"Alias validation error: {error_msg}")
            raise HTTPException(status_code=400, detail=error_msg)
    except CodeGenerationError as e:
        logger.error(f"Code generation error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error in shorten: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/{code}")
async def redirect_to_url(code: str):
    """
    Redirect to original URL and increment click counter.

    Response: 302 redirect to original URL
    """
    try:
        long_url = get_redirect_url(code)
        if not long_url:
            logger.debug(f"Short code not found: {code}")
            raise HTTPException(status_code=404, detail="Short code not found")
        logger.debug(f"Redirecting code {code} to target URL")
        return RedirectResponse(url=long_url, status_code=302)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in redirect: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/stats/{code}")
async def get_url_stats(code: str) -> dict:
    """
    Get statistics for a shortened URL.

    Response: {"code": "...", "alias": null, "long_url": "...", "clicks": N, "created_at": "..."}
    """
    try:
        stats = get_stats(code)
        if not stats:
            logger.debug(f"Stats not found for code: {code}")
            raise HTTPException(status_code=404, detail="Short code not found")
        logger.debug(f"Retrieved stats for code: {code}")
        return stats
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in stats: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")
