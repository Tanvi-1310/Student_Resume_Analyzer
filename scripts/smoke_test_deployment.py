"""Deployment verification smoke-test script for Student Resume Analyzer.

Validates that a live deployment (local or remote Render instance) correctly serves:
1. Public frontend dashboard (GET /)
2. Application health endpoint (GET /health)
3. In-memory PDF resume extraction (POST /api/v1/resumes/extract)
4. In-memory DOCX resume extraction (POST /api/v1/resumes/extract)
5. Structured entity & skill analysis (POST /api/v1/resumes/analyze-text)
6. Job description matching (POST /api/v1/resumes/match)
7. Explainable feedback rubric (POST /api/v1/resumes/feedback)

Usage:
    python scripts/smoke_test_deployment.py --base-url https://student-resume-analyzer.onrender.com
    python scripts/smoke_test_deployment.py --base-url http://127.0.0.1:8000
"""

import argparse
import io
import os
import sys
from typing import Any, Dict, List, Tuple
import httpx
from docx import Document


def generate_minimal_text_pdf(lines: List[str]) -> bytes:
    """Generate minimal valid PDF bytes containing text lines without third-party dependencies."""
    stream_content = (
        "BT /F1 12 Tf 16 TL 72 700 Td "
        + " ".join(f"({line}) Tj T*" for line in lines)
        + " ET"
    )
    stream_bytes = stream_content.encode("latin1")
    length = len(stream_bytes)
    pdf = f"""%PDF-1.4
1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj
2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj
3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >> endobj
4 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj
5 0 obj << /Length {length} >> stream
{stream_content}
endstream
endobj
xref
0 6
0000000000 65535 f 
0000000009 00000 n 
0000000058 00000 n 
0000000115 00000 n 
0000000244 00000 n 
0000000323 00000 n 
trailer << /Size 6 /Root 1 0 R >>
startxref
{430 + length}
%%EOF
"""
    return pdf.encode("latin1")


