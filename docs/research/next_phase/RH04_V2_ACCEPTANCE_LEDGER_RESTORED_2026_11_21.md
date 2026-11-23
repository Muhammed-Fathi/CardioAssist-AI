# RH-04 V2 acceptance ledger — restored to the controlling contract

**Document ID:** CAI-RH04-V2-LEDGER-v2
**Supersedes:** `RH04_V2_LEDGER_ROW_UPDATE_2026_11_21.md` (Round 8)
**Status:** unratified. No gate below is closed by this file. Issue #132 stays **OPEN**.

## 0. Correction notice

The Round 8 ledger **reassigned the meanings of the V2 acceptance IDs** and is
withdrawn as an acceptance record. It claimed:

| Round 8 claim | Controlling text | Verdict |
|---|---|---|
| V2-01 = calibration-ordering correction | V2-01 = owner ratification in the decision register | **wrong** |
| V2-02 = source-specific objectives | V2-02 = solver + convergence-criterion declaration | **wrong** |
| V2-03 = 29-case candidate pack | V2-03 = new pack, digest, provenance, complete delta mapping | **partly aligned, still wrong scope** |
| V2-04 = Path B round trip | V2-04 = exact replay on the required cross-environment matrix | **wrong** |
| V2-05 = portability scope | V2-05 = dual-run V1/V2 CI window | **wrong** |
| V2-07 = exit policy | V2-07 = required negative tests | **wrong** |

A toy Path B test is **not** V2-04 completion. A calibration-order repair is
**not** V2-01 ratification. The two ID systems below are separated permanently.

## 1. Implementation-task IDs (what the agent may complete)

These are *work items*. Completing one closes nothing.

| Task | Description | State |
|---|---|---|
| `T-CAL-ORDER` | Intercept/slope ordering corrected against the production contract | **DONE** |
| `T-OBJECTIVES` | Distinct Cleveland/liblinear and generic/lbfgs objectives | **DONE** |
| `T-SELECTION` | Actual selected family/profile/hyperparameters recorded per source | **DONE (round 9)** |
| `T-PORTABLE` | Declarative portable archive rehydrated into the registered estimator | **DONE (round 10)** |
| `T-ADMISSION` | Independent trusted manifest + HMAC; verifier derives nothing from the artifact | **DONE (round 10)** |
| `T-ADMISSION-PATH` | Admission is mandatory **in the replay constructor** and runs for every route before any facade call; missing/unexpected/swapped/duplicate/foreign-key routes refuse | **DONE (round 10.1)** |
| `T-REPLAY29` | **All 29 cases executed through the real facade**, exact type-and-value | **DONE (round 10)** |
| `T-NOTOLERANCE` | Portability established without a numeric tolerance; `1e-14` removed | **DONE (round 10)** |
| `T-LANEB-INDEPENDENT` | Lane B reads no producer bundle: model, preprocessing, calibration, fold ensemble, SHAP background and descriptor all come from pinned archive/manifest/registry declarations | **DONE (round 10.1)** |
| `T-LANEB-FIXEDREF` | Lane B has its own fixed reference identity from the pinned artifact (`891d9e3b…`), never a freshly trained Lane A result | **DONE (round 10.1)** |
| `T-MANIFEST-COMPLETE` | Raw archive-file SHA-256, semantic digest, actual ordered split/fold assignments, calibration OOF provenance, SHAP background digest, registry metadata digest; `build_manifest()` emits the real 29 case IDs | **DONE (round 10.1)** |
| `T-CONCURRENCY` | No mutable request/binding/panel state; 8 concurrent executions leak nothing | **DONE (round 10.1)** |
| `T-MANIFEST-ANCHOR` | The trusted manifest is authenticated against a hash compiled into reviewed source; a manifest supplied beside the archives is not an anchor | **DONE (round 10.2)** |
| `T-SHAP-POLICY` | No publication-prohibited training projection is committed in **any** representation; the background is deterministically reconstructed and digest-checked | **DONE (round 10.2)** |
| `T-ENFORCE-ALL` | Raw-file bytes, registry metadata digest and the complete ordered training-input digest are all *enforced*, not merely recorded | **DONE (round 10.2)** |
| `T-CONTEXT-LOCAL` | Dispatch is context-local; 8 simultaneous full 29-case replays and nested contexts dispatch correctly and restore the facade loader | **DONE (round 10.2, corrected round 10.3)** |
| `T-LINEAGE` | Producer configuration imported from the registered producers; the five seed roles kept distinct; refit reproduces the archived estimator exactly | **DONE (round 10.3)** |
| `T-ONE-ENTRY` | A single supported admission + replay entry point; the cold path, matrix and docs all use it; no raw-dict admission shortcut | **DONE (round 10.3)** |
| `T-SNAPSHOT` | Admitted state is independently owned and mutation-refusing; caller edits after admission cannot change evaluation | **DONE (round 10.3)** |
| `T-OOF` | Final-development OOF calibration partition identified separately from the outer folds | **DONE (round 10.3)** |
| `T-NO-ANCHOR-OVERRIDE` | No caller-selectable trust anchor anywhere on the acceptance path | **DONE (round 10.3)** |
| `T-DIGEST-BIND` | Full algorithm declaration bound into `pipeline_digest` | **DONE (round 9)** |
| `T-CHILD-RC` | Helper rejects unknown verdicts and inconsistent child rcs | **DONE (round 9)** |
| `T-XENV` | Requested vs resident kernel matrix, cold processes, rehydrated Lane B (5 classes → 1 group) | **PARTIAL** (3.12 / Windows NOT MEASURED) |
| `T-WIN` | Native Windows executed by a reviewer | **BLOCKED** (no Windows host) |
| `T-CI` | Hosted exact-head verification of the corrected commit | **BLOCKED** (see §5) |

