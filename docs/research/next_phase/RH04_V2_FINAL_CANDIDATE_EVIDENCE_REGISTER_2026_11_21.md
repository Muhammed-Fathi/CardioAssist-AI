# RH-04 Final Candidate Evidence Register

**Document ID:** CAI-RH04-REGISTER-v1
**Status:** `FINAL_CANDIDATE_PREPARED_NOT_ACCEPTED`
**Round:** 10.4 — final candidate preparation
**Focused suite:** 273 passed / 0 failed
**Wider suite:** 1380 passed / 2 skipped / 0 failed / 0 errors
**Contracts:** 306 passed · **Combined:** 1688 passed / 2 skipped

This register is the per-gate disposition for V2-01 through V2-10. It records
**implementation findings**, never formal gate closure. Issue #132 stays OPEN and
PR #139 stays Draft until independent review and maintainer ratification.

Legend: `SATISFIED_BY_TEST` = an actual test asserts it and passes.
`PARTIAL` = part of the criterion is evidenced, part is not, and the unreached part
is named. `NOT_SATISFIED` = the criterion is not met and no test is claimed for it.

---

## V2-01 — Producer lineage

**Disposition: SATISFIED_BY_TEST** for the corrected scope.

The Round 10.3 finding was real and it was two different defects on two routes:

