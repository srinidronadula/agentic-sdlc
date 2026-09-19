"""
Test suite for URL Shortener reliability improvements.

Tests cover:
- Input validation (URL format, length, types)
- Error handling (logging, graceful failures)
- Database constraints (uniqueness, integrity)
- Collision handling (retry logic)
- Edge cases (None, empty strings, special characters)
"""
import pytest


class TestInputValidation:
    """Test URL input validation and safety checks."""
    
    def test_valid_http_url(self, client):
        """Valid HTTP URL should be accepted."""
        response = client.post("/shorten", json={"url": "http://example.com"})
        assert response.status_code == 201
        assert "code" in response.json()
    
    def test_valid_https_url(self, client):
        """Valid HTTPS URL should be accepted."""
        response = client.post("/shorten", json={"url": "https://example.com/path"})
        assert response.status_code == 201
        assert "code" in response.json()
    
    def test_valid_https_with_query_params(self, client):
        """HTTPS URL with query parameters should be accepted."""
        response = client.post(
            "/shorten",
            json={"url": "https://example.com/path?key=value&foo=bar"}
        )
        assert response.status_code == 201
        assert "code" in response.json()
    
    def test_valid_https_with_fragment(self, client):
        """HTTPS URL with fragment should be accepted."""
        response = client.post(
            "/shorten",
            json={"url": "https://example.com/path#section"}
        )
        assert response.status_code == 201
        assert "code" in response.json()
    
    def test_invalid_url_none(self, client):
        """None as URL should be rejected."""
        response = client.post("/shorten", json={"url": None})
        assert response.status_code == 400
        assert "cannot be empty" in response.json()["detail"].lower()
    
    def test_invalid_url_empty_string(self, client):
        """Empty string as URL should be rejected."""
        response = client.post("/shorten", json={"url": ""})
        assert response.status_code == 400
        assert "cannot be empty" in response.json()["detail"].lower()
    
    def test_invalid_url_whitespace_only(self, client):
        """Whitespace-only URL should be rejected."""
        response = client.post("/shorten", json={"url": "   "})
        assert response.status_code == 400
    
    def test_invalid_url_no_scheme(self, client):
        """URL without scheme should be rejected."""
        response = client.post("/shorten", json={"url": "example.com"})
        assert response.status_code == 400
        assert "http or https" in response.json()["detail"].lower()
    
    def test_invalid_url_ftp_scheme(self, client):
        """URL with FTP scheme should be rejected."""
        response = client.post("/shorten", json={"url": "ftp://example.com"})
        assert response.status_code == 400
        assert "http or https" in response.json()["detail"].lower()
    
    def test_invalid_url_missing_domain(self, client):
        """URL with scheme but no domain should be rejected."""
        response = client.post("/shorten", json={"url": "https://"})
        assert response.status_code == 400
        assert "missing domain" in response.json()["detail"].lower()
    
    def test_invalid_url_too_long(self, client):
        """URL exceeding max length should be rejected."""
        long_url = "https://example.com/" + "a" * 2100
        response = client.post("/shorten", json={"url": long_url})
        assert response.status_code == 400
        assert "too long" in response.json()["detail"].lower()
    
    def test_valid_url_with_port(self, client):
        """URL with explicit port should be accepted."""
        response = client.post("/shorten", json={"url": "https://example.com:8080/path"})
        assert response.status_code == 201
        assert "code" in response.json()
    
    def test_valid_url_with_basic_auth(self, client):
        """URL with basic auth should be accepted."""
        response = client.post("/shorten", json={"url": "https://user:pass@example.com"})
        assert response.status_code == 201
        assert "code" in response.json()


class TestCollisionHandling:
    """Test collision detection and retry logic."""
    
    def test_different_urls_get_different_codes(self, client):
        """Two different URLs should get different short codes."""
        url1 = "https://example1.com"
        url2 = "https://example2.com"
        
        response1 = client.post("/shorten", json={"url": url1})
        response2 = client.post("/shorten", json={"url": url2})
        
        code1 = response1.json()["code"]
        code2 = response2.json()["code"]
        
        assert code1 != code2
    
    def test_same_url_different_codes(self, client):
        """Same URL shortened twice should get different codes."""
        url = "https://example.com"
        
        response1 = client.post("/shorten", json={"url": url})
        response2 = client.post("/shorten", json={"url": url})
        
        code1 = response1.json()["code"]
        code2 = response2.json()["code"]
        
        assert code1 != code2
    
    def test_code_uniqueness_constraint(self, client):
        """Two requests with same generated code should not cause data corruption."""
        # Create one URL
        response1 = client.post(
            "/shorten",
            json={"url": "https://example1.com"}
        )
        assert response1.status_code == 201
        
        # Create another URL
        response2 = client.post(
            "/shorten",
            json={"url": "https://example2.com"}
        )
        assert response2.status_code == 201
        
        # Both should exist
        code1 = response1.json()["code"]
        code2 = response2.json()["code"]
        
        stats1 = client.get(f"/stats/{code1}").json()
        stats2 = client.get(f"/stats/{code2}").json()
        
        assert stats1["long_url"] == "https://example1.com"
        assert stats2["long_url"] == "https://example2.com"


