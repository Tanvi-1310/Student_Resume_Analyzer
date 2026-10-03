"""Automated tests for resume section detection, contact parsing, and skill extraction."""

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.schemas.parser import StructuredResumeResponse
from app.services.contact_extractor import extract_contact_info
from app.services.resume_parser import resume_parser_service
from app.services.section_detector import detect_sections
from app.services.skill_extractor import extract_skills

client = TestClient(app)

# ---------------------------------------------------------------------------
# Synthetic Test Fixtures
# ---------------------------------------------------------------------------

SYNTHETIC_CONVENTIONAL_RESUME = """
Jordan Smith
Email: jordan.smith@example.edu | Phone: +1 (555) 234-5678
LinkedIn: linkedin.com/in/jordansmith-dev
GitHub: https://github.com/jordansmith-code
Portfolio: https://jordansmith.dev

Summary
Motivated computer science student with a focus on backend web services and cloud infrastructure.

Education
University of Science and Technology
Bachelor of Science in Computer Science, 2021 - 2025
• GPA: 3.8 / 4.0
• Coursework: Data Structures, Distributed Systems, Database Management

Experience
Software Engineering Intern | CloudTech Solutions
June 2023 - August 2023
• Built high-throughput REST APIs using FastAPI and PostgreSQL
• Optimized query performance, reducing response latency by 35%
• Integrated Docker containers into automated GitHub Actions CI/CD pipeline

Projects
Student Portfolio Aggregator | Academic Project
January 2024 - Present
• Designed a full-stack platform utilizing React, Node.js, and MongoDB
• Implemented caching with Redis and unit tests using pytest

Technical Skills
Languages: Python, Java, JavaScript, TypeScript, SQL, C, C++
Frameworks: FastAPI, Django, React, Express
Databases: PostgreSQL, MongoDB, Redis
Tools: Docker, Kubernetes, Linux, Git, GitHub, AWS

Certifications
AWS Certified Cloud Practitioner - Issued Nov 2023
"""


# ---------------------------------------------------------------------------
# Section Detection Tests
# ---------------------------------------------------------------------------

def test_conventional_resume_sections():
    """Verify that all standard sections are detected on a conventional resume."""
    sections, warnings = detect_sections(SYNTHETIC_CONVENTIONAL_RESUME)
    assert "summary" in sections
    assert "education" in sections
    assert "experience" in sections
    assert "projects" in sections
    assert "skills" in sections
    assert "certifications" in sections
    assert len(warnings) == 0


def test_alternate_section_headings():
    """Verify that heading variations (e.g. Academic Background, Work Experience) are recognized."""
    resume_text = """
Academic Background
BS in Software Engineering

Work Experience:
Software Developer Intern

Academic Projects:
Campus Navigator App

Core Competencies:
Python, Docker, SQL

Honors & Awards:
Dean's List 2023
"""
    sections, warnings = detect_sections(resume_text)
    assert "education" in sections
    assert "experience" in sections
    assert "projects" in sections
    assert "skills" in sections
    assert "achievements" in sections
    assert len(warnings) == 0


def test_resume_without_headings():
    """Verify behavior when no standard headings exist in the text."""
    narrative = (
        "Alex Rivera is a dedicated learner who loves building applications. "
        "Alex writes Python and React applications and has deployed backends using Docker. "
        "Reach out at alex.rivera@example.com."
    )
    sections, warnings = detect_sections(narrative)
    assert len(sections) == 0
    assert len(warnings) > 0
    assert "No standard section headings" in warnings[0]

    # Even without headings, skill extraction should still function!
    skills, _ = extract_skills(narrative)
    skill_names = {s.name for s in skills}
    assert "Python" in skill_names
    assert "React" in skill_names
    assert "Docker" in skill_names


