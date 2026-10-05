"""Automated tests for machine learning evaluation, cross-validation integrity, metrics, and XAI explanations."""

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.schemas.ml_evaluation import (
    ClassificationMetrics,
    ConfusionMatrixData,
    EvaluationSummaryResponse,
    LocalExplanationResponse,
    ModelComparisonTable,
    ModelEvaluationResult,
)
from app.services.ml_evaluator import (
    MLEvaluatorService,
    compute_classification_metrics,
    ml_evaluator_service,
)

client = TestClient(app)


# ---------------------------------------------------------------------------
# 1. Metric Calculations & Zero Denominators
# ---------------------------------------------------------------------------


def test_compute_classification_metrics_standard():
    """Verify standard formulas for Accuracy, Precision, Recall, and F1."""
    # TP=10, TN=10, FP=2, FN=3 -> Total=25
    metrics = compute_classification_metrics(tp=10, tn=10, fp=2, fn=3)

    assert metrics.accuracy == pytest.approx(20 / 25, abs=1e-4)  # 0.80
    assert metrics.precision == pytest.approx(10 / 12, abs=1e-4)  # 0.8333
    assert metrics.recall == pytest.approx(10 / 13, abs=1e-4)  # 0.7692
    expected_f1 = 2 * (10 / 12 * 10 / 13) / (10 / 12 + 10 / 13)
    assert metrics.f1_score == pytest.approx(expected_f1, abs=1e-4)  # 0.80


def test_compute_classification_metrics_zero_denominators():
    """Verify safe handling of zero denominators in precision, recall, and F1."""
    # All predictions negative: TP=0, FP=0, TN=15, FN=10
    m_no_pos_pred = compute_classification_metrics(tp=0, tn=15, fp=0, fn=10)
    assert m_no_pos_pred.precision == 0.0
    assert m_no_pos_pred.recall == 0.0
    assert m_no_pos_pred.f1_score == 0.0
    assert m_no_pos_pred.accuracy == pytest.approx(15 / 25, abs=1e-4)

    # All actual negative: TP=0, FN=0, TN=20, FP=5
    m_no_pos_actual = compute_classification_metrics(tp=0, tn=20, fp=5, fn=0)
    assert m_no_pos_actual.precision == 0.0
    assert m_no_pos_actual.recall == 0.0
    assert m_no_pos_actual.f1_score == 0.0
    assert m_no_pos_actual.accuracy == pytest.approx(20 / 25, abs=1e-4)

    # All zeros edge case
    m_all_zero = compute_classification_metrics(tp=0, tn=0, fp=0, fn=0)
    assert m_all_zero.accuracy == 0.0
    assert m_all_zero.precision == 0.0
    assert m_all_zero.recall == 0.0
    assert m_all_zero.f1_score == 0.0


# ---------------------------------------------------------------------------
# 2. Benchmark Dataset & Stratified Splits Integrity
# ---------------------------------------------------------------------------


def test_benchmark_dataset_partition_and_balance():
    """Verify that the synthetic benchmark data is cleanly parsed into binary classes."""
    data = ml_evaluator_service.load_benchmark_data()
    assert len(data) == 25

    # Count classes: relevance >= 2 is positive (1), <= 1 is negative (0)
    positives = sum(1 for row in data if row["label"] == 1)
    negatives = sum(1 for row in data if row["label"] == 0)

    assert positives == 12, "Benchmark must have exactly 12 positive relevance examples"
    assert negatives == 13, "Benchmark must have exactly 13 negative relevance examples"
    assert positives + negatives == 25


def test_stratified_cv_splits_no_data_leakage():
    """Verify that Stratified 5-Fold CV generates disjoint test folds covering all 25 samples."""
    data = ml_evaluator_service.load_benchmark_data()
    labels = [row["label"] for row in data]
    splits = ml_evaluator_service.generate_stratified_folds(labels, n_splits=5, seed=42)

    assert len(splits) == 5

    all_test_indices = []
    for train_idx, test_idx in splits:
        # Check no overlap between train and test within any fold
        overlap = set(train_idx).intersection(set(test_idx))
        assert len(overlap) == 0, f"Data leakage detected in fold! Overlap: {overlap}"

        # Each test fold should have 5 items in a 25-item dataset
        assert len(test_idx) == 5
        assert len(train_idx) == 20

        all_test_indices.extend(test_idx)

    # Union of all test sets must cover every sample exactly once
    assert len(all_test_indices) == 25
    assert set(all_test_indices) == set(range(25)), "Test folds must completely partition the dataset"


