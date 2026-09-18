"""Evaluation harness for the Claim Decision Engine.

Runs every supplied public case plus any candidate-created cases through
the multi-agent workflow and reports:

  - decision accuracy against a separately-maintained expected-outcomes file
  - abstention rate (NEEDS_REVIEW share)
  - retrieval coverage and average chunks per case
  - citation coverage and page-level citation correctness proxy
  - validation pass rate
  - average confidence

Reads expected outcomes from data/cases/expected_outcomes.json, which is
deliberately separate from the public cases (the assignment forbids
modifying them).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.schemas.claim import ClaimCase
from app.workflow.claim_workflow import ClaimWorkflow


# ---------------------------------------------------------
# Paths
# ---------------------------------------------------------

DATA_DIR = PROJECT_ROOT / "data"
CASES_DIR = DATA_DIR / "cases"

PUBLIC_CASES_PATH = CASES_DIR /  "public_test_cases.json"
ADDITIONAL_CASES_PATH = CASES_DIR / "additional_test_cases.json"
EXPECTED_OUTCOMES_PATH = CASES_DIR /  "expected_outcomes.json"

EVALUATION_DIR = PROJECT_ROOT / "evaluation"
if not EVALUATION_DIR.exists():
    EVALUATION_DIR = PROJECT_ROOT / "evalution"
OUTPUT_PATH = EVALUATION_DIR / "evaluation_results.json"


# ---------------------------------------------------------
# Loaders
# ---------------------------------------------------------

def load_cases(file_path: Path, required: bool = True) -> list[dict[str, Any]]:
    if not file_path.exists():
        if required:
            raise FileNotFoundError(f"Test case file not found: {file_path}")
        print(f"[warn] Optional case file missing: {file_path}")
        return []

    with file_path.open("r", encoding="utf-8") as file:
        data = json.load(file)

    if isinstance(data, dict):
        cases = data.get("cases", [])
    elif isinstance(data, list):
        cases = data
    else:
        raise ValueError(f"Unsupported JSON format in {file_path}")

    if not isinstance(cases, list):
        raise ValueError(f"'cases' must be a list in {file_path}")

    return cases


def load_expected_outcomes() -> dict[str, dict[str, Any]]:
    """Ground truth for accuracy computation.

    Returns an empty dict when the file is absent so the harness still runs;
    in that case accuracy is reported as None rather than zero, which would
    be misleading.
    """
    if not EXPECTED_OUTCOMES_PATH.exists():
        print(f"[warn] Expected outcomes file missing: {EXPECTED_OUTCOMES_PATH}")
        return {}
    with EXPECTED_OUTCOMES_PATH.open("r", encoding="utf-8") as file:
        return json.load(file)


def load_all_test_cases() -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    public_cases = load_cases(PUBLIC_CASES_PATH, required=True)
    additional_cases = load_cases(ADDITIONAL_CASES_PATH, required=False)
    return public_cases, additional_cases, public_cases + additional_cases


# ---------------------------------------------------------
# Evaluate one case
# ---------------------------------------------------------

def evaluate_case(
    workflow: ClaimWorkflow,
    raw_case: dict[str, Any],
    case_source: str,
    expected: dict[str, Any] | None,
) -> dict[str, Any]:
    claim = ClaimCase.model_validate(raw_case)
    result = workflow.run(claim.model_dump())

    # Prefer top-level keys (what the API returns); fall back to the nested
    # decision_analysis so we read the same value regardless of which writer
    # ran last.
    nested = result.get("decision_analysis", {}) or {}
    decision = result.get("decision") or nested.get("decision") or "NEEDS_REVIEW"
    confidence = result.get("confidence")
    if confidence is None:
        confidence = nested.get("confidence", 0.0)
    citations = result.get("citations") or nested.get("citations", []) or []
    missing_evidence = result.get("missing_evidence") or nested.get("missing_evidence", []) or []

    validation = result.get("validation", {}) or {}
    retrieved_evidence = result.get("retrieved_evidence", []) or []

    valid_page_citations = sum(
        1 for c in citations
        if isinstance(c, dict)
        and c.get("page_number") is not None
        and c.get("page_number") != "Unknown"
    )

    expected_decision = (expected or {}).get("expected_decision")
    expected_rationale = (expected or {}).get("rationale", "")

    return {
        "case_id": claim.case_id,
        "source": case_source,
        "decision": decision,
        "confidence": confidence,
        "expected_decision": expected_decision,
        "expected_rationale": expected_rationale,
        "decision_correct": (expected_decision == decision) if expected_decision else None,
        "citation_count": len(citations),
        "valid_page_citation_count": valid_page_citations,
        "retrieval_count": len(retrieved_evidence),
        "validation_status": validation.get("status", "FAIL"),
        "missing_evidence": missing_evidence,
    }


# ---------------------------------------------------------
# Summaries
# ---------------------------------------------------------

def calculate_summary(results: list[dict[str, Any]]) -> dict[str, Any]:
    total_cases = len(results)
    if not total_cases:
        return {"total_cases": 0}

    decision_counts: dict[str, int] = {}
    for r in results:
        d = r.get("decision", "ERROR")
        decision_counts[d] = decision_counts.get(d, 0) + 1

    cases_with_retrieval = sum(1 for r in results if r.get("retrieval_count", 0) > 0)
    cases_with_citations = sum(1 for r in results if r.get("citation_count", 0) > 0)
    cases_with_valid_page_citations = sum(
        1 for r in results if r.get("valid_page_citation_count", 0) > 0
    )
    passed_validation = sum(1 for r in results if r.get("validation_status") == "PASS")
    needs_review_cases = sum(1 for r in results if r.get("decision") == "NEEDS_REVIEW")
    error_cases = sum(1 for r in results if r.get("decision") == "ERROR")

    total_retrieved_chunks = sum(r.get("retrieval_count", 0) for r in results)
    total_citations = sum(r.get("citation_count", 0) for r in results)

    # Accuracy: only over cases where an expected outcome exists.
    comparable = [r for r in results if r.get("expected_decision") is not None]
    if comparable:
        correct = sum(1 for r in comparable if r.get("decision_correct") is True)
        accuracy: float | None = round(correct / len(comparable), 4)
        correct_count: int | None = correct
        comparable_count: int | None = len(comparable)
    else:
        accuracy = None
        correct_count = None
        comparable_count = 0

    average_confidence = sum(r.get("confidence", 0.0) for r in results) / total_cases

    return {
        "total_cases": total_cases,
        "decision_counts": decision_counts,
        "needs_review_cases": needs_review_cases,
        "error_cases": error_cases,

        "accuracy": accuracy,
        "correct_count": correct_count,
        "comparable_case_count": comparable_count,

        "cases_with_retrieval": cases_with_retrieval,
        "retrieval_coverage": round(cases_with_retrieval / total_cases, 4),

        "cases_with_citations": cases_with_citations,
        "citation_coverage": round(cases_with_citations / total_cases, 4),

        "cases_with_valid_page_citations": cases_with_valid_page_citations,
        "page_citation_coverage": round(cases_with_valid_page_citations / total_cases, 4),

        "total_retrieved_chunks": total_retrieved_chunks,
        "average_retrieved_chunks_per_case": round(total_retrieved_chunks / total_cases, 4),

        "total_citations": total_citations,
        "average_citations_per_case": round(total_citations / total_cases, 4),

        "passed_validation": passed_validation,
        "validation_pass_rate": round(passed_validation / total_cases, 4),

        "average_confidence": round(average_confidence, 4),
    }


# ---------------------------------------------------------
# Main
# ---------------------------------------------------------

def main() -> None:
    print("Loading test cases...")
    public_cases, additional_cases, all_cases = load_all_test_cases()
    expected_outcomes = load_expected_outcomes()

    print(f"Public cases loaded: {len(public_cases)}")
    print(f"Additional cases loaded: {len(additional_cases)}")
    print(f"Total cases to evaluate: {len(all_cases)}")
    print(f"Expected outcomes available for: {len(expected_outcomes)} cases")

    workflow = ClaimWorkflow()
    public_case_ids = {c.get("case_id") for c in public_cases}

    results: list[dict[str, Any]] = []

    for index, raw_case in enumerate(all_cases, start=1):
        case_id = raw_case.get("case_id", f"unknown-{index}")
        case_source = "public" if case_id in public_case_ids else "additional"
        expected = expected_outcomes.get(case_id)

        print(f"Evaluating case {index}/{len(all_cases)}: {case_id}")
        try:
            result = evaluate_case(workflow, raw_case, case_source, expected)
            results.append(result)
        except Exception as exc:
            print(f"Error while evaluating {case_id}: {exc}")
            results.append({
                "case_id": case_id,
                "source": case_source,
                "decision": "ERROR",
                "confidence": 0.0,
                "expected_decision": (expected or {}).get("expected_decision"),
                "expected_rationale": (expected or {}).get("rationale", ""),
                "decision_correct": False if expected else None,
                "citation_count": 0,
                "valid_page_citation_count": 0,
                "retrieval_count": 0,
                "validation_status": "FAIL",
                "missing_evidence": [str(exc)],
            })

    public_results = [r for r in results if r["source"] == "public"]
    additional_results = [r for r in results if r["source"] == "additional"]

    output = {
        "metadata": {
            "public_case_count": len(public_cases),
            "additional_case_count": len(additional_cases),
            "total_case_count": len(all_cases),
            "expected_outcomes_count": len(expected_outcomes),
        },
        "summary": calculate_summary(results),
        "public_summary": calculate_summary(public_results),
        "additional_summary": calculate_summary(additional_results),
        "results": results,
    }

    EVALUATION_DIR.mkdir(parents=True, exist_ok=True)
    with OUTPUT_PATH.open("w", encoding="utf-8") as file:
        json.dump(output, file, indent=2, ensure_ascii=False)

    print("\nEvaluation completed.")
    print("\nOverall summary:")
    print(json.dumps(output["summary"], indent=2))
    print("\nPublic summary:")
    print(json.dumps(output["public_summary"], indent=2))
    print("\nAdditional summary:")
    print(json.dumps(output["additional_summary"], indent=2))
    print(f"\nResults saved to: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()