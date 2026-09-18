from fastapi import APIRouter, HTTPException

from app.schemas.claim import ClaimCase
from app.schemas.decision import ClaimDecision
from app.services.decision_service import build_claim_decision
from app.workflow.claim_workflow import ClaimWorkflow


router = APIRouter()

workflow = ClaimWorkflow()


@router.get("/health")
def health_check():
    return {
        "status": "healthy",
        "service": "policy-aware-multi-agent-rag-claim-engine",
    }


@router.post("/analyze", response_model=ClaimDecision)
def analyze_claim(claim: ClaimCase):
    try:
        state = workflow.run(claim.model_dump())
        decision = build_claim_decision(state)

        return decision

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Claim analysis failed: {str(exc)}",
        ) from exc