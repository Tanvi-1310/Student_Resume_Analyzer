"""API Version 1 endpoints."""

from app.api.v1.resumes import router as resumes_router

__all__ = ["resumes_router"]
