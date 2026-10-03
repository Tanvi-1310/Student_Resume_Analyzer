"""Tests for the PDF ingestion service and /api/v1/resumes/extract endpoint."""

import io
import pytest
from fastapi.testclient import TestClient

from app.core import settings
from app.main import app
from app.services.pdf_extractor import (
    PDFEmptyError,
    PDFExtractorService,
    PDFInvalidSignatureError,
    PDFMalformedError,
    PDFPageLimitExceededError,
)

# TestClient instance
client = TestClient(app)


# ---------------------------------------------------------------------------
# Synthetic in-memory PDF test fixtures
# ---------------------------------------------------------------------------

def generate_minimal_text_pdf(text_lines: list[str]) -> bytes:
    """Generate valid in-memory PDF 1.4 bytes containing specified text lines."""
    stream_content = (
        "BT /F1 12 Tf 16 TL 72 700 Td "
        + " ".join(f"({line}) Tj T*" for line in text_lines)
        + " ET"
    )
    stream_bytes = stream_content.encode("latin1")
    length = len(stream_bytes)
    pdf = f"""%PDF-1.4
1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj
2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj
3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >> endobj
4 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj
5 0 obj << /Length {length} >> stream
{stream_content}
endstream
endobj
xref
0 6
0000000000 65535 f 
0000000009 00000 n 
0000000058 00000 n 
0000000115 00000 n 
0000000244 00000 n 
0000000323 00000 n 
trailer << /Size 6 /Root 1 0 R >>
startxref
500
%%EOF""".encode("latin1")
    return pdf


def generate_blank_pdf(num_pages: int = 1) -> bytes:
    """Generate in-memory PDF containing blank pages (no text layer)."""
    import pypdf

    writer = pypdf.PdfWriter()
    for _ in range(num_pages):
        writer.add_blank_page(width=612, height=792)
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


def generate_multipage_text_pdf(pages_text: list[list[str]]) -> bytes:
    """Generate multi-page in-memory PDF with text on each page."""
    import pypdf

    writer = pypdf.PdfWriter()
    for lines in pages_text:
        single_page_bytes = generate_minimal_text_pdf(lines)
        reader = pypdf.PdfReader(io.BytesIO(single_page_bytes))
        writer.add_page(reader.pages[0])
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# API Endpoint Tests
# ---------------------------------------------------------------------------

def test_valid_text_pdf_extraction_success():
    """Verify that a valid text-based PDF extracts expected content and metadata."""
    sample_text = [
        "Candidate: Alex Johnson",
        "Education: BS in Computer Science",
        "Skills: Python FastAPI Docker PostgreSQL",
        "Projects: Student Resume Analyzer with NLP pipeline",
        "Experience: Software Engineering Intern at Tech Corp building REST APIs",
    ]
    pdf_bytes = generate_minimal_text_pdf(sample_text)

    files = {"file": ("alex_johnson_resume.pdf", pdf_bytes, "application/pdf")}
    response = client.post("/api/v1/resumes/extract", files=files)

    assert response.status_code == 200
    data = response.json()

    assert data["filename"] == "alex_johnson_resume.pdf"
    assert data["page_count"] == 1
    assert data["character_count"] > 100
    assert data["word_count"] > 20
    assert "Alex Johnson" in data["extracted_text"]
    assert "FastAPI" in data["extracted_text"]
    assert data["is_scanned_or_image_based"] is False
    assert len(data["pages"]) == 1
    assert data["pages"][0]["page_number"] == 1
    assert data["pages"][0]["has_text"] is True


def test_empty_upload_rejected():
    """Verify that an empty (0-byte) file upload is rejected with HTTP 400."""
    files = {"file": ("empty.pdf", b"", "application/pdf")}
    response = client.post("/api/v1/resumes/extract", files=files)

    assert response.status_code == 400
    detail = response.json().get("detail", "").lower()
    assert "empty" in detail


def test_non_pdf_extension_rejected():
    """Verify that unsupported file extensions are rejected with HTTP 400."""
    files = {"file": ("resume.txt", b"Plain text resume content", "text/plain")}
    response = client.post("/api/v1/resumes/extract", files=files)

    assert response.status_code == 400
    detail = response.json().get("detail", "").lower()
    assert ".pdf" in detail or "only pdf" in detail


def test_invalid_pdf_signature_rejected():
    """Verify that a file with a .pdf extension but invalid header bytes is rejected."""
    fake_content = b"This is just plain ASCII text masquerading as a PDF file."
    files = {"file": ("fake.pdf", fake_content, "application/pdf")}
    response = client.post("/api/v1/resumes/extract", files=files)

    assert response.status_code == 400
    detail = response.json().get("detail", "").lower()
    assert "signature" in detail or "valid pdf" in detail


