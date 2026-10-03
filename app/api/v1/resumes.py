"""API endpoints for PDF and DOCX resume ingestion and extraction."""

from pathlib import Path
from fastapi import APIRouter, File, HTTPException, UploadFile, status

from app.core import settings
from app.schemas.feedback import ResumeFeedbackRequest, ResumeFeedbackResponse
from app.schemas.matcher import JobMatchRequest, JobMatchResponse
from app.schemas.parser import ResumeAnalyzeRequest, StructuredResumeResponse
from app.schemas.resume import ResumeExtractionResponse
from app.services.docx_extractor import (
    DocxEmptyError,
    DocxEncryptedError,
    DocxExtractionError,
    DocxInvalidSignatureError,
    DocxMalformedError,
    DocxPageLimitExceededError,
    DocxUnsupportedLegacyDocError,
    docx_extractor_service,
)
from app.services.feedback_analyzer import feedback_analyzer_service
from app.services.job_matcher import job_matcher_service
from app.services.pdf_extractor import (
    PDFEmptyError,
    PDFEncryptedError,
    PDFExtractionError,
    PDFInvalidSignatureError,
    PDFMalformedError,
    PDFPageLimitExceededError,
    pdf_extractor_service,
)
from app.services.resume_parser import resume_parser_service

router = APIRouter(prefix="/resumes", tags=["Resume Ingestion & Analysis"])


@router.post(
    "/extract",
    response_model=ResumeExtractionResponse,
    status_code=status.HTTP_200_OK,
    summary="Extract text and metadata from PDF or Word (.docx) resume",
    description=(
        "Uploads a PDF or Word (.docx) resume, verifies its format and integrity in-memory, "
        "extracts readable text, and returns document-quality metrics. "
        "No files or candidate data are stored to disk."
    ),
)
async def extract_resume_document(
    file: UploadFile = File(..., description="Resume document file: PDF (.pdf) or Word (.docx) (max 5 MB)"),
) -> ResumeExtractionResponse:
    """Validate uploaded PDF or DOCX resume and extract text and quality diagnostics."""
    # 1. Filename & extension validation
    raw_filename = file.filename or "resume.pdf"
    file_ext = Path(raw_filename).suffix.lower()

    if file_ext == ".doc":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Legacy binary Word documents (.doc) are not supported. "
                "Please save or convert your resume to modern Word (.docx) or PDF (.pdf) format."
            ),
        )

    allowed_exts = [f".{ext.lower()}" for ext in settings.ALLOWED_EXTENSIONS]
    if file_ext not in allowed_exts:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid file extension '{file_ext}'. Only PDF (.pdf) and Word (.docx) documents are accepted.",
        )

    # 2. In-memory read with bounded size check
    max_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    try:
        # Read max_bytes + 1 to detect oversized payloads without unbounded memory usage
        contents = await file.read(max_bytes + 1)
        if len(contents) > max_bytes:
            raise HTTPException(
                status_code=getattr(status, "HTTP_413_CONTENT_TOO_LARGE", 413),
                detail=(
                    f"Uploaded file exceeds the maximum allowed size of "
                    f"{settings.MAX_UPLOAD_SIZE_MB} MB."
                ),
            )
        if len(contents) == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Uploaded file is empty (0 bytes).",
            )
    finally:
        await file.close()

    # 3. Document routing and extraction with curated error handling
    sanitized_filename = Path(raw_filename).name
    try:
        if file_ext == ".pdf":
            return pdf_extractor_service.extract_text_from_bytes(
                pdf_bytes=contents,
                filename=sanitized_filename,
            )
        elif file_ext == ".docx":
            return docx_extractor_service.extract_text_from_bytes(
                docx_bytes=contents,
                filename=sanitized_filename,
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported document format: {file_ext}",
            )
    except (
        PDFEmptyError,
        PDFInvalidSignatureError,
        PDFPageLimitExceededError,
        DocxEmptyError,
        DocxInvalidSignatureError,
        DocxUnsupportedLegacyDocError,
        DocxPageLimitExceededError,
    ) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except (
        PDFEncryptedError,
        PDFMalformedError,
        PDFExtractionError,
        DocxEncryptedError,
        DocxMalformedError,
        DocxExtractionError,
    ) as exc:
        raise HTTPException(
            status_code=getattr(status, "HTTP_422_UNPROCESSABLE_CONTENT", 422),
            detail=str(exc),
        ) from exc


@router.post(
    "/analyze-text",
    response_model=StructuredResumeResponse,
    status_code=status.HTTP_200_OK,
    summary="Extract structured sections, contact details, and skills from resume text",
    description=(
        "Converts unformatted resume text into structured sections, "
        "identifies candidate contact details, and extracts canonical technical skills. "
        "Operates purely in memory with zero persistence."
    ),
)
async def analyze_resume_text(
    payload: ResumeAnalyzeRequest,
) -> StructuredResumeResponse:
    """Analyze resume plain text into structured sections, contact info, and skills."""
    cleaned_text = payload.text.strip()
    if not cleaned_text:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Resume text cannot be empty or whitespace-only.",
        )

    if len(payload.text) > 50000:
        raise HTTPException(
            status_code=getattr(status, "HTTP_413_CONTENT_TOO_LARGE", 413),
            detail="Resume text exceeds the maximum allowable length of 50,000 characters.",
        )

    result = resume_parser_service.parse_resume_text(
        text=payload.text,
        filename=payload.filename or "resume.pdf",
    )
    return result


@router.post(
    "/match",
    response_model=JobMatchResponse,
    status_code=status.HTTP_200_OK,
    summary="Compare resume text with target job description",
    description=(
        "Computes two explainable baseline signals: lexical TF-IDF cosine similarity "
        "and canonical technical skill overlap ratio. Operates purely in memory."
    ),
)
async def match_resume_with_job(
    payload: JobMatchRequest,
) -> JobMatchResponse:
    """Compare extracted resume text against a target job description."""
    clean_resume = payload.resume_text.strip()
    if not clean_resume:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Resume text cannot be empty or whitespace-only.",
        )

    clean_jd = payload.job_description.strip()
    if not clean_jd:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Job description cannot be empty or whitespace-only.",
        )

    if len(payload.resume_text) > 50000 or len(payload.job_description) > 50000:
        raise HTTPException(
            status_code=getattr(status, "HTTP_413_CONTENT_TOO_LARGE", 413),
            detail="Payload text exceeds the maximum allowable length of 50,000 characters.",
        )

    result = job_matcher_service.match(
        resume_text=payload.resume_text,
        job_description=payload.job_description,
        resume_filename=payload.resume_filename or "resume.pdf",
    )
    return result


@router.post(
    "/feedback",
    response_model=ResumeFeedbackResponse,
    status_code=status.HTTP_200_OK,
    summary="Generate explainable, rule-based rubric feedback for a resume",
    description=(
        "Evaluates resume text across four transparent heuristic dimensions: "
        "Resume Structure, Contact Completeness, Quantified Impact, and Skill-Taxonomy Coverage. "
        "Provides actionable recommendations and specific evidence deductions. "
        "NOT an ATS score or hiring prediction. Operates purely in memory."
    ),
)
async def generate_resume_feedback(
    payload: ResumeFeedbackRequest,
) -> ResumeFeedbackResponse:
    """Generate deterministic, explainable rubric feedback for resume text."""
    clean_resume = payload.resume_text.strip()
    if not clean_resume:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Resume text cannot be empty or whitespace-only.",
        )

    if len(payload.resume_text) > 50000:
        raise HTTPException(
            status_code=getattr(status, "HTTP_413_CONTENT_TOO_LARGE", 413),
            detail="Resume text exceeds the maximum allowable length of 50,000 characters.",
        )

    if payload.job_description and len(payload.job_description) > 50000:
        raise HTTPException(
            status_code=getattr(status, "HTTP_413_CONTENT_TOO_LARGE", 413),
            detail="Job description exceeds the maximum allowable length of 50,000 characters.",
        )

    result = feedback_analyzer_service.generate_feedback(
        resume_text=payload.resume_text,
        job_description=payload.job_description,
        resume_filename=payload.resume_filename or "resume.pdf",
    )
    return result

