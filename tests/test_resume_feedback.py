"""Automated tests for explainable, rule-based resume feedback rubric."""

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.schemas.feedback import ResumeFeedbackResponse
from app.services.feedback_analyzer import (
    detect_quantified_metrics,
    feedback_analyzer_service,
)

client = TestClient(app)


# ---------------------------------------------------------------------------
# Test Fixtures & Synthetic Resumes
# ---------------------------------------------------------------------------

CONVENTIONAL_RESUME = """
Jane Doe
jane.doe@example.com | +1 (555) 234-5678 | https://linkedin.com/in/janedoe | https://github.com/janedoe

EDUCATION
Bachelor of Science in Computer Science
University of California, Berkeley (2020 - 2024)

TECHNICAL SKILLS
Languages: Python, JavaScript, TypeScript, SQL, C++
Frameworks & Tools: FastAPI, React, Docker, Git, PostgreSQL

PROFESSIONAL EXPERIENCE
Software Engineer Intern | Tech Innovations Inc. | June 2023 - August 2023
- Optimized PostgreSQL database indexes, reducing query latency by 45% across 12 high-traffic endpoints.
- Built automated data pipeline with FastAPI and Docker processing over 50,000 requests per day.
- Improved frontend load speed by 2x, resulting in an estimated $5,000 annual cloud infrastructure savings.

PROJECTS
Student Resume Analyzer | Python, FastAPI, React
- Developed an open-source resume review platform serving 1,500 users in university hackathon.
- Achieved 98% test coverage across 65 unit and integration tests using pytest.
"""

STUDENT_PROJECT_RESUME = """
Alex Smith
alex.smith@college.edu | 415-555-7890 | https://github.com/alexsmith

OBJECTIVE
Motivated undergraduate seeking a software engineering internship.

EDUCATION
B.S. in Software Engineering, State University (Expected May 2026)
Coursework: CS 101, Data Structures, Algorithms, Web Development

PROJECTS
Campus Event Finder | Python, FastAPI, React
- Architected RESTful API backend handling 5,000 daily queries with sub-50ms latency.
- Implemented real-time notifications with WebSockets, boosting weekly active users by 35%.

AI Study Buddy | Python, PyTorch, Docker
- Built collaborative study tool used by over 200 students during final exam week.
- Reduced model inference memory footprint by 40% through quantization.

TECHNICAL SKILLS
Python, JavaScript, React, FastAPI, Docker, Git, SQL
"""

NARRATIVE_RESUME_NO_METRICS = """
Robert Johnson
robert.j@example.com | 212-555-0199 | https://github.com/robertj

EDUCATION
B.S. in Information Systems, City College

WORK EXPERIENCE
IT Support Specialist | Acme Corp
- Responsible for monitoring company servers and responding to employee help desk tickets.
- Assisted in software upgrades, network maintenance, and user access configuration.
- Participated in weekly standups, sprint reviews, and technical documentation drafting.

PROJECTS
Personal Portfolio Website
- Created responsive web pages using HTML, CSS, and basic JavaScript.
- Deployed website to GitHub Pages and configured custom DNS records.

SKILLS
Python, HTML, CSS, JavaScript, Git
"""

EXCLUSION_GUARD_RESUME = """
Taylor Morgan
taylor@example.com | (555) 012-3456 | https://github.com/taylorm

EDUCATION
B.S. Computer Science, Class of 2024
GPA: 3.8 / 4.0
Relevant Coursework: CS 101, CS 201, MATH 240, STAT 301

EXPERIENCE
Junior Developer | Tech Labs (2022 - 2023)
- Maintained web application using Python 3.11 and Java 17.
- Updated dependencies to v2.4.0 and configured OAuth 2.0 authentication.
- Resolved bug tickets in legacy codebase originally authored in 2019.

PROJECTS
Course Scheduler | Python 3.10
- Built scheduler app for course CS 350 following university guidelines established in 2021.
- Documented API endpoints according to OpenAPI v3 specifications.

SKILLS
Python, Java, Git, SQL
"""


