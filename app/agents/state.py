from typing import Any, TypedDict


class ClaimState(TypedDict, total=False):
    case_id: str

    claim: dict[str, Any]

    investigation_plan: list[str]
    missing_fields: list[str]

    retrieved_evidence: list[dict[str, Any]]

    case_analysis: dict[str, Any]
    coverage_analysis: dict[str, Any]
    decision_analysis: dict[str, Any]

    decision: dict[str, Any]
    validation: dict[str, Any]

    trace: list[dict[str, Any]]