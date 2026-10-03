"""Automated tests for explainable job description matching and Phase 4 contract regression."""

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.schemas.matcher import JobMatchResponse
from app.services.job_matcher import job_matcher_service
from app.services.resume_parser import resume_parser_service
from app.services.skill_extractor import extract_skills

client = TestClient(app)


# ---------------------------------------------------------------------------
# Signal A: Lexical TF-IDF Text Similarity Tests
# ---------------------------------------------------------------------------

def test_identical_text_similarity():
    """Verify that identical texts produce maximum similarity (1.0)."""
    text = "Senior Python software engineer developing REST APIs using FastAPI and PostgreSQL."
    sim, _ = job_matcher_service.compute_text_similarity(text, text)
    assert 0.999 <= sim <= 1.0


def test_unrelated_text_similarity():
    """Verify that completely disjoint vocabularies produce near-zero similarity."""
    resume = "Pastry chef specializing in sourdough fermentation, artisan breads, and French croissants."
    jd = "Kubernetes infrastructure engineer configuring Docker containers, Helm charts, and cloud clusters."
    sim, _ = job_matcher_service.compute_text_similarity(resume, jd)
    assert 0.0 <= sim <= 0.05


def test_strong_vs_weak_lexical_overlap():
    """Verify that a conceptually aligned resume scores higher than a loosely aligned one."""
    jd = (
        "Seeking a Python backend developer experienced in building web APIs, "
        "relational database modeling with PostgreSQL, and automated testing."
    )
    strong_resume = (
        "Backend developer with extensive experience in Python, building web APIs with FastAPI, "
        "PostgreSQL query optimization, and pytest test suites."
    )
    weak_resume = (
        "Project coordinator managing marketing campaigns, social media outreach, "
        "and client relations with basic knowledge of computers."
    )

    sim_strong, _ = job_matcher_service.compute_text_similarity(strong_resume, jd)
    sim_weak, _ = job_matcher_service.compute_text_similarity(weak_resume, jd)

    assert sim_strong > sim_weak
    assert sim_strong > 0.15
    assert sim_weak < 0.05


def test_empty_or_stopword_text_similarity():
    """Verify that empty texts or stop-word-only texts safely return 0.0 without errors."""
    sim_empty, exp_empty = job_matcher_service.compute_text_similarity("", "Python Developer")
    assert sim_empty == 0.0
    assert "empty" in exp_empty.lower()

    sim_stopwords, exp_stopwords = job_matcher_service.compute_text_similarity("the and or is in at", "with for of by")
    assert sim_stopwords == 0.0


# ---------------------------------------------------------------------------
# Signal B: Skill Overlap and Alias Mapping Tests
# ---------------------------------------------------------------------------

def test_skill_aliases_mapping_to_canonical():
    """Verify that skill aliases in both resume and JD resolve to the same canonical names."""
    resume_text = "Proficient in JS, Postgres, and ReactJS."
    jd_text = "Looking for someone skilled in JavaScript, PostgreSQL, and React."

    result = job_matcher_service.match(resume_text, jd_text)

    assert result.matched_skills == ["JavaScript", "PostgreSQL", "React"]
    assert result.missing_skills == []
    assert result.additional_skills == []
    assert result.skill_overlap_ratio == 1.0


def test_skill_overlap_three_way_split():
    """Verify clean partition into matched, missing (from JD), and additional (from resume)."""
    resume_text = "Technical skills: Python, FastAPI, Docker, Redis."
    jd_text = "Requirements: Python, FastAPI, Kubernetes, AWS."

    result = job_matcher_service.match(resume_text, jd_text)

    # Matched = intersection
    assert result.matched_skills == ["FastAPI", "Python"]
    # Missing = in JD but not in resume
    assert result.missing_skills == ["AWS", "Kubernetes"]
    # Additional = in resume but not in JD
    assert result.additional_skills == ["Docker", "Redis"]

    # Overlap ratio = 2 / 4 = 0.5
    assert result.skill_overlap_ratio == 0.5
    assert "50.0%" in result.skill_overlap_explanation


def test_job_description_with_no_skills_avoids_division_by_zero():
    """Verify that when JD has no taxonomy skills, ratio is None and zero-division is avoided."""
    resume_text = "Skilled in Python and Docker."
    jd_text = "Seeking an enthusiastic self-starter with excellent communication and team collaboration."

    result = job_matcher_service.match(resume_text, jd_text)

    assert result.skill_overlap_ratio is None
    assert result.job_description_skills == []
    assert result.matched_skills == []
    assert result.additional_skills == ["Docker", "Python"]
    assert "division by zero avoided" in result.skill_overlap_explanation.lower()


# ---------------------------------------------------------------------------
# API Endpoint Integration Tests
# ---------------------------------------------------------------------------

