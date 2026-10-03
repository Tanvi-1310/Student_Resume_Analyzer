# Student Resume Analyzer — Sequence Diagram

## Purpose
This sequence diagram depicts the chronological interactions among client and server components during an end-to-end resume evaluation session. It demonstrates how format-specific extractors handle document ingestion, how downstream NLP services parse text and extract entities, and how the frontend coordinates asynchronous HTTP calls using **verbatim code-derived endpoint paths**.

---

## Diagram

```mermaid
sequenceDiagram
    autonumber
    actor User as Student / User
    participant UI as Frontend Client (app.js)
    participant API as FastAPI Router (app/api/v1/resumes.py)
    participant PDF as PDFExtractorService (pdf_extractor.py)
    participant DOCX as DocxExtractorService (docx_extractor.py)
    participant Parser as ResumeParserService (resume_parser.py)
    participant Skills as SkillExtractor (skill_extractor.py)
    participant Matcher as JobMatcherService (job_matcher.py)
    participant Feedback as FeedbackAnalyzerService (feedback_analyzer.py)

    %% Step 1: Document Upload & Ingestion
    User->>UI: Selects resume file (.pdf or .docx) & clicks Analyze
    UI->>UI: Displays loading spinner & validates file extension

    alt Upload is PDF document
        UI->>API: POST /api/v1/resumes/extract (multipart/form-data: .pdf)
        API->>PDF: extract_text_from_bytes(pdf_bytes, filename)
        PDF->>PDF: Validate %PDF header, page count <= 10, decrypt check
        PDF-->>API: ResumeExtractionResponse (extracted_text, page_count, warnings)
        API-->>UI: HTTP 200: JSON ResumeExtractionResponse
    else Upload is DOCX document
        UI->>API: POST /api/v1/resumes/extract (multipart/form-data: .docx)
        API->>DOCX: extract_text_from_bytes(docx_bytes, filename)
        DOCX->>DOCX: Validate PK zip header, check explicit page breaks, extract XML
        DOCX-->>API: ResumeExtractionResponse (extracted_text, page_count, warnings)
        API-->>UI: HTTP 200: JSON ResumeExtractionResponse
    end

    %% Step 2: Structured Parsing
    UI->>API: POST /api/v1/resumes/analyze-text (JSON: {text, filename})
    API->>Parser: parse_resume_text(text, filename)
    Parser->>Parser: detect_sections(text) -> [education, experience, projects, skills]
    Parser->>Parser: extract_contact_info(text) -> (email, phone, links)
    Parser->>Skills: extract_skills(text)
    Skills->>Skills: Word-boundary regex & category classification
    Skills-->>Parser: (skills, skills_by_category)
    Parser-->>API: StructuredResumeResponse
    API-->>UI: HTTP 200: JSON StructuredResumeResponse
    UI->>UI: Renders sections, contact badges, and detected skills

    %% Step 3: Optional Job Matching
    opt Target Job Description Provided
        UI->>API: POST /api/v1/resumes/match (JSON: {resume_text, job_description})
        API->>Matcher: match(resume_text, job_description)
        Matcher->>Matcher: TfidfVectorizer fit & cosine similarity calculation
        Matcher->>Skills: extract_skills(job_description)
        Matcher->>Matcher: Partition skills (Matched, Missing, Additional)
        Matcher-->>API: JobMatchResponse (text_similarity, overlap_ratio, partitions)
        API-->>UI: HTTP 200: JSON JobMatchResponse
        UI->>UI: Renders matched vs missing skill pills & TF-IDF similarity score
    end

    %% Step 4: Resume Feedback Rubric
    UI->>API: POST /api/v1/resumes/feedback (JSON: {resume_text, job_description})
    API->>Feedback: generate_feedback(resume_text, job_description)
    Feedback->>Feedback: Score Dimension 1: Structure (25 pts max)
    Feedback->>Feedback: Score Dimension 2: Contact Completeness (25 pts max)
    Feedback->>Feedback: Score Dimension 3: Quantified Impact (25 pts max with exclusion guards)
    Feedback->>Feedback: Score Dimension 4: Skill Coverage (25 pts max)
    Feedback-->>API: ResumeFeedbackResponse (total_score, dimensions, recommendations)
    API-->>UI: HTTP 200: JSON ResumeFeedbackResponse

    %% Step 5: Render Results
    UI->>UI: Hides spinner, renders feedback cards, recommendations, and disclaimer
    UI-->>User: Displays full interactive analysis dashboard
```

---

## Explanation of Interactions

1. **Document Ingestion (`POST /api/v1/resumes/extract`):** The frontend sends a multipart file upload. FastAPI routes `.pdf` files to `PDFExtractorService` and `.docx` files to `DocxExtractorService`. Both extractors execute in-memory with zero disk persistence, returning identical `ResumeExtractionResponse` structures.
2. **Text Parsing (`POST /api/v1/resumes/analyze-text`):** The extracted plain text is transmitted to the structured parser. `ResumeParserService` orchestrates section detection, contact extraction (email, phone, LinkedIn, GitHub), and taxonomy skill identification.
3. **Job Matching (`POST /api/v1/resumes/match`):** If the user provided a job description, the frontend requests lexical matching. `JobMatcherService` computes TF-IDF cosine similarity and standardizes skill overlap.
4. **Pedagogical Feedback (`POST /api/v1/resumes/feedback`):** The text is scored against the four-dimension rubric. Actionable suggestions and quantified metrics are returned to the client.
5. **Safe Rendering:** The frontend updates DOM elements strictly using `textContent` to prevent script injection.
