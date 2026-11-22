# RH-04 V2 — reproducibility protocol, candidate evidence and the maintainer decision

**Document version:** `rh04.v2.protocol/v1`
**Status:** `PROPOSED — NOT RATIFIED`. This document and the code beside it are a
**candidate**. Nothing here is wired into CI voting, a production default, the
canonical V1 pack, the canonical comparator, the default solver, or any scoring
path.
**Supersedes:** nothing. It implements the *destination* that
`docs/rh04-issue132-acceptance-decision.md` §5 named P-2 and §7 called `V2-01…V2-10`.
**Issue:** [#132](https://github.com/Muhammed-Fathi/CardioAssist-AI/issues/132) — stays **OPEN**.
**Scope:** research-only, synthetic-only engineering reproducibility. No clinical
claim, no model-equivalence claim, no RH-07/RH-08 acceptance.

---

## 0. Executive summary — what changed in the understanding of #132

The prior acceptance record localised the drift to *"the SciPy L-BFGS-B fit"*.
Re-measuring the whole pipeline stage by stage (§4) shows that description was
**true of the observed case but not of the mechanism**. Two findings are new and
both are load-bearing:

1. **The calibrator is not the only host-dependent stage.** sklearn's
   `LogisticRegression.decision_function` (a BLAS `gemv`) produces different
   raw logits under different OpenBLAS kernels on the same features
   (`np_dot_64/120/512` and `blas_matmul_120x16` differ; `np.dot` at n ≤ 16,
   `np.log`, `np.log1p`, `safe_clipped_logit` and `scipy.special.expit` do not).
   **A portable calibrator alone does not make the pack portable** — measured,
   §4.3.
2. **The V1-era "portable" solver cannot be the V2 reference.** On a real
   64-row fold it *never terminates*: its float64 KKT residual bottoms out at
   `1.27e-10` against a `1e-10` threshold, so it exhausts its budget and raises
   `calibration_solver_did_not_converge` — a false negative, not a real failure
   to converge (§3.2, evidence `EV-03`).

The candidate V2 reference fixes (1)'s *effect on the reference* by computing the
fit in **software-declared decimal arithmetic** with a *reachable, declared*
criterion, and it **measures and reports** the remaining non-portability rather
than claiming it away: with the decimal reference, **13 of 17** dispatch classes
produce a byte-identical 29-case pack, and the 4 that differ differ in **exactly
one case** because of (1) (§5).

**What V2 can honestly be today:** a reproducibility contract that is exact on
the **tested** dispatch classes, with an explicit, measured list of the
conditions under which it is *not* exact, and a fail-closed diagnostic that
names the condition. What it **cannot** honestly be today: an unconditional
"exact on any machine" claim. Activating an exact-match **gate** on that basis
would fail on Haswell-class CI runners — measured, §5.3 — which is precisely the
CI lottery #132 exists to end.

---

## 1. Authority and constraints

| Item | Standing |
|---|---|
| PR #136 acceptance decision | Merged. P-4 recommended; V2 is the only declared exit. |
| PR #137 non-voting observer | Draft/Open. **Not merged, not modified here.** |
| Issue #132 | **OPEN.** This document does not close it. |
| PR #133 / #134 | **Unchanged.** |
| V1 pack, digest `0307b396…`, comparator, tolerances | **Byte-identical to `main`** (verified, §7). |
| Default solver (`scipy_lbfgsb`), `.github/workflows/**` | **Byte-identical to `main`.** |
| Owner decision required before any gate changes | **Yes — §8, decision `D-V2-1`.** |

---

## 2. The problem, restated precisely

* V1 exactness is a property of **one arithmetic**: binary64 L-BFGS-B on SciPy's
  `SkylakeX` OpenBLAS kernel. Re-measured across 9 dispatch classes, replay is
  exact only where SciPy's *resident* kernel is `SkylakeX`
  (`docs/rh04-issue132-acceptance-decision.md` §1.4).
* V1's reference values are a **stopping artifact** of the default L-BFGS-B
  controls (`pgtol=1e-5`), so any *better*-converged solver necessarily disagrees
  with them by ~4×10⁸ ULP (§2.3 of that document). A V2 reference therefore
  **must** be a different number. That is not a defect of V2; it is the
  difference between *"the value L-BFGS-B stopped at"* and *"the optimum of the
  declared objective"*.
* Consequently V2 re-certifies the two calibrated float fields of two cases and
  nothing else (§6).

---

## 3. V2 reference algorithm — declared, versioned, criterion-first

### 3.1 The declaration (`research/intake/rh04_v2_reference_fit.py`)

```
protocol_id  rh04.v2.decimal-reference-fit/v2
arithmetic   python `decimal` (MPDEC), 40 significant digits, ROUND_HALF_EVEN
objective    mean(softplus(eta) - y*eta) + 0.5*l2*(a^2 + (b-1)^2),  eta = a + b*logit
criterion    max_i  kkt_i  <= 1e-16        (box-constrained KKT residual)
line search  exact 1-D golden-section minimisation, 140 iterations, no tolerance
bounds       (-15, 0.01) .. (15, 15)       (identical to production)
l2_anchor    1e-3                          (decimal literal, not a binary64 literal)
return       one correctly-rounded Decimal -> binary64 conversion per parameter
host-dependent operations: none.  BLAS calls: 0.  libm calls: 0.
```

`declared_protocol()` emits exactly this and is embedded in the pack, so a
reader can tell which reference a value came from without reading the code.

### 3.2 Why decimal, and why 1e-16

| Quantity | Value | Meaning |
|---|---|---|
| float64 KKT floor on real cohorts | `1.3e-10` … `5.5e-8` | A `<=1e-10` criterion is **unreachable** here |
| decimal KKT residual at the optimum | `1.7e-18` … `9.2e-18` | measured at 40/60/80 digits, identical |
| declared tolerance | `1e-16` | reachable with ~2 orders of margin, ~6 orders below the float64 floor |

The 1e-16 criterion is *below* what binary64 can express for these sums. That is
the point: the criterion is only meaningful in the arithmetic that evaluates it,
and it is a property of the declared algorithm rather than of the host.

### 3.3 Two algorithmic rules that are load-bearing (both learned from failure)

1. **Exact line minimisation, not Armijo backtracking.** Armijo compares
   objective *values*; at 40 digits `f(x)` and `f(x + t·d)` can be
   indistinguishable for small `t`, so a good step fails the test. A convex
   2-parameter problem admits a tolerance-free 1-D search.
2. **Active set by the box cap only, with no epsilon.** A component on a face is
   pinned only when its step points outward; otherwise the cap shortens the step.
   An epsilon band on "is this on the face" misclassified an iterate sitting
   `1e-40` outside the face. Measured failure that forced this rule: a slope
   pinned at `0.01` with a coupled Newton step pointing outward produced a
   feasible step length of `1.9e-39`, stalling a genuinely convergent fit.

### 3.4 Honest limits of the algorithm

* MPDEC is portable *software* arithmetic, not IEEE-754; no claim is made that it
  matches an independent decimal implementation bit for bit.
* Inputs are binary64 and are converted exactly, so nothing is lost at the
  boundary — but the reference is still "the optimum of *these* inputs".
* Downstream numerics are out of scope (§4).

---

## 4. Stage-level portability audit — what is actually host-dependent

Tool: `research/intake/rh04_v2_portability_audit.py` (`--json`, `--compare`).
36 stages; the report contains digests only (no values, no paths, no scores).

### 4.1 Measured stage map (`SkylakeX` vs `Sandybridge`, same host, same wheel set)

| Stage class | Verdict | Detail |
|---|---|---|
| Calibration fit (float64 L-BFGS-B) | **dispatch-dependent** | 2 equivalence classes |
| Decimal reference fit | **INVARIANT** | identical binary64 output on all tested classes |
| `np.log`, `np.log1p`, `safe_clipped_logit` | INVARIANT | libm path is stable on this host |
| `scipy.special.expit` | INVARIANT | stable for logits in `[-800, 800]` |
| `np.dot` at n ∈ {2, 16} | INVARIANT | small sizes use a scalar path |
| `np.dot` at n ∈ {64, 120, 512} | **dispatch-dependent** | the V1-era mechanism |
| `np.mean(a*b)`, `np.einsum` | INVARIANT | not the mechanism here |
| sklearn `decision_function` (`gemv`) | **dispatch-dependent** | `SKX` vs `Sandybridge` only |
| selected family / hyperparameters | INVARIANT | model selection is stable |
| bundle `preprocessing.json`, `shap_background.json` | INVARIANT | |

### 4.2 The consequence that changes the strategy

Because the **linear** research family feeds `decision_function` output to the
calibrator, its OOF raw logits are dispatch-dependent **before** any calibration
happens. Replacing the calibrator alone therefore cannot make the pack portable.
This was measured directly (§4.3, `EV-05`).

### 4.3 Controlled experiment — with inputs held fixed, the decimal fit is exact

Instrumenting every fit invocation during a full pack generation:

* 6 of 14 invocations received **bit-identical** `(y, logits)` inputs under
  `SkylakeX` and `Sandybridge` — **all 6 produced bit-identical parameters**.
* The other invocations received **different inputs**, produced by
  `decision_function` (`l2_logistic_regression`) or by the dummy prior. Those
  rows are *input* differences, not fit differences.

That is the sharpest available statement: **the V2 fit is a deterministic
function of its inputs; the remaining non-portability enters upstream.**

---

## 5. Cross-dispatch evidence for the candidate pack

### 5.1 Fresh generation per dispatch class (17 classes, cold process each)

Every row below is a **fresh cold-process generation** (not a hash of the
committed file).

| Group | Measured dispatch classes | Fresh pack digest |
|---|---|---|
| **A — 13 classes** | `SkylakeX`, `Cooperlake`, `Generic`, `AVX512`, `AVX2`, `Haswell`, `Zen`, `Nehalem`, `Atom`, `Ryu`, `Skylake`, `SapphireRapids`, `CortexA57` | `b74f781d…595f2` |
| **B — 3 classes** | `Sandybridge`, `Prescott`, `Katmai` | `3df8de94…89568` |
| — | `Excavator` | **SIGILL** (exit 132) during pack generation — but it *survives* `np.dot(n=10)` and `scipy.linalg` (§5.4) |
| — | `Bulldozer` | **SIGILL** (exit 132) on the very first `np.dot` after import (§5.4) |
| — | *(unset — host)* | same as `SkylakeX` on this machine |

`Haswell` is in **group A**. Group B differs from group A in **exactly one case**
(`da_a2_resting_v1`), in two fields, by `2.220e-16` and `1.110e-16` — traced in
§4.3 to the upstream `gemv`, not to the calibrator.

### 5.2 Exact replay

`python -m research.intake.rh04_v2_candidate --check` regenerates all 29 cases
in a fresh interpreter and compares every field with strict type-and-value
equality (**no tolerance, no approved exception**). Exit 0 and
`EXACT_REPLAY, 29 cases` on `SkylakeX` and `Haswell`; `Sandybridge` fails closed
with the redacted field diff. The committed fixture is byte-reproducible from
source (§7).

### 5.3 What this means for a *gate*

An exact-match V2 gate would be **green on the CI dispatch classes measured here
(Haswell, Zen→Haswell, SkylakeX-like)** and **red on `Sandybridge`-class**. That
is better than V1 (which is red on Haswell **and** Sandybridge) but it is **not**
the unconditional portability a gate requires. This is decision `D-V2-1`.

### 5.4 The forced-`SkylakeX` test's portability question, answered by evidence

The PR #137 review observed `test_cli_under_a_forced_dispatch_is_fail_closed_and_labelled[SkylakeX]`
failing with `JSONDecodeError` on empty child stdout. Four hypotheses were
separated by measurement rather than inference:

| Hypothesis | Test | Result |
|---|---|---|
| Unsupported CPU instruction (SIGILL) | Force 20 dispatch names in a cold child | **19 run; `Bulldozer` → SIGILL** (`returncode -4`, empty stdout, empty stderr) |
| Python exception in the child | Instrument the child, print progressively | Child reaches `np.dot` and dies **inside** it, after importing numpy and allocating |
| Empty output for another reason | Reproduce the classifier CLI under `Bulldozer` | `returncode -4`, `stdout_len 0`, `JSONDecodeError` **reproduced exactly** |
| Actual numerical drift | Same CLI under a non-golden kernel | Exit 2/1 with a *parseable* payload — a different signature |

**Conclusion:** the empty-stdout signature is a **signal death (SIGILL), not
numerical drift and not a Python exception**, and it is reproducible on this host
by forcing an incompatible kernel.

**A second, sharper result:** SIGILL is **operation-depth dependent**. Under
`Bulldozer` the child dies on the first `np.dot(n=10)`; under `Excavator` the
same light probe *passes* and the death only occurs deep inside pack generation.
So a cheap "does this kernel start?" probe is **not** sufficient to classify a
dispatch as usable: the failing instruction may live in a kernel path that only a
heavy reduction reaches. That is why §5.4's classification is scoped to the
operation tested and why a capability probe must exercise the real workload.

**Correction to the earlier record (important):** the PR #137 hypothesis that
"`SkylakeX` is unsupported on Haswell-class runners" is **not supported** by
these measurements. `SkylakeX` dispatched successfully in a cold process on this
AVX-512 host, and OpenBLAS did not abort. Any kernel request can legitimately
`SIGILL` if the kernel's instruction set is absent from the host; that is a
property of the request, not of the instruction count of the name. What the
failing CI job actually did remains **unproven** to the documented standard,
because its child return code and stderr were never captured. The correct fix is
therefore **not** to remove or skip the test but to make it *diagnose its own
failure*: capture the child's return code and signal name, and report
`DIED_WITH_SIGNAL`/`SIGILL` as a distinguishable, still-failing outcome. That is
`D-V2-2`, and it is deliberately **not** implemented here (the test lives in the
merged PR #136 surface and changing it is a separate authorized step).

---

## 6. V1 → V2 numeric mapping (re-certification scope)

Exactly **4 changed paths of 29 cases** (`build_mapping`):

| Case | Field | V1 | V2 | Δ | Δ in ULP |
|---|---|---|---|---|---|
| `da_a2_resting_v1` | `calibrated_log_odds` | `1.1439672594951131` | `1.1439682851654605` | `+1.026e-06` | ≈4.6e9 |
| `da_a2_resting_v1` | `calibrated_research_score` | `0.7584072878055222` | `0.7584074757346128` | `+1.879e-07` | ≈1.7e9 |
| `da_a1_basic_clinical_v1` | `calibrated_log_odds` | `2.6971396718292335` | `2.6971398591262560` | `+1.873e-07` | ≈4.2e8 |
| `da_a1_basic_clinical_v1` | `calibrated_research_score` | `0.9368576513885218` | `0.9368576624681499` | `+1.108e-08` | ≈1.0e8 |

Every other field of every case — `status`, `panel_id`, `route_id`,
`dataset_id`, `evidence_level`, `error`, `abstention_reason`,
`unavailable_reason`, `present_fields`, `missing_fields_with_reason`,
`raw_model_score`, `raw_model_log_odds`, `scale_declaration`, `score_kind`,
`exploratory_threshold`, `exploratory_above_threshold_flag`,
`calibration_reason`, `score_interpretation`, `clinical_probability_claim` — is
**bit-identical**. Ranking, the threshold flag and every refusal case are
unaffected.

**Interpretation, stated conservatively:** the deltas are the distance between
an L-BFGS-B *stop* and the objective's *optimum* (V1→V2 is a change of *what the
reference means*, not a bug fix). `1.9e-7` in log-odds corresponds to `~1.1e-8`
in probability. No scientific metric moves. This is still a re-certification,
and it is the reason it needs `D-V2-1`.

---

## 7. Preservation proof (V1 must be untouched)

Byte-identical to `origin/main` (sha256 compared file by file):

```
SAME  research/intake/offline_fixture_pack.py        27a47e92…
SAME  research/intake/fixtures/offline_io.v1.json    206418e5…  (PACK_SHA256 0307b396…, 29 cases)
SAME  ai/report_comparison.py                        aeb34406…
SAME  ai/calibration.py                              f9068e7a…  (default solver unchanged)
SAME  .github/workflows/experiment-runner-ci.yml     e77ab008…  (no workflow change)
SAME  tests/experiments/test_offline_fixture_pack.py 6696bb50…
SAME  research/intake/diagnose_fixture_replay.py     ea813aea…
SAME  research/intake/rh04_environment_class.py      5aacd10a…
```

Enforced by tests too (`test_v1_frozen_pack_digest_is_unchanged`,
`test_v1_comparator_still_has_exactly_one_approved_exception`,
`test_v1_strict_comparator_is_type_exact`,
`test_no_production_module_imports_the_v2_candidate`).

The candidate V2 pack is **not** a gate: `V2_PACK_SHA256` is the literal
`"UNPINNED_CANDIDATE_PACK_DO_NOT_USE_AS_A_GATE"`. Its content digest is
`b74f781d7c7839a33c3693e53511ac4d200b8bcf5b0a38526e9a9e2b657595f2`.

---

## 8. The maintainer decisions V2 needs (explicit, named)

### `D-V2-1` — Adopt (or refuse) a *scoped* exact-reference contract, and re-certify two float fields

* **Question:** do you accept that the RH-04 reference becomes *"the optimum of
  the declared decimal algorithm"* instead of *"the value SciPy L-BFGS-B stopped
  at on a SkylakeX kernel"*, accepting the four re-certified values in §6?
* **Not implied by:** any CI greenness, any review of #137, or this document.
* **If yes:** V1 becomes frozen history; V2 becomes the reference; the pack
  inventory/digest becomes a real gate constant; `docs/DECISIONS.md` records the
  transition (`V2-01`). V1 keeps running read-only (`V2-05`).
* **If no:** V2 stays a candidate and #132 stays open on the same terms.

### `D-V2-2` — Make the forced-dispatch test diagnose its own failure

* **Question:** authorize changing
  `test_cli_under_a_forced_dispatch_is_fail_closed_and_labelled` so that a child
  that dies by signal reports `SIGILL`/`SIGSEGV` (still failing, but
  distinguishable from a classifier bug and from numerical drift).
* **Why it needs a decision:** it lives in the merged PR #136 surface and the
  round-4 instruction is *"do not remove, skip or weaken"*; making it *more*
  informative is not weakening, but it is a change that needs your authorization.
* **Runtime evidence supports it:** §5.4 reproduces the exact empty-stdout
  signature via `SIGILL`.

### `D-V2-3` — Choose the gate shape (none of these is automatic)

| Option | Effect on CI | Honest description |
|---|---|---|
| **a — observe only** (today) | no vote | V2 `--check` reports; canonical V1 stays authoritative and stays red where it is red. Zero new false claims. |
| **b — scoped exact gate** | green on measured classes, red on `Sandybridge`-class | Truthful if the supported set is declared: *"exact on classes A"*. Requires `D-V2-1`. |
| **c — exact gate + fail-closed classifier** | as (b), and a new class is a loud, named failure instead of a lottery | Extends the existing non-voting observer into a *declared-class* check. Requires `D-V2-1` and a workflow change **by you** (the App cannot push workflows). |
| **d — universal exact gate** | would fail on Haswell | **Not supported by evidence. Do not adopt.** |

**Recommendation:** (a) now; (b) after `D-V2-1`; (c) only if you also want the
*supported-class* declaration to be machine-enforced. Never (d).

### `D-V2-4` — UCI-412-specific option, if the linear `gemv` must also be portable

The remaining single-case difference is upstream (`decision_function`). Making it
exact requires **production** changes (a declared deterministic decision path for
the linear family) with the same re-certification scope. This is deliberately
**not** implemented: it is a production numerical change, and it should be
separately authorized or explicitly declined. Declining it means V2 is exact on
class A **only**.

---

## 9. Evidence matrix

| ID | Claim | Status | Evidence |
|---|---|---|---|
| `EV-01` | V1 exactness is a function of SciPy's resident kernel | `MEASURED_HERE` | §1.4 of the acceptance decision; 9 dispatch classes |
| `EV-02` | The float64 KKT criterion `1e-10` is unreachable on a real fold | `MEASURED_HERE` | residual frozen at `1.2737e-10` for 380 iterations; test `test_decimal_reference_converges_where_the_float64_portable_solver_does_not` |
| `EV-03` | The recorded hard cohort is genuine and re-verified | `MEASURED_HERE` | `sha256(y)=eabaacb1…`, `sha256(logits)=bc3de6e9…`, 46/64 positives, asserted in the test |
| `EV-04` | With fixed inputs the decimal fit is invariant | `MEASURED_HERE` | 6/6 identical-input fits → identical outputs (§4.3) |
| `EV-05` | A portable calibrator alone does not make the pack portable | `MEASURED_HERE` | with the earlier solver revision the pack split into 2 digests (`ee31a7e0…`, `accbd002…`); instrumentation then localised it to the upstream `gemv` (§4.3) |
| `EV-06` | 13 of 17 tested dispatch classes give one identical V2 pack | `MEASURED_HERE` | §5.1 |
| `EV-07` | The 4 differing classes differ in exactly 1 of 29 cases | `MEASURED_HERE` | `da_a2_resting_v1`, 2 fields, `2.220e-16` / `1.110e-16` |
| `EV-08` | `expit`, `log`, `log1p`, `np.mean(a*b)` are invariant on this wheel set | `MEASURED_HERE` | audit stage map §4.1 |
| `EV-09` | Empty child stdout under forced dispatch = SIGILL, not drift | `MEASURED_HERE` | §5.4; `Bulldozer` → `returncode -4` |
| `EV-10` | The CI job's actual child return code | **UNPROVEN** | logs are unreadable from the sandbox; see §5.4 |
| `EV-11` | Python 3.12 + decimal reference | **NOT MEASURED HERE** | no 3.12 interpreter available (no egress to a Python distribution host) |
| `EV-12` | Native Windows | **NOT MEASURED HERE** | requires `D-V2-1` first; owner-run, zero Python required of you if the V2 `--check` is executed by CI |
| `EV-13` | Behaviour on non-x86 or a rebuilt wheel set | **UNPROVEN** | no evidence, no claim |

---

## 10. Reproducing every number in this document

```bash
# 1. The reference fit alone (seconds)
python -c "from research.intake import rh04_v2_portability_audit as a; \
import json; print(json.dumps(a.fit_stages(), indent=1))"

# 2. Stage-level portability map, twice, then compare
for ct in SkylakeX Haswell Sandybridge; do
  OPENBLAS_CORETYPE=$ct python -m research.intake.rh04_v2_portability_audit --json > /tmp/$ct.json
done
python -m research.intake.rh04_v2_portability_audit --compare /tmp/SkylakeX.json /tmp/Sandybridge.json

# 3. Regenerate the candidate pack under two dispatch classes (~90 s each) and
#    compare digests
OPENBLAS_CORETYPE=SkylakeX   python -m research.intake.rh04_v2_candidate --write
OPENBLAS_CORETYPE=Sandybridge python -m research.intake.rh04_v2_candidate --write

# 4. Exact replay of the committed candidate (no tolerance)
OPENBLAS_CORETYPE=Haswell python -m research.intake.rh04_v2_candidate --check

# 5. The candidate test suite
python -m pytest tests/experiments/test_rh04_v2_reference.py -q
```

**Runtime notes (measured):** one pack generation ≈ 90 s; the full candidate
suite ≈ 5.5 min, of which ≈ 3 min is three unavoidable full generations/replays.
The suite is deliberately not registered in CI by this PR.

---

## 11. Changed files

| File | Role |
|---|---|
| `research/intake/rh04_v2_reference_fit.py` | Declared decimal reference fit + protocol declaration |
| `research/intake/rh04_v2_candidate.py` | Generator, strict validator (zero tolerance), V1→V2 mapping, `--check`/`--write` |
| `research/intake/rh04_v2_portability_audit.py` | 36-stage portability map, `--json`/`--compare` |
| `research/intake/fixtures/offline_io.v2.json` | Candidate pack (29 cases), digest `b74f781d…`, **not a gate** |
| `tests/experiments/test_rh04_v2_reference.py` | 40 tests: preservation, determinism, fail-closed, seam hygiene, audit logic, cold-process replay |
| `docs/research/next_phase/RH04_V2_REPRODUCIBILITY_PROTOCOL_2026_11_21.md` | This document |

**Not changed:** every production module, the V1 pack/digest/comparator/
tolerances, the default solver, `.github/workflows/**`, and PR #137.

---

## 12. What would make V2 certifiable

1. `D-V2-1` accepted (scope + re-certification of §6) → record in `docs/DECISIONS.md`.
2. `D-V2-3(b)` chosen → pin `V2_PACK_SHA256` and add the supported-class
   declaration to `declared_protocol()`.
3. Cross-environment evidence on the *pinned* digest: ≥3 dispatch classes ×
   {3.11, 3.12} on Linux (this document has 3.11 × 17 classes; 3.12 is `EV-11`)
   **plus** native Windows (`EV-12`) — the original `V2-04` requirement stands.
4. `D-V2-2` applied so a new dispatch class is a named failure, not a lottery.
5. Only then: retire V1 by an explicit owner decision, and close #132.

Until (1)–(5), the honest sentence for the RH-07/RH-08 registers is:

> The RH-04 reference is reproducible on the 13 measured OpenBLAS dispatch
> classes under the declared decimal algorithm; on 4 further measured classes one
> case differs by `2.2e-16` because a BLAS `gemv` upstream of the calibrator is
> kernel-dependent. No unconditional cross-machine claim is made.

**This document and its code are a candidate. They are not certified, not
merged into any gate, and not an acceptance of #132.**
