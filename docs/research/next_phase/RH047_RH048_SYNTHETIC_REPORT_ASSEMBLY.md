# RH-04.7 / RH-04.8 — synthetic research evidence report assembly

**Status:** implementation PR for review; no clinical/scientific approval or completed RH-05/RH-07/RH-08 acceptance claimed.

This is a *narrow composition* of existing approved components. It does not add a
predictor, training route, evaluation engine, ledger, Flask/FastAPI API, model
weights, dataset, new JSON input panel, score threshold or user-facing service.

## What runs

`research.report_assembly` reuses these exact existing entry points:

| Evidence | Implementation reused | New assembly responsibility |
|---|---|---|
| AI-12.1 | `ai.research_evidence.build_evidence_pack` and `ai.report_comparison.report_bytes` | Bind 8-stage completed synthetic proof and model-card/evidence-pack SHA, *without exporting predictions or training rows* |
| RH-04.3/4 | `research.intake.offline_fixture_pack.validate` | **Actually replay** the registered 29 cases, then index all five routes and four statuses with case-level projection and structure SHA-256 |
| RH-04.5/6 | `research.intake.offline_demo_card_mapping.validate/load_mapping` | Refuse stale mapping, fixture, registry, crosswalk or mock-contract hashes; keep the static mock separate |
| AI-10.1 | `ai.ai10_synthetic_transport.run_ai10_synthetic_locked_site` and `ai.training.ExternalEvaluationLedger` | Run *one genuine fabricated* assessment, read protected COMPLETED receipt, test duplicate consumption and wrong plan rejection, identity overlap and insufficient-cohort refusal |
| Source provenance | Existing AI-12.1 reproducibility collector | Carry Git commit, Python/OS/architecture, installed numeric dependency versions |

The assembled report is JSON schema ID
`cardioassist.rh04.synthetic_research_report/v1`.
The full closed consumer schema is `research/schemas/rh04_synthetic_report.v1.schema.json`; its exact byte SHA-256 and ID are included in `source_bindings`. The Python validator additionally checks live reviewed fixture/card sources and source HEAD. It has `report_sha256` calculated over all other canonical fields using the
existing research-facade canonical digest. There are **no timestamps or random
ledger reservation IDs in the report**. All source hashes remain exact SHA
comparisons; no byte-equivalence claim is made across different OS/library
builds. The manifest's deterministic same-environment digest is a checksum,
**not a signature or independent authentication of a historical run**.

### Native run: Bash / PowerShell

Use Python 3.12 with the existing repo's pinned research requirements, in a
normal checkout at the commit under review. Create a NEW output location
**outside the repository** and do not reuse a previous one-shot ledger.

```powershell
# Execute from the CardioAssist-AI repository root, in its configured venv.
python -W error -m research.report_assembly --ledger "$env:TEMP\cai-rh04-ledger-new.json" --output "$env:TEMP\cai-rh04-report-new.json"
python -W error -m research.report_assembly --validate "$env:TEMP\cai-rh04-report-new.json"
python -m pytest -q -W error tests/experiments/test_rh04_report_assembly.py
python -m pytest -q -W error tests/experiments/test_research_evidence.py tests/experiments/test_ai10_synthetic_transport.py tests/experiments/test_offline_fixture_pack.py tests/experiments/test_offline_demo_card_mapping.py
python scripts/verify_sources.py
git diff --check
```

The filenames ending `-new.json` are **examples**: if those files already
exist, pick different new filenames. Both generated files remain local,
outside Git; do not upload the ledger, protected artifacts, experiment inputs
or key material. Run again with **new** filenames: the ledger is intentionally
single-use and a completed ledger cannot be reused as a fresh training cohort.
The aggregate report and a validated hash can be shared after privacy review.

### Consumer contract and provenance

A consumer first calls `--validate`, which checks the report SHA, current
Git `HEAD`, known source/fixture/mapping integrity and the exact approved
29-case ordering and safe statuses. This *does not rerun model fits* or
authenticate the saved report as a trusted producer signature. To establish
execution evidence, reproduce the generation on an independently controlled
machine and retain the external protected ledger for local audit.

Report top-level fields:

- `schema_version`, `status`, `evidence_grade`, `report_sha256`;
- `source_commit`, `environment`, `dependencies`, `source_bindings` (including the exact report schema ID/hash);
- `ai12_evidence`: existing pack SHA and 8-stage demo digest, no input/output scores;
- `facade`: five registered routes, three unavailable ones, 29 fixture IDs
  with exact expected projection and structural digests, four facade statuses;
- `ai10_ledger`: report/plan SHA, protected ledger COMPLETED state and
  summary SHA, actual replay/plan/overlap/insufficient refusal results;
- `mock_backend`: only `MOCK_SYNTHETIC_SEPARATE_STATIC_CONTRACT_ONLY`;
- `real_studies`: AI-9.2 and AI-10.2 both explicitly `NOT_PERFORMED`;
- fixed limitations and no unauthorized patient identifiers, raw submitted
  feature values, unredacted explanation or prediction, keys, ledger path or
  private file location.

**Known scientific/operational limits:** numeric synthetic ML values can vary
slightly across OS/BLAS environments (the existing AI-12.1 comparator controls
that separately). The existing 29-case offline replay remains an exact expected
projection check, so any platform-dependent failure must be diagnosed against
the frozen fixture and its security/semantic invariants — never papered over by
rewriting golden values. Neither a fabricated "site shift" nor a ledger entry
proves actual participant independence, transportability or external AUROC.

The report does **not** perform or authorize AI-9.2, AI-10.2, D-048, a real
Hungary assessment, SHAP/LIME for a real patient, a real CAD provider,
institutional/clinical sign-off or a future clinical probability interface.

## Acceptance work remaining after this PR

- Run the new tests, existing 29-case pack/AI-12.1/AI-10.1 suites,
  backend/contracts boundary suites, source verifier and `git diff --check`,
  and record *observed* counts at exact reviewed head.
- Independent consumer/model-card review, real Windows NTFS 8/8 at the final
  release SHA and cross-OS semantic-versus-byte comparison belong to **RH-05**.
- Manuscript reconciliation, 19 independently unverified RH-03 claims and
  10 pending reviewer actions belong to **RH-03 / RH-07**.
- Final 15-point evidence-led acceptance, model cards, report/manuscript
  release bundle and freeze belong to **RH-07 / RH-08**.
