"""API Version 1 endpoints."""

from app.api.v1.evaluation import router as evaluation_router
from app.api.v1.resumes import router as resumes_router

__all__ = ["resumes_router", "evaluation_router"]

