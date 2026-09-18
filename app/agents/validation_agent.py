from typing import Any

from app.agents.base import add_trace


class ValidationAgent:
    name = "ValidationAgent"

    def run(self, state: dict[str, Any]) -> dict[str, Any]:
        decision_analysis = state.get("decision_analysis", {})
        decision = decision_analysis.get("decision", "NEEDS_REVIEW")
        citations = decision_analysis.get("citations", [])

        unsupported_claims: list[str] = []

        for citation in citations:
            if not isinstance(citation, dict):
                unsupported_claims.append("Invalid citation format.")
                continue

            chunk_id = citation.get("chunk_id")
            page_number = citation.get("page_number")
            section = citation.get("section")
            excerpt = citation.get("excerpt")

            if not chunk_id:
                unsupported_claims.append("Citation is missing chunk ID.")
            if page_number is None:
                unsupported_claims.append(
                    f"Citation {chunk_id or 'unknown'} is missing page number."
                )
            if not section:
                unsupported_claims.append(
                    f"Citation {chunk_id or 'unknown'} is missing section."
                )
            if not excerpt:
                unsupported_claims.append(
                    f"Citation {chunk_id or 'unknown'} is missing excerpt."
                )

        if decision != "NEEDS_REVIEW" and not citations:
            unsupported_claims.append(
                f"{decision} decision requires policy citations."
            )
        if decision == "NOT_ADMISSIBLE" and not citations:
            unsupported_claims.append(
                "A NOT_ADMISSIBLE decision requires policy citations."
            )

        unsupported_claims = list(dict.fromkeys(unsupported_claims))

        # Downgrade if validation fails — update BOTH the audit dict
        # and the top-level contract keys.
        if unsupported_claims:
            decision_analysis["decision"] = "NEEDS_REVIEW"
            decision_analysis["confidence"] = min(
                float(decision_analysis.get("confidence", 0.0)),
                0.40,
            )
            state["decision_analysis"] = decision_analysis
            state["decision"] = "NEEDS_REVIEW"
            state["confidence"] = decision_analysis["confidence"]

        validation_status = "PASS" if not unsupported_claims else "FAIL"

        state["validation"] = {
            "status": validation_status,
            "unsupported_claims": unsupported_claims,
            "checked_claims": len(citations),
        }

        add_trace(
            state,
            self.name,
            "Validated decision citations and decision reliability",
            {
                "validation_status": validation_status,
                "unsupported_claim_count": len(unsupported_claims),
                "final_decision": state.get("decision"),
            },
        )

        return state