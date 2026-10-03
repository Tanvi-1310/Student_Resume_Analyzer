"""Explainable job description matching service.

Computes two distinct, transparent baseline signals:
1. TF-IDF Cosine Text Similarity (scikit-learn vectorizer fitted on the compared pair).
2. Explicit Canonical Skill Overlap (reusing the curated skill taxonomy).

CRITICAL METHODOLOGY DISCLAIMER:
- Text similarity is purely lexical; it does NOT measure candidate qualification.
- Skill overlap checks keyword presence; absence does NOT imply lack of ability.
- No hiring probability or composite black-box score is generated.
"""

from typing import List, Optional, Set, Tuple
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from app.schemas.matcher import JobMatchResponse
from app.services.skill_extractor import extract_skills


class JobMatcherService:
    """Service providing transparent, explainable job description alignment baselines."""

    def __init__(self) -> None:
        self.disclaimer = (
            "This analysis provides an interpretable lexical baseline. TF-IDF similarity "
            "measures textual overlap, and skill overlap reflects explicit keyword mentions. "
            "Keyword absence does not demonstrate lack of competency, and these metrics do not "
            "represent hiring probabilities or automated screening decisions."
        )

    def compute_text_similarity(self, resume_text: str, job_description: str) -> Tuple[float, str]:
        """Compute lexical TF-IDF cosine similarity between resume and job description.

        Returns:
            Tuple of (similarity_float_0_to_1, explanatory_string).
        """
        clean_resume = resume_text.strip()
        clean_jd = job_description.strip()

        if not clean_resume or not clean_jd:
            return 0.0, "One or both input texts are empty. Lexical similarity is 0.0."

        try:
            vectorizer = TfidfVectorizer(
                stop_words="english",
                token_pattern=r"(?u)\b\w+\b",
                ngram_range=(1, 2),
                lowercase=True,
            )
            tfidf_matrix = vectorizer.fit_transform([clean_resume, clean_jd])
            raw_sim = float(cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:2])[0][0])
            bounded_sim = max(0.0, min(1.0, raw_sim))
            rounded_sim = round(bounded_sim, 4)

            explanation = (
                f"Lexical TF-IDF cosine similarity is {rounded_sim:.4f} (or {rounded_sim * 100:.1f}%). "
                "This value reflects shared unigram and bigram vocabulary between the resume "
                "and job description text, bounded strictly between 0.0 and 1.0."
            )
            return rounded_sim, explanation
        except ValueError:
            # Raised if vocabulary is completely empty (e.g. text contains only punctuation/stop words)
            return 0.0, (
                "Insufficient content tokens after stop-word filtering to compute vocabulary vectors. "
                "Lexical similarity defaulted to 0.0."
            )

    def match(
        self,
        resume_text: str,
        job_description: str,
        resume_filename: str = "resume.pdf",
    ) -> JobMatchResponse:
        """Perform dual-signal comparison between resume and job description.

        Args:
            resume_text: Extracted text from resume document.
            job_description: Target job posting or internship specification.
            resume_filename: Original document filename for tracking.

        Returns:
            JobMatchResponse containing independent text similarity and skill overlap signals.
        """
        # Signal A: Lexical TF-IDF Cosine Similarity
        text_sim, text_sim_exp = self.compute_text_similarity(resume_text, job_description)

        # Signal B: Explicit Skill Set Overlap
        resume_skill_evidences, _ = extract_skills(resume_text)
        jd_skill_evidences, _ = extract_skills(job_description)

        resume_skills_set: Set[str] = {s.name for s in resume_skill_evidences}
        jd_skills_set: Set[str] = {s.name for s in jd_skill_evidences}

        matched_skills: List[str] = sorted(list(resume_skills_set & jd_skills_set))
        missing_skills: List[str] = sorted(list(jd_skills_set - resume_skills_set))
        additional_skills: List[str] = sorted(list(resume_skills_set - jd_skills_set))

        total_jd_skills = len(jd_skills_set)
        if total_jd_skills > 0:
            overlap_ratio: Optional[float] = round(len(matched_skills) / total_jd_skills, 4)
            skill_exp = (
                f"Detected {len(matched_skills)} of {total_jd_skills} canonical technical skills "
                f"specified in the job description ({overlap_ratio * 100:.1f}% overlap ratio)."
            )
        else:
            overlap_ratio = None
            skill_exp = (
                "The job description did not contain any recognized canonical technical skills "
                "from the standard taxonomy. A skill overlap ratio cannot be calculated (division by zero avoided)."
            )

        return JobMatchResponse(
            resume_filename=resume_filename,
            text_similarity=text_sim,
            text_similarity_explanation=text_sim_exp,
            skill_overlap_ratio=overlap_ratio,
            skill_overlap_explanation=skill_exp,
            matched_skills=matched_skills,
            missing_skills=missing_skills,
            additional_skills=additional_skills,
            job_description_skills=sorted(list(jd_skills_set)),
            resume_skills=sorted(list(resume_skills_set)),
            methodology_disclaimer=self.disclaimer,
        )


# Singleton instance
job_matcher_service = JobMatcherService()