## 2. Acceptance-gate IDs (what the owner may ratify)

Meanings quoted from `docs/rh04-issue132-acceptance-decision.md` §7. Every row
states evidence, status, blocker and next action.

### V2-01 — Owner ratification in the decision register
- **Original meaning:** Owner ratification of the V1→V2 transition, recorded in `docs/DECISIONS.md`, naming the accepting reviewer and the decision-document version.
- **Evidence:** none. No `docs/DECISIONS.md` entry exists.
- **Status:** **OPEN — owner action only.**
- **Blocker:** I cannot ratify my own work. Requires the owner.
- **Next action:** owner records a `DECISIONS.md` entry naming reviewer + version **after** V2-02…V2-10 are evidenced.

### V2-02 — Solver and host-independent convergence-criterion declaration
- **Original meaning:** hardened `deterministic_portable_newton` with the Issue #132 P0 issues *closed*, or a documented alternative whose convergence test is explicitly not host-dependent. "The criterion is part of the contract."
- **Evidence:** `T-OBJECTIVES` declares two profiles and refuses unknown ones; the decimal fitter's criterion is a declared gradient tolerance (`1e-24`) in decimal arithmetic, reached in 5 iterations with `|g|∞ ≈ 5.4e-26`. The P0 issues listed in the decision text (inward-gradient face pinning, Armijo sign, zero-step-with-nonzero-KKT, tautological assertion) were closed in earlier rounds and the tautology is now removed from the proposal.
- **Status:** **PARTIAL.**
- **Blocker:** the criterion is declared and measured, but the decision text also requires the *evidence that it is not host-dependent*, which needs the multi-class × 3.11/3.12 matrix (V2-04).
- **Next action:** cite the V2-04 matrix once produced; separately confirm no tolerance widening occurred.

### V2-03 — New pack, new digest, provenance, complete delta mapping
- **Original meaning:** `offline_io.v2.json` with its own `PACK_SHA256_V2`, recorded provenance (solver, criterion, tolerance, platform, kernel names), and a written mapping of every V1 expected value to its V2 counterpart with the numeric delta. V1 files stay frozen.
- **Evidence:** `offline_io.v2.json` exists; `T-REPLAY29` produces a candidate full reference with a semantic digest and a **case-level** V1→candidate mapping (**2 of 29 cases**, exactly 4 calibrated score paths). V1 files are byte-identical to `main`.
- **Status:** **PARTIAL.**
- **Blocker:** the mapping is at case-path granularity with numeric deltas only for the 4 changed paths; a *per-expected-value* mapping across all 29 cases is not yet tabulated, and the candidate is explicitly not a pinned pack.
- **Next action:** emit the full per-value delta table into the candidate evidence document; keep it labelled unratified.

### V2-04 — Exact replay on the required cross-environment matrix
- **Original meaning:** **≥3 dispatch classes × {Python 3.11, 3.12} on Linux, plus native Windows, all reporting `EXACT_REPLAY`.** "Deltas-only is not acceptable for V2."
- **Evidence:** Five requested dispatches resolve to **five environment classes** producing **two** Lane A result groups. The Lane B portable lane now executes **all 29 cases through the real facade** and reproduces the registered lane **exactly** on every field — because rehydration of the declarative archive into a real scikit-learn estimator is measured **bit-identical** to the original fitted estimator (linear `decision_function`/`predict_proba`, forest `predict_proba` over 500 rows). No numeric tolerance is involved.
- **Status:** **NOT MET** under the original text, which demands `EXACT_REPLAY` from the registered path. Lane B now satisfies the *purpose*, but only a ratified amendment to V2-04a/b can convert that into gate credit.
- **Blocker:** (a) no Python 3.12 interpreter locally; (b) no native Windows host; (c) the registered full reference is genuinely kernel-sensitive, so `EXACT_REPLAY` across ≥3 classes cannot be produced for Lane A without changing the scientific method — which is forbidden.
- **Next action:** owner decision required (§4). Either amend V2-04 to a two-lane contract, or fund 3 classes × 2 versions + Windows against Lane A and accept that it may never be `EXACT_REPLAY`.

