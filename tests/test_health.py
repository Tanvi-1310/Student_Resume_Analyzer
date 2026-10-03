"""Tests for the core application initialization and /health endpoint."""

import sys
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.main import app
from app.schemas import HealthResponse


def test_app_instance():
    """Verify that the FastAPI application initializes cleanly."""
    assert isinstance(app, FastAPI)
    assert app.title == "Student Resume Analyzer"


def test_no_ml_models_loaded_at_startup():
    """Verify that importing and initializing app does not pull in heavy ML modules."""
    forbidden_heavy_modules = [
        "torch",
        "transformers",
        "sentence_transformers",
        "spacy",
    ]
    for module_name in forbidden_heavy_modules:
        assert module_name not in sys.modules, (
            f"Module '{module_name}' was unexpectedly loaded during startup."
        )


def test_health_endpoint_success():
    """Verify that GET /health responds with status code 200."""
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200


def test_health_response_contract():
    """Verify that GET /health JSON response conforms to the HealthResponse contract."""
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "ok"
    assert data["app"] == "Student Resume Analyzer"
    assert "version" in data

    # Schema validation
    validated = HealthResponse(**data)
    assert validated.status == "ok"
    assert validated.app == "Student Resume Analyzer"


def test_frontend_root_served():
    """Verify that GET / returns the HTML landing page."""
    client = TestClient(app)
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers.get("content-type", "")
    assert "Student Resume Analyzer" in response.text
