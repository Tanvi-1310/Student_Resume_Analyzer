"""Pydantic schemas for ML evaluation, feature importance, and Explainable AI (XAI)."""

from typing import Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class ClassificationMetrics(BaseModel):
    """Standard classification performance metrics calculated from evaluation data."""

    model_config = ConfigDict(frozen=True)

    accuracy: float = Field(..., ge=0.0, le=1.0, description="Accuracy: (TP + TN) / Total")
    precision: float = Field(..., ge=0.0, le=1.0, description="Precision: TP / (TP + FP)")
    recall: float = Field(..., ge=0.0, le=1.0, description="Recall: TP / (TP + FN)")
    f1_score: float = Field(..., ge=0.0, le=1.0, description="Harmonic mean of precision and recall")
    total_samples: int = Field(..., ge=0, description="Total evaluated samples")
    positive_samples: int = Field(..., ge=0, description="Total positive ground-truth samples")
    negative_samples: int = Field(..., ge=0, description="Total negative ground-truth samples")
    zero_division_convention: str = Field(
        default="0.0",
        description="Convention applied when denominator is zero (e.g. 0.0)",
    )


class ConfusionMatrixData(BaseModel):
    """2x2 Confusion matrix schema with explicit cell counts and definitions."""

    model_config = ConfigDict(frozen=True)

    true_positives: int = Field(..., ge=0, description="Actual Relevant predicted as Relevant (TP)")
    false_negatives: int = Field(..., ge=0, description="Actual Relevant predicted as Not Relevant (FN)")
    false_positives: int = Field(..., ge=0, description="Actual Not Relevant predicted as Relevant (FP)")
    true_negatives: int = Field(..., ge=0, description="Actual Not Relevant predicted as Not Relevant (TN)")
    true_positive: Optional[int] = Field(default=None, description="TP alias")
    false_negative: Optional[int] = Field(default=None, description="FN alias")
    false_positive: Optional[int] = Field(default=None, description="FP alias")
    true_negative: Optional[int] = Field(default=None, description="TN alias")
    positive_label_definition: str = Field(
        ...,
        description="Explicit definition of the positive class (e.g., human relevance score >= 2)",
    )
    negative_label_definition: str = Field(
        ...,
        description="Explicit definition of the negative class (e.g., human relevance score <= 1)",
    )
    plain_language_explanation: str = Field(
        ...,
        description="Plain-language description of confusion matrix outcomes",
    )

    @property
    def tp(self) -> int:
        return self.true_positives

    @property
    def tn(self) -> int:
        return self.true_negatives

    @property
    def fp(self) -> int:
        return self.false_positives

    @property
    def fn(self) -> int:
        return self.false_negatives

    @property
    def total(self) -> int:
        return self.true_positives + self.true_negatives + self.false_positives + self.false_negatives


class FeatureImportanceItem(BaseModel):
    """Feature importance or learned coefficient entry."""

    model_config = ConfigDict(frozen=True)

    feature_name: str = Field(..., description="Internal feature identifier")
    display_name: str = Field(..., description="Human-readable feature name")
    importance_score: float = Field(..., description="Normalized magnitude or importance weight")
    raw_coefficient: Optional[float] = Field(
        default=None,
        description="Raw model coefficient if linear model; None if tree/heuristic",
    )
    direction: str = Field(
        ...,
        description="Direction of impact: 'positive', 'negative', or 'neutral'",
    )
    interpretation: str = Field(
        ...,
        description="Plain-language explanation of what this feature reflects",
    )


class ModelEvaluationResult(BaseModel):
    """Detailed evaluation result for an individual machine-learning or baseline model."""

    model_config = ConfigDict(frozen=True)

    model_id: str = Field(..., description="Unique model identifier")
    model_name: str = Field(..., description="Display name of the model")
    model_type: str = Field(
        ...,
        description="Model family (e.g., 'Linear Classifier', 'Support Vector Machine', 'Similarity Ranker')",
    )
    purpose: str = Field(..., description="Core operational purpose of this model")
    input_features: List[str] = Field(..., description="List of input features used by this model")
    evaluation_method: str = Field(
        ...,
        description="Evaluation protocol (e.g., 'Stratified 5-Fold Cross-Validation (Out-of-Fold)')",
    )
    metrics: ClassificationMetrics = Field(..., description="Classification metric suite")
    confusion_matrix: ConfusionMatrixData = Field(..., description="Out-of-fold confusion matrix")
    feature_importance: List[FeatureImportanceItem] = Field(
        default_factory=list,
        description="Ranked global feature importance or coefficient weights",
    )
    ranking_metric_name: Optional[str] = Field(
        default="Mean Grouped NDCG@3",
        description="Ranking metric name",
    )
    ranking_metric_value: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Ranking metric value if supported",
    )
    is_best: bool = Field(default=False, description="Whether this is the recommended model")
    notes: str = Field(..., description="Methodological notes and boundary conditions")