### V2-05 — Dual-run V1/V2 CI window until the owner retires V1
- **Original meaning:** both the scoped V1 gate and the V2 gate run in CI until the owner retires V1; no silent substitution.
- **Evidence:** V1 gate unchanged and present. No V2 gate is wired into CI.
- **Status:** **NOT STARTED.**
- **Blocker:** requires a workflow change, which is an explicit separate proposal (no workflow-permission bypass).
- **Next action:** attach the CI/oracle dependency proposal (§5) for review; do not touch workflows unilaterally.

### V2-06 — Semantics re-statement (`calibration.json` / `scale_declaration` / model cards / manifest)
- **Original meaning:** stop implying "L-BFGS-B output"; declare the fitted criterion. Includes the §2.4 artifact-byte statement.
- **Evidence:** the portable declaration states arithmetic, agreement bound and non-claims machine-readably. No production manifest text was changed (correctly: production wording is a separate authorization).
- **Status:** **PARTIAL — deliberately not actioned.**
- **Blocker:** editing production manifest/model-card wording is an activation change, outside this round's authorization.
- **Next action:** owner approves a wording-only change set; then apply it as its own reviewable commit.

### V2-07 — Required negative tests, each failing closed
- **Original meaning:** wrong digest, >29 cases, a drifted non-calibration field, a planted second tolerance exception, a solver-provenance regression, an unreachable-criterion (fail-closed) case, and a V1 pack byte-integrity assertion.
- **Evidence:** Round 10 adds 19 structural refusals exercised with a **valid MAC** (attacker holds the key), plus recomputed self-hash, coordinated binding change, swapped route, missing manifest entry, wrong key, non-finite/invalid parameters, tree cycle, unreachable node and hostile node count. V1 byte-integrity assertion present.
- **Status:** **PARTIAL.**
- **Blocker:** ">29 cases" and "planted second tolerance exception" are still not written against the candidate pack.
- **Next action:** add those two negative tests.

### V2-08 — Security parity
- **Original meaning:** `_approved_replay_equal` type-strictness, redaction (`_describe`), no-fallback, fail-closed ordering and refusal-path tests must still pass; **no new tolerance surface**.
- **Evidence:** the canonical comparator is untouched (byte-identical to `main`). The Round 9 `DECLARED_SCORE_AGREEMENT = 1e-14` **has been removed**; the portable lane now requires exact equality on every field, so no new tolerance surface exists. The Round 9 module is retained with a superseded banner for history only.
- **Status:** **SATISFIED IN SUBSTANCE for the new lane** — no owner ruling is now needed on the tolerance question.
- **Blocker:** the substantive parity tests must still be demonstrated in the dual-run window (V2-05).
- **Next action:** include the parity suite in V2-05 once a V2 gate exists.

### V2-09 — Explicit non-claims
- **Original meaning:** engineering reproducibility only; no clinical validity, no model equivalence, no RH-07 science, no RH-08 release, no D-047/M3a metrics.
- **Evidence:** the portable declaration carries `acceptance_reference: false`, `replaces_regeneration: false`, `ratifies_D_V2_7: false`, `bit_identical_to_scikit_learn: false`; the ledger states non-claims explicitly.
- **Status:** **LARGELY MET** for the candidate; final wording belongs in the acceptance record.

### V2-10 — Single-revert rollback
- **Original meaning:** a V2 revert must be a single revert of pack + comparator + gate, leaving V1 intact and green.
- **Evidence:** no V2 gate exists to revert; V1 is intact and byte-identical.
- **Status:** **NOT APPLICABLE YET.**
- **Blocker:** depends on V2-05.
- **Next action:** once a V2 gate lands, demonstrate the single-revert on a scratch branch.

## 3. Gate summary

| Gate | Status |
|---|---|
| V2-01 | OPEN — owner only |
| V2-02 | PARTIAL |
| V2-03 | PARTIAL |
| V2-04 | **NOT MET** — amendment proposed (`RH04_V2_AMENDMENT_PROPOSAL_2026_11_21.md`) |
| V2-05 | NOT STARTED |
| V2-06 | PARTIAL — deliberately not actioned |
| V2-07 | PARTIAL |
| V2-08 | LARGELY SATISFIED — tolerance removed |
| V2-09 | LARGELY MET |
| V2-10 | N/A yet |

**No gate is closed. Zero of ten.**

## 4. Owner-decision packet — two-lane architecture

