# Graduation handoff scope — Flutter / React engineering team

**Status:** PROPOSAL ONLY. Docs-only. **Not approved, not a scope change, not an
instruction to build.** Prepared for independent review and owner decision.
**Target:** Thursday 3 December 2026.
**Separate from RH-04.** Nothing here changes, blocks, or is blocked by the RH-04
gate work. No frontend, backend, database or product feature is implemented by this
document.

---

## 1. The one thing that must be decided first

The intended term-one demo workflow contains this step:

> preliminary AI assessment and explanation → NOT_REVIEWED → doctor review

**A patient sees a preliminary AI result before a clinician reviews it.** That
conflicts with three existing statements in the repository, written independently:

| source | statement |
|---|---|
| `02_FEATURE_TRACEABILITY_MATRIX.md` L105 | "Patient UI never shows Track-A scores." |
| `02_FEATURE_TRACEABILITY_MATRIX.md` L140 | Slide "daily risk pulse" / patient risk display is **PROHIBITED** (patients never see Track-A scores or personal risk %) |
| `01_MASTER_ARCHITECTURE_AND_DELIVERY_BLUEPRINT.md` L223 | no offline CAD inference (patients never see Track-A scores) |
| `06_TESTING_AND_ACCEPTANCE_MATRIX.md` L156 | Monitoring screens do not call CAD inference or display Track-A scores |

**This is not a documentation contradiction to be tidied up in this PR.** It is a
product and clinical-governance decision that belongs to the owner, and it is
exactly the kind of silent reversal the register exists to prevent (D-042: no
intended feature is removed or silently changed; any change needs an explicit new
decision entry with human approval).

### The three options, stated honestly

| option | what the demo shows the patient | consequence |
|---|---|---|
| **A. Keep the prohibition** (lowest risk) | "Your report is being prepared for your doctor." No score, no band, no percentage. | Workflow is unchanged; the demo loses the "AI insight" moment for the patient, keeps it for the clinician. |
| **B. Narrow, explicit amendment** | A qualitative, non-numeric status — "Preliminary assessment ready; awaiting clinician review" — with **no score, no risk %, no band after review** | Requires a new APPROVED decision entry naming exactly what is shown, to whom, and with what disclaimer. Does **not** require touching Track-A score policy. |
| **C. Show the preliminary result to the patient** | Numeric or banded preliminary output before review | **Conflicts with four existing statements.** Requires an explicit, reasoned reversal of the patient-visibility policy, plus clinical sign-off. Not recommended for a demo. |

**Recommendation: Option B.** It preserves the demo narrative, keeps every existing
prohibition intact, and adds no clinical claim. **It still needs an owner decision
entry before any UI work starts.**

---

## 2. What the demo workflow actually requires

Each row is marked **IMPLEMENTED**, **MOCK**, **PLANNED (contract review)** or
**DEFERRED**, based on what exists in the repository today.

| # | Demo step | Status | Evidence / gap |
|---|---|---|---|
| 1 | Patient manual or synthetic OCR input | **MOCK + partially PLANNED** | OCR endpoint is planned M5 (`POST /v1/documents/lab-reports`, contract review required). Manual entry is not implemented. |
| 2 | Feature validation | **IMPLEMENTED (research surface)** | `ai/preprocessing.py` validates and encodes with fail-closed contract errors. Not yet exposed as a product API. |
| 3 | Preliminary AI assessment + explanation | **IMPLEMENTED (research/synthetic only)** | Facade returns status + SHAP/LIME, synthetic data only, `SYNTHETIC_RESEARCH`, `approved_for_serving: false`. |
| 4 | NOT_REVIEWED state | **IMPLEMENTED read-only** | `pending_review` exists in mock responses. No state-transition endpoint. |
| 5 | Doctor review action | **NOT IMPLEMENTED** | "no review-action endpoint exists yet" (`M1A3_INTEGRATION_HANDOFF.md` L66; traceability L130, L166). |
| 6 | Clinician notes + demo prescription/follow-up | **NOT IMPLEMENTED** | Planned M1b follow-up/summary CRUD. |
| 7 | In-app notification | **NOT IMPLEMENTED** | Planned M1b; push (FCM/APNs) explicitly **DEFERRED**. |
| 8 | Patient views the message | **NOT IMPLEMENTED** | Depends on 5–7 and on the §1 decision. |

**Plain reading:** four of the eight steps in the intended demo do not exist as
working code, and the one that carries the clinical-governance question (§1) is
also the one that decides step 8.

---

## 3. Conflicts found, beyond §1

| # | conflict | severity | owner action |
|---|---|---|---|
| C-1 | Patient-visible preliminary AI result vs. "patients never see Track-A scores" | **BLOCKING** | Decision entry (§1) |
| C-2 | Demo needs a review-action endpoint; **none exists in the approved contract** | **BLOCKING** for steps 5–8 | Contract review before implementation |
| C-3 | Push notifications are **DEFERRED** by policy; demo says "in-app notification" | LOW if strictly in-app | Confirm "in-app only" is acceptable for the demo |
| C-4 | OCR is planned M5 with its own contract; demo treats it as available | MEDIUM | Either scope OCR out (manual entry only) or bring M5 forward — owner choice |
| C-5 | Demo runs on synthetic/demo data only; no PHI | **Constraint, not a conflict** | Must stay true; no real patient data in the demo |
| C-6 | Track-A score is a "benchmark-cohort score, never an absolute personal probability" (§F-6) | **Constraint** | Any patient-facing wording must not imply personal probability |

---

## 4. Proposed term-one / term-two split

This is a **proposal**, not an approved plan.

### Term one (demo, 3 Dec 2026) — proposed

- Steps 1–4 on **synthetic data only**, with the OCR step stubbed or manual.
- Step 5 (doctor review) **only if C-2 is resolved**; otherwise the demo shows the
  read-only `pending_review` state and stops there.
- Steps 6–8 **demonstrated with mocks**, clearly labelled as mock in the UI.

### Term two — proposed

- Review-action and follow-up APIs (M1b), real notification delivery, richer OCR
  (M5), wearable adapters (all ACCESS-GATED, P-6), system integration (F08/FHIR).

---

## 5. What this document does not do

- It does not change D-042, D-038, D-039 or any APPROVED decision.
- It does not authorise implementation of any frontend, backend or database feature.
- It does not claim any step of the demo workflow is functional beyond the status
  column in §2.
- It does not touch the RH-04 gate, Lane A/Lane B architecture, or V1.

## 6. Decisions requested

| # | decision | blocks |
|---|---|---|
| G-1 | Choose Option A, B or C for patient visibility | Term-one UI, step 8 |
| G-2 | Approve or defer the review-action endpoint (C-2) | Steps 5–8 |
| G-3 | Confirm in-app-only notifications for term one (C-3) | Step 7 |
| G-4 | OCR in or out of term one (C-4) | Step 1 |
| G-5 | Accept or amend the term-one/term-two split (§4) | Whole plan |

**No build work should start before G-1 and G-2 are answered.** Everything else can
proceed in parallel.
