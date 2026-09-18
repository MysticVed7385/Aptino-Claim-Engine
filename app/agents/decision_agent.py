"""Decision Agent.

Synthesises the specialist findings from upstream agents into a single
claim decision, promotes the result to top-level state (so the API response
builder and downstream consumers can read it), and keeps an audit copy
inside state["decision_analysis"].

Also extracts structured sub-limits from the retrieved policy text so the
deterministic calculator in app/core/sub_limit_calculator.py has real
numbers to work with, instead of passing plain strings to the UI.
"""

from __future__ import annotations

import re
from typing import Any

from app.agents.base import add_trace


# Phrases the policy uses to express caps. Extend as the policy PDF reveals
# more; the parser is intentionally narrow so it does not invent limits.
_ROOM_RENT_LIMIT_PATTERNS = [
    r"room rent[^.]*?(?P<pct>\d+(?:\.\d+)?)\s*%\s*(?:of\s*)?(?:the\s*)?basic\s*sum\s*insured",
    r"room rent[^.]*?(?P<pct>\d+(?:\.\d+)?)\s*%\s*(?:of\s*)?sum\s*insured",
    r"room rent[^.]*?(?P<amt>rs\.?\s*[\d,]+)",
]

_MEDICINES_LIMIT_PATTERNS = [
    r"(?P<pct>\d+(?:\.\d+)?)\s*%\s*sum\s*insured[^.]*?(?:medicines|drugs|diagnostic)",
    r"(?:medicines|drugs|diagnostics|anesthesia|operation theatre)[^.]*?(?P<pct>\d+(?:\.\d+)?)\s*%\s*sum\s*insured",
]

_AMBULANCE_LIMIT_PATTERNS = [
    r"ambulance[^.]*?(?P<pct>\d+(?:\.\d+)?)\s*%\s*of\s*(?:the\s*)?basic\s*sum\s*insured",
    r"ambulance[^.]*?rupees?\s*(?P<amt>[\d,]+)",
    r"ambulance[^.]*?rs\.?\s*(?P<amt>[\d,]+)",
]


