# Architecture and Design Note

## 1. Project Overview

The Policy-Aware Multi-Agent RAG Claim Decision Engine analyzes
health-insurance claim cases against an authoritative policy document.

The system retrieves relevant policy evidence, analyzes claim information,
evaluates coverage conditions, generates a structured decision, and
validates that decision against the cited policy text. It is designed as
a decision-support tool: it does not replace human claim adjudication, and
it abstains (`NEEDS_REVIEW`) when the supplied evidence does not support a
safe conclusion.

The policy document supplied with the assignment (CSC Individual Health
Insurance, Universal Sompo General Insurance Co. Ltd., policy wording
UNIHLIP18004V011718) is the sole source of policy rules. No external
insurance or medical knowledge is used anywhere in the pipeline.

---

## 2. High-Level Architecture

The system is composed of eight major components:

1. **Policy ingestion** — PDF parsing and structure-aware chunking.
2. **Hybrid retrieval** — dense (BGE + FAISS) and sparse (BM25) retrieval
   combined by Reciprocal Rank Fusion and cross-encoder reranking.
3. **Multi-agent workflow** — five specialized agents exchanging a
   structured state object.
4. **Decision generation** — synthesizing a single decision status,
   confidence score, findings, limits, and citations.
5. **Citation validation** — checking that each decision claim is backed
   by a retrieved policy chunk.
6. **FastAPI backend** — `POST /analyze` and `GET /health`.
7. **Streamlit frontend** — reviewer-facing UI that talks to the backend
   over plain HTTP.
8. **Evaluation pipeline** — a reproducible harness that runs all public
   and candidate-authored cases and reports accuracy, retrieval coverage,
   citation coverage, and validation pass rate.

The policy PDF is processed into page-aware and section-aware chunks.
Each chunk carries a stable `chunk_id`, its `page_number`, its `section`
heading, and its source filename. Chunks are indexed for both dense and
sparse retrieval.

For each claim, the backend builds a retrieval query from the case facts,
fetches relevant policy evidence, and passes that evidence through the
five specialized agents in sequence. The final response includes the
decision, per-claim citations traceable to a specific page and section,
and an audit trace showing what each agent did.

---

## 3. Agent Boundaries

The system uses five specialized agents, each with a distinct
responsibility and a distinct slice of the shared state. The boundaries
are drawn so that a failure in one agent does not silently corrupt the
work of another, and so that each agent's output can be inspected in
isolation during review.

### Case Analysis Agent

`app/agents/case_analysis.py`

Extracts structured information from the claim and produces an
investigation plan.

**Responsibilities:**
- Identifies required claim fields (`policy_start_date`, `claim_date`,
  patient, hospital, treatment, documents).
- Detects missing fields that block a safe decision.
- Produces a fixed-step investigation plan covering eligibility,
  waiting periods, exclusions, treatment admissibility, and evidence
  sufficiency.

**Outputs to state:**
`state["missing_fields"]`, `state["investigation_plan"]`,
`state["case_analysis"]`.

This agent focuses on claim understanding. It does not make or influence
the policy decision.

### Policy Evidence Agent

`app/agents/policy_evidence_agent.py`

Builds a set of focused retrieval queries — one per decision dimension
— and returns the union of retrieved policy chunks.

**Responsibilities:**
- Builds one query per decision dimension: coverage scope, waiting
  periods, room-rent limits, ambulance caps, pre/post hospitalization
  windows, exclusions, sub-limits, network-hospital handling, pre-existing
  disease definitions, and day-care procedure coverage.
- Adds case-specific queries derived from `treatment.diagnosis`,
  `treatment.procedure`, and each present expense category.
- Runs each query through the hybrid retriever (dense + sparse + RRF +
  rerank) and deduplicates results by `chunk_id`.
- Records query count and unique chunk count in the trace for
  auditability.

**Outputs to state:** `state["retrieved_evidence"]`.

**Design note:** an earlier version concatenated the raw case JSON into
a single query string, which caused the retriever to match on tokens such
as `{'age': 34}`. Replacing that with multi-query retrieval across named
decision dimensions measurably improved topical relevance of the returned
chunks (see Failure Class 1 in `evaluation/FAILURE_ANALYSIS.md`).

### Coverage and Exclusion Agent

`app/agents/coverage_agent.py`

Assesses coverage scope, waiting periods, exclusions, and applicable
limits from the retrieved evidence and the structured case fields.

**Responsibilities:**
- Detects topic flags: pre-existing disease, maternity, cosmetic
  treatment, dental treatment, outpatient treatment.
- Reads structured booleans directly (`treatment.pre_existing`,
  `treatment.experimental`) rather than inferring them from text.
- Computes the 30-day initial waiting period via date arithmetic
  between `policy_start_date` and `claim_date`.
- Computes the 48-month pre-existing disease waiting period via
  `continuous_coverage_months` and `prior_insurer_continuous_years`.
