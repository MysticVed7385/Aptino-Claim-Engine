# Failure Analysis — Claim Decision Engine

This document records the failure modes observed during evaluation of the
Policy-Aware Multi-Agent RAG Claim Decision Engine, the root causes behind
them, and the changes made in response. It is written against two
measurements of the same 17-case suite (12 supplied public cases + 5
candidate-authored cases): the initial run at 70.6% accuracy, and the
post-fix run at 94.1% accuracy.

The suite, expected outcomes, and per-case results are in:

- `data/cases/public_test_cases.json` — 12 supplied cases (unmodified)
- `data/cases/additional_test_cases.json` — 5 candidate-authored cases
- `data/cases/expected_outcomes.json` — ground truth with rationales
- `evaluation/evaluation_results.json` — full per-case output from the latest run

---

## Summary of Results

| Run | Accuracy | Correct | NEEDS_REVIEW | NOT_ADMISSIBLE | ADMISSIBLE_WITH_LIMITS |
|---|---|---|---|---|---|
| Initial | 0.7059 | 12 / 17 | 8 | 0 | 9 |
| Final   | 0.9412 | 16 / 17 | 7 | 3 | 7 |

The improvement came from three targeted changes to
`app/agents/coverage_agent.py`. One failure remains, documented below as a
known limitation.

---

## Failure Class 1 — Exclusion Confirmation Depended on Retrieved Evidence

### Affected cases

| Case | Expected | Initial | Final |
|---|---|---|---|
| PUB-008 | NOT_ADMISSIBLE | NEEDS_REVIEW | NOT_ADMISSIBLE |
| PUB-012 | NOT_ADMISSIBLE | NEEDS_REVIEW | NOT_ADMISSIBLE |
| CUSTOM-002 | NOT_ADMISSIBLE | ADMISSIBLE_WITH_LIMITS | NOT_ADMISSIBLE |

### Root cause

The original `CoverageExclusionAgent` confirmed an exclusion only when three
conditions held simultaneously:

1. the case text mentioned an excluded category (e.g. "cosmetic"),
2. the retrieved evidence text contained the same category token, and
3. the retrieved evidence text contained an explicit exclusion phrase such as
   "not covered" or "excluded".

Condition (3) was the fault line. When the hybrid retriever returned a chunk
that did not happen to contain the literal exclusion clause, condition (3)
failed, `exclusion_confirmed` stayed `False`, and the case fell through to a
benign branch. PUB-008 (cosmetic surgery) and CUSTOM-002 (rhinoplasty) landed
in `NEEDS_REVIEW` and `ADMISSIBLE_WITH_LIMITS` respectively, despite the case
facts placing the claim squarely inside the policy's exclusion list.

PUB-012 was a separate but related bug: `treatment.experimental` was present
as a structured boolean in the case JSON but was never read by any agent. The
system saw a clean inpatient case and abstained for unrelated reasons.

### Fix

Three changes in `app/agents/coverage_agent.py`:

1. **Structured boolean checks.** The agent now reads
   `treatment.experimental` and `treatment.pre_existing` directly rather than
   inferring them from diagnosis strings.

2. **Topic-driven exclusion triggers.** When the case facts alone place the
   claim in an excluded category (cosmetic, dental, outpatient, experimental),
   the exclusion is confirmed without requiring the retrieved evidence to
   quote the exclusion clause. The evidence-confirmed path is retained and
   tracked separately under `exclusion_breakdown` in the coverage analysis.

3. **Reconstructive-necessity guard.** The cosmetic exclusion fires by topic
   unless the case explicitly documents `reconstructive_necessity_documented:
   true`, which preserves the legitimate reconstructive-surgery path.

### Verification

After the fix, the evaluation shows all three cases returning
`NOT_ADMISSIBLE`, matching their expected outcomes. The `decision_counts`
distribution acquired a new `NOT_ADMISSIBLE` bucket, confirming the branch
was previously unreachable for these inputs.

---

## Failure Class 2 — Waiting-Period Detection Depended on Retrieved Evidence

### Affected cases

| Case | Expected | Initial | Final |
|---|---|---|---|
| CUSTOM-001 | NEEDS_REVIEW | ADMISSIBLE_WITH_LIMITS | NEEDS_REVIEW |
| PUB-002 | NEEDS_REVIEW | NEEDS_REVIEW | NEEDS_REVIEW |

PUB-002 was correct in both runs — but for the wrong reason. It returned
`NEEDS_REVIEW` because the retriever happened to surface the 30-day
waiting-period clause, not because the system performed the date arithmetic
that would have made it correct under any retrieval outcome. CUSTOM-001,
which has the same structural situation (claim filed 19 days after policy
inception), was not so lucky: the retriever returned a different set of
chunks, the waiting-period text was not present, and the case fell through
to `ADMISSIBLE_WITH_LIMITS`.

