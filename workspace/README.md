# URL Shortener

A minimal FastAPI-based URL shortener service with SQLite persistence and click tracking.

## Features

- **POST /shorten** – Create a shortened URL with auto-generated 6-character code
- **GET /{code}** – Redirect to original URL (302) and atomically increment click counter
- **GET /stats/{code}** – View click statistics (code, original URL, total clicks, creation time)
- **SQLite persistence** – Data survives process restarts (`urls.db`)
- **Random codes** – Auto-generated alphanumeric, collision-checked
- **URL validation** – Strict http/https scheme enforcement, domain required
- **Thread-safe** – Uses file locks for concurrent database access
- **Fast lookup** – O(1) code-to-URL retrieval via primary key

## Setup

### Prerequisites
- Python 3.8+
- pip

### Install Dependencies

```bash
pip install -r requirements.txt
```

Installs:
- `fastapi` – Web framework
- `uvicorn` – ASGI server
- `pytest` – Testing framework
- `httpx` – HTTP client for testing

## Running the Server

```bash
uvicorn shortener.app:app --reload
```

Server runs on `http://localhost:8000` by default.

For production, use:
```bash
uvicorn shortener.app:app --host 0.0.0.0 --port 8000 --workers 4
```

## API Reference

### 1. Create a Shortened URL

**Endpoint:** `POST /shorten`

**Request:**
```json
{
  "long_url": "https://example.com/some/very/long/path?param=value&another=param"
}
```

**Response (201 Created):**
```json
{
  "code": "a7x9k2",
  "short_url": "http://localhost:8000/a7x9k2",
  "long_url": "https://example.com/some/very/long/path?param=value&another=param",
  "created_at": "2025-01-15T10:30:00Z"
}
```

**Example:**
```bash
curl -X POST "http://localhost:8000/shorten" \
  -H "Content-Type: application/json" \
  -d '{"long_url": "https://www.python.org/downloads"}'
```

**Error Responses:**
- **400 Bad Request** – Missing `long_url` field
  ```json
  {"detail": "missing field"}
  ```
- **400 Bad Request** – Invalid URL scheme (must be http or https)
  ```json
  {"detail": "URL must use http or https"}
  ```
- **400 Bad Request** – Malformed URL or missing domain
  ```json
  {"detail": "Invalid URL format"}
  ```
- **500 Internal Server Error** – Cannot generate unique code after retries
  ```json
  {"detail": "Failed to generate unique code"}
  ```

---

### 2. Redirect to Original URL

**Endpoint:** `GET /{code}`

**Response (302 Found):**
- Redirects client to the original long URL
- Increments click counter by 1 (atomic operation)
- Example: visiting `/a7x9k2` redirects to `https://example.com/some/very/long/path?...`

**Example:**
```bash
curl -L "http://localhost:8000/a7x9k2"
# Follows redirect automatically with -L flag
```

**Error Responses:**
- **404 Not Found** – Code doesn't exist
  ```json
  {"detail": "Short code not found"}
  ```

---

### 3. Get Statistics

**Endpoint:** `GET /stats/{code}`

**Response (200 OK):**
```json
{
  "code": "a7x9k2",
  "long_url": "https://example.com/some/very/long/path?param=value&another=param",
  "clicks": 42,
  "created_at": "2025-01-15T10:30:00Z"
}
```

**Example:**
```bash
curl "http://localhost:8000/stats/a7x9k2"
```

**Error Responses:**
- **404 Not Found** – Code doesn't exist
  ```json
  {"detail": "Short code not found"}
  ```

---

## Complete Usage Example

```bash
# Start server
uvicorn shortener.app:app --reload &

# Create shortened URL
CODE=$(curl -s -X POST "http://localhost:8000/shorten" \
  -H "Content-Type: application/json" \
  -d '{"long_url": "https://github.com/python/cpython"}' | jq -r '.code')

echo "Code: $CODE"

# Check stats before clicking
curl "http://localhost:8000/stats/$CODE"
# Output: {..., "clicks": 0}

# Simulate 3 clicks
for i in {1..3}; do
  curl -L "http://localhost:8000/$CODE" > /dev/null
done

# Check stats after clicking
curl "http://localhost:8000/stats/$CODE"
# Output: {..., "clicks": 3}
```

## Running Tests

```bash
pytest -v
```

Expected output:
```
tests/test_shortener.py::test_create_shortened_url PASSED
tests/test_shortener.py::test_invalid_url_scheme PASSED
tests/test_shortener.py::test_missing_domain PASSED
tests/test_shortener.py::test_redirect_increments_clicks PASSED
tests/test_shortener.py::test_get_stats PASSED
tests/test_shortener.py::test_code_not_found PASSED
tests/test_shortener.py::test_different_urls_different_codes PASSED
tests/test_shortener.py::test_multiple_clicks PASSED
tests/test_shortener.py::test_persistence_across_requests PASSED
tests/test_shortener.py::test_code_collision_handling PASSED
tests/test_shortener.py::test_stats_includes_all_fields PASSED
tests/test_shortener.py::test_redirect_without_prior_creation PASSED

======================== 12 passed in 1.31s ========================
```

Run specific test:
```bash
pytest tests/test_shortener.py::test_create_shortened_url -v
```

## Project Structure

```
workspace/
├── shortener/
│   ├── __init__.py              # Package init
│   ├── app.py                   # FastAPI application, route handlers
│   ├── db.py                    # SQLite operations, schema management
│   ├── service.py               # Business logic, validation, code generation
│   └── utils.py                 # Utility functions (if any)
├── tests/
│   ├── __init__.py
│   ├── conftest.py              # Pytest fixtures (test client, temp DB)
│   └── test_shortener.py        # 12 integration tests
├── urls.db                       # SQLite database (auto-created on startup)
├── requirements.txt             # Python dependencies
├── pytest.ini                   # Pytest configuration
└── README.md                    # This file
```