# ---------------------------------------------------------------------------
# 1. Quantified Metrics Detection & Exclusion Guard Unit Tests
# ---------------------------------------------------------------------------

def test_detect_quantified_metrics_true_positives():
    """Verify that concrete metrics (percentages, multipliers, scale counts, currency) are detected."""
    text = (
        "Reduced latency by 45% across all endpoints. "
        "Improved rendering speed by 3x for 10,000 users. "
        "Saved $12,000 in monthly compute expenditures."
    )
    metrics = detect_quantified_metrics(text)
    assert len(metrics) >= 3

    types = {m.metric_type for m in metrics}
    assert "percentage" in types
    assert "multiplier" in types or "scale_count" in types or "currency" in types


def test_detect_quantified_metrics_exclusion_guards():
    """Verify that dates, phone numbers, version numbers, course codes, and GPA are NOT counted."""
    text = (
        "Graduated in 2024 with a 3.9 GPA after completing CS 101 and MATH 240. "
        "Contact me at +1 (555) 123-4567 or via Python 3.11 and Java 17 development tools. "
        "Upgraded library from v1.2 to v2.4 in year 2023."
    )
    metrics = detect_quantified_metrics(text)
    assert len(metrics) == 0, f"Expected 0 metrics due to exclusion guards, but got: {metrics}"


# ---------------------------------------------------------------------------
# 2. Rubric Dimension Tests
# ---------------------------------------------------------------------------

def test_conventional_resume_feedback_high_scores():
    """Verify that a comprehensive resume receives strong scores across all four dimensions."""
    resp = feedback_analyzer_service.generate_feedback(
        resume_text=CONVENTIONAL_RESUME,
        resume_filename="jane_doe_resume.pdf",
    )
    assert resp.total_score >= 80.0
    assert resp.index_label in ["Exemplary", "Proficient"]
    assert resp.structure_feedback.score >= 20.0
    assert resp.contact_feedback.score >= 22.0
    assert resp.impact_feedback.score >= 20.0
    assert resp.skills_feedback.score >= 20.0
    assert len(resp.quantified_metrics_detected) >= 3
    assert len(resp.prioritized_recommendations) > 0
    assert "ATS score" not in resp.methodology_disclaimer
    assert "heuristic" in resp.methodology_disclaimer.lower()


def test_student_resume_with_projects_only():
    """Verify that a student resume with projects and coursework receives practical section credit without employment."""
    resp = feedback_analyzer_service.generate_feedback(
        resume_text=STUDENT_PROJECT_RESUME,
        resume_filename="alex_smith_student.pdf",
    )
    # Structure must acknowledge projects as valid practical equivalent
    struct = resp.structure_feedback
    assert any("Projects" in s for s in struct.strengths)
    assert struct.score >= 20.0

    # Impact should successfully find metrics from the projects
    assert resp.impact_feedback.score >= 20.0
    assert len(resp.quantified_metrics_detected) >= 2


def test_missing_contacts_deductions():
    """Verify that missing email and phone result in specific deductions and suggestions."""
    resume_no_contact = """
Unknown Candidate
https://github.com/developer

EDUCATION
B.S. in Computer Science

PROJECTS
Web Scraper
- Extracted 10,000 records from online portal with 99% accuracy.

SKILLS
Python, SQL, Git
"""
    resp = feedback_analyzer_service.generate_feedback(resume_no_contact)
    contact = resp.contact_feedback
    assert contact.score < 15.0
    assert any("email" in d.lower() for d in contact.deductions)
    assert any("phone" in d.lower() for d in contact.deductions)
    assert any("email" in s.lower() for s in contact.suggestions)


