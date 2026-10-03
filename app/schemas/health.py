"""Health check response schemas."""

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """Schema representing the health status response."""

    status: str = Field(..., description="Operational status of the service", examples=["ok"])
    app: str = Field(..., description="Name of the application", examples=["Student Resume Analyzer"])
    version: str = Field(..., description="Semantic version of the application", examples=["0.1.0"])
