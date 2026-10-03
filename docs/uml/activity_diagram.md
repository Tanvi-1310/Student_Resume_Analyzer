# Student Resume Analyzer — Activity Diagram

## Purpose
This activity diagram models the end-to-end processing pipeline from initial document upload through format-specific extraction, input validation, error handling, structured resume parsing, optional job-description matching, and feedback generation. It reflects the exact control flow, validation gates, and error response branches implemented in the system.

---

## Diagram

```mermaid
flowchart TD
    Start([Start]) --> Upload[User Uploads Document via Web Client]

    %% Validation Gates
    Upload --> SizeCheck{File Size <= 5 MB?}
    SizeCheck -->|No| RejectSize[HTTP 413: Content Too Large\n'Uploaded file exceeds maximum allowed size']
    RejectSize --> EndFail([End: Display Error])

    SizeCheck -->|Yes| EmptyCheck{File Bytes > 0?}
    EmptyCheck -->|No| RejectEmpty[HTTP 400: Bad Request\n'Uploaded file is empty (0 bytes)']
    RejectEmpty --> EndFail

    EmptyCheck -->|Yes| ExtCheck{File Extension?}
    ExtCheck -->|.doc| RejectLegacyDoc[HTTP 400: Bad Request\n'Legacy binary Word .doc not supported; convert to .docx or .pdf']
    RejectLegacyDoc --> EndFail

    ExtCheck -->|Other Invalid| RejectExt[HTTP 400: Bad Request\n'Invalid file extension; only .pdf and .docx accepted']
    RejectExt --> EndFail

    ExtCheck -->|.pdf or .docx| FormatBranch{Document Format?}

    %% PDF Extraction Branch
    FormatBranch -->|.pdf| ValidatePdfSig{Valid %PDF Header?}
    ValidatePdfSig -->|No| RejectPdfSig[HTTP 400: Invalid PDF Signature]
    RejectPdfSig --> EndFail

    ValidatePdfSig -->|Yes| PdfEncrypted{PDF Encrypted?}
    PdfEncrypted -->|Yes| RejectPdfEnc[HTTP 422: Password-Protected PDF]
    RejectPdfEnc --> EndFail

    PdfEncrypted -->|No| PdfPageCheck{Page Count <= 10?}
    PdfPageCheck -->|No| RejectPdfPage[HTTP 400: Page Limit Exceeded]
    RejectPdfPage --> EndFail

    PdfPageCheck -->|Yes| ExtractPdf[Extract Text via pdfplumber / pypdf in-memory]

    %% DOCX Extraction Branch
    FormatBranch -->|.docx| ValidateDocxSig{Valid PK Zip Header?}
    ValidateDocxSig -->|No| RejectDocxSig[HTTP 400: Invalid DOCX Signature]
    RejectDocxSig --> EndFail

    ValidateDocxSig -->|Yes| DocxEncrypted{DOCX Encrypted?}
    DocxEncrypted -->|Yes| RejectDocxEnc[HTTP 422: Password-Protected DOCX]
    RejectDocxEnc --> EndFail

    DocxEncrypted -->|No| DocxPageCheck{Explicit Page Breaks <= 10?}
    DocxPageCheck -->|No| RejectDocxPage[HTTP 400: Page Limit Exceeded]
    RejectDocxPage --> EndFail

    DocxPageCheck -->|Yes| ExtractDocx[Extract Paragraphs, Bullets, Tables via python-docx in-memory]

    %% Merge Extraction Outputs
    ExtractPdf --> TextAssess{Extracted Text Volume?}
    ExtractDocx --> TextAssess

    TextAssess -->|0 Chars or Scanned| ScannedWarn[Set Flag: is_scanned_or_image_based = True\nAdd Quality Warning to Response]
    TextAssess -->|Low Volume < 100 chars| LowWarn[Add Low-Text Warning to Response]
    TextAssess -->|Sufficient Text| CleanExtract[Extraction Status: Success]

    ScannedWarn --> ReturnExtraction[Return ResumeExtractionResponse]
    LowWarn --> ReturnExtraction
    CleanExtract --> ReturnExtraction

    %% Downstream Processing
    ReturnExtraction --> ParseResume[Parse Resume Text via POST /api/v1/resumes/analyze-text]
    ParseResume --> DetectSections[Detect Section Boundaries & Hierarchy]
    DetectSections --> ExtractContacts[Extract Email, Phone, Links]
    ExtractContacts --> MatchSkills[Extract Canonical Skills & Evidence Snippets]

    MatchSkills --> JdProvided{Target Job Description Provided?}
    
    JdProvided -->|Yes| MatchJob[POST /api/v1/resumes/match\nCompute TF-IDF Similarity & Skill Overlap Ratio]
    JdProvided -->|No| SkipMatch[Skip Job Matching Step]

    MatchJob --> GenerateFeedback[POST /api/v1/resumes/feedback\nEvaluate 4 Rubric Dimensions: Structure, Contacts, Impact, Skills]
    SkipMatch --> GenerateFeedback

    GenerateFeedback --> RenderDashboard[Render Interactive Results on Frontend Dashboard]
    RenderDashboard --> EndSuccess([End: Display Results])
```

---

## Explanation of Workflow Stages

1. **Upload & Pre-flight Inspection:** The client submits a file to `POST /api/v1/resumes/extract`. Bounded reading streams up to 5 MB + 1 byte into memory (`io.BytesIO`), safely enforcing payload size limits and empty file checks.
2. **Format-Specific Validation:**
   - **PDF:** Checks for `%PDF` magic bytes, tests for encryption/password locks, enforces $\le 10$ pages, and extracts character streams.
   - **DOCX:** Validates ZIP `PK\x03\x04` header, tests for password-protected OpenXML parts, checks explicit page breaks, and traverses paragraphs, bullets, and tables in document order.
3. **Quality Assessment:** Character density heuristics flag scanned/image-based documents without optical character recognition (OCR), returning clear diagnostics without crashing.
4. **Structured Parsing (`POST /api/v1/resumes/analyze-text`):** Identifies sections (Education, Experience, Projects, Skills), extracts validated contact info, and matches skills with negative lookahead safeguards.
5. **Job Description Matching (`POST /api/v1/resumes/match`):** When a job description is provided, calculates TF-IDF cosine similarity and partitions skills into Matched, Missing, and Additional sets.
6. **Formative Feedback (`POST /api/v1/resumes/feedback`):** Calculates rule-based scores across four dimensions with strict exclusion guards on quantified metrics.
