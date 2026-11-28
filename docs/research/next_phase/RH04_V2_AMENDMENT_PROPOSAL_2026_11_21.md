# D-V2-7 / V2-04 amendment proposal — two-lane architecture

**Document ID:** CAI-RH04-AMEND-v2
**Status:** PROPOSAL. **Not ratified. Nothing here is in force.**
**Authority:** `docs/rh04-issue132-acceptance-decision.md` §7 remains controlling
until the owner ratifies this document. No gate is marked accepted here.

---

## 1. Why an amendment is proposed

V2-04 as written requires **`EXACT_REPLAY` for the registered regeneration path**
across ≥3 dispatch classes × {Python 3.11, 3.12} on Linux, plus native Windows.

Measured fact: the registered path is **not** kernel-invariant. Five resident
environment classes produce **two** different result groups (`aea7d617…` and
`3366be81…`), and the grouping does not even follow the environment class
(`Sandybridge` and `Prescott` share a result despite differing classes).

On the evidence available, V2-04 cannot be met by Lane A **under the present
implementation**: the registered path trains scikit-learn models whose numerics
depend on the BLAS dispatch actually loaded.

**This is an observed property of this implementation and these numerical
libraries. It is not a claim of mathematical impossibility.** Nothing here
establishes that no training procedure could be host-independent, and this
document does not assert that. What is established is narrower and sufficient for
the decision: with the registered producer as it is, across five measured resident
dispatch classes, the results differ.

Meeting V2-04 on the registered path would therefore require changing the
scientific method (a dispatch pin) or changing the producer, both of which are
outside this bounded round and were not attempted.

Meanwhile a genuinely portable inference path **does** exist and does achieve
exact replay — not by tolerance, but because rehydration from declarative arrays
into a real scikit-learn estimator is measured bit-identical to the original
fitted estimator.

The amendment therefore separates two questions that V2-04 currently conflates.

---

## 2. Clause-by-clause amendment

### V2-04 — *was:* cross-environment replay evidence

> **ORIGINAL**
>
> `V2-04` **Cross-environment replay evidence** on the new pack: ≥3 dispatch
> classes × {Python 3.11, 3.12} on Linux, **plus native Windows**, all reporting
> `EXACT_REPLAY`. Deltas-only is *not* acceptable for V2 — that is the entire
> point.

> **PROPOSED REPLACEMENT**
>
> `V2-04` is split into two independently verifiable gates.
>
> `V2-04a` **Registered regeneration across the environment matrix.** Run the
> registered synthetic regeneration on ≥3 dispatch classes × {Python 3.11, 3.12}
> on Linux plus native Windows, recording requested dispatch, **resident** kernel
> name and version, interpreter and package versions, and the resulting semantic
> digest. Each cell reports the verdict it actually produces. `EXACT_REPLAY` is
> required **within a declared host class**; across classes, a differing digest is
> recorded as a **named portability finding** and is *not* treated as a failure of
> the implementation. No tolerance is introduced. This gate deliberately does
> **not** claim training reproducibility across classes.
>
> `V2-04b` **Portable inference exact replay.** Load the pinned, independently
> admitted portable reference artifact and execute the complete registered set of
> cases through the registered request/response facade on the same matrix. **All
> cells must report exact type-and-value agreement, with no numeric exception
> surface.** A difference in any field, in any cell, fails the gate.

