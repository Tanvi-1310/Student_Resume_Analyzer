"""Pydantic schemas for explainable job description matching.

IMPORTANT METHODOLOGY & INTERPRETABILITY NOTICE:
The metrics computed here are baseline lexical comparisons (TF-IDF text similarity
and explicit skill set overlap). They DO NOT represent:
- Hiring probability or applicant qualification.
- An automated decision or black-box ATS score.
- A guarantee of skill possession (keyword absence != lack of ability).
"""

from typing import List, Optional
from pydantic import BaseModel, Field


class JobMatchRequest(BaseModel):
    """Payload for comparing a resume against a target job description."""

    resume_text: str = Field(
        ...,
        description="Plain text extracted from candidate resume document",
        min_length=1,
        max_length=50000,
    )
    job_description: str = Field(
        ...,
        description="Plain text content of the target job description or role requirements",
        min_length=1,
        max_length=50000,
    )
    resume_filename: Optional[str] = Field(
        "resume.pdf",
        description="Original resume filename for tracking",
    )


class JobMatchResponse(BaseModel):
    """Interpretable, dual-signal matching results comparing resume text with job description."""

    resume_filename: str = Field(..., description="Filename associated with analyzed resume")
    text_similarity: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Lexical TF-IDF cosine similarity bounded strictly between 0.0 and 1.0",
    )
    text_similarity_explanation: str = Field(
        ...,
        description="Human-readable explanation of what the lexical TF-IDF metric represents",
    )
    skill_overlap_ratio: Optional[float] = Field(
        None,
        ge=0.0,
        le=1.0,
        description=(
            "Ratio of matched skills to total canonical skills identified in the job description. "
            "Returns null if no canonical skills were detected in the job description."
        ),
    )
    skill_overlap_explanation: str = Field(
        ...,
        description="Explanation of the skill overlap ratio and zero-division handling",
    )
    matched_skills: List[str] = Field(
        default_factory=list,
        description="Canonical skills detected in both the resume and the job description",
    )
    missing_skills: List[str] = Field(
        default_factory=list,
        description="Canonical skills mentioned in the job description but not detected in the resume",
    )
    additional_skills: List[str] = Field(
        default_factory=list,
        description="Canonical skills detected in the resume that were not requested in the job description",
    )
    job_description_skills: List[str] = Field(
        default_factory=list,
        description="All canonical skills identified in the target job description",
    )
    resume_skills: List[str] = Field(
        default_factory=list,
        description="All canonical skills identified in the candidate resume",
    )
    methodology_disclaimer: str = Field(
        ...,
        description="Academic disclaimer highlighting baseline nature and ethical limitations",
    )
