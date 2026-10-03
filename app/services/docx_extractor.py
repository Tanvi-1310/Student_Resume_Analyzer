"""DOCX document ingestion and text extraction service.

Responsibilities:
1. Validate OpenXML / PKZip binary signature and structural integrity.
2. Reject legacy binary (.doc) files with an informative message.
3. Enforce document page/section limits.
4. Extract text from paragraphs, headings, bullet lists, and tables in document order.
5. Operate purely in-memory with zero disk persistence to protect candidate privacy.
"""

import io
import re
import zipfile
from typing import List, Tuple

import docx
from docx.oxml.table import CT_Tbl
from docx.oxml.text.paragraph import CT_P
from docx.table import Table
from docx.text.paragraph import Paragraph

from app.core import settings
from app.schemas.resume import PageExtractionMetadata, ResumeExtractionResponse


class DocxExtractionError(Exception):
    """Base exception for all DOCX extraction and parsing failures."""


class DocxEmptyError(DocxExtractionError):
    """Raised when uploaded file payload has 0 bytes."""


class DocxInvalidSignatureError(DocxExtractionError):
    """Raised when file header does not match standard OpenXML / PKZip magic bytes."""


class DocxUnsupportedLegacyDocError(DocxExtractionError):
    """Raised when uploaded file is a legacy binary Microsoft Word document (.doc)."""


class DocxPageLimitExceededError(DocxExtractionError):
    """Raised when document page/section count exceeds configured system limits."""


class DocxEncryptedError(DocxExtractionError):
    """Raised when DOCX is encrypted or password-protected."""


class DocxMalformedError(DocxExtractionError):
    """Raised when DOCX package or internal XML stream is damaged, truncated, or unreadable."""