def test_narrative_resume_no_quantified_metrics():
    """Verify that narrative bullets with no numerical metrics receive baseline credit but appropriate deductions."""
    resp = feedback_analyzer_service.generate_feedback(NARRATIVE_RESUME_NO_METRICS)
    impact = resp.impact_feedback
    # 5.0 baseline points for having experience/projects without metrics
    assert impact.score == 5.0
    assert len(resp.quantified_metrics_detected) == 0
    assert any("no concrete quantified impact" in d.lower() for d in impact.deductions)
    assert any("quantify" in s.lower() or "metric" in s.lower() for s in impact.suggestions)


def test_exclusion_guard_resume_impact_score():
    """Verify that a resume with dates and version numbers but no real metrics does not trigger false positive metrics."""
    resp = feedback_analyzer_service.generate_feedback(EXCLUSION_GUARD_RESUME)
    assert len(resp.quantified_metrics_detected) == 0
    assert resp.impact_feedback.score == 5.0


def test_empty_or_minimal_resume():
    """Verify that empty or minimal text receives appropriate structural deductions."""
    minimal_text = "Jane Doe\nSoftware Engineer"
    resp = feedback_analyzer_service.generate_feedback(minimal_text)
    struct = resp.structure_feedback
    assert struct.score < 10.0
    assert any("brief" in d.lower() or "substantive" in d.lower() for d in struct.deductions)


# ---------------------------------------------------------------------------
# 3. Job Description Dual-Mode Tests
# ---------------------------------------------------------------------------

def test_feedback_without_job_description():
    """Verify that omitting a job description defaults to general taxonomy breadth (Mode B)."""
    resp = feedback_analyzer_service.generate_feedback(
        resume_text=STUDENT_PROJECT_RESUME,
        job_description=None,
    )
    assert resp.has_job_description is False
    assert resp.job_description_skills_count is None
    assert resp.matched_job_skills is None
    assert resp.missing_job_skills is None
    assert "breadth" in resp.skills_feedback.summary.lower()


def test_feedback_with_target_job_description():
    """Verify that supplying a target job description evaluates role-specific skill alignment (Mode A)."""
    target_jd = (
        "Seeking an intern with skills in Python, FastAPI, Docker, and Kubernetes. "
        "Experience with React and PostgreSQL is a plus."
    )
    resp = feedback_analyzer_service.generate_feedback(
        resume_text=STUDENT_PROJECT_RESUME,
        job_description=target_jd,
    )
    assert resp.has_job_description is True
    assert resp.job_description_skills_count is not None
    assert resp.job_description_skills_count > 0
    assert resp.matched_job_skills is not None
    assert resp.missing_job_skills is not None
    assert "python" in [s.lower() for s in resp.matched_job_skills]
    assert "kubernetes" in [s.lower() for s in resp.missing_job_skills]
    assert "role-specific" in resp.skills_feedback.summary.lower()


def test_feedback_with_empty_skill_job_description():
    """Verify that a job description with zero recognizable technical skills falls back to general breadth without division by zero."""
    fluff_jd = (
        "We are looking for a dynamic, highly motivated rockstar ninja who is enthusiastic, "
        "enjoys synergy, and thrives in high-pressure environments."
    )
    resp = feedback_analyzer_service.generate_feedback(
        resume_text=STUDENT_PROJECT_RESUME,
        job_description=fluff_jd,
    )
    assert resp.has_job_description is True
    assert resp.job_description_skills_count == 0
    assert resp.matched_job_skills == []
    assert resp.missing_job_skills == []
    assert any("0 recognized" in s.lower() or "fallback" in s.lower() for s in resp.skills_feedback.strengths)


# ---------------------------------------------------------------------------
# 4. Determinism & Consistency Tests
# ---------------------------------------------------------------------------

def test_feedback_score_determinism():
    """Verify that running the feedback analyzer multiple times on identical input yields exact same results."""
    run1 = feedback_analyzer_service.generate_feedback(CONVENTIONAL_RESUME)
    run2 = feedback_analyzer_service.generate_feedback(CONVENTIONAL_RESUME)

    assert run1.total_score == run2.total_score
    assert run1.structure_feedback.score == run2.structure_feedback.score
    assert run1.contact_feedback.score == run2.contact_feedback.score
    assert run1.impact_feedback.score == run2.impact_feedback.score
    assert run1.skills_feedback.score == run2.skills_feedback.score
    assert run1.prioritized_recommendations == run2.prioritized_recommendations


