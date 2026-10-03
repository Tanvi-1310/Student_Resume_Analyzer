# Evaluation and Benchmarking Plan: Explainable Job Description Matching Baseline

---

## 1. Overview and Objective
This document outlines the evaluation methodology, mathematical definitions, academic qualifications, and benchmarking roadmap for the **Student Resume Analyzer Matching Framework (Phases 5, 6 & 7)**.

The framework implements:
1. **Explainable Baseline Signals:**
   - **Lexical TF-IDF Text Cosine Similarity:** Unsupervised statistical term-frequency and inverse-document-frequency similarity over unigrams and bigrams.
   - **Explicit Canonical Skill Overlap:** Deterministic dictionary-based matching identifying common technical skills, skills required by the job description but not detected on the resume, and additional candidate competencies.
   - **Optional Dense Semantic Embeddings:** Pretrained bi-encoder sentence embeddings (`sentence-transformers/all-MiniLM-L6-v2`) computing vector cosine proximity.
2. **Within-Job-Group Evaluation Pipeline (`scripts/evaluate_matching.py`):**
   - Version-controlled grouped benchmark fixture (`data/evaluation/synthetic_matching_benchmark.json`) comprising 5 shared job postings with 5 candidate resumes each (25 candidate–job pairs).
   - Standard Information Extraction metrics (Micro- and Macro-averaged Precision, Recall, and F1) on skill sets.
   - Grouped within-job ranking evaluation (Mean Grouped NDCG@K and Mean Within-Group Spearman's rank correlation $\rho$).

---

## 2. Signal Definitions and Mathematical Formulations

### A. TF-IDF Text Cosine Similarity

#### Mathematical Definition
Given the vocabulary $V$ formed by the unigrams and bigrams of the resume text $d_{\text{resume}}$ and job description $d_{\text{jd}}$ (with English stop words removed), each document is represented as a real-valued vector $\mathbf{u}, \mathbf{v} \in \mathbb{R}^{|V|}$ where each coordinate represents the term frequency–inverse document frequency (TF-IDF) weight:

$$\text{TF-IDF}(t, d) = \text{TF}(t, d) \times \left( \ln \frac{1 + N}{1 + \text{DF}(t)} + 1 \right)$$

where $N = 2$ and $\text{DF}(t)$ is the number of documents containing term $t$.

The cosine similarity is defined as the dot product of the $L_2$-normalized vectors:

$$\text{Cosine Similarity}(\mathbf{u}, \mathbf{v}) = \frac{\mathbf{u} \cdot \mathbf{v}}{\|\mathbf{u}\|_2 \|\mathbf{v}\|_2} = \sum_{i=1}^{|V|} \hat{u}_i \hat{v}_i$$

The output value is bounded in $[0.0, 1.0]$. If either input consists exclusively of stop words, whitespace, or empty strings such that the vocabulary is empty, the similarity defaults safely to $0.0$.

#### What TF-IDF Cosine Similarity Measures
* **Statistical Lexical Overlap:** Measures how frequently specific vocabulary words and two-word technical phrases (e.g., `"machine learning"`, `"rest api"`) co-occur in both documents relative to document length.
* **Topic Salience:** Downweights frequent generic English words while highlighting shared domain-specific terminology.

#### What TF-IDF Cosine Similarity Does NOT Measure
* **Semantic Paraphrasing:** Cannot recognize that *"distributed datastore"* and *"Cassandra cluster"* refer to compatible architectural competencies without token overlap.
* **Semantic Negation or Context:** Gives positive weight to a term even if used negatively (e.g., *"not seeking front-end roles"* vs *"front-end developer required"*).
* **Candidate Quality or Accomplishment:** Cannot differentiate between a student listing a term in a class project and a seasoned engineer describing high-impact production scale.
* **Section Relevance:** Treats all occurrences uniformly regardless of whether a word appears under Education, Experience, or Interests.

---

### B. Explicit Skill Overlap Ratio

#### Mathematical Definition
Let $S_{\text{resume}}$ be the set of canonical technical skills detected in the resume text, and let $S_{\text{jd}}$ be the set of canonical technical skills detected in the job description:

$$S_{\text{matched}} = S_{\text{resume}} \cap S_{\text{jd}}$$

$$S_{\text{missing}} = S_{\text{jd}} \setminus S_{\text{resume}}$$

$$S_{\text{additional}} = S_{\text{resume}} \setminus S_{\text{jd}}$$

The **Skill Overlap Ratio** $R_{\text{overlap}}$ is computed as:

$$R_{\text{overlap}} = \frac{|S_{\text{matched}}|}{|S_{\text{jd}}|}$$

#### Division by Zero Safeguard
If the job description contains zero recognized skills from the canonical taxonomy ($|S_{\text{jd}}| = 0$):
* $R_{\text{overlap}} = \text{null}$ (`None` in Python / `null` in JSON).
* A transparent explanation is returned: *"No recognized skills detected in the job description; skill overlap ratio is undefined."*
* The system avoids arbitrary default values (such as $0.0$ or $1.0$) that would mislead candidates or downstream processes.

---

### C. Optional Semantic Embedding Baseline

#### Mathematical Formulation
When optional dependencies are available, candidate resume text $d_{\text{resume}}$ and job description text $d_{\text{jd}}$ are encoded into 384-dimensional dense vectors using `sentence-transformers/all-MiniLM-L6-v2`:

$$\mathbf{e}_{\text{resume}} = \text{Encoder}(d_{\text{resume}}), \quad \mathbf{e}_{\text{jd}} = \text{Encoder}(d_{\text{jd}})$$

Each vector is unit normalized using Euclidean norm ($\|\mathbf{e}\|_2 = 1.0$), reducing cosine similarity to the dot product:

$$\text{Embedding Similarity}(\mathbf{e}_{\text{resume}}, \mathbf{e}_{\text{jd}}) = \mathbf{e}_{\text{resume}} \cdot \mathbf{e}_{\text{jd}} = \sum_{k=1}^{384} e_{\text{resume}, k} \cdot e_{\text{jd}, k}$$

The output is bounded strictly in $[0.0, 1.0]$.

#### Requirements and Dependency Setup
* Optional Extra: Not required for core application startup or standard evaluation.
* Installation:
  ```powershell
  pip install sentence-transformers torch
  ```
* Reproducibility Disclosure: Dense embedding numerical values can exhibit subtle floating-point variations across CPU architectures, PyTorch library builds, and CUDA drivers. Exact cross-machine reproduction requires pinning the model revision (`all-MiniLM-L6-v2`) and underlying runtime versions.

---

## 3. Evaluation Benchmark Fixture: Within-Job Group Design

### Why Within-Job-Group Ranking is Mathematically Required
In information retrieval and recruitment search, ranking metrics such as NDCG and Spearman's rank correlation are defined per query. Comparing candidate scores across *different* job descriptions in a single global list introduces confounding bias:
* Different roles have different requirement densities (e.g. 6 skills vs. 2 skills).
* A candidate with score 0.5 for a frontend job cannot be meaningfully ranked against a candidate with score 0.4 for a backend job.
* True candidate evaluation reflects how a candidate pool is ranked for a **single specific vacancy**.

### Benchmark Group Structure
The benchmark fixture (`data/evaluation/synthetic_matching_benchmark.json`) organizes 25 synthetic candidate pairs into **5 distinct job groups** with 5 candidates per group:

1. **`JOB-GRP-01`**: Junior Backend Web Developer (Python, FastAPI, PostgreSQL, Docker, Git)
2. **`JOB-GRP-02`**: Frontend Web Engineer (TypeScript, JavaScript, React, HTML, CSS)
3. **`JOB-GRP-03`**: Machine Learning Research Intern (Python, PyTorch, TensorFlow, Scikit-learn)
4. **`JOB-GRP-04`**: Cloud Infrastructure & DevOps Engineer (Kubernetes, Docker, AWS, Linux, Terraform)
5. **`JOB-GRP-05`**: Administrative Office Coordinator (Non-Technical Role with zero taxonomy skills)

Every candidate in a group is evaluated against the **exact identical job description**.

### Graded Human Relevance Scale (0–3)
* **3 (Highly Relevant / Strong Match):** Substantial technical alignment with the primary required stack, relevant project/work experiences, and domain context.
* **2 (Moderately Relevant / Partial Match):** Demonstrates related technical foundations and several required skills, but lacks one or more critical core requirements.
* **1 (Weakly Relevant / Minimal Match):** Tangential overlap or surface words only; candidate focus is in an unrelated area or specialization.
* **0 (Irrelevant / Disjoint / Degenerate):** Unrelated domain, missing core requirements entirely, or empty/malformed text.

---

## 4. Quantitative Evaluation Metric Definitions

### A. Information Extraction Metrics (Skill Sets)
For candidate resume skills ($S_{\text{res}}$), job description skills ($S_{\text{jd}}$), and matched skills ($S_{\text{match}}$):
* $TP = |P \cap G|$ (Predicted skills matching ground-truth annotations)
* $FP = |P \setminus G|$ (Spurious/hallucinated skill extractions)
* $FN = |G \setminus P|$ (Unextracted/missed canonical skills)

#### Edge Case Rules
* If both predicted and ground-truth sets are empty ($|P| = 0, |G| = 0$): $P = 1.0, R = 1.0, F_1 = 1.0$.
* If $TP = 0$ and either set is non-empty: $P = 0.0, R = 0.0, F_1 = 0.0$.
* Otherwise: $P = \frac{TP}{|P|}, \quad R = \frac{TP}{|G|}, \quad F_1 = \frac{2 P R}{P + R}$.

#### Aggregation Methods
1. **Macro-Averaging (Unweighted Example Mean):**
   $$\text{Macro-Metric} = \frac{1}{N} \sum_{i=1}^N \text{Metric}_i$$
2. **Micro-Averaging (Pooled Instance Aggregation):**
   $$\text{Micro-Precision} = \frac{\sum_i TP_i}{\sum_i (TP_i + FP_i)}, \quad \text{Micro-Recall} = \frac{\sum_i TP_i}{\sum_i (TP_i + FN_i)}$$

---

### B. Grouped Within-Job Ranking Metrics

For each job group $g \in G$:

#### 1. Grouped NDCG@K
Within group $g$, candidates are sorted by predicted score descending (with stable secondary tie-breaking on `example_id`):

$$\text{DCG}@K(g) = \sum_{r=1}^K \frac{2^{y_{\pi(r)}} - 1}{\log_2(r + 1)}, \quad \text{IDCG}@K(g) = \sum_{r=1}^K \frac{2^{y^*_r} - 1}{\log_2(r + 1)}, \quad \text{NDCG}@K(g) = \frac{\text{DCG}@K(g)}{\text{IDCG}@K(g)}$$

The overall grouped metric is the mean across all $|G|$ groups:

$$\text{Mean Grouped NDCG}@K = \frac{1}{|G|} \sum_{g \in G} \text{NDCG}@K(g)$$

#### 2. Within-Group Spearman's Rank Correlation ($\rho$)
Within group $g$, Spearman's $\rho(g)$ is computed on fractional average ranks:
* Tied score values receive the average of their assigned rank positions.
* **Skip Condition:** If either the score vector or the human label vector in group $g$ has **zero variance** (all values equal, e.g. `JOB-GRP-05` where skill overlap is undefined for all candidates), correlation is mathematically undefined. Group $g$ is explicitly skipped and recorded in the diagnostic log.
* The reported mean is computed over all valid groups $G_{\text{valid}}$:

$$\text{Mean Within-Group Spearman } \rho = \frac{1}{|G_{\text{valid}}|} \sum_{g \in G_{\text{valid}}} \rho(g)$$

---

## 5. Academic Defense: Why Matching Values Are NOT Hiring Probabilities

> [!WARNING]
> **Ethical & Academic Disclaimer:**
> Neither the TF-IDF similarity score, skill overlap ratio, nor dense embedding similarity represents candidate qualification, job suitability, hiring probability, or a validated Applicant Tracking System (ATS) score.

1. **Keyword Absence is Not Proof of Incompetence:** A student may have built distributed systems in Go without explicitly typing the word *"Docker"* or *"Microservices"* into their resume. Automated keyword omission does not equate to lack of underlying computer science capability.
2. **Context and Depth are Ignored:** Two resumes with identical counts for `"Python"` could represent a student who completed an introductory homework assignment versus one who built an open-source library. Lexical counting is context-blind.
3. **Unequal Requirement Importance:** Real-world job descriptions have mandatory requirements (*"Must have 4 years React experience"*) and optional preferences (*"Nice to have: Docker"*). The baseline treats all recognized skills with equal unweighted unit importance.
4. **Vulnerability to Keyword Stuffing:** Unsupervised lexical matching can be trivially gamed by repeating target keywords or pasting job descriptions in white font—vulnerabilities that modern recruitment tools guard against.
5. **No Discriminatory Bias Validation:** Machine learning models trained on historical hiring data inherit human hiring biases. The current baseline intentionally avoids black-box predictive models and presents unweighted, transparent counts to ensure accountability.

---

## 6. Evaluator Disclosures and Bias Analysis

### A. Synthetic Software Tests vs. Real-World Validation
* All 25 examples in `data/evaluation/synthetic_matching_benchmark.json` are **synthetic software test fixtures** engineered to verify software code paths, schema boundaries, edge cases, and deterministic arithmetic.
* They demonstrate how the evaluation pipeline functions; they do **not** constitute an empirical sample of real-world candidate populations or validated hiring outcomes.

### B. Single-Annotator Disclosure
* Ground-truth labels were generated and reviewed by a single technical evaluator (`primary_evaluator_01`).
* **Limitation:** Inter-annotator agreement metrics (such as Cohen's $\kappa$ or Fleiss' $\kappa$) cannot be computed without multiple independent double-blind annotators.

### C. Potential Algorithmic Biases
1. **Bias Against Nontraditional Backgrounds:** Self-taught developers or students from multidisciplinary backgrounds often use narrative problem-solving descriptions rather than dense industry buzzwords. Lexical matchers unfairly penalize these candidates.
2. **Writing Style Sensitivity:** Highly formatted, bulleted resumes featuring standard headings ("Technical Skills", "Experience") are parsed accurately; narrative prose or non-chronological portfolios suffer high omission rates.
3. **Layout Sensitivity:** Multi-column creative resume formats can cause text stream interleaving during PDF extraction, breaking sentence context.

---

## 7. Future Plan for Externally Sourced Academic Dataset

To transition from synthetic verification to empirical academic validation, the following protocol will be followed:

1. **Dataset Provenance & Licensing:**
   - Candidate resource: Public academic resume datasets released under permissive open licenses (e.g. Kaggle Dataturks Resume Entities under Creative Commons CC BY-SA 4.0).
   - Ingestion will require verified license terms and public repository provenance.
2. **Strict Anonymization & Privacy Preservation:**
   - Automated Personally Identifiable Information (PII) scrubbing removing real names, residential addresses, contact numbers, email domains, and employer names.
   - Replacement with synthetic Faker entities to guarantee zero student data leakage.
3. **Multi-Annotator Protocol:**
   - Dual-annotator double-blind labeling of resume–job description pairs on the 0–3 relevance scale.
   - Reporting Cohen's $\kappa$ inter-rater reliability prior to benchmark publication.
