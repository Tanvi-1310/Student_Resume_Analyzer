# Student Resume Analyzer — Component Diagram

## Purpose
This component diagram depicts the high-level software components and subsystem boundaries of the Student Resume Analyzer project. It illustrates the separation of concerns between presentation, API routing, in-memory document ingestion, NLP information extraction, alignment/feedback scoring, and offline reproducible evaluation.

---

## Diagram

```mermaid
flowchart TD
    subgraph ClientLayer ["Client Layer (Presentation)"]
        UI["Web Frontend\n(index.html, styles.css, app.js)\n- Vanilla JS Single-Page Interface\n- File Picker (.pdf, .docx)\n- In-Memory DOM Rendering (Safe textContent)"]
    end

    subgraph APILayer ["FastAPI Application (Routing & Orchestration)"]
        Router["FastAPI Application Core (app/main.py)\n- CORS Middleware\n- Static Mounts (/css, /js)\n- Route Handler (app/api/v1/resumes.py)"]
    end

    subgraph IngestionSubsystem ["Document Ingestion Subsystem (In-Memory / Zero Disk Persistence)"]
        PDFComp["PDF Extractor Component\n(pdf_extractor.py)\n- pdfplumber / pypdf\n- %PDF Magic Bytes Check\n- Page Limit Guard (<= 10)"]
        DOCXComp["DOCX Extractor Component\n(docx_extractor.py)\n- python-docx OpenXML Engine\n- PK Zip Signature Check\n- Explicit Break Tracking"]
        DocGuard["Format & Security Guard\n- 5 MB Streaming Read Limit\n- Legacy .doc Rejection\n- Path Traversal Sanitizer"]
    end

    subgraph NLPSubsystem ["Resume Analysis & Information Extraction Subsystem"]
        ParserComp["Resume Parser (resume_parser.py)"]
        SectionComp["Section Detector (section_detector.py)\n- 9 Standard Section Types"]
        ContactComp["Contact Extractor (contact_extractor.py)\n- Email, Phone, LinkedIn, GitHub, URLs"]
        SkillComp["Skill Taxonomy Extractor (skill_extractor.py)\n- 45+ Canonical Skills & Negative Guards"]
    end

    subgraph ScoringSubsystem ["Matching & Feedback Subsystem"]
        MatchComp["Job Matcher (job_matcher.py)\n- TF-IDF Cosine Similarity\n- 3-Way Skill Partition"]
        FeedbackComp["Feedback Analyzer (feedback_analyzer.py)\n- 4 Rubric Dimensions (100 pts)\n- Exclusion Guards on Quantified Metrics"]
    end

    subgraph EvalSubsystem ["Offline Evaluation Subsystem (CLI / Automation)"]
        EvalRunner["Evaluation Script (scripts/evaluate_matching.py)"]
        SynthBench["Grouped Benchmark (synthetic_matching_benchmark.json)\n- 5 Job Groups x 5 Candidates"]
        TestSuites["Automated Test Suites (pytest)\n- 10 Modular Test Suites"]
    end

    %% Wiring
    UI -->|HTTP / JSON & Multipart| Router
    Router --> DocGuard
    DocGuard --> PDFComp
    DocGuard --> DOCXComp

    PDFComp -.->|Extracted Text (In-Memory)| ParserComp
    DOCXComp -.->|Extracted Text (In-Memory)| ParserComp

    ParserComp --> SectionComp
    ParserComp --> ContactComp
    ParserComp --> SkillComp

    Router --> MatchComp
    Router --> FeedbackComp

    MatchComp --> SkillComp
    FeedbackComp --> SectionComp
    FeedbackComp --> ContactComp
    FeedbackComp --> SkillComp

    EvalRunner --> MatchComp
    EvalRunner --> SynthBench
    TestSuites --> Router
    TestSuites --> IngestionSubsystem
    TestSuites --> NLPSubsystem
    TestSuites --> ScoringSubsystem
```

---

## Explanation of Components

1. **Client Layer:** Single-page dashboard built with vanilla JavaScript, modern CSS, and HTML5. Provides file selection, reactive drag-and-drop, and real-time result cards. No external UI frameworks or cookies are used.
2. **FastAPI Application Core:** High-performance asynchronous API layer hosting registered routes (`/health`, `/api/v1/resumes/extract`, `/api/v1/resumes/analyze-text`, `/api/v1/resumes/match`, `/api/v1/resumes/feedback`).
3. **Document Ingestion Subsystem:** Purely in-memory document parsing engine. Houses independent extractors for PDF (`pdfplumber`) and DOCX (`python-docx`). Enforces payload size limits (5 MB), file signature checks, explicit page break detection, and rejection of legacy binary `.doc` files.
4. **Resume Analysis Subsystem:** Modular NLP pipeline identifying document hierarchy, contact information, and canonical technical skills with provenance snippets.
5. **Matching & Feedback Subsystem:** Generates explainable matching signals (TF-IDF cosine similarity, skill overlap ratio) and formative feedback scores across Structure, Contacts, Impact, and Skills.
6. **Evaluation Subsystem:** Standalone CLI tools and pytest test suites validating ranking quality (within-job NDCG and Spearman correlation) and ensuring regression prevention across the entire pipeline.
7. **Architectural Properties:** 
   - **Zero Disk Persistence:** Volatile in-memory buffers (`io.BytesIO`) ensure candidate privacy.
   - **No External Cloud Dependencies:** No OCR APIs, third-party LLMs, or database systems are required.
