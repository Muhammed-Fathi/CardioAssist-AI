# AI-12.1 · Reproduce the offline CAD research demo

**Evidence status: `SYNTHETIC_E2E_COMPLETE` (software only).** No patient data, clinical performance measurement, human signature, new real-data permission, model serving or `/v1` change. The runtime backend remains `MOCK_SYNTHETIC` only. The frozen real Cleveland bundle, UCI-412 scientific hold, locked external cohort and Gate PT are not exercised or modified.

## Run it

From the repository root, with Git and Python 3.11/3.12 with venv/pip installed:

```sh
python scripts/run_research_evidence.py --output synthetic-pack.json
```

On Windows you can use `py -3.12` in place of `python`. The bootstrap uses a temporary external venv, installs `research/uci412/requirements.txt`, checks the install, runs the demo, then removes the venv. Only package installation requires network access. $0, local CPU/disk; no API key, GPU, account or data download. Use a **new** output filename (an absolute path outside the checkout to keep Git clean). Never point any command here at a patient file or a private bundle.

In an existing pinned research environment:

```sh
python -W error -m ai.research_evidence --output synthetic-pack.json
python -W error -m ai.research_evidence --compare synthetic-pack.json
```

No arguments prints the entire pack as JSON. `--no-lime` explicitly reports `provided: false`, `reason: not_requested_by_caller`, and null LIME quality, not a fictitious explanation. `--output` never overwrites a file. Neither the generator nor the comparator accepts custom inference inputs. The private automatic workspace (bundle, tamper-test copy and ephemeral HMAC keys) is removed before the evidence is published.

## What is in the pack?

[Current generated Linux pack](linux-uci45-envelope.v1.json) · [JSON Schema 2020-12](evidence-pack.v1.schema.json) · [Original Linux pack](linux-example.v1.json) and its [measured field-level BLAS comparison](linux-blas-comparison.v1.json) (historical; unchanged).

| JSON member | What to inspect |
|---|---|
| `model_card` | Independently versioned JSON card. Dataset **contract** versus actual fabricated cohort/label provenance, seed and hash; explicit registry selection, model family/version/serialized-model hash; route/panel versions and hashes, ordered five-field contract, protocol ID/config/hash, declared capabilities, interpretation, refusals and limitations. |
| `report` | Original AI-11.1 v1 eight-stage report. Registry → fabricated cohort → nested-CV selection and signed bundle → successful facade call → abstention → blocked contracts → errors → repeat and redaction checks. No second trainer, calibrator, router, predictor or explainer. |
| `inference` | **Exact preimage** of `report.stage_results[7].detail.canonical_payload_sha256`: the existing facade's redacted v1 response to the two fixed synthetic inputs. Full-precision raw and calibrated scores, scale/additivity and background size for SHAP, LIME perturbations/seed, fidelity, holdout fit, stability and quality verdicts, and the verified bundle member hashes. Not input rows, background values or model weights. |
| `reproducibility` | Actual Git commit and `ai`/`research` tree IDs, whether those source trees were clean, pinned requirements path, installed numerical/runtime dependency versions, Python, OS/architecture and selected BLAS/OpenMP metadata. No hostname, environment dump, credentials or local library paths. |
| `pack_sha256` | SHA-256 of compact, key-sorted, ASCII-escaped JSON of all other members. Like the records+labels and training-config hashes, this is a reproducibility checksum, **not** a signature or a loading entitlement. Only the existing trusted-root/HMAC verifier authorizes deserialization during the fixed synthetic run. |

The example records the clean **implementation** commit. The subsequent evidence/example commit necessarily has another Git SHA; compare the two source tree IDs, too. Hashes of `.joblib` and other members come from **actual authenticated bundle contents**, not filenames. Random keys, key IDs, time-stamped manifests and training derivatives are not published.

### Observed Linux result, not a reference prediction to hardcode

`da_a2_resting_v1`, `synth_ai7_da_a2_resting_v1@0.1.0`: 96 rows from the seeded generator (`20261117`); bounded nested CV selected L2 logistic regression. The two inference examples are from the *development fixture*, not an independent test. For its first row:

| Observation | Result |
|---|---|
| Raw positive-class model output | `0.7584707634896621` |
| Development-OOF logistic-calibrated synthetic score | `0.7584072878055222` (not an estimate of individual CAD risk) |
| Exact interventional linear SHAP | `calibrated_log_odds`; additivity check passed, 24 synthetic background samples; **not** additive in calibrated probability |
| LIME | `calibrated_log_odds`; `ACCEPTABLE_LOCAL_APPROXIMATION`, local absolute error `0.0035001607179419025`, held-out neighborhood weighted R² `0.9958103340068923` (surrogate fidelity, **not CAD accuracy**) |
| `ABSTAIN` | Optional `trestbps` missing with reason `not_provided` → `registry_abstain_policy_optional_field_missing` |
| `UNAVAILABLE` | Resting+labs route → `model_entry_blocked_pending_authorization` |
| `ERROR` | Incompatible unit → `unit_mismatch`; tampered artifact → `file_size_mismatch`; foreign key → `untrusted_bundle_producer_signature` |

