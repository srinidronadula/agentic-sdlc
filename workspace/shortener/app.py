from fastapi import FastAPI, HTTPException
from fastapi.responses import RedirectResponse

from shortener import db
from shortener.service import (
    create_short_url,
    get_redirect_url,
    get_stats,
    InvalidURLError,
    CodeGenerationError,
)

app = FastAPI(title="URL Shortener")


# Initialize database on startup
@app.on_event("startup")
async def startup():
    db.init_db()


class ShortenRequest:
    def __init__(self, url: str):
        self.url = url


class ShortenResponse:
    def __init__(self, code: str, short_url: str, long_url: str, created_at: str):
        self.code = code
        self.short_url = short_url
        self.long_url = long_url
        self.created_at = created_at


@app.post("/shorten", status_code=201)
async def shorten(request: dict) -> dict:
    """
    Create a shortened URL.

    Request: {"url": "https://example.com/long/path"}
    Response: {"code": "abc123", "short_url": "...", "long_url": "...", "created_at": "..."}
    """
    if "url" not in request:
        raise HTTPException(
            status_code=400, detail="Missing required field: url"
        )

    long_url = request["url"]

    try:
        result = create_short_url(long_url)
        return result
    except InvalidURLError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except CodeGenerationError as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/{code}")
async def redirect_to_url(code: str):
    """
    Redirect to original URL and increment click counter.

    Response: 302 redirect to original URL
    """
    long_url = get_redirect_url(code)
    if not long_url:
        raise HTTPException(status_code=404, detail="Short code not found")
    return RedirectResponse(url=long_url, status_code=302)


@app.get("/stats/{code}")
async def get_url_stats(code: str) -> dict:
    """
    Get statistics for a shortened URL.

    Response: {"code": "...", "long_url": "...", "clicks": N, "created_at": "..."}
    """
    stats = get_stats(code)
    if not stats:
        raise HTTPException(status_code=404, detail="Short code not found")
    return stats
