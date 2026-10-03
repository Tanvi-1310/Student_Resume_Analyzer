# Student Resume Analyzer — System Architecture

---

## 1. System Overview

The **Student Resume Analyzer** is a modular, privacy-preserving web application and NLP pipeline engineered to assist students and early-career software developers in assessing resume structure, extractability, job-description alignment, and measurable impact.

The application operates entirely **in volatile memory (`io.BytesIO`) with zero disk persistence**. Uploaded candidate resumes, extracted text, and job descriptions are never saved to disk, external databases, cloud storage, or tracking cookies.

---

## 2. Frontend & Backend Architecture

The system follows a lightweight, decoupled client-server architecture:

```
+------------------------------------------------------------------------+
|                          Web Frontend Client                           |
|       (Semantic HTML5, Vanilla JavaScript ES6+, Responsive CSS)        |
+-----------------------------------+------------------------------------+
                                    | HTTP / REST (Multipart & JSON)
+-----------------------------------v------------------------------------+
|                         FastAPI Core Router                            |
|                     (app/main.py, app/api/v1/)                         |
+-----------------------------------+------------------------------------+
                                    |
          +-------------------------+-------------------------+
          |                                                   |
+---------v-------------------------+               +---------v---------+
| Document Ingestion Subsystem      |               | Matching/Feedback |
|   - PDFExtractorService           |               |   - JobMatcher    |
|   - DocxExtractorService          |               |   - Feedback      |
+-----------------+-----------------+               +---------+---------+
                  | (in-memory text)                          ^
+-----------------v-----------------+                         |
| NLP Extraction Subsystem          |                         |
|   - SectionDetector               |-------------------------+
|   - ContactExtractor              |
|   - SkillExtractor & Taxonomy     |
+-----------------------------------+
```

### Frontend Architecture
* **Technology:** Semantic HTML5, Vanilla JavaScript (ES6+), and Vanilla CSS (no heavy frontend frameworks such as React, Vue, or Tailwind).
* **Security & Rendering:** Dynamic resume text and extracted skills are attached exclusively via `document.createElement()` and `.textContent = ...`, preventing Cross-Site Scripting (XSS).
* **State Management:** Fully client-side and ephemeral. The interface resets clean on page reload without residual browser storage.

### Backend Architecture
* **Framework:** **FastAPI** running asynchronously with Uvicorn.
* **Routing & Middleware:** Modular route registration via `APIRouter` with prefix `/api/v1`. Configured CORS middleware restricting origins to local development hosts.
* **Data Contracts:** Enforced via **Pydantic v2** models with strict typing, boundary limits, and descriptive validation errors.

---

## 3. Registered API Route-to-Component Mapping