8/8 stages; **1 abstention, 3 unavailable and 38 error cases**, none with a score. The target contract is historical cross-sectional angiographic CAD presence, not a future event. A synthetic OOF calibrator does not validate a population probability; neither XAI method establishes causality.

### Why the synthetic facade refuses an extreme finite input

The UCI-45 source contract requires finite, positive measurements; it does **not** specify medical upper limits. A declared `age=10**12` therefore passed panel validation. In [the failing Python 3.12 CI job](https://github.com/Muhammed-Fathi/CardioAssist-AI/actions/runs/44252990449/job/134627918359), it was scored. A passing test on another runtime was not proof of rejection at intake: a later SHAP sum check could fail instead. On pinned Linux 3.11.18 and 3.12.16, changing numerical kernels reproduced both outcomes for the same input and model family. SHAP checks agreement between model and explanation, not input admissibility.

Only the offline `da_a2_resting_v1` facade entry applies the extra check. Its sole admitted generator draws `age` in **40–79** and `trestbps` in **90–199** (inclusive). The generator and facade share those existing draw endpoints. After validating the panel, but **before prediction**, a present measurement outside that envelope yields `ERROR` / `outside_synthetic_fixture_envelope`, with no score or explanation. Missing optional fields retain their existing policy. This is an envelope check, not seed replay or a claim that every in-range value was generated. The endpoints describe fabricated numbers, **not patient eligibility or normal values**. Nothing is clipped; no source schema, clinical rule, estimator, SHAP tolerance, or real-data permission changed.

`--compare` uses the separately generated current Linux pack because the `ai` source tree changed. Comparing the historical and current full packs directly must report `DIFFERENT` for that tree; it is not an allowed roundoff difference. The archived files have not been rewritten and the comparison rules are unchanged.

## Why do the Windows and Linux digests differ?

[PR #79 native-Windows record](https://github.com/Muhammed-Fathi/CardioAssist-AI/pull/79#issuecomment-6969302514) reports `d8e6f5d95ac5b1c01a1f5abddc2cca6b4db0fc8d1dd603c5e8194d735c86309e` on Python 3.12.9. We reproduced the original Linux digest `0722d728f756e589a3d97b4328e6dc106111835889e6b6387969cf0b0b99b853` on Python 3.11.2. The PR #79 head and merge have identical file trees. **The Windows record gives the summary and digest, not the original stage JSON or the stage-8 response.** The only directly observed unequal historical field is `/deterministic_sha256`. A digest cannot identify which input leaves changed. Do not state that only SHAP, rounding, BLAS or the OS caused that specific pair.

The v1 digest covers `stage_results`, `evidence_level` and `registry_digest_sha256`. It is not a file SHA: stdout indentation, CRLF, a PowerShell BOM and the `runpy` warning on stderr cannot explain a different **internal** digest. Stage 4 already rounds four displayed numbers to six places. **Stage 8 additionally commits to the entire unrounded facade response**, including the hashes of serialized model, calibration and evaluation artifacts. Matching four displayed numbers is not sufficient.

**Controlled differential, actually executed:** on the same Linux interpreter, pins, code and fixtures, changed only OpenBLAS CPU kernel selection (`SkylakeX` → `OPENBLAS_CORETYPE=Haswell`). The latter legacy digest was `79cb09ca20d792bd5e8743010e7524cf4555523302d5e68898e0b4d3cc5eff65`. Exactly two fields in the legacy report differed:

* `/stage_results/7/detail/canonical_payload_sha256`: `9e513ff7daaa522a8aaf5195f6f0277718166bdde85dcdc7d6a96a312d2cdbac` → `77037acbea55aa0cfbe6f37786177dda8cfd317b1114623b757b02bf910209e1`;
* `/deterministic_sha256`, as above. All stage-4 displayed scores and refusal codes matched.

In the expanded response, **51 continuous measurements** differed within the declared tolerance, including `/inference/records/0/lime_explanation/explanation/attributions/0/lime_weight` (`0.28139749234027` vs `0.2813974923402707`); the verified hashes for `calibration.json`, `evaluation_summary.json` and `model.joblib` also differed. See the linked JSON for *every* path and numerical delta. This establishes a mechanism, **not a reconstructed or simulated Windows result**. No CPU kernel is forced by the demo.

### How to obtain the exact historical field diff

`python -m ai.research_evidence --compare WINDOWS.json` compares an **archived AI-11.1 report or new evidence pack** to the shipped, checksum-checked Linux reference. JSON only: it does not train, load a model, follow filenames in either document or use peer-supplied tolerances. For a legacy peer the reference file bytes are the nested Linux v1 report serialized in the original UTF-8/LF CLI format. Preserve both originals. If using a fresh Windows run to diagnose the old pair, first check that `demo_digest.peer` actually equals the historical Windows digest. Otherwise it is a **new pair**. An old JSON can locate the differing stage field; the new pack with a matching v1 digest can also open up stage 8.

* `exact_file_bytes_equal`: actual byte comparison including whitespace/encoding. `canonical_json_equal`: parsed, type-preserving sorted JSON; **no numerical rounding**. Finite round-trip binary64 numbers only. File digests and the original v1 digest are reported separately.
* `fixture_behavior`: default is exact on identities, source trees, dependency pins, labels, codes, counts, orders, scales, votes, thresholds, verification and governance. Only the enumerated continuous measurements (scores, SHAP error, fold dispersion, LIME coefficients/fidelity/stability etc.) use `abs(a-b) <= max(1e-12, 1e-9 * max(abs(a), abs(b)))`. These are software roundoff bounds, not clinical acceptance margins. **Every differing numeric leaf retains both values and the absolute delta**, even if it passes. Strings from the peer and unknown keys are withheld, not echoed as labels.
* Environment/commit context is reported, not forced equal. Tree or protocol drift fails. Byte differences in trained artifact members are explicitly reported by path and `artifact_member_hashes_equal`; they are **not** waived in the loader. Close outputs on two fixed fixtures are not proof of equivalent estimators or full cross-platform scientific validation.
* `MATCH` (exit 0) means agreement on this limited comparison. `DIFFERENT` or `INDETERMINATE` (exit 1) requires inspection. In particular, a changed opaque stage-8 hash with no preimage is **not** a pass. Malformed/oversized JSON, inconsistent checksums, non-finite values, or I/O errors fail closed (exit 2). No comparison can authenticate a peer's claims. Compare only these synthetic reports, never patient records.

## Native Windows PowerShell 5.1 verification (maintainer gate, not a Linux test)

Open **Windows PowerShell** in your existing repository (for example `Set-Location -LiteralPath 'E:\CardioAssist_AI_GitHub_Starter'`). Prerequisites: Git for Windows, `py -3.12` with venv/pip, writable private NTFS storage, network for the fetch and dependency installation. Paste this block. Paste the **full 40-character PR head SHA from the delivery** when prompted; this deliberately refuses a moved ref. It does not switch branches, reset, clean or copy ignored files from the original checkout.

```powershell
$ErrorActionPreference = 'Stop'
$ExpectedSha = (Read-Host 'Paste exact reviewed PR head SHA').Trim()
if ($ExpectedSha -cnotmatch '^[0-9a-f]{40}$') { throw 'Expected 40 lowercase hex characters' }
git fetch --no-tags origin refs/heads/arena/462f2a9b-cardioassist-ai
if ($LASTEXITCODE -ne 0) { throw 'Fetch failed' }
$Fetched = git rev-parse FETCH_HEAD
if ($LASTEXITCODE -ne 0 -or $Fetched -cne $ExpectedSha) { throw 'Fetched head is not the reviewed head' }
$WT = Join-Path $env:LOCALAPPDATA ('CAI12-w-' + [guid]::NewGuid().ToString('N').Substring(0,12))
if (Test-Path -LiteralPath $WT) { throw 'Choose a new path; never reuse a protected checkout' }
git worktree add --detach $WT $ExpectedSha
if ($LASTEXITCODE -ne 0) { throw 'Isolated worktree creation failed' }
Set-Location -LiteralPath $WT
.\scripts\verify_ai12_windows.ps1 -ExpectedSha $ExpectedSha
```

[Read the exact verification commands](../../../scripts/verify_ai12_windows.ps1) before execution. The script checks detached/clean HEAD, creates a **separate new external Python environment**, uses its `Scripts\python.exe` directly (no activation), installs both research and backend dev pins, runs `pip check`, source verification, the native ACL harness, the warnings-as-errors eight-stage demo, two byte-compared packs, both comparison modes, focused and full pytest, `git diff --check` and the final clean-tree check. It prints native exit codes and keeps both packs and `field-comparison.json` outside the checkout. If local policy disallows scripts, run its listed commands interactively under your normal local policy; do not disable ACLs, warnings or machine-wide execution policy.

Inspect `fixture_behavior`, `artifact_member_hashes_equal` and `differences` separately. `legacy-comparison.json` may be `INDETERMINATE` while `field-comparison.json` resolves the observed fixture behavior; an actual threshold, policy or decision change blocks acceptance. A stale digest is not a target to force. Record actual SHA, OS/Python/versions, exits, pass/fail/skip counts and ACL mechanism. An interrupted full suite is not a pass. Native Windows verification of **this PR** is pending until performed by the maintainer; after a human merge repeat on a clean detached **exact merge SHA** fetched from `main`. Keep local artifacts private. Do not delete existing datasets, manifests, bundles, environments or other worktrees.
