"""Reproducible Evaluation Framework for Resume Matching Baselines.

Phase 7:
1. Validates structured benchmark fixture (5 job groups x 5 candidates = 25 pairs).
2. Calculates Information Extraction metrics (Precision, Recall, F1) on skill sets.
3. Computes within-job-group ranking metrics (Grouped NDCG@K and within-group Spearman Rho),
   averaging across groups, and reporting skipped groups with exact reasons.
4. Provides optional semantic embedding baseline adapter using Sentence-Transformers
   via `--include-embeddings` with graceful degradation and clear actionable error messages.
5. Deterministic execution and machine-readable JSON export via `--output`.

METHODOLOGY & ETHICAL DISCLAIMER:
This evaluation operates on synthetic software test fixtures designed to probe edge cases
and verify algorithmic behavior. It does NOT represent empirical real-world candidate
validation or human hiring outcomes.
"""

import argparse
import json
import math
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

# Add repository root to Python path
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.services.embedding_matcher import semantic_embedding_matcher
from app.services.job_matcher import job_matcher_service
from app.services.skill_extractor import extract_skills


# ---------------------------------------------------------------------------
# 1. Dataset Schema Validation
# ---------------------------------------------------------------------------

REQUIRED_EXAMPLE_KEYS = {
    "example_id": str,
    "job_group_id": str,
    "category": str,
    "resume_text": str,
    "job_description": str,
    "annotated_job_skills": list,
    "annotated_resume_skills": list,
    "expected_matched_skills": list,
    "expected_missing_skills": list,
    "human_relevance_label": int,
    "rationale": str,
    "annotation_status": str,
}


def validate_benchmark_record(record: Any) -> Tuple[bool, Optional[str]]:
    """Validate that a benchmark example conforms strictly to the evaluation schema.

    Returns:
        Tuple of (is_valid, error_message_if_invalid).
    """
    if not isinstance(record, dict):
        return False, f"Record is not a JSON object; got {type(record).__name__}."

    for key, expected_type in REQUIRED_EXAMPLE_KEYS.items():
        if key not in record:
            return False, f"Missing required key: '{key}'."
        val = record[key]
        if expected_type == int:
            if not isinstance(val, int) or isinstance(val, bool):
                return False, f"Field '{key}' must be integer; got {type(val).__name__}."
        elif not isinstance(val, expected_type):
            return False, f"Field '{key}' must be {expected_type.__name__}; got {type(val).__name__}."

    # Validate human relevance label range [0, 3]
    label = record["human_relevance_label"]
    if label not in {0, 1, 2, 3}:
        return False, f"Invalid human_relevance_label: {label}. Must be 0, 1, 2, or 3."

    # Validate string lists
    for list_key in [
        "annotated_job_skills",
        "annotated_resume_skills",
        "expected_matched_skills",
        "expected_missing_skills",
    ]:
        items = record[list_key]
        if not all(isinstance(item, str) for item in items):
            return False, f"Field '{list_key}' must contain only strings."

    return True, None


def load_and_validate_dataset(
    dataset_path: Path,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], Dict[str, Any]]:
    """Load benchmark dataset from disk, validating schema and tracking skips.

    Returns:
        Tuple of (valid_examples, skipped_examples, metadata_dict).
    """
    if not dataset_path.exists():
        raise FileNotFoundError(f"Evaluation benchmark file not found: {dataset_path}")

    with open(dataset_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, dict) or "examples" not in data:
        raise ValueError("Invalid benchmark structure: Root must be an object with an 'examples' list.")

    metadata = {
        "schema_version": data.get("schema_version", "unknown"),
        "dataset_name": data.get("dataset_name", "unknown"),
        "annotator_metadata": data.get("annotator_metadata", {}),
        "relevance_scale": data.get("relevance_scale", {}),
    }

    raw_examples = data["examples"]
    valid_examples: List[Dict[str, Any]] = []
    skipped_examples: List[Dict[str, Any]] = []

    for idx, raw in enumerate(raw_examples):
        is_valid, err = validate_benchmark_record(raw)
        if is_valid:
            valid_examples.append(raw)
        else:
            skipped_examples.append(
                {
                    "index": idx,
                    "example_id": raw.get("example_id", f"UNKNOWN_INDEX_{idx}") if isinstance(raw, dict) else f"UNKNOWN_{idx}",
                    "reason": err,
                }
            )

    return valid_examples, skipped_examples, metadata


