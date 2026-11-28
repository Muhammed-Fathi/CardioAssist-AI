# RH-04 V2 acceptance ledger — v3, reconciled against the amendment packet

**Document ID:** CAI-RH04-V2-LEDGER-v3
**Supersedes:** `RH04_V2_ACCEPTANCE_LEDGER_RESTORED_2026_11_21.md` (v2)
**Status:** **unratified.** No gate below is closed by this file. Issue #132 stays
**OPEN**. Zero of ten closed.

The acceptance ID meanings are the original `docs/rh04-issue132-acceptance-decision.md`
§7 meanings, as v2 restored them. This file does not reassign any ID. It records,
per gate, the evidence obtained since v2, the amendment now proposed, and what
remains refused.

---

## 1. Change since v2

| gate | v2 status | v3 status | what changed |
|---|---|---|---|
| V2-01 | OPEN | **OPEN** | unchanged; owner-only |
| V2-02 | PARTIAL | **PARTIAL** | amendment text written; criterion still not shown host-independent |
| V2-03 | PARTIAL | **PARTIAL** | pack now bound to approved identity; per-value delta table still missing |
| V2-04 | NOT MET | **NOT MET** | divergence measured, reproduced, and **observed non-deterministic in hosted CI** |
| V2-05 | NOT STARTED | **PROPOSED** | stage contract written; nothing wired into CI |
| V2-06 | PARTIAL | **PARTIAL** | semantics clause drafted; production wording untouched |
| V2-07 | PARTIAL | **PARTIAL** | four negative tests added, one mutation-verified; unreachable-criterion reconciled |
| V2-08 | LARGELY SAT | **LARGELY SAT** | comparator byte-identical; still no tolerance |
| V2-09 | LARGELY MET | **LARGELY MET** | unchanged |
| V2-10 | N/A YET | **DEMONSTRATED, unratified** | single revert repeated on the final version |

Nothing moved to closed. Three rows moved from "not started / not applicable" to
"proposed / demonstrated", which is *evidence*, not closure.

---

## 2. Per-gate record

### V2-01 — Owner ratification in the decision register — **OPEN**
Owner action only. No `docs/DECISIONS.md` entry exists and I cannot create one for
my own work. Unchanged from v2.

### V2-02 — Solver and host-independent convergence criterion — **PARTIAL**
Two profiles declared and enforced (`T-OBJECTIVES`); unknown profiles refused. The
decimal criterion is a declared gradient tolerance reached with measured residual.
**Not satisfied:** "host-independent" is an empirical claim and the empirical
matrix does not support it for Lane A — the diagnostic diverges on 2 of 5 kernels.
The amendment therefore narrows the claim rather than asserting it. Retained:
criterion declared and measured. Withdrawn: the implication that declaration alone
establishes host-independence.

### V2-03 — New pack, digest, provenance, complete delta mapping — **PARTIAL**
The pack is now bound to its own independently approved identity: admission
verifies `canonical_response_digest` against the reviewed `PACK_SHA256`
(`0307b396…`), plus the approved bindings and requests, and replay materialises
requests from the verified snapshot rather than re-reading disk. A negative test
edits a base request while preserving case IDs, edits and order, and is refused.
**Still missing:** a per-expected-value delta table across all 29 cases. The
candidate remains explicitly not a pinned pack.

### V2-04 — Exact replay on the required cross-environment matrix — **NOT MET**
Original text requires ≥3 dispatch classes × Linux 3.11 and 3.12, plus native
Windows, all `EXACT_REPLAY`. **This matrix is retained as written** — it is not
replaced by "measured environments".

Measured now, for the first time with reproduction:

| kernel | differing cases |
|---|---|
| unset | 0 (`EXACT_REPLAY`) |
| Prescott | **2** |
| Haswell | **2** |
| Nehalem | 1 |
| Sandybridge | 1 |

CI's 3.12 diagnostic reported exactly 2 differing cases at `f78f521`, matching
Prescott/Haswell. **Hosted non-determinism is now directly observed:** the same
diagnostic command on the unchanged workflow passed at `89b0a8f` twenty minutes
later, on a commit whose only changes are files the diagnostic does not import. So
the gate is not deterministically red — it is environment-dependent, which is a
stronger form of the same finding.
So Lane A cannot produce `EXACT_REPLAY` across ≥3 classes without changing the
scientific method, which is forbidden. **Not met, and not amendable to "met" by
redefinition** — only by an owner decision on scope. Lane B does replay all 29
cases exactly, but that is a different question and is recorded as `V2-04b` under
amendment, not as V2-04 satisfied.

