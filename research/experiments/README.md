# D-047 / M2c — Guarded Local CAD Experiment Runner

**Implementation state:** M2c runner code and synthetic tests are prepared for human review. The verified authorization comment on PR #31 authorizes this bounded engineering implementation; it is **not** authorization to run actual data in Arena, CI, a remote environment, or before a completed local D-047 manifest. Gate PT P-3 remains **CLOSED**.

**No real Cleveland data were downloaded, opened, parsed, fitted, evaluated, or uploaded by this implementation.** The dry-run uses generated rows in memory. The positive integration test creates source-shaped synthetic bytes, explicitly fake D-046/D-047 manifests, placeholder license text, and reports only inside an isolated temporary Git repository. Its outputs are labeled synthetic test fixtures, not UCI data or research results. No performance numbers in synthetic tests are medical or Cleveland benchmark results.

## Scope and safety boundary

- Only `data/raw/uci-45/processed.cleveland.data` (UCI-45 / DA-A2) is supported. The adapter checks the exact headerless 14-column order recorded in `research/audit/registry.py`, accepts only `?` as a missing token, maps `num=0` to 0 and `num=1..4` to 1, and exposes only `age, sex, cp, trestbps, restecg` to models.
- `num` is target-only. `ca`, `thal`, angiography/vessel/catheterization fields, IDs, site fields, wearable/monitoring inputs, extra columns, raw 76-column rows, and alternate cohorts are excluded or rejected.
- Real-data commands fail closed unless run interactively on a local fixed Windows drive, outside CI/hosted notebooks/Arena, with a clean committed worktree, Git-ignored `/data/`, a valid D-046 read-only DA-A2 authorization/provenance/license chain, matching source hashes/byte size, and a completed separate D-047 local manifest bound to PR #31, the frozen protocol, the registered plan, the exact source hash, and the allowlisted operations.
- The checked-in authorization JSON is a **template only**. D-046 read-only audit permission does not authorize fitting. The runner never edits or downloads the source file and re-hashes it after parsing/fitting. Parser errors do not echo input cell contents.
- Real run reports and row-aligned OOF predictions are written only under a unique `data/experiments/run-.../` directory. `/data/` is Git-ignored; preflight rejects tracked or unignored paths and symlinks/junctions. No full-cohort model artifact is produced or saved by this runner.
- Real reports carry exactly `INTERNAL_EXPLORATORY_NOT_SUPERVISOR_APPROVED`. They explicitly deny external validation, supervisor approval, patient-care use, and clinical-performance claims.
- `research/intake/` remains synthetic-only and is not used for real rows. There is no `synthetic=true` bypass.

## Governance records and registered method

- [D-047 proposed protocol](../../docs/research/gate-pt/02_d047_internal_exploratory_cleveland_PROTOCOL_PROPOSED.md) and [decision record](../../docs/DECISIONS.md) define the exploratory scope; neither implies supervisor approval.
- The committed [registered plan](cleveland_d047_exploratory_plan.v0.1.json) is validated against a narrow in-code allowlist; CLI options cannot change or expand the model grids.
- The [local authorization template](internal_exploratory_authorization.template.json) is deliberately non-authorizing. The separate [report template](../../docs/research/gate-pt/03_internal_exploratory_RESULTS_TEMPLATE.md) is not a result.

### Registered method

