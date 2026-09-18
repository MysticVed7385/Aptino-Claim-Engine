from typing import Any
from pydantic import BaseModel, ConfigDict, Field


class ClaimCase(BaseModel):
    model_config = ConfigDict(extra="allow")

    case_id: str = Field(..., min_length=1)

    policy_id: str | None = None
    policy_start_date: str | None = None
    claim_date: str | None = None

    sum_insured_inr: float | None = None
    continuous_coverage_months: int | None = None
    prior_insurer_continuous_years: int | None = None

    patient: dict[str, Any] = Field(default_factory=dict)
    hospital: dict[str, Any] = Field(default_factory=dict)
    treatment: dict[str, Any] = Field(default_factory=dict)

    expenses_inr: dict[str, Any] = Field(default_factory=dict)
    documents: list[Any] = Field(default_factory=list)

    task: str = Field(..., min_length=1)

    prior_policy: dict[str, Any] = Field(default_factory=dict)
    evidence_context: dict[str, Any] = Field(default_factory=dict)
    expense_timing: dict[str, Any] = Field(default_factory=dict)
    billing_context: dict[str, Any] = Field(default_factory=dict)