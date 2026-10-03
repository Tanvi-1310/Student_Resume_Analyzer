"""Explainable, rule-based resume feedback rubric service.

Evaluates student resumes across four transparent dimensions:
1. Resume Structure (hierarchy, headings, student-relevant practical sections)
2. Contact Completeness (email, phone, professional links, header confidence)
3. Quantified Impact (concrete numerical outcomes in project & experience bullets)
4. Skill-Taxonomy Coverage (breadth or role-specific job alignment)

IMPORTANT ETHICAL & ACADEMIC NOTICE:
This service is an explainable resume-improvement aid. It is:
- NOT a validated ATS score.
- NOT a hiring probability or candidate qualification prediction.
- NOT an employability score or interview likelihood estimator.
Every deduction is backed by identifiable evidence and practical student recommendations.
"""

import re
from typing import Dict, List, Optional, Set, Tuple

from app.schemas.feedback import (
    DimensionFeedback,
    QuantifiedMetricEvidence,
    ResumeFeedbackResponse,
)
from app.services.job_matcher import job_matcher_service
from app.services.resume_parser import resume_parser_service


# ---------------------------------------------------------------------------
# Quantified Impact Detection Patterns & Exclusion Guards
# ---------------------------------------------------------------------------

PERCENTAGE_PATTERN = re.compile(r"(?<![a-zA-Z0-9_])\b\d+(?:\.\d+)?\s*%", re.IGNORECASE)
MULTIPLIER_PATTERN = re.compile(r"(?<![a-zA-Z0-9_.])\b\d+(?:\.\d+)?\s*[xX]\b")
CURRENCY_PATTERN = re.compile(r"[\$€£]\s*\d+(?:,\d{3})*(?:\.\d+)?(?:\s*[kKmMbB])?")

SCALE_COUNT_PATTERN = re.compile(
    r"(?<![a-zA-Z0-9_])\b\d+(?:,\d{3})*(?:\.\d+)?\s*(?:k|m|b|\+)?\s*(?:requests|users|queries|records|customers|clients|downloads|students|participants|stars|commits|benchmarks|views|visitors|endpoints|lines of code|loc)\b",
    re.IGNORECASE,
)

PERFORMANCE_DELTA_PATTERN = re.compile(
    r"\b(?:reduced|decreased|improved|increased|boosted|saved|cut|accelerated|dropped)\s+[^.\n]*?\b\d+(?:\.\d+)?\s*(?:%|ms|seconds|minutes|hours|days|weeks|percent)\b",
    re.IGNORECASE,
)

# Exclusion guards: patterns that contain numbers but do NOT indicate achievement metrics
YEAR_PATTERN = re.compile(r"\b(?:19|20)\d{2}\b")
PHONE_LIKE_PATTERN = re.compile(
    r"\+?\d{1,3}[-.\s]?\(?\d{2,4}\)?[-.\s]?\d{3,4}[-.\s]?(?:\d{4}|\b)(?:\s*(?:ext|x)\s*\d+)?",
    re.IGNORECASE,
)
VERSION_NUMBER_PATTERN = re.compile(
    r"\b(?:Python|Java|HTML|CSS|ECMAScript|OAuth|C|v|version)\s*v?\d+(?:\.\d+)*\w*\b|\bv\d+(?:\.\d+)*\w*\b",
    re.IGNORECASE,
)
COURSE_CODE_PATTERN = re.compile(r"\b(?:CS|CSE|MATH|PHYS|CHEM|ENG|STAT)\s*\d+[a-zA-Z]?\b", re.IGNORECASE)
GPA_PATTERN = re.compile(
    r"\b(?:GPA|gpa)\s*[:=]?\s*\d+(?:\.\d+)?(?:\s*\/\s*\d+(?:\.\d+)?)?\b|\b\d+(?:\.\d+)?\s*\/\s*\d+(?:\.\d+)?\s*(?:GPA|gpa)\b",
    re.IGNORECASE,
)

DISALLOWED_NAME_WORDS = {
    "software", "engineer", "developer", "intern", "analyst", "consultant",
    "manager", "lead", "specialist", "scientist", "student", "undergraduate",
    "graduate", "curriculum", "vitae", "resume", "profile", "portfolio",
    "objective", "summary", "contact", "experience", "education", "skills",
    "projects", "university", "college", "school", "bachelor", "master", "phd",
}