class ModelComparisonRow(BaseModel):
    """Single row in the model comparison table."""

    model_config = ConfigDict(frozen=True)

    model_id: str = Field(..., description="Model identifier")
    model_name: str = Field(..., description="Model display name")
    model_type: str = Field(..., description="Model type / category")
    accuracy: float = Field(..., description="Classification accuracy")
    precision: float = Field(..., description="Precision score")
    recall: float = Field(..., description="Recall score")
    f1_score: float = Field(..., description="F1-score")
    samples: int = Field(default=25, description="Number of evaluated samples")
    ranking_metric: Optional[str] = Field(default="NDCG@3", description="Ranking metric name")
    ranking_metric_value: Optional[float] = Field(default=None, description="Ranking metric score")
    evaluation_method: str = Field(..., description="Evaluation methodology")
    is_best: bool = Field(default=False, description="Flag indicating selected top model")
    notes: str = Field(..., description="Short explanatory note")


class ModelComparisonTable(BaseModel):
    """Comparative benchmarking table of all evaluated models."""

    model_config = ConfigDict(frozen=True)

    rows: List[ModelComparisonRow] = Field(..., description="Model comparison rows")
    selection_rule: str = Field(..., description="Explicit rule used to select the best model")
    best_model_id: str = Field(..., description="ID of best-performing model under selection rule")
    best_model_name: str = Field(..., description="Name of best-performing model")


class WorkflowStep(BaseModel):
    """Individual stage in the ML processing workflow."""

    model_config = ConfigDict(frozen=True)

    step_number: int = Field(..., description="Sequential step index")
    title: str = Field(..., description="Stage title")
    description: str = Field(..., description="Detailed description of data flow")
    component: str = Field(..., description="Subsystem component responsible")


class EvaluationSummaryResponse(BaseModel):
    """Comprehensive payload for the frontend ML evaluation dashboard."""

    model_config = ConfigDict(frozen=True)

    dataset_name: str = Field(..., description="Benchmark dataset title")
    dataset_size: int = Field(..., description="Total candidate-job pairs in benchmark")
    class_distribution: Dict[str, int] = Field(
        ...,
        description="Ground-truth class label counts (Positive vs Negative)",
    )
    evaluation_strategy: str = Field(..., description="Validation methodology explanation")
    default_model: ModelEvaluationResult = Field(
        ...,
        description="Full evaluation result for the default selected model",
    )
    comparison_table: ModelComparisonTable = Field(
        ...,
        description="Side-by-side model comparison table",
    )
    workflow_steps: List[WorkflowStep] = Field(
        ...,
        description="End-to-end ML workflow pipeline stages",
    )
    ethical_disclaimer: str = Field(
        ...,
        description="Academic disclaimer distinguishing relevance from candidate suitability",
    )


class LocalFactor(BaseModel):
    """Positive or negative driver in an individual match decision."""

    model_config = ConfigDict(frozen=True)

    factor_name: str = Field(..., description="Name of the signal or feature")
    contribution: float = Field(..., description="Signed contribution value")
    direction: str = Field(..., description="'positive' or 'negative'")
    description: str = Field(..., description="Plain-language description of this factor")


class LocalExplanationRequest(BaseModel):
    """Request payload to generate a local XAI match explanation."""

    resume_text: str = Field(..., min_length=1, max_length=50000, description="Resume text")
    job_description: str = Field(..., min_length=1, max_length=50000, description="Job description")
    model_id: Optional[str] = Field(
        default="logistic_regression",
        description="Model to use for explanation (default: logistic_regression)",
    )


class LocalExplanationResponse(BaseModel):
    """Explainable AI (XAI) local explanation for a specific resume-job pair."""

    model_config = ConfigDict(frozen=True)

    model_id: str = Field(..., description="Evaluated model identifier")
    model_name: str = Field(..., description="Evaluated model name")
    prediction_label: str = Field(..., description="'Relevant Match' or 'Not Relevant Match'")
    prediction_probability: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Model estimated probability of relevance if calibrated",
    )
    decision_score: float = Field(..., description="Decision function or log-odds score")
    matched_skills: List[str] = Field(..., description="Canonical skills found in both texts")
    missing_skills: List[str] = Field(..., description="Job skills not detected in resume")
    tfidf_similarity: float = Field(..., description="Lexical TF-IDF cosine similarity")
    skill_overlap_ratio: Optional[float] = Field(default=None, description="Skill overlap ratio")
    feature_contributions: List[FeatureImportanceItem] = Field(
        ...,
        description="Local contribution of each feature to this specific decision",
    )
    positive_factors: List[LocalFactor] = Field(
        ...,
        description="Factors that increased the relevance score",
    )
    negative_factors: List[LocalFactor] = Field(
        ...,
        description="Factors that decreased the relevance score",
    )
    plain_language_explanation: str = Field(
        ...,
        description="Human-readable synthesis of why this prediction was made",
    )
    disclaimer: str = Field(
        ...,
        description="Ethical notice clarifying that missing skills mean missing text evidence, not candidate inability",
    )