def test_mixed_capitalization_and_colons():
    """Verify that headings with unusual casing, markdown headers, and colons are caught."""
    text = """
## professional summary:
Passionate developer

eDuCaTiOn:
State University

**WORK EXPERIENCE** :
Tech Intern

projects:
Cool App
"""
    sections, _ = detect_sections(text)
    assert "summary" in sections
    assert "education" in sections
    assert "experience" in sections
    assert "projects" in sections


def test_body_sentences_not_treated_as_headings():
    """Verify that words like 'experience' or 'skills' inside long sentences are not treated as section headers."""
    text = """
Summary
I am an engineer with extensive work experience in distributed systems.
My key skills include designing scalable architectures.

Education
University of Tech
"""
    sections, _ = detect_sections(text)
    # Only Summary and Education should be top-level sections
    assert "summary" in sections
    assert "education" in sections
    assert "experience" not in sections


# ---------------------------------------------------------------------------
# Skill Extraction & Alias Deduplication Tests
# ---------------------------------------------------------------------------

def test_duplicate_aliases_resolve_to_single_canonical():
    """Verify that multiple aliases for a skill produce one canonical record."""
    text = "Skilled in JavaScript, JS, and ECMAScript. Experienced in PostgreSQL and Postgres."
    skills, categories = extract_skills(text)
    names = [s.name for s in skills]

    assert names.count("JavaScript") == 1
    assert names.count("PostgreSQL") == 1
    assert len(names) == 2


def test_java_and_javascript_remain_distinct():
    """Verify that Java and JavaScript regexes do not collide or produce false positives."""
    # Java alone
    java_text = "Proficient in Java 17 and Spring Boot enterprise backends."
    skills_java, _ = extract_skills(java_text)
    names_java = {s.name for s in skills_java}
    assert "Java" in names_java
    assert "JavaScript" not in names_java

    # JavaScript alone
    js_text = "Experienced in modern JavaScript and React frontend development."
    skills_js, _ = extract_skills(js_text)
    names_js = {s.name for s in skills_js}
    assert "JavaScript" in names_js
    assert "Java" not in names_js

    # Both
    both_text = "Full stack engineer proficient in both Java and JavaScript."
    skills_both, _ = extract_skills(both_text)
    names_both = {s.name for s in skills_both}
    assert "Java" in names_both
    assert "JavaScript" in names_both


def test_avoid_false_matches_for_c_and_short_terms():
    """Verify that C language is not matched inside ordinary prose or course grades."""
    negative_text = (
        "Received Grade C in Organic Chemistry. "
        "Completed Section C compliance training. "
        "Assisted Category C operations. "
        "Implemented CSS responsive styling and CI/CD pipelines in Vitamin C lab."
    )
    skills_neg, _ = extract_skills(negative_text)
    names_neg = {s.name for s in skills_neg}
    assert "C" not in names_neg
    assert "CSS" in names_neg  # CSS should be legitimately found

    positive_text = "Programming Languages: C, C++, and Python."
    skills_pos, _ = extract_skills(positive_text)
    names_pos = {s.name for s in skills_pos}
    assert "C" in names_pos
    assert "C++" in names_pos
    assert "Python" in names_pos


def test_framework_and_ml_skills_extraction():
    """Verify extraction of ML and framework skills with evidence snippets."""
    text = "Built predictive pipelines using scikit-learn, pandas, and PyTorch for NLP classification."
    skills, categories = extract_skills(text)
    names = {s.name for s in skills}
    assert "scikit-learn" in names
    assert "pandas" in names
    assert "PyTorch" in names
    assert "NLP" in names

    # Check evidence snippet
    sklearn_evidence = next(s for s in skills if s.name == "scikit-learn")
    assert "scikit-learn" in sklearn_evidence.evidence_snippet
    assert sklearn_evidence.category == "Data & ML"


# ---------------------------------------------------------------------------
# Contact Extraction Tests
# ---------------------------------------------------------------------------