def test_malformed_pdf_handled_safely():
    """Verify that damaged or truncated PDF streams are handled safely with HTTP 422."""
    corrupt_bytes = b"%PDF-1.4\n1 0 obj << corrupted data truncated\n%%EOF"
    files = {"file": ("corrupt.pdf", corrupt_bytes, "application/pdf")}
    response = client.post("/api/v1/resumes/extract", files=files)

    assert response.status_code == 422
    detail = response.json().get("detail", "")
    assert isinstance(detail, str)
    assert len(detail) > 0
    # Confirm internal system path is not leaked
    assert "C:\\" not in detail
    assert "/home" not in detail


def test_oversized_upload_rejected():
    """Verify that uploads exceeding MAX_UPLOAD_SIZE_MB are rejected with HTTP 413."""
    max_mb = settings.MAX_UPLOAD_SIZE_MB
    oversized_bytes = b"%PDF-" + b"X" * (max_mb * 1024 * 1024 + 1024)

    files = {"file": ("huge.pdf", oversized_bytes, "application/pdf")}
    response = client.post("/api/v1/resumes/extract", files=files)

    assert response.status_code == 413
    detail = response.json().get("detail", "").lower()
    assert "maximum" in detail or "exceeds" in detail


def test_page_limit_exceeded_rejected():
    """Verify that PDFs exceeding MAX_PAGE_COUNT are rejected with HTTP 400."""
    max_pages = settings.MAX_PAGE_COUNT
    excessive_pdf = generate_blank_pdf(num_pages=max_pages + 1)

    files = {"file": ("too_many_pages.pdf", excessive_pdf, "application/pdf")}
    response = client.post("/api/v1/resumes/extract", files=files)

    assert response.status_code == 400
    detail = response.json().get("detail", "").lower()
    assert "maximum page limit" in detail or "exceeds" in detail


def test_multipage_pdf_metadata():
    """Verify that multi-page PDFs return accurate per-page metadata."""
    p1 = ["Page One Header", "Candidate Profile Overview"]
    p2 = ["Page Two Header", "Certifications and Honors"]
    pdf_bytes = generate_multipage_text_pdf([p1, p2])

    files = {"file": ("two_page_resume.pdf", pdf_bytes, "application/pdf")}
    response = client.post("/api/v1/resumes/extract", files=files)

    assert response.status_code == 200
    data = response.json()
    assert data["page_count"] == 2
    assert len(data["pages"]) == 2
    assert data["pages"][0]["page_number"] == 1
    assert data["pages"][1]["page_number"] == 2
    assert "Page One" in data["extracted_text"]
    assert "Page Two" in data["extracted_text"]


def test_scanned_pdf_produces_warning():
    """Verify that an image-based or blank PDF triggers scanned warning and flag."""
    blank_pdf = generate_blank_pdf(num_pages=1)

    files = {"file": ("scanned_resume.pdf", blank_pdf, "application/pdf")}
    response = client.post("/api/v1/resumes/extract", files=files)

    assert response.status_code == 200
    data = response.json()
    assert data["is_scanned_or_image_based"] is True
    assert data["character_count"] == 0
    assert len(data["warnings"]) >= 1
    warning_text = " ".join(data["warnings"]).lower()
    assert "scanned" in warning_text or "ocr" in warning_text


# ---------------------------------------------------------------------------
# Direct Service Unit Tests
# ---------------------------------------------------------------------------

def test_service_invalid_signature_exception():
    """Verify that PDFExtractorService raises PDFInvalidSignatureError on bad bytes."""
    service = PDFExtractorService()
    with pytest.raises(PDFInvalidSignatureError):
        service.extract_text_from_bytes(b"NOT_A_PDF")


def test_service_empty_bytes_exception():
    """Verify that PDFExtractorService raises PDFEmptyError on empty payload."""
    service = PDFExtractorService()
    with pytest.raises(PDFEmptyError):
        service.extract_text_from_bytes(b"")


def test_service_page_limit_exception():
    """Verify that PDFExtractorService raises PDFPageLimitExceededError."""
    service = PDFExtractorService(max_page_count=2)
    three_page_pdf = generate_blank_pdf(num_pages=3)
    with pytest.raises(PDFPageLimitExceededError):
        service.extract_text_from_bytes(three_page_pdf)
