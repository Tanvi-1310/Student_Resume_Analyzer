"""Pydantic schemas for structured resume section, contact, and skill analysis.

IMPORTANT DATA GOVERNANCE & PRIVACY NOTICE:
Structured resume entities include candidate contact fields and career details.
- All analysis is executed purely in memory.
- No resume entities are persisted to long-term databases or external trackers.
- No AI-generated quality scores or fabricated matching metrics are generated in this phase.
"""

from typing import Dict, List, Optional
from pydantic import BaseModel, Field


class ContactInfo(BaseModel):
    """Extracted candidate contact details."""

    email: Optional[str] = Field(None, description="Candidate email address if found")
    phone: Optional[str] = Field(None, description="Candidate telephone number if found")
    linkedin_url: Optional[str] = Field(None, description="LinkedIn profile URL if found")
    github_url: Optional[str] = Field(None, description="GitHub profile URL if found")
    portfolio_url: Optional[str] = Field(None, description="Personal website or portfolio URL if found")


class SkillEvidence(BaseModel):
    """Extracted technical skill with canonical name, taxonomy category, and evidence snippet."""

    name: str = Field(..., description="Canonical skill name (e.g. 'JavaScript', 'PostgreSQL', 'Python')")
    category: str = Field(..., description="Skill taxonomy category (e.g. 'Programming Languages', 'Databases')")
    matched_alias: str = Field(..., description="The exact token or alias string matched in the text (e.g. 'JS')")
    evidence_snippet: str = Field(..., description="Sentence or line context where the skill was identified")


class SectionContent(BaseModel):
    """Extracted text and structural elements of an identified resume section."""

    section_key: str = Field(..., description="Standardized section identifier (e.g. 'education', 'skills')")
    heading: str = Field(..., description="Original raw heading text from the resume")
    raw_text: str = Field(..., description="Full text content contained within this section")
    bullet_points: List[str] = Field(default_factory=list, description="Extracted bullet points or lines")
    detected_dates: List[str] = Field(default_factory=list, description="Date mentions identified within section")


class ResumeAnalyzeRequest(BaseModel):
    """Request payload for structured text analysis."""

    text: str = Field(
        ...,
        description="Plain text content extracted from resume PDF",
        min_length=1,
        max_length=50000,
    )
    filename: Optional[str] = Field(
        "resume.pdf",
        description="Original document filename for metadata tracking",
    )


class StructuredResumeResponse(BaseModel):
    """Structured response containing detected sections, contact info, and extracted skills."""

    filename: str = Field(..., description="Filename associated with this analysis")
    contact_info: ContactInfo = Field(..., description="Extracted contact coordinates")
    detected_sections: Dict[str, SectionContent] = Field(
        ..., description="Map of detected section keys to their structured contents"
    )
    detected_section_keys: List[str] = Field(
        ..., description="List of standardized section keys successfully detected"
    )
    missing_standard_sections: List[str] = Field(
        ..., description="Standard sections not detected in the resume"
    )
    skills: List[SkillEvidence] = Field(
        default_factory=list, description="List of canonical technical skills with evidence"
    )
    skills_by_category: Dict[str, List[str]] = Field(
        default_factory=dict, description="Canonical skill names grouped by category"
    )
    warnings: List[str] = Field(
        default_factory=list, description="Diagnostic warnings regarding missing sections or ambiguous data"
    )
    parser_notes: List[str] = Field(
        default_factory=list, description="Informational processing notes"
    )