# ---------------------------------------------------------------------------
# 2. Information Extraction Metric Functions
# ---------------------------------------------------------------------------

def compute_set_metrics(
    predicted: Set[str],
    ground_truth: Set[str],
) -> Dict[str, Any]:
    """Compute true positives, false positives, false negatives, precision, recall, and F1.

    Special edge cases:
    - If both predicted and ground truth are empty: TP=0, FP=0, FN=0, P=1.0, R=1.0, F1=1.0.
    - If predicted is non-empty and ground truth is empty: TP=0, FP>0, FN=0, P=0.0, R=0.0, F1=0.0.
    - If predicted is empty and ground truth is non-empty: TP=0, FP=0, FN>0, P=0.0, R=0.0, F1=0.0.
    """
    tp = len(predicted & ground_truth)
    fp = len(predicted - ground_truth)
    fn = len(ground_truth - predicted)

    if len(predicted) == 0 and len(ground_truth) == 0:
        precision = 1.0
        recall = 1.0
        f1 = 1.0
    elif tp == 0:
        precision = 0.0
        recall = 0.0
        f1 = 0.0
    else:
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = (2.0 * precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0

    return {
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
    }


def aggregate_metrics(metrics_list: List[Dict[str, Any]]) -> Dict[str, float]:
    """Aggregate individual example set metrics into macro and micro averages."""
    n = len(metrics_list)
    if n == 0:
        return {
            "macro_precision": 0.0,
            "macro_recall": 0.0,
            "macro_f1": 0.0,
            "micro_precision": 0.0,
            "micro_recall": 0.0,
            "micro_f1": 0.0,
            "total_tp": 0,
            "total_fp": 0,
            "total_fn": 0,
        }

    # Macro averages (unweighted average of per-example scores)
    macro_precision = sum(m["precision"] for m in metrics_list) / n
    macro_recall = sum(m["recall"] for m in metrics_list) / n
    macro_f1 = sum(m["f1"] for m in metrics_list) / n

    # Micro averages (pooled instance counts)
    total_tp = sum(m["tp"] for m in metrics_list)
    total_fp = sum(m["fp"] for m in metrics_list)
    total_fn = sum(m["fn"] for m in metrics_list)

    denom_p = total_tp + total_fp
    denom_r = total_tp + total_fn

    micro_precision = total_tp / denom_p if denom_p > 0 else 0.0
    micro_recall = total_tp / denom_r if denom_r > 0 else 0.0
    denom_f1 = micro_precision + micro_recall
    micro_f1 = (2.0 * micro_precision * micro_recall) / denom_f1 if denom_f1 > 0 else 0.0

    return {
        "macro_precision": round(macro_precision, 4),
        "macro_recall": round(macro_recall, 4),
        "macro_f1": round(macro_f1, 4),
        "micro_precision": round(micro_precision, 4),
        "micro_recall": round(micro_recall, 4),
        "micro_f1": round(micro_f1, 4),
        "total_tp": total_tp,
        "total_fp": total_fp,
        "total_fn": total_fn,
    }


# ---------------------------------------------------------------------------
# 3. Ranking Metrics (Spearman's Rho and NDCG)
# ---------------------------------------------------------------------------

def _compute_fractional_ranks(values: List[float]) -> List[float]:
    """Compute fractional (average) ranks for a sequence of values, handling ties.

    Rank is 1-based ascending (smallest value gets rank 1).
    Tied values receive the arithmetic mean of their assigned rank positions.
    """
    indexed = sorted(enumerate(values), key=lambda x: x[1])
    ranks = [0.0] * len(values)

    i = 0
    n = len(indexed)
    while i < n:
        j = i
        while j < n - 1 and math.isclose(indexed[j][1], indexed[j + 1][1], abs_tol=1e-9):
            j += 1
        # Range of tied positions is [i+1, j+1]
        avg_rank = (i + 1 + j + 1) / 2.0
        for k in range(i, j + 1):
            orig_idx = indexed[k][0]
            ranks[orig_idx] = avg_rank
        i = j + 1

    return ranks


def compute_spearman_correlation(
    x: List[float],
    y: List[float],
) -> Optional[float]:
    """Calculate Spearman's rank correlation coefficient with exact fractional tie handling.

    Returns:
        Correlation float in [-1.0, 1.0], or None if either vector lacks variance (e.g. constant).
    """
    if len(x) != len(y) or len(x) < 2:
        return None

    rx = _compute_fractional_ranks(x)
    ry = _compute_fractional_ranks(y)

    mean_rx = sum(rx) / len(rx)
    mean_ry = sum(ry) / len(ry)

    num = sum((rx[i] - mean_rx) * (ry[i] - mean_ry) for i in range(len(rx)))
    den_x = sum((rx[i] - mean_rx) ** 2 for i in range(len(rx)))
    den_y = sum((ry[i] - mean_ry) ** 2 for i in range(len(ry)))

    if math.isclose(den_x, 0.0, abs_tol=1e-12) or math.isclose(den_y, 0.0, abs_tol=1e-12):
        return None

    rho = num / (math.sqrt(den_x) * math.sqrt(den_y))
    return round(max(-1.0, min(1.0, rho)), 4)


def compute_dcg(relevances: List[int], k: Optional[int] = None) -> float:
    """Compute Discounted Cumulative Gain (DCG) using logarithmic discounting."""
    effective_k = len(relevances) if k is None else min(k, len(relevances))
    dcg = 0.0
    for i in range(effective_k):
        gain = (2 ** relevances[i]) - 1
        discount = math.log2(i + 2)  # i=0 -> log2(2) = 1.0
        dcg += gain / discount
    return dcg


def compute_ndcg(
    scores: List[float],
    labels: List[int],
    k: Optional[int] = None,
    secondary_keys: Optional[List[str]] = None,
) -> float:
    """Compute Normalized Discounted Cumulative Gain (NDCG@K) with deterministic tie-breaking.

    Args:
        scores: Predicted continuous alignment scores (e.g. similarity or overlap).
        labels: Ground-truth graded relevance labels (e.g. 0 to 3).
        k: Cutoff threshold. None evaluates full list.
        secondary_keys: Optional stable identifiers for deterministic sorting in case of ties.

    Returns:
        NDCG value in [0.0, 1.0].
    """
    if not scores or not labels or len(scores) != len(labels):
        return 0.0

    n = len(scores)
    sec_keys = secondary_keys if secondary_keys is not None else [str(i) for i in range(n)]

    # Deterministic ranking: sort by predicted score descending, secondary key ascending
    paired = list(zip(scores, labels, sec_keys))
    ranked_pairs = sorted(paired, key=lambda item: (-item[0], item[2]))
    actual_relevances = [item[1] for item in ranked_pairs]

    # Ideal ranking: sort by ground-truth label descending
    ideal_relevances = sorted(labels, reverse=True)

    actual_dcg = compute_dcg(actual_relevances, k=k)
    ideal_dcg = compute_dcg(ideal_relevances, k=k)

    if math.isclose(ideal_dcg, 0.0, abs_tol=1e-12):
        # All items have zero relevance
        return 1.0 if math.isclose(actual_dcg, 0.0, abs_tol=1e-12) else 0.0

    return round(min(1.0, max(0.0, actual_dcg / ideal_dcg)), 4)


# ---------------------------------------------------------------------------
# 4. Grouped Within-Job Ranking Evaluation
# ---------------------------------------------------------------------------

def evaluate_signal_within_groups(
    groups_data: Dict[str, List[Dict[str, Any]]],
    score_key: str,
    k_cutoff: int = 3,
) -> Dict[str, Any]:
    """Calculate NDCG and Spearman correlation within each job group, then aggregate across groups.

    Args:
        groups_data: Mapping of job_group_id to list of candidate records in that group.
        score_key: Key in candidate record storing predicted score float (e.g. 'text_similarity').
        k_cutoff: Rank cutoff for NDCG@K.

    Returns:
        Dictionary with mean NDCG, mean Spearman correlation, valid group count, and skipped group logs.
    """
    group_ndcg_all: List[float] = []
    group_ndcg_k: List[float] = []
    group_spearman: List[float] = []
    per_group_metrics: Dict[str, Any] = {}
    skipped_spearman_groups: List[Dict[str, str]] = []

    for gid, candidates in sorted(groups_data.items()):
        scores: List[float] = []
        labels: List[int] = []
        ids: List[str] = []

        for c in candidates:
            raw_val = c.get(score_key)
            # Impute 0.0 if score is None (e.g. undefined skill overlap when JD has 0 skills)
            val = 0.0 if raw_val is None else float(raw_val)
            scores.append(val)
            labels.append(int(c["human_relevance_label"]))
            ids.append(c["example_id"])

        # Within-group NDCG
        ndcg_all = compute_ndcg(scores, labels, k=None, secondary_keys=ids)
        ndcg_k = compute_ndcg(scores, labels, k=k_cutoff, secondary_keys=ids)
        group_ndcg_all.append(ndcg_all)
        group_ndcg_k.append(ndcg_k)

        # Within-group Spearman's rho
        rho = compute_spearman_correlation(scores, [float(y) for y in labels])
        if rho is not None:
            group_spearman.append(rho)
            rho_str = f"{rho:.4f}"
        else:
            # Check why correlation is undefined
            score_var = len(set(scores)) > 1
            label_var = len(set(labels)) > 1
            if not score_var:
                reason = "Zero score variance across group candidates (all scores equal)"
            elif not label_var:
                reason = "Zero human relevance label variance (all labels equal)"
            else:
                reason = "Insufficient variation or candidate count < 2"

            skipped_spearman_groups.append({"job_group_id": gid, "reason": reason})
            rho_str = "skipped (no variance)"

        per_group_metrics[gid] = {
            "candidate_count": len(candidates),
            "ndcg_all": ndcg_all,
            f"ndcg_at_{k_cutoff}": ndcg_k,
            "spearman_rho": rho_str,
        }

    total_groups = len(groups_data)
    mean_ndcg_all = round(sum(group_ndcg_all) / total_groups, 4) if total_groups > 0 else 0.0
    mean_ndcg_k = round(sum(group_ndcg_k) / total_groups, 4) if total_groups > 0 else 0.0
    valid_spearman_groups = len(group_spearman)
    mean_spearman = round(sum(group_spearman) / valid_spearman_groups, 4) if valid_spearman_groups > 0 else None

    return {
        "mean_grouped_ndcg_all": mean_ndcg_all,
        f"mean_grouped_ndcg_at_{k_cutoff}": mean_ndcg_k,
        "mean_within_group_spearman_rho": mean_spearman,
        "total_groups_evaluated": total_groups,
        "valid_spearman_groups_count": valid_spearman_groups,
        "skipped_spearman_groups_count": len(skipped_spearman_groups),
        "skipped_spearman_groups_details": skipped_spearman_groups,
        "per_group_breakdown": per_group_metrics,
    }


# ---------------------------------------------------------------------------
# 5. Master Evaluation Runner
# ---------------------------------------------------------------------------

def run_evaluation(
    dataset_path: Optional[Path] = None,
    output_json_path: Optional[Path] = None,
    include_embeddings: bool = False,
    quiet: bool = False,
) -> Dict[str, Any]:
    """Execute complete reproducible evaluation workflow.

    Args:
        dataset_path: Path to benchmark JSON. Defaults to data/evaluation/synthetic_matching_benchmark.json.
        output_json_path: Optional path to save machine-readable evaluation report.
        include_embeddings: If True, executes optional sentence-transformer baseline if dependencies are present.
        quiet: If True, suppresses standard stdout printing.

    Returns:
        Structured dictionary containing full evaluation metrics.
    """
    if dataset_path is None:
        dataset_path = REPO_ROOT / "data" / "evaluation" / "synthetic_matching_benchmark.json"

    valid_examples, skipped_examples, metadata = load_and_validate_dataset(dataset_path)

    # Check optional embedding availability if requested
    embedding_status = "not_requested"
    embedding_unavailable_reason = None
    if include_embeddings:
        if semantic_embedding_matcher.is_available():
            embedding_status = "available"
        else:
            embedding_status = "unavailable"
            embedding_unavailable_reason = semantic_embedding_matcher.get_unavailable_reason()

    resume_skill_metrics: List[Dict[str, Any]] = []
    jd_skill_metrics: List[Dict[str, Any]] = []
    matched_skill_metrics: List[Dict[str, Any]] = []

    label_counts = {0: 0, 1: 0, 2: 0, 3: 0}
    categories_breakdown: Dict[str, int] = {}
    groups_data: Dict[str, List[Dict[str, Any]]] = {}

    per_example_results: List[Dict[str, Any]] = []

    for ex in valid_examples:
        eid = ex["example_id"]
        gid = ex["job_group_id"]
        cat = ex["category"]
        resume_text = ex["resume_text"]
        jd_text = ex["job_description"]
        human_label = ex["human_relevance_label"]

        label_counts[human_label] += 1
        categories_breakdown[cat] = categories_breakdown.get(cat, 0) + 1

        # Run system under evaluation
        match_result = job_matcher_service.match(resume_text, jd_text, resume_filename=f"{eid}.pdf")

        pred_resume_skills = set(match_result.resume_skills)
        pred_jd_skills = set(match_result.job_description_skills)
        pred_matched_skills = set(match_result.matched_skills)

        true_resume_skills = set(ex["annotated_resume_skills"])
        true_jd_skills = set(ex["annotated_job_skills"])
        true_matched_skills = set(ex["expected_matched_skills"])

        res_metric = compute_set_metrics(pred_resume_skills, true_resume_skills)
        jd_metric = compute_set_metrics(pred_jd_skills, true_jd_skills)
        match_metric = compute_set_metrics(pred_matched_skills, true_matched_skills)

        resume_skill_metrics.append(res_metric)
        jd_skill_metrics.append(jd_metric)
        matched_skill_metrics.append(match_metric)

        text_sim = match_result.text_similarity
        skill_overlap = match_result.skill_overlap_ratio

        # Compute optional embedding similarity if available
        emb_sim = None
        if embedding_status == "available":
            try:
                emb_sim, _ = semantic_embedding_matcher.compute_similarity(resume_text, jd_text)
            except Exception as e:
                emb_sim = None

        cand_data = {
            "example_id": eid,
            "job_group_id": gid,
            "human_relevance_label": human_label,
            "text_similarity": text_sim,
            "skill_overlap_ratio": skill_overlap,
            "semantic_embedding_similarity": emb_sim,
        }
        groups_data.setdefault(gid, []).append(cand_data)

        per_example_results.append(
            {
                "example_id": eid,
                "job_group_id": gid,
                "category": cat,
                "human_relevance_label": human_label,
                "text_similarity": text_sim,
                "skill_overlap_ratio": skill_overlap,
                "semantic_embedding_similarity": emb_sim,
                "predicted_resume_skills": sorted(list(pred_resume_skills)),
                "annotated_resume_skills": sorted(list(true_resume_skills)),
                "predicted_jd_skills": sorted(list(pred_jd_skills)),
                "annotated_jd_skills": sorted(list(true_jd_skills)),
                "predicted_matched_skills": sorted(list(pred_matched_skills)),
                "annotated_matched_skills": sorted(list(true_matched_skills)),
                "matched_skills_f1": match_metric["f1"],
                "rationale": ex.get("rationale", ""),
            }
        )

    # Aggregations for skill extraction
    agg_resume = aggregate_metrics(resume_skill_metrics)
    agg_jd = aggregate_metrics(jd_skill_metrics)
    agg_matched = aggregate_metrics(matched_skill_metrics)

    # Grouped within-job ranking evaluation
    k_cutoff = 3
    text_ranking = evaluate_signal_within_groups(groups_data, "text_similarity", k_cutoff=k_cutoff)
    skills_ranking = evaluate_signal_within_groups(groups_data, "skill_overlap_ratio", k_cutoff=k_cutoff)

    embedding_ranking = None
    if embedding_status == "available":
        embedding_ranking = evaluate_signal_within_groups(
            groups_data, "semantic_embedding_similarity", k_cutoff=k_cutoff
        )

    total_evaluated = len(valid_examples)
    total_skipped = len(skipped_examples)

    evaluation_report = {
        "benchmark_metadata": metadata,
        "execution_summary": {
            "total_examples_configured": total_evaluated + total_skipped,
            "examples_evaluated": total_evaluated,
            "examples_skipped": total_skipped,
            "job_groups_count": len(groups_data),
            "skipped_details": skipped_examples,
            "human_label_distribution": {
                str(k): {"count": count, "percentage": round((count / total_evaluated * 100) if total_evaluated else 0, 1)}
                for k, count in label_counts.items()
            },
            "category_distribution": categories_breakdown,
        },
        "skill_extraction_evaluation": {
            "candidate_resume_skills": agg_resume,
            "job_description_skills": agg_jd,
            "matched_skills": agg_matched,
        },
        "grouped_ranking_evaluation": {
            "k_cutoff": k_cutoff,
            "tf_idf_text_similarity": text_ranking,
            "canonical_skill_overlap_ratio": skills_ranking,
            "semantic_embedding_similarity": {
                "status": embedding_status,
                "reason": embedding_unavailable_reason,
                "metrics": embedding_ranking,
            },
        },
        "methodology_disclaimer": (
            "Academic Notice: This evaluation was executed against a curated synthetic benchmark. "
            "NDCG and Spearman correlation are computed within each shared job group and averaged across groups. "
            "These metrics demonstrate pipeline behavior, boundary conditions, and evaluation reproducibility; "
            "they are not an empirical estimate of general recruitment accuracy."
        ),
        "per_example_details": per_example_results,
    }

    # Save to disk if explicitly requested
    if output_json_path:
        out_p = Path(output_json_path)
        out_p.parent.mkdir(parents=True, exist_ok=True)
        with open(out_p, "w", encoding="utf-8") as f:
            json.dump(evaluation_report, f, indent=2)

    # Pretty print summary table to stdout unless quiet
    if not quiet:
        _print_terminal_report(evaluation_report, k_cutoff=k_cutoff)

    return evaluation_report


def _print_terminal_report(report: Dict[str, Any], k_cutoff: int = 3) -> None:
    """Print clean, professional ASCII summary table to console."""
    es = report["execution_summary"]
    se = report["skill_extraction_evaluation"]
    gr = report["grouped_ranking_evaluation"]

    print("=" * 82)
    print("  STUDENT RESUME ANALYZER — PHASE 7 GROUPED EVALUATION REPORT")
    print("=" * 82)
    print(f"Dataset Name:         {report['benchmark_metadata']['dataset_name']}")
    print(f"Examples Evaluated:   {es['examples_evaluated']} across {es['job_groups_count']} Job Groups (Skipped: {es['examples_skipped']})")

    # Label Distribution
    print("\n--- Human Relevance Label Distribution (Scale 0-3) ---")
    for lbl, stats in es["human_label_distribution"].items():
        print(f"  Label {lbl}: {stats['count']:2d} examples ({stats['percentage']:5.1f}%)")

    # Skill Extraction Performance Table
    print("\n--- Information Extraction Metrics (Precision / Recall / F1) ---")
    print(f"{'Target Set':<25} | {'Micro-P':<8} {'Micro-R':<8} {'Micro-F1':<8} | {'Macro-P':<8} {'Macro-R':<8} {'Macro-F1':<8}")
    print("-" * 82)
    for title, key in [
        ("Resume Skills", "candidate_resume_skills"),
        ("Job Description Skills", "job_description_skills"),
        ("Matched Skills", "matched_skills"),
    ]:
        m = se[key]
        print(
            f"{title:<25} | "
            f"{m['micro_precision']:<8.4f} {m['micro_recall']:<8.4f} {m['micro_f1']:<8.4f} | "
            f"{m['macro_precision']:<8.4f} {m['macro_recall']:<8.4f} {m['macro_f1']:<8.4f}"
        )

    # Within-Group Ranking Table
    print(f"\n--- Within-Job-Group Ranking Quality (Averaged across {es['job_groups_count']} Groups) ---")
    print(f"{'Signal':<30} | {'Mean Spearman':<15} | {'Valid Grps':<10} | {'Mean NDCG@All':<13} | {f'Mean NDCG@{k_cutoff}':<12}")
    print("-" * 82)

    for title, key in [
        ("TF-IDF Text Similarity", "tf_idf_text_similarity"),
        ("Skill Overlap Ratio", "canonical_skill_overlap_ratio"),
    ]:
        r = gr[key]
        mean_rho = f"{r['mean_within_group_spearman_rho']:.4f}" if r["mean_within_group_spearman_rho"] is not None else "N/A"
        print(
            f"{title:<30} | "
            f"{mean_rho:<15} | "
            f"{r['valid_spearman_groups_count']}/{r['total_groups_evaluated']:<8} | "
            f"{r['mean_grouped_ndcg_all']:<13.4f} | "
            f"{r[f'mean_grouped_ndcg_at_{k_cutoff}']:<12.4f}"
        )

    # Semantic Embedding Row
    emb_entry = gr["semantic_embedding_similarity"]
    emb_status = emb_entry.get("status")
    if emb_status == "available" and emb_entry.get("metrics"):
        em = emb_entry["metrics"]
        mean_rho = f"{em['mean_within_group_spearman_rho']:.4f}" if em["mean_within_group_spearman_rho"] is not None else "N/A"
        print(
            f"{'Semantic Embeddings (all-MiniLM)':<30} | "
            f"{mean_rho:<15} | "
            f"{em['valid_spearman_groups_count']}/{em['total_groups_evaluated']:<8} | "
            f"{em['mean_grouped_ndcg_all']:<13.4f} | "
            f"{em[f'mean_grouped_ndcg_at_{k_cutoff}']:<12.4f}"
        )
    elif emb_status == "unavailable":
        print(
            f"{'Semantic Embeddings (all-MiniLM)':<30} | "
            f"{'UNAVAILABLE':<15} | "
            f"{'0/' + str(es['job_groups_count']):<10} | "
            f"{'(missing dep)':<13} | "
            f"{'(pip install)':<12}"
        )
    else:
        print(
            f"{'Semantic Embeddings (all-MiniLM)':<30} | "
            f"{'NOT REQUESTED':<15} | "
            f"{'--':<10} | "
            f"{'--':<13} | "
            f"{'--':<12}"
        )

    # Skipped Groups Summary
    print("\n--- Within-Group Ranking Diagnostic Details ---")
    skills_skips = gr["canonical_skill_overlap_ratio"]["skipped_spearman_groups_details"]
    if skills_skips:
        for s in skills_skips:
            print(f"  • Skill Overlap Spearman skipped for {s['job_group_id']}: {s['reason']}")
    else:
        print("  • All job groups had sufficient variance for Spearman correlation.")

    # Embedding Availability Notice if requested
    if emb_status == "unavailable":
        print("\n[OPTIONAL EMBEDDING BASELINE NOTICE]")
        print("  " + emb_entry.get("reason", "").replace("\n", "\n  "))

    print("\n--- Evaluator Disclaimer ---")
    print(report["methodology_disclaimer"])
    print("=" * 82)


# ---------------------------------------------------------------------------
# CLI Entrypoint
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run reproducible evaluation framework for resume matching baseline."
    )
    parser.add_argument(
        "--dataset",
        type=Path,
        default=REPO_ROOT / "data" / "evaluation" / "synthetic_matching_benchmark.json",
        help="Path to evaluation benchmark JSON fixture.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Optional path to output machine-readable evaluation report JSON.",
    )
    parser.add_argument(
        "--include-embeddings",
        action="store_true",
        help="Enable optional semantic embedding baseline evaluation (requires sentence-transformers & torch).",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress console output.",
    )

    args = parser.parse_args()
    try:
        run_evaluation(
            dataset_path=args.dataset,
            output_json_path=args.output,
            include_embeddings=args.include_embeddings,
            quiet=args.quiet,
        )
    except Exception as e:
        print(f"Error during evaluation execution: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