def generate_minimal_text_docx(paragraphs: List[str]) -> bytes:
    """Generate minimal valid DOCX bytes using python-docx."""
    doc = Document()
    for p in paragraphs:
        doc.add_paragraph(p)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def run_smoke_test(base_url: str) -> bool:
    """Execute end-to-end smoke test against the target base URL."""
    base = base_url.rstrip("/")
    print("=" * 70)
    print(f"STUDENT RESUME ANALYZER — DEPLOYMENT SMOKE TEST")
    print(f"Target URL: {base}")
    print("=" * 70)

    client = httpx.Client(timeout=30.0, follow_redirects=True)
    all_passed = True

    # 1. Frontend Test
    print("\n[1/7] Testing Public Frontend Landing Page (GET /)...")
    try:
        resp = client.get(f"{base}/")
        if resp.status_code == 200 and "Student Resume Analyzer" in resp.text:
            print(f"  PASS: HTTP 200 OK — Landing page loaded successfully ({len(resp.text)} bytes).")
        else:
            print(f"  FAIL: HTTP {resp.status_code} — Expected page content not found.")
            all_passed = False
    except Exception as exc:
        print(f"  FAIL: Request error: {exc}")
        all_passed = False

    # 2. Health Endpoint Test
    print("\n[2/7] Testing Operational Health Endpoint (GET /health)...")
    try:
        resp = client.get(f"{base}/health")
        if resp.status_code == 200:
            data = resp.json()
            if data.get("status") == "ok":
                print(f"  PASS: HTTP 200 OK — status='ok', app='{data.get('app')}', v{data.get('version')}.")
            else:
                print(f"  FAIL: Expected status='ok', got: {data}")
                all_passed = False
        else:
            print(f"  FAIL: HTTP {resp.status_code}: {resp.text}")
            all_passed = False
    except Exception as exc:
        print(f"  FAIL: Request error: {exc}")
        all_passed = False

    # 3. PDF Resume Extraction Test
    print("\n[3/7] Testing PDF Upload Extraction (POST /api/v1/resumes/extract)...")
    pdf_text_extracted = ""
    try:
        pdf_lines = [
            "Alex Morgan",
            "Email: alex.morgan@example.edu | Phone: +1-555-0101 | GitHub: github.com/alexmorgan",
            "Education",
            "Bachelor of Science in Computer Science, University of Technology",
            "Experience",
            "Software Intern: Built scalable backend services with Python, FastAPI, and PostgreSQL.",
            "Technical Skills",
            "Python, FastAPI, PostgreSQL, Docker, Git",
        ]
        pdf_bytes = generate_minimal_text_pdf(pdf_lines)
        files = {
            "file": (
                "smoke_test_resume.pdf",
                pdf_bytes,
                "application/pdf",
            )
        }
        resp = client.post(f"{base}/api/v1/resumes/extract", files=files)
        if resp.status_code == 200:
            data = resp.json()
            pdf_text_extracted = data.get("extracted_text", "")
            if len(pdf_text_extracted) > 20:
                print(f"  PASS: HTTP 200 OK — Extracted {data.get('character_count')} chars, {data.get('word_count')} words from PDF.")
            else:
                print(f"  FAIL: Extracted text is too short or empty: '{pdf_text_extracted}'")
                all_passed = False
        else:
            print(f"  FAIL: HTTP {resp.status_code}: {resp.text}")
            all_passed = False
    except Exception as exc:
        print(f"  FAIL: Request error: {exc}")
        all_passed = False

    # 4. DOCX Resume Extraction Test
    print("\n[4/7] Testing DOCX Upload Extraction (POST /api/v1/resumes/extract)...")
    try:
        docx_lines = [
            "Jane Doe",
            "Email: jane.doe@example.edu | Phone: +1-555-0199 | LinkedIn: linkedin.com/in/janedoe",
            "Education",
            "B.S. in Software Engineering, State University",
            "Experience",
            "Junior Web Developer: Engineered frontend interfaces and web backends using TypeScript, React, and Python.",
            "Technical Skills",
            "TypeScript, React, Python, HTML, CSS, Git",
        ]
        docx_bytes = generate_minimal_text_docx(docx_lines)
        files = {
            "file": (
                "smoke_test_resume.docx",
                docx_bytes,
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        }
        resp = client.post(f"{base}/api/v1/resumes/extract", files=files)
        if resp.status_code == 200:
            data = resp.json()
            docx_text = data.get("extracted_text", "")
            if len(docx_text) > 20:
                print(f"  PASS: HTTP 200 OK — Extracted {data.get('character_count')} chars, {data.get('word_count')} words from DOCX.")
            else:
                print(f"  FAIL: Extracted text is too short or empty: '{docx_text}'")
                all_passed = False
        else:
            print(f"  FAIL: HTTP {resp.status_code}: {resp.text}")
            all_passed = False
    except Exception as exc:
        print(f"  FAIL: Request error: {exc}")
        all_passed = False

    # Standard test payload for downstream endpoints
    test_resume_text = (
        pdf_text_extracted
        if len(pdf_text_extracted) > 50
        else (
            "Alex Morgan\nEmail: alex.morgan@example.edu | Phone: +1-555-0101 | GitHub: github.com/alexmorgan\n\n"
            "Education\nBachelor of Science in Computer Science\n\n"
            "Experience\nSoftware Engineer Intern at CloudTech: Engineered REST APIs using Python, FastAPI, and PostgreSQL. "
            "Automated Docker builds and improved performance by 35%.\n\n"
            "Technical Skills\nPython, FastAPI, PostgreSQL, Docker, Git"
        )
    )

    test_jd_text = (
        "Backend Developer Opening\n"
        "Requirements:\n"
        "• Strong proficiency in Python and FastAPI.\n"
        "• Experience working with PostgreSQL databases and Docker containers.\n"
        "• Working knowledge of Git version control."
    )

    # 5. Structured Parsing & Entity Analysis Test
    print("\n[5/7] Testing Structured Analysis (POST /api/v1/resumes/analyze-text)...")
    try:
        payload = {
            "text": test_resume_text,
            "filename": "smoke_resume.pdf",
        }
        resp = client.post(f"{base}/api/v1/resumes/analyze-text", json=payload)
        if resp.status_code == 200:
            data = resp.json()
            skills_found = data.get("skills", [])
            sections_found = data.get("detected_section_keys", [])
            print(f"  PASS: HTTP 200 OK — Sections: {sections_found}, Skills: {skills_found}.")
        else:
            print(f"  FAIL: HTTP {resp.status_code}: {resp.text}")
            all_passed = False
    except Exception as exc:
        print(f"  FAIL: Request error: {exc}")
        all_passed = False

    # 6. Job Description Matching Test
    print("\n[6/7] Testing Job Matching (POST /api/v1/resumes/match)...")
    try:
        payload = {
            "resume_text": test_resume_text,
            "job_description": test_jd_text,
            "resume_filename": "smoke_resume.pdf",
        }
        resp = client.post(f"{base}/api/v1/resumes/match", json=payload)
        if resp.status_code == 200:
            data = resp.json()
            sim = data.get("text_similarity")
            overlap = data.get("skill_overlap_ratio")
            matched = data.get("matched_skills", [])
            print(f"  PASS: HTTP 200 OK — TF-IDF Similarity: {sim:.4f}, Skill Overlap: {overlap:.4f}, Matched: {matched}.")
        else:
            print(f"  FAIL: HTTP {resp.status_code}: {resp.text}")
            all_passed = False
    except Exception as exc:
        print(f"  FAIL: Request error: {exc}")
        all_passed = False

    # 7. Formative Feedback Rubric Test
    print("\n[7/9] Testing Feedback Rubric (POST /api/v1/resumes/feedback)...")
    try:
        payload = {
            "resume_text": test_resume_text,
            "job_description": test_jd_text,
            "resume_filename": "smoke_resume.pdf",
        }
        resp = client.post(f"{base}/api/v1/resumes/feedback", json=payload)
        if resp.status_code == 200:
            data = resp.json()
            total_score = data.get("total_score")
            index_label = data.get("index_label")
            metrics_count = len(data.get("quantified_metrics_detected", []))
            print(f"  PASS: HTTP 200 OK — Total Score: {total_score}/100 ({index_label}), Quantified Metrics: {metrics_count}.")
        else:
            print(f"  FAIL: HTTP {resp.status_code}: {resp.text}")
            all_passed = False
    except Exception as exc:
        print(f"  FAIL: Request error: {exc}")
        all_passed = False

    # 8. ML Evaluation Summary Test
    print("\n[8/9] Testing ML Evaluation Summary (GET /api/v1/evaluation/summary)...")
    try:
        resp = client.get(f"{base}/api/v1/evaluation/summary")
        if resp.status_code == 200:
            data = resp.json()
            dataset_size = data.get("dataset_size")
            best_model = data.get("comparison_table", {}).get("best_model_name")
            print(f"  PASS: HTTP 200 OK — Benchmark Pairs: {dataset_size}, Top Model: '{best_model}'.")
        else:
            print(f"  FAIL: HTTP {resp.status_code}: {resp.text}")
            all_passed = False
    except Exception as exc:
        print(f"  FAIL: Request error: {exc}")
        all_passed = False

    # 9. Explainable AI Local Match Explanation Test
    print("\n[9/9] Testing Explainable AI Local Explainer (POST /api/v1/evaluation/explain)...")
    try:
        payload = {
            "resume_text": test_resume_text,
            "job_description": test_jd_text,
            "model_id": "logistic_regression",
        }
        resp = client.post(f"{base}/api/v1/evaluation/explain", json=payload)
        if resp.status_code == 200:
            data = resp.json()
            pred_label = data.get("prediction_label")
            prob = data.get("prediction_probability")
            pos_count = len(data.get("positive_factors", []))
            neg_count = len(data.get("negative_factors", []))
            print(f"  PASS: HTTP 200 OK — Label: '{pred_label}' (p={prob:.3f}), Positive Drivers: {pos_count}, Negative Drivers: {neg_count}.")
        else:
            print(f"  FAIL: HTTP {resp.status_code}: {resp.text}")
            all_passed = False
    except Exception as exc:
        print(f"  FAIL: Request error: {exc}")
        all_passed = False

    print("\n" + "=" * 70)
    if all_passed:
        print("ALL SMOKE TESTS PASSED: Live deployment is operational.")
        print("=" * 70)
        return True
    else:
        print("SMOKE TEST FAILED: One or more endpoints returned errors.")
        print("=" * 70)
        return False


def main() -> None:
    parser = argparse.ArgumentParser(description="Deployment smoke test for Student Resume Analyzer.")
    parser.add_argument(
        "--base-url",
        type=str,
        default=os.environ.get("DEPLOYMENT_BASE_URL", "http://127.0.0.1:8000"),
        help="Base URL of deployed service (e.g. https://student-resume-analyzer.onrender.com).",
    )
    args = parser.parse_args()
    success = run_smoke_test(args.base_url)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
