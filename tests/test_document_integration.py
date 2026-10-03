"""End-to-end integration, cross-format consistency, API contract, and security tests.

Verifies:
1. PDF vs. DOCX cross-format consistency on logically equivalent resumes.
2. Complete public API contract audit across all document ingestion and analysis routes.
3. Security and privacy constraints (sanitized filenames, zero disk persistence, PII safeguards).
"""

import io
import os
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from app.core import settings
from app.main import app
from app.schemas.feedback import ResumeFeedbackResponse
from app.schemas.matcher import JobMatchResponse
from app.schemas.parser import StructuredResumeResponse
from app.schemas.resume import ResumeExtractionResponse
from tests.test_docx_extractor import create_in_memory_docx
from tests.test_pdf_extractor import generate_minimal_text_pdf

client = TestClient(app)


# ---------------------------------------------------------------------------
# Equivalent Fictional Resume Definition
# ---------------------------------------------------------------------------

SHARED_RESUME_LINES = [
    "Alex M. Smith",
    "alex.smith@college.edu | +1 (415) 555-7890 | https://github.com/alexsmith",
    "EDUCATION",
    "B.S. in Software Engineering, State University (Expected May 2026)",
    "PROJECTS",
    "Campus Event Finder | Python, FastAPI, React",
    "- Architected RESTful API backend handling 5,000 daily queries with sub-50ms latency.",
    "- Implemented real-time notifications with WebSockets, boosting weekly active users by 35%.",
    "AI Study Buddy | Python, PyTorch, Docker",
    "- Built collaborative study tool used by over 200 students during final exam week.",
    "- Reduced model inference memory footprint by 40% through quantization.",
    "TECHNICAL SKILLS",
    "Languages: Python, JavaScript, SQL",
    "Frameworks & Tools: React, FastAPI, Docker, Git",
]


# ---------------------------------------------------------------------------
# 1. Cross-Format Consistency Tests (PDF vs. DOCX)
# ---------------------------------------------------------------------------