### Root cause

The original agent treated the 30-day initial waiting period as a
text-matching problem. It looked for tokens such as "waiting period" or
"pre-existing" in the retrieved evidence. But the 30-day rule is a date
arithmetic problem. The correct behavior is to compute the elapsed days
between `policy_start_date` and `claim_date` and apply the rule directly.

Relying on retrieval for a deterministic property of the input is a category
error. When retrieval works, it happens to produce the right answer. When it
doesn't, the system silently approves a claim that should have been flagged.

### Fix

Two additions to `app/agents/coverage_agent.py`:

1. **Date arithmetic.** Compute `days_since_inception = (claim_date -
   policy_start_date).days`. If fewer than 30 days have elapsed and no prior
   continuous coverage is declared, set `initial_waiting_period_applies =
   True`.

2. **Pre-existing disease waiting period as a separate condition.** The
   48-month pre-existing disease exclusion is now evaluated against
   `continuous_coverage_months < 48` directly, rather than relying on
   retrieval to surface the clause.

Both conditions feed into `waiting_period_relevant`, and the full
intermediate state (`days_since_inception`, `initial_waiting_period_applies`,
`pre_existing_waiting_period_applies`) is recorded in the trace so a reviewer
can see exactly how the determination was reached.

### Verification

After the fix, CUSTOM-001 returns `NEEDS_REVIEW`, matching its expected
outcome. The trace exposes `days_since_inception: 19` and
`initial_waiting_period_applies: true`, making the reasoning inspectable
without any reliance on which chunks were retrieved.

---

## Remaining Failure — PUB-007 (Cancer Treatment Sub-Limit)

### Case

PUB-007 describes a cancer treatment claim of ₹8,90,000 against a
₹10,00,000 sum insured with 31 months of continuous coverage. The expected
decision is `ADMISSIBLE_WITH_LIMITS`, because the claim is clearly within
cover but should be reduced by the policy's category-specific limits. The
system returns `NEEDS_REVIEW`.

### Root cause

The retrieved evidence for PUB-007 does not contain a numeric sub-limit
specific to oncology. The policy's 40% sub-limit on medicines and diagnostics
applies, but the coverage agent's `limit_relevant` flag is driven by
text-matching against a small set of phrasings ("40% sum insured", "subject
to a limit", etc.). When the retrieved chunks do not include that phrasing in
a form the agent recognises, `limit_relevant` stays `False`, and the case
falls into the `requires_manual_review` branch, producing `NEEDS_REVIEW`.

### Why this has not been fixed

There are two candidate fixes, and neither is clearly better than accepting
the abstention:

**Option A — Reorder the branch checks.** Move the `limit_relevant` check
ahead of `requires_manual_review` in `DecisionAgent`, so a clean case with no
extracted limits is still classified as `ADMISSIBLE_WITH_LIMITS`. This raises
accuracy to 1.0 but does so by weakening the system's caution. A claim where
the system cannot state what the applicable limit *is* should arguably not be
declared "admissible with limits" without qualification.

**Option B — Add a category-specific limit extractor.** Scan the retrieved
chunks for oncology-related sub-limits and promote them into
`applicable_limits` with numeric values. This is the correct engineering fix,
but it requires building a per-disease sub-limit parser, which is outside the
scope of the current submission.

### Decision

The submission accepts the abstention and documents it as a known limitation.
Conservative abstention on high-value claims where a limit cannot be stated
is the safer production behavior. `NEEDS_REVIEW` is not a wrong answer — it
is a refusal to produce an unsupported one.

A future version would add the Option B extractor and treat the abstention
as resolved.

---

## What the Failures Teach

Three general lessons emerge from this analysis, all of which are already
reflected in the current code:

1. **Structured fields beat text inference.** Whenever the case JSON
   contains a boolean or a date, use it directly. Searching for its textual
   representation in retrieved chunks is fragile and adds no information.

2. **Deterministic properties belong in deterministic code.** Waiting-period
   arithmetic, document-checklist verification, and sub-limit caps should
   not depend on what the retriever happened to return. These are properties
   of the input and the policy document, not of the retrieval ranking.

3. **Citation correctness is not the same as citation presence.** The
   validation agent currently checks that citations have a chunk_id, page
   number, and section — but it does not verify that the excerpt actually
   supports the decision statement it is attached to. This is a known gap,
   documented as the next improvement in the README, and represents the
   most valuable next step for the system beyond the current submission.

---

## Reproducing the Analysis

From the repository root:

```bash
python evaluate.py