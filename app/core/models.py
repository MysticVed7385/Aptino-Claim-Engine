from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Decision Statuses
# ---------------------------------------------------------------------------

class DecisionStatus(str, Enum):
    ADMISSIBLE = "ADMISSIBLE"
    ADMISSIBLE_WITH_LIMITS = "ADMISSIBLE_WITH_LIMITS"
    PARTIALLY_ADMISSIBLE = "PARTIALLY_ADMISSIBLE"
    NOT_ADMISSIBLE = "NOT_ADMISSIBLE"
    NEEDS_REVIEW = "NEEDS_REVIEW"


# ---------------------------------------------------------------------------
# Retrieval & Evidence Schemas
# ---------------------------------------------------------------------------

class EvidenceChunk(BaseModel):
    """Represents a policy passage retrieved during search."""
    chunk_id: str
    text: str
    section: str
    clause: Optional[str] = None
    page_start: int
    page_end: int
    chunk_type: Optional[str] = "policy_clause"
    dense_rank: Optional[int] = None
    sparse_rank: Optional[int] = None
    fused_score: Optional[float] = None
    rerank_score: Optional[float] = None


class Citation(BaseModel):
    """Traceable citation pointing back to specific policy source pages."""
    claim: str
    source: str = "policy.pdf"
    page: int
    section: str
    chunk_id: str


# ---------------------------------------------------------------------------
# Validation & Trace Schemas
# ---------------------------------------------------------------------------

class ValidationResult(BaseModel):
    status: str  # "PASS" or "FAIL"
    unsupported_claims: List[str] = Field(default_factory=list)


class TraceItem(BaseModel):
    agent: str
    action: str
    elapsed_time_ms: float
    details: Optional[Dict[str, Any]] = None


# ---------------------------------------------------------------------------
# API Output Schema
# ---------------------------------------------------------------------------

class AnalysisResponse(BaseModel):
    case_id: str
    decision: DecisionStatus
    confidence: float
    key_findings: List[str] = Field(default_factory=list)
    applicable_limits: List[str] = Field(default_factory=list)
    missing_evidence: List[str] = Field(default_factory=list)
    citations: List[Citation] = Field(default_factory=list)
    validation: ValidationResult
    trace: List[TraceItem] = Field(default_factory=list)