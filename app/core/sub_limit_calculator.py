"""Deterministic payable-amount calculation.

Deliberately LLM-free: money math is the last place you want hallucination.
"""

from __future__ import annotations

from typing import Any


def calculate_payable_amount(
    claim: dict[str, Any],
    limits: list[dict[str, Any]],
    waiting_period_applies: bool = False,
) -> dict[str, Any]:
    """Compute payable amount given claim facts and applicable limits.

    Returns {"payable_inr": float | None, "breakdown": list[dict]}.
    Returns payable_inr=None when the input lacks enough structure to
    compute safely (NEEDS_REVIEW territory).
    """

    if waiting_period_applies:
        return {"payable_inr": 0.0, "breakdown": [{"reason": "waiting period applies"}]}

    expenses = claim.get("expenses_inr") or {}
    if not expenses:
        return {"payable_inr": None, "breakdown": [{"reason": "no expenses in case"}]}

    total_claimed = sum(v for v in expenses.values() if isinstance(v, (int, float)))
    breakdown: list[dict[str, Any]] = [{"name": "total_claimed", "amount_inr": total_claimed}]

    payable = float(total_claimed)

    for limit in limits:
        if not isinstance(limit, dict):
            continue
        limit_type = limit.get("type")
        limit_value = limit.get("limit_inr")
        if limit_type == "ambulance_cap" and limit_value is not None:
            amb_claimed = expenses.get("ambulance", 0)
            amb_payable = min(amb_claimed, limit_value)
            payable -= (amb_claimed - amb_payable)
            breakdown.append({"name": "ambulance_cap", "amount_inr": amb_payable})
        elif limit_type == "room_rent_sublimit" and limit_value is not None:
            room_claimed = expenses.get("room", 0)
            room_payable = min(room_claimed, limit_value)
            payable -= (room_claimed - room_payable)
            breakdown.append({"name": "room_rent_sublimit", "amount_inr": room_payable})
        # Extend with more limit types as your policy analysis demands.

    # Cap at sum insured if present
    sum_insured = claim.get("sum_insured_inr")
    if sum_insured is not None:
        payable = min(payable, float(sum_insured))

    return {"payable_inr": round(payable, 2), "breakdown": breakdown}