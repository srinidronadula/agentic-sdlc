import pytest


def test_shorten_valid_url(client):
    """Test creating a shortened URL."""
    response = client.post(
        "/shorten",
        json={"url": "https://example.com/some/very/long/path?param=value"},
    )
    assert response.status_code == 201
    data = response.json()
    assert "code" in data
    assert "short_url" in data
    assert "long_url" in data
    assert "created_at" in data
    assert data["long_url"] == "https://example.com/some/very/long/path?param=value"
    assert len(data["code"]) == 6


def test_shorten_missing_url_field(client):
    """Test creating URL without url field."""
    response = client.post("/shorten", json={})
    assert response.status_code == 400
    assert "Missing required field" in response.json()["detail"]


def test_shorten_invalid_url_scheme(client):
    """Test creating URL with invalid scheme."""
    response = client.post("/shorten", json={"url": "ftp://example.com"})
    assert response.status_code == 400
    assert "http or https" in response.json()["detail"]


def test_shorten_invalid_url_no_domain(client):
    """Test creating URL without domain."""
    response = client.post("/shorten", json={"url": "http://"})
    assert response.status_code == 400


def test_redirect_to_original_url(client):
    """Test redirecting from short code to original URL."""
    # Create a shortened URL
    create_response = client.post(
        "/shorten", json={"url": "https://example.com/target"}
    )
    code = create_response.json()["code"]

    # Redirect using the code
    response = client.get(f"/{code}", follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["location"] == "https://example.com/target"


def test_redirect_nonexistent_code(client):
    """Test redirecting with non-existent code."""
    response = client.get("/nonexistent")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"]


def test_click_count_increments(client):
    """Test that click count increments on each redirect."""
    # Create a shortened URL
    create_response = client.post(
        "/shorten", json={"url": "https://example.com/target"}
    )
    code = create_response.json()["code"]

    # Check initial stats (0 clicks)
    stats = client.get(f"/stats/{code}").json()
    assert stats["clicks"] == 0

    # Follow redirect once
    client.get(f"/{code}", follow_redirects=False)
    stats = client.get(f"/stats/{code}").json()
    assert stats["clicks"] == 1

    # Follow redirect again
    client.get(f"/{code}", follow_redirects=False)
    stats = client.get(f"/stats/{code}").json()
    assert stats["clicks"] == 2


def test_stats_nonexistent_code(client):
    """Test getting stats for non-existent code."""
    response = client.get("/stats/nonexistent")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"]


def test_stats_response_format(client):
    """Test stats response includes all required fields."""
    # Create a shortened URL
    create_response = client.post(
        "/shorten", json={"url": "https://example.com/target"}
    )
    code = create_response.json()["code"]

    # Get stats
    stats = client.get(f"/stats/{code}").json()
    assert stats["code"] == code
    assert stats["long_url"] == "https://example.com/target"
    assert stats["clicks"] == 0
    assert "created_at" in stats


def test_multiple_shortens_different_codes(client):
    """Test that different URLs get different codes."""
    url1 = "https://example.com/path1"
    url2 = "https://example.com/path2"

    response1 = client.post("/shorten", json={"url": url1})
    response2 = client.post("/shorten", json={"url": url2})

    code1 = response1.json()["code"]
    code2 = response2.json()["code"]

    assert code1 != code2

    # Both should redirect correctly
    r1 = client.get(f"/{code1}", follow_redirects=False)
    r2 = client.get(f"/{code2}", follow_redirects=False)

    assert r1.headers["location"] == url1
    assert r2.headers["location"] == url2


def test_shorten_same_url_twice_different_codes(client):
    """Test that same URL shortened twice gets different codes."""
    url = "https://example.com/target"

    response1 = client.post("/shorten", json={"url": url})
    response2 = client.post("/shorten", json={"url": url})

    code1 = response1.json()["code"]
    code2 = response2.json()["code"]

    # Different codes even though same URL
    assert code1 != code2

    # Both redirect to the same URL
    r1 = client.get(f"/{code1}", follow_redirects=False)
    r2 = client.get(f"/{code2}", follow_redirects=False)

    assert r1.headers["location"] == url
    assert r2.headers["location"] == url


def test_persistence_across_requests(client):
    """Test that data persists (simulating DB survival)."""
    # Create a shortened URL
    create_response = client.post(
        "/shorten", json={"url": "https://example.com/target"}
    )
    code = create_response.json()["code"]

    # Click it
    client.get(f"/{code}", follow_redirects=False)
    client.get(f"/{code}", follow_redirects=False)

    # Check stats
    stats = client.get(f"/stats/{code}").json()
    assert stats["clicks"] == 2

    # Verify we can still redirect
    response = client.get(f"/{code}", follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["location"] == "https://example.com/target"
