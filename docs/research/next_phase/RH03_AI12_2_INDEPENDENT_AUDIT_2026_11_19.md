# RH-03 / AI-12.2 independent scientific manuscript verification

**Audit date:** 2026-11-19 (UTC)
**Baseline:** `9606b955b5c5906031ee88de704c3825b1f8b914`
**Audit scope:** read-only review of the graduation manuscript, its coverage JSON and RH-01 claim index; Git object provenance check for all 28 indexed source documents.
**Disposition:** provenance checks pass; scientific review and final manuscript graduation remain pending. This is not a scientific approval, reproducibility rerun, clinical validation, or lifting of any hold.

## Executive result

All 28 RH-01 `source_path` entries exist at the baseline and their actual Git blob IDs exactly match the pinned SHA values in the index. The manuscript coverage enumerates FR-01–FR-17 and the claim index enumerates CL-001–CL-028. I found no source-blob discrepancy and no clearly supportable numerical correction to make from this archival, read-only check. This does **not** mean the archived experiments were rerun or that the manuscript values are independently reproduced: the source documents themselves characterize key real-data results as historical/internal exploratory evidence.

The complete 28-row claim matrix, including exact source path, source section, report destination, match disposition, and reviewer requirement, is in `RH03_AI12_2_AUDIT_MATRIX_2026_11_19.json`. The validator checks structural coverage and source-object identity only.

## High-risk scientific checks

### Cleveland D-047 versus UCI-412 M3a

Keep these results as separate source-specific analyses. Both report 303 records, but the cohorts, endpoints/label definitions, predictor panels and class fractions differ. D-047 reports 139 positive / 164 negative; UCI-412 reports 216 `Cad` / 87 `Normal`. Therefore the reported AUROCs (Cleveland 0.8271 ± 0.0097; UCI-412 0.9107 ± 0.0071) are not a head-to-head comparison on a shared benchmark. The report's explicit non-comparability warning is scientifically necessary. The ± values are descriptive population SDs across four dependent repeated-CV runs—not confidence intervals, standard errors, or independent-cohort uncertainty intervals.

### Sampling adequacy and inference

The indexed Cleveland adequacy source states the outcome-proportion criterion at the stated 0.05 half-width requires 382 observations (not met at n=303); its additional MAPE criterion at p=8 requires 459. Human exploratory adequacy remains `NOT ASSESSED`. UCI-412 requires 315 for its stated outcome-proportion criterion (not met at n=303); its R²-dependent criteria are not assessed. These are not grounds to imply a sample is adequate simply because a repeated-CV SD is small. Repeated folds/repeats reuse the same participants and do not multiply the independent sample size.

### Calibration and explainability

The historical Cleveland calibration source records logistic slope 0.8980 (4/4 estimable) and CITL −0.0212, with RF/LR estimation caveats; UCI-412 records logistic slope 1.0891 (4/4) and CITL 0.0206, RF 3/4, and no reported joint free-intercept fit or reliability bins. These are descriptive diagnostics, not proof of medical reliability or transportable calibration. Keep intercept and slope estimability explicit.

The manuscript appropriately distinguishes the research explainers from the active application route: genuine offline grouped SHAP and seeded tabular LIME are research implementations with scale/fidelity limitations; the running inference registry admits only `MOCK_SYNTHETIC`. SHAP-shaped synthetic offsets are not genuine SHAP and neither explainer supplies clinical evidence. Do not imply real patient inference, external validity, feature causality or clinical utility.

### Dataset, statuses and references

The evidence records leave UCI-412 field timing/direction questions unresolved, identify UCI-411 as the same 303 participants (not independent validation), and treat Hungary as a conditional locked-site candidate without a real assessment. Fictional-cohort AI-9.1/AI-10.1 rehearsals are engineering demonstrations, not clinical incremental-value or external-validation findings. No patient-level dataset was accessed, no model was trained, no external validation was performed, and no approval or scientific hold was changed in this task. Source references are exact repository paths and pinned object IDs; a human academic reviewer must still verify source interpretation and bibliographic adequacy.

## Numerical discrepancy ledger

- **Pinned source hash discrepancies:** 0 / 28.
- **Coverage inventory discrepancies:** 0; 17 FR identifiers and 28 CL identifiers present.
- **Numerical corrections established by this audit:** none.
- **Potential interpretation hazard explicitly guarded:** treating ± repeated-CV SD as a CI or comparing the Cleveland and UCI-412 AUROCs as a same-cohort model comparison. Do not do either.

This is an archival consistency result only. It is not an independent numeric recomputation; consequently, any unobserved arithmetic or source-to-run discrepancy remains unresolved until an authorized, qualified reviewer inspects protected experiment provenance.

## Validator and test outcomes

`research/manuscript_audit/validate_integrity.py` is standard-library-only and read-only: it parses the two JSON inventories, verifies 17/28 identifier completeness, confirms manuscript chapter identifiers, and resolves every pinned source blob with `git rev-parse <base>:<path>`. It does not read dataset files, execute models, change artifacts or make a scientific truth judgment.

Synthetic-only tests: `python -m unittest discover -s tests/manuscript_audit -v` — expected 2 tests covering missing inventory and pinned-hash mismatch. Direct check: `python research/manuscript_audit/validate_integrity.py` — expected PASS, 17 chapters, 28 sources.

## Remaining reviewer requirements / blockers

1. Independent academic/statistical review of every source-to-report interpretation and citation; especially source-defined endpoint language (`>50%` versus `≥50%`), variable acquisition timing/direction and calibration estimability.
2. Confirm protected experiment artifacts/manifests against source documents through an authorized human process; no rerun was within this audit's scope.
3. Preserve formal research gates: P-1 pending, P-3 closed, P-5 prohibited as recorded in governance; D-047 / M3a status and local authorization requirements remain untouched. No supervisor, ethics, institutional or clinical approval is inferred.
4. Complete Windows-local final-release acceptance and bind the actual final release SHA/report hash before calling the manuscript graduated. Current SHA is an audit-start baseline, not that release identity.
5. Obtain human review of the whole manuscript, not just the indexed claims; this automated checker cannot assess writing, adequacy of literature coverage, causal interpretation or clinical safety.

## Provenance and execution record

- `AGENTS.md` and `docs/DECISIONS.md` governance context inspected; scientific restrictions were followed.
- Every one of 28 source documents in `RH01_CLAIM_EVIDENCE_INDEX_2026_11_19.json` was resolved at baseline with `git rev-parse <baseline>:<source_path>` and compared byte-for-byte by Git blob SHA to `source_blob_sha`.
- No dataset, patient-level data, model weights or providers were accessed or changed; no training, validation, calibration, SHAP/LIME execution, or approval action occurred.
- The audit did not amend the manuscript or source protocols because no correction could be established as fully verified from these records alone.
