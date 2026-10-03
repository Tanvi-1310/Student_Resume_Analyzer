# Student Resume Analyzer

[![Python Version](https://img.shields.io/badge/python-3.11%20%7C%203.12%20%7C%203.13-blue.svg)](https://www.python.org/)
[![Framework](https://img.shields.io/badge/framework-FastAPI-green.svg)](https://fastapi.tiangolo.com/)
[![Project Status](https://img.shields.io/badge/status-Release%20Ready%20%7C%20Audited-brightgreen.svg)](#implementation-status)
[![Tests](https://img.shields.io/badge/tests-141%20passed-success.svg)](#running-tests)

An academically defensible, modular system designed for student resume structure evaluation, Applicant Tracking System (ATS) compatibility analysis, explainable job description alignment, and reproducible within-job ranking evaluation.

---

## 1. Project Purpose and Scope

In academic and entry-level career transitions, student resumes frequently encounter ATS filtering hurdles due to non-standard section headers, missing quantifiable impact metrics, unextractable multi-column layouts, and vocabulary mismatches with job descriptions.

The **Student Resume Analyzer** addresses these challenges by providing:
1. **Multi-Format Document Ingestion:** Robust, in-memory text and structure extraction for both **PDF (`.pdf`)** and **Word (`.docx`)** documents with strict validation.
2. **Structural & Format Verification:** Inspecting document hierarchy, contact entity presence, and parseability.
3. **Taxonomy-Grounded Skill Extraction:** Identifying candidate skills mapped against standardized ontologies (e.g., ESCO, O*NET) rather than brittle substring matching.
4. **Transparent Job Description Matching:** Providing separate, interpretable signals (TF-IDF text similarity and canonical skill overlap) without unvalidated black-box scores.
5. **Valid Within-Job Grouped Ranking:** Evaluating ranking quality (NDCG@K and Spearman's $\rho$) within shared job pools where candidates compete for the same role.
6. **Explainable 4-Dimension Feedback Rubric:** Formative scoring across Structure, Contact Completeness, Quantified Impact (with strict exclusion guards), and Skill-Taxonomy Coverage.
7. **Academic Explainability:** Explicitly qualifying that lexical absence is not proof of missing ability, and distinguishing heuristic improvement rubrics from hiring probabilities.

---

## 2. Implementation Status

| Milestone / Phase | Status | Description |
| :--- | :--- | :--- |
| **Phase 1: Repository Audit** | **Completed** | Clean read-only audit of environment and git status. |
| **Phase 2: Project Scaffold** | **Completed** | Modular package structure, config, health endpoint, basic shell UI, and unit tests. |
| **Phase 3: Document Ingestion** | **Completed** | Multi-page in-memory PDF text extraction (`POST /api/v1/resumes/extract`), structure validation, scanned-PDF detection, and test suite. |
| **Phase 4: Section & Entity Parsing** | **Completed** | Master structured resume parser (`POST /api/v1/resumes/analyze-text`), section boundary detection, contact coordinates, and canonical skill taxonomy matching. |
| **Phase 5: Explainable Job Matching** | **Completed** | Dual-signal baseline matcher (`POST /api/v1/resumes/match`), unigram+bigram TF-IDF cosine similarity, canonical skill overlap ratio, zero-division safeguard, and 3-way skill partition. |
| **Phase 6: Reproducible Evaluation Framework** | **Completed** | Standalone evaluation runner (`scripts/evaluate_matching.py`), synthetic benchmark fixture, micro/macro skill extraction metrics, and contract regression tests. |
| **Phase 7: Grouped Within-Job Ranking & Semantic Baselines** | **Completed** | Valid within-job ranking evaluation across 5 job groups (25 pairs), Mean Grouped NDCG@3, Mean Within-Group Spearman $\rho$ with explicit skip diagnostics, optional Sentence-Transformer embedding baseline adapter (`--include-embeddings`). |
| **Phase 8: Explainable Resume Feedback Rubric** | **Completed** | Formative 4-dimension heuristic rubric (`POST /api/v1/resumes/feedback`), conservative metric detection with exclusion guards against dates/versions/GPA, student project equivalence, frontend feedback view. |
| **Phase 9: Reliability Audit & Scoring Verification** | **Completed** | Additive contact point reconciliation (Alex Smith 98/100, 1-link partial credit), name candidate header guards, metric token normalization, mutually exclusive skill partitions, and zero-skill JD fallback. |
| **Phase 10: E2E Integration, DOCX Support & Security Audit** | **Completed** | Full support for Word (`.docx`) resumes alongside PDF, legacy binary `.doc` rejection with conversion guidance, cross-format consistency tests, security/privacy audit. |
| **Phase 11: UML Architecture & Canonical Route Inspection** | **Completed** | Academic UML diagrams (5 deliverables), canonical fail-closed runtime route inventory (`RouteInventoryItem`), zero-private-internals enforcement. |
| **Phase 12: Final Repository Hygiene & Commit Readiness** | **Completed (Current)** | Complete repository audit, stale documentation reconciliation, single canonical route source, and 141 passing tests. |

> **Privacy & Security Guarantee:** Uploaded resumes and job descriptions are processed strictly in volatile memory. No documents, candidate text, or personal coordinates are persisted to disk, databases, cookies, or browser storage. External AI APIs and pretrained weight downloads are not invoked during standard use.

---

## 3. System Design & UML Architecture

The project adheres to a modular, decoupled client-server architecture designed for college software engineering defense and viva presentation. Document processing is completely stateless and executes in volatile memory buffers (`io.BytesIO`) with zero disk persistence.

### Architectural Overview Diagram

```
+------------------------------------------------------------------------+
|                           Frontend Client                              |
|   (Semantic HTML5, Responsive CSS, Vanilla JS In-Memory Dashboard)     |
+-----------------------------------+------------------------------------+
                                    | HTTP / JSON & Multipart
+-----------------------------------v------------------------------------+
|                         FastAPI Core Router                            |
|             (app/main.py, app/api/v1/resumes.py, app/schemas/)         |
+-----------------------------------+------------------------------------+
                                    |
          +-------------------------+-------------------------+
          |                                                   |
+---------v-------------------------+               +---------v---------+
| Document Ingestion Layer          |               |   Job Matcher     |
| (PDF & DOCX Extractor Services)   |               | (JobMatcherService|
|   - PDF: pdfplumber / pypdf       |               |   - TF-IDF Cosine |
|   - DOCX: python-docx OpenXML     |               |   - Skill Overlap |
|   - Legacy .doc rejection guard   |               +---------+---------+
|   - Scanned / empty check         |                         ^
+---------+-------------------------+                         |
          |                                                   |
+---------v---------+                                         |
| NLP Extraction    |                                         |
| (ResumeParser)    |-----------------------------------------+
|   - Contact Regex |
|   - Skill Taxonomy| (Programming, Frameworks, ML/AI, Databases, Cloud)
+-------------------+
          |
          | Offline Verification & Within-Job Group Evaluation
+---------v--------------------------------------------------------------+
| Evaluation Engine (scripts/evaluate_matching.py)                       |
|   - Grouped Benchmark (data/evaluation/synthetic_matching_benchmark.json)|
|   - 5 Job Groups x 5 Candidates (25 candidate–job pairs)               |
|   - Skill Extraction Metrics (Micro/Macro Precision, Recall, F1)       |
|   - Within-Job Ranking (Mean Grouped NDCG@3, Within-Group Spearman Rho)|
|   - Optional Semantic Embedding Baseline (all-MiniLM-L6-v2)            |
+------------------------------------------------------------------------+
```

### UML Diagrams & System Design Specifications

Complete architectural documentation and five UML diagrams modeled in Mermaid Markdown are maintained under `docs/`:

* **System Architecture Specification:** [`docs/architecture.md`](docs/architecture.md) — Comprehensive technical architecture, route-to-component mappings, and system constraints.
* **1. Use Case Diagram:** [`docs/uml/use_case_diagram.md`](docs/uml/use_case_diagram.md) — Student/candidate user interactions, document ingestion, skill viewing, job matching, and feedback generation.
* **2. Activity Diagram:** [`docs/uml/activity_diagram.md`](docs/uml/activity_diagram.md) — End-to-end processing pipeline, format branching, validation gates, error rejections, and feedback calculation.
* **3. Sequence Diagram:** [`docs/uml/sequence_diagram.md`](docs/uml/sequence_diagram.md) — Chronological message flow across Frontend, FastAPI, PDF/DOCX Extractors, Parser, Matcher, and Rubric Services using verbatim API paths.
* **4. Class Diagram:** [`docs/uml/class_diagram.md`](docs/uml/class_diagram.md) — Object-oriented domain model, configuration, extraction services, parser delegates, and Pydantic schemas.
* **5. Component Diagram:** [`docs/uml/component_diagram.md`](docs/uml/component_diagram.md) — Subsystem decomposition (Client, API, Document Ingestion, NLP Parsing, Scoring, and Offline Evaluation).

### Architecture Summary (College Viva Reference)
1. **Decoupled Modularity:** Clear separation between presentation (Vanilla JS single-page app), API routing (FastAPI asynchronous routes), in-memory document ingestion, NLP information extraction, and offline evaluation.
2. **Privacy-Preserving Ephemeral Design:** Resumes are processed strictly in volatile memory (`io.BytesIO`). No candidate documents, extracted text, or PII coordinates are written to disk, databases, or cookies.
3. **Dual Document Support & Clean Rejection:** Modern text-based PDF (`pdfplumber`/`pypdf`) and Word (`python-docx`) are fully supported. Legacy binary `.doc` files are rejected cleanly at extension and signature levels with HTTP 400 conversion guidance.
4. **Explainable Alignment vs. Black-Box Claims:** Features separate, interpretable signals (TF-IDF cosine similarity and canonical skill overlap ratio) and a 4-dimension formative rubric, explicitly disclaiming unvalidated "ATS scores" or hiring predictions.

---

## 4. Setup Instructions (Windows PowerShell)

### Prerequisites
* Windows 10/11 with **PowerShell**
* **Python 3.11**, **Python 3.12**, or **Python 3.13** installed.

### Step 1: Clone and Navigate to Repository
```powershell
git clone https://github.com/Tanvi-1310/Student_Resume_Analyzer.git
cd Student_Resume_Analyzer
```

### Step 2: Create and Activate Virtual Environment
```powershell
# Create virtual environment
python -m venv venv

# Activate virtual environment in PowerShell
.\venv\Scripts\Activate.ps1
```
*(If PowerShell restricts script execution, run `Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned` prior to activation).*

### Step 3: Configure Environment Variables
```powershell
Copy-Item .env.example .env
```

### Step 4: Install Dependencies

**Standard Core Installation (FastAPI, scikit-learn, pypdf, pytest):**
```powershell
pip install --upgrade pip
pip install -r requirements.txt
```

**Optional Semantic Embedding Dependencies (Sentence-Transformers & PyTorch):**
*(Only required if running the optional `--include-embeddings` evaluation command)*
```powershell
pip install sentence-transformers torch
```

---

## 5. Running the Application

Start the local development server using Uvicorn:

```powershell
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Once running, access:
* **Interactive Frontend:** [http://127.0.0.1:8000/](http://127.0.0.1:8000/)
* **System Health Check:** [http://127.0.0.1:8000/health](http://127.0.0.1:8000/health)
* **Interactive API Documentation (Swagger/OpenAPI):** [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
* **Alternative API Documentation (ReDoc):** [http://127.0.0.1:8000/redoc](http://127.0.0.1:8000/redoc)

---

## 6. Endpoints & Matching Methodology

### Endpoints Overview

The application exposes the following canonical, runtime-derived endpoints (inspected via [`app/core/route_inspector.py`](app/core/route_inspector.py)):

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/` | Serves the interactive landing dashboard (`frontend/index.html`). |
| `POST` | `/api/v1/resumes/analyze-text` | Structured parsing (contacts, sections, canonical skills with evidence). |
| `POST` | `/api/v1/resumes/extract` | Multipart PDF (`.pdf`) or Word (`.docx`) upload with in-memory text and quality diagnostics. |
| `POST` | `/api/v1/resumes/feedback` | Explainable 4-dimension heuristic feedback rubric with actionable suggestions. |
| `POST` | `/api/v1/resumes/match` | Explainable job description matching (TF-IDF similarity + skill overlap). |
| `GET` | `/health` | Application status, version, and environment. |


---

### Document Ingestion & Validation Contract

The document ingestion layer (`POST /api/v1/resumes/extract`) enforces a strict, consistent contract for all uploaded files:

* **Supported Formats:**
  * **PDF (`.pdf`):** Processed via `pdfplumber` (with `pypdf` fallback). Magic byte header validation (`%PDF`).
  * **Word (`.docx`):** Modern Office OpenXML documents processed via `python-docx`. Magic byte validation (`PK\x03\x04`). Document order is strictly preserved across headings, paragraphs, bullet lists, and tables.
* **Explicit Non-Support for Legacy Word (`.doc`):**
  * Binary OLE2 Compound File formats (`.doc`) are trapped at both extension and signature levels (`\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1`).
  * Rejected cleanly with HTTP 400 Bad Request: *"Legacy binary Word documents (.doc) are not supported. Please save or convert your resume to modern Word (.docx) or PDF (.pdf) format."*
* **Limits & Thresholds:**
  * **File Size:** Enforces `MAX_UPLOAD_SIZE_MB = 5` via bounded streaming (`max_bytes + 1` read limit) returning HTTP 413 Payload Too Large.
  * **Page Count:** Enforces `MAX_PAGES = 10` returning HTTP 400 Bad Request.
  * **Empty Payload:** 0-byte uploads return HTTP 400 Bad Request.
  * **Encrypted Documents:** Password-protected PDFs and encrypted DOCX packages return HTTP 422 Unprocessable Entity.
  * **Scanned/Low-Text Quality:** Returns `extracted_text` with non-blocking warnings when extracted text density is low (e.g., scanned images without OCR).
* **Privacy & Ephemeral Processing:**
  * Resumes are read entirely into ephemeral memory buffers (`io.BytesIO`).
  * **Zero disk persistence:** No files, temporary files, caches, or candidate PII are written to disk.
  * Sanitized filename handling prevents path traversal vulnerabilities.

---

### Mathematical Formulations

#### 1. TF-IDF Text Cosine Similarity
Using `scikit-learn`'s `TfidfVectorizer(ngram_range=(1, 2), stop_words="english")` fitted on the compared document pair $[d_{\text{resume}}, d_{\text{jd}}]$:

$$\text{Cosine Similarity}(\mathbf{u}, \mathbf{v}) = \frac{\mathbf{u} \cdot \mathbf{v}}{\|\mathbf{u}\|_2 \|\mathbf{v}\|_2}$$

* Bounded strictly in $[0.0, 1.0]$.
* Empty, whitespace-only, or stopword-only inputs evaluate safely to $0.0$.
* Labeled as **lexical text similarity**, never as hiring likelihood.

#### 2. Canonical Skill Overlap Ratio
Canonical skills are extracted from both documents using word-boundary pattern matching and alias normalization:

$$\text{Skill Overlap Ratio} = \frac{|S_{\text{matched}}|}{|S_{\text{jd}}|}$$

where $S_{\text{matched}} = S_{\text{resume}} \cap S_{\text{jd}}$.
* If the job description contains no recognized skills ($|S_{\text{jd}}| = 0$), the ratio returns `null` with an explanatory message, avoiding division by zero.
* The skills are partitioned into three distinct lists:
  * **Matched Skills:** $S_{\text{matched}} = S_{\text{resume}} \cap S_{\text{jd}}$
  * **Missing Skills:** $S_{\text{missing}} = S_{\text{jd}} \setminus S_{\text{resume}}$
  * **Additional Skills:** $S_{\text{additional}} = S_{\text{resume}} \setminus S_{\text{jd}}$

---

## 7. Reproducible Within-Job Grouped Evaluation (Phase 7)

Ranking metrics (NDCG and Spearman correlation) are mathematically valid only when candidates are evaluated against the **same job description query**. Phase 7 restructures the benchmark into **5 shared job groups** with 5 candidates per group (25 candidate–job pairs).

### Running the Evaluation Script

```powershell
# Run standard evaluation (TF-IDF + Skill Overlap across 5 job groups)
python scripts/evaluate_matching.py

# Run with optional Sentence-Transformer embedding baseline
python scripts/evaluate_matching.py --include-embeddings

# Export machine-readable JSON evaluation report
python scripts/evaluate_matching.py --output data/evaluation/evaluation_report.json
```

### Actual Grouped Evaluation Report Output

```text
==================================================================================
  STUDENT RESUME ANALYZER — PHASE 7 GROUPED EVALUATION REPORT
==================================================================================
Dataset Name:         Synthetic Resume–Job Description Grouped Matching Benchmark
Examples Evaluated:   25 across 5 Job Groups (Skipped: 0)

--- Human Relevance Label Distribution (Scale 0-3) ---
  Label 0:  7 examples ( 28.0%)
  Label 1:  6 examples ( 24.0%)
  Label 2:  6 examples ( 24.0%)
  Label 3:  6 examples ( 24.0%)

--- Information Extraction Metrics (Precision / Recall / F1) ---
Target Set                | Micro-P  Micro-R  Micro-F1 | Macro-P  Macro-R  Macro-F1
----------------------------------------------------------------------------------
Resume Skills             | 0.8364   0.9388   0.8846   | 0.8386   0.8787   0.8538  
Job Description Skills    | 0.9000   0.9000   0.9000   | 0.9200   0.9100   0.9111  
Matched Skills            | 0.9062   0.9062   0.9062   | 0.9267   0.9187   0.9222  

--- Within-Job-Group Ranking Quality (Averaged across 5 Groups) ---
Signal                         | Mean Spearman   | Valid Grps | Mean NDCG@All | Mean NDCG@3 
----------------------------------------------------------------------------------
TF-IDF Text Similarity         | 0.7227          | 5/5        | 0.9431        | 0.9043      
Skill Overlap Ratio            | 0.9174          | 4/5        | 1.0000        | 1.0000      
Semantic Embeddings (all-MiniLM) | NOT REQUESTED   | --         | --            | --          

--- Within-Group Ranking Diagnostic Details ---
  • Skill Overlap Spearman skipped for JOB-GRP-05: Zero score variance across group candidates (all scores equal)

--- Evaluator Disclaimer ---
Academic Notice: This evaluation was executed against a curated synthetic benchmark. 
NDCG and Spearman correlation are computed within each shared job group and averaged across groups. 
These metrics demonstrate pipeline behavior, boundary conditions, and evaluation reproducibility; 
they are not an empirical estimate of general recruitment accuracy.
==================================================================================
```

---

## 8. Explainable Resume Feedback Rubric (Phase 8 & 9)

The system provides formative, rule-based pedagogical feedback evaluated across four transparent dimensions (25.0 max points each, totaling 100.0 max points):

1. **Resume Structure (25.0 pts):** Substantive content check ($\ge 20$ words), dedicated Education section, practical foundation (Academic/Personal Projects count equivalently to professional experience for students), and section segmentation count.
2. **Contact Completeness (25.0 pts):** RFC-compliant email (10 pts), phone number (7 pts), professional links (5 pts for $\ge 2$ links, 3 pts for 1 link), and confident name header (3 pts with job-title guards).
3. **Quantified Impact (25.0 pts):** Concrete numerical outcomes (percentages, scale multipliers, counts, currency, performance deltas) with strict exclusion guards (calendar years, phone numbers, tech version numbers like `v2.0x`, course codes like `CS 10x`, and GPA do *not* count as metrics) and token normalization deduplication.
4. **Skill-Taxonomy Coverage (25.0 pts):** Role-specific alignment ($R \times 25.0$ with mutually exclusive matched/missing partition and zero-skill JD fallback) when a target job description is provided, or general taxonomy breadth ($\ge 6$ skills across $\ge 2$ categories) when evaluated standalone. Exposes canonical `detected_resume_skills`.

> **Academic Notice:** This index is labeled explicitly as **Resume Feedback Index (heuristic)**. It is not an ATS score, hiring probability, or prediction of recruitment outcomes. Full specifications and edge cases are documented in [`docs/resume_feedback_rubric.md`](docs/resume_feedback_rubric.md).

---

## 9. Running Tests

Execute the automated test suite via pytest from the repository root:

```powershell
pytest -v
```

The test suite consists of **141 passing automated tests** across ten modular test suites:
1. `tests/test_health.py` (5 tests): Application initialization, absence of heavy models at startup, health response contract, static landing page.
2. `tests/test_pdf_extractor.py` (12 tests): In-memory PDF text extraction, empty/oversized upload rejection, non-PDF extension checks, invalid header safety, scanned PDF warnings, multi-page metrics.
3. `tests/test_docx_extractor.py` (18 tests): Modern `.docx` OpenXML text extraction, paragraph/bullet ordering, table preservation, explicit page break counting, pagination approximation regression test, empty file rejection, invalid signature handling, legacy `.doc` rejection with actionable message, corrupted/malformed file handling, encrypted document rejection, page limit enforcement, low-text quality warnings, and downstream parser/feedback pipeline compatibility.
4. `tests/test_document_integration.py` (8 tests): PDF vs. DOCX cross-format downstream consistency (identical section, contact, skill, metric, and feedback score extraction on logically equivalent resumes), unsupported extension rejection, missing upload validation, empty/whitespace payload rejection across all endpoints, oversized text bounds (50,001 characters), zero-skill JD fallback, path traversal filename sanitization (`../../passwd.docx`), and ephemeral in-memory zero-disk persistence verification.
5. `tests/test_resume_parser.py` (17 tests): Section heading boundary detection, mixed casing, negative heading guards, contact extraction (email, phone, URLs), skill taxonomy matching, Java vs. JavaScript isolation, single-letter language C safeguards.
6. `tests/test_job_matcher.py` (14 tests): TF-IDF text similarity bounds, strong vs weak overlap, alias normalization, 3-way partition, zero-division safeguards, 1:1 category consistency, regression skills (`TypeScript`, `React`, `Django`, `SQL`, `Git`, `GitHub`), bullet snippet prioritization.
7. `tests/test_evaluation_framework.py` (16 tests): Benchmark schema conformance, 5-group structure validation, record rejection rules, hand-computable precision/recall/F1, empty/disjoint set handling, fractional rank ties, Spearman $\rho$ edge cases, NDCG hand-computation, hand-computable grouped ranking across 2 groups, zero-variance group skipping, embedding matcher availability API, mock embedding vector normalization/dot product, deterministic repeated execution, graceful `--include-embeddings` fallback, and unbroken API contracts.
8. `tests/test_resume_feedback.py` (22 tests): Conventional resume scoring, student project equivalence without employment, missing contact deductions, narrative bullets without metrics, exclusion guards (dates, phone numbers, Python 3.11, Java 17, CS 101, 3.8 GPA), empty/minimal resumes, job description dual-mode (JD with skills, JD with no skills, no JD), score determinism, HTTP 400 empty input rejection, HTTP 413/422 oversized input rejection, API response contract, granular contact component breakdowns (email only, email+phone, 1 link partial credit, 2+ links full credit, missing all), name detection heuristics & title guards, skill partition consistency & deduplication, metric deduplication & normalization, and exact threshold boundaries.
9. `tests/test_architecture_consistency.py` (4 tests): Verification that all documented public endpoint paths correspond to actual registered FastAPI routes via the canonical route inspector, confirmation of core architecture components in source tree, file format support configuration checks, and verification that all 5 UML diagram deliverables exist with valid Mermaid markdown.
10. `tests/test_route_inspector.py` (25 tests): Canonical route schema (`RouteInventoryItem`), static prohibition of private framework internals, runtime discovery from `app.routes`, OpenAPI fallback for included router wrappers, phantom route rejection, router prefix resolution without string concatenation, framework docs filtering, static mount filtering, root route toggling, duplicate detection (`DuplicateRouteError`), distinct methods on same path, deterministic ordering, unnamed routes, fail-closed validation (`RouteInventoryValidationError` raised when `route.matches()` raises unexpectedly, structured error attributes and cause, no-cause formatting, legitimate policy exclusions never raise, real application completes without validation errors), and **fail-closed OpenAPI capability detection** (absence of callable `openapi` uses direct routes without error, callable `openapi()` raising `AttributeError` fails explicitly without silent fallback, callable `openapi()` raising `RuntimeError` fails explicitly, and partial route inventories are strictly prohibited).


---

## 10. Academic Limitations & Benchmarking Plan

For detailed evaluation methodology, mathematical limitations, and the benchmarking protocol against dense Sentence-Transformer models, refer to:
* [`docs/matching_evaluation_plan.md`](docs/matching_evaluation_plan.md) — Job description matching evaluation and benchmarking plan.
* [`docs/extraction_evaluation_plan.md`](docs/extraction_evaluation_plan.md) — Information extraction evaluation and ground-truth dataset plan.

### Core Baseline Limitations
* **Synonyms & Paraphrasing:** Lexical matching cannot associate non-cataloged synonyms (e.g., *"Kubernetes orchestration"* vs *"container management"*).
* **Negation & Context:** Phrases such as *"no experience with Java"* will extract `"Java"`.
* **Proficiency Depth:** A coursework mention is treated identically to years of production expertise.
* **Unequal Importance:** Core job requirements and optional nice-to-haves carry equal weight in the overlap ratio.

---

## 11. License

Academic Project — Developed for educational, research, and demonstrative purposes.
