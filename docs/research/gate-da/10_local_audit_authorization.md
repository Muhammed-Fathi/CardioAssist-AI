# D-046 — Maintainer Local Read-Only Dataset Audit Authorization

## Authorization

- Status: AUTHORIZED_FOR_LOCAL_READ_ONLY_AUDIT
- Authorization date: 2026-10-21
- Human authorizer: Muhammed Fathi
- Responsible acquirer: Muhammed Fathi
- Audit reviewer: Muhammed Fathi
- Environment: E:\CardioAssist_AI_GitHub_Starter
- Scope: DA-A1, DA-A2, DA-B1, DA-B2
- Supervisor approval: NOT CLAIMED
- Model training: NOT AUTHORIZED

The named maintainer explicitly accepted local read-only audit access
using the AUTHORIZE-READ-ONLY-4 confirmation.

## Dataset and File Scope

| Access ID | UCI ID | Authorized files | Excluded files |
|---|---|---|---|
| DA-A1 | 412 | Z-Alizadeh sani dataset.xlsx | extention of Z-Alizadeh sani dataset.xlsx |
| DA-A2 | 45 | processed.cleveland.data, cleveland.data, processed.hungarian.data, hungarian.data, processed.switzerland.data, switzerland.data, processed.va.data, long-beach-va.data, heart-disease.names | new.data, reprocessed.hungarian.data, processed.long-beach-va.data |
| DA-B1 | 411 | extention of Z-Alizadeh sani dataset.xlsx |  |
| DA-B2 | 145 | heart.dat |  |

## Usage Restrictions

DA-A1 and DA-A2 are primary data-quality and suitability audit candidates.

DA-B1 is audit-only for correspondence with DA-A1.
It must not count as an independent cohort.

DA-B2 is audit-only for overlap investigation against Cleveland.
It must not count as independent training or validation data.

All datasets are restricted to local read-only audit.
No model fitting, tuning, feature selection, performance evaluation,
calibration, SHAP, LIME, or clinical-readiness claims are authorized.

Patient-level files must remain under git-ignored data/raw directories.
Originals must remain byte-identical.
Official UCI provenance and license snapshots must be recorded.

## Governance Implementation

The committed research/audit/gate_da_authorization.json remains
the PENDING baseline template used by existing regression tests.

The human-authorized operational manifest is stored locally at:
data/manifests/gate_da_authorization.local.json

All real-data audit operations must explicitly pass that
local manifest using the --auth-manifest CLI option.

This record requires review and merge into main before acquisition.

Gate PT remains closed and requires its separate approval process.