- **Baseline:** `DummyClassifier(strategy="prior")`, fit to each outer-training fold only.
- **L2 logistic regression:** `liblinear`, `C={0.1, 1, 10}`, `max_iter=2000`, no class weighting.
- **Constrained random forest:** 200 trees, `max_depth={3, 5}`, `min_samples_leaf={5, 10}`, `max_features="sqrt"`, no class weighting.
- **Evaluation:** repeated nested stratified CV with outer 5-fold CV, inner 5-fold CV, four outer seeds `20261023`–`20261026`. Every outer-training partition performs inner-CV hyperparameter selection for both families. If the best LR inner AUROC is within 0.01 of the best RF AUROC, LR is selected by the prespecified simplicity rule. Each outer assessment fold is evaluated once; per-family scores are supportive, the inner-selected procedure is primary.
- **Preprocessing:** every estimator is a sklearn `Pipeline`. Numeric median imputation and LR standardization, plus categorical most-frequent imputation and fixed-reference one-hot encoding, are fitted within each inner-training fold. The winning family is refit on the outer-training partition only. All-missing training-fold fields fail closed.
- **Determinism:** fixed outer and label-shuffle seeds, versioned inner/model seed derivation, `n_jobs=1`, and single-threaded numerical libraries.
- **Metrics:** AUROC, average precision/AUPRC, accuracy, sensitivity, specificity, confusion matrix, Brier score, calibration-in-the-large, descriptive calibration slope/intercept, and a quantile reliability curve when estimable. The only classification threshold is the fixed exploratory 0.50 cutoff; it is never tuned on outer predictions.
- **Negative control:** three label-shuffle nested-CV smoke tests (`20262001`–`20262003`), reported as a small descriptive null distribution—not a permutation p-value.
- **Repeated-CV interpretation:** each repeat gives one outer-fold prediction per source row. The four repeats reuse the same people; report per-repeat metrics and descriptive mean/SD only. No pooled `4 × n` inference or naive confidence interval is generated.

The report marks the Riley-style sample-size sensitivity analysis as **not assessed** because no human-reviewed anticipated Cox–Snell R-squared assumptions are supplied. It therefore permits only a software/research feasibility interpretation; no clinical predictive adequacy is claimed. A later supervisor-facing report still needs human TRIPOD+AI / PROBAST+AI review.

## Windows PowerShell setup and synthetic dry-run

From the repository root (for example, `E:\CardioAssist_AI_GitHub_Starter`):

```powershell
Set-Location E:\CardioAssist_AI_GitHub_Starter
py -3.12 -m venv .venv-experiments
.\.venv-experiments\Scripts\Activate.ps1
python -m pip install -r research/experiments/requirements.txt
python -m pip check
python -m pytest tests/experiments -q -W error
python -m research.experiments dry-run
```

`dry-run` creates a deterministic, 303-row **synthetic software fixture in memory**, executes the registered nested-CV/model-selection/metric/label-shuffle wiring, prints only a PASS marker and test-scope facts, does not access a dataset path, and writes no report, prediction, or model file. Its output is labelled `SYNTHETIC_SOFTWARE_FIXTURE_ONLY_NOT_A_RESEARCH_RESULT`.

## Windows-local synthetic positive-path smoke test

Before any authorized real-data experiment, run this on the maintainer's **interactive PowerShell console**, from a repository on a local fixed Windows drive, outside Arena/CI/remote or synced folders. The first command exercises the actual Windows console, environment, path, reparse-point, and fixed-drive runtime guard without opening `data/`. The test then creates a temporary Git repository containing only generated source-shaped bytes and clearly fake D-046/D-047/provenance/license fixtures, and runs the full guarded orchestration, nested CV, report/prediction writer, and hash/preservation assertions there. It does not use or create the real checkout's `data/` files.

```powershell
python -c "import sys; from pathlib import Path; from research.experiments.safety import enforce_local_windows_runtime; assert sys.stdin.isatty(), 'Use an interactive local PowerShell console'; enforce_local_windows_runtime(repo_root=Path.cwd()); print('PASS: local Windows runtime guard')"
python -m pytest tests/experiments/test_authorized_local_integration.py -q -W error
```

The integration test uses a test-only Win32-drive stub on POSIX. On Windows it calls the production runtime guard with the actual environment and drive checks; it bypasses only pytest's captured-stdin check because the standalone console probe above checks that requirement. It uses the production protected `write_real_run_outputs` writer with an explicitly synthetic report body; it deliberately does **not** send generated rows through `build_real_experiment_report`, whose source attribution is for real UCI data. That real-source report composition remains unverified until a genuinely authorized local run. A successful Linux/Arena test is **not** evidence that Windows drive, console, reparse-point, or NTFS ACL behavior passed. If the Windows console probe or synthetic integration test fails, stop; do not proceed to real-data preflight or fitting.

## Local preflight (does not parse source rows or fit)