def test_pdf_vs_docx_cross_format_consistency():
    """Verify that equivalent resumes in PDF and DOCX formats produce consistent downstream results."""
    # A. Generate PDF and DOCX representations of the exact same candidate
    pdf_bytes = generate_minimal_text_pdf(SHARED_RESUME_LINES)
    docx_bytes = create_in_memory_docx(paragraphs=SHARED_RESUME_LINES)

    # B. Extract both via the unified upload endpoint
    pdf_resp = client.post(
        "/api/v1/resumes/extract",
        files={"file": ("alex_resume.pdf", pdf_bytes, "application/pdf")},
    )
    docx_resp = client.post(
        "/api/v1/resumes/extract",
        files={
            "file": (
                "alex_resume.docx",
                docx_bytes,
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
    )

    assert pdf_resp.status_code == 200
    assert docx_resp.status_code == 200

    pdf_data = ResumeExtractionResponse(**pdf_resp.json())
    docx_data = ResumeExtractionResponse(**docx_resp.json())

    # 1. Extracted text presence
    assert len(pdf_data.extracted_text) > 100
    assert len(docx_data.extracted_text) > 100

    # 2. Downstream structured parsing (/analyze-text)
    pdf_parsed = client.post("/api/v1/resumes/analyze-text", json={"text": pdf_data.extracted_text}).json()
    docx_parsed = client.post("/api/v1/resumes/analyze-text", json={"text": docx_data.extracted_text}).json()

    pdf_struct = StructuredResumeResponse(**pdf_parsed)
    docx_struct = StructuredResumeResponse(**docx_parsed)

    # Verify major sections are detected in both
    for sec in ["education", "projects", "skills"]:
        assert sec in pdf_struct.detected_section_keys, f"Missing {sec} in PDF"
        assert sec in docx_struct.detected_section_keys, f"Missing {sec} in DOCX"

    # Verify contact coordinates
    assert pdf_struct.contact_info.email == docx_struct.contact_info.email == "alex.smith@college.edu"
    assert "github.com/alexsmith" in (pdf_struct.contact_info.github_url or "")
    assert "github.com/alexsmith" in (docx_struct.contact_info.github_url or "")

    # Verify canonical skills overlap
    pdf_skills = {s.name for s in pdf_struct.skills}
    docx_skills = {s.name for s in docx_struct.skills}
    common_skills = {"Python", "FastAPI", "React", "Docker", "SQL"}
    assert common_skills.issubset(pdf_skills), f"PDF missing skills: {common_skills - pdf_skills}"
    assert common_skills.issubset(docx_skills), f"DOCX missing skills: {common_skills - docx_skills}"

    # 3. Downstream Feedback Rubric (/feedback)
    pdf_fb_raw = client.post("/api/v1/resumes/feedback", json={"resume_text": pdf_data.extracted_text}).json()
    docx_fb_raw = client.post("/api/v1/resumes/feedback", json={"resume_text": docx_data.extracted_text}).json()

    pdf_fb = ResumeFeedbackResponse(**pdf_fb_raw)
    docx_fb = ResumeFeedbackResponse(**docx_fb_raw)

    # Both must fall into Exemplary / Proficient tiers
    assert pdf_fb.index_label in ["Exemplary", "Proficient"]
    assert docx_fb.index_label in ["Exemplary", "Proficient"]

    # Scores should be within 3 points of each other despite parser layout variances
    assert abs(pdf_fb.total_score - docx_fb.total_score) <= 3.0
    assert 0.0 <= pdf_fb.total_score <= 100.0
    assert 0.0 <= docx_fb.total_score <= 100.0

    # Quantified metrics detected in both
    assert len(pdf_fb.quantified_metrics_detected) >= 2
    assert len(docx_fb.quantified_metrics_detected) >= 2

    # 4. Downstream Job Matching (/match)
    target_jd = (
        "Seeking a Software Engineer intern skilled in Python, FastAPI, Docker, and React. "
        "SQL database knowledge is a plus."
    )
    pdf_match_raw = client.post(
        "/api/v1/resumes/match",
        json={"resume_text": pdf_data.extracted_text, "job_description": target_jd},
    ).json()
    docx_match_raw = client.post(
        "/api/v1/resumes/match",
        json={"resume_text": docx_data.extracted_text, "job_description": target_jd},
    ).json()

    pdf_match = JobMatchResponse(**pdf_match_raw)
    docx_match = JobMatchResponse(**docx_match_raw)

    assert abs(pdf_match.skill_overlap_ratio - docx_match.skill_overlap_ratio) < 0.05
    assert "Python" in pdf_match.matched_skills and "Python" in docx_match.matched_skills
    assert "Docker" in pdf_match.matched_skills and "Docker" in docx_match.matched_skills


# ---------------------------------------------------------------------------
# 2. Public API Contract & Status Code Audit
# ---------------------------------------------------------------------------

def test_api_unsupported_file_extension_rejected():
    """Verify that unsupported extensions (.txt, .rtf, .png) return HTTP 400."""
    for ext, mime in [("resume.txt", "text/plain"), ("resume.rtf", "application/rtf"), ("pic.png", "image/png")]:
        files = {"file": (ext, b"Sample content", mime)}
        resp = client.post("/api/v1/resumes/extract", files=files)
        assert resp.status_code == 400, f"Expected 400 for {ext}, got {resp.status_code}"
        detail = resp.json().get("detail", "").lower()
        assert "invalid file extension" in detail or "only pdf" in detail


def test_api_missing_upload_file_rejected():
    """Verify that missing file payload returns HTTP 422."""
    resp = client.post("/api/v1/resumes/extract")
    assert resp.status_code == 422


def test_api_empty_text_rejections():
    """Verify that empty and whitespace text inputs return HTTP 400 across all analysis routes."""
    endpoints = [
        ("/api/v1/resumes/analyze-text", {"text": "   \n\t  "}),
        ("/api/v1/resumes/match", {"resume_text": "   ", "job_description": "Python job"}),
        ("/api/v1/resumes/match", {"resume_text": "Python resume", "job_description": "   "}),
        ("/api/v1/resumes/feedback", {"resume_text": "   \n  "}),
    ]
    for url, payload in endpoints:
        resp = client.post(url, json=payload)
        assert resp.status_code == 400, f"Expected 400 for {url} with empty input, got {resp.status_code}"
        assert "empty" in resp.json().get("detail", "").lower()


def test_api_oversized_text_rejections():
    """Verify that payloads exceeding 50,000 characters return HTTP 413 or 422."""
    huge_text = "A" * 50001
    endpoints = [
        ("/api/v1/resumes/analyze-text", {"text": huge_text}),
        ("/api/v1/resumes/match", {"resume_text": huge_text, "job_description": "Python developer"}),
        ("/api/v1/resumes/match", {"resume_text": "Python developer", "job_description": huge_text}),
        ("/api/v1/resumes/feedback", {"resume_text": huge_text}),
    ]
    for url, payload in endpoints:
        resp = client.post(url, json=payload)
        assert resp.status_code in (413, 422), f"Expected 413 or 422 for {url} with oversized text, got {resp.status_code}"


def test_api_job_description_zero_skills_fallback():
    """Verify that a job description with zero recognized skills still reports JD supplied and explains fallback."""
    fluff_jd = "Enthusiastic proactive team ninja wanted for exciting synergy leadership opportunities."
    resp = client.post(
        "/api/v1/resumes/feedback",
        json={
            "resume_text": "\n".join(SHARED_RESUME_LINES),
            "job_description": fluff_jd,
        },
    )
    assert resp.status_code == 200
    data = ResumeFeedbackResponse(**resp.json())
    assert data.has_job_description is True
    assert data.job_description_skills_count == 0
    assert data.matched_job_skills == []
    assert data.missing_job_skills == []
    assert any("0 recognized" in s.lower() or "fallback" in s.lower() for s in data.skills_feedback.strengths)


# ---------------------------------------------------------------------------
# 3. Security, Privacy, and In-Memory Handling Audit
# ---------------------------------------------------------------------------

def test_api_path_traversal_filename_sanitization():
    """Verify that path traversal attempts in uploaded filenames are stripped to bare basenames."""
    raw_docx = create_in_memory_docx(paragraphs=["Simple content."])
    malicious_filenames = [
        "../../../../etc/passwd.docx",
        "..\\..\\..\\boot.ini.docx",
        "nested/path/to/resume.docx",
    ]
    for fn in malicious_filenames:
        files = {
            "file": (
                fn,
                raw_docx,
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        }
        resp = client.post("/api/v1/resumes/extract", files=files)
        assert resp.status_code == 200
        extracted_fn = resp.json()["filename"]
        assert "/" not in extracted_fn and "\\" not in extracted_fn
        assert extracted_fn == Path(fn).name


def test_api_ephemeral_in_memory_processing_zero_disk_leak():
    """Verify that document processing never leaves behind temporary files on disk."""
    workspace_root = Path(__file__).resolve().parent.parent
    uploads_dir = workspace_root / "uploads"
    temp_dir = workspace_root / "temp"

    # Count files before
    def count_files(p: Path) -> int:
        return len(list(p.glob("**/*"))) if p.exists() else 0

    before_uploads = count_files(uploads_dir)
    before_temp = count_files(temp_dir)

    # Perform upload
    raw_docx = create_in_memory_docx(paragraphs=SHARED_RESUME_LINES)
    resp = client.post(
        "/api/v1/resumes/extract",
        files={
            "file": (
                "privacy_test.docx",
                raw_docx,
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
    )
    assert resp.status_code == 200

    # Count files after
    after_uploads = count_files(uploads_dir)
    after_temp = count_files(temp_dir)

    assert before_uploads == after_uploads
    assert before_temp == after_temp
