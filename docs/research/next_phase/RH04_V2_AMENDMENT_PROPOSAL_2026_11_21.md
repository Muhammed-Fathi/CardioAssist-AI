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

So V2-04 cannot be met by Lane A for a reason that is *physical*, not a defect
to be fixed: the registered path trains scikit-learn models whose numerics depend
on the BLAS dispatch. Meeting it would require changing the scientific method
(a dispatch pin), which every standing instruction forbids.

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
- evaluation attempted on an archive with no manifest entry.

### V2-08 — *unchanged, and the Round 9 risk is retired*

> **ORIGINAL**
>
> `V2-08` **Security parity:** `_approved_replay_equal`'s type-strictness,
> redaction (`_describe`), no-fallback, fail-closed ordering and refusal-path
> tests must all still pass, and V2 must introduce **no** new tolerance surface.

Round 9 introduced `DECLARED_SCORE_AGREEMENT = 1e-14`, arguably a new tolerance
surface. **This proposal removes it.** The portable lane now requires exact
equality, so V2-08 can be satisfied as written with no ruling needed.

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
