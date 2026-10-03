"""Pydantic schemas for PDF and DOCX resume extraction and document metadata.

IMPORTANT PRIVACY & DATA GOVERNANCE NOTICE:
Extracted resume text contains Personally Identifiable Information (PII) including
candidate names, contact numbers, email addresses, and employment/educational history.
In compliance with project specifications:
- Uploaded resumes must be processed entirely in-memory and NEVER persisted to disk.
- Frontends and consuming clients must not persist extracted text to localStorage,
  sessionStorage, cookies, or remote analytics.
- No AI-generated quality scores or fabricated ratings are produced in this phase.
"""

from typing import List
from pydantic import BaseModel, Field


class PageExtractionMetadata(BaseModel):
    """Extraction metrics and status for an individual document page or segment."""

    page_number: int = Field(..., description="1-indexed page or section number", ge=1)
    character_count: int = Field(..., description="Total characters extracted from this page", ge=0)
    word_count: int = Field(..., description="Total whitespace-delimited words on this page", ge=0)
    has_text: bool = Field(..., description="Whether extractable text was found on this page")


class ResumeExtractionResponse(BaseModel):
    """Structured response containing extracted resume text and document-quality diagnostics."""

    filename: str = Field(..., description="Sanitized original filename of the uploaded document")
    page_count: int = Field(..., description="Total number of pages or segments in the document", ge=1)
    character_count: int = Field(..., description="Total characters extracted across all pages", ge=0)
    word_count: int = Field(..., description="Total words extracted across all pages", ge=0)
    pages: List[PageExtractionMetadata] = Field(
        ..., description="Per-page diagnostic extraction metadata"
    )
    extracted_text: str = Field(
        ...,
        description=(
            "Normalized textual content extracted from the document. "
            "Contains sensitive personal information; clients must not retain after session."
        ),
    )
    is_scanned_or_image_based: bool = Field(
        ...,
        description="True if the document contains little or no selectable text, suggesting scanned images or blank layout.",
    )
    warnings: List[str] = Field(
        default_factory=list,
        description="List of user-readable diagnostic warnings (e.g., insufficient text, probable scan).",
    )
    parser_status: str = Field(
        ...,
        description="Execution status of the extraction pipeline (e.g., 'success', 'warning_scanned_or_empty', 'warning_low_text').",
    )
    parser_engine: str = Field(
        ...,
        description="Underlying parser engine utilized (e.g., 'pdfplumber', 'pypdf', 'python-docx').",
    )