def test_contact_extraction_complete():
    """Verify extraction of all contact channels."""
    text = (
        "Taylor Swift\n"
        "Email: taylor.swift@cs.stanford.edu\n"
        "Phone: (415) 555-0199\n"
        "LinkedIn: https://www.linkedin.com/in/taylorswift-dev\n"
        "GitHub: https://github.com/taylorswift-codes\n"
        "Portfolio: https://taylorswift.io"
    )
    contact = extract_contact_info(text)
    assert contact.email == "taylor.swift@cs.stanford.edu"
    assert contact.phone == "(415) 555-0199"
    assert contact.linkedin_url == "https://linkedin.com/in/taylorswift-dev"
    assert contact.github_url == "https://github.com/taylorswift-codes"
    assert contact.portfolio_url == "https://taylorswift.io"


def test_contact_missing_fields():
    """Verify that absent contact fields safely return None without errors."""
    text = "Resume with no phone and no links. Contact via student@college.edu."
    contact = extract_contact_info(text)
    assert contact.email == "student@college.edu"
    assert contact.phone is None
    assert contact.linkedin_url is None
    assert contact.github_url is None
    assert contact.portfolio_url is None


def test_phone_safeguards_against_random_numbers():
    """Verify that arbitrary numbers (e.g. zip codes, years) are not falsely captured as phone numbers."""
    text = "Graduated in 2024. Zip code is 94105. Student ID is 12345."
    contact = extract_contact_info(text)
    assert contact.phone is None


# ---------------------------------------------------------------------------
# Bullets & Date Mentions Tests
# ---------------------------------------------------------------------------

def test_bullet_and_date_extraction():
    """Verify bullet points and date ranges are properly identified in section content."""
    sections, _ = detect_sections(SYNTHETIC_CONVENTIONAL_RESUME)
    exp = sections["experience"]

    assert len(exp.bullet_points) >= 3
    assert any("REST APIs" in b for b in exp.bullet_points)
    assert any("Docker" in b for b in exp.bullet_points)

    # Date extraction check
    assert any("2023" in d for d in exp.detected_dates)


# ---------------------------------------------------------------------------
# Master Service & API Endpoint Tests
# ---------------------------------------------------------------------------

def test_master_service_structured_output():
    """Verify that master ResumeParserService produces the full StructuredResumeResponse."""
    response = resume_parser_service.parse_resume_text(
        SYNTHETIC_CONVENTIONAL_RESUME, filename="jordan_resume.pdf"
    )
    assert isinstance(response, StructuredResumeResponse)
    assert response.filename == "jordan_resume.pdf"
    assert response.contact_info.email == "jordan.smith@example.edu"
    assert len(response.missing_standard_sections) == 0
    assert len(response.skills) >= 10
    assert "Programming Languages" in response.skills_by_category


def test_api_analyze_text_success():
    """Verify POST /api/v1/resumes/analyze-text endpoint returns 200 and valid schema."""
    payload = {
        "text": SYNTHETIC_CONVENTIONAL_RESUME,
        "filename": "test_resume.pdf",
    }
    response = client.post("/api/v1/resumes/analyze-text", json=payload)
    assert response.status_code == 200

    data = response.json()
    assert data["filename"] == "test_resume.pdf"
    assert data["contact_info"]["email"] == "jordan.smith@example.edu"
    assert "education" in data["detected_sections"]
    assert "skills" in data["detected_sections"]
    assert len(data["skills"]) > 5


def test_api_analyze_text_blank_input_rejected():
    """Verify that blank or whitespace-only text is rejected with HTTP 400."""
    response = client.post(
        "/api/v1/resumes/analyze-text",
        json={"text": "   \n\t   ", "filename": "blank.pdf"},
    )
    assert response.status_code == 400
    detail = response.json().get("detail", "").lower()
    assert "empty" in detail or "whitespace" in detail


def test_api_analyze_text_oversized_input_rejected():
    """Verify that excessively large text payloads (>50k chars) are rejected."""
    oversized = "A" * 50005
    response = client.post(
        "/api/v1/resumes/analyze-text",
        json={"text": oversized, "filename": "huge.txt"},
    )
    assert response.status_code in (413, 422)
