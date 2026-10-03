"""Pydantic schemas and DTOs for request/response validation."""

from app.schemas.feedback import (
    DimensionFeedback,
    QuantifiedMetricEvidence,
    ResumeFeedbackRequest,
    ResumeFeedbackResponse,
)
from app.schemas.health import HealthResponse
from app.schemas.matcher import JobMatchRequest, JobMatchResponse
from app.schemas.parser import (
    ContactInfo,
    ResumeAnalyzeRequest,
    SectionContent,
    SkillEvidence,
    StructuredResumeResponse,
)
from app.schemas.resume import PageExtractionMetadata, ResumeExtractionResponse

__all__ = [
    "HealthResponse",
    "PageExtractionMetadata",
    "ResumeExtractionResponse",
    "ContactInfo",
    "SkillEvidence",
    "SectionContent",
    "ResumeAnalyzeRequest",
    "StructuredResumeResponse",
    "JobMatchRequest",
    "JobMatchResponse",
    "DimensionFeedback",
    "QuantifiedMetricEvidence",
    "ResumeFeedbackRequest",
    "ResumeFeedbackResponse",
]
