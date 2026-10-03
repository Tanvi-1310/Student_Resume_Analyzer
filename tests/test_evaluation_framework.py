"""Automated tests for Phase 7 evaluation framework, grouped ranking metrics, and embedding baseline."""

import math
from pathlib import Path
from unittest.mock import MagicMock
import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.embedding_matcher import SemanticEmbeddingMatcher, semantic_embedding_matcher
from scripts.evaluate_matching import (
    REPO_ROOT,
    validate_benchmark_record,
    load_and_validate_dataset,
    compute_set_metrics,
    aggregate_metrics,
    _compute_fractional_ranks,
    compute_spearman_correlation,
    compute_dcg,
    compute_ndcg,
    evaluate_signal_within_groups,
    run_evaluation,
)

client = TestClient(app)
BENCHMARK_PATH = REPO_ROOT / "data" / "evaluation" / "synthetic_matching_benchmark.json"


# ---------------------------------------------------------------------------
# 1. Dataset Schema and Grouped Validation Tests
# ---------------------------------------------------------------------------

def test_benchmark_dataset_schema_conformance():
    """Verify that the version-controlled benchmark JSON loads and has 0 skipped records."""
    assert BENCHMARK_PATH.exists(), f"Benchmark file missing at {BENCHMARK_PATH}"
    valid_examples, skipped_examples, metadata = load_and_validate_dataset(BENCHMARK_PATH)

    assert len(valid_examples) == 25, f"Expected exactly 25 evaluation examples, got {len(valid_examples)}"
    assert len(skipped_examples) == 0, f"Expected 0 skipped examples, got: {skipped_examples}"
    assert metadata["schema_version"] == "1.0.0"
    assert "relevance_scale" in metadata
    assert metadata["annotator_metadata"]["annotator_count"] == 1


def test_benchmark_dataset_grouped_structure():
    """Verify that the benchmark contains 5 job groups with exactly 5 candidates each."""
    valid_examples, _, _ = load_and_validate_dataset(BENCHMARK_PATH)

    groups = {}
    for ex in valid_examples:
        gid = ex["job_group_id"]
        groups.setdefault(gid, []).append(ex)

    assert len(groups) == 5, f"Expected 5 distinct job groups, found {len(groups)}"
    for gid, cands in groups.items():
        assert len(cands) == 5, f"Group {gid} has {len(cands)} candidates; expected 5"
        # Verify that all candidates in the group share the exact same job description
        jds = {c["job_description"] for c in cands}
        assert len(jds) == 1, f"Candidates in {gid} do not share the same job description"


def test_validate_benchmark_record_rejections():
    """Verify that malformed records, missing fields, and out-of-range labels are rejected."""
    valid_record = {
        "example_id": "TEST-001",
        "job_group_id": "JOB-GRP-TEST",
        "category": "unit_test",
        "resume_text": "Sample resume text with Python.",
        "job_description": "Sample JD requiring Python.",
        "annotated_job_skills": ["Python"],
        "annotated_resume_skills": ["Python"],
        "expected_matched_skills": ["Python"],
        "expected_missing_skills": [],
        "human_relevance_label": 3,
        "rationale": "Perfect match for testing.",
        "annotation_status": "reviewed",
    }

    # Valid record passes
    is_valid, err = validate_benchmark_record(valid_record)
    assert is_valid is True
    assert err is None

    # Missing job_group_id
    missing_gid = dict(valid_record)
    del missing_gid["job_group_id"]
    is_valid, err = validate_benchmark_record(missing_gid)
    assert is_valid is False
    assert "Missing required key: 'job_group_id'" in err

    # Out of bounds label
    bad_label = dict(valid_record, human_relevance_label=5)
    is_valid, err = validate_benchmark_record(bad_label)
    assert is_valid is False
    assert "Invalid human_relevance_label" in err

    # Label wrong type (float)
    float_label = dict(valid_record, human_relevance_label=2.5)
    is_valid, err = validate_benchmark_record(float_label)
    assert is_valid is False
    assert "must be integer" in err

    # List contains non-string
    bad_list = dict(valid_record, annotated_job_skills=["Python", 123])
    is_valid, err = validate_benchmark_record(bad_list)
    assert is_valid is False
    assert "must contain only strings" in err

    # Non-dict record
    is_valid, err = validate_benchmark_record(["not", "a", "dict"])
    assert is_valid is False
    assert "not a JSON object" in err


# ---------------------------------------------------------------------------
# 2. Metric Calculations on Small Hand-Computable Examples
# ---------------------------------------------------------------------------