def _get_exclusion_spans(line: str) -> List[Tuple[int, int]]:
    """Identify text spans corresponding to non-achievement numbers."""
    spans: List[Tuple[int, int]] = []
    for pattern in [
        YEAR_PATTERN,
        PHONE_LIKE_PATTERN,
        VERSION_NUMBER_PATTERN,
        COURSE_CODE_PATTERN,
        GPA_PATTERN,
    ]:
        for m in pattern.finditer(line):
            spans.append((m.start(), m.end()))
    return spans


def _overlaps_exclusion(start: int, end: int, exclusion_spans: List[Tuple[int, int]]) -> bool:
    """Return True if match interval [start, end] intersects any exclusion span."""
    return any(max(start, exc_s) < min(end, exc_e) for exc_s, exc_e in exclusion_spans)


def _normalize_metric_token(token: str) -> str:
    """Normalize metric token string for deduplication (case-insensitive, whitespace-trimmed)."""
    norm = token.lower().strip()
    norm = re.sub(r"\s+", "", norm)
    norm = norm.replace(",", "")
    return norm


def detect_quantified_metrics(text: str) -> List[QuantifiedMetricEvidence]:
    """Scan text for verified concrete quantified metrics while applying exclusion guards."""
    results: List[QuantifiedMetricEvidence] = []
    seen_normalized_tokens: Set[str] = set()

    lines = [line.strip() for line in text.split("\n") if line.strip()]

    for line in lines:
        exclusion_spans = _get_exclusion_spans(line)
        line_matched_spans: List[Tuple[int, int]] = []

        # 1. Check percentages
        for match in PERCENTAGE_PATTERN.finditer(line):
            if _overlaps_exclusion(match.start(), match.end(), exclusion_spans):
                continue
            token = match.group(0).strip()
            norm = _normalize_metric_token(token)
            if norm not in seen_normalized_tokens:
                seen_normalized_tokens.add(norm)
                line_matched_spans.append((match.start(), match.end()))
                results.append(
                    QuantifiedMetricEvidence(
                        metric_type="percentage",
                        matched_token=token,
                        bullet_snippet=line,
                    )
                )

        # 2. Check multipliers
        for match in MULTIPLIER_PATTERN.finditer(line):
            if _overlaps_exclusion(match.start(), match.end(), exclusion_spans):
                continue
            token = match.group(0).strip()
            norm = _normalize_metric_token(token)
            if norm not in seen_normalized_tokens:
                seen_normalized_tokens.add(norm)
                line_matched_spans.append((match.start(), match.end()))
                results.append(
                    QuantifiedMetricEvidence(
                        metric_type="multiplier",
                        matched_token=token,
                        bullet_snippet=line,
                    )
                )

        # 3. Check scale counts
        for match in SCALE_COUNT_PATTERN.finditer(line):
            if _overlaps_exclusion(match.start(), match.end(), exclusion_spans):
                continue
            token = match.group(0).strip()
            norm = _normalize_metric_token(token)
            if norm not in seen_normalized_tokens:
                seen_normalized_tokens.add(norm)
                line_matched_spans.append((match.start(), match.end()))
                results.append(
                    QuantifiedMetricEvidence(
                        metric_type="scale_count",
                        matched_token=token,
                        bullet_snippet=line,
                    )
                )

        # 4. Check currency metrics
        for match in CURRENCY_PATTERN.finditer(line):
            if _overlaps_exclusion(match.start(), match.end(), exclusion_spans):
                continue
            token = match.group(0).strip()
            norm = _normalize_metric_token(token)
            if norm not in seen_normalized_tokens:
                seen_normalized_tokens.add(norm)
                line_matched_spans.append((match.start(), match.end()))
                results.append(
                    QuantifiedMetricEvidence(
                        metric_type="currency",
                        matched_token=token,
                        bullet_snippet=line,
                    )
                )

        # 5. Check performance deltas
        for match in PERFORMANCE_DELTA_PATTERN.finditer(line):
            if _overlaps_exclusion(match.start(), match.end(), exclusion_spans):
                continue
            # Avoid double-counting if a percentage on this line was already matched
            if any(max(match.start(), s) < min(match.end(), e) for s, e in line_matched_spans):
                continue
            token = match.group(0).strip()
            norm = _normalize_metric_token(token)
            if norm not in seen_normalized_tokens:
                seen_normalized_tokens.add(norm)
                line_matched_spans.append((match.start(), match.end()))
                results.append(
                    QuantifiedMetricEvidence(
                        metric_type="performance_delta",
                        matched_token=token,
                        bullet_snippet=line,
                    )
                )

    return results