class DecisionAgent:
    name = "DecisionAgent"

    # Weight multipliers used to convert retrieval strength into a
    # case-specific confidence score. Kept as constants so the reasoning
    # is inspectable rather than buried in arithmetic.
    BASE_CONFIDENCE = {
        "ADMISSIBLE": 0.55,
        "ADMISSIBLE_WITH_LIMITS": 0.50,
        "PARTIALLY_ADMISSIBLE": 0.45,
        "NOT_ADMISSIBLE": 0.65,
        "NEEDS_REVIEW": 0.25,
    }
    MAX_CITATION_BONUS = 0.20
    MISSING_FIELD_PENALTY = 0.10

    def run(self, state: dict[str, Any]) -> dict[str, Any]:
        missing_fields = state.get("missing_fields", [])
        evidence = state.get("retrieved_evidence", [])
        coverage = state.get("coverage_analysis", {})

        citations = self._build_citations(evidence)
        extracted_limits = self._extract_limits(evidence)

        findings: list[str] = []
        applicable_limits: list[dict[str, Any]] = []
        missing_evidence = list(missing_fields)

        topics = coverage.get("topics", {})

        # --- branch selection (unchanged logic, now with structured limits) ---
        if missing_fields:
            decision = "NEEDS_REVIEW"
            findings.append(
                "Required claim information is missing and needs to be "
                "verified before a final decision."
            )

        elif not evidence:
            decision = "NEEDS_REVIEW"
            findings.append("No relevant policy evidence was retrieved for the claim.")
            missing_evidence.append("Relevant policy evidence")

        elif coverage.get("exclusion_confirmed"):
            decision = "NOT_ADMISSIBLE"
            findings.append(
                "The retrieved policy evidence indicates that the treatment "
                "falls under a potentially applicable exclusion."
            )

        elif coverage.get("waiting_period_relevant"):
            decision = "NEEDS_REVIEW"
            findings.append("The claim may involve a policy waiting-period condition.")
            missing_evidence.append(
                "Confirmation of policy commencement date, continuous coverage, "
                "and waiting-period eligibility"
            )

        elif coverage.get("requires_manual_review"):
            decision = "NEEDS_REVIEW"
            findings.append(
                "Additional claim documents or eligibility information are "
                "required for a reliable preliminary decision."
            )

        elif coverage.get("limit_relevant") or extracted_limits:
            decision = "ADMISSIBLE_WITH_LIMITS"
            findings.append(
                "The claim appears admissible, subject to the applicable "
                "policy limits or sub-limits identified below."
            )

            # Promote structured limits instead of a vague sentence
            applicable_limits = extracted_limits
            if not applicable_limits:
                applicable_limits = [{
                    "name": "unspecified sub-limit",
                    "claimed_inr": None,
                    "limit_inr": None,
                    "payable_inr": None,
                }]
                findings.append(
                    "Policy language referencing a sub-limit was retrieved, "
                    "but the specific cap could not be extracted with "
                    "confidence."
                )

        else:
            decision = "ADMISSIBLE"
            findings.append(
                "The available claim information and retrieved policy evidence "
                "do not identify a known exclusion or unresolved waiting-period "
                "condition."
            )

        # --- topic-specific observations ---
        topic_messages = {
            "pre_existing_disease": "The claim may involve a pre-existing disease.",
            "maternity": "The claim may involve maternity-related treatment.",
            "cosmetic_treatment": "The claim may involve cosmetic treatment.",
            "dental_treatment": "The claim may involve dental treatment.",
            "outpatient_treatment": "The claim may involve outpatient treatment.",
        }
        for topic, message in topic_messages.items():
            if topics.get(topic):
                findings.append(message)

        if coverage.get("exclusion_relevant"):
            findings.append(
                "Potential exclusion-related policy language was identified "
                "in the retrieved evidence."
            )

        missing_evidence = list(dict.fromkeys(missing_evidence))

        # --- case-specific confidence ---
        confidence = self._compute_confidence(
            decision=decision,
            citation_count=len(citations),
            missing_fields_count=len(missing_fields),
            evidence_count=len(evidence),
        )

        decision_analysis = {
            "decision": decision,
            "confidence": confidence,
            "key_findings": findings,
            "applicable_limits": applicable_limits,
            "missing_evidence": missing_evidence,
            "citations": citations,
        }

        # --- top-level contract keys (the fix) ---
        state["decision_analysis"] = decision_analysis       # audit copy
        state["decision"] = decision
        state["confidence"] = confidence
        state["key_findings"] = findings
        state["applicable_limits"] = applicable_limits
        state["missing_evidence"] = missing_evidence
        state["citations"] = citations

        add_trace(
            state,
            self.name,
            "Generated evidence-aware decision",
            {
                "decision": decision,
                "confidence": confidence,
                "citation_count": len(citations),
                "structured_limit_count": len(extracted_limits),
                "missing_evidence_count": len(missing_evidence),
            },
        )

        return state

    # ------------------------------------------------------------------
    # citations
    # ------------------------------------------------------------------
    @staticmethod
    def _build_citations(evidence: list[dict[str, Any]]) -> list[dict[str, Any]]:
        citations: list[dict[str, Any]] = []
        for item in evidence:
            if not isinstance(item, dict):
                continue
            citations.append({
                "chunk_id": item.get("chunk_id"),
                "page_number": item.get("page_number"),
                "section": item.get("section"),
                "source": item.get("source", "policy.pdf"),
                "excerpt": str(item.get("text", ""))[:500],
            })
        return citations

    # ------------------------------------------------------------------
    # confidence
    # ------------------------------------------------------------------
    def _compute_confidence(
        self,
        decision: str,
        citation_count: int,
        missing_fields_count: int,
        evidence_count: int,
    ) -> float:
        """Confidence derived from evidence strength, not a constant.

        Starts from a base per decision type, adds a bonus proportional to
        the number of citations (capped), and penalises missing fields.
        Values are clamped to [0.05, 0.95] so the API never reports 0.0
        or 1.0, which would imply certainty the system does not have.
        """
        base = self.BASE_CONFIDENCE.get(decision, 0.30)
        citation_bonus = min(
            self.MAX_CITATION_BONUS,
            0.03 * min(citation_count, 8),
        )
        missing_penalty = self.MISSING_FIELD_PENALTY if missing_fields_count else 0.0

        score = base + citation_bonus - missing_penalty
        return round(max(0.05, min(0.95, score)), 2)

    # ------------------------------------------------------------------
    # structured limit extraction
    # ------------------------------------------------------------------
    def _extract_limits(self, evidence: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Parse sub-limits out of retrieved policy chunks.

        Returns dicts of the shape:
            {"name": str, "claimed_inr": None, "limit_inr": float | None, "payable_inr": None}

        The `limit_inr` is filled only when the clause expresses an
        absolute amount. Percentage-based caps are recorded in `name`
        verbatim so a reviewer sees the source language; the calculator
        later resolves them against the case sum insured.
        """
        extracted: list[dict[str, Any]] = []
        seen_names: set[str] = set()

        for item in evidence:
            if not isinstance(item, dict):
                continue
            text = str(item.get("text", ""))
            section = item.get("section", "policy clause")

            # room rent sub-limit
            for pattern in _ROOM_RENT_LIMIT_PATTERNS:
                m = re.search(pattern, text, flags=re.IGNORECASE)
                if m:
                    name = "room rent sub-limit"
                    if name not in seen_names:
                        limit_inr = None
                        if m.groupdict().get("amt"):
                            limit_inr = self._parse_amount(m.group("amt"))
                        extracted.append({
                            "name": f"{name} ({section})",
                            "claimed_inr": None,
                            "limit_inr": limit_inr,
                            "payable_inr": None,
                        })
                        seen_names.add(name)
                    break

            # medicines / diagnostics sub-limit (the 40% one in this policy)
            for pattern in _MEDICINES_LIMIT_PATTERNS:
                m = re.search(pattern, text, flags=re.IGNORECASE)
                if m:
                    pct = m.groupdict().get("pct")
                    name = f"medicines/diagnostics cap: {pct}% of sum insured" if pct else "medicines cap"
                    if name not in seen_names:
                        extracted.append({
                            "name": f"{name} ({section})",
                            "claimed_inr": None,
                            "limit_inr": None,
                            "payable_inr": None,
                        })
                        seen_names.add(name)
                    break

            # ambulance cap
            for pattern in _AMBULANCE_LIMIT_PATTERNS:
                m = re.search(pattern, text, flags=re.IGNORECASE)
                if m:
                    name = "ambulance cap"
                    if name not in seen_names:
                        limit_inr = None
                        if m.groupdict().get("amt"):
                            limit_inr = self._parse_amount(m.group("amt"))
                        extracted.append({
                            "name": f"{name} ({section})",
                            "claimed_inr": None,
                            "limit_inr": limit_inr,
                            "payable_inr": None,
                        })
                        seen_names.add(name)
                    break

        return extracted

    @staticmethod
    def _parse_amount(raw: str) -> float | None:
        try:
            cleaned = re.sub(r"[^\d.]", "", raw)
            return float(cleaned) if cleaned else None
        except (ValueError, TypeError):
            return None