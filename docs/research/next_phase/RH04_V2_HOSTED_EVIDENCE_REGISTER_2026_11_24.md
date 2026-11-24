# RH-04 V2 — corrected hosted evidence register

**Run:** [`45446417665`](https://github.com/Muhammed-Fathi/CardioAssist-AI/actions/runs/45446417665)
**PR #141 head:** `73d9f9d5e60b134b25317a1018a9c93746ff3e7d`
**Tested merge checkout:** `0c55e3de6355fe2ba59f69c6c49825726373b6f3`
**main:** `c6a6bdee46a552a2b0d705a723c862ff8a95be4d`

**This run is retained permanently as evidence.** It is not superseded, not rerun to
obtain green, and not edited. It is the run that exposed the architectural
contradiction.

---

## 0. Correction to the previous report

An earlier summary of this run reported that all six stages passed and only the
aggregate step failed. **That was wrong, and the reviewer's logs corrected it.**

The error was avoidable and its root is recorded here so it is not repeated:
every stage step ends with `exit 0` unconditionally, so a green *step conclusion*
means only that the script ran to completion. The real result is written to
`stageN_exit`. The earlier report noted that fact and then reasoned about step
conclusions anyway. It also reproduced Stage 1 under **native** dispatch instead of
the job's forced `OPENBLAS_CORETYPE`, which is exactly why it saw `457 passed`
where the hosted runner saw `456 passed, 1 failed`.

**Green step conclusions are not evidence that an internal stage succeeded.**

## 1. Hosted per-stage outcomes — both host jobs

| Stage | Exit | Interpretation |
|---|---|---|
| Stage 1 V1 scoped | **0** | 457 passed |
| Stage 2 Lane A | **0** | `any_failure=false` |
| Stage 3 Lane B | **0** | ACCEPTED |
| Stage 4 regression | **0** | |
| Stage 5 security | **0** | |
| Stage 6 classify | **0** | |
| Aggregate | **0** | both host jobs **success** |

## 2. Hosted per-stage outcomes — all eight forced-dispatch jobs

Every one of haswell/nehalem/sandybridge/prescott × Python 3.11/3.12 reported the
same pattern.

| Stage | Exit | Evidence recorded |
|---|---|---|
| Stage 1 V1 scoped | **1** | **456 passed, 1 failed** |
| Stage 2 Lane A | **1** | convergence `any_failure=false`; same-environment regeneration identity **true**; cross-environment exact coefficient lineage **false for REST** |
| Stage 3 Lane B | **0** | **ACCEPTED, 29 cases, exact reference digest** |
| Stage 4 regression | **1** | **33 passed, 2 failed**, 274 deselected |
| Stage 5 security | **0** | |
| Stage 6 classify | **1** | `KeyError: 'run1_digests'` |

Failed tests, verbatim from the hosted logs:

1. `test_offline_fixture_pack.py::test_golden_replay`
2. `test_lane_a_lane_b_delta_mapping_is_explicit_and_non_numeric`
3. `test_v2_02_lane_a_records_actual_regenerated_parameters`

All three failures were reproduced locally under forced dispatch, at this exact
commit, with matching counts.

## 3. What the failures actually mean

**Lane B was never at fault.** It returned the identical fixed digest
`891d9e3b2a33…` on all eight forced-dispatch jobs and on the earlier run. The one
lane that must be exact was exact everywhere.

**Lane A did not fail to converge.** `any_failure=false` on every job, and
same-environment regeneration was bit-identical (`true`). What failed was a
bit-equality test *against the frozen archive*, on one route (REST).

**The three test failures are one cause.** A logistic-regression refit moves by
1–2 ulp when a different BLAS kernel reassociates L-BFGS:

| forced class | resident architectures | `da_a2` max abs Δ | in ulp |
|---|---|---|---|
| host (native) | `SkylakeX` | `0.0` | 0 |
| haswell | `Haswell` | `5.551e-17` | 1.00 |
| nehalem | `Nehalem` | `5.551e-17` | 1.00 |
| prescott | `Prescott, Katmai` | `8.327e-17` (+`1.110e-16` int) | 1.50 |
| sandybridge | `Sandybridge` | `1.110e-16` | 2.00 |

`test_golden_replay` failed at `absolute_delta 4.441e-16` on
`calibrated_log_odds` — the same effect downstream of the same refit.

**Stage 6 was a plain schema bug.** It read `report["run1_digests"]`; Stage 2
writes `identities_run1`. It raised in all eight jobs before classifying anything.

## 4. The three replays, kept distinct

The register separates three things that were previously conflated:

| evidence | what replays | digest behaviour | what it proves |
|---|---|---|---|
| **V1 golden replay** | fresh producer bundles vs. the frozen V1 pack | drifts by ~1 ulp off SkylakeX | the V1 pack's exact-replay contract is host-sensitive — a **real, retained failure** (§V1 transition) |
| **Lane B (frozen archive)** | admitted frozen archive bytes, no fitting | **identical on all 8 jobs** | the frozen artifacts replay deterministically |
| **Lane A fresh-model replay** | models re-fitted *now* by the registered producer | differs per class | a freshly regenerated model produces a stable, environment-characterised response identity |

Lane A previously called `replay_admitted` on frozen archives, so its "replay
identity" was a copy of Lane B's. It could not have detected regeneration drift.
That is corrected: the two now carry separate digests and an explicit
`fresh_and_frozen_are_equivalent: false`.

**Frozen-archive replay is not evidence about regeneration.** A frozen replay can
be green while regeneration has drifted, and vice versa.

## 5. Claim register

| Claim | Status |
|---|---|
| Lane B exact on all 8 forced-dispatch jobs | **verified** |
| Lane A converged on all 8 jobs | **verified** (`any_failure=false`) |
| Lane A same-environment regeneration identical | **verified** (`true`) |
| Lane A cross-environment parameters identical | **false, and not required** — see the amendment |
| V1 golden replay exact off SkylakeX | **false** — retained as a mandatory failure |
| Gate passed | **no** — 8 of 10 jobs failed; 0/10 gates closed |
| Native Windows executed | **no** |

## 5a. A pre-existing portability guard that is SUPPOSED to stay red

`test_generation_is_semantically_identical_to_the_committed_candidate` fails on
prescott and (not observed here) on other non-reference kernels. Its own failure
message states the contract:

> This is a PORTABILITY finding, not a metadata artifact and not a regression: the
> numerical reference genuinely differs on this host. **It must stay failing; do not
> add the digest to an allowlist.**

Observed locally at `73d9f9d` under `OPENBLAS_CORETYPE=prescott`:

```
committed class : class-a (042612c4…)
this host class : class-b (72b18071…)
```

It is **not** selected by Stage 4's filter, so the gate does not run it, and it is
**not** an artefact of this round — it fails identically at `73d9f9d`. It is recorded
here as a known, intended red: the honest statement that semantic regeneration is
host-dependent, which is the same fact the amendment is built on.

Fixing it by widening, allowlisting or deleting the assertion would be exactly the
suppression this project forbids.

## 6. Permanence

This run, its job conclusions and its stage exits are recorded above and are not
to be overwritten by a later green run. Any future pass is a *different*
observation and must cite both.
