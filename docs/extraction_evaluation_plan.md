# Evaluation and Benchmarking Plan: Resume Extraction Pipeline

---

## 1. Overview and Objective
This document outlines the evaluation methodology, metric definitions, and ground-truth validation plan for the Student Resume Analyzer extraction pipeline (Phase 4).

The extraction pipeline consists of:
1. **Section Boundary Detection:** Line-by-line lexical and morphological matching for 9 standard section types.
2. **Contact Information Extraction:** Conservative regex pattern matching for email, phone, LinkedIn, GitHub, and portfolio URLs.
3. **Technical Skill Extraction:** Curated dictionary and taxonomy matcher (45+ skills across 7 categories) with alias resolution and negative lookahead guards.

---

## 2. Extraction Rules and Known Architectural Limitations

### A. Section Detection Rules & Edge Cases
* **Matching Strategy:** Strictly checks candidate line strings against anchored heading patterns (`re.fullmatch`) after stripping markdown decorators (`##`, `**`) and trailing punctuation (`:`).
* **Limitations:**
  * Multi-column resume layouts (e.g. side-by-side Education and Skills) can scramble line order during PDF text stream extraction.
  * Stylized graphic headings or resumes where section names are embedded in vector graphics/images without OCR will not trigger text-based heading rules.
  * Non-standard heading names (e.g., "Where I Have Been" instead of "Experience") require explicit taxonomy alias expansion.

### B. Contact Information Rules & Edge Cases
* **Matching Strategy:** Conservative regular expressions enforcing minimum digit counts (10–13 digits for telephone numbers) and structured URL schemas.
* **Limitations:**
  * Candidate names are intentionally not inferred from the first line, as student resumes often place contact details, pronouns, or headers before or beside names.
  * International phone number formats with unusual regional prefix spacing may fail strict digit sequence bounds.

### C. Technical Skill Extraction & Baseline Nature
* **Matching Strategy:** Word-boundary token matching with negative lookaheads (`Java(?!\s*Script)`, standalone `C` boundary checks) and alias normalization (`JS` $\rightarrow$ `JavaScript`, `Postgres` $\rightarrow$ `PostgreSQL`).
* **Why Dictionary-Based Matching is a Baseline (Not Proof of High Accuracy):**
  * A dictionary-based parser serves as an empirical baseline (Information Extraction Rule Baseline). It cannot infer contextual proficiency (e.g., distinguishing "exposure to Python" from "5 years leading Python microservice development").
  * Emerging or non-cataloged technologies are not extracted unless present in the taxonomy.
  * Dictionary matching provides exact reproducibility, low computational overhead, and full explainability, making it the ideal baseline against which future fine-tuned token classification (NER) or semantic embedding models can be benchmarked.

---

## 3. Quantitative Evaluation Metrics

To rigorously evaluate extraction performance during college project defense, standard Information Extraction metrics will be computed:

### Definitions
* **True Positives ($TP$):** Entity correctly extracted by the parser matching ground-truth annotation.
* **False Positives ($FP$):** Entity extracted by the parser that was not present or incorrect in ground truth (hallucination or false token collision).
* **False Negatives ($FN$):** Entity present in ground truth that the parser failed to detect (missed skill or section).

### Metric Formulas
$$\text{Precision} = \frac{TP}{TP + FP}$$

$$\text{Recall} = \frac{TP}{TP + FN}$$

$$\text{F}_1\text{-Score} = 2 \times \frac{\text{Precision} \times \text{Recall}}{\text{Precision} + \text{Recall}}$$

For skills, Macro-F1 across categories (Programming Languages, Databases, Tools) and Micro-F1 across all token instances will be computed.

---

## 4. Ethically Sourced Evaluation Dataset Plan

### Ethical Sourcing Criteria
1. **Consent & Privacy:** No student resumes will be scraped without explicit candidate consent.
2. **Anonymization:** All test resumes must undergo synthetic de-identification (scrubbing real names, addresses, phone numbers, and replacing them with synthetic Faker/Fictitious identities).
3. **Public Academic Datasets:**
   * Benchmark candidate: Kaggle Resume Entities Dataset (Dataturks annotated format, under open academic license).
   * Licenses must be verified prior to downloading in subsequent phases.

### Annotation Procedure
1. Create a gold-standard JSON schema defining ground-truth annotations:
   ```json
   {
     "document_id": "synth_resume_001",
     "ground_truth_sections": ["education", "experience", "skills", "projects"],
     "ground_truth_contacts": {
       "email": "candidate@example.edu",
       "phone": "+1-555-0199",
       "linkedin": "https://linkedin.com/in/candidate"
     },
     "ground_truth_skills": ["Python", "FastAPI", "Docker", "PostgreSQL"]
   }
   ```
2. Annotate a balanced validation split of 50 student resumes covering diverse fields (Computer Science, Data Science, Web Development, DevOps).
3. Compare parser output against gold-standard records to generate automated Precision, Recall, and Confusion Matrices.
