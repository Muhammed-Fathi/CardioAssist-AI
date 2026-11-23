# RH-04 V2 — final decision-register wording for owner ratification

**Document ID:** CAI-RH04-V2-DECISION-WORDING-v1
**Status:** **PROPOSED TEXT ONLY.** Nothing below is in force. No entry exists in
`docs/DECISIONS.md` and this file does not create one. Ratification is an owner act.

---

## 0. What the owner is being asked to do

Three separable acts, which must not be merged into one:

| # | act | closes |
|---|---|---|
| A | Ratify the two-lane architecture (CAI-RH04-AMEND-v3) | the *scope* question in V2-04 |
| B | Accept the V2 evidence package as substantial and sufficient for the gates named below | nothing on its own |
| C | Record V2-01 in `docs/DECISIONS.md` | V2-01 |

A and B are prerequisites of C, not substitutes for it. This document supplies
wording for all three and recommends performing them in order.

---

## 1. Proposed decision text — architecture (act A)

> **CAI-DECISION-RH04-LANES**
>
> The RH-04 V2 workstream is ratified as a **two-lane architecture**.
>
> **Lane A** is the registered research regeneration path. It trains, selects,
> calibrates and replays through the project's own `ai.training` code. Its purpose
> is to answer *"did training, selection and calibration reproduce?"*. It is
> **diagnostic**: numerical divergence between environments is a reportable
> finding, recorded with its environment identity, and is not by itself a failure.
> Training failure, missing evidence and invalid output **are** failures.
>
> **Lane B** is the fixed-artifact inference path. It admits a versioned,
> independently authenticated artifact set and replays all 29 registered cases
> through the real facade against a fixed reference identity
> (`891d9e3b2a332c6efc251d97fee25ed46a627ed25b2a089594057b4c9896cdc8`) with
> **no numeric tolerance**. Its purpose is to answer *"does this artifact score
> identically everywhere?"*.
>
> **Neither lane replaces the other.** Lane B is an inference reference. It is not
> a regeneration reference, it does not ratify `D-V2-7`, and it is not bit-identical
> to scikit-learn.
>
> **The cross-environment matrix is retained in full:** at least three resident
> dispatch classes on Linux Python 3.11, at least three on Linux Python 3.12, and
> native Windows. It is **not** substituted by whichever environments happened to
> be measurable. V2-04a requires Lane A evidence to be *reported* across that
> matrix; V2-04b requires Lane B to *pass exactly* across it.
>
> **Lane B portability is a measured property, not a deduction.** It does not follow
> from the absence of training, and it must be re-measured for any new environment.

---

## 2. Proposed decision text — evidence acceptance (act B)

> **CAI-DECISION-RH04-EVIDENCE**
>
> The owner has reviewed the RH-04 V2 evidence package at the frozen delivery SHA
> and records the following as established:
>
> 1. Lane B replays all 29 registered cases through the real facade and produces the
>    fixed digest exactly, with zero numeric deltas across 479 compared leaves,
>    where the comparison is demonstrated able to detect a change of one part in
>    10^15.
> 2. The complete per-expected-value mapping exists: 29 of 29 cases, every leaf
>    classified, no leaf dropped or coerced.
> 3. Lane A convergence is observed from the registered path, not asserted:
>    100 of 100 observed logistic fits satisfy the solver's own declared stopping
>    rule, evaluated independently in decimal arithmetic, with no fit reaching its
>    iteration cap.
> 4. Hosted CI has produced a fully green run of the synthetic-runner workflow with
>    the V2 tests present: 2098 passed and 2 skipped on both Python 3.11 and 3.12,
>    and 396 UCI-412 tests passing.
> 5. The frozen V1 artifacts are byte-identical to the base commit.
>
> **Not established, and not claimed:** clinical validity, model equivalence with
> scikit-learn, host-independence of Lane A, native Windows evidence (not yet
> executed), or Linux Python 3.12 Lane B replay measured outside hosted CI.

---

## 3. Proposed `docs/DECISIONS.md` entry (act C, closes V2-01)

> ### D-RH04-V2-01 — RH-04 V2 transition ratified
>
> **Date:** <owner to set>
> **Reviewer:** <owner to name>
> **Decision document:** `docs/rh04-issue132-acceptance-decision.md` §7, as amended
> by `CAI-RH04-AMEND-v3`
> **Evidence package:** PR #141 at <frozen SHA>
>
> The owner ratifies the V1→V2 transition for the RH-04 workstream under the
> two-lane architecture recorded in `CAI-DECISION-RH04-LANES`, on the evidence
> recorded in `CAI-DECISION-RH04-EVIDENCE`.
>
> **Scope of this ratification:**
>
> * research reproducibility and artifact portability only;
> * the synthetic 29-case reference pack only;
> * no production activation, no clinical claim, no real-data fitting.
>
> **Explicitly not ratified by this entry:**
>
> * `D-V2-7` — Lane B remains an inference path and does not replace regeneration;
> * any retirement of V1 — V1 remains the mandatory scoped gate until separately
>   retired;
> * the V2-06 production wording change, which needs its own authorization.
>
> **If V1 blocks the transition despite successful V2 evidence**, the required act
> is an explicit retirement decision recorded here, naming the reviewer and the
> effective date. Suppressing a V1 failure to avoid that decision is not permitted.

---

## 4. Recommendation on ordering

1. **Act A first.** Ratifying evidence against an unratified architecture is
   incoherent: the matrix requirement, and therefore what counts as satisfied,
   depends on the lane split.
2. **Act B second**, because it is a statement about evidence and does not close a
   gate by itself.
3. **Act C last.** It is the only act that closes a gate, and it is the only one
   that must be recorded in `docs/DECISIONS.md`.

---

## 5. What this document is not

* It is **not** a ratification, and creates no `DECISIONS.md` entry.
* It does **not** close V2-01 or any other gate.
* It does **not** authorize a merge, an Issue #132 closure, or production use.
* It does **not** retire V1.

The wording above is offered so that the owner can ratify precisely and narrowly,
rather than by referring to a PR body that will keep changing.
