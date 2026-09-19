import os
import pytest
from fastapi.testclient import TestClient

from shortener.app import app
from shortener import db


@pytest.fixture(autouse=True)
def clean_db():
    """Clean up test database before each test."""
    # Remove existing DB if present
    if os.path.exists(db.DB_PATH):
        os.remove(db.DB_PATH)
    
    # Initialize fresh DB
    db.init_db()
    
    yield
    
    # Cleanup after test
    if os.path.exists(db.DB_PATH):
        os.remove(db.DB_PATH)


@pytest.fixture
def client():
    """Provide a test client for the FastAPI app."""
    return TestClient(app)
