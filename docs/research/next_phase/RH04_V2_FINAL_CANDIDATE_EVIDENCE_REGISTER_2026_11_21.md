# RH-04 Final Candidate Evidence Register

**Document ID:** CAI-RH04-REGISTER-v2 (supersedes v1)
**Status:** `FINAL_CANDIDATE_PREPARED_NOT_ACCEPTED`
**Delivery SHA:** recorded in the delivery PR body

**Controlling definitions:** `docs/rh04-issue132-acceptance-decision.md` §7.
That document is on `main` and is **not modified** by this branch. Where v1 of
this register disagreed with it, v1 was wrong and has been rebuilt.

---

## 1. A correction to v1

v1 of this register reassigned acceptance IDs. It put producer lineage under
V2-01, the entry point under V2-03, and OOF provenance under V2-04, and it
described implementation work as if it satisfied those gates. **That was wrong.**
§7 defines V2-01 as owner ratification and V2-04 as cross-environment exact
replay; neither is what v1 recorded there.

The original definitions are restored verbatim below. Implementation findings now
carry **`T-*` identifiers only**, and no finding is described as satisfying a gate.

**Zero gates are closed by this document.**

---

## 2. Acceptance gates — original §7 text, verbatim

### V2-01 — Owner ratification

> `V2-01` **Owner ratification** of the V1→V2 transition, recorded in
> `docs/DECISIONS.md`, naming the accepting reviewer and this document's version.

**Status: NOT SATISFIED.** `docs/DECISIONS.md` carries no V1→V2 ratification.
This is the owner's act and is not performable by an agent.

### V2-02 — Solver and criterion declaration

> `V2-02` **Solver + criterion declaration.** Either the hardened
> `deterministic_portable_newton` ... or a documented alternative whose
> convergence test is explicitly *not* host-dependent. **The criterion is part of
> the contract.**

**Status: NOT SATISFIED.**

The measured producer facts are recorded under `T-PRODUCER-FIT` and
`T-CAL-INPUT`. They describe what the registered producer does; they do **not**
declare a host-independent convergence criterion, and they do not harden
`deterministic_portable_newton`.

**An isolated Decimal oracle is not producer provenance.** A Decimal evaluation
can show a criterion has a computable optimum; it cannot show that the archived
scikit-learn parameters were produced by that code path. No such credit is taken.

### V2-03 — New pack, new digest, provenance, delta mapping

> `V2-03` **New pack, new digest.** `research/intake/fixtures/offline_io.v2.json`
> with its own `PACK_SHA256_V2`, recorded provenance (solver, criterion, tolerance,
> generating platform, kernel names), and a written mapping from each V1 expected
> value to its V2 counterpart with the numeric delta. V1 files stay forever frozen.

**Status: NOT SATISFIED.** There is no `offline_io.v2.json`. The Lane B pack is a
set of *archives plus a manifest*, deliberately not a V2 expected-output pack, and
it is addressed by SHA-256 rather than `PACK_SHA256_V2`.

`T-V1V2-MAP` supplies the per-case/per-field structural mapping and `T-V2-DELTA`
the numeric delta mapping; neither is a V2 pack.

V1 remains frozen and byte-identical — see `T-V1-FROZEN`.

### V2-04 — Cross-environment exact replay

> `V2-04` **Cross-environment replay evidence** on the new pack: ≥3 dispatch
> classes × {Python 3.11, 3.12} on Linux, **plus native Windows**, all reporting
> `EXACT_REPLAY`. Deltas-only is *not* acceptable for V2 — that is the entire point.

**Status: NOT SATISFIED, and this is the central finding.**

Measured on the **registered training path**: different dispatch classes produce
**different** results. That is an observed property of the present implementation
under the present numerical libraries — it is **not** a claim of mathematical
impossibility, and this register makes no such claim.

Measured on the **Lane B replay path**: five resident dispatch classes produce one
digest (`T-XENV-LANEB`). That is a different path that performs no fitting.

Lane B's invariance does **not** satisfy V2-04, which is about the pack produced by
regeneration. `T-XENV-LANEB` is evidence for a two-lane amendment, not for V2-04.

**Not measured:** Python 3.12, native Windows, non-x86.

### V2-05 — Dual-run window

> `V2-05` **Dual-run window.** Both V1 (scoped, §6) and V2 gates run in CI until
> the owner retires V1. No silent substitution.

**Status: NOT SATISFIED.** No workflow runs both. The proposal in
`RH04_V2_DUAL_RUN_AND_ROLLBACK_2026_11_21.md` was corrected this round: two Lane B
runs on different BLAS kernels are **not** a dual-run window. Protected workflows
are unmodified pending separate authorization.

### V2-06 — Semantics re-statement

> `V2-06` **Semantics re-statement.** `calibration.json` / `scale_declaration` /
> model cards / manifest wording must stop implying "L-BFGS-B output" and start
> declaring the fitted criterion. Includes the §2.4 artifact-byte statement.