def test_api_match_success_contract():
    """Verify POST /api/v1/resumes/match returns HTTP 200 and conforms to schema."""
    payload = {
        "resume_text": "Experienced Python engineer with FastAPI and Docker.",
        "job_description": "We are hiring a Python developer with Docker and Kubernetes skills.",
        "resume_filename": "candidate_resume.pdf",
    }
    response = client.post("/api/v1/resumes/match", json=payload)
    assert response.status_code == 200

    data = response.json()
    validated = JobMatchResponse(**data)
    assert validated.resume_filename == "candidate_resume.pdf"
    assert 0.0 <= validated.text_similarity <= 1.0
    assert validated.matched_skills == ["Docker", "Python"]
    assert validated.missing_skills == ["Kubernetes"]
    assert validated.skill_overlap_ratio == round(2 / 3, 4)


def test_api_match_blank_inputs_rejected():
    """Verify that empty resume or JD payloads are rejected with HTTP 400."""
    # Blank resume
    r1 = client.post(
        "/api/v1/resumes/match",
        json={"resume_text": "   ", "job_description": "Python developer"},
    )
    assert r1.status_code == 400
    assert "resume text cannot be empty" in r1.json()["detail"].lower()

    # Blank JD
    r2 = client.post(
        "/api/v1/resumes/match",
        json={"resume_text": "Python engineer", "job_description": "\n\t  "},
    )
    assert r2.status_code == 400
    assert "job description cannot be empty" in r2.json()["detail"].lower()


def test_api_match_oversized_payload_rejected():
    """Verify that oversized text (>50k chars) is rejected with HTTP 413 or 422."""
    huge_text = "Python " * 10000
    response = client.post(
        "/api/v1/resumes/match",
        json={"resume_text": huge_text, "job_description": "Python"},
    )
    assert response.status_code in (413, 422)


# ---------------------------------------------------------------------------
# Phase 4 Response Contract Regression & Consistency Tests
# ---------------------------------------------------------------------------

def test_skills_and_skills_by_category_consistency():
    """Verify strict 1:1 synchronization between skills and skills_by_category."""
    sample_resume = """
    Jane Doe | Email: jane@example.com
    
    Education
    BS in Computer Science
    
    Experience
    Software Engineer Intern
    • Developed REST APIs in Python using Django and PostgreSQL
    • Designed frontend interfaces in TypeScript using React and Next.js
    • Managed containerization with Docker and source control with Git and GitHub
    
    Skills
    Languages: Python, TypeScript, SQL
    Frameworks: React, Next.js, Django
    Databases: PostgreSQL
    Tools: Git, GitHub, Docker
    """
    result = resume_parser_service.parse_resume_text(sample_resume, filename="jane.pdf")

    # 1. Check set equality
    evidence_names = {s.name for s in result.skills}
    categorized_names = {name for cat_list in result.skills_by_category.values() for name in cat_list}
    assert evidence_names == categorized_names

    # 2. Check total count equality (no duplicates across categories)
    total_categorized = sum(len(cat_list) for cat_list in result.skills_by_category.values())
    assert len(result.skills) == total_categorized


def test_regression_skills_typescript_react_django_sql_git_github():
    """Regression test specifically verifying TypeScript, React, Django, SQL, Git, and GitHub."""
    text = (
        "Proficient in TypeScript, React, Django, and SQL. "
        "Uses Git for version control and hosts open-source repositories on GitHub."
    )
    skills, categories = extract_skills(text)
    names = {s.name for s in skills}

    assert "TypeScript" in names
    assert "React" in names
    assert "Django" in names
    assert "SQL" in names
    assert "Git" in names
    assert "GitHub" in names


def test_git_and_github_do_not_collide():
    """Verify that a resume with only GitHub does NOT falsely detect Git."""
    text_only_github = "Check out my projects on GitHub: https://github.com/alex-dev."
    skills_gh, _ = extract_skills(text_only_github)
    names_gh = {s.name for s in skills_gh}
    assert "GitHub" in names_gh
    assert "Git" not in names_gh

    text_only_git = "Proficient in Git branching workflows and rebasing."
    skills_git, _ = extract_skills(text_only_git)
    names_git = {s.name for s in skills_git}
    assert "Git" in names_git
    assert "GitHub" not in names_git


def test_evidence_snippet_prioritizes_bullet_over_comma_list():
    """Verify that when a skill appears in both a list and a descriptive bullet, the bullet is selected."""
    text = (
        "Technical Skills: Python, FastAPI, Docker\n\n"
        "Experience:\n"
        "• Architected scalable microservices using FastAPI with 99.9% uptime"
    )
    skills, _ = extract_skills(text)
    fastapi_skill = next(s for s in skills if s.name == "FastAPI")

    assert "Architected scalable microservices" in fastapi_skill.evidence_snippet
    assert fastapi_skill.matched_alias == "FastAPI"
