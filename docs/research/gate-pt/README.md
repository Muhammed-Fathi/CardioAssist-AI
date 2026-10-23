# Gate PT — Research Protocol Authorization Handoff

**Only clinical/research sign-off can open Gate PT P-3.** Merging design documents never grants model-training permission.

- [01 — One-decision Cleveland CAD model-development packet (NOT APPROVED)](01_first_cleveland_model_review_packet_NOT_APPROVED.md): named source, small candidate predictor panel, statistical adequacy, fixed candidate model/CV budget, non-pooling rule, training stop conditions and blank supervisor decision fields.
- [Existing full M2a v0.1 research proposal](../gate-da/15_ai_model_development_evaluation_protocol_DRAFT.md): broader study rationale and conditional future multi-cohort evaluation.
- [Existing formal Gate PT methodology checklist](../gate-da/05_gate_pt_methodology_outline_NOT_APPROVED.md): umbrella governance.
- [Tracked approval action — Issue #29](https://github.com/Muhammed-Fathi/CardioAssist-AI/issues/29).

**Explicit status:** P-1 pending, P-3 closed; D-046 read-only local data audit only; D-046-EP not approved. No signed clinical study plan, real model fit or clinical performance exists at this point.

The first Cleveland-only model experiment **does not depend** on first resolving the UCI-412 50% threshold discrepancy, Hungary recodings, Swiss cholesterol zeros, or VA missingness; those are **future multi-site** concerns. It **does depend** on the Cleveland-specific frozen scientific protocol, sample-size assessment, input admissibility, source-training authorization and actual supervisor P-3 signoff.

## Internal-before-supervisor path (requires its OWN human approval)

- [02 — D-047 internal exploratory Cleveland protocol (PROPOSED)](02_d047_internal_exploratory_cleveland_PROTOCOL_PROPOSED.md): a narrowly scoped, maintainer-owned **internal**, not supervisor-approved, modeling exception contemplated by D-046-EP. Requires separate explicit human PR comment, PR merge and protected local authorization.
- [03 — Internal experiment report template (NO RESULTS)](03_internal_exploratory_RESULTS_TEMPLATE.md): honest report structure for initial private research before presenting to supervisor.
- [04 — First internal exploratory results (REVIEW DRAFT)](04_d047_first_internal_results_REVIEW_DRAFT.md): maintainer-reported, sanitized aggregates from the completed D-047 Cleveland run, with calibration limits, sample-size `NOT ASSESSED` status and reviewer checklists. **Internal evidence only — P-3 stays CLOSED; not supervisor-approved, not externally validated.**
- [05 — M2e.1 CAD Riley-style sample-size evidence and adequacy review (REVIEW DRAFT)](05_m2e1_cad_riley_sample_size_adequacy_REVIEW_DRAFT.md): reproduces the published Riley binary-outcome criteria against their worked examples, records the R²-free finding that the published three cannot be met at n = 303 (382 by outcome-proportion precision) and that the additional approximate MAPE criterion requires 459 at p = 8, reports that no eligible anticipated Cox–Snell R² was **identified in the examined sources** (extraction-level screen plus three external CAD studies — not a full-text or literature-wide absence claim), and leaves the status at **`NOT ASSESSED — PENDING HUMAN REVIEW`**. Scenario tables are explicitly hypothetical and adopt nothing. **No approval, no gate action; P-3 stays CLOSED.** The companion verification script is a proposed scope exception to a documentation-only Issue and is pending maintainer decision (Q11).

The formal P-3 approval packet above remains required for supervisor-approved clinical/scientific claims; it must not be presented as a prerequisite to every future internally authorized D-047 exploratory pilot **if D-047 is explicitly ratified**. No approval/experiment is implied by adding these links.