# ---------------------------------------------------------------------------
# 3. Model Evaluation Results & Confusion Matrix Consistency
# ---------------------------------------------------------------------------


def test_all_evaluated_models_confusion_matrix_consistency():
    """Ensure that every evaluated model's metrics mathematically match its confusion matrix."""
    models_dict = ml_evaluator_service.evaluate_all_models()

    expected_models = {
        "multinomial_nb",
        "skill_overlap_baseline",
        "logistic_regression",
        "linear_svm",
        "tfidf_baseline",
    }
    assert set(models_dict.keys()) == expected_models

    for model_id, result in models_dict.items():
        cm = result.confusion_matrix
        m = result.metrics

        # Total sample count in confusion matrix must equal 25
        assert cm.total == 25, f"Model {model_id} confusion matrix total is {cm.total}, expected 25"
        assert cm.tp + cm.tn + cm.fp + cm.fn == 25

        # Mathematical verification of metrics
        calc_accuracy = (cm.tp + cm.tn) / 25.0
        assert m.accuracy == pytest.approx(calc_accuracy, abs=1e-4), (
            f"Accuracy mismatch for {model_id}: {m.accuracy} vs {calc_accuracy}"
        )

        calc_precision = cm.tp / (cm.tp + cm.fp) if (cm.tp + cm.fp) > 0 else 0.0
        assert m.precision == pytest.approx(calc_precision, abs=1e-4), (
            f"Precision mismatch for {model_id}: {m.precision} vs {calc_precision}"
        )

        calc_recall = cm.tp / (cm.tp + cm.fn) if (cm.tp + cm.fn) > 0 else 0.0
        assert m.recall == pytest.approx(calc_recall, abs=1e-4), (
            f"Recall mismatch for {model_id}: {m.recall} vs {calc_recall}"
        )

        calc_f1 = (
            2 * calc_precision * calc_recall / (calc_precision + calc_recall)
            if (calc_precision + calc_recall) > 0
            else 0.0
        )
        assert m.f1_score == pytest.approx(calc_f1, abs=1e-4), (
            f"F1 score mismatch for {model_id}: {m.f1_score} vs {calc_f1}"
        )

        # NDCG@3 should be present for rankers and models
        assert result.ranking_metric_value is not None
        assert 0.0 <= result.ranking_metric_value <= 1.0


def test_feature_importance_sorting_and_structure():
    """Verify that feature importances are properly ranked from highest to lowest."""
    models_dict = ml_evaluator_service.evaluate_all_models()

    for model_id, result in models_dict.items():
        fi = result.feature_importance
        assert len(fi) > 0, f"Model {model_id} has no feature importances"

        # Check descending order
        scores = [item.importance_score for item in fi]
        assert scores == sorted(scores, reverse=True), (
            f"Feature importances for {model_id} are not sorted descending: {scores}"
        )

        for item in fi:
            assert item.feature_name.strip() != ""
            assert item.interpretation.strip() != ""
            assert item.direction in {"positive", "negative", "neutral"}


def test_model_comparison_table_selection_rule():
    """Verify that the comparison table designates the best model according to the explicit rule."""
    summary = ml_evaluator_service.get_summary()
    comp_table = summary.comparison_table

    assert len(comp_table.rows) == 5
    best_rows = [r for r in comp_table.rows if r.is_best]
    assert len(best_rows) == 1, "Exactly one model should be marked as best"

    best_model = best_rows[0]
    assert best_model.model_id == comp_table.best_model_id
    assert comp_table.best_model_id == "multinomial_nb"
    assert "F1-score" in comp_table.selection_rule


# ---------------------------------------------------------------------------
# 4. Explainable AI (XAI) Local Explanations
# ---------------------------------------------------------------------------