The application derives its route inventory deterministically from runtime route objects using the canonical inspector [`app/core/route_inspector.py`](file:///c:/Users/patil/Student_Resume_Analyzer/app/core/route_inspector.py).

### Canonical Route Schema & Discovery
* **Canonical Schema:** `RouteInventoryItem(method: str, path: str, name: str | None, source: str | None)`.
* **Framework-Version-Safe Runtime Extraction:** Discovers routes using a framework-version-safe dual strategy:
  1. Inspects directly accessible public route attributes (`path`, `methods`, `name`, `endpoint`) on objects in `app.routes`.
  2. Uses the public OpenAPI paths specification (`app.openapi()["paths"]`) for included router endpoints whose top-level wrapper objects do not expose direct route attributes, safely cross-checked against live runtime route matches (`route.matches(scope)`).
  3. Strictly avoids any private framework internals (such as `_IncludedRouter`, `effective_candidates()`, or `effective_route_contexts`). Where route names or modules cannot be obtained through stable public APIs, they safely default to `None`.
* **Deterministic Filtering Rules:**
  * **Application Routes:** Documentable business endpoints (`/health`, `/api/v1/resumes/*`, `/`) are included.
  * **Framework Documentation Routes:** Excluded by default (`/openapi.json`, `/docs`, `/redoc`, `/docs/oauth2-redirect`); available via `include_docs=True`.
  * **Static File Mounts:** Excluded by default (`/css`, `/js`); available via `include_static=True`.
* **Duplicate Detection:** Enforces unique `(method, path)` identities. Conflicting duplicate registrations raise `DuplicateRouteError` with deterministic diagnostic reporting.
* **Deterministic Sort Order:** Ordered strictly by `(path, method, name)`.

### Registered Application Route Table

The following table reflects the **exact, canonical route inventory** derived at runtime via `get_route_inventory(app)`:

| HTTP Method | Exact Path | Purpose | Primary Backend Component | Request Type | Response Type |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `GET` | `/` | Serves the single-page interactive landing dashboard. | `serve_index` ([`app/main.py`](file:///c:/Users/patil/Student_Resume_Analyzer/app/main.py)) | None (HTTP GET) | `FileResponse` (`text/html`) |
| `POST` | `/api/v1/resumes/analyze-text` | Parses raw resume text into sections, contact coordinates, and canonical skills. | `analyze_resume_text` ([`app/api/v1/resumes.py`](file:///c:/Users/patil/Student_Resume_Analyzer/app/api/v1/resumes.py)) | `application/json` (`ResumeAnalyzeRequest`) | `StructuredResumeResponse` ([`app/schemas/parser.py`](file:///c:/Users/patil/Student_Resume_Analyzer/app/schemas/parser.py)) |
| `POST` | `/api/v1/resumes/extract` | Validates uploaded resume and extracts text and quality diagnostics in-memory. | `extract_resume_document` ([`app/api/v1/resumes.py`](file:///c:/Users/patil/Student_Resume_Analyzer/app/api/v1/resumes.py)) | `multipart/form-data` (`file: UploadFile`) | `ResumeExtractionResponse` ([`app/schemas/resume.py`](file:///c:/Users/patil/Student_Resume_Analyzer/app/schemas/resume.py)) |
| `POST` | `/api/v1/resumes/feedback` | Evaluates text across a 4-dimension heuristic rubric and provides formative recommendations. | `generate_resume_feedback` ([`app/api/v1/resumes.py`](file:///c:/Users/patil/Student_Resume_Analyzer/app/api/v1/resumes.py)) | `application/json` (`ResumeFeedbackRequest`) | `ResumeFeedbackResponse` ([`app/schemas/feedback.py`](file:///c:/Users/patil/Student_Resume_Analyzer/app/schemas/feedback.py)) |
| `POST` | `/api/v1/resumes/match` | Computes TF-IDF cosine similarity and canonical skill overlap against a job description. | `match_resume_with_job` ([`app/api/v1/resumes.py`](file:///c:/Users/patil/Student_Resume_Analyzer/app/api/v1/resumes.py)) | `application/json` (`JobMatchRequest`) | `JobMatchResponse` ([`app/schemas/matcher.py`](file:///c:/Users/patil/Student_Resume_Analyzer/app/schemas/matcher.py)) |
| `GET` | `/health` | Returns operational health, app name, and version. | `health_check` ([`app/main.py`](file:///c:/Users/patil/Student_Resume_Analyzer/app/main.py)) | None (HTTP GET) | `HealthResponse` ([`app/schemas/health.py`](file:///c:/Users/patil/Student_Resume_Analyzer/app/schemas/health.py)) |

*Static asset mounts: `/css` mounted to `frontend/css/`, `/js` mounted to `frontend/js/`.*

---

## 4. Document Ingestion Subsystem

The document ingestion layer (`POST /api/v1/resumes/extract`) enforces uniform validation and quality assessment across all supported formats:

### A. Supported Formats
1. **PDF (`.pdf`):** Supported via [`PDFExtractorService`](file:///c:/Users/patil/Student_Resume_Analyzer/app/services/pdf_extractor.py).
   - Validates `%PDF` magic byte header.
   - Extracts character streams using `pdfplumber` (with `pypdf` fallback).
   - Enforces a maximum document page limit (`MAX_PAGE_COUNT = 10`).
   - Computes per-page character and word statistics.
2. **Word (`.docx`):** Supported via [`DocxExtractorService`](file:///c:/Users/patil/Student_Resume_Analyzer/app/services/docx_extractor.py).
   - Validates ZIP archive magic signature (`PK\x03\x04`) and confirms internal `word/document.xml` parts.
   - Parses document body elements in natural document order: paragraphs, headings, bullet lists, and tables.
   - Tracks explicit page breaks (`<w:br w:type='page'>`) and Word rendered break hints (`<w:lastRenderedPageBreak>`).
   - Enforces maximum document page limit (`MAX_PAGE_COUNT = 10`).

### B. Explicit Non-Support for Legacy Binary Word (`.doc`)
- Binary OLE2 Compound File formats (`.doc`) cannot be parsed reliably across platforms without external proprietary desktop office suites.
- Legacy `.doc` files are trapped at both the file extension and magic byte levels (`\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1`).
- Rejected cleanly with HTTP 400 Bad Request and actionable conversion instructions: *"Legacy binary Word documents (.doc) are not supported. Please save or convert your resume to modern Word (.docx) or PDF (.pdf) format."*

### C. Validation & Safety Guards
- **Streaming Upload Bounds:** Enforces `MAX_UPLOAD_SIZE_MB = 5` via `file.read(max_bytes + 1)`, preventing memory exhaustion.
- **Empty File Protection:** Uploads with 0 bytes are rejected with HTTP 400.
- **Path Traversal Protection:** Input filenames are normalized with `Path(filename).name`.
- **Encrypted Documents:** Password-protected PDFs and encrypted DOCX packages return HTTP 422 Unprocessable Content.
- **Scanned Document Warnings:** Documents with zero or unusually low text density trigger non-blocking diagnostic warnings (`is_scanned_or_image_based = True`).

---

## 5. Resume Analysis & NLP Extraction Subsystem

The extraction pipeline converts unformatted plain text into structured candidate records:

1. **Section Boundary Detection ([`SectionDetector`](file:///c:/Users/patil/Student_Resume_Analyzer/app/services/section_detector.py)):**
   - Matches lines against anchored patterns for 9 standard resume sections: `education`, `experience`, `projects`, `skills`, `certifications`, `summary`, `publications`, `awards`, `volunteer`.
   - Incorporates negative lookahead guards preventing regular sentences or job titles from triggering false section headers.
2. **Contact Extraction ([`ContactExtractor`](file:///c:/Users/patil/Student_Resume_Analyzer/app/services/contact_extractor.py)):**
   - Conservative regular expressions extract RFC-compliant emails, validated phone numbers (requiring 10–13 digits), and professional URLs (LinkedIn, GitHub, Portfolios).
3. **Skill Taxonomy Extraction ([`SkillExtractor`](file:///c:/Users/patil/Student_Resume_Analyzer/app/services/skill_extractor.py)):**
   - Standardized taxonomy of 45+ technical skills categorized into Programming Languages, Frameworks, Libraries, ML/AI, Databases, Cloud & DevOps, and Developer Tools.
   - Word-boundary token matching with negative lookahead guards (e.g. `Java` will not match `JavaScript`; standalone `C` requires isolated word boundaries).
   - Captures contextual evidence snippets from candidate bullets for provenance.

---

## 6. Explainable Job Matching Subsystem

The matching engine ([`JobMatcherService`](file:///c:/Users/patil/Student_Resume_Analyzer/app/services/job_matcher.py)) calculates transparent, dual-signal alignment:

1. **TF-IDF Text Similarity:**
   - Evaluates lexical cosine similarity using scikit-learn's `TfidfVectorizer(ngram_range=(1, 2), stop_words="english")`.
   - Strictly bounded in $[0.0, 1.0]$. Empty or stopword-only inputs evaluate safely to $0.0$.
2. **Canonical Skill Overlap Ratio:**
   - Computes set intersection $S_{\text{matched}} = S_{\text{resume}} \cap S_{\text{jd}}$ divided by total recognized skills in the job description:
     $$\text{Overlap Ratio} = \frac{|S_{\text{matched}}|}{|S_{\text{jd}}|}$$
   - Generates a mutually exclusive 3-way partition: **Matched Skills**, **Missing Skills**, and **Additional Skills**.
   - If the job description contains zero recognized skills ($|S_{\text{jd}}| = 0$), returns `null` with an explanatory fallback message, avoiding division by zero.

---

## 7. Heuristic Resume Feedback Rubric

The feedback engine ([`FeedbackAnalyzerService`](file:///c:/Users/patil/Student_Resume_Analyzer/app/services/feedback_analyzer.py)) scores resumes across four transparent dimensions (25.0 points max each, 100.0 points total):

1. **Resume Structure (25.0 pts):** Evaluates substantive content volume ($\ge 20$ words), dedicated Education section, practical student foundation (Academic/Personal Projects count equivalently to employment), and section segmentation count.
2. **Contact Completeness (25.0 pts):** Validated email (10 pts), phone number (7 pts), professional links (5 pts for $\ge 2$ links, 3 pts for 1 link), and candidate name header (3 pts with title guards).
3. **Quantified Impact (25.0 pts):** Identifies measurable outcomes (percentages, counts, scale multipliers, financial impact) with strict exclusion guards (calendar years, phone numbers, tech versions such as `v2.0x`, course codes such as `CS 101`, and GPA do not count as metrics).
4. **Skill-Taxonomy Coverage (25.0 pts):** Role-specific alignment ($R \times 25.0$) when a target job description is provided, or general taxonomy breadth ($\ge 6$ skills across $\ge 2$ categories) in standalone mode.

> **Academic Notice:** This index is labeled explicitly as **Resume Feedback Index (heuristic)**. It is a formative learning aid, not an ATS score, hiring probability, or prediction of recruitment outcomes.

---

## 8. Offline Evaluation Framework

A reproducible evaluation suite ([`scripts/evaluate_matching.py`](file:///c:/Users/patil/Student_Resume_Analyzer/scripts/evaluate_matching.py)) validates ranking behavior:
- **Grouped Benchmark:** Evaluates 25 candidate–job pairs grouped across **5 shared job descriptions** (5 candidates per job pool) in [`data/evaluation/synthetic_matching_benchmark.json`](file:///c:/Users/patil/Student_Resume_Analyzer/data/evaluation/synthetic_matching_benchmark.json).
- **Ranking Quality Metrics:** Computes Mean NDCG@3 and Within-Group Spearman's $\rho$ within shared query pools. Zero-variance pools are handled with explicit diagnostic skips rather than mathematical errors.
- **Information Extraction Metrics:** Measures micro and macro Precision, Recall, and F1-scores for extracted resume skills, job description skills, and matched intersections.

---

## 9. Privacy, Security, and System Boundaries

* **Zero Disk Persistence:** Volatile in-memory buffers (`io.BytesIO`) ensure candidate privacy. No uploaded documents or extracted text are stored on disk.
* **No Database or ORM:** The application is fully stateless.
* **No Optical Character Recognition (OCR):** Scanned or image-only documents trigger diagnostic warnings rather than unverified OCR text.
* **No Large Language Models (LLMs):** All extraction, matching, and feedback logic is rule-based, deterministic, and fully explainable.
* **No Authentication / Multi-Tenancy:** Designed as an educational engineering prototype.

---

## 10. Technical Limitations

1. **Word Layout Pagination:** DOCX page counting is derived from explicit XML page breaks (`<w:br w:type='page'>`) and rendered break hints (`<w:lastRenderedPageBreak>`). True visual pagination rendered by Microsoft Word's desktop layout engine is not calculated.
2. **Multi-Column PDF Layouts:** Visually styled multi-column resumes may interleave adjacent column lines during text stream extraction.
3. **Vocabulary Mismatches:** Lexical matching cannot associate uncataloged synonyms without explicit ontology aliases.
4. **Context & Negation:** Phrases such as *"no experience with Java"* will extract `"Java"`.
5. **Synthetic Evaluation Scope:** Evaluation metrics demonstrate pipeline behavior against a curated synthetic benchmark; they do not represent real-world recruitment efficacy.