def test_compute_set_metrics_hand_computable():
    """Verify precision, recall, and F1 calculation against an exact hand-computed case."""
    ground_truth = {"Python", "Docker", "PostgreSQL"}
    predicted = {"Python", "Docker", "FastAPI"}

    # TP = {"Python", "Docker"} -> 2
    # FP = {"FastAPI"} -> 1
    # FN = {"PostgreSQL"} -> 1
    # Precision = 2/3 ≈ 0.6667, Recall = 2/3 ≈ 0.6667, F1 = 2/3 ≈ 0.6667
    metrics = compute_set_metrics(predicted, ground_truth)
    assert metrics["tp"] == 2
    assert metrics["fp"] == 1
    assert metrics["fn"] == 1
    assert metrics["precision"] == 0.6667
    assert metrics["recall"] == 0.6667
    assert metrics["f1"] == 0.6667


def test_set_metrics_edge_cases_empty_and_disjoint():
    """Verify edge cases: both empty, one empty, and disjoint sets."""
    both_empty = compute_set_metrics(set(), set())
    assert both_empty["precision"] == 1.0
    assert both_empty["recall"] == 1.0
    assert both_empty["f1"] == 1.0

    pred_only = compute_set_metrics({"Python"}, set())
    assert pred_only["precision"] == 0.0
    assert pred_only["recall"] == 0.0
    assert pred_only["f1"] == 0.0

    truth_only = compute_set_metrics(set(), {"Python"})
    assert truth_only["precision"] == 0.0
    assert truth_only["recall"] == 0.0
    assert truth_only["f1"] == 0.0


def test_aggregate_metrics_macro_and_micro():
    """Verify macro vs micro aggregation on a hand-computable 2-example fixture."""
    ex1 = {"tp": 2, "fp": 0, "fn": 0, "precision": 1.0, "recall": 1.0, "f1": 1.0}
    ex2 = {"tp": 1, "fp": 1, "fn": 1, "precision": 0.5, "recall": 0.5, "f1": 0.5}

    agg = aggregate_metrics([ex1, ex2])
    assert agg["macro_precision"] == 0.75
    assert agg["macro_recall"] == 0.75
    assert agg["macro_f1"] == 0.75
    assert agg["micro_precision"] == 0.75
    assert agg["micro_recall"] == 0.75
    assert agg["micro_f1"] == 0.75


# ---------------------------------------------------------------------------
# 3. Within-Group Ranking Tests (Ties, Constant Groups, and Aggregation)
# ---------------------------------------------------------------------------

def test_fractional_ranks_handling_ties():
    """Verify that tied values receive the arithmetic average of their rank positions."""
    values = [10.0, 20.0, 20.0, 40.0]
    ranks = _compute_fractional_ranks(values)
    assert ranks == [1.0, 2.5, 2.5, 4.0]


def test_spearman_correlation_edge_cases():
    """Verify Spearman correlation with perfect monotonic, inverse monotonic, and zero variance."""
    x_mono = [1.0, 2.0, 3.0, 4.0]
    y_mono = [10.0, 20.0, 30.0, 40.0]
    assert compute_spearman_correlation(x_mono, y_mono) == 1.0

    y_inv = [40.0, 30.0, 20.0, 10.0]
    assert compute_spearman_correlation(x_mono, y_inv) == -1.0

    # Zero variance in one vector (all values identical) returns None
    x_const = [5.0, 5.0, 5.0, 5.0]
    assert compute_spearman_correlation(x_const, y_mono) is None


def test_ndcg_hand_computable():
    """Verify NDCG calculation on hand-computable relevance cases."""
    labels_perfect = [3, 2, 1, 0]
    scores_perfect = [0.9, 0.7, 0.4, 0.1]
    assert compute_ndcg(scores_perfect, labels_perfect) == 1.0

    # Reverse ranking
    labels_rev = [3, 0]
    scores_rev = [0.1, 0.9]
    ndcg_rev = compute_ndcg(scores_rev, labels_rev)
    assert 0.63 <= ndcg_rev <= 0.64


def test_evaluate_signal_within_groups_hand_computable():
    """Verify within-group ranking evaluation across two hand-computable job groups."""
    groups_data = {
        "GRP-1": [
            {"example_id": "C1", "text_similarity": 0.8, "human_relevance_label": 3},
            {"example_id": "C2", "text_similarity": 0.5, "human_relevance_label": 2},
            {"example_id": "C3", "text_similarity": 0.1, "human_relevance_label": 0},
        ],
        "GRP-2": [
            # Group with constant scores (zero variance)
            {"example_id": "C4", "text_similarity": 0.5, "human_relevance_label": 2},
            {"example_id": "C5", "text_similarity": 0.5, "human_relevance_label": 1},
            {"example_id": "C6", "text_similarity": 0.5, "human_relevance_label": 0},
        ],
    }

    result = evaluate_signal_within_groups(groups_data, "text_similarity", k_cutoff=2)

    assert result["total_groups_evaluated"] == 2
    # GRP-1 has perfect monotonic order -> Spearman = 1.0, NDCG = 1.0
    # GRP-2 has constant scores -> Spearman is skipped; NDCG is computed with ties
    assert result["valid_spearman_groups_count"] == 1
    assert result["skipped_spearman_groups_count"] == 1
    assert result["mean_within_group_spearman_rho"] == 1.0
    assert result["skipped_spearman_groups_details"][0]["job_group_id"] == "GRP-2"
    assert "Zero score variance" in result["skipped_spearman_groups_details"][0]["reason"]


