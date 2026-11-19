# RH-03 / AI-12.2 independent scientific manuscript verification

**Audit date:** 2026-11-19 (UTC)
**Baseline:** `9606b955b5c5906031ee88de704c3825b1f8b914`
**Audit scope:** read-only review of the graduation manuscript, its coverage JSON and RH-01 claim index; Git object provenance check for all 28 indexed source documents.
**Disposition:** provenance checks pass. Content comparison is partial: 9 claims have a narrow source-to-report transcription match, while 19 are explicitly `NOT_VERIFIABLE` by this audit. The task is not represented as a completed scientific verification; final scientific review and manuscript graduation remain pending. This is not scientific approval, reproducibility rerun, clinical validation, or lifting of any hold.

## Executive result

All 28 RH-01 `source_path` entries resolve at baseline and their Git blob IDs match the pinned SHA values. Coverage enumerates FR-01–FR-17 and the source index enumerates CL-001–CL-028. The revised matrix now gives each claim a manuscript chapter/line span, direct source excerpts with source line numbers, report excerpts and a distinct content-check status. Nine rows are limited transcription matches; 19 are `NOT_VERIFIABLE`, because repository-level archived prose is insufficient to establish the underlying research result or semantic truth. No result was rerun.

The complete 28-row matrix, including exact source paths, source line excerpts, manuscript line spans, independent content status and limitations, is in `RH03_AI12_2_AUDIT_MATRIX_2026_11_19.json`.

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

## Content-check result and numerical discrepancy ledger

Only nine claim rows are marked `PASS_SOURCE_MATCH`, and only as **transcription checks** of displayed source/report text—not validation of the historical computation. The remaining 19 claims are individually `NOT_VERIFIABLE`; many concern protected experimental provenance, secondary-source meaning, implementation semantics, or protocol/governance facts requiring a qualified human reviewer. No mismatch has been established.

- **Pinned source hash discrepancies:** 0 / 28.
- **Coverage inventory discrepancies:** 0; 17 FR identifiers and 28 CL identifiers present.
- **Claim content disposition:** 9 limited transcription matches; 19 `NOT_VERIFIABLE`; 0 `MISMATCH`; 0 `OUT_OF_SCOPE`.
- **Numerical corrections established by this audit:** none.
- **Potential interpretation hazard explicitly guarded:** treating ± repeated-CV SD as a CI or comparing the Cleveland and UCI-412 AUROCs as a same-cohort model comparison. Do not do either.

This is an archival consistency result only. It is not an independent numeric recomputation; consequently, any unobserved arithmetic or source-to-run discrepancy remains unresolved until an authorized, qualified reviewer inspects protected experiment provenance.

## Ten pending reviewer actions

All ten canonical actions from the coverage file are reproduced in the JSON matrix with their original `PENDING` status; none is marked complete:

REVIEW-01 — **PENDING:** Clinical source/feature chronology and target interpretation
REVIEW-02 — **PENDING:** Historical local protected aggregate provenance attestation where permitted
REVIEW-03 — **PENDING:** Report numeric values and table links vs original review documents
REVIEW-04 — **PENDING:** Scientific statistics: repeat SD not CI; no real external or labs claims
REVIEW-05 — **PENDING:** Calibration and sample-size limitations and exact Riley assumptions
REVIEW-06 — **PENDING:** Explainability fidelity scale and synthetic background privacy
REVIEW-07 — **PENDING:** Dataset/protocol acceptance and original research gate statuses
REVIEW-08 — **PENDING:** University report authorship, citations, declared contributions and formatting
REVIEW-09 — **PENDING:** Original code/test release SHA with native Windows 8/8 and synthetic E2E revalidation
REVIEW-10 — **PENDING:** Named independent reviewer decisions and formal acceptance

## Validator and test outcomes

`research/manuscript_audit/validate_integrity.py` is standard-library-only and read-only: it checks the new matrix against RH-01 and coverage, validates 17 FR / 28 CL cross-links, content-status enum, source mappings and SHAs, manuscript line spans/excerpts, all ten pending reviewer actions, and rejects affirmative clinical-go/approval fields. It does not read datasets, execute models or make scientific truth judgments.

Synthetic-only tests: `python -m unittest discover -s tests/manuscript_audit -v` — 5 tests passed: positive complete-matrix test plus negative cases for omitted row, wrong source mapping, reviewer status drift and stale excerpt anchor. Direct check: `python research/manuscript_audit/validate_integrity.py` — PASS with 17 chapters, 28 claims, 10 still-pending actions; content status counts: 9 `PASS_SOURCE_MATCH` (transcription only), 19 `NOT_VERIFIABLE`, 0 `MISMATCH`, 0 `OUT_OF_SCOPE`.

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
