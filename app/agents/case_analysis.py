from typing import Any

from app.agents.base import add_trace


class CaseAnalysisAgent:
    name = "CaseAnalysisAgent"

    REQUIRED_FIELDS = {
        "policy_start_date": "policy_start_date",
        "claim_date": "claim_date",
        "patient": "patient information",
        "hospital": "hospital information",
        "treatment": "treatment information",
        "documents": "supporting documents",
    }

    def run(self, state: dict[str, Any]) -> dict[str, Any]:
        claim = state.get("claim", {})

        missing_fields = [
            label
            for field, label in self.REQUIRED_FIELDS.items()
            if not claim.get(field)
        ]

        investigation_plan = [
            "Check policy eligibility and coverage period",
            "Check waiting-period provisions",
            "Check exclusions and limitations",
            "Check treatment and expense admissibility",
            "Verify whether supporting evidence is sufficient",
        ]

        case_analysis = {
            "case_id": claim.get("case_id"),
            "policy_id": claim.get("policy_id"),
            "missing_fields": missing_fields,
            "investigation_plan": investigation_plan,
        }

        # --- top-level contract keys ---
        state["missing_fields"] = missing_fields
        state["investigation_plan"] = investigation_plan
        state["case_analysis"] = case_analysis  # audit copy

        add_trace(
            state,
            self.name,
            "Completed initial claim analysis",
            {
                "missing_field_count": len(missing_fields),
                "plan_step_count": len(investigation_plan),
            },
        )

        return state