# ---------------------------------------------------------------------------
# 4. Optional Semantic Embedding Baseline Tests
# ---------------------------------------------------------------------------

def test_embedding_matcher_availability_api():
    """Verify that SemanticEmbeddingMatcher provides safe availability and diagnostic checks."""
    matcher = SemanticEmbeddingMatcher()
    is_avail = matcher.is_available()
    assert isinstance(is_avail, bool)

    if not is_avail:
        reason = matcher.get_unavailable_reason()
        assert reason is not None
        assert "pip install sentence-transformers torch" in reason
        with pytest.raises(RuntimeError) as exc_info:
            matcher.compute_similarity("Resume text", "Job description")
        assert "sentence-transformers" in str(exc_info.value)


def test_embedding_matcher_mock_computation():
    """Verify vector normalization and dot-product similarity logic using mock embeddings."""
    matcher = SemanticEmbeddingMatcher()
    # Mock SentenceTransformer model returning unit vectors
    mock_model = MagicMock()
    # Return two orthogonal vectors (dot product = 0.0)
    mock_model.encode.return_value = np.array([
        [1.0, 0.0, 0.0],
        [0.0, 1.0, 0.0],
    ])
    matcher._model = mock_model

    sim, exp = matcher.compute_similarity("Developer with Python", "Looking for React developer")
    assert sim == 0.0
    assert "0.0000" in exp

    # Return two identical vectors (dot product = 1.0)
    mock_model.encode.return_value = np.array([
        [0.6, 0.8, 0.0],
        [0.6, 0.8, 0.0],
    ])
    sim_identical, _ = matcher.compute_similarity("Same text", "Same text")
    assert 0.999 <= sim_identical <= 1.0


# ---------------------------------------------------------------------------
# 5. Determinism, CLI Evaluation Runner, and API Contracts
# ---------------------------------------------------------------------------

def test_deterministic_repeated_execution():
    """Verify that multiple evaluation runs on the benchmark yield identical output."""
    res1 = run_evaluation(quiet=True)
    res2 = run_evaluation(quiet=True)

    assert res1["execution_summary"] == res2["execution_summary"]
    assert res1["skill_extraction_evaluation"] == res2["skill_extraction_evaluation"]
    assert res1["grouped_ranking_evaluation"] == res2["grouped_ranking_evaluation"]


def test_run_evaluation_include_embeddings_graceful():
    """Verify that --include-embeddings runs safely without crashing even if dependencies are missing."""
    res = run_evaluation(include_embeddings=True, quiet=True)
    assert "grouped_ranking_evaluation" in res
    emb = res["grouped_ranking_evaluation"]["semantic_embedding_similarity"]
    assert emb["status"] in {"available", "unavailable"}


def test_api_match_endpoint_contract_unbroken():
    """Verify that POST /api/v1/resumes/match retains its full contract during Phase 7."""
    payload = {
        "resume_text": "Experienced Python and FastAPI backend developer with PostgreSQL.",
        "job_description": "Seeking Python and FastAPI engineer with PostgreSQL.",
        "resume_filename": "candidate.pdf",
    }
    response = client.post("/api/v1/resumes/match", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert "text_similarity" in data
    assert "skill_overlap_ratio" in data
    assert "matched_skills" in data
    assert "missing_skills" in data
    assert "additional_skills" in data
    assert "job_description_skills" in data
    assert "resume_skills" in data
    assert "methodology_disclaimer" in data
    assert data["matched_skills"] == ["FastAPI", "PostgreSQL", "Python"]


def test_api_analyze_text_endpoint_contract_unbroken():
    """Verify that POST /api/v1/resumes/analyze-text continues to pass its contract."""
    payload = {
        "text": "Jane Doe\nEmail: jane@example.com\n\nSkills\nPython, Docker, SQL",
        "filename": "jane.pdf",
    }
    response = client.post("/api/v1/resumes/analyze-text", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "contact_info" in data
    assert "detected_section_keys" in data
    assert "skills" in data
    assert "skills_by_category" in data
