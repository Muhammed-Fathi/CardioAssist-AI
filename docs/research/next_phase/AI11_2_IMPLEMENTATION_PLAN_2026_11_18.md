# AI-11.2 — Read-only research model catalog: implementation scope and acceptance plan

**Date:** 2026-11-18  
**Status:** PROPOSED / docs-only scope review — **AI-11.2 NOT_STARTED**.  
**Reviewed `main` baseline:** `443db7b59f97d566ab326839fa13cdd4677a7c42` (AI-11.1/#79, AI-12.1/#82 and documentation closeout/#83 merged).  
**Claim boundary:** SYNTHETIC-ONLY RESEARCH SOFTWARE. No patient use, no real-data permission, no clinical model serving or medical performance claim.

## 1. Source-first inventory: what is already implemented

| Existing component (verified on baseline) | Established behavior | Do **not** duplicate |
|---|---|---|
| `ai/research_registry.py` | Immutable `ResearchModelEntry`, cross-bound route/panel/version/hash metadata, `registry_contract()`, digest, entry-state reasons and artifact identity/capability checks | No second registry, artifact loader or route resolver |
| `ai/research_facade.py` | Typed offline request/response, version and panel checks, `SYNTHETIC_RESULT` / `ABSTAIN` / `UNAVAILABLE` / `ERROR`, refusal/redaction, authenticated local synthetic bundles | No new scoring, SHAP, LIME, calibration, or input validation engine |
| `ai/research_routes.py`, `ai/panels.py` | Source-specific route eligibility, panel field-order/units/missingness and SHA binding | No universal feature harmonization or inferred routing |
| `ai/research_evidence.py`, `docs/research/ai12_1/evidence-pack.v1.schema.json` | Actual **one** exercised Cleveland synthetic pack and versioned model card with measured provenance, limitations and schema validation | Do not invent equivalent evidence/model cards for other entries |
| `backend/app/inference/registry.py` | Application provider selection is hard-wired to `MOCK_SYNTHETIC` | No backend provider registration, `/v1` endpoint, DI switch or environment flag |
| `tests/experiments/test_research_facade.py`, `tests/backend/test_inference_provider.py` | Extensive existing immutable-registry, lifecycle, tamper, refusal, route/panel and mock-provider regression tests | Reuse rather than clone their test harness |

### Current source-bound model slots

The existing immutable registry has **five** entries; **two** are active for *strictly offline synthetic research*, not clinical serving:

| Registered model id | Route | Existing state | Interpretation for a consumer |
|---|---|---|---|
| `synth_ai7_da_a2_resting_v1` | `da_a2_resting_v1` | `ACTIVE_SYNTHETIC_OFFLINE` | Synthetic-only offline; AI-12.1 contains an actual published demo model card for this route |
| `synth_ai8_uci412_da_a1_basic_clinical` | `da_a1_basic_clinical_v1` | `ACTIVE_SYNTHETIC_OFFLINE` | Synthetic-only offline; **does not** resolve the real UCI-412 `SCIENTIFIC_HOLD`; no AI-12.1 Cleveland card can be reused as its evidence |
| `synth_ai7_da_a2_resting_labs_v1` | `da_a2_resting_labs_v1` | `BLOCKED_PENDING_AUTHORIZATION` | Contract-only, `UNAVAILABLE`, no score |
| `synth_ai7_da_a1_clinical_core_labs_v1` | `da_a1_clinical_core_labs_v1` | `BLOCKED_SOURCE_TIMING_UNVERIFIED` | Contract-only, `UNAVAILABLE`, no score |
| `synth_ai7_da_a2_hungary_locked_transportability_v1` | `da_a2_hungary_locked_transportability_v1` | `LOCKED_EXTERNAL_TARGET_NEVER_FACADE` | Locked external evaluation target; never a selectable or trainable serving model |

The states above must be verified against current source and tests on the actual future code-PR head before freezing any release fixture. Two active entries mean **offline synthetic eligibility only**, not authenticated availability of a model artifact for a caller, a license to load a real bundle, or validated CAD prediction.

## 2. Exact gap / scope decision

**Already exists:** a JSON-safe, path-free `registry_contract()` containing five entries, identity, governance, capabilities and state. An independent CLI/schema designed for a downstream **research handoff artifact** has not been found in the inspected AI-11.1/AI-12.1 implementation. The additional AI-11.2 value must be a **thin, reproducible, stable projection** of the existing registry, *not* a replacement for it.

**Propose one narrow synthetic-only code PR:**

1. **Read-only catalog projection.** New `ai/research_catalog.py` (or an equally small equivalent if a further repo audit finds a better location). Pure function `build_research_model_catalog()`; derive from `registry_contract()` and registered panel/route contracts, never from hand-authored model entries. Deterministic ordering and canonical hash of exported content. Do not mutate the source registry.
2. **Consumer contract.** New `docs/research/ai11_2/research-model-catalog.v1.schema.json` (JSON Schema 2020-12) and `README.md`. Version schema separately from registry. Include a machine-readable disclaimer that this is an **offline research description, not a serving registry**.
3. **Export CLI.** New `scripts/export_research_model_catalog.py`: `--format json` to stdout by default; optional `--output <NEW_PATH>` (exclusive create only, no overwrite). No inference, dataset access, model load, signing key, subprocess launch, network, environment-dependent provider selection or authentication work. Clear exit codes for invalid args/writes; no partial committed artifact. Do not introduce arbitrary user-supplied models, routes or plugin paths.
4. **Status/evidence separation.** Every exported entry must bind exact model+route+panel+target+protocol versions/hashes, ordered feature contract, allowed synthetic operations, missingness/abstention policy, registry-declared capability flags, entry state and reason, and explicit governance flags `real_data_execution_authorized=false`, `approved_for_serving=false`, `clinical_use_authorized=false`. An optional link to the **existing** published Cleveland synthetic card is informational; **do not** fabricate model-performance evidence or artifact hashes for the other slots. A registry-declared capability is not a proven verified-artifact capability; make this distinction explicit.
5. **Optional research-only handoff (not HTTP).** Document how an offline research consumer first reads the immutable catalog and then calls the **existing** `run_offline_research_inference_from_document()` only with a separately verified, approved-for-this-synthetic-fixture local source. Catalog output alone must **never** cause artifact loading or select a model automatically. No `backend/app/` changes needed.

### Proposed catalog envelope (illustrative, not yet implemented)

```json
{
  "schema_version": "cardioassist.ai.research_model_catalog/v1",
  "catalog_version": "1.0.0",
  "source_registry_schema_version": "cardioassist.ai.research_registry/v1",
  "source_registry_digest_sha256": "<64-hex-from-live-registry>",
  "research_only": true,
  "real_data_execution_authorized": false,
  "approved_for_serving": false,
  "clinical_use_authorized": false,
  "entries": ["<five-mapped-read-only-descriptors>"],
  "catalog_sha256": "<canonical-content-checksum-not-a-signature>"
}
```

Schema and serialisation rules are review requirements, **not immutable final choices**. Resolve the exact key names before writing tests; never hard-code placeholder hashes. The hash is a checksum, not trust/authenticity or an entitlement to deserialise an artifact.

## 3. Required non-negotiable negative controls

- Registry entry count/id/order and active-vs-blocked states agree with actual `RESEARCH_MODEL_REGISTRY`; no entry is silently filtered or promoted.
- A forged or mutated catalog projection is **never** interpreted as a new registry or as an authorization; the facade must still resolve its immutable internal registry and reject unknown/version-mismatched entries.
- Route/panel/model/protocol/hash mismatch is refused by existing binding checks; avoid introducing a second permissive copy of validation rules.
- Blocked labs and locked Hungary entries are described as unavailable and cannot trigger training, inference, upload, external evaluation or fallback.
- Demonstrate that no artifact, joblib/pickle, real bundle, source dataset, environment secret, user local path, HMAC key, record value, or file-system address is loaded or emitted during catalog-only export. Exercise malformed option/path, existing output file, and stdout behavior.
- Statuses cannot be misleadingly renamed `READY`, `PRODUCTION`, `PATIENT_APPROVED`, or `CALIBRATED_FOR_PATIENTS`; registry capability is only a declaration, not live verified model evidence.
- The FastAPI active-provider allowlist remains exactly `MOCK_SYNTHETIC`; no backend/runtime importing the catalog for provider selection. `/v1` OpenAPI, fixtures, idempotency, diagnostic registry and mock responses remain unchanged.
- Existing fail-closed HMAC/trusted-root/ACL checks remain upstream of any actual artifact deserialization; catalog access alone never authorizes loading.
- No changes to `AGENTS.md`, `docs/DECISIONS.md`, protected source manifests, frozen protocols, `research/uci412/**`, Gate PT decisions or locked Hungary evidence.

## 4. Proposed code-PR file boundary and test plan

| File | Expected change |
|---|---|
| `ai/research_catalog.py` | Pure deterministic read-only projection; smallest possible adapter of existing registry/route/panel metadata |
| `scripts/export_research_model_catalog.py` | No-side-effect stdout/export CLI; exclusive output semantics |
| `docs/research/ai11_2/research-model-catalog.v1.schema.json` | Versioned consumer JSON schema; structural and safety constraints |
| `docs/research/ai11_2/README.md` | Research handoff, explanation of each entry, null/blocked evidence, example and Windows instructions |
| `tests/experiments/test_research_catalog.py` | Deterministic bytes, hashes, immutability/source agreement, five statuses, zero private/artifact I/O, invalid inputs and malicious promotion rejection |
| `tests/contracts/test_research_catalog_schema.py` | Valid example and schema-negative tests without depending on a live medical/AI stack |
| Existing backend and facade tests | Re-run unchanged; only edit on demonstrated regression with review |

**Reassess the implementation:** if inspection on the implementation branch proves the existing `registry_contract()` plus a schema and a thin CLI fully satisfy the handoff, drop the new Python module instead of building an unnecessary layer. No new train/score or signing logic under any interpretation.

### Pre-merge acceptance (Linux + Windows)

1. Exact pinned code-PR SHA + clean worktree; `pip check`, `python scripts/verify_sources.py` and `git diff --check`.
2. Focused: `python -m pytest -W error -q -ra --tb=short tests/experiments/test_research_catalog.py tests/contracts/test_research_catalog_schema.py tests/experiments/test_research_facade.py tests/backend/test_inference_provider.py` (adjust only if module paths are actually different; report exact collected/pass/skip/fail counts).
3. Applicable regression: `python -m pytest -W error -q -ra --tb=short` with true exit code, counts, warnings, and runtime; never infer full-suite pass from two segmented runs.
4. `python scripts/validate_ai_windows_compat.py` on **native** Windows NTFS: 8/8 or document actual result; no ACL bypass/exclusions.
5. Export catalog twice to different **new external** files; compare byte-for-byte with SHA-256 on same machine; validate against schema; assert all five entries and three refusals; verify the repo remains clean. Cross-OS bitwise equality is **not** a required claim without demonstrated reproducibility.
6. `python -W error -m ai.research_demo --format json`: 8/8; `python -W error -m ai.research_evidence --output <new-external-pack>` and `--compare <pack>` behavior stays in expected scope. Real-data runs are prohibited.
7. Four applicable hosted GitHub workflows independently green at exact PR head, and actual Windows local results recorded **before** merge. After human merge, do focused post-merge check at exact merge SHA, then a separate docs-only tracker update.

**Windows PowerShell 5.1:** use a clean **detached** worktree and the maintainer's existing external Python 3.12 environment; avoid reusing or altering the main checkout, locked data or unrelated project's environment. Set and verify `$WT`, `$Python`, `$Out`, and exact `$Sha` prior to any command; route all generated files exclusively into a new `$Out` folder. Never set execution-policy bypass to run unreviewed scripts or disable Windows Defender.

**Do not assume test counts:** previous AI-12.1 source-head Windows full suite was 2,531 passed, 3 skipped at source `75c6ab4...`; it is historical baseline evidence, not the acceptance result of a future AI-11.2 code PR.

## 5. Decision gates and handoff

- **Code PR is not authorized to merge itself.** First review this proposed scope and check whether any existing exporter already satisfies it, then open a separate implementation PR.
- **Engineering done:** immutable source-derived read-only catalog, versioned schema, CLI, accurate statuses, no private/artifact reads, negative controls, mock-only FastAPI boundary, Linux CI and native Windows post-merge acceptance.
- **Scientific/clinical still held:** `UCI-412 SCIENTIFIC_HOLD`, D-048 not newly authorized, Hungary locked, Gate PT P-3 CLOSED, independent external validation absent. No new model training, score calibration, clinical performance, patient data or live endpoint enabled.
- **Next executable step:** create reviewed **AI-11.2 CODE PR** scoped to this thin read-only handoff, with implementation/negative tests. Do not mark AI-11.2 complete in `ai_master_progress.json` until the code PR has merged and the maintainer's exact-merge native Windows tests have passed.