| route | cohort data | recorded metadata | consequence |
|---|---|---|---|
| `da_a1_basic_clinical_v1` | **wrong** (seed 20261025 vs producer's 20261028) | wrong | committed input digest and fold assignments described a cohort the model was never fitted on; 95 vs 101 positives |
| `da_a2_resting_v1` | correct (`_cohort()` ignores metadata, uses `DEMO_SEED`) | wrong | the *data* was right and only its *recorded identity* was wrong |

Separating those two is the substantive correction. A single "lineage was wrong"
statement would have implied the REST model was mis-trained, which it was not.

**Evidence.** `research/intake/rh04_v2_producer_lineage.py` reads `DEMO_SEED`,
`DEMO_N_ROWS`, `DEMO_TRAINING_CONFIG`, `Uci412ResearchModelConfig` and
`CANDIDATE_FAMILIES` from the producers themselves. The duplicated
`SPLIT_DERIVATIONS` table is deleted. Tests:

- `test_producer_lineage_is_read_from_the_producers_own_declarations`
- `test_old_basic_cohort_seed_fails_identity_verification` — the wrong seed `20261025` produces a different `training_input_sha256`, proving the test can fail
- `test_registered_producer_lineage_is_established_for_both_models`

**Measured, not assumed.** The provenance correction left inference byte-identical:
`model`, `preprocessing`, `calibration`, `fold_ensemble` are unchanged for both
routes; only `training_identity` differs. The Lane B digest is therefore still
`891d9e3b…`.

---

## V2-02 — Fitted solver criterion under two lanes

**Disposition: PARTIAL — explicitly not satisfied.**

This is the gate that Round 10.3 correctly refused to close, and Round 10.4 does
not close it either.

**What is true.** Lane B fits no model and no calibrator. It rehydrates declared
arrays into genuine scikit-learn objects and calls the registered inference path.
It therefore makes **no solver claim at all**. An isolated Decimal oracle is not
evidence that the archived sklearn parameters were produced by that oracle, and
this register does not credit it as such.

**What is now additionally true.** The calibrator's *actual* input is captured at
the producer boundary and pinned (§V2-04). The producer run reproduces both
archived calibrators exactly, including `solver = scipy_lbfgsb`.

**What remains unsatisfied.** The criterion-reachability demonstration against the
real training path has not been run. V2-02 requires showing the fitted criterion
is reachable and identifiable under both lanes; that has not been done.

**Do not read "calibrator provenance now captured" as "V2-02 satisfied."**

---

## V2-03 — One supported acceptance entry point

**Disposition: SATISFIED_BY_TEST.**

Ten ordered steps in `python -m research.intake.rh04_v2_portable_archive <dir>`:
manifest anchor → registered 29-case set → raw SHA-256 before parsing → strict
JSON (duplicate keys and non-finite refused) → structural validation → all
semantic bindings → independently owned frozen snapshot → complete 29-case facade
execution → exact comparison to the fixed reference → sanitised JSON with
non-zero exit on refusal.

**Negative evidence, all through the real command:**

| mutation | result |
|---|---|
| whitespace-only edit to one archive | `REFUSED` exit 1, at the raw-byte gate before parsing |
| forged manifest supplied beside the archives | `REFUSED` — a co-supplied manifest is not a trust anchor |
| caller mutation after admission | inert; in-place edit raises `TypeError` |

Tests include `test_acceptance_api_has_no_caller_selectable_trust_anchor` (inspects
every acceptance signature), `test_cold_process_replay_needs_no_producer_bundle`,
and `test_caller_mutation_after_admission_cannot_change_evaluation`.

---

## V2-04 — OOF provenance

**Disposition: SATISFIED_BY_TEST** for the corrected scope.

Three identities are now kept apart, and the distinction is the whole point:

| identity | what it is | who can compute it |
|---|---|---|
| `training_input_sha256` | ordered development design matrix | Lane A |
| `calibration_oof.assignment_sha256` | which rows `full_cv+333` held out in which fold | Lane A |
| `calibration_input.oof_input_sha256` | **the ordered OOF probability vector actually fitted** | Lane A only |

**The defect corrected.** The previous `calibration_input_sha256` hashed the
development feature/target matrix. A calibrator can consume a different vector from
the same matrix, so that binding could not detect a change to the calibrator's real
input — it was a correct digest of the wrong quantity.

**Now captured by observation, not reconstruction.** `calibration_input_identity()`
drives the registered producer and intercepts
`OofLogisticCalibrator.fit_from_oof` for the single `FULL_DEVELOPMENT_OOF_FINAL`
fit. The arrays recorded are literally the ones fitted. No parallel training
architecture is introduced.

| route | link | OOF n | solver | intercept | slope |
|---|---|---|---|---|---|
| basic | `clipped_logit_of_raw_probability` | 120 | `scipy_lbfgsb` | `-0.8264874886346654` | `1.6547968324340276` |
| resting | `exact_raw_log_odds` | 96 | `scipy_lbfgsb` | `-0.00994579150712183` | `1.0083887187888398` |

Both reproduce the archived calibrators **exactly**, and the link typing is
enforced both ways: `exact_raw_log_odds` must pin a raw-logit digest,
`clipped_logit_of_raw_probability` must not.

**Privacy.** Raw OOF vectors are digested and discarded. Nothing is written to disk
or committed; only SHA-256 digests and permitted scalar provenance leave the
function.

**Enforcement is real, and honestly bounded.** Admission compares the pinned link,
scope, family, sample count, intercept, slope, status and solver against the
archive. It also refuses a manifest that claims
`recomputable_in_lane_b != False`, because Lane B never fits and therefore cannot
recompute an OOF digest. That field is pinned as a capability statement, not
evidence.

Full-development inner-selection seeds (`full_cv + 10*offset` →
`20351035`, `20351045`) and the dummy-calibration schedule
(`repeat_seed + 1000*fold + 1` → `20262026`) are included.

---

## V2-05 — Dual-run workflow

**Disposition: NOT_SATISFIED — proposal only.**

`RH04_V2_DUAL_RUN_AND_ROLLBACK_2026_11_21.md` specifies the workflow using
existing repository policy. Nothing is implemented.

---

## V2-06 — Registry and semantic binding

**Disposition: SATISFIED_BY_TEST.**

Panel, model id/version, bundle protocol, cohort id, model family, execution
profile, representation version, preprocessing, encoded feature order, selected
hyperparameters, split identity, calibration identity and fold-ensemble identity
are each compared against the pinned manifest. A test per binding class, plus
`test_registry_metadata_identity_is_enforced` which patches only the pinned
registry digest and requires refusal.

---

## V2-07 — Negative acceptance

**Disposition: SATISFIED_BY_TEST.**

Each negative names the guarantee it exercises and fails for that reason:

| test | actual violation | intended refusal |
|---|---|---|
| wrong reference digest | pinned digest altered | reference mismatch |
| >29 cases | extra case appended | case-set cardinality |
| missing / reordered / duplicate case | case list permuted | ordered case-set identity |
| non-calibration field drift | `model.family` altered, everything re-attested | semantic binding |
| planted second tolerance exception | an `isclose` added to a scoring function | AST scan of scoring functions |
| solver provenance mismatch | pinned solver altered | calibrator provenance |
| unreachable convergence criterion | criterion never satisfiable | reachability refusal |
| V1 byte preservation | V1 pack/comparator bytes | unchanged-file assertion |

**A corrected finding.** `test_v2_07_non_calibration_field_drift_is_detected`
initially failed for the *right* reason and the test was wrong: re-attesting the
body is not enough, because the manifest pins `archive_sha256`. The test now also
re-pins the file digests and patches the anchor test-locally, so the semantic layer
is genuinely what refuses. The earlier version would have passed for the wrong
reason had the digest check been weaker.

**A guard that could never fire.** `_validate_calibration_oof` contained
`if x == x - 333 + 333 and x % 1 != 0`, which is `False` for every integer. It has
been replaced with checks that can fail (`n_splits >= 2`, seed ordering), and
`test_calibration_oof_seed_validator_can_actually_fail` proves the replacement can
raise.

---

## V2-08 — Lane separation

**Disposition: SATISFIED_BY_TEST.**

Lane A = registered synthetic regeneration + diagnostic comparison.
Lane B = independently admitted fixed artifacts, no fitting, complete 29-case
replay.

`LANE_B_REFERENCE_DIGEST` is a fixed constant asserted by both the cold-process and
CLI tests. `test_portable_lane_matches_the_registered_lane_exactly_on_all_29_cases`
is labelled **DIAGNOSTIC ONLY** and is not the oracle. Three further tests verify
separation by AST scope (Lane B functions contain no `joblib.load`, no `fit`, no
producer import).

---

## V2-09 — Acceptance preparation

**Disposition: PARTIAL.**

Reconciled, with the two planned items still plans: dual-run (V2-05) and rollback.

---

## V2-10 — Documentation and environment

**Disposition: PARTIAL.**

All four controlling documents updated; sizes/digests recomputed; superseded rounds
retained as superseded. Five resident dispatch classes measured with the unified
entry point, all matching at `891d9e3b…`, with the *resident* kernel read from
`threadpoolctl` rather than assumed from the request.

**Corrected this round.** Round 10.3's wider-suite claim excluded two files with
`--ignore=`. That exclusion is withdrawn: with the repository's own reviewed pins
installed, all files run (`1380 passed, 2 skipped`).

**Not measured:** Python 3.12, native Windows, non-x86, hosted CI. These are named
as gaps, not passes.

---

## Ledger-worthy contradictions reconciled this round

1. **`calibration_input_sha256` was the development matrix.** Fixed; three
   identities separated; enforcement added.
2. **`inner_selection_identity` sorted the family tuple.** Fixed; producer order
   preserved and verified against observed producer execution.
3. **The RF proof compared only `tree_.value`.** Extended to all 9 structural
   arrays × 50 trees plus 4 scalars, with 10 mutation classes each detected.
4. **A seed guard could never fire.** Replaced and tested.
5. **The wider suite's 35 errors + 1 failure were described as "pre-existing".**
   They were unexecuted coverage. With the repository's own reviewed pins
   installed, they now run: 47 passed in those two files.
6. **Round 10.3 claimed the lineage correction left inference unchanged.** Now
   measured rather than assumed: byte-identical, digest unchanged.
