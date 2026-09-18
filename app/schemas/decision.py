"""Response contract for POST /analyze.

Mirrors Section 5 of the assignment spec: decision, confidence, findings,
limits, missing evidence, citations, validation, and trace. Pydantic
enforces the shape so the API can never return a malformed response.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class Citation(BaseModel):
    chunk_id: str | None = None
    page_number: int | None = None
    section: str | None = None
    source: str = "policy.pdf"
    excerpt: str | None = None


class ApplicableLimit(BaseModel):
    """Structured limit entry the UI and downstream consumers can rely on."""
    name: str
    claimed_inr: float | None = None
    limit_inr: float | None = None
    payable_inr: float | None = None


class ValidationResult(BaseModel):
    status: str = "NOT_RUN"
    unsupported_claims: list[str] = Field(default_factory=list)
    checked_claims: int = 0


class TraceStep(BaseModel):
    agent: str
    action: str
    details: dict[str, Any] = Field(default_factory=dict)
    timestamp: str | None = None


class ClaimDecision(BaseModel):
    case_id: str
    decision: str
    confidence: float
    key_findings: list[str] = Field(default_factory=list)
    applicable_limits: list[ApplicableLimit] = Field(default_factory=list)
    missing_evidence: list[str] = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)
    validation: ValidationResult = Field(default_factory=ValidationResult)
    trace: list[TraceStep] = Field(default_factory=list)
    estimated_payable_inr: float | None = None
    model: str | None = None
    elapsed_ms: int = 0