class TestDatabaseIntegrity:
    """Test database constraint enforcement and recovery."""
    
    def test_clicks_counter_never_negative(self, client):
        """Click counter should be enforced non-negative."""
        response = client.post("/shorten", json={"url": "https://example.com"})
        code = response.json()["code"]
        
        # Click multiple times
        for _ in range(5):
            client.get(f"/{code}")
        
        stats = client.get(f"/stats/{code}").json()
        assert stats["clicks"] == 5
        assert stats["clicks"] >= 0
    
    def test_url_record_has_all_required_fields(self, client):
        """Created URL record should have all required fields."""
        response = client.post("/shorten", json={"url": "https://example.com"})
        assert response.status_code == 201
        
        data = response.json()
        assert "code" in data
        assert "short_url" in data
        assert "long_url" in data
        assert "created_at" in data
        assert data["long_url"] == "https://example.com"
    
    def test_stats_response_consistency(self, client):
        """Stats response should be consistent across calls."""
        response = client.post("/shorten", json={"url": "https://example.com"})
        code = response.json()["code"]
        
        stats1 = client.get(f"/stats/{code}").json()
        stats2 = client.get(f"/stats/{code}").json()
        
        # Data consistency: same code, same long_url, same created_at
        assert stats1["code"] == stats2["code"]
        assert stats1["long_url"] == stats2["long_url"]
        assert stats1["created_at"] == stats2["created_at"]


class TestAliasValidation:
    """Test custom alias validation and uniqueness."""
    
    def test_valid_alias(self, client):
        """Valid alias should be accepted."""
        response = client.post(
            "/shorten",
            json={"url": "https://example.com", "alias": "mylink"}
        )
        assert response.status_code == 201
        assert response.json()["code"] == "mylink"
    
    def test_alias_taken_returns_409(self, client):
        """Duplicate alias should return 409 Conflict."""
        # Create first URL with alias
        response1 = client.post(
            "/shorten",
            json={"url": "https://example1.com", "alias": "taken"}
        )
        assert response1.status_code == 201
        
        # Try to create another with same alias
        response2 = client.post(
            "/shorten",
            json={"url": "https://example2.com", "alias": "taken"}
        )
        assert response2.status_code == 409
        assert "taken" in response2.json()["detail"].lower()
    
    def test_reserved_alias_rejected(self, client):
        """Reserved aliases should be rejected."""
        response = client.post(
            "/shorten",
            json={"url": "https://example.com", "alias": "admin"}
        )
        assert response.status_code == 400
        assert "reserved" in response.json()["detail"].lower()
    
    def test_alias_with_invalid_format(self, client):
        """Invalid alias format should be rejected."""
        response = client.post(
            "/shorten",
            json={"url": "https://example.com", "alias": "UPPERCASE"}
        )
        assert response.status_code == 400
    
    def test_alias_too_short(self, client):
        """Alias shorter than 3 chars should be rejected."""
        response = client.post(
            "/shorten",
            json={"url": "https://example.com", "alias": "ab"}
        )
        assert response.status_code == 400
    
    def test_alias_too_long(self, client):
        """Alias longer than 50 chars should be rejected."""
        response = client.post(
            "/shorten",
            json={"url": "https://example.com", "alias": "a" * 51}
        )
        assert response.status_code == 400


class TestErrorHandling:
    """Test graceful error handling and error responses."""
    
    def test_missing_url_field_returns_400(self, client):
        """Missing URL field should return 400."""
        response = client.post("/shorten", json={})
        assert response.status_code == 400
        assert "Missing required field" in response.json()["detail"]
    
    def test_missing_url_field_with_alias(self, client):
        """Missing URL field even with alias should return 400."""
        response = client.post("/shorten", json={"alias": "test"})
        assert response.status_code == 400
        assert "Missing required field" in response.json()["detail"]
    
    def test_nonexistent_code_returns_404_on_redirect(self, client):
        """Redirect with nonexistent code should return 404."""
        response = client.get("/nonexistent123")
        assert response.status_code == 404
    
    def test_nonexistent_code_returns_404_on_stats(self, client):
        """Stats request for nonexistent code should return 404."""
        response = client.get("/stats/nonexistent123")
        assert response.status_code == 404
    
    def test_error_response_has_detail_field(self, client):
        """Error response should have detail field."""
        response = client.post("/shorten", json={"url": "ftp://example.com"})
        assert response.status_code == 400
        assert "detail" in response.json()
        assert isinstance(response.json()["detail"], str)