def _extract_name_candidate(text: str) -> Optional[str]:
    """Examine initial text lines to identify candidate name with reasonable confidence.

    Adheres strictly to privacy principles: does not infer identity from uncertain text,
    disallows job titles or section labels from being recognized as names, and never logs
    or exports personal identity data.
    """
    lines = [line.strip() for line in text.split("\n") if line.strip()]
    if not lines:
        return None

    # Inspect first 2 non-empty lines
    for line in lines[:2]:
        # Disallow lines with email, phone, URLs, pipes, bullets, colons, or slashes
        if any(c in line for c in ("@", "http", "www.", ".com", ":", "|", "•", "▪", "►", "*", "/")):
            continue
        if any(c.isdigit() for c in line):
            continue

        words = line.split()
        if not (2 <= len(words) <= 4):
            continue

        # Reject if any word is a common title, section, or resume buzzword
        lower_words = [w.lower().rstrip(".,") for w in words]
        if any(w in DISALLOWED_NAME_WORDS for w in lower_words):
            continue

        # Ensure all words begin with an uppercase letter
        if all(w[0].isupper() for w in words if w):
            return line

    return None


class FeedbackAnalyzerService:
    """Service evaluating student resumes across four transparent feedback dimensions."""

    def __init__(self) -> None:
        self.disclaimer = (
            "This Resume Feedback Index is an explainable, rule-based pedagogical rubric designed to "
            "guide student formatting and content improvements. It is NOT an automated ATS screening score, "
            "a hiring probability, an employability rating, or a validated predictor of recruitment outcomes. "
            "Evaluations reflect heuristic rule compliance across four transparent dimensions."
        )

    def evaluate_resume(
        self,
        resume_text: str,
        job_description: Optional[str] = None,
        resume_filename: str = "resume.pdf",
    ) -> ResumeFeedbackResponse:
        """Execute four-dimension heuristic evaluation on resume text.

        Args:
            resume_text: Extracted text from resume document.
            job_description: Optional target job description to evaluate role-specific alignment.
            resume_filename: Associated document filename for tracking.

        Returns:
            ResumeFeedbackResponse containing dimension breakdowns, evidence, and recommendations.
        """
        clean_resume = resume_text.strip()
        parsed_resume = resume_parser_service.parse_resume_text(clean_resume, filename=resume_filename)

        # -------------------------------------------------------------------
        # Dimension 1: Resume Structure (Max: 25 pts)
        # -------------------------------------------------------------------
        struct_score = 0.0
        struct_strengths: List[str] = []
        struct_deductions: List[str] = []
        struct_suggestions: List[str] = []

        # A. Usable content baseline (5 pts)
        words = clean_resume.split()
        if len(clean_resume) >= 100 and len(words) >= 20:
            struct_score += 5.0
            struct_strengths.append("Extracted content contains sufficient substantive text for structural parsing.")
        else:
            struct_deductions.append("-5 pts: Content is extremely brief (< 20 words); insufficient substantive text for full evaluation.")
            struct_suggestions.append("Ensure your resume contains complete descriptive text rather than brief fragments.")

        # B. Educational and Practical Foundation (10 pts)
        sec_keys = set(parsed_resume.detected_section_keys)
        has_edu = "education" in sec_keys
        has_exp = "experience" in sec_keys
        has_proj = "projects" in sec_keys

        if has_edu:
            struct_score += 5.0
            struct_strengths.append("Identified dedicated 'Education' section.")
        else:
            struct_deductions.append("-5 pts: Missing recognized 'Education' section.")
            struct_suggestions.append("Add a clear 'Education' section specifying degree program, expected graduation date, and coursework.")

        # Students: Projects or research are valid practical equivalents to professional employment
        if has_exp:
            struct_score += 5.0
            struct_strengths.append("Identified dedicated 'Experience' section.")
        elif has_proj:
            struct_score += 5.0
            struct_strengths.append("Identified dedicated 'Projects' section (excellent practical foundation for student candidates).")
            struct_suggestions.append("Academic and personal projects effectively demonstrate technical capability in lieu of corporate experience.")
        else:
            struct_deductions.append("-5 pts: Missing both 'Experience' and 'Projects' sections.")
            struct_suggestions.append("Include an 'Academic Projects' or 'Personal Projects' section to demonstrate practical application of skills.")

        # C. Heading Organization and Segmentation (10 pts)
        sec_count = len(parsed_resume.detected_section_keys)
        if sec_count >= 3:
            struct_score += 10.0
            struct_strengths.append(f"Clear section hierarchy with {sec_count} recognized headings ({', '.join(parsed_resume.detected_section_keys)}).")
        elif sec_count == 2:
            struct_score += 7.0
            struct_deductions.append("-3 pts: Limited section segmentation (only 2 recognized headings).")
            struct_suggestions.append("Segment your resume into distinct sections (e.g., 'Education', 'Projects', 'Technical Skills', 'Experience').")
        elif sec_count == 1:
            struct_score += 4.0
            struct_deductions.append("-6 pts: Minimal section segmentation (only 1 recognized heading).")
            struct_suggestions.append("Use standard, clear section headings to help automated parsers and human reviewers navigate your resume.")
        else:
            struct_deductions.append("-10 pts: No standard section headings detected; document parsed as unsegmented text.")
            struct_suggestions.append("Organize your resume with bold, standardized section headers (e.g. 'EDUCATION', 'PROJECTS', 'SKILLS').")

        struct_score = min(25.0, max(0.0, struct_score))
        struct_status = "Strong" if struct_score >= 20 else ("Proficient" if struct_score >= 14 else "Needs Attention")
        structure_feedback = DimensionFeedback(
            dimension_name="Resume Structure",
            score=struct_score,
            max_score=25.0,
            percentage=round((struct_score / 25.0) * 100, 1),
            status=struct_status,
            summary=f"Evaluated document hierarchy and core sections ({sec_count} detected sections).",
            strengths=struct_strengths,
            deductions=struct_deductions,
            suggestions=struct_suggestions,
        )

        # -------------------------------------------------------------------
        # Dimension 2: Contact Completeness (Max: 25 pts)
        # -------------------------------------------------------------------
        contact_score = 0.0
        contact_strengths: List[str] = []
        contact_deductions: List[str] = []
        contact_suggestions: List[str] = []
        contact = parsed_resume.contact_info

        # A. Email address (10 pts)
        if contact.email:
            contact_score += 10.0
            contact_strengths.append("Valid candidate email address identified.")
        else:
            contact_deductions.append("-10 pts: Missing valid email address.")
            contact_suggestions.append("Include a professional email address (e.g., university or personal email) prominently near the top.")

        # B. Phone number (7 pts)
        if contact.phone:
            contact_score += 7.0
            contact_strengths.append("Valid telephone number identified.")
        else:
            contact_deductions.append("-7 pts: Telephone number not identified.")
            contact_suggestions.append("Include a direct contact phone number with area code (or omit intentionally if privacy is preferred).")

        # C. Professional Profile Links (5 pts)
        links = []
        if contact.linkedin_url:
            links.append("LinkedIn")
        if contact.github_url:
            links.append("GitHub")
        if contact.portfolio_url:
            links.append("Portfolio")

        if len(links) >= 2:
            contact_score += 5.0
            contact_strengths.append(f"Identified online professional profile(s): {', '.join(links)}.")
        elif len(links) == 1:
            contact_score += 3.0
            contact_strengths.append(f"Identified online professional profile: {links[0]}.")
            contact_deductions.append("-2 pts: Only 1 online professional link identified (consider providing both GitHub and LinkedIn or a portfolio link).")
            contact_suggestions.append("Adding a second professional link (e.g. GitHub for code and LinkedIn for professional context) demonstrates breadth.")
        else:
            contact_deductions.append("-5 pts: No online professional profile (GitHub, LinkedIn, or Portfolio) identified.")
            contact_suggestions.append("Add clickable links to your GitHub profile, LinkedIn, or personal portfolio to showcase active code.")

        # D. Name Header Confidence (3 pts)
        name_candidate = _extract_name_candidate(clean_resume)
        if name_candidate:
            contact_score += 3.0
            contact_strengths.append(f"Candidate name header identified with high confidence ('{name_candidate}').")
        else:
            contact_deductions.append("-3 pts: Candidate name header could not be identified with high confidence (first line may contain title, contact details, or multi-column layout).")
            contact_suggestions.append("Place your full name as the first line of the document in prominent, clean text without titles or contact details on the same line.")

        contact_score = min(25.0, max(0.0, round(contact_score, 1)))
        contact_status = "Strong" if contact_score >= 20.0 else ("Proficient" if contact_score >= 14.0 else "Needs Attention")
        contact_feedback = DimensionFeedback(
            dimension_name="Contact Completeness",
            score=contact_score,
            max_score=25.0,
            percentage=round((contact_score / 25.0) * 100, 1),
            status=contact_status,
            summary=f"Evaluated communication coordinates ({len(links)} online profile links detected).",
            strengths=contact_strengths,
            deductions=contact_deductions,
            suggestions=contact_suggestions,
        )

        # -------------------------------------------------------------------
        # Dimension 3: Quantified Impact (Max: 25 pts)
        # -------------------------------------------------------------------
        impact_score = 0.0
        impact_strengths: List[str] = []
        impact_deductions: List[str] = []
        impact_suggestions: List[str] = []

        # Extract text from relevant experience and project sections
        practical_text_chunks: List[str] = []
        for key in ["experience", "projects", "research", "work"]:
            if key in parsed_resume.detected_sections:
                sec_obj = parsed_resume.detected_sections[key]
                practical_text_chunks.append(sec_obj.raw_text)

        practical_text = "\n".join(practical_text_chunks)
        # If no dedicated sections detected, fall back to entire text
        search_text = practical_text if practical_text.strip() else clean_resume
        quantified_metrics = detect_quantified_metrics(search_text)

        metric_count = len(quantified_metrics)
        if metric_count >= 3:
            impact_score = 25.0
            impact_strengths.append(f"Exemplary demonstration of measurable outcomes ({metric_count} concrete metrics detected).")
        elif metric_count == 2:
            impact_score = 20.0
            impact_strengths.append(f"Good quantitative evidence ({metric_count} concrete metrics detected).")
            impact_deductions.append("-5 pts: Could benefit from additional quantified achievement metrics across projects.")
            impact_suggestions.append("Add 1-2 more quantified impact metrics (e.g. performance speedups, user counts, test coverage).")
        elif metric_count == 1:
            impact_score = 14.0
            impact_strengths.append(f"Identified 1 concrete metric: '{quantified_metrics[0].matched_token}'.")
            impact_deductions.append("-11 pts: Limited quantifiable evidence across project and experience bullets.")
            impact_suggestions.append("Transform qualitative descriptions into measurable achievements using counts, percentages, or scale metrics.")
        elif practical_text.strip():
            impact_score = 5.0
            impact_deductions.append("-20 pts: Project and experience bullets are purely narrative with no concrete quantified impact metrics detected.")
            impact_suggestions.append(
                "Quantify your accomplishments using the XYZ formula: 'Accomplished [X] as measured by [Y], by doing [Z]' "
                "(e.g., 'Reduced query latency by 28%', 'Handled 1,500 requests/min', 'Automated 45 test cases')."
            )
        else:
            impact_score = 0.0
            impact_deductions.append("-25 pts: No project or experience text detected to evaluate measurable outcomes.")
            impact_suggestions.append("Add an 'Academic Projects' or 'Work Experience' section with bullet points highlighting your accomplishments.")

        impact_score = min(25.0, max(0.0, impact_score))
        impact_status = "Strong" if impact_score >= 20 else ("Proficient" if impact_score >= 14 else "Needs Attention")
        impact_feedback = DimensionFeedback(
            dimension_name="Quantified Impact",
            score=impact_score,
            max_score=25.0,
            percentage=round((impact_score / 25.0) * 100, 1),
            status=impact_status,
            summary=f"Evaluated measurable outcomes across practical bullets ({metric_count} verified metrics recognized).",
            strengths=impact_strengths,
            deductions=impact_deductions,
            suggestions=impact_suggestions,
        )

        # -------------------------------------------------------------------
        # Dimension 4: Skill-Taxonomy Coverage (Max: 25 pts)
        # -------------------------------------------------------------------
        skill_score = 0.0
        skill_strengths: List[str] = []
        skill_deductions: List[str] = []
        skill_suggestions: List[str] = []

        has_supplied_jd = bool(job_description and job_description.strip())
        jd_skills_count: Optional[int] = None
        matched_job_skills: Optional[List[str]] = None
        missing_job_skills: Optional[List[str]] = None
        detected_resume_skills = [s.name for s in parsed_resume.skills]

        if has_supplied_jd:
            # Mode A: Role-Specific Job Alignment
            match_res = job_matcher_service.match(clean_resume, job_description.strip(), resume_filename=resume_filename)
            jd_skills_count = len(match_res.job_description_skills)
            matched_job_skills = match_res.matched_skills
            missing_job_skills = match_res.missing_skills

            if jd_skills_count > 0:
                ratio = len(matched_job_skills) / jd_skills_count
                skill_score = round(ratio * 25.0, 1)
                skill_strengths.append(
                    f"Matched {len(matched_job_skills)} of {jd_skills_count} recognized target skills "
                    f"({ratio * 100:.1f}%): {', '.join(matched_job_skills)}."
                )
                if missing_job_skills:
                    skill_deductions.append(
                        f"-{25.0 - skill_score:.1f} pts: Missing {len(missing_job_skills)} target skills "
                        f"specified in the job description: {', '.join(missing_job_skills)}."
                    )
                    skill_suggestions.append(
                        f"Review target skills ({', '.join(missing_job_skills[:4])}). If you possess "
                        "coursework or project experience in these areas, explicitly mention them. "
                        "Do NOT add skills you have not actually used."
                    )
            else:
                # Job description contained zero technical skills; fall back to general breadth
                skill_strengths.append(
                    "Target job description specified 0 recognized technical skills from our taxonomy; "
                    "evaluated general taxonomy breadth as fallback."
                )
                skill_suggestions.append(
                    "Include concrete technical requirements (e.g. languages, frameworks, developer tools) "
                    "in the target job description to evaluate role-specific alignment."
                )

        if not has_supplied_jd or jd_skills_count == 0:
            # Mode B: General Taxonomy Breadth
            res_skills = parsed_resume.skills
            cat_count = len(parsed_resume.skills_by_category)
            skill_count = len(res_skills)
            skill_names = [s.name for s in res_skills]

            if skill_count >= 6 and cat_count >= 2:
                skill_score = 25.0
                skill_strengths.append(
                    f"Broad technical coverage ({skill_count} canonical skills across {cat_count} categories: {', '.join(skill_names)})."
                )
            elif skill_count >= 4 and cat_count >= 2:
                skill_score = 20.0
                skill_strengths.append(
                    f"Good technical coverage ({skill_count} canonical skills across {cat_count} categories: {', '.join(skill_names)})."
                )
                skill_deductions.append("-5 pts: Moderate technical taxonomy breadth.")
                skill_suggestions.append(
                    "Consider expanding technical breadth by incorporating complementary databases or cloud toolkits utilized in projects."
                )
            elif skill_count >= 2:
                skill_score = 14.0
                skill_strengths.append(f"Identified {skill_count} technical skills: {', '.join(skill_names)}.")
                skill_deductions.append("-11 pts: Limited technical skill diversity detected.")
                skill_suggestions.append(
                    "Incorporate additional tools, frameworks, and databases utilized in coursework or projects."
                )
            elif skill_count == 1:
                skill_score = 8.0
                skill_strengths.append(f"Identified 1 technical skill: {skill_names[0]}.")
                skill_deductions.append("-17 pts: Only 1 recognized technical skill detected.")
                skill_suggestions.append(
                    "Create a dedicated 'Technical Skills' section categorizing languages, frameworks, databases, and developer tools."
                )
            else:
                skill_score = 0.0
                skill_deductions.append("-25 pts: No canonical technical skills from standard taxonomy detected.")
                skill_suggestions.append(
                    "List technical proficiencies (e.g. Python, SQL, Git, Docker) in an easily readable 'Technical Skills' section."
                )

        skill_score = min(25.0, max(0.0, round(skill_score, 1)))
        skill_status = "Strong" if skill_score >= 20.0 else ("Proficient" if skill_score >= 14.0 else "Needs Attention")

        if has_supplied_jd and jd_skills_count and jd_skills_count > 0:
            summary_text = f"Evaluated role-specific skill alignment ({len(matched_job_skills or [])}/{jd_skills_count} target skills matched)."
        elif has_supplied_jd:
            summary_text = f"Target job description contained 0 recognized taxonomy skills; evaluated general taxonomy breadth ({len(parsed_resume.skills)} skills detected)."
        else:
            summary_text = f"Evaluated general technical taxonomy breadth ({len(parsed_resume.skills)} skills detected across {len(parsed_resume.skills_by_category)} categories)."

        skills_feedback = DimensionFeedback(
            dimension_name="Skill-Taxonomy Coverage",
            score=skill_score,
            max_score=25.0,
            percentage=round((skill_score / 25.0) * 100, 1),
            status=skill_status,
            summary=summary_text,
            strengths=skill_strengths,
            deductions=skill_deductions,
            suggestions=skill_suggestions,
        )

        # -------------------------------------------------------------------
        # Overall Heuristic Index & Prioritized Recommendations
        # -------------------------------------------------------------------
        total_score = round(struct_score + contact_score + impact_score + skill_score, 1)
        total_score = min(100.0, max(0.0, total_score))
        total_percentage = round((total_score / 100.0) * 100, 1)

        if total_score >= 85.0:
            index_label = "Exemplary"
        elif total_score >= 70.0:
            index_label = "Proficient"
        elif total_score >= 50.0:
            index_label = "Developing"
        else:
            index_label = "Needs Significant Work"

        # Prioritize suggestions from dimensions with lowest percentage scores
        dim_pairs = [
            (structure_feedback.percentage, struct_suggestions),
            (contact_feedback.percentage, contact_suggestions),
            (impact_feedback.percentage, impact_suggestions),
            (skills_feedback.percentage, skill_suggestions),
        ]
        dim_pairs.sort(key=lambda item: item[0])  # Lowest percentage first

        prioritized_recs: List[str] = []
        for _, suggestions in dim_pairs:
            for s in suggestions:
                if s not in prioritized_recs:
                    prioritized_recs.append(s)

        if not prioritized_recs:
            prioritized_recs.append(
                "All heuristic checks passed strongly. Continue refining bullet points with role-specific keywords and active verbs tailored to each job application."
            )

        return ResumeFeedbackResponse(
            resume_filename=resume_filename,
            total_score=total_score,
            total_max_score=100.0,
            total_percentage=total_percentage,
            index_label=index_label,
            structure_feedback=structure_feedback,
            contact_feedback=contact_feedback,
            impact_feedback=impact_feedback,
            skills_feedback=skills_feedback,
            quantified_metrics_detected=quantified_metrics,
            prioritized_recommendations=prioritized_recs[:5],  # Top 5 prioritized recommendations
            detected_resume_skills=detected_resume_skills,
            has_job_description=has_supplied_jd,
            job_description_skills_count=jd_skills_count if has_supplied_jd else None,
            matched_job_skills=matched_job_skills if has_supplied_jd else None,
            missing_job_skills=missing_job_skills if has_supplied_jd else None,
            methodology_disclaimer=self.disclaimer,
        )

    # Alias for API endpoint and test consistency
    generate_feedback = evaluate_resume


# Singleton instance
feedback_analyzer_service = FeedbackAnalyzerService()