**Status: PARTIAL.** `T-PRODUCER-FIT` now records the actual objective, bounds,
link, solver and fit status. The model-card and manifest *wording* re-statement
across the production surface is **not** done.

### V2-07 — Negative tests

> `V2-07` **Negative tests first:** wrong digest, >29 cases, a drifted
> non-calibration field, a planted second tolerance exception, a
> solver-provenance regression, an unreachable-criterion (fail-closed) case, and a
> V1 pack byte-integrity assertion. Each must fail closed.

**Status: NOT SATISFIED as written.** Every listed case has an implementation test
(`T-NEG-*`), and each fails for its intended reason. But the clause is scoped to
the V2 *pack*, which does not exist; and no listed case is an
**unreachable-criterion fail-closed** test against the registered producer.

Asserting this gate from the `T-NEG-*` tests would be the same category error v1
made.

### V2-08 — Security parity, no new tolerance

> `V2-08` **Security parity:** `_approved_replay_equal`'s type-strictness,
> redaction (`_describe`), no-fallback, fail-closed ordering and refusal-path tests
> must all still pass, and V2 must introduce **no** new tolerance surface.

**Status: SATISFIED BY TEST.** `T-NO-TOLERANCE` and `T-V1-FROZEN` both pass. There
is no numeric tolerance anywhere in Lane B; comparison is exact type-and-value.

### V2-09 — Explicit non-claims

> `V2-09` **Explicit non-claims.** V2 acceptance must state it is engineering
> reproducibility only: no clinical validity, no model-equivalence, no RH-07
> science, no RH-08 release, no D-047/M3a metrics.

**Status: NOT SATISFIED as a gate** (there is no accepted V2 to attach it to).
The non-claims themselves are stated in every document this branch adds.

### V2-10 — Rollback plan

> `V2-10` **Rollback plan:** V2 revert must be a single revert of the pack +
> comparator + gate, leaving V1 intact and green.

**Status: DEMONSTRATED ON A SCRATCH BRANCH** (`T-ROLLBACK`). Because this delivery
is additive, one `git revert` of the delivery commit restores main exactly. The
demonstration executes that revert and runs the V1 checks, rather than inferring
success from a missing file.

---

## 3. Implementation findings (`T-*` only — none is a gate)

| ID | Finding | Evidence |
|---|---|---|
| `T-PRODUCER-FIT` | Actual producer solver/objective/bounds/link recorded: `scipy_lbfgsb`, mean log-loss + L2 anchor 1e-3, intercept [-15,15], slope [0.01,15] | calibrator captured by observation |
| `T-CAL-INPUT` | Calibrator input is the ordered OOF vector, not the design matrix; three identities distinct | pinned in manifest, enforced at admission |
| `T-FAMILY-ORDER` | Inner-selection offsets follow declared order; verified against seeds observed from a real producer run | `20263128` then `20263138` |
| `T-RF-STRUCTURE` | All 9 structural arrays × 50 trees + 4 scalars exact; 10 mutation classes detected | `max_float_delta = 0.0` |
| `T-SELECTION` | Selection reproduced independently, not only conditionally | both routes match |
| `T-SINGLE-READ` | Caller mapping read once; snapshot derives from the admitted result | AST test asserts exactly one read |
| `T-CASE-BIND` | Routes, edits and expected digests bound, not just case ids | 4 refusal paths tested |
| `T-FIXTURE-BIND` | V1 pack verified once, identity carried, replay refuses a changed pack | 2 refusal paths tested |
| `T-V1V2-MAP` | 29/29 cases: identical leaf-path sets, types, statuses | structural mapping |
| `T-V2-DELTA` | Numeric per-field delta mapping between V1 expected and V2 replay | delta report |
| `T-NO-TOLERANCE` | No numeric tolerance in the portable lane | AST scan of scoring functions |
| `T-XENV-LANEB` | Five resident dispatch classes → one digest | resident kernels read from threadpoolctl |
| `T-V1-FROZEN` | V1 pack and comparator byte-identical to main | digest comparison |
| `T-ROLLBACK` | Single revert of the delivery commit restores main; V1 green | scratch-branch demonstration |
| `T-DEPS` | Wider suite runs with no file excluded | 1380 passed / 2 skipped |

## 4. What remains blocking

1. **V2-01** needs the owner, in `docs/DECISIONS.md`.
2. **V2-02** needs a declared host-independent criterion — not more measurement.
3. **V2-04** cannot pass on the registered path as implemented; it requires either
   an owner amendment to the two-lane architecture or a change to the scientific
   method, and the latter is out of scope.
4. **V2-05** needs protected-workflow authorization.
5. Python 3.12, native Windows and non-x86 remain unmeasured.

**No gate is closed. RH-04 is not accepted.**