This must be run only on the maintainer's local Windows computer after the separate local authorization files and protected source provenance exist:

```powershell
python -m research.audit verify-ignore
python -m research.experiments preflight
```

Preflight checks runtime, clean code commit, D-046 read-only DA-A2 authorization, D-047 human authorization, frozen protocol/plan hashes, license snapshot, exact source path, Git-ignore protections, source SHA-256 and byte size. It hashes the source but does **not** parse its CSV rows or fit any model. Missing/mismatched values stop execution.

## Windows data-root ACL prerequisite (human-verified; not automated)

The runner's `chmod` calls are best-effort on Windows and do **not** verify effective NTFS ACLs. Before placing source data or running a real fit, the maintainer must secure the local `data` root and verify that only the authorized Windows user and required system administrators can read its contents. Keep the repository off UNC/network drives and out of OneDrive, SharePoint, Dropbox, or other sync/backup locations. If data already exists, have the data custodian review and secure every existing child ACL; do not blindly overwrite ACLs or alter original source bytes.

For a new, empty local `data` directory, a maintainer may use this reviewed PowerShell pattern (it changes ACLs; verify the resolved path first and stop if it is not the intended local repository):

```powershell
$dataRoot = (New-Item -ItemType Directory -Force .\data).FullName
if (Get-ChildItem -LiteralPath $dataRoot -Force | Select-Object -First 1) {
  throw "data is not empty; do not apply the empty-root example to existing data"
}
$currentSid = [System.Security.Principal.WindowsIdentity]::GetCurrent().User.Value
$currentAce = "*$($currentSid):(OI)(CI)F"

icacls $dataRoot /inheritance:r
if ($LASTEXITCODE -ne 0) { throw "Could not disable inherited data-root ACLs" }
icacls $dataRoot /grant:r $currentAce '*S-1-5-18:(OI)(CI)F' '*S-1-5-32-544:(OI)(CI)F'
if ($LASTEXITCODE -ne 0) { throw "Could not apply the restrictive data-root ACL" }
icacls $dataRoot /verify
icacls $dataRoot
(Get-Acl -LiteralPath $dataRoot).Access |
  Select-Object IdentityReference, FileSystemRights, AccessControlType, IsInherited |
  Format-Table -AutoSize
```

Review the output locally; expect only the current user, `SYSTEM`, `Administrators`, and any separately approved institutional account. No broad `Users`, `Everyone`, or `Authenticated Users` access should remain. The command is a setup aid, **not proof** of effective access on descendants or managed endpoints. Verify the output/run directories inherit the intended ACL before writing any sensitive prediction file. The test suite, Linux checks, and this agent cannot verify Windows ACLs; record the human check and stop if uncertain.

## Human-operated local authorization (never generated or signed by the agent)

Prerequisites: the maintainer has completed the separately authorized local DA-A2 acquisition/audit steps and has the protected local `data/manifests/gate_da_authorization.local.json`, `data/manifests/provenance_manifest.json`, license snapshot, and exact processed Cleveland original. Do not download another copy as part of this M2c handoff. If any prerequisite is absent, stop.

After review/merge of the M2c code and confirmation that PR #31 remains the authorizing governance record, copy the blank template and inspect the local-only hashes:

```powershell
New-Item -ItemType Directory -Force .\data\manifests | Out-Null
Copy-Item .\research\experiments\internal_exploratory_authorization.template.json `
  .\data\manifests\internal_exploratory_authorization.local.json