### Option A — keep the current single full-regeneration contract
- Lane A only: train, select, calibrate, replay per host.
- **Establishes:** maximal scientific fidelity; the registered method is the reference.
- **Cannot establish:** `EXACT_REPLAY` across ≥3 classes (measured: 2 classes already disagree), or Python 3.12/Windows exactness without those hosts.
- **V2-04 outcome:** unachievable as written unless the dispatch pinning that was explicitly rejected becomes acceptable, or the gate is scoped down.
- **Runtime:** ~117 s per full reference.

### Option B — portable frozen-artifact inference as the *reference-producing* lane
- Lane B: admission-gated declarative artifacts rehydrated into genuine scikit-learn
  estimators, executed through the registered facade, compared exactly against a
  fixed reference identity derived from the pinned artifact. **The exact-rational
  evaluator described in earlier revisions of this ledger is superseded and no
  longer exists.**
- **Establishes:** host-independent scoring and calibration **by construction**; a bounded, reviewable artifact (4096-byte class); no pickle on the verification path; refused tampering.
- **Does not establish:** bit-identity with scikit-learn (measured ≤6.66e-15); training reproducibility — training still happens once, on Lane A.
- **V2-04 outcome:** `EXACT_REPLAY` becomes achievable *for the portable lane* on any host, because the arithmetic is rational.
- **Requires amending:** V2-04 (scope), V2-06 (semantics), V2-08 (the declared bound), and it *is* the D-V2-7 ratification question.

### Option C — two-lane, explicitly scoped (recommended, smallest defensible)
Neither lane replaces the other; each answers a different question.

| | Lane A — research regeneration | Lane B — portable inference |
|---|---|---|
| Question | *did training+selection+OOF reproduce?* | *does this artifact score identically everywhere?* |
| Reference-producing | **yes** (scientific truth) | **no** (candidate; portable evaluator) |
| Host-independent | no (measured) | yes, for model+calibration |
| Gate | per-host report, deltas **reported not hidden** | genuine `EXACT_REPLAY` |
| Runtime | ~117 s | ~0.06 s class |

**Full clause-by-clause text is in
[`RH04_V2_AMENDMENT_PROPOSAL_2026_11_21.md`](RH04_V2_AMENDMENT_PROPOSAL_2026_11_21.md).**
Summary:
1. **V2-04** — split into `V2-04a` (Lane A: ≥3 classes × 3.11/3.12 + Windows, each reporting its measured verdict, `EXACT_REPLAY` required only on a declared host class) and `V2-04b` (Lane B: `EXACT_REPLAY` required on every host).
2. **V2-06** — declare Lane B's arithmetic. *(Superseded: there is no agreement
   bound to declare. `1e-14` is removed; Lane B compares exactly against its own
   fixed identity.)*
3. **V2-08** — state that `DECLARED_SCORE_AGREEMENT` is a *reported* bound in the candidate lane and that no existing gate consumes it; if the owner prefers, make Lane B report deltas with no pass/fail threshold at all.
4. **D-V2-7** — remains proposed; Lane B is an inference path, never a replacement for regeneration.

**Security / science / runtime / rollback implications:** no production inference change; no new dependency; the scientific reference stays Lane A; rollback is a single revert of candidate modules because nothing is wired into a gate yet.

**Smallest defensible architecture for graduation:** **Option C**, because Option A cannot meet V2-04 for reasons that are physical (dispatch) rather than technical, and Option B alone would subordinate the scientific reference to a candidate artifact.

## 5. CI / oracle dependency proposal (for separate review)

Hosted verification of the corrected head is **not** blocked by the "do not rerun until green" instruction — that instruction forbids retrying a *failing* workload to hide flakiness, not legitimately verifying a new corrected commit. This round does not push a workflow change, because no workflow-permission change has been authorized. Proposed, for review:

```yaml
# proposal only -- NOT applied
- name: rh04-v2-portable-oracle
  run: |
    python -m pip install -r research/experiments/requirements-oracle.txt
    python -c "import mpmath; assert mpmath.__version__ == '1.4.1'"
    python -m pytest tests/experiments/test_rh04_v2_reference.py -q -W error -k oracle
```

Fail-closed: if `mpmath` is absent the oracle tests raise `AssertionError` with the
install command; they never skip.

## 6. Explicit non-claims

- No clinical validity, no model equivalence, no patient readiness.
- The portable lane is **not** bit-identical to scikit-learn.
- `1e-14` is **removed**. It was a candidate agreement bound in Round 9; Round 10
  deleted it and Round 10.1 leaves Lane B with no numeric exception surface at all.
- Fixed coefficients do **not** imply SHAP/LIME reproducibility; those are outside the exported replay fields.
- The Round 8 ledger is withdrawn as an acceptance record.
