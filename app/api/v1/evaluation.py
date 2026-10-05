"""API endpoints for Machine Learning model evaluation, comparison, and Explainable AI (XAI)."""

from fastapi import APIRouter, HTTPException, status

from app.schemas.ml_evaluation import (
    EvaluationSummaryResponse,
    LocalExplanationRequest,
    LocalExplanationResponse,
    ModelEvaluationResult,
)
from app.services.ml_evaluator import ml_evaluator_service

router = APIRouter(prefix="/evaluation", tags=["ML Evaluation & XAI"])


@router.get(
    "/summary",
    response_model=EvaluationSummaryResponse,
    status_code=status.HTTP_200_OK,
    summary="Get complete ML evaluation summary, model comparison, and dataset metrics",
    description=(
        "Returns the authoritative evaluation summary calculated via Stratified 5-Fold Cross-Validation "
        "on the benchmark dataset, including confusion matrix, classification metrics, feature importances, "
        "and side-by-side comparison across all 5 models."
    ),
)
async def get_evaluation_summary() -> EvaluationSummaryResponse:
    """Return comprehensive ML evaluation dashboard summary."""
    try:
        return ml_evaluator_service.evaluate_all()
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate evaluation summary: {str(exc)}",
        ) from exc


@router.get(
    "/models/{model_id}",
    response_model=ModelEvaluationResult,
    status_code=status.HTTP_200_OK,
    summary="Get detailed evaluation results for a specific model",
    description=(
        "Returns metrics, 2x2 confusion matrix, and feature importances for a specific evaluated model "
        "(e.g. 'multinomial_nb', 'logistic_regression', 'linear_svm', 'skill_overlap_baseline', 'tfidf_baseline')."
    ),
)
async def get_model_evaluation(model_id: str) -> ModelEvaluationResult:
    """Return model-specific evaluation details."""
    clean_id = model_id.strip().lower()
    res = ml_evaluator_service.get_model_result(clean_id)
    if res is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                f"Model '{clean_id}' not found. Available models: "
                f"multinomial_nb, logistic_regression, linear_svm, skill_overlap_baseline, tfidf_baseline"
            ),
        )
    return res


@router.post(
    "/explain",
    response_model=LocalExplanationResponse,
    status_code=status.HTTP_200_OK,
    summary="Generate Explainable AI (XAI) local explanation for a resume and job description",
    description=(
        "Performs local feature contribution decomposition and driver analysis for an arbitrary "
        "resume and job description pair, identifying specific positive and negative alignment signals."
    ),
)
async def explain_match_prediction(
    payload: LocalExplanationRequest,
) -> LocalExplanationResponse:
    """Generate explainable match prediction with positive and negative drivers."""
    clean_resume = payload.resume_text.strip()
    if not clean_resume:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Resume text cannot be empty or whitespace-only.",
        )

    clean_jd = payload.job_description.strip()
    if not clean_jd:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Job description cannot be empty or whitespace-only.",
        )

    if len(payload.resume_text) > 50000 or len(payload.job_description) > 50000:
        raise HTTPException(
            status_code=getattr(status, "HTTP_413_CONTENT_TOO_LARGE", 413),
            detail="Payload text exceeds the maximum allowable length of 50,000 characters.",
        )

    try:
        model_id = payload.model_id or "logistic_regression"
        return ml_evaluator_service.explain_pair(
            resume_text=payload.resume_text,
            job_description=payload.job_description,
            model_id=model_id,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate match explanation: {str(exc)}",
        ) from exc
