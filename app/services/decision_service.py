"""Convert the multi-agent state dict into the API response contract."""

from __future__ import annotations

import time
from typing import Any

from app.core.sub_limit_calculator import calculate_payable_amount
from app.schemas.decision import ClaimDecision


def build_claim_decision(state: dict[str, Any]) -> ClaimDecision:
    """Assemble the response contract from the workflow's final state.

    The state is expected to contain:
        decision, confidence, key_findings, applicable_limits,
        missing_evidence, citations, validation, trace, model
    Missing pieces are defaulted rather than raising, so the API stays
    resilient to partial agent failures.
    """

    case_id = state.get("case_id", "UNKNOWN")
    decision = state.get("decision", "NEEDS_REVIEW")
    confidence = float(state.get("confidence", 0.0))
    key_findings = list(state.get("key_findings", []))
    missing_evidence = list(state.get("missing_evidence", []))
    citations = list(state.get("citations", []))
    trace = list(state.get("trace", []))
    validation = state.get("validation", {"status": "NOT_RUN", "unsupported_claims": [], "checked_claims": 0})

    # --- applicable limits: coerce to the dict shape the UI expects ---
    raw_limits = state.get("applicable_limits", [])
    applicable_limits = []
    for item in raw_limits:
        if isinstance(item, dict):
            applicable_limits.append({
                "name": item.get("name", "unspecified limit"),
                "claimed_inr": item.get("claimed_inr"),
                "limit_inr": item.get("limit_inr"),
                "payable_inr": item.get("payable_inr"),
            })
        else:
            # Backend produced a plain string; wrap it so the UI doesn't crash
            applicable_limits.append({
                "name": str(item),
                "claimed_inr": None,
                "limit_inr": None,
                "payable_inr": None,
            })

    # --- deterministic payable calculation ---
    payable = calculate_payable_amount(
        claim=state.get("claim", {}),
        limits=raw_limits,
        waiting_period_applies=state.get("waiting_period_applies", False),
    )

    return ClaimDecision(
        case_id=case_id,
        decision=decision,
        confidence=confidence,
        key_findings=key_findings,
        applicable_limits=applicable_limits,
        missing_evidence=missing_evidence,
        citations=citations,
        validation=validation,
        trace=trace,
        estimated_payable_inr=payable.get("payable_inr"),
        model=state.get("model", "unknown"),
        elapsed_ms=state.get("elapsed_ms", 0),
    )