class DocxExtractorService:
    """Service handling in-memory extraction of text and metadata from Word (.docx) files."""

    def __init__(
        self,
        max_page_count: int = settings.MAX_PAGE_COUNT,
        min_extracted_chars_warning: int = settings.MIN_EXTRACTED_CHARS_WARNING,
        min_page_chars_scanned: int = settings.MIN_PAGE_CHARS_SCANNED_CHECK,
    ) -> None:
        self.max_page_count = max_page_count
        self.min_extracted_chars_warning = min_extracted_chars_warning
        self.min_page_chars_scanned = min_page_chars_scanned

    def extract_text_from_bytes(
        self,
        docx_bytes: bytes,
        filename: str = "uploaded_resume.docx",
    ) -> ResumeExtractionResponse:
        """Extract text and document diagnostics from raw Word (.docx) bytes.

        Args:
            docx_bytes: Raw binary content of the DOCX file.
            filename: Original sanitized filename for metadata tracking.

        Returns:
            ResumeExtractionResponse containing extracted text, counts, and diagnostic flags.

        Raises:
            DocxEmptyError: If bytes are empty.
            DocxUnsupportedLegacyDocError: If file has binary .doc OLE signature.
            DocxInvalidSignatureError: If header does not begin with standard ZIP magic bytes.
            DocxEncryptedError: If document requires password or decryption.
            DocxMalformedError: If document structure or internal XML is corrupted.
            DocxPageLimitExceededError: If page count exceeds maximum allowable limit.
            DocxExtractionError: For any unhandled document extraction issue.
        """
        # 1. Structural pre-checks
        if not docx_bytes:
            raise DocxEmptyError("The uploaded file is empty (0 bytes).")

        # Detect legacy binary Word (.doc) Compound File Binary header
        if docx_bytes.startswith(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"):
            # Check if this OLE2 file is an EncryptedPackage (Office encrypted file)
            if b"EncryptedPackage" in docx_bytes or b"EncryptionInfo" in docx_bytes:
                raise DocxEncryptedError(
                    "The Word document is encrypted or password-protected and cannot be parsed."
                )
            raise DocxUnsupportedLegacyDocError(
                "Legacy binary Word documents (.doc) are not supported. "
                "Please save or convert your resume to modern Word (.docx) or PDF (.pdf) format."
            )

        # Standard OpenXML DOCX files are ZIP archives starting with PK\x03\x04
        if not docx_bytes.startswith(b"PK\x03\x04"):
            raise DocxInvalidSignatureError(
                "Invalid DOCX signature. The file does not appear to be a standard Word (.docx) document."
            )

        # 2. Inspect ZIP archive integrity and encryption
        stream = io.BytesIO(docx_bytes)
        try:
            with zipfile.ZipFile(stream, "r") as zf:
                # Check for password-protected entries in zip
                for zinfo in zf.infolist():
                    if zinfo.flag_bits & 0x1:
                        raise DocxEncryptedError(
                            "The Word (.docx) document is encrypted or password-protected and cannot be parsed."
                        )
                # Verify that it looks like an OpenXML document
                namelist = zf.namelist()
                if "word/document.xml" not in namelist and "[Content_Types].xml" not in namelist:
                    raise DocxMalformedError(
                        "The Word (.docx) document is missing essential WordprocessingML parts."
                    )
        except DocxEncryptedError:
            raise
        except (zipfile.BadZipFile, zipfile.LargeZipFile) as exc:
            raise DocxMalformedError(
                "The Word (.docx) document is malformed, truncated, or unreadable."
            ) from exc
        except Exception as exc:
            msg = str(exc).lower()
            if "encrypted" in msg or "password" in msg:
                raise DocxEncryptedError(
                    "The Word (.docx) document is encrypted or password-protected."
                ) from exc
            raise DocxMalformedError(
                "The Word (.docx) document package could not be read."
            ) from exc

        # 3. Parse with python-docx
        stream.seek(0)
        try:
            doc = docx.Document(stream)
        except Exception as exc:
            msg = str(exc).lower()
            if "password" in msg or "encrypt" in msg:
                raise DocxEncryptedError(
                    "The Word (.docx) document is encrypted or password-protected."
                ) from exc
            raise DocxMalformedError(
                "The Word (.docx) document is damaged or cannot be parsed."
            ) from exc

        # 4. Extract blocks preserving document order & page boundaries
        page_segments, page_count = self._extract_document_elements(doc)

        # 5. Page limit enforcement (based on explicit XML breaks and rendered break hints)
        if page_count > self.max_page_count:
            raise DocxPageLimitExceededError(
                f"Document exceeds the maximum page limit of {self.max_page_count} pages "
                f"(detected {page_count} page breaks/segments)."
            )

        # 6. Per-page metadata generation
        pages_metadata: List[PageExtractionMetadata] = []
        cleaned_pages: List[str] = []

        for idx, page_lines in enumerate(page_segments, start=1):
            page_text = "\n".join(page_lines).strip()
            cleaned_pages.append(page_text)
            char_count = len(page_text)
            word_count = len(page_text.split())
            pages_metadata.append(
                PageExtractionMetadata(
                    page_number=idx,
                    character_count=char_count,
                    word_count=word_count,
                    has_text=char_count > 0,
                )
            )

        # 7. Full document text assembly
        extracted_text = "\n\n".join(p for p in cleaned_pages if p).strip()
        total_characters = len(extracted_text)
        total_words = len(extracted_text.split())

        # 8. Diagnostics
        warnings: List[str] = []
        is_scanned_or_image_based = False

        avg_chars_per_page = total_characters / page_count if page_count > 0 else 0

        if total_characters == 0 or avg_chars_per_page < self.min_page_chars_scanned:
            is_scanned_or_image_based = True
            warnings.append(
                "Document appears to be empty or image-based with little to no selectable text. "
                "Optical Character Recognition (OCR) is not supported in this version. "
                "Please upload a standard text-based Word (.docx) resume."
            )
        elif total_characters < self.min_extracted_chars_warning:
            warnings.append(
                f"Extracted text volume is unusually low ({total_characters} characters). "
                "The resume may contain non-standard containers or incomplete sections."
            )

        # 9. Parser status
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
            parser_engine="python-docx",
        )

    def _extract_document_elements(self, doc: docx.Document) -> Tuple[List[List[str]], int]:
        """Extract paragraphs and tables in natural reading order while tracking page breaks.
        
        Technical Note on Word Pagination:
        WordprocessingML (.docx) files do not natively store visual print pagination layout
        unless calculated dynamically by a desktop rendering engine (e.g. Word / LibreOffice).
        In this lightweight Python service, page segmentation is derived from explicit XML page breaks
        (<w:br w:type='page'>) and Word rendered break hints (<w:lastRenderedPageBreak>). Unbroken
        paragraphs without explicit breaks are treated as single-segment content.
        """
        pages: List[List[str]] = [[]]

        # Iterate through body elements in document order
        for child in doc.element.body:
            # Paragraph
            if isinstance(child, CT_P):
                xml_str = child.xml
                # Check for explicit page breaks before or inside paragraph
                if 'w:type="page"' in xml_str or "lastRenderedPageBreak" in xml_str:
                    # If current page already has content, start a new page
                    if pages[-1]:
                        pages.append([])

                p = Paragraph(child, doc)
                text = p.text.strip()
                if text:
                    # Normalize bullet points: if paragraph style indicates a bullet or list,
                    # ensure bullet prefix is retained so downstream parser recognizes it
                    style_name = (p.style.name if p.style else "").lower()
                    if "bullet" in style_name or "list" in style_name:
                        if not text.startswith(("-", "•", "▪", "►", "*")):
                            text = f"- {text}"
                    pages[-1].append(text)

            # Table
            elif isinstance(child, CT_Tbl):
                tbl = Table(child, doc)
                for row in tbl.rows:
                    row_cells = [cell.text.strip() for cell in row.cells if cell.text.strip()]
                    # Deduplicate merged cells that repeat identical text
                    deduped_cells: List[str] = []
                    for c in row_cells:
                        if not deduped_cells or c != deduped_cells[-1]:
                            deduped_cells.append(c)
                    if deduped_cells:
                        pages[-1].append(" | ".join(deduped_cells))

        # Filter out empty trailing pages if any
        if len(pages) > 1 and not pages[-1]:
            pages.pop()

        page_count = max(1, len(pages))
        return pages, page_count


# Singleton service instance
docx_extractor_service = DocxExtractorService()
