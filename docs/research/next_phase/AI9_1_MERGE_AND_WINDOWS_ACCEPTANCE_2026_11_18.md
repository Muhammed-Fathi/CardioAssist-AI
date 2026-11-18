# AI-9.1 — merged Windows engineering closeout and synthetic paired report

**Date:** 2026-11-18  
**Proposed engineering status:** `MERGED_ENGINEERING_COMPLETE_SYNTHETIC_ONLY`  
**Proposed local Windows status:** `LOCALLY_ACCEPTED_ENGINEERING_ONLY`  
**Research evidence:** `SYNTHETIC_TEST_NOT_CLINICAL_EVIDENCE`  
**Provenance:** Maintainer-provided PowerShell 5.1 logs and generated JSON; independently checked GitHub merge/CI and external report JSON hash by the documentation author. The documentation author **did not execute native Windows tests**.  
**Scope:** docs-only acceptance record; does not approve real-data access, new fitting, laboratory model serving, external validation or clinical use.

## 1. Source and merge identity

| Event | Exact evidence |
|---|---|
| Reviewed implementation | [PR #87](https://github.com/Muhammed-Fathi/CardioAssist-AI/pull/87) |
| Exact PR head | `27fa6e57b2845d7dc4ae9ab20c17adab0a2d7733` |
| **Merged main SHA** | `b21ca074e9ef609894354e6d0327c4b7cc717093` |
| GitHub merge date | 2026-11-18 16:30:35 UTC |
| Changed scope | Six **added** files only: `ai/ai9_paired_synthetic.py`, `scripts/run_ai9_synthetic_comparison.py`, schema/README in `docs/research/ai9_1/`, and two AI-9.1 test modules |
| Previous main | `60bb1b815203e38f64ee699041868674896b616c` |

The PR did not modify a frozen real dataset, source files, models, original D-047/M3a plans, registered UCI-412 research authorizations, real-backend provider or Hungary locked assets. Its executable output is an **in-process fabricated synthetic** cohort and a paired Clinical vs Clinical+Labs *methods* comparison.

## 2. Hosted GitHub and Windows pre-merge evidence — exact PR head

| Gate | Observed result |
|---|---|
| GitHub Actions | **7/7 jobs SUCCESS** at `27fa6e...`: contract 1, audit Python 3.11+3.12 (2), backend Python 3.11+3.12 (2), synthetic experiment runner Python 3.11+3.12 (2) |
| Windows source revision | Detached exact PR-head worktree; clean before and after |
| Native runtime | Windows PowerShell 5.1, Python **3.12.9**, existing external prevalidated venv; `pip check` **PASS** |
| Focused regression | `python -m pytest -W error -q -ra --tb=short tests/experiments/test_ai9_paired_synthetic.py tests/contracts/test_ai9_paired_synthetic_schema.py tests/experiments/test_research_facade.py tests/backend/test_inference_provider.py` → **200 passed / 0 failed** in **60.22 seconds**, exit 0 |
| Protected sources | `python scripts/verify_sources.py` → **PASS**, four committed protected-file hashes matched; supervisor 25-paper census: **9 GREEN, 1 PINK, 6 ORANGE, 9 RED** |
| Native NTFS security | `python scripts/validate_ai_windows_compat.py` → JSON `PASSED`, **8/8**, exit 0 |
| **Full monolithic Windows suite** | `python -m pytest -W error -q -ra --tb=short` → **2,597 passed, 3 skipped, 0 failed**; exit 0; **6,505.47 seconds** (1:48:25) |
| Two independent external synthetic report exports | Byte-identical SHA-256 `6ebf36f021b4ddae0947a1cee508f40716be82dc47aaaa538173356c8a2f900a`, Draft-2020-12 JSON Schema PASS and internal checksum PASS |
| Final worktree | Same head SHA, `git status --porcelain --untracked-files=all` empty |

**Three documented Windows skips, not failures:** two cases in `tests/experiments/test_private_directory_creation_regression.py` (native Windows ACL preservation/inherited-ACL rejection) and one in `tests/experiments/test_research_routes.py` (insecure ACL case). The native **8/8** Windows security validation ran separately and passed. The full-suite result is **pre-merge**, not a claim of a second post-merge full-suite execution.

## 3. Native Windows post-merge smoke — exact merged SHA

Maintainer fetched `origin/main`, asserted it equals `b21ca074e9ef609894354e6d0327c4b7cc717093` and created a **new clean detached worktree** pinned to that SHA. Results from the actual merged code:

| Post-merge gate | Observed result |
|---|---|
| Clean exact merge SHA and `pip check` | **PASS**; Python 3.12.9 |
| `python scripts/verify_sources.py` | **PASS**; same four protected hashes and same 25-paper census |
| `python scripts/validate_ai_windows_compat.py` | **PASSED 8/8**, native Windows output parsed and checked |
| `pytest -W error -q -ra --tb=short tests/experiments/test_ai9_paired_synthetic.py tests/contracts/test_ai9_paired_synthetic_schema.py` | **44 passed, 0 failed** in **11.31 seconds** |
| Fresh synthetic output `scripts/run_ai9_synthetic_comparison.py --output <external-new-json>` | `SYNTHETIC_INCREMENTAL_VALUE_EXERCISE_COMPLETE`; 120 matched fictional rows |
| Validate actual output with `Draft202012Validator` and synthetic-only flags | **REPORT SCHEMA AND SCOPE: PASS** |
| Post-merge JSON SHA-256 | `6ebf36f021b4ddae0947a1cee508f40716be82dc47aaaa538173356c8a2f900a` — **exactly matches** pre-merge export bytes |
| Canonical JSON inner digest | `ed85b4f5ad7b47e90b2538022dd34277a8b593484d3fe47104ff83f236935f3c`; independently recomputed from submitted JSON excluding the `sha256` field: **MATCH** |
| Final worktree | Still exact merge SHA and **CLEAN** |
| Post-merge full monolithic suite | **NOT RE-RUN** — scoped 44 tests + security/source/report checks only; complete 2,597/3 suite belongs to reviewed PR head |

The attached generated report was also byte-hashed independently of the PowerShell transcript; its outer checksum and canonical content checksum match the above values. The report was **not** committed; no source records or locally generated real model artifacts entered Git.

## 4. Synthetic scientific report and honest interpretation

| Quantity | Result |
|---|---|
| Synthetic cohort | **120** matched individuals, 89 synthetic positives / 31 synthetic negatives |
| Paired model arms | `da_a2_resting_v1` (five raw clinical features) versus `da_a2_resting_labs_v1` (seven features = same five plus `chol` and `fbs`) |
| Family | L2 logistic regression **fixed across both arms** |
| Evaluation design | Same seeded 3 outer folds, 3 training-only inner folds, preprocessing/hyperparameter selection/calibration contained within train; compare held-out paired outcomes |
| Generated missing labs | `chol` 25/120, `fbs` 25/120; these are **invented** missingness observations |
| Clinical-only ROC AUC / Brier | `0.632113084450888` / `0.18231499413831945` |
| Clinical+Labs ROC AUC / Brier | `0.5976803189561435` / `0.18761493254286296` |
| Labs-minus-clinical paired delta AUROC / Brier | `-0.0344327654947445` / `+0.005299938404543514` |
| Conditional paired bootstrap delta AUROC interval | `[-0.07803552011598405, +0.002346864806089111]` (64 resamples; 95% conditional percentile) |
| Evidence flags | `SYNTHETIC_TEST_NOT_CLINICAL_EVIDENCE`; `real_data_execution_authorized=false`, `clinical_use_authorized=false`, `labs_route_activated=false` |

A negative synthetic labs-vs-clinical delta **is not an engineering failure**, and no favorable medical claim was fabricated. The displayed bootstrap is conditional on already-fitted outer-fold predictions: it does not refit models or quantify all selection uncertainty and is **not a clinical confidence interval**. Synthetic data do not establish actual labs improvement, real-data calibration, model sample-size adequacy or clinical utility. Prior real D-047 Cleveland and M3a UCI-412 **internal exploratory** outcomes remain intact, distinct and incomparable across cohorts.

## 5. Closeout disposition and next action

- **Accepted engineering scope:** AI-9.1 synthetic paired comparison harness, schema and tests **MERGED** and **NATIVE WINDOWS ACCEPTED** based on the exact-head full suite and exact-merge smoke above.
- **Parent AI-9:** **IN_PROGRESS** — AI-9.1 engineering slice done; AI-9.2 **real** clinical+labs incremental-value study remains separately gated by verified field meaning/timing, scientific cohort feasibility and appropriately authorized local protocol/data use.
- **Clinical:** `NOT_ESTABLISHED`; backend remains `MOCK_SYNTHETIC`; no real labs model route or clinical service is activated.
- **Immediate next:** human reviews/merges this docs-only closeout, then implementation starts in a **separate AI-10.1 PR** for a *synthetic-only* locked external-evaluation demonstration reusing existing external evaluation/ledger; Hungary remains untouched. In parallel scope **AI-12.2** research/graduation deliverable by indexing **existing** source audits, decisions and the already-executed D-047/M3a exploratory reports; do **not** restart dataset/model selection.
- **Required tracking rule:** the old Gate DA/PT source research remains authoritative; new implementation and results must be recorded by exact commit and evidence level. No separate real-data or scientific approvals follow from merging this docs-only PR.

**Review gate:** Link the exact PR/head/merge SHA and locally verified checks above in the [master progress tracker](../ai_master_progress.json). No separate signature, supervisor approval or model-fitness authorization is asserted or created.