def test_local_explanation_strong_match():
    """Verify XAI local explanation on a matching candidate-job description."""
    resume_text = (
        "Alice Smith - Software Engineer\n"
        "Skills: Python, FastAPI, Docker, PostgreSQL, Machine Learning, Git\n"
        "Experience: 3 years developing REST APIs and ML pipelines.\n"
        "Education: B.S. in Computer Science."
    )
    job_desc = (
        "We are looking for a Software Engineer skilled in Python, FastAPI, Docker, and PostgreSQL. "
        "A degree in Computer Science is required."
    )

    explanation = ml_evaluator_service.explain_pair(
        resume_text=resume_text,
        job_description=job_desc,
        model_id="logistic_regression",
    )

    assert isinstance(explanation, LocalExplanationResponse)
    assert explanation.prediction_label == "Relevant Match"
    assert "python" in [s.lower() for s in explanation.matched_skills]
    assert "fastapi" in [s.lower() for s in explanation.matched_skills]
    assert len(explanation.positive_factors) > 0
    assert "missing skills indicate missing evidence in the supplied text" in explanation.disclaimer.lower()


def test_local_explanation_mismatch():
    """Verify XAI local explanation on a mismatched pair highlights missing skills."""
    resume_text = (
        "Bob Jones - Graphic Designer\n"
        "Skills: Adobe Photoshop, Illustrator, Figma, Typography\n"
        "Experience: 2 years designing marketing brochures and logos."
    )
    job_desc = (
        "Senior Cloud Architect required with expertise in Kubernetes, Terraform, AWS, and Golang."
    )

    explanation = ml_evaluator_service.explain_pair(
        resume_text=resume_text,
        job_description=job_desc,
        model_id="logistic_regression",
    )

    assert isinstance(explanation, LocalExplanationResponse)
    assert explanation.prediction_label == "Not Relevant Match"
    assert len(explanation.negative_factors) > 0
    assert len(explanation.missing_skills) > 0


# ---------------------------------------------------------------------------
# 5. REST API Integration Endpoints
# ---------------------------------------------------------------------------


def test_api_evaluation_summary():
    """Verify GET /api/v1/evaluation/summary returns the complete dashboard payload."""
    response = client.get("/api/v1/evaluation/summary")
    assert response.status_code == 200

    payload = response.json()
    assert "Matching Benchmark" in payload["dataset_name"]
    assert sum(payload["class_distribution"].values()) == 25
    assert 12 in payload["class_distribution"].values()
    assert 13 in payload["class_distribution"].values()
    assert len(payload["comparison_table"]["rows"]) == 5
    assert len(payload["workflow_steps"]) >= 4
    assert "ethical_disclaimer" in payload


def test_api_get_model_details_valid():
    """Verify GET /api/v1/evaluation/models/{model_id} returns detailed evaluation."""
    for model_id in ["multinomial_nb", "skill_overlap_baseline", "logistic_regression", "linear_svm", "tfidf_baseline"]:
        resp = client.get(f"/api/v1/evaluation/models/{model_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["model_id"] == model_id
        assert "confusion_matrix" in data
        assert "feature_importance" in data
        assert "metrics" in data


def test_api_get_model_details_not_found():
    """Verify GET /api/v1/evaluation/models/unknown returns 404."""
    resp = client.get("/api/v1/evaluation/models/unsupported_transformer_v9")
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()


def test_api_local_explanation_endpoint():
    """Verify POST /api/v1/evaluation/explain returns an XAI explanation."""
    payload = {
        "resume_text": "Experienced Python developer with Django, SQL, and Docker experience.",
        "job_description": "Seeking Python and Docker engineer.",
        "model_id": "logistic_regression",
    }
    resp = client.post("/api/v1/evaluation/explain", json=payload)
    assert resp.status_code == 200

    data = resp.json()
    assert "prediction_label" in data
    assert "matched_skills" in data
    assert "feature_contributions" in data
    assert "positive_factors" in data
    assert "plain_language_explanation" in data


def test_api_local_explanation_validation_error():
    """Verify POST /api/v1/evaluation/explain fails on empty or missing body."""
    # Empty string violates min_length=1
    resp = client.post("/api/v1/evaluation/explain", json={"resume_text": "", "job_description": ""})
    assert resp.status_code == 422
