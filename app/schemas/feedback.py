"""Pydantic schemas for the explainable, rule-based resume feedback rubric.

IMPORTANT ETHICAL & ACADEMIC DISCLAIMER:
This rubric is an explainable resume-improvement aid. It is:
- NOT a validated ATS score.
- NOT a hiring probability or candidate qualification rating.
- NOT an employability score or prediction of interview outcomes.
Scores represent heuristic rule compliance across four transparent dimensions.
"""

from typing import List, Optional
from pydantic import BaseModel, Field


class DimensionFeedback(BaseModel):
    """Evaluation feedback and scoring for an individual rubric dimension."""

    dimension_name: str = Field(..., description="Name of the rubric dimension")
    score: float = Field(..., ge=0.0, description="Points awarded for this dimension")
    max_score: float = Field(..., ge=0.0, description="Maximum possible points for this dimension")
    percentage: float = Field(..., ge=0.0, le=100.0, description="Score as a percentage of max points")
    status: str = Field(..., description="Qualitative status (e.g. 'Strong', 'Proficient', 'Needs Attention')")
    summary: str = Field(..., description="Concise summary of findings for this dimension")
    strengths: List[str] = Field(default_factory=list, description="Positive evidence detected")
    deductions: List[str] = Field(default_factory=list, description="Reasons for point deductions")
    suggestions: List[str] = Field(default_factory=list, description="Actionable recommendations for improvement")


class QuantifiedMetricEvidence(BaseModel):
    """Evidence snippet and detected token of a recognized quantified achievement."""

    metric_type: str = Field(..., description="Type of metric detected: percentage, multiplier, scale_count, currency, duration")
    matched_token: str = Field(..., description="Exact numerical or unit token recognized")
    bullet_snippet: str = Field(..., description="Containing bullet point or sentence context")


class ResumeFeedbackRequest(BaseModel):
    """Payload for requesting heuristic resume feedback."""

    resume_text: str = Field(
        ...,
        min_length=1,
        max_length=50000,
        description="Plain text content extracted from candidate resume document",
    )
    job_description: Optional[str] = Field(
        None,
        max_length=50000,
        description="Optional target job description to evaluate role-specific skill alignment",
    )
    resume_filename: Optional[str] = Field(
        "resume.pdf",
        description="Original document filename for tracking",
    )


class ResumeFeedbackResponse(BaseModel):
    """Structured response containing four-dimension heuristic rubric feedback."""

    resume_filename: str = Field(..., description="Filename associated with evaluated resume")
    total_score: float = Field(..., ge=0.0, le=100.0, description="Total heuristic score out of 100")
    total_max_score: float = Field(100.0, description="Maximum possible index score")
    total_percentage: float = Field(..., ge=0.0, le=100.0, description="Total score percentage")
    index_label: str = Field(..., description="Heuristic performance tier: Developing, Proficient, Strong, Exemplary")
    
    # Four separate rubric dimensions
    structure_feedback: DimensionFeedback = Field(..., description="Evaluation of document hierarchy, headings, and student-relevant sections")
    contact_feedback: DimensionFeedback = Field(..., description="Evaluation of email, phone, links, and header layout")
    impact_feedback: DimensionFeedback = Field(..., description="Evaluation of concrete quantified metrics in experience and projects")
    skills_feedback: DimensionFeedback = Field(..., description="Evaluation of taxonomy coverage or role-specific alignment")
    
    # Specific evidence
    quantified_metrics_detected: List[QuantifiedMetricEvidence] = Field(
        default_factory=list,
        description="List of verified quantified metrics detected in project and experience bullets",
    )
    prioritized_recommendations: List[str] = Field(
        default_factory=list,
        description="Ranked list of highest-priority actionable recommendations for the candidate",
    )
    
    # Detected resume skills
    detected_resume_skills: List[str] = Field(
        default_factory=list,
        description="Canonical technical skills detected on the candidate resume",
    )
    
    # Job-specific context
    has_job_description: bool = Field(..., description="Whether a job description was supplied for role-specific alignment")
    job_description_skills_count: Optional[int] = Field(None, description="Number of recognized skills in job description if supplied")
    matched_job_skills: Optional[List[str]] = Field(None, description="Skills matched against job description if supplied")
    missing_job_skills: Optional[List[str]] = Field(None, description="Target job skills not detected on resume if supplied")
    
    methodology_disclaimer: str = Field(
        ...,
        description="Academic disclaimer highlighting heuristic nature and ethical boundaries",
    )
