"""Streamlit frontend for the Aptino Claim Assessment Engine.

Run with:   streamlit run frontend/streamlit_app.py
Expects the FastAPI backend already running at BACKEND_URL (default below) -
this file only talks to the backend over plain HTTP, it never imports the
agent pipeline directly. That separation matters: it's the same boundary a
real deployed frontend/backend pair would have (different processes,
possibly different machines), so testing it locally is a genuine rehearsal
for deployment, not a shortcut that would behave differently once deployed.
"""

from __future__ import annotations

import json
import os

import requests
import streamlit as st

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")

st.set_page_config(page_title="Aptino Claim Assessment Engine", page_icon="🩺", layout="wide")


# ---------------------------------------------------------------------------
# Backend connectivity
# ---------------------------------------------------------------------------


@st.cache_data(ttl=15)
def check_backend() -> dict | None:
    """Cached so we don't hit /health on every widget interaction."""
    try:
        response = requests.get(f"{BACKEND_URL}/health", timeout=5)
        response.raise_for_status()
        return response.json()
    except requests.RequestException:
        return None


def call_analyze(case_payload: dict) -> dict:
    """POST one claim case to the backend and return the parsed JSON response."""
    response = requests.post(f"{BACKEND_URL}/analyze", json=case_payload, timeout=120)
    response.raise_for_status()
    return response.json()


# ---------------------------------------------------------------------------
# Sidebar - connection status + case source
# ---------------------------------------------------------------------------

st.sidebar.title("🩺 Claim Assessment Engine")
st.sidebar.caption("Multi-agent policy-aware claim assessment")

health = check_backend()
if health is None:
    st.sidebar.error(
        f"Backend not reachable at {BACKEND_URL}.\n\n"
        "Start it in another terminal with:\n\n"
        "`uvicorn workflow.main:app --reload --port 8000`"
    )
else:
    st.sidebar.success("Backend connected")
    with st.sidebar.expander("Backend details", expanded=False):
        st.json(health)

st.sidebar.divider()

source = st.sidebar.radio("Load a case from", ["Public test cases", "Paste JSON"])


def load_public_cases() -> list[dict]:
    path = os.path.join(os.path.dirname(__file__), "..", "data", "cases", "public_test_cases.json")
    try:
        with open(path, encoding="utf-8") as handle:
            return json.load(handle)
    except FileNotFoundError:
        return []


# ---------------------------------------------------------------------------
# Main - case input
# ---------------------------------------------------------------------------

st.title("Claim Admissibility Assessment")
st.caption(
    "Enter or select a claim case. The system runs it through five agents against "
    "the policy PDF and returns a decision with page-level citations."
)

case_payload: dict | None = None

if source == "Public test cases":
    cases = load_public_cases()
    if not cases:
        st.warning("No public_test_cases.json found under data/cases/.")
    else:
        labels = [f"{c['case_id']} — {c.get('treatment', {}).get('diagnosis', '')}" for c in cases]
        choice = st.selectbox("Case", labels)
        case_payload = cases[labels.index(choice)]
        with st.expander("Raw case JSON", expanded=False):
            st.json(case_payload)
else:
    raw_text = st.text_area("Paste a claim case as JSON", height=280)
    if raw_text.strip():
        try:
            case_payload = json.loads(raw_text)
        except json.JSONDecodeError as exc:
            st.error(f"Invalid JSON: {exc}")

run_clicked = st.button("Run assessment", type="primary", disabled=case_payload is None or health is None)

# ---------------------------------------------------------------------------
# Result rendering
# ---------------------------------------------------------------------------

_DECISION_COLOR = {
    "ADMISSIBLE": "green",
    "ADMISSIBLE_WITH_LIMITS": "blue",
    "PARTIALLY_ADMISSIBLE": "orange",
    "NOT_ADMISSIBLE": "red",
    "NEEDS_REVIEW": "gray",
}

if run_clicked and case_payload is not None:
    with st.spinner("Running Case Analysis → Policy Evidence → Coverage & Exclusion → Decision → Validation..."):
        try:
            result = call_analyze(case_payload)
        except requests.HTTPError as exc:
            st.error(f"Backend returned an error: {exc.response.status_code} — {exc.response.text}")
            result = None
        except requests.RequestException as exc:
            st.error(f"Could not reach backend: {exc}")
            result = None

    if result:
        decision = result["decision"]
        color = _DECISION_COLOR.get(decision, "gray")

        col1, col2, col3 = st.columns(3)
        col1.markdown(f"### :{color}[{decision.replace('_', ' ')}]")
        col2.metric("Confidence", f"{result['confidence']:.0%}")
        if result.get("estimated_payable_inr") is not None:
            col3.metric("Estimated payable", f"₹{result['estimated_payable_inr']:,.0f}")
        else:
            col3.metric("Estimated payable", "—")

        st.markdown("#### Rationale")
        # Render each finding as a bullet
        for finding in result.get("key_findings", []):
            st.write(f"- {finding}")

        if result.get("key_findings"):
            st.markdown("#### Key findings")
            for item in result["key_findings"]:
                st.markdown(f"- {item}")

        if result.get("missing_evidence"):
            st.warning("Missing / blocking evidence:\n\n" + "\n".join(f"- {m}" for m in result["missing_evidence"]))

        if result.get("applicable_limits"):
            st.markdown("#### Applicable sub-limits")
            st.table(
                [
                    {
                        "Item": l["name"],
                        "Claimed (₹)": f"{l['claimed_inr']:,.0f}" if l.get("claimed_inr") else "—",
                        "Limit (₹)": f"{l['limit_inr']:,.0f}" if l.get("limit_inr") else "—",
                        "Payable (₹)": f"{l['payable_inr']:,.0f}" if l.get("payable_inr") else "—",
                    }
                    for l in result["applicable_limits"]
                ]
            )

        if result.get("citations"):
            st.markdown("#### Citations")
            for c in result["citations"]:
                page = c.get("page")
                page_label = f"p.{page}" if page else "computed"
                st.markdown(f"**[{c['chunk_id']}]** {c['section']} — {c.get('clause', '')} ({page_label})")
                if c.get("quote"):
                    st.caption(c["quote"])

        validation = result.get("validation", {})
        v_status = validation.get("status", "?")
        v_icon = "✅" if v_status == "PASS" else "⚠️"
        st.markdown(f"#### Validation: {v_icon} {v_status}  \n({validation.get('checked_claims', 0)} citations checked)")
        if validation.get("unsupported_claims"):
            for u in validation["unsupported_claims"]:
                st.caption(f"⚠️ {u}")

        with st.expander("Agent trace (full audit log)", expanded=False):
            for step in result.get("trace", []):
                st.text(
                    f"[{step['agent']}] {step['action']}: {step.get('detail', '')} "
                    f"({step.get('elapsed_ms', 0)} ms)"
                )

        with st.expander("Raw response JSON", expanded=False):
            st.json(result)

        st.caption(f"Model: {result.get('model', '?')} · Elapsed: {result.get('elapsed_ms', 0)} ms")
elif health is None:
    st.info("Start the backend first, then this page will let you run an assessment.")