## Database

SQLite database `urls.db` is created automatically on first startup in the working directory.

### Schema

```sql
CREATE TABLE urls (
  code TEXT PRIMARY KEY,
  long_url TEXT NOT NULL,
  clicks INTEGER DEFAULT 0,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_created_at ON urls(created_at);
```

### Details

- **code** – Primary key; 6-character random alphanumeric string
- **long_url** – Original URL (required); stored as-is
- **clicks** – Integer click counter; defaults to 0, incremented on each redirect
- **created_at** – ISO timestamp; auto-populated on insert
- **Index on created_at** – Prepared for future features (e.g., purging old entries)

## Configuration

### Base URL

Short links use `http://localhost:8000/` as the base. To customize:

1. Set environment variable:
   ```bash
   export BASE_URL="https://short.example.com"
   ```

2. Or modify `shortener/app.py` line (example):
   ```python
   BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000")
   ```

### Code Length

Currently hardcoded to 6 characters. To change:

1. Edit `shortener/service.py`:
   ```python
   CODE_LENGTH = 8  # Change from 6 to 8
   ```

2. Regenerate database (old codes will still work, new ones will be 8 chars)

### Collision Handling

Collision detection uses up to 10 retries. To increase/decrease:

1. Edit `shortener/service.py`:
   ```python
   MAX_RETRIES = 20  # Change from 10 to 20
   ```

## Limitations

### By Design

1. **No authentication** – Any client can create or view stats. Not suitable for multi-tenant use.
2. **No URL deduplication** – Shortening the same long URL twice produces different codes.
3. **No referrer/user-agent tracking** – Only total clicks counted, no granular analytics.
4. **No expiry** – Shortened URLs persist forever (no TTL mechanism).
5. **Random codes only** – Users cannot customize short codes (e.g., `/mycompany`).
6. **Single-process SQLite** – File-based locking; horizontal scaling requires external DB.
7. **Total click count only** – No timestamp per click, no unique user detection.

### Operational Considerations

1. **Collision risk at scale** – With 6-char alphanumeric (2.176B combinations):
   - ~1,000 URLs: negligible collision risk (~0.0%)
   - ~10M URLs: significant collision risk; recommend 8+ chars or external DB
   - Mitigation: increase `CODE_LENGTH` or switch to PostgreSQL

2. **Concurrency limits** – File-based locks (fcntl/msvcrt) are process-level:
   - OK for ~100 req/sec on modern hardware
   - For >1000 req/sec, migrate to PostgreSQL with proper connection pooling

3. **Database file size** – Each URL row ~200–500 bytes:
   - 1M URLs ≈ 200–500 MB
   - 10M URLs ≈ 2–5 GB (SQLite still handles well)
   - For 100M+ URLs, use PostgreSQL

4. **No backup mechanism** – `urls.db` is single point of failure. Backup regularly:
   ```bash
   cp urls.db urls.db.backup.$(date +%s)
   ```

### Security Considerations

1. **No rate limiting** – Clients can hammer `/shorten` or stats endpoints. Add rate limiting for production.
2. **No URL sanitization** – Long URLs stored and redirected as-is. Inject/XSS risk if URL contains untrusted data.
3. **Open API** – Anyone can create short links and view stats. Add authentication/authorization for sensitive use.
4. **Redirect flooding** – Malicious actors can artificially inflate click counters. No click validation.

## Migration Path

To scale beyond these limitations:

1. **Multi-user support** – Add user table, JWT auth, per-user URLs
2. **Detailed analytics** – Add `clicks` table with (code, timestamp, ip, user_agent)
3. **URL deduplication** – Hash long URL, check before insert; reuse existing code
4. **Custom codes** – Add user input validation, check availability before creation
5. **External database** – Swap SQLite for PostgreSQL/MySQL; remove file locks
6. **Caching** – Add Redis for hot code lookup, analytics aggregation
7. **Expiry** – Add TTL column, cleanup job for expired entries
8. **Rate limiting** – Integrate slowapi or similar middleware

## Error Handling

| HTTP Code | Scenario | Response |
|-----------|----------|----------|
| 201 | URL shortened successfully | JSON with code, short_url, long_url, created_at |
| 302 | Redirect to original URL | Location header; click counter incremented |
| 200 | Stats retrieved | JSON with code, long_url, clicks, created_at |
| 400 | Invalid request (missing field, bad scheme, malformed URL) | JSON `{"detail": "..."}` |
| 404 | Code not found | JSON `{"detail": "Short code not found"}` |
| 500 | Collision after retries, DB failure | JSON `{"detail": "Failed to generate unique code"}` |

## Troubleshooting

### "Address already in use"
Port 8000 is taken. Use a different port:
```bash
uvicorn shortener.app:app --port 8001
```

### "urls.db is locked"
Another process is accessing the database. Ensure only one server instance is running, or restart both.

### Tests failing with "database is locked"
Run with increased timeout or serial execution:
```bash
pytest --timeout=10
```

### "Failed to generate unique code"
Extremely rare. Indicates collision after 10 retries. Either:
- Increase `MAX_RETRIES` in `service.py`
- Increase `CODE_LENGTH` to 7+ chars
- Switch to external database

## License

MIT (implied). See source code for details.

## Support

For bugs or questions, refer to the test suite in `tests/test_shortener.py` for expected behavior.
