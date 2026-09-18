from typing import Any


def normalize_text(value: Any) -> str:
    if value is None:
        return ""

    if isinstance(value, dict):
        return " ".join(
            f"{key} {normalize_text(item)}"
            for key, item in value.items()
        )

    if isinstance(value, list):
        return " ".join(normalize_text(item) for item in value)

    return str(value)


def build_claim_text(claim: dict[str, Any]) -> str:
    fields = [
        claim.get("task"),
        claim.get("patient"),
        claim.get("hospital"),
        claim.get("treatment"),
        claim.get("expenses_inr"),
        claim.get("documents"),
        claim.get("prior_policy"),
        claim.get("evidence_context"),
        claim.get("expense_timing"),
        claim.get("billing_context"),
    ]

    return " ".join(normalize_text(field) for field in fields).lower()


def detect_policy_topics(claim: dict[str, Any]) -> dict[str, bool]:
    claim_text = build_claim_text(claim)

    return {
        "pre_existing_disease": any(
            phrase in claim_text
            for phrase in [
                "pre-existing",
                "pre existing",
                "preexisting",
                "existing disease",
            ]
        ),
        "hospitalization": any(
            phrase in claim_text
            for phrase in [
                "hospitalization",
                "hospitalisation",
                "admitted",
                "inpatient",
            ]
        ),
        "maternity": any(
            phrase in claim_text
            for phrase in [
                "maternity",
                "pregnancy",
                "childbirth",
                "delivery",
            ]
        ),
        "cosmetic_treatment": any(
            phrase in claim_text
            for phrase in [
                "cosmetic",
                "plastic surgery",
                "aesthetic",
            ]
        ),
        "dental_treatment": "dental" in claim_text,
        "outpatient_treatment": any(
            phrase in claim_text
            for phrase in [
                "outpatient",
                "out-patient",
                "opd",
            ]
        ),
        "accidental_injury": any(
            phrase in claim_text
            for phrase in [
                "accident",
                "accidental injury",
                "road traffic accident",
            ]
        ),
    }