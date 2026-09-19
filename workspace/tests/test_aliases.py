import pytest


class TestAliasValidation:
    """Test custom alias validation."""

    def test_shorten_with_valid_custom_alias(self, client):
        """Test creating a shortened URL with a valid custom alias."""
        response = client.post(
            "/shorten",
            json={
                "url": "https://example.com/target",
                "alias": "my-custom-link",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["code"] == "my-custom-link"
        assert data["alias"] == "my-custom-link"
        assert data["long_url"] == "https://example.com/target"

    def test_shorten_with_alias_minimal_length(self, client):
        """Test alias with minimum length (3 chars)."""
        response = client.post(
            "/shorten",
            json={
                "url": "https://example.com/target",
                "alias": "abc",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["alias"] == "abc"

    def test_shorten_with_alias_maximum_length(self, client):
        """Test alias with maximum length (50 chars)."""
        long_alias = "a" * 50
        response = client.post(
            "/shorten",
            json={
                "url": "https://example.com/target",
                "alias": long_alias,
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["alias"] == long_alias

    def test_shorten_with_alias_too_short(self, client):
        """Test alias that is too short."""
        response = client.post(
            "/shorten",
            json={
                "url": "https://example.com/target",
                "alias": "ab",  # Only 2 chars
            },
        )
        assert response.status_code == 400
        assert "3-50 characters" in response.json()["detail"]

    def test_shorten_with_alias_too_long(self, client):
        """Test alias that is too long."""
        response = client.post(
            "/shorten",
            json={
                "url": "https://example.com/target",
                "alias": "a" * 51,  # 51 chars
            },
        )
        assert response.status_code == 400
        assert "3-50 characters" in response.json()["detail"]

    def test_shorten_with_alias_invalid_characters(self, client):
        """Test alias with invalid characters (uppercase, special chars)."""
        # Uppercase
        response = client.post(
            "/shorten",
            json={
                "url": "https://example.com/target",
                "alias": "My-Link",
            },
        )
        assert response.status_code == 400
        assert "lowercase" in response.json()["detail"].lower()

        # Special characters
        response = client.post(
            "/shorten",
            json={
                "url": "https://example.com/target",
                "alias": "my_link@123",
            },
        )
        assert response.status_code == 400

    def test_shorten_with_alias_leading_hyphen(self, client):
        """Test alias with leading hyphen (invalid)."""
        response = client.post(
            "/shorten",
            json={
                "url": "https://example.com/target",
                "alias": "-my-link",
            },
        )
        assert response.status_code == 400

    def test_shorten_with_alias_trailing_hyphen(self, client):
        """Test alias with trailing hyphen (invalid)."""
        response = client.post(
            "/shorten",
            json={
                "url": "https://example.com/target",
                "alias": "my-link-",
            },
        )
        assert response.status_code == 400

    def test_shorten_with_alias_empty_string(self, client):
        """Test with empty string alias."""
        response = client.post(
            "/shorten",
            json={
                "url": "https://example.com/target",
                "alias": "",
            },
        )
        assert response.status_code == 400
        assert "empty" in response.json()["detail"].lower()

    def test_shorten_with_alias_reserved_word(self, client):
        """Test that reserved aliases are rejected."""
        reserved_words = ["shorten", "health", "api", "admin", "stats", "docs"]
        
        for reserved in reserved_words:
            response = client.post(
                "/shorten",
                json={
                    "url": "https://example.com/target",
                    "alias": reserved,
                },
            )
            assert response.status_code == 400
            assert "reserved" in response.json()["detail"].lower()

    def test_shorten_with_alias_taken(self, client):
        """Test that duplicate aliases are rejected with 409."""
        # Create first shortened URL with alias
        response1 = client.post(
            "/shorten",
            json={
                "url": "https://example.com/first",
                "alias": "my-link",
            },
        )
        assert response1.status_code == 201

        # Try to create another with same alias
        response2 = client.post(
            "/shorten",
            json={
                "url": "https://example.com/second",
                "alias": "my-link",
            },
        )
        assert response2.status_code == 409
        assert "taken" in response2.json()["detail"].lower()

    def test_shorten_without_alias_still_works(self, client):
        """Test that omitting alias generates random code (backward compat)."""
        response = client.post(
            "/shorten",
            json={"url": "https://example.com/target"},
        )
        assert response.status_code == 201
        data = response.json()
        assert "code" in data
        assert data["alias"] is None
        assert len(data["code"]) == 6  # Random code length

    def test_shorten_with_null_alias(self, client):
        """Test that explicit null alias generates random code."""
        response = client.post(
            "/shorten",
            json={
                "url": "https://example.com/target",
                "alias": None,
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["alias"] is None
        assert len(data["code"]) == 6

    def test_shorten_with_alias_and_numbers(self, client):
        """Test alias with numbers."""
        response = client.post(
            "/shorten",
            json={
                "url": "https://example.com/target",
                "alias": "link123",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["alias"] == "link123"

    def test_shorten_with_alias_multiple_hyphens(self, client):
        """Test alias with multiple consecutive hyphens."""
        response = client.post(
            "/shorten",
            json={
                "url": "https://example.com/target",
                "alias": "my-super-long-link",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["alias"] == "my-super-long-link"


class TestAliasRedirect:
    """Test redirect and stats with aliases."""

    def test_redirect_using_alias(self, client):
        """Test redirecting using custom alias."""
        # Create shortened URL with alias
        create_response = client.post(
            "/shorten",
            json={
                "url": "https://example.com/target",
                "alias": "my-link",
            },
        )
        assert create_response.status_code == 201

        # Redirect using alias
        response = client.get("/my-link", follow_redirects=False)
        assert response.status_code == 302
        assert response.headers["location"] == "https://example.com/target"

    def test_redirect_still_works_with_random_code(self, client):
        """Test that redirect with random code still works."""
        # Create shortened URL without alias
        create_response = client.post(
            "/shorten",
            json={"url": "https://example.com/target"},
        )
        code = create_response.json()["code"]

        # Redirect using random code
        response = client.get(f"/{code}", follow_redirects=False)
        assert response.status_code == 302
        assert response.headers["location"] == "https://example.com/target"

    def test_stats_with_alias(self, client):
        """Test getting stats using alias."""
        # Create shortened URL with alias
        create_response = client.post(
            "/shorten",
            json={
                "url": "https://example.com/target",
                "alias": "my-link",
            },
        )
        assert create_response.status_code == 201

        # Get stats using alias
        stats_response = client.get("/stats/my-link")
        assert stats_response.status_code == 200
        stats = stats_response.json()
        assert stats["code"] == "my-link"
        assert stats["alias"] == "my-link"
        assert stats["long_url"] == "https://example.com/target"
        assert stats["clicks"] == 0

    def test_stats_includes_alias_field_for_random_code(self, client):
        """Test that stats response includes alias field even for random codes."""
        # Create shortened URL without alias
        create_response = client.post(
            "/shorten",
            json={"url": "https://example.com/target"},
        )
        code = create_response.json()["code"]

        # Get stats
        stats_response = client.get(f"/stats/{code}")
        assert stats_response.status_code == 200
        stats = stats_response.json()
        assert "alias" in stats
        assert stats["alias"] is None

    def test_click_count_increments_with_alias(self, client):
        """Test that click count increments when using alias."""
        # Create shortened URL with alias
        create_response = client.post(
            "/shorten",
            json={
                "url": "https://example.com/target",
                "alias": "my-link",
            },
        )
        assert create_response.status_code == 201

        # Check initial stats
        stats = client.get("/stats/my-link").json()
        assert stats["clicks"] == 0

        # Click via alias
        client.get("/my-link", follow_redirects=False)
        stats = client.get("/stats/my-link").json()
        assert stats["clicks"] == 1

        # Click again
        client.get("/my-link", follow_redirects=False)
        stats = client.get("/stats/my-link").json()
        assert stats["clicks"] == 2

    def test_shorten_response_includes_alias(self, client):
        """Test that shorten response always includes alias field."""
        # With custom alias
        response1 = client.post(
            "/shorten",
            json={
                "url": "https://example.com/first",
                "alias": "link1",
            },
        )
        assert "alias" in response1.json()
        assert response1.json()["alias"] == "link1"

        # Without alias
        response2 = client.post(
            "/shorten",
            json={"url": "https://example.com/second"},
        )
        assert "alias" in response2.json()
        assert response2.json()["alias"] is None


class TestAliasIntegration:
    """Integration tests for aliases with existing functionality."""

    def test_multiple_aliases_different_urls(self, client):
        """Test creating multiple aliases for different URLs."""
        url1 = "https://example.com/path1"
        url2 = "https://example.com/path2"

        response1 = client.post(
            "/shorten",
            json={"url": url1, "alias": "link1"},
        )
        response2 = client.post(
            "/shorten",
            json={"url": url2, "alias": "link2"},
        )

        assert response1.status_code == 201
        assert response2.status_code == 201

        # Both should redirect correctly
        r1 = client.get("/link1", follow_redirects=False)
        r2 = client.get("/link2", follow_redirects=False)

        assert r1.headers["location"] == url1
        assert r2.headers["location"] == url2

    def test_alias_and_random_code_coexist(self, client):
        """Test that aliases and random codes work together."""
        response_with_alias = client.post(
            "/shorten",
            json={
                "url": "https://example.com/with-alias",
                "alias": "my-alias",
            },
        )
        response_random = client.post(
            "/shorten",
            json={"url": "https://example.com/random-code"},
        )

        alias = response_with_alias.json()["code"]
        code = response_random.json()["code"]

        # Both should work
        r1 = client.get(f"/{alias}", follow_redirects=False)
        r2 = client.get(f"/{code}", follow_redirects=False)

        assert r1.status_code == 302
        assert r2.status_code == 302
        assert r1.headers["location"] == "https://example.com/with-alias"
        assert r2.headers["location"] == "https://example.com/random-code"

    def test_alias_case_sensitivity_reserved_check(self, client):
        """Test that reserved word check is case-insensitive."""
        # Lowercase reserved word
        response = client.post(
            "/shorten",
            json={
                "url": "https://example.com/target",
                "alias": "admin",
            },
        )
        assert response.status_code == 400

    def test_short_url_field_reflects_alias(self, client):
        """Test that short_url field contains the alias."""
        response = client.post(
            "/shorten",
            json={
                "url": "https://example.com/target",
                "alias": "my-link",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert "my-link" in data["short_url"]

    def test_same_url_different_aliases(self, client):
        """Test shortening same URL with different aliases."""
        url = "https://example.com/target"

        response1 = client.post(
            "/shorten",
            json={"url": url, "alias": "alias1"},
        )
        response2 = client.post(
            "/shorten",
            json={"url": url, "alias": "alias2"},
        )

        assert response1.status_code == 201
        assert response2.status_code == 201

        # Both aliases should redirect to same URL
        r1 = client.get("/alias1", follow_redirects=False)
        r2 = client.get("/alias2", follow_redirects=False)

        assert r1.headers["location"] == url
        assert r2.headers["location"] == url
