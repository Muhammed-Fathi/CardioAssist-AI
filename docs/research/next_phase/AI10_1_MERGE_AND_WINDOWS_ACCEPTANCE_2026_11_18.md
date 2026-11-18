# AI-10.1 — merged synthetic locked-site engineering acceptance

**Recorded:** 2026-11-18. **Disposition:** `MERGED_ENGINEERING_COMPLETE_SYNTHETIC_ONLY` / `LOCALLY_ACCEPTED_ENGINEERING_ONLY`. **Evidence class:** `SYNTHETIC_TRANSPORT_TEST_NOT_EXTERNAL_VALIDATION`.

**Provenance:** GitHub PR/commit and hosted CI were checked through GitHub. Native Windows PowerShell 5.1 logs and the post-merge generated `ai10-postmerge.json` were provided by the maintainer. The documentation author independently calculated the report file SHA-256 and the canonical JSON internal SHA-256, but **did not execute tests on the maintainer's Windows machine** or independently examine the private external ledger file. Do not portray maintainer-reported command outcomes as an independently re-run Windows lab.

## 1. Exact source / merge identity

| Item | Evidence |
|---|---|
| PR | [#90 — synthetic locked external-site rehearsal](https://github.com/Muhammed-Fathi/CardioAssist-AI/pull/90) |
| Reviewed source head | `b5276717eb3cf45551141ec818beebfb291a0eff` |
| **Merge commit / main after merge** | `5786424593c5fa9387a1bf382b2233b02779de42` |
| Merged | 2026-11-18 20:21:56 UTC |
| Main before merge | `ce50915b8f362d9e32c301c357d2ec476dff787c` |
| Source change scope | **Exactly six newly added files**; no old engine/provider/dataset/approval file changed |
| Earlier process docs | PR #88 and AI-9.1 closeout PR #89 both merged before #90 |

New files: `ai/ai10_synthetic_transport.py`, `scripts/run_ai10_synthetic_locked_site.py`, `docs/research/ai10_1/README.md`, `docs/research/ai10_1/synthetic-locked-site.v1.schema.json`, `tests/experiments/test_ai10_synthetic_transport.py`, and `tests/contracts/test_ai10_synthetic_schema.py`.

The implementation composes pre-existing `train_research_model`, `evaluate_locked_external_cohort`, `ExternalEvaluationLedger`, and the registered `da_a2_resting_v1` synthetic route. It **does not** perform or authorize independent real Hungary evaluation.

## 2. GitHub CI and pre-merge Windows evidence

| Gate on reviewed PR head `b527671...` | Outcome |
|---|---|
| Hosted GitHub Actions | Four workflows, **7/7 jobs SUCCESS** (contracts 1, audit 1, backend 2, synthetic experiments 2; Python versions per each CI matrix) |
| Clean exact detached head | PASS before and after full suite |
| Local Python / `pip check` | Existing Python 3.12.9 virtualenv; **PASS** |
| Protected source `scripts/verify_sources.py` | **PASS**, four committed SHA-256 hashes; supervisor paper census unchanged: 9 GREEN / 1 PINK / 6 ORANGE / 9 RED |
| Windows native `scripts/validate_ai_windows_compat.py` | **PASSED 8/8** |
| AI-10.1 focused two test modules with `-W error` | **18 passed in 7.17 s**, 0 failures |
| **Full Windows** `python -m pytest -W error -q -ra --tb=short` | **2,615 passed, 3 skipped, 0 failed**; exit 0; **6,063.69 s (1:41:03)** |
| Synthetic CLI result | `SYNTHETIC_LOCKED_SITE_EXERCISE_COMPLETE` on fabricated fixtures |
| Final HEAD and git status | Exactly `b5276717eb3cf45551141ec818beebfb291a0eff`; `git status --porcelain --untracked-files=all` empty; **PASS** |

**Three documented Windows-only skips** (not counted as passed): `tests/experiments/test_private_directory_creation_regression.py:30` (native Windows ACL preservation), `tests/experiments/test_private_directory_creation_regression.py:47` (inherited ACL rejection), and `tests/experiments/test_research_routes.py:556` (insecure ACL case). Native Windows security validation independently reported **8/8 PASSED**.

**Historical verifier correction:** The first ad-hoc PowerShell `python -c $Verify` command failed with `SyntaxError` from double-quote stripping. Its subsequent manually printed green PASS was **not accepted as evidence**. The uploaded pre-merge JSON was independently hashed and schema-constraint checked. This problem was not an observed ML or one-shot ledger exception.

## 3. Native Windows post-merge smoke on exact merge SHA

A *new* detached and clean worktree was created from freshly fetched `origin/main`, verified as `5786424593c5fa9387a1bf382b2233b02779de42`. The maintainer's exact 6-step PowerShell command ran to its final success message **without errors**:

| Post-merge check | Actual maintainer result |
|---|---|
| Fresh detached HEAD / `pip check` | Exact merge SHA, clean checkout; `No broken requirements found` |
| `scripts/verify_sources.py` | **PASS** — same four source hashes and unchanged 25-paper census |
| `scripts/validate_ai_windows_compat.py` | **PASSED 8/8**, parsed and verified by script |
| AI-10.1 two focused modules | **18 passed in 7.40 s**, 0 failed |
| Fresh fake-site CLI and private external paths | `SYNTHETIC_LOCKED_SITE_EXERCISE_COMPLETE`, aggregate JSON and local protected ledger |
| **Standalone** `verify_ai10.py` (no fragile `python -c`) | `AI-10.1 SCHEMA: PASS`; `DIGEST: PASS`; `LEDGER: COMPLETED`; `SYNTHETIC SCOPE: PASS` |
| Report file SHA-256 | `dea4674bf14ae5ff55a9c819f1d3f137c92a7eeda30915813a0bb1e2cad91f2d` |
| Report inner canonical digest | `aee7535850b8c1bd4cb040164252a593bd82656b457f921382598766b6693c47` |
| Final head / worktree | No SHA drift; `git status --porcelain --untracked-files=all` empty |
| Final printed result | `AI-10.1 POST-MERGE SMOKE: PASSED`; `WINDOWS SECURITY: 8/8 PASSED` |
| **Post-merge full 2,615-test suite** | **NOT RE-RUN**; the 2,615/3 full suite belongs to the pre-merge reviewed source head, and the merged six-file change has targeted 18-test/source/security/report smoke |

Both SHA-256 values were **independently recomputed** from the *uploaded post-merge JSON bytes* and matched the earlier pre-merge report. This demonstrates stable fabricated report replay on the observed execution, not cryptographic proof of model binary identity or real-world data independence.

## 4. Generated report — synthetic values ONLY

| Field | Generated value |
|---|---|
| Development / mock external rows | 96 / 48 |
| Mock external class counts | 35 positives / 13 negatives |
| Registered panel | `da_a2_resting_v1`; contract SHA-256 `c18ad4cd2cf08f6fefb2e340573760da7000bc1d8eb4ad38783b873c018e57b8` |
| Selected family | `l2_logistic_regression` (development synthetic cohort only) |
| Invented shift | Age +4 years; resting blood pressure +7 mmHg, bounded |
| Synthetic uncalibrated ROC AUC / Brier | 0.7692307692307693 / 0.18266855964550913 |
| Synthetic transport-calibrated ROC AUC / Brier | 0.7692307692307693 / 0.17751924735231636 |
| Evaluator's one-shot receipt | Report claims `ledger_slot_consumed=true` and `ledger_status=COMPLETED`; maintainer's verifier read one private ledger entry and checked `COMPLETED` |
| Model tuning on invented external set | Report field `model_tuned_on_external=false` |
| Real Hungary, real clinical validation | **NOT performed**; all real-data/clinical-use flags `false` |

Scores, outcome counts and simulated site shift are **fabricated technical test outputs**; there is no support for CAD prognosis, clinical discrimination/calibration claims, accuracy across actual sites, or population transfer. Report metadata digest is **not an authenticated estimator-weights digest**. A protected local ledger is **not** an independent medical review, regulator authorization or patient-level overlap audit.

## 5. Honest closeout and outstanding science

- **AI-10.1:** source **MERGED**, pre-merge full-suite and post-merge focused/NTFS/JSON checks **locally accepted for synthetic engineering ONLY**. Source-level model/evaluator guards remain in place.
- **AI-10 parent:** **IN_PROGRESS**; real Cleveland-to-Hungary locked assessment remains **NOT_ESTABLISHED / CONDITIONAL_CANDIDATE_NOT_READY**, never activated by this PR.
- **Real assessment missing gates:** compatible predictor units/coding/endpoint timing, named site/participant overlap verification, missingness and transportability feasibility, locked artifact and predeclared analysis plan, precision/sample-size review, separately authorized access/governance and qualified oversight. No permissions were changed.
- **Next executable research deliverable:** AI-12.2 graduate report/evidence-indexed handoff, incorporating the already completed Gate DA/PT research, historical Cleveland D-047 and UCI-412 M3a internal exploratory experiments (distinguishing their cohorts/targets, no invalid AUROC head-to-head claim), AI-9.1, AI-10.1, source integrity, test evidence and limitations. Do not restart dataset discovery or model development without an approved new question.
- **Tracking policy:** this is a **docs-only proposed closeout**. Human reviews/merges the PR before the canonical tracker change is accepted; no real validation or clinical approval follows from its merge.

Reference documents: [AI9–AI12 execution slices](AI9_AI12_EXECUTION_SLICES.md), [AI-9.1 Windows closeout](AI9_1_MERGE_AND_WINDOWS_ACCEPTANCE_2026_11_18.md), [M2f Hungary conditions](../gate-pt/07_m2f_hungary_scientific_decision_and_conditional_protocol.md), and [master completion plan](../CARDIOASSIST_AI_MASTER_COMPLETION_PLAN.md).