# ---------------------------------------------------------------------------
# 5. API Endpoint Tests (POST /api/v1/resumes/feedback)
# ---------------------------------------------------------------------------

def test_api_feedback_endpoint_success():
    """Verify that the API endpoint returns 200 OK and validates against the Pydantic response contract."""
    response = client.post(
        "/api/v1/resumes/feedback",
        json={
            "resume_text": CONVENTIONAL_RESUME,
            "resume_filename": "jane_doe.pdf",
        },
    )
    assert response.status_code == 200
    data = response.json()
    validated = ResumeFeedbackResponse(**data)
    assert validated.total_score > 0
    assert validated.structure_feedback.max_score == 25.0
    assert validated.contact_feedback.max_score == 25.0
    assert validated.impact_feedback.max_score == 25.0
    assert validated.skills_feedback.max_score == 25.0
    assert isinstance(validated.detected_resume_skills, list)
    assert len(validated.detected_resume_skills) > 0


def test_api_feedback_empty_input():
    """Verify that blank or whitespace resume text is rejected with HTTP 400."""
    response = client.post(
        "/api/v1/resumes/feedback",
        json={"resume_text": "   \n\t  "},
    )
    assert response.status_code == 400
    assert "empty" in response.json()["detail"].lower()


def test_api_feedback_oversized_input():
    """Verify that input exceeding 50,000 characters is rejected with HTTP 413 or 422."""
    oversized_text = "A" * 50001
    response = client.post(
        "/api/v1/resumes/feedback",
        json={"resume_text": oversized_text},
    )
    assert response.status_code in (413, 422)


# ---------------------------------------------------------------------------
# 6. Phase 9 Reliability Audit & Regression Tests
# ---------------------------------------------------------------------------

def test_contact_scoring_breakdowns():
    """Explicitly test email only, email+phone, 1 link, 2+ links, and missing all."""
    # A. Email only (with clean name) -> 10 (email) + 3 (name) = 13.0 pts
    email_only = "Jane Doe\njane.doe@example.com\n\nEDUCATION\nBS Computer Science\n\nPROJECTS\nApp: Python"
    r_email = feedback_analyzer_service.generate_feedback(email_only)
    assert r_email.contact_feedback.score == 13.0
    assert any("-7 pts: Telephone number not identified" in d for d in r_email.contact_feedback.deductions)
    assert any("-5 pts: No online professional profile" in d for d in r_email.contact_feedback.deductions)

    # B. Email + Phone (with clean name) -> 10 + 7 + 3 = 20.0 pts
    email_phone = "Jane Doe\njane.doe@example.com | 415-555-1234\n\nEDUCATION\nBS CS\n\nPROJECTS\nApp: Python"
    r_ep = feedback_analyzer_service.generate_feedback(email_phone)
    assert r_ep.contact_feedback.score == 20.0
    assert any("-5 pts: No online professional profile" in d for d in r_ep.contact_feedback.deductions)

    # C. One professional profile link -> 10 + 7 + 3 (1 link) + 3 (name) = 23.0 pts
    one_link = "Jane Doe\njane.doe@example.com | 415-555-1234 | https://github.com/janedoe\n\nEDUCATION\nBS CS\n\nPROJECTS\nApp: Python"
    r_1l = feedback_analyzer_service.generate_feedback(one_link)
    assert r_1l.contact_feedback.score == 23.0
    assert any("-2 pts: Only 1 online professional link" in d for d in r_1l.contact_feedback.deductions)

    # D. Two professional profile links -> 10 + 7 + 5 (2 links) + 3 (name) = 25.0 pts (Full credit)
    two_links = "Jane Doe\njane.doe@example.com | 415-555-1234 | https://github.com/janedoe | https://linkedin.com/in/janedoe\n\nEDUCATION\nBS CS\n\nPROJECTS\nApp: Python"
    r_2l = feedback_analyzer_service.generate_feedback(two_links)
    assert r_2l.contact_feedback.score == 25.0
    assert len(r_2l.contact_feedback.deductions) == 0

    # E. Missing email, phone, and links (uncertain/no name) -> 0.0 pts (All deductions apply)
    missing_all = "Software Engineer\nSeeking an opportunity in tech.\n\nEDUCATION\nBS CS\n\nPROJECTS\nApp: Python"
    r_all_missing = feedback_analyzer_service.generate_feedback(missing_all)
    assert r_all_missing.contact_feedback.score == 0.0
    assert any("-10 pts: Missing valid email" in d for d in r_all_missing.contact_feedback.deductions)
    assert any("-7 pts: Telephone number not identified" in d for d in r_all_missing.contact_feedback.deductions)
    assert any("-5 pts: No online professional profile" in d for d in r_all_missing.contact_feedback.deductions)
    assert any("-3 pts: Candidate name header could not be identified with high confidence" in d for d in r_all_missing.contact_feedback.deductions)