> **Reasons.** (a) V2-04a and V2-04b answer different scientific questions
> ("did training reproduce?" vs "does this artifact score identically
> everywhere?"). (b) The original clause is unachievable for Lane A without
> altering the method. (c) The replacement is *stricter*, not looser, for the
> portable lane: it mandates exactness with no tolerance rather than permitting
> deltas.

> **Changed guarantees.** V2-04 previously implied that the *registered path*
> would replay exactly everywhere. That implication is withdrawn as unachievable
> and replaced with an explicit per-class statement plus an exact portable gate.

> **Residual risks.** Lane A portability limitations are now *documented* rather
> than hidden; a future OpenBLAS rebuild could add a class. Lane B's exactness is
> conditional on the artifact being correctly admitted — mitigated by the
> external manifest, and by the fact that a forged artifact changes the digest and
> is refused.

### V2-03 — *was:* new pack, digest, provenance, complete delta mapping

> **ORIGINAL**
>
> `V2-03` **New pack, new digest.** `research/intake/fixtures/offline_io.v2.json`
> with its own `PACK_SHA256_V2`, recorded provenance (solver, criterion,
> tolerance, generating platform, kernel names), and a written mapping from each
> V1 expected value to its V2 counterpart with the numeric delta. V1 files stay
> forever frozen.

> **PROPOSED ADDITION** (original text retained; one paragraph appended)
>
> Additionally, when the two-lane architecture is adopted, V2-03 must describe
> **two distinct reference identities**: the Lane A regeneration digest and the
> Lane B portable reference identity (archive digests + trusted-manifest digest).
> The candidate must remain labelled unratified until review; a pinned pack may
> only be created after ratification.

> **Reasons.** Round 9 and Round 10 each introduce new identities; without a
> clause they could be mistaken for a ratified pack.

### V2-06 — *was:* semantics re-statement

> **ORIGINAL**
>
> `V2-06` **Semantics re-statement.** `calibration.json` / `scale_declaration` /
> model cards / manifest wording must stop implying "L-BFGS-B output" and start
> declaring the fitted criterion. Includes the §2.4 artifact-byte statement.

> **PROPOSED ADDITION**
>
> V2-06 must additionally state, for the portable lane, that its numerical
> contract is *rehydration of declarative parameters into the registered
> estimator class*, that this is measured bit-identical to the fitted estimator
> on the recorded families, and that it is **not** a claim about training
> reproducibility. Calibration semantics remain intercept-first with the
> registered `intercept + slope * raw_log_odds` contract.

### V2-05 — *unchanged in substance, restated*

Dual-run of the V1 and V2 gates in CI remains **required** until explicit owner
retirement of V1. This proposal adds nothing and removes nothing.

> **PROPOSED ADDITION:** the V2 dual-run includes **both** V2-04a and V2-04b,
> and a failure in either blocks the window.

### V2-07 — *unchanged in substance, extended*

Required negative tests remain mandatory. Added to the list, drawn from the
implemented evidence:

- forged artifact with a recomputed internal hash and a valid MAC;
- coordinated binding change (training identity and preprocessing altered
  together);
- swapped route and route absent from the manifest;
- wrong trusted key;
- non-finite, wrongly typed and out-of-range parameters;
- tree cycle, unreachable node, hostile node count;
- evaluation attempted on an archive with no manifest entry;
- a **self-consistent forgery** for a valid Logistic Regression model: one finite
  coefficient changed, internal digest recomputed, fixture MAC re-signed with the
  published key, forged manifest re-pinned. Refused because the manifest is not
  the trust anchor (Round 10.2);
- a manifest whose pinned registry-metadata digest or complete ordered
  training-input digest does not match what is actually loaded or recomputable
  (Round 10.2);
- an archive that stores the publication-prohibited SHAP training projection in
  any form, including base64 (Round 10.2);
- **construction** of a replay without a trusted manifest and key (Round 10.1:
  admission is in the constructor, not an optional helper);
- an archive whose split assignment or SHAP background digest disagrees with the
  independently trusted manifest, even after the attacker recomputes the
  archive's own hash, re-signs it with the committed key and re-pins the manifest
  entry — the assignment is recomputed from the pinned seed schedule, which the
  attacker cannot make agree with a different fold partition.

### V2-08 — *unchanged, and the Round 9 risk is retired*

> **ORIGINAL**
>
> `V2-08` **Security parity:** `_approved_replay_equal`'s type-strictness,
> redaction (`_describe`), no-fallback, fail-closed ordering and refusal-path
> tests must all still pass, and V2 must introduce **no** new tolerance surface.

Round 9 introduced `DECLARED_SCORE_AGREEMENT = 1e-14`, arguably a new tolerance
surface. **This proposal removes it.** The portable lane now requires exact
equality against its own fixed reference identity, so V2-08 can be satisfied as
written with no ruling needed.

Round 10.1 adds one clarification that this proposal should carry: Lane B's exact
equality is directed at **Lane B's own** versioned reference, never at freshly
generated Lane A output. Rehydration is bit-identical to a fitted estimator
*within a process on the same host*; that measurement does not make Lane A a
valid expected reference for Lane B, and no test uses it that way.

### V2-02 — the fitted solver criterion, under two lanes

The original V2-02 asks that the fitted solver criterion be demonstrably reachable
and correctly reported. **This proposal does not credit an isolated Decimal oracle
as the solver that generated a rehydrated scikit-learn artifact.** Under the
two-lane design the honest statement is:

* **Lane A** runs the project's real training path. Its solver criterion is
  whatever `ai/training.py` specifies for the selected profile
  (`lbfgs`/`max_iter=1000` for `AI1_GENERIC_V1`), and convergence is reported by
  scikit-learn itself.
* **Lane B** does not fit anything. It rehydrates already-fitted parameters, so it
  makes **no** solver claim at all. Its obligation is parameter *identity*, which
  Round 10.3 satisfies by refitting from the producer cohort and matching exactly.
* A Decimal arithmetic oracle can support V2-03's determinism claims as a
  *diagnostic*, but it must never be described as the optimisation that produced
  the artifact.

Consequence: V2-02 remains **not satisfied**, because the criterion-reachability
demonstration has not been executed against the real training run. It is not
satisfied by the rehydration work, and this proposal does not claim otherwise.

### V2-09 — *unchanged*

Non-claims remain: engineering reproducibility only, no clinical validity, no
model equivalence, no RH-07 science, no RH-08 release, no D-047/M3a metrics.

### V2-10 — *strengthened*

> **ORIGINAL**
>
> `V2-10` **Rollback plan:** V2 revert must be a single revert of the pack +
> comparator + gate, leaving V1 intact and green.

> **PROPOSED REPLACEMENT**
>
> V2-10 requires an **executable** demonstration, not a statement of intent: on a
> scratch branch, revert the V2 pack + comparator + gate in one commit and show
> (a) V1 remains byte-identical to `main`, (b) the V1 gate passes, (c) no V2
> artifact is referenced by any remaining code path. The demonstration is
> recorded with its commit SHA.

### V2-01 — *unchanged*

Owner ratification in `docs/DECISIONS.md`, naming the accepting reviewer and this
document's version. **Not performed here and not performable by the agent.**

### D-V2-7 — *remains proposed*

Frozen-parameter reuse stays unratified. Lane B is an **inference** path over a
fixed artifact; it does not replace regeneration, and Path A remains the only
path that produces a reference from data.

---

## 3. What Lane B does and does not prove

| establishes | does not establish |
|---|---|
| scoring and calibration are host-independent **by construction** | that training is reproducible |
| a real, tampered-with artifact is refused | that the model is scientifically valid |
| the registered facade's behaviour is preserved for all cases | clinical validity or model equivalence |
| exact replay without any tolerance | that a `prevalence_dummy` model could be represented |

## 4. Recommendation

**Adopt the two-lane architecture** as the smallest defensible arrangement:

- Lane A stays the sole scientific reference and honestly reports per-class
  behaviour.
- Lane B gives the reproducible artifact the roadmap needs an exact replay for.
- The two are compared diagnostically; numeric deltas between evaluators are
  **evidence**, never an acceptance tolerance.

This satisfies V2-04's *purpose* — reproducible delivery across environments —
without pretending the registered training path is bit-portable, and without
weakening any existing clause.

## 5. Status of every gate after this proposal

Unchanged and deliberately so: **zero of ten gates are closed.** V2-04 remains
`NOT MET` under the original text, and would be replaced by V2-04a/b only on
ratification.

---

## 6. Round 10.4 addendum — V2-02 stated explicitly

Round 10.4 does not change this proposal's direction. It makes the V2-02 position
exact, because V2-02 is the clause most likely to be read as satisfied by accident.

### 6.1 The actual producer solver and fitted criterion

| element | value |
|---|---|
| calibrator | `OofLogisticCalibrator`, `FULL_DEVELOPMENT_OOF_FINAL` |
| solver | `scipy_lbfgsb` (L-BFGS-B) |
| objective | mean log-loss + `0.5 * l2_anchor * (a² + (b-1)²)`, `l2_anchor = 1e-3` |
| bounds | intercept `[-15, 15]`, slope `[0.01, 15]` |
| input link (LR route) | `exact_raw_log_odds` — exact affine map, no clamping |
| input link (tree route) | `clipped_logit_of_raw_probability` — clamp to `[1e-6, 1-1e-6]` then logit |
| estimator (LR route) | `lbfgs`, `max_iter=1000`, `AI1_GENERIC_V1` |
| estimator (tree route) | `RandomForestClassifier`, `max_features="sqrt"`, 50 trees, `n_jobs=1` |

Both routes were measured by driving the registered producer and intercepting the
real fit: intercepts and slopes match the archived calibrators **exactly**.

### 6.2 Why an isolated Decimal oracle is not evidence

A Decimal oracle can establish that a *criterion* has a computable optimum. It
cannot establish that the archived `sklearn` parameters were produced by the code
path that actually ran. Those are different claims, and only the first is
mathematical. The second requires the producer itself, which is what §6.1 does.

V2-02 therefore remains **NOT SATISFIED**. Lane B does not fit, so it makes no
solver claim; and Lane B's silence is not a demonstration of criterion
reachability.

### 6.3 Guarantees retained and withdrawn under the two-lane split

| guarantee | Lane A | Lane B |
|---|---|---|
| scientific reference produced from data | **retained** | withdrawn (Lane B fits nothing) |
| model selection reproduced from the producer | **retained** | withdrawn |
| exact replay across dispatch classes | withdrawn (physically impossible without a dispatch pin) | **retained** |
| refusal of tampered artifacts | retained | **retained** |
| registered facade behaviour for all 29 cases | retained | **retained** |
| training reproducibility demonstrated | **retained** as per-class, not exact | withdrawn |
| solver provenance | **retained** (§6.1) | withdrawn |

The precise limit of the new acceptance claim: Lane B asserts that a **fixed,
independently admitted artifact** evaluates identically everywhere, through the
registered facade, with no fitting and no tolerance. It asserts nothing about how
that artifact came to exist. That is Lane A's claim, and Lane A's claim is
exact-only per dispatch class, never across classes.

### 6.4 What is still not established

Cross-environment exactness is **not** described as established for the training
path. It is established for Lane B's replay, measured on five resident dispatch
classes (§V2-10 of the evidence register), and it is not established at all for
Python 3.12, native Windows or non-x86.

No numerical acceptance tolerance is introduced by this addendum. Where two lanes
produce different numbers, that difference is **evidence about the environment**,
never a threshold that a run is allowed to pass through.

**Nothing in this addendum is ratified. Zero of ten gates are closed.**


---

## 7. Ratification packet — explicit original / proposed text

**Status: PROPOSAL. Not ratified by the agent.** `docs/rh04-issue132-acceptance-decision.md`
§7 remains controlling until the owner acts. Each clause below quotes the original
verbatim and proposes replacement text.

### V2-02 — Solver and criterion declaration

**Original (§7):**
> `V2-02` **Solver + criterion declaration.** Either the hardened
> `deterministic_portable_newton` (whose P0 issues ... must be *closed*, not merely
> patched ...) or a documented alternative whose convergence test is explicitly
> *not* host-dependent. **The criterion is part of the contract.**

**Proposed:**
> `V2-02` **Solver + criterion declaration, per lane.**
>
> **Lane A (registered regeneration).** The producer's fitted objective, bounds,
> input link and solver are declared and recorded: mean log-loss plus an L2 anchor
> of 1e-3 around slope 1, intercept bounds [-15, 15], slope bounds [0.01, 15],
> solver `scipy_lbfgsb` (L-BFGS-B), input link `exact_raw_log_odds` for the linear
> route and `clipped_logit_of_raw_probability` for the tree route, fit scope
> `FULL_DEVELOPMENT_OOF_FINAL`, fit status `FITTED_OOF_MONOTONE_LOGISTIC`. These
> are **observed properties of the present implementation**, recorded so a reviewer
> can see what ran. They are **not** a guarantee of host independence, and this
> clause does not assert one.
>
> **Lane B (fixed-artifact replay).** **No fitting or optimization takes place.**
> Lane B rehydrates declared arrays into real scikit-learn objects and executes the
> registered facade. It therefore makes **no fitted-solver claim**, and its
> host-independence follows from performing no arithmetic that depends on the
> fitted solution.
>
> **Provenance.** An isolated arbitrary-precision oracle is **not** accepted as
> evidence of producer provenance. Provenance requires the registered producer,
> captured at its own boundary.

### V2-04 — cross-environment replay (consequential)

**Original:** as quoted in §2 above.

**Proposed:** replace with two separately-labelled criteria:

> `V2-04a` **Lane A cross-environment evidence — diagnostic.** Lane A is executed
> across ≥3 resident dispatch classes and the per-class result groups are reported.
> Differences are recorded as findings. **No exactness is required or claimed.**
>
> `V2-04b` **Lane B cross-environment exact replay — mandatory.** For a fixed,
> independently admitted artifact set, every measured resident dispatch class must
> report the identical reference digest, with no numeric tolerance.

The clause is **split, not weakened**: the original exactness requirement is
retained in full and moved to the lane that can satisfy it, and the lane that
cannot satisfy it is required to report its differences instead of hiding them.

### Clauses not proposed for change

V2-01, V2-03, V2-05 … V2-10 keep their original text. V2-05's dual-run window and
V2-10's rollback are clarified in `RH04_V2_DUAL_RUN_AND_ROLLBACK_2026_11_21.md`
without altering the clauses.

### What ratification would and would not do

**Would:** move the exactness requirement to Lane B and permit Lane A to report
per-class results.
**Would not:** close any gate; authorize production use; establish clinical
validity; or make RH-04 accepted.

**Owner action required, in `docs/DECISIONS.md`, naming the reviewer and this
document's version.**