Get-FileHash .\data\raw\uci-45\processed.cleveland.data -Algorithm SHA256
Get-FileHash .\docs\research\gate-pt\02_d047_internal_exploratory_cleveland_PROTOCOL_PROPOSED.md -Algorithm SHA256
Get-FileHash .\research\experiments\cleveland_d047_exploratory_plan.v0.1.json -Algorithm SHA256
notepad .\data\manifests\internal_exploratory_authorization.local.json
```

The maintainer must complete the manifest **locally and never commit/share it**. In particular, fill the exact comment `AUTHORIZE-D047-INTERNAL-CLEVELAND`, PR number `31`, merged/pinned protocol commit `434e49a37e6e60b8b91498dde0f9d02dc1af18de`, local signer `Muhammed Fathi`/date/required attestation, the full source SHA-256 from protected provenance, and the frozen protocol and plan SHA-256 values. Keep all allowlists/forbidden operations exactly as in the template. The runner validates the local human-attestation fields and hash bindings; the manifest's signature semantics are explicitly **not cryptographic**. If institutional policy requires a cryptographic signature, do not run until a reviewed signature-verification mechanism is added.

The exact authorization values do not waive formal Gate PT P-3. No supervisor signoff is asserted.

### Windows-only checks required before a real-data experiment

1. From interactive local PowerShell, pass the standalone `enforce_local_windows_runtime` console probe above. This checks actual Windows, TTY, CI/Arena/remote environment flags, local fixed-drive type, and repository path/reparse restrictions without opening source rows.
2. Pass `test_authorized_local_integration.py` using only its generated temporary fixtures; this exercises the complete guarded path and outputs without claiming Windows ACL verification.
3. Verify the repository and `/data/` are on a local fixed drive and not in a network, remote, or sync-managed location. Secure the effective NTFS ACLs for the data root **and descendants** and keep evidence local; the runner does not validate those ACLs.
4. Complete the real D-046 read-only authorization/provenance/license chain and a separately human-signed, hash-bound D-047 manifest for the exact source, protocol, and plan. The synthetic test manifests are never reused.
5. Run `python -m research.experiments preflight` successfully from the local console. It must verify all gates and source byte hash/size before parsing rows; any mismatch means stop.
6. Only then, with the data custodian present, run `python -m research.experiments run` and type the exact confirmation phrase. Gate PT P-3 remains closed; this does not authorize clinical use or supervisor approval.

## Eventual local run

Only after a successful local preflight, with the data custodian operating an interactive local Windows PowerShell console:

```powershell
python -m research.experiments preflight
python -m research.experiments run
```

The `run` command requires typing `RUN D047 CLEVELAND LOCALLY`. It creates a unique protected ignored output directory containing an aggregate `report.json` and row-aligned `predictions.csv`; the latter contains local source-row order, labels and OOF probabilities and must never be committed, uploaded, pasted into GitHub, or copied to a remote service. No final full-cohort model artifact is saved. Preserve NTFS access controls on the repository's `data` directory and keep the computer local/offline during fitting.

## Testing and status

- **IMPLEMENTED:** strict source adapter; distinct D-046/D-047 authorization checks; Windows/CI/remote-drive/interactive guards; Git-ignore and output protections; deterministic nested model selection/evaluation; label-shuffle smoke test; aggregate-only report builder; protected local predictions output; Windows setup/preflight/run handoff; a synthetic-only workflow **template** at `research/experiments/ci/experiment-runner-ci.yml.example`.
- **TESTED:** synthetic source-schema/target parsing; `?` handling; leakage rejection; no-row preflight; local runtime/auth/provenance/hash validation using explicitly fake test profiles; a positive synthetic `run_authorized_local_experiment` path in an isolated temporary Git repository; source-byte preservation; actual nested CV and label shuffles; aggregate synthetic report vs row-level prediction separation; mutated source/protocol/plan/authorization bindings and dirty-worktree fail-closed regressions; output-ignore/mode/hash checks.
- **PROPOSED / NOT AUTHORIZED:** any actual real-data execution, final model fit for reuse, deployment, clinical decision, supervisor-approved formal study, external validation, clinical performance claim, or publication claim.
- **UNVERIFIED / NOT ACTIVE:** dedicated GitHub CI for this ML runner is **not active**; the workflow is only a template outside `.github/workflows/`. Existing contract, backend, or audit CI does not prove the runner passed dedicated CI. Windows-specific GetDriveTypeW/console/reparse-point behavior and effective NTFS ACLs require the documented local Windows checks; Linux test shims do not verify those. Also unverified: the production `build_real_experiment_report` composition with a genuine authorized local source (synthetic bytes are never mislabeled as UCI); actual human local manifest values, local source/provenance files, actual source structure/hash, any real-data model result, Riley-style sample-size assumptions, and supervisor/clinician review.