- Confirms exclusions: cosmetic, dental, outpatient, and experimental.
  Exclusion confirmation does not depend on the retrieved evidence
  containing the literal exclusion clause — case facts alone can trigger
  it, because the policy's exclusion list applies regardless of which
  chunk happened to be retrieved.
- Flags `requires_manual_review` when documents are incomplete relative
  to the policy's document requirements.

**Outputs to state:**
`state["coverage_analysis"]`, `state["waiting_period_applies"]`,
`state["exclusion_confirmed"]`, `state["limit_relevant"]`.

**Design note:** treating waiting periods and exclusions as date
arithmetic and structured-field checks — rather than text-matching
problems — removed the largest source of misclassification in the
evaluation (see Failure Class 2 in `evaluation/FAILURE_ANALYSIS.md`).

### Decision Agent

`app/agents/decision_agent.py`

Synthesizes the specialist findings into a single structured decision.

**Responsibilities:**
- Selects a decision branch based on the coverage analysis:
  `ADMISSIBLE`, `ADMISSIBLE_WITH_LIMITS`, `PARTIALLY_ADMISSIBLE`,
  `NOT_ADMISSIBLE`, or `NEEDS_REVIEW`.
- Builds the list of key findings and missing evidence entries.
- Extracts structured sub-limits from retrieved policy text (the policy's
  40% medicines/diagnostics cap and the ambulance cap) and emits them as
  `applicable_limits` entries the UI can render and the deterministic
  calculator can consume.
- Computes a case-specific confidence score from the decision branch,
  the number of citations retrieved, and whether any required fields
  are missing. Confidence is never a constant.

**Outputs to state (both top-level and audit copy):**
`state["decision"]`, `state["confidence"]`, `state["key_findings"]`,
`state["applicable_limits"]`, `state["missing_evidence"]`,
`state["citations"]`, `state["decision_analysis"]`.

The five supported decision statuses are:

| Status | Meaning |
|---|---|
| `ADMISSIBLE` | Claim is supported by facts and policy, no material limit identified. |
| `ADMISSIBLE_WITH_LIMITS` | Claim is admissible but one or more policy limits, caps, or deductions apply. |
| `PARTIALLY_ADMISSIBLE` | Only part of the claim is supported; the excluded portion is identified. |
| `NOT_ADMISSIBLE` | Policy evidence supports a rejection or exclusion. |
| `NEEDS_REVIEW` | A safe decision cannot be made because required evidence or policy support is missing. |

### Validation Agent

`app/agents/validation_agent.py`

Verifies that each material decision statement is backed by retrieved
policy evidence.

**Responsibilities:**
- Checks that each citation has a `chunk_id`, `page_number`, `section`,
  and `excerpt`.
- Rejects decisions that are not `NEEDS_REVIEW` but carry no citations.
- Rejects `NOT_ADMISSIBLE` decisions that carry no citations.
- When validation fails, downgrades the decision to `NEEDS_REVIEW` and
  caps confidence at 0.40, writing the downgrade to both the top-level
  state and the audit copy.

**Outputs to state:** `state["validation"]`.

**Known limitation:** the current validator checks citation *presence*
and *metadata*, not whether each excerpt semantically supports the claim
it is attached to. A future iteration would add an LLM-checked support
verification per citation. This is documented in the README's Known
Limitations section.

---

## 4. State Flow

The workflow uses a single mutable `dict` state object threaded through
all five agents. Each agent reads what it needs from the state and writes
its outputs back under well-defined keys — both a top-level contract key
consumed by the response builder, and a nested `*_analysis` audit copy
that preserves the agent's full reasoning for inspection.

State keys written by each agent, in order:

| Agent | Top-level keys written |
|---|---|
| Case Analysis Agent | `missing_fields`, `investigation_plan` |
| Policy Evidence Agent | `retrieved_evidence` |
| Coverage and Exclusion Agent | `coverage_analysis`, `waiting_period_applies`, `exclusion_confirmed`, `limit_relevant` |
| Decision Agent | `decision`, `confidence`, `key_findings`, `applicable_limits`, `missing_evidence`, `citations`, `decision_analysis` |
| Validation Agent | `validation` (and may overwrite `decision`, `confidence` on downgrade) |

Every agent also appends a structured entry to `state["trace"]` via the
shared `add_trace` helper in `app/agents/base.py`. Each trace entry
records the agent name, a short action description, a details dict, and
an ISO timestamp. The trace is what the API returns so reviewers can see
what the system did without exposing internal chain-of-thought.

The state flows through the agents in the following order:

```text
Claim Input (case JSON)
    |
    v
Case Analysis Agent
    |
    v
Policy Evidence Agent
    |
    v
Coverage and Exclusion Agent
    |
    v
Decision Agent
    |
    v
Validation Agent
    |
    v
ClaimDecision response contract
    (case_id, decision, confidence, key_findings,
     applicable_limits, missing_evidence, citations,
     validation, trace, estimated_payable_inr)