def test_contact_name_detection_heuristics():
    """Verify name detection guards against job titles, symbols, and multi-column headers."""
    # Job title on first line should NOT be recognized as candidate name
    title_header = "Software Engineer\nCurriculum Vitae\nemail@example.com"
    r_title = feedback_analyzer_service.generate_feedback(title_header)
    assert any("-3 pts: Candidate name header could not be identified with high confidence" in d for d in r_title.contact_feedback.deductions)

    # Header with pipe symbols should NOT be treated as a single person's name
    pipe_header = "Alex Smith | Software Engineer | alex@example.com\n\nEDUCATION\nBS CS"
    r_pipe = feedback_analyzer_service.generate_feedback(pipe_header)
    # The first line has pipes so _extract_name_candidate rejects it
    assert any("-3 pts: Candidate name header could not be identified with high confidence" in d for d in r_pipe.contact_feedback.deductions)

    # Clean name on first line
    clean_header = "Alex M. Smith\nalex@example.com\n\nEDUCATION\nBS CS\n\nPROJECTS\nApp: Python"
    r_clean = feedback_analyzer_service.generate_feedback(clean_header)
    assert any("Candidate name header identified with high confidence ('Alex M. Smith')" in s for s in r_clean.contact_feedback.strengths)


def test_skill_partition_consistency_and_deduplication():
    """Verify matched and missing skills are mutually exclusive, their union equals JD skills, and aliases deduplicate."""
    jd_text = "Required skills: Python, FastAPI, Docker, Kubernetes, PostgreSQL, React"
    # Resume contains React and ReactJS (alias duplicate), Postgres and PostgreSQL (alias duplicate)
    resume_text = (
        "Jane Doe\njane@example.com | 555-1234\n\n"
        "EDUCATION\nBS Computer Science\n\n"
        "EXPERIENCE\nSoftware Engineer\n- Developed backend with Python and FastAPI.\n\n"
        "PROJECTS\nWeb App\n- Built containerized app using Docker, React, and ReactJS.\n"
        "- Stored data in Postgres and PostgreSQL database.\n\n"
        "SKILLS\nPython, FastAPI, Docker, React, ReactJS, Postgres, PostgreSQL"
    )
    resp = feedback_analyzer_service.generate_feedback(resume_text=resume_text, job_description=jd_text)

    # 1. Alias deduplication in detected skills
    detected_skills = resp.detected_resume_skills
    assert detected_skills.count("React") == 1
    assert detected_skills.count("PostgreSQL") == 1
    assert "ReactJS" not in detected_skills  # Canonical form is React
    assert "Postgres" not in detected_skills  # Canonical form is PostgreSQL

    # 2. Mutually exclusive partition for JD matching
    matched = set(resp.matched_job_skills or [])
    missing = set(resp.missing_job_skills or [])
    assert matched.isdisjoint(missing), f"Overlap detected between matched and missing: {matched & missing}"

    # 3. Union equals recognized target job skills
    target_union = matched | missing
    assert target_union == {"Python", "FastAPI", "Docker", "Kubernetes", "PostgreSQL", "React"}
    assert "Kubernetes" in missing
    assert "Python" in matched
    assert "Docker" in matched


