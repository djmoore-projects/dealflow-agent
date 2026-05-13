"""
RAGAS evaluation suite for DealFlow Agent retrieval quality.

Metrics evaluated:
  faithfulness      — does the answer stay faithful to the retrieved context?
  answer_relevancy  — is the answer responsive to the question asked?
  context_recall    — does retrieved context cover the ground truth answer?
  context_precision — is retrieved context relevant (not noisy)?

The eval harness can run in two modes:
  1. GOLDEN mode (CI default): uses pre-written contexts from golden_dataset.py.
     Does not require a running pgvector instance.
  2. LIVE mode: runs real retrieval against pgvector, then evaluates.
     Requires DATABASE_URL and OPENAI_API_KEY.

RAGAS uses OpenAI as its internal LLM judge (faithfulness, answer_relevancy
require LLM evaluation). Set OPENAI_API_KEY in CI secrets.

CI fails if faithfulness < FAITHFULNESS_THRESHOLD (default 0.75).
"""
from __future__ import annotations

import os
import sys
from typing import Optional

from datasets import Dataset

from src.evals.golden_dataset import GOLDEN_QA_PAIRS
from src.utils.logging import configure_logging, get_logger

configure_logging()
logger = get_logger(__name__)

FAITHFULNESS_THRESHOLD = float(os.getenv("FAITHFULNESS_THRESHOLD", "0.75"))


def _build_golden_dataset() -> Dataset:
    """Build a RAGAS Dataset using pre-written golden contexts.

    This mode does not require a running database. Contexts are the exact
    passages from the golden dataset, simulating perfect retrieval.
    """
    return Dataset.from_dict(
        {
            "question": [qa["question"] for qa in GOLDEN_QA_PAIRS],
            "answer": [qa["ground_truth"] for qa in GOLDEN_QA_PAIRS],
            "contexts": [[qa["context"]] for qa in GOLDEN_QA_PAIRS],
            "ground_truth": [qa["ground_truth"] for qa in GOLDEN_QA_PAIRS],
        }
    )


def _build_live_dataset(job_id: Optional[str] = None) -> Dataset:
    """Build a RAGAS Dataset using live retrieval from pgvector.

    Args:
        job_id: If provided, filter retrieved chunks to this job.

    Returns:
        RAGAS-compatible Dataset.
    """
    from src.rag.retrieval import retrieve_chunks

    questions = [qa["question"] for qa in GOLDEN_QA_PAIRS]
    answers = []
    contexts = []

    for qa in GOLDEN_QA_PAIRS:
        chunks = retrieve_chunks(query=qa["question"], k=3, job_id=job_id)
        contexts.append([c.content for c in chunks])
        # Use ground truth as answer — we're evaluating retrieval, not generation
        answers.append(qa["ground_truth"])

    return Dataset.from_dict(
        {
            "question": questions,
            "answer": answers,
            "contexts": contexts,
            "ground_truth": [qa["ground_truth"] for qa in GOLDEN_QA_PAIRS],
        }
    )


def run_evals(live: bool = False, job_id: Optional[str] = None) -> dict[str, float]:
    """Run the RAGAS evaluation suite and return metric scores.

    Args:
        live: If True, use live pgvector retrieval. If False, use golden contexts.
        job_id: Job ID to filter live retrieval (only used when live=True).

    Returns:
        Dict of metric name → score (0.0–1.0).

    Raises:
        SystemExit: If faithfulness score is below FAITHFULNESS_THRESHOLD (for CI).
    """
    from ragas import evaluate
    from ragas.metrics import answer_relevancy, context_precision, context_recall, faithfulness

    logger.info("Starting RAGAS evaluation", mode="live" if live else "golden")

    dataset = _build_live_dataset(job_id=job_id) if live else _build_golden_dataset()

    result = evaluate(
        dataset=dataset,
        metrics=[faithfulness, answer_relevancy, context_recall, context_precision],
    )

    scores: dict[str, float] = {
        "faithfulness": float(result["faithfulness"]),
        "answer_relevancy": float(result["answer_relevancy"]),
        "context_recall": float(result["context_recall"]),
        "context_precision": float(result["context_precision"]),
    }

    _print_scores(scores)
    return scores


def _print_scores(scores: dict[str, float]) -> None:
    """Print RAGAS scores in a CI-friendly table format."""
    print("\n" + "=" * 50)
    print("RAGAS EVALUATION RESULTS")
    print("=" * 50)
    for metric, score in scores.items():
        status = "PASS" if metric != "faithfulness" or score >= FAITHFULNESS_THRESHOLD else "FAIL"
        print(f"  {metric:<25} {score:.4f}  [{status}]")
    print("=" * 50 + "\n")


def assert_faithfulness(scores: dict[str, float]) -> None:
    """Raise SystemExit if faithfulness is below threshold. Called by CI."""
    score = scores.get("faithfulness", 0.0)
    if score < FAITHFULNESS_THRESHOLD:
        logger.error(
            "Faithfulness below threshold — build failed",
            score=score,
            threshold=FAITHFULNESS_THRESHOLD,
        )
        sys.exit(1)
    logger.info("Faithfulness check passed", score=score, threshold=FAITHFULNESS_THRESHOLD)


if __name__ == "__main__":
    live_mode = "--live" in sys.argv
    scores = run_evals(live=live_mode)
    assert_faithfulness(scores)