### V2-05 — Dual-run V1/V2 window — **PROPOSED**
Stage contract written (`RH04_V2_DUAL_RUN_AND_ROLLBACK_2026_11_21.md`): V1 mandatory,
Lane A **classified** (divergence reportable; training failure, missing evidence and
invalid output are failures), Lane B mandatory, security checks mandatory; every
stage reports even when another fails. **Nothing is wired into CI.** Wiring requires
workflow authorization beyond the three named dependability items.

### V2-06 — Semantics re-statement — **PARTIAL, deliberately not actioned**
Clause drafted in the amendment packet. Production `calibration.json`,
`scale_declaration`, model cards and manifest text are untouched, because editing
them is an activation change outside this authorization.

### V2-07 — Required negative tests — **PARTIAL**
Added this round:

- `test_changed_base_request_is_refused_before_admission` — base request edited with
  IDs, edits and order preserved → refused on approved-identity mismatch.
- `test_the_executed_snapshot_is_materialised_before_verification` — replaces an AST
  count. **Mutation-verified against both implementations**: passes (1 traversal) on
  the fix, fails (4 traversals) on the old code. Two earlier attempts passed against
  the old code and were discarded rather than kept as decoration.
- `test_a_pack_with_more_than_29_cases_is_refused` — 30-case pack refused. Note the
  refusal arrives via the registered case-set comparison, not a bare count check;
  the test asserts the actual message so it cannot drift into asserting a fiction.
- `test_the_admission_isclose_is_structural_not_an_acceptance_tolerance` — the
  "planted second tolerance exception" requirement, inverted honestly: there is
  exactly one `isclose` and it is a structural admission invariant on tree class
  proportions, not a replay tolerance. The test fails if a second numeric
  comparison is introduced anywhere in the module.

**Still open:** the unreachable-criterion case is reconciled in the amendment — it
stays a negative test, and the amendment states plainly that the criterion is
unreachable *by construction* in Lane B rather than pretending otherwise.

### V2-08 — Security parity, no new tolerance — **SATISFIED IN SUBSTANCE**
Canonical comparator byte-identical to `main`; `DECLARED_SCORE_AGREEMENT` remains
removed; Lane B has no numeric tolerance surface. The amendment explicitly adds
"no new acceptance tolerance" and does not reopen the question.

### V2-09 — Explicit non-claims — **LARGELY MET**
Declaration carries `acceptance_reference: false`, `replaces_regeneration: false`,
`ratifies_D_V2_7: false`, `bit_identical_to_scikit_learn: false`. Amendment adds one
more: **the absence of training in Lane B is not evidence of host independence** —
that is measured, not inferred.

### V2-10 — Single-revert rollback — **DEMONSTRATED on the final version, unratified**
Repeated **after** the pack, comparator and admission corrections were in place.
Squash the delivery to one commit on a scratch branch from `origin/main`, then a
single `git revert`:

| check | result |
|---|---|
| single command | one `git revert --no-edit` |
| reverted tree | `3106bece1fe0e7c09ff0635d66cc883d1ecca33e` |
| `origin/main` tree | `3106bece1fe0e7c09ff0635d66cc883d1ecca33e` |
| equality | **identical** |
| V2 files after revert | **0** present |
| V1 suite executed | **457 passed** in 35.12 s |

This is a demonstration, not a ratification, and it does not close V2-10 — a gate
is closed by the owner, not by a passing script.

---

## 3. Gate summary

| Gate | Status |
|---|---|
| V2-01 | OPEN — owner only |
| V2-02 | PARTIAL |
| V2-03 | PARTIAL |
| V2-04 | **NOT MET** (matrix retained verbatim) |
| V2-05 | PROPOSED — not wired |
| V2-06 | PARTIAL — deliberately not actioned |
| V2-07 | PARTIAL |
| V2-08 | SATISFIED IN SUBSTANCE |
| V2-09 | LARGELY MET |
| V2-10 | DEMONSTRATED, unratified |

**Closed: 0 of 10.**

---

## 4. Explicit non-claims

- No clinical validity, no model equivalence, no patient readiness.
- Lane B is **not** bit-identical to scikit-learn, and its portability does **not**
  come from being untrained — it comes from fixed artefacts and exact replay, both
  of which are measured.
- Lane A divergence is a **finding**, not a licence: failed training, missing
  evidence and invalid output remain failures.
- Fixed coefficients do not imply SHAP/LIME reproducibility.
- Hosted CI post-correction has **not** been read. No claim is made that the
  infrastructure failures are resolved.