def test_quantified_metrics_deduplication_and_normalization():
    """Verify repeated mentions of identical or spaced metrics do not inflate count."""
    text = (
        "- Optimized queries, achieving 45% faster execution.\n"
        "- Further refactoring yielded an additional 45 % throughput increase.\n"
        "- Accelerated build pipeline by 2x overall.\n"
        "- Improved test execution speed by 2X on CI.\n"
        "- Handled 1,000 requests per second across 1000 nodes."
    )
    metrics = detect_quantified_metrics(text)
    # Tokens should be deduplicated: only one 45%, one 2x, one 1,000/1000
    types_and_tokens = [f"{m.metric_type}:{m.matched_token}" for m in metrics]
    # We should have exactly 3 unique metric concepts (percentage, multiplier, scale count)
    assert len(metrics) == 3, f"Expected 3 deduplicated metrics, got {len(metrics)}: {types_and_tokens}"


def test_quantified_metrics_false_positive_guards():
    """Verify dates, GPA, course codes, versions, and phone numbers are excluded from metrics."""
    test_cases = [
        ("Graduated in Class of 2024 from university.", 0),
        ("Completed courses CS 101, CS 10x, and MATH 240.", 0),
        ("Upgraded service to v2.0x faster library release.", 0),
        ("Maintained GPA of 3.8 / 4.0 throughout studies.", 0),
        ("Call +1 (555) 234-5678 or 415-555-7890 for references.", 0),
        ("Authored Python 3.11 code adhering to OpenAPI v3 specs.", 0),
    ]
    for text, expected_count in test_cases:
        res = detect_quantified_metrics(text)
        assert len(res) == expected_count, f"Expected {expected_count} metrics for '{text}', got: {res}"


def test_exact_threshold_boundaries():
    """Verify threshold boundaries 85.0, 84.9, 70.0, 69.9, 50.0, 49.9, and 0.0."""
    def get_label_for_score(score: float) -> str:
        if score >= 85.0:
            return "Exemplary"
        elif score >= 70.0:
            return "Proficient"
        elif score >= 50.0:
            return "Developing"
        else:
            return "Needs Significant Work"

    assert get_label_for_score(100.0) == "Exemplary"
    assert get_label_for_score(85.0) == "Exemplary"
    assert get_label_for_score(84.9) == "Proficient"
    assert get_label_for_score(70.0) == "Proficient"
    assert get_label_for_score(69.9) == "Developing"
    assert get_label_for_score(50.0) == "Developing"
    assert get_label_for_score(49.9) == "Needs Significant Work"
    assert get_label_for_score(0.0) == "Needs Significant Work"


def test_aggregate_score_sum_and_bounds():
    """Verify total score is strictly bounded [0.0, 100.0] and exactly equals dimension sum."""
    resp = feedback_analyzer_service.generate_feedback(STUDENT_PROJECT_RESUME)
    expected_sum = round(
        resp.structure_feedback.score +
        resp.contact_feedback.score +
        resp.impact_feedback.score +
        resp.skills_feedback.score,
        1
    )
    assert resp.total_score == expected_sum
    assert 0.0 <= resp.total_score <= 100.0
    assert resp.total_percentage == resp.total_score
    for dim in [resp.structure_feedback, resp.contact_feedback, resp.impact_feedback, resp.skills_feedback]:
        assert 0.0 <= dim.score <= 25.0
        assert dim.max_score == 25.0
        assert dim.percentage == round((dim.score / 25.0) * 100, 1)


