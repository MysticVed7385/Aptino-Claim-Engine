from datetime import date
from typing import Any

from app.agents.base import add_trace


class CoverageExclusionAgent:
    name = "CoverageExclusionAgent"

    def run(self, state: dict[str, Any]) -> dict[str, Any]:
        claim = state.get("claim", {}) or {}
        evidence = state.get("retrieved_evidence", []) or []
        treatment = claim.get("treatment", {}) or {}

        # --- text views used for token matching ---
        patient_text = str(claim.get("patient", "")).lower()
        treatment_text = str(treatment).lower()
        hospital_text = str(claim.get("hospital", "")).lower()
        document_text = str(claim.get("documents", [])).lower()

        claim_text = " ".join([patient_text, treatment_text, hospital_text, document_text])

        evidence_text = " ".join(
            str(item.get("text", "")).lower()
            for item in evidence
            if isinstance(item, dict)
        )

        combined_text = f"{claim_text} {evidence_text}"

        # --- topic flags (from case facts + case text) ---
        topics = {
            "pre_existing_disease": self._contains_any(claim_text, [
                "pre-existing", "pre existing", "preexisting",
                "existing disease", "prior disease", "previous illness",
            ]),
            "maternity": self._contains_any(claim_text, [
                "maternity", "pregnancy", "pregnant", "delivery",
                "childbirth", "caesarean", "c-section",
            ]),
            "cosmetic_treatment": self._contains_any(claim_text, [
                "cosmetic", "plastic surgery", "beautification", "aesthetic surgery",
                "rhinoplasty",
            ]),
            "dental_treatment": self._contains_any(claim_text, [
                "dental", "tooth", "teeth", "dentist",
            ]),
            "outpatient_treatment": self._contains_any(claim_text, [
                "outpatient", "out-patient", "opd", "without hospitalization",
            ]),
        }

        # ---- FIX 1: respect the structured boolean flags, not just text ----
        # The case schema carries `pre_existing` and `experimental` as
        # booleans. Relying on the diagnosis string to contain the word
        # "experimental" or "pre-existing" is fragile; use the field.
        if treatment.get("pre_existing") is True:
            topics["pre_existing_disease"] = True

        experimental_flag = treatment.get("experimental") is True

        # ---- FIX 2: day-count waiting-period math ----
        # The 30-day initial waiting period is a date arithmetic problem.
        # Relying on retrieval to surface POLICY-00030 fails whenever a
        # different waiting-period clause dominates the result set.
        days_since_inception: int | None = None
        try:
            policy_start = date.fromisoformat(str(claim.get("policy_start_date")))
            claim_date = date.fromisoformat(str(claim.get("claim_date")))
            days_since_inception = (claim_date - policy_start).days
        except (KeyError, TypeError, ValueError):
            pass

        prior_continuous_years = claim.get("prior_insurer_continuous_years", 0) or 0
        continuous_months = claim.get("continuous_coverage_months", 0) or 0

        initial_waiting_period_applies = (
            days_since_inception is not None
            and days_since_inception < 30
            and prior_continuous_years == 0
            and continuous_months == 0
        )

        pre_existing_waiting_period_applies = (
            topics["pre_existing_disease"]
            and continuous_months < 48
            and prior_continuous_years == 0
        )

        waiting_period_relevant = (
            initial_waiting_period_applies
            or pre_existing_waiting_period_applies
            or topics["maternity"]
        )

        # --- limits / exclusion / document flags (unchanged) ---
        exclusion_relevant = self._contains_any(combined_text, [
            "exclusion", "excluded", "not covered", "shall not be covered",
            "not admissible", "cosmetic treatment", "dental treatment",
            "outpatient treatment",
        ])

        limit_relevant = self._contains_any(combined_text, [
            "subject to a limit", "sub-limit", "sub limit", "maximum",
            "limited to", "sum insured", "40% sum insured",
            "1.0% of the basic sum insured", "0.1% of the basic sum insured",
        ])

        inpatient_indicator = self._contains_any(claim_text, [
            "inpatient", "in-patient", "hospitalization", "hospitalisation",
            "admitted", "discharged",
        ])

        required_document_indicator = self._contains_any(document_text, [
            "discharge summary", "hospital bill", "medical report",
            "diagnostic report", "prescription", "invoice",
        ])

        evidence_sufficient = bool(evidence)

        requires_manual_review = (
            not evidence_sufficient
            or (inpatient_indicator and not required_document_indicator)
        )

        exclusion_terms = [
            "not covered", "excluded", "exclusion",
            "shall not be covered", "not admissible",
        ]

        # --- evidence-confirmed exclusions (unchanged) ---
        cosmetic_exclusion_by_evidence = (
            topics["cosmetic_treatment"]
            and self._contains_any(evidence_text, [
                "cosmetic treatment", "cosmetic surgery",
                "beautification", "aesthetic surgery",
            ])
            and self._contains_any(evidence_text, exclusion_terms)
        )

        dental_exclusion_by_evidence = (
            topics["dental_treatment"]
            and self._contains_any(evidence_text, ["dental treatment", "dental", "dentist"])
            and self._contains_any(evidence_text, exclusion_terms)
        )

        outpatient_exclusion_by_evidence = (
            topics["outpatient_treatment"]
            and self._contains_any(evidence_text, ["outpatient", "out-patient", "opd"])
            and self._contains_any(evidence_text, exclusion_terms)
        )

        # ---- FIX 3: exclusion triggers that do not require evidence ----
        # When the case facts alone place the claim in an excluded
        # category, the policy's exclusion list applies regardless of
        # which chunk the retriever happened to return. Requiring the
        # evidence to also quote the exclusion clause meant cosmetic
        # and experimental cases were falling through to a benign
        # ADMISSIBLE_WITH_LIMITS branch instead of being rejected.
        cosmetic_exclusion_by_topic = (
            topics["cosmetic_treatment"]
            and not treatment.get("reconstructive_necessity_documented", False)
        )

        dental_exclusion_by_topic = topics["dental_treatment"]

        outpatient_exclusion_by_topic = (
            topics["outpatient_treatment"]
            and not treatment.get("requires_hospitalization", False)
        )

        experimental_exclusion = experimental_flag

        exclusion_confirmed = (
            cosmetic_exclusion_by_evidence
            or dental_exclusion_by_evidence
            or outpatient_exclusion_by_evidence
            or cosmetic_exclusion_by_topic
            or dental_exclusion_by_topic
            or outpatient_exclusion_by_topic
            or experimental_exclusion
        )

        coverage_analysis = {
            "topics": topics,
            "waiting_period_relevant": waiting_period_relevant,
            "initial_waiting_period_applies": initial_waiting_period_applies,
            "pre_existing_waiting_period_applies": pre_existing_waiting_period_applies,
            "days_since_inception": days_since_inception,
            "experimental_flag": experimental_flag,
            "exclusion_relevant": exclusion_relevant,
            "exclusion_confirmed": exclusion_confirmed,
            "exclusion_breakdown": {
                "cosmetic_by_evidence": cosmetic_exclusion_by_evidence,
                "cosmetic_by_topic": cosmetic_exclusion_by_topic,
                "dental_by_evidence": dental_exclusion_by_evidence,
                "dental_by_topic": dental_exclusion_by_topic,
                "outpatient_by_evidence": outpatient_exclusion_by_evidence,
                "outpatient_by_topic": outpatient_exclusion_by_topic,
                "experimental": experimental_exclusion,
            },
            "limit_relevant": limit_relevant,
            "inpatient_indicator": inpatient_indicator,
            "required_document_indicator": required_document_indicator,
            "evidence_sufficient": evidence_sufficient,
            "requires_manual_review": requires_manual_review,
        }

        # --- top-level contract keys ---
        state["coverage_analysis"] = coverage_analysis
        state["waiting_period_applies"] = waiting_period_relevant
        state["exclusion_confirmed"] = exclusion_confirmed
        state["limit_relevant"] = limit_relevant

        add_trace(
            state,
            self.name,
            "Analyzed coverage topics, exclusions, limits, and review conditions",
            {
                "topics": topics,
                "waiting_period_relevant": waiting_period_relevant,
                "initial_waiting_period_applies": initial_waiting_period_applies,
                "exclusion_confirmed": exclusion_confirmed,
                "exclusion_breakdown": coverage_analysis["exclusion_breakdown"],
                "limit_relevant": limit_relevant,
                "requires_manual_review": requires_manual_review,
            },
        )

        return state

    @staticmethod
    def _contains_any(text: str, terms: list[str]) -> bool:
        return any(term in text for term in terms)