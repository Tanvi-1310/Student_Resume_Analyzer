"""PDF document ingestion and text extraction service.

Responsibilities:
1. Validate PDF binary signature and structural integrity.
2. Enforce page count bounds.
3. Extract textual content on a per-page basis with diagnostic metrics.
4. Detect scanned or image-based documents where text layers are absent.
5. Operate purely in-memory with zero disk persistence to protect candidate privacy.
"""

import io
from typing import List, Tuple

from app.core import settings
from app.schemas.resume import PageExtractionMetadata, ResumeExtractionResponse

# Parser engine imports with fallback capability
try:
    import pdfplumber
    from pdfminer.pdfdocument import PDFEncryptionError, PDFPasswordIncorrect
    from pdfminer.pdfparser import PDFSyntaxError, PSEOF
    HAS_PDFPLUMBER = True
except ImportError:
    HAS_PDFPLUMBER = False

try:
    import pypdf
    from pypdf.errors import FileNotDecryptedError, PdfReadError
    HAS_PYPDF = True
except ImportError:
    HAS_PYPDF = False


class PDFExtractionError(Exception):
    """Base exception for all PDF extraction and parsing failures."""


class PDFEmptyError(PDFExtractionError):
    """Raised when uploaded file payload has 0 bytes."""


class PDFInvalidSignatureError(PDFExtractionError):
    """Raised when file header does not match standard PDF magic bytes."""


class PDFPageLimitExceededError(PDFExtractionError):
    """Raised when document page count exceeds configured system limits."""


class PDFEncryptedError(PDFExtractionError):
    """Raised when PDF is encrypted or password-protected."""


class PDFMalformedError(PDFExtractionError):
    """Raised when PDF stream is damaged, truncated, or unreadable."""


class PDFExtractorService:
    """Service handling in-memory extraction of text and metadata from PDF files."""

    def __init__(
        self,
        max_page_count: int = settings.MAX_PAGE_COUNT,
        min_extracted_chars_warning: int = settings.MIN_EXTRACTED_CHARS_WARNING,
        min_page_chars_scanned: int = settings.MIN_PAGE_CHARS_SCANNED_CHECK,
    ) -> None:
        self.max_page_count = max_page_count
        self.min_extracted_chars_warning = min_extracted_chars_warning
        self.min_page_chars_scanned = min_page_chars_scanned

        if not HAS_PDFPLUMBER and not HAS_PYPDF:
            raise RuntimeError(
                "No compatible PDF extraction engine is installed. "
                "Please install pdfplumber or pypdf."
            )

    def extract_text_from_bytes(
        self,
        pdf_bytes: bytes,
        filename: str = "uploaded_resume.pdf",
    ) -> ResumeExtractionResponse:
        """Extract text and document diagnostics from raw PDF bytes.

        Args:
            pdf_bytes: Raw binary content of the PDF file.
            filename: Original sanitized filename for metadata tracking.

        Returns:
            ResumeExtractionResponse containing extracted text, counts, and diagnostic flags.

        Raises:
            PDFEmptyError: If bytes are empty.
            PDFInvalidSignatureError: If header does not begin with %PDF-.
            PDFPageLimitExceededError: If page count exceeds maximum allowable limit.
            PDFEncryptedError: If document requires password or decryption.
            PDFMalformedError: If document syntax is broken or corrupted.
            PDFExtractionError: For any unhandled document extraction issue.
        """
        # 1. Structural pre-checks
        if not pdf_bytes:
            raise PDFEmptyError("The uploaded file is empty (0 bytes).")

        if not pdf_bytes.startswith(b"%PDF-"):
            raise PDFInvalidSignatureError(
                "Invalid PDF signature. The file does not appear to be a standard PDF document."
            )

        # 2. Parse using primary engine (pdfplumber) or fallback (pypdf)
        if HAS_PDFPLUMBER:
            page_texts, engine_used = self._extract_with_pdfplumber(pdf_bytes)
        else:
            page_texts, engine_used = self._extract_with_pypdf(pdf_bytes)

        page_count = len(page_texts)

        # 3. Page count limit enforcement
        if page_count > self.max_page_count:
            raise PDFPageLimitExceededError(
                f"Document exceeds the maximum page limit of {self.max_page_count} pages "
                f"(received {page_count} pages)."
            )

        # 4. Per-page metadata generation
        pages_metadata: List[PageExtractionMetadata] = []
        cleaned_pages: List[str] = []

        for idx, raw_text in enumerate(page_texts, start=1):
            cleaned = (raw_text or "").strip()
            cleaned_pages.append(cleaned)
            char_count = len(cleaned)
            word_count = len(cleaned.split())
            pages_metadata.append(
                PageExtractionMetadata(
                    page_number=idx,
                    character_count=char_count,
                    word_count=word_count,
                    has_text=char_count > 0,
                )
            )

        # 5. Full document text assembly
        extracted_text = "\n\n".join(p for p in cleaned_pages if p).strip()
        total_characters = len(extracted_text)
        total_words = len(extracted_text.split())

        # 6. Quality diagnostics and scanned-PDF detection
        warnings: List[str] = []
        is_scanned_or_image_based = False

        avg_chars_per_page = total_characters / page_count if page_count > 0 else 0

        if total_characters == 0 or avg_chars_per_page < self.min_page_chars_scanned:
            is_scanned_or_image_based = True
            warnings.append(
                "Document appears to be scanned or image-based with little to no selectable text. "
                "Optical Character Recognition (OCR) is not supported in this version. "
                "Please upload a standard text-based PDF."
            )
        elif total_characters < self.min_extracted_chars_warning:
            warnings.append(
                f"Extracted text volume is unusually low ({total_characters} characters). "
                "The resume may contain non-standard vector containers or incomplete sections."
            )

        # 7. Parser status determination
        if is_scanned_or_image_based:
            parser_status = "warning_scanned_or_empty"
        elif warnings:
            parser_status = "warning_low_text"
        else:
            parser_status = "success"

        return ResumeExtractionResponse(
            filename=filename,
            page_count=page_count,
            character_count=total_characters,
            word_count=total_words,
            pages=pages_metadata,
            extracted_text=extracted_text,
            is_scanned_or_image_based=is_scanned_or_image_based,
            warnings=warnings,
            parser_status=parser_status,
            parser_engine=engine_used,
        )

    def _extract_with_pdfplumber(self, pdf_bytes: bytes) -> Tuple[List[str], str]:
        """Extract pages utilizing pdfplumber."""
        stream = io.BytesIO(pdf_bytes)
        try:
            with pdfplumber.open(stream) as pdf:
                page_texts = []
                for page in pdf.pages:
                    text = page.extract_text() or ""
                    page_texts.append(text)
                return page_texts, "pdfplumber"
        except (PDFPasswordIncorrect, PDFEncryptionError) as exc:
            raise PDFEncryptedError(
                "The PDF document is encrypted or password-protected and cannot be parsed."
            ) from exc
        except (PDFSyntaxError, PSEOF) as exc:
            raise PDFMalformedError(
                "The PDF document is malformed or corrupted."
            ) from exc
        except Exception as exc:
            # Check message indicators for encrypted/syntax errors
            msg = str(exc).lower()
            if "password" in msg or "encrypt" in msg:
                raise PDFEncryptedError(
                    "The PDF document is encrypted or password-protected."
                ) from exc
            if "syntax" in msg or "eof" in msg or "damaged" in msg:
                raise PDFMalformedError(
                    "The PDF document is damaged or malformed."
                ) from exc
            raise PDFExtractionError(
                "An unexpected error occurred during PDF document parsing."
            ) from exc

    def _extract_with_pypdf(self, pdf_bytes: bytes) -> Tuple[List[str], str]:
        """Extract pages utilizing pypdf fallback engine."""
        stream = io.BytesIO(pdf_bytes)
        try:
            reader = pypdf.PdfReader(stream)
            if reader.is_encrypted:
                raise PDFEncryptedError(
                    "The PDF document is encrypted or password-protected."
                )
            page_texts = []
            for page in reader.pages:
                text = page.extract_text() or ""
                page_texts.append(text)
            return page_texts, "pypdf"
        except FileNotDecryptedError as exc:
            raise PDFEncryptedError(
                "The PDF document is encrypted or password-protected."
            ) from exc
        except (PdfReadError, ValueError) as exc:
            raise PDFMalformedError(
                "The PDF document is malformed, truncated, or unreadable."
            ) from exc
        except PDFEncryptedError:
            raise
        except Exception as exc:
            msg = str(exc).lower()
            if "password" in msg or "encrypt" in msg:
                raise PDFEncryptedError(
                    "The PDF document is encrypted or password-protected."
                ) from exc
            raise PDFExtractionError(
                "An unexpected error occurred during PDF document parsing."
            ) from exc


# Default module instance for dependency injection
pdf_extractor_service = PDFExtractorService()
