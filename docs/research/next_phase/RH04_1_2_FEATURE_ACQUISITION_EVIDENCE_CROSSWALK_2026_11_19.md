# RH-04.1/RH-04.2 — Feature acquisition-evidence crosswalk (EVIDENCE ONLY)

**Status:** `EVIDENCE_ONLY_NOT_APPROVED` · **Prepared:** 2026-11-19 ·
**Verified `main` baseline:** `545d0d835ecb64a6b1aaeb3957705a30bb2ce760` ·
**Branch:** `arena/80cb76a4-cardioassist-ai` ·
**Artifact:** [`research/intake/schemas/feature_acquisition_evidence_crosswalk.v1.json`](../../../research/intake/schemas/feature_acquisition_evidence_crosswalk.v1.json)
(`rh04_feature_acquisition_evidence_crosswalk.v1`, schema `1.1.0`,
document digest `1c79195261c40ffc212d384c64b3645a2ef563f39b3b5b240a5a906c108abda7`,
file size 78,287 bytes)

> **Revision 2 (PR #113 review `5972725432`).** Schema `1.1.0` corrects an
> over-broad source permission: v1.0.0 exported
> `AUTHORIZED_INTERNAL_EXPLORATORY_NOT_SUPERVISOR_APPROVED` for **all seven**
> UCI-45 features — including `chol`/`fbs` — and `query_feature_evidence()`
> returned that status for the five resting features when reached through the
> **locked Hungary route**. D-047 covers only the original Cleveland
> five-field internal exploratory study. The correction separates (a)
> historical D-047 authorization **evidence**, (b) the **current effective
> permission** of a feature/panel/route, and (c) the **absence of new
> real-data authorization**; see §2.1. D-047 itself, every frozen panel, route,
> hold, restriction and timing fact are unchanged.

> **Scope note — Issue #112 text was not readable.** Reading Issue #112 through
> the GitHub API returned `403 Resource not accessible by integration` for the
> authenticated identity, so this slice implements the **stated fallback
> scope**: a versioned, machine-readable feature acquisition-evidence crosswalk
> with a tested, fail-closed offline validator and a deterministic metadata
> query. Nothing here is claimed as a complete implementation of the unread
> Issue #112 text; the maintainer must confirm coverage.

---

## 1. What already exists and is reused (no duplication)

| Existing artifact | Role in this slice |
|---|---|
| `ai/panels.py` → `REGISTERED_PANELS` (4 panels) | Authoritative feature roster, order, units, codes, ranges, targets. The crosswalk **references** panel ids/versions and never restates clinical semantics. |
| `ai/research_routes.py` → `RESEARCH_ROUTE_CATALOG` (5 routes) | Authoritative activation, admissibility, authorization, evaluation status and permitted/forbidden operations. |
| `research/intake/uci412_field_contract.py` + `schemas/uci412_basic_clinical_field_contract.v0.1.json` | The registered 16-field acquisition-channel taxonomy (`VERIFIED_REGISTERED_SOURCE_DOMAIN`) and its fail-closed "JSON must agree with frozen code" pattern. |
| `research/intake/cleveland_source_mapping.py` + R1 mapping JSON | UCI-45 five-field proposed channel/timing statements. |
| `research/uci412/feature_schema.py` + dictionary `1.1.0` | Registered `source_domain`, `input_owner` and `availability_at_decision_time` per UCI-412 column. |
| `research/uci412/schemas/ai8r_eligibility.v1.json` | Per-field `pre_angiography = UNVERIFIED` evidence register (16/16). |
| `docs/research/next_phase/RH02_SOURCE_QUESTION_REGISTER_2026_11_19.json` | Q-04 timing-gap finding: 0/16 owner-verified pre-angiography timings. |

No second clinical feature schema, no second route catalog, no new model route,
no new endpoint and no new provider is introduced.

## 2. The four distinctions, per registered feature (30 records)

| # | Distinction | Machine-readable fields |
|---|---|---|
| 1 | **Original-source feature-definition evidence** | `definition_evidence_ids` → `evidence_register[]` (`evidence_class`, `reference_path`, `establishes_feature_definition`, `establishes_acquisition_timing`, `owner_attested_timing_evidence`) |
| 2 | **Proposed acquisition channel** | `acquisition.channel` (4-value taxonomy) + `acquisition.channel_status` (`VERIFIED_REGISTERED_SOURCE_DOMAIN` = 16 UCI-412 basic fields, `PROPOSED_FUTURE_ACQUISITION_CHANNEL` = 7 UCI-412 labs + 7 UCI-45 fields) |
| 3 | **Verified vs unverified pre-angiography timing** | `acquisition.timing_status`, `acquisition.owner_verified_pre_angiography`, `acquisition.timing_derived_from_channel_status`, `acquisition.timing_evidence_ids` |
| 4 | **Source-specific permission and restrictions** | `permission_id`, `effective_permission` (`effective_permission_status`, `historical_authorization_reference_ids`, `real_data_execution_authorized_by_this_crosswalk`), `restriction_ids[]`, `sources[]`, `blocked_items[]` |

Counts: **30** features (7 UCI-45 + 23 UCI-412) across **4** panels
(5/7/16/23 features) and **5** routes; **10** registered evidence items;
**3** scoped permission records; **1** historical authorization reference;
**9** restrictions; **3** blocked items.

The `PEER_REVIEWED_SECONDARY_PUBLICATION` class is registered in the evidence
taxonomy but deliberately **unused** in v1: the secondary Tao et al. (2025)
table supports only a provisional 0/1 direction and is never promoted here to
definition or timing authority.

### 2.1 Authorization scope (schema `1.1.0`)

The crosswalk never exports an unqualified `AUTHORIZED…` status. The validator
rejects any permission status or effective status starting with `AUTHORIZED`,
and the string `AUTHORIZED_INTERNAL_EXPLORATORY_NOT_SUPERVISOR_APPROVED` no
longer appears anywhere in the document.

| Surface | Machine-readable field | Cleveland resting five (`DA-A2`) | `chol` / `fbs` | UCI-412 (23 features) | Hungary locked route |
|---|---|---|---|---|---|
| **Historical D-047 evidence** (what was done) | `authorization_references[]` → `AUTHREF-D047-CLEVELAND-FIVE-FIELD` | `decision_id: D-047`, `execution_status: COMPLETED_HISTORICAL_INTERNAL_EXPLORATORY`, label `INTERNAL_EXPLORATORY_NOT_SUPERVISOR_APPROVED`, `authorizes_new_real_data_execution: false` | **not covered** | **not covered** | **not covered** (panel `da_a2_resting_v1` only) |
| **Current effective permission** (what may run now) | `effective_permission.effective_permission_status` | `HISTORICAL_REFERENCE_ONLY_NO_NEW_AUTHORIZATION` (5) | `NOT_AUTHORIZED` (2) | `SCIENTIFIC_HOLD_NEW_REAL_FIT` (23) | `NOT_AUTHORIZED` |
| **New real-data authorization granted** | `real_data_execution_authorized_by_this_crosswalk`, `authorization_scope`, `holds` | `false` | `false` | `false` | `false` |

Route-level effective permissions: `da_a2_resting_v1` →
`HISTORICAL_REFERENCE_ONLY_NO_NEW_AUTHORIZATION`; `da_a1_basic_clinical_v1` →
`SCIENTIFIC_HOLD_NEW_REAL_FIT`; `da_a2_resting_labs_v1`,
`da_a1_clinical_core_labs_v1`, `da_a2_hungary_locked_transportability_v1` →
`NOT_AUTHORIZED`. Source-level: UCI-45 → `NOT_AUTHORIZED_FOR_NEW_REAL_DATA`,
UCI-412 → `SCIENTIFIC_HOLD_NEW_REAL_FIT`.

Permission records are scoped, not source-wide:

| Permission record | `permission_status` | Covered features |
|---|---|---|
| `PERM-UCI45-D047-HISTORICAL-REFERENCE` | `HISTORICAL_D047_SCOPE_REFERENCE_ONLY` | exactly `age`, `sex`, `cp`, `trestbps`, `restecg` |
| `PERM-UCI45-LABS-NOT-AUTHORIZED` | `NOT_AUTHORIZED_OUT_OF_D047_SCOPE` | exactly `chol`, `fbs` |
| `PERM-UCI412-SCIENTIFIC-HOLD` | `SCIENTIFIC_HOLD_NEW_REAL_FIT` | all 23 UCI-412 features |

`authorization_scope` states that a historical reference is **not** a currently
operative permission, that no new real-data execution is authorized, and that
`chol`, `fbs` and the locked Hungary route are outside D-047. `holds` gains
`historical_d047_authorization_scope =
CLEVELAND_FIVE_FIELD_INTERNAL_EXPLORATORY_ONLY` and
`new_real_data_authorization_granted_by_this_crosswalk = false`, both frozen and
validator-checked. The validator also freezes, per permission record, the only
effective status it may resolve to, and freezes the reference's dataset, panel,
exact five feature names, execution status, historical label and evidence ids.

### Timing reality recorded

| Source | Registered features | Owner-verified pre-angiography timing |
|---|---|---|
| UCI-412 (`DA-A1`) | 23 (16 basic + 7 labs) | **0 / 16** basic-clinical, **0 / 7** labs |
| UCI-45 (`DA-A2`) | 7 | **0 / 7** |

`VERIFIED_REGISTERED_SOURCE_DOMAIN` verifies only that the proposed channel
matches a frozen register's `source_domain`/`input_owner`. Every crosswalk
record carries `timing_derived_from_channel_status: false`, and the validator
forbids any other combination.

### Holds and blocked items preserved

| Hold / block | Recorded state |
|---|---|
| Gate PT P-1 | `PENDING` |
| Gate PT P-3 | `CLOSED` |
| Gate PT P-5 | `NOT_MADE_PROHIBITED` |
| UCI-412 scientific hold | `true` |
| UCI-45 labs extension (`da_a2_resting_labs_v1`) | `BLOCKED`, contract query only |
| UCI-412 labs route (`da_a1_clinical_core_labs_v1`) | `BLOCKED`, contract query only |
| Hungary locked evaluation (`da_a2_hungary_locked_transportability_v1`) | `BLOCKED`, contract query only |

Activation by this artifact: **none**. `permissions[].activation_by_this_artifact
= "NONE"` and
`permissions[].real_data_execution_authorized_by_this_crosswalk = false`.

## 3. Functional code (not JSON documentation)

`research/intake/feature_acquisition_crosswalk.py` (stdlib only):

- `validate_crosswalk(document)` — fail-closed structural and semantic
  validation with stable error codes and JSON paths;
- `load_crosswalk()` — reads and validates the single registered document;
- `query_feature_evidence(...)` — deterministic, read-only metadata query over
  `dataset_id`, `panel_id`, `route_id`, `feature_name`, `timing_status`,
  `channel_status` with canonical output and explicit zero-result semantics;
- `describe_crosswalk()` — deterministic summary counts;
- `crosswalk_document_digest(document)` / `canonical_json(...)` — stable
  digests for provenance and determinism checks;
- CLI: `python -m research.intake.feature_acquisition_crosswalk
  {validate,describe,query}`.

Every result state is `METADATA_ONLY_NO_CAD_PROBABILITY_COMPUTED`;
`cad_probability_computed: false`, `read_only: true`, `files_written: false`.

## 4. Fail-closed negative coverage (mandated categories)

| Required category | Representative enforced codes |
|---|---|
| Unknown fields | `unknown_field`, `missing_field` (top level, feature, acquisition, route, evidence blocks) |
| Source mismatch | `source_mismatch`, `route_panel_mismatch`, `panel_dataset_mismatch`, `feature_key_mismatch`, `permission_mismatch` |
| Timing promotion | `timing_promotion_without_owner_evidence`, `evidence_class_cannot_establish_timing`, `timing_status_inconsistent`, `scientific_hold_promotion` |
| Prohibited variables | `prohibited_feature` (Cath, LAD, num, ca, thal, thalach, EF-TTE, wearable_ecg, patient_id), `unregistered_feature` (e.g. `Q Wave`) |
| Invalid status | `invalid_timing_status`, `invalid_channel_status`, `invalid_permission_status`, `invalid_activation_state`, `invalid_disposition`, `status_promotion`, `invalid_evidence_class` |
| Unauthorized route activation | `unauthorized_route_activation`, `unauthorized_activation`, `missing_route_restriction`, `operation_overlap`, `unknown_route_id` (6th route) |
| Authorization-scope widening | `unknown_authorization_reference`, `duplicate_authorization_reference`, `missing_authorization_reference`, `authorization_scope_mismatch` (widened feature list, moved panel/dataset, reopened execution status, rewritten label, labs record citing D-047, Hungary route citing D-047, weakened statement, flipped holds), `invalid_effective_permission_status`, `unauthorized_permission_status` |

Additional integrity guards: `invalid_reference_path`,
`missing_reference_document`, `duplicate_feature_key`, `missing_feature`,
`panel_version_mismatch`, `panel_registry_mismatch`,
`restriction_set_mismatch`, `offline_clause_mismatch`,
`no_result_contract_mismatch`, `taxonomy_definition_mismatch`,
`baseline_sha_mismatch`.

## 5. IMPLEMENTED / TESTED / PROPOSED / UNVERIFIED

**IMPLEMENTED** — the versioned crosswalk document, the stdlib-only offline
validator, the deterministic metadata query and CLI, the stdlib-only test suite
and the live panel/route binding suite. No backend, contract, migration,
workflow, model artifact or source-status change.

**TESTED** — see §6 for exact commands and results.

**PROPOSED / NOT DECIDED** — every acquisition channel for UCI-45 and every
laboratory channel for UCI-412 remains a proposal
(`PROPOSED_FUTURE_ACQUISITION_CHANNEL`). No dataset selection decision
(Cleveland is **not** selected), no harmonized cross-dataset schema, no
calibration or threshold decision, and no scientific adjudication of any of the
open questions (S-9 direction, BP/PR semantics, chest-pain exclusivity,
`>`50% vs `≥50%` boundary, 54/55/56 column count) is made or implied.

**UNVERIFIED** — owner-verified pre-angiography timing for **all** 30 features;
UCI-412 laboratory admissibility; owner codebook / CRF acquisition protocol for
both sources; whether a future owner-supplied codebook would even satisfy the
reviewed elevation procedure (that requires a code-and-evidence change plus
independent review, not a JSON edit).

## 6. Exact verification (Linux sandbox, Python 3.11.2)

| Check | Command | Result |
|---|---|---|
| Focused RH-04 stdlib suite | `python -m pytest tests/audit/test_feature_acquisition_crosswalk.py -q -W error` | 120 passed |
| Focused live binding | `python -m pytest tests/experiments/test_feature_acquisition_crosswalk_panel_binding.py -q -W error` | 34 passed |
| Audit + experiment regression suites | `python -m pytest tests/audit tests/experiments -q -W error` | 1515 passed, 2 skipped (audit 696, experiments 819) |
| UCI-412 regression suite | `python -m pytest tests/uci412 -q -W error` | 396 passed |
| Manuscript-audit integrity | `python -m pytest tests/manuscript_audit -q -W error` | 5 passed |
| Contract suite | `python -m pytest tests/contracts -q -W error` | 306 passed |
| Backend suite | `python -m pytest tests/backend -q -W error` | 583 passed |
| Source-material integrity | `python scripts/verify_sources.py` | all SHA-256 OK; 25 papers 9/1/6/9 |
| Audit toolchain self-test | `python -m research.audit self-test` | PASS (`originals_byte_identical: true`) |
| Audit ignore check | `python -m research.audit verify-ignore` | PASS |
| Synthetic experiment dry-run | `python -m research.experiments dry-run` | PASS |
| UCI-412 synthetic dry-run | `python -m research.uci412 dry-run` | PASS |
| Crosswalk CLI | `python -m research.intake.feature_acquisition_crosswalk validate` | `validated: true`, schema `1.1.0`, 30 features, 5 routes, digest `1c791952…abda7` |
| Whitespace hygiene | `git diff --check` | clean |
| Full repository suite | `python -m pytest -q -W error` | **2805 passed, 2 skipped** |

Environment note: `tests/backend` needs the repository-pinned
`anyio==4.14.2` for `-W error`; with the newer resolution in this sandbox a
third-party `starlette`/`anyio` deprecation warning fails the run before any
test executes. This slice does not touch backend code.

## 7. Limitations (explicit)

1. **No owner evidence was accessed.** No owner-signed acquisition codebook, CRF
   timestamp, or per-field collection protocol exists in any reviewed document.
   The crosswalk records that absence; it does not resolve it.
2. **No issue-#112 text available** (GitHub 403), so this is the fallback scope,
   not a verified reading of that issue.
3. **No real data, model fitting, calibration, SHAP/LIME, packaging or inference
   run** — synthetic in-memory fixtures only.
4. **No cross-dataset harmonization.** The crosswalk records two independent,
   non-translatable source contracts and explicitly forbids translation.
5. **No scientific or clinical status change.** Gate PT P-1/P-3/P-5, D-046,
   D-047, D-048 and every register entry are untouched; the historical
   completion tracker is deliberately not revised, so RH-04 remains `PLANNED`
   in that snapshot.
6. **Not an approved intake contract.** A future reviewed intake design would
   need its own authorization; this evidence layer creates no scoring path.
7. **Windows-native replay not performed** in this environment (Linux sandbox
   only); the suites used are the repository's existing Linux CI commands.

## 8. Explicit non-changes

`backend/**`, `shared/contracts/**`, `.github/workflows/**`, `alembic/**`,
`research/uci412/**` schemas, `research/experiments/**` plan,
`docs/DECISIONS.md`, `docs/research/ai_master_progress.json`, the completion
tracker JSON and every existing panel/route descriptor are **unmodified**.

## 9. Review-driven change log

| Review | Finding | Correction | Evidence |
|---|---|---|---|
| PR #113 review `5972725432` | `AUTHORIZED_INTERNAL_EXPLORATORY_NOT_SUPERVISOR_APPROVED` was exported for all 7 UCI-45 features, including `chol`/`fbs`, and for the five resting features when queried through the locked Hungary route | Split historical D-047 evidence from effective permission; scoped permission records; added `authorization_scope`, `authorization_references[]`, `effective_permission` on features/routes and `effective_source_permission_status` on sources; D-047 reference limited to the exact Cleveland five-field roster and marked non-authorizing | `tests/audit/test_feature_acquisition_crosswalk.py::test_chol_and_fbs_are_not_authorized_by_d047`, `::test_hungary_locked_route_is_not_authorized_by_d047`, `::test_historical_d047_five_field_scope_is_represented_accurately`, `::test_no_exported_status_is_an_unqualified_authorization`, `::test_route_operations_holds_and_timing_evidence_are_unchanged` |

Unchanged by that correction: schema id, crosswalk id, `EVIDENCE_ONLY_NOT_APPROVED`
status, baseline SHA, all four panel contracts and their `contract_sha256`, all
five route descriptors, every permitted/forbidden operation set, all nine
restrictions, all three blocked items, every hold, and all 30 timing records
(`0/16` UCI-412 basic, `0/7` UCI-412 labs, `0/7` UCI-45 owner-verified).