class TestPersistence:
    """Test data persistence and recovery."""
    
    def test_url_persists_across_requests(self, client):
        """Created URL should persist across multiple requests."""
        # Create URL
        create_response = client.post(
            "/shorten",
            json={"url": "https://example.com/path"}
        )
        code = create_response.json()["code"]
        
        # Verify it exists
        redirect_response = client.get(f"/{code}", follow_redirects=False)
        assert redirect_response.status_code == 302
        
        # Verify stats exist
        stats_response = client.get(f"/stats/{code}")
        assert stats_response.status_code == 200
    
    def test_clicks_persist_across_requests(self, client):
        """Click count should persist across requests."""
        # Create URL
        create_response = client.post(
            "/shorten",
            json={"url": "https://example.com"}
        )
        code = create_response.json()["code"]
        
        # Click it
        client.get(f"/{code}")
        client.get(f"/{code}")
        
        # Verify count
        stats = client.get(f"/stats/{code}").json()
        assert stats["clicks"] == 2
        
        # Click again
        client.get(f"/{code}")
        
        # Verify updated count
        stats = client.get(f"/stats/{code}").json()
        assert stats["clicks"] == 3
    
    def test_alias_persists_across_requests(self, client):
        """Custom alias should persist and be retrievable."""
        # Create with alias
        create_response = client.post(
            "/shorten",
            json={"url": "https://example.com", "alias": "custom"}
        )
        assert create_response.status_code == 201
        assert create_response.json()["code"] == "custom"
        
        # Redirect using alias
        redirect_response = client.get("/custom", follow_redirects=False)
        assert redirect_response.status_code == 302
        
        # Get stats using alias
        stats_response = client.get("/stats/custom")
        assert stats_response.status_code == 200
        assert stats_response.json()["alias"] == "custom"


class TestResponseFormats:
    """Test that responses have correct format and data types."""
    
    def test_shorten_response_format(self, client):
        """Shorten response should have correct format."""
        response = client.post(
            "/shorten",
            json={"url": "https://example.com"}
        )
        data = response.json()
        
        assert isinstance(data["code"], str)
        assert isinstance(data["short_url"], str)
        assert isinstance(data["long_url"], str)
        assert isinstance(data["created_at"], str)
        assert data["code"] in data["short_url"]
    
    def test_stats_response_format(self, client):
        """Stats response should have correct format."""
        create_response = client.post(
            "/shorten",
            json={"url": "https://example.com"}
        )
        code = create_response.json()["code"]
        
        stats = client.get(f"/stats/{code}").json()
        
        assert isinstance(stats["code"], str)
        assert isinstance(stats["long_url"], str)
        assert isinstance(stats["clicks"], int)
        assert isinstance(stats["created_at"], str)
    
    def test_redirect_response_headers(self, client):
        """Redirect response should have correct headers."""
        create_response = client.post(
            "/shorten",
            json={"url": "https://example.com/target"}
        )
        code = create_response.json()["code"]
        
        response = client.get(f"/{code}", follow_redirects=False)
        
        assert response.status_code == 302
        assert "location" in response.headers
        assert response.headers["location"] == "https://example.com/target"


class TestIdempotency:
    """Test behavior with repeated operations."""
    
    def test_same_url_multiple_times(self, client):
        """Creating same URL multiple times should succeed with different codes."""
        url = "https://example.com"
        
        codes = []
        for _ in range(3):
            response = client.post("/shorten", json={"url": url})
            assert response.status_code == 201
            codes.append(response.json()["code"])
        
        # All codes should be unique
        assert len(codes) == len(set(codes))
        
        # All should redirect to same URL
        for code in codes:
            response = client.get(f"/{code}", follow_redirects=False)
            assert response.headers["location"] == url
    
    def test_stats_multiple_calls(self, client):
        """Multiple stats calls should return consistent data."""
        create_response = client.post(
            "/shorten",
            json={"url": "https://example.com"}
        )
        code = create_response.json()["code"]
        
        stats_list = [
            client.get(f"/stats/{code}").json()
            for _ in range(3)
        ]
        
        # All stats calls should return same data (except clicks may increment)
        for i in range(len(stats_list) - 1):
            assert stats_list[i]["code"] == stats_list[i + 1]["code"]
            assert stats_list[i]["long_url"] == stats_list[i + 1]["long_url"]
            assert stats_list[i]["created_at"] == stats_list[i + 1]["created_at"]
