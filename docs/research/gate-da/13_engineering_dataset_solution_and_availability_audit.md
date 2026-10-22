# M2a — Engineer the solution: pre-training dataset feasibility and implementation handoff

**Decision prepared 2026-10-22 | Status: engineering feasibility **PROPOSED**, not selected model predictors or a frozen clinical protocol.** D-046 allows local *read-only* audits of authorized UCI inputs; Gate PT (P-3) prohibits fitting, feature selection, tuning, evaluation, calibration or explanation on real patient records before supervisor clinical-protocol signoff. Do not confuse a technical test pass with clinical validation.

## The current engineering conclusion

We **will not** train a naïve shared 13-predictor model across UCI-45 cohorts. Raw-versus-Processed files are source representations, not additional patients. The source-warned raw Cleveland remains unparsed and byte-guarded. We will investigate a **pre-angiography** clinician-entry CAD-presence decision point, with a phase-aware input design and disclosure of site differences; do not use angiographic `ca` or per-vessel stenosis to predict an angiography-derived target. Exact disease threshold harmonization (>50% vs >=50%) and availability timing remain protocol questions, not decisions to invent.

**Independent prior research reviewed:**

1. [UCI Heart Disease official](https://archive.ics.uci.edu/dataset/45/heart+disease), DOI [10.24432/C52P4X](https://doi.org/10.24432/C52P4X): four sites; 76 raw fields vs conventional 14; target `num` 0 versus 1–4; critical distinctions of `ca` fluoroscopy and `thal` stress testing. The primary codebook lists `chol` in mg/dl, `trestbps` in mm Hg, and raw sentinel -9.0, but **does not explicitly specify** zero as missing.
2. [Datanovia / datarium four-site heart-disease documentation](https://rpkgs.datanovia.com/datarium/reference/heartdisease.html): describes **172 cholesterol zeros** (123 Switzerland plus 49 Long Beach VA) as *not measured*. This is a useful **secondary, not UCI-original** coding interpretation and matches our local real raw/processed frequencies.
3. [Hasan & Dhrubo (2026), Scientific Reports](https://www.nature.com/articles/s41598-026-35451-3): their multi-region study removed largely absent `ca`/`thal` and observed Statlog–Cleveland overlap in **their specific combined dataset**. We **will not automatically copy** those feature choices or assume the same overlap in official UCI-145 until explicitly verified; any evaluation cohort must not contain development samples.
4. [Mauya et al. (2025), Engineering Reports](https://onlinelibrary.wiley.com/doi/full/10.1002/eng2.13034): accounts for Swiss cholesterol's unavailability by reducing the feature panel. Use it as evidence of a tested alternative, **not** proof that dropping `chol` is clinically best for our target or universal among centers.
5. [BMJ evaluation methodology](https://www.bmj.com/content/384/bmj-2023-074819) and [TRIPOD+AI (BMJ 2024)](https://www.bmj.com/content/385/bmj-2023-078378): justify transparent per-center missingness and outcome definition, leakage protection, validation separated from development, and proper reporting of discrimination and calibration. [Health-care cross-validation tutorial](https://pmc.ncbi.nlm.nih.gov/articles/PMC11041453/) places imputation, encoding, scaling and tuning within training folds only; no global median or target-based fill before splitting.

## Practical decision: run an availability audit, not another unstructured review

**Implementation in this PR**: `research/audit/availability_scenarios.py` plus synthetic-only regression tests. The module uses verified local D-046 authorization and SHA-256 source provenance, rejects data outside Git-ignored paths, and byte-guards **all nine** DA-A2 assets while parsing *only the four approved 14-attribute Processed* cohorts. The quarantined raw Cleveland is not parsed. It constructs no new dataset file, modifies no values, and prints **fixed-label, aggregate counts only**. No outcome inspection, feature ranking, fitting, imputation or automatic dataset decision occurs.

Pre-specified **descriptive measurement-stage feasibility** bundles (not trained feature subsets):

| Label | Available measurements hypothesized at stage | What it tests |
|---|---|---|
| `history_only` | `age, sex, cp` | History-level structured intake |
| `resting_assessment` | History + `trestbps, restecg` | Baseline measurements at resting clinical visit |
| `resting_plus_labs` | Resting + `chol, fbs` | Does actual laboratory availability permit a richer path? |
| `includes_exercise_tests` | Resting+labs + `thalach, exang, oldpeak, slope` | Availability effect of optional exercise-test stage |

Every bundle is counted **twice**, on unmodified row data:
- **Literal-source scenario**: `?` or `-9` are missing as already parsed; preserve valid zeros (especially oldpeak, binary categorical fields).
- **Explicit hypothetical coding sensitivity**: *for measurement availability counts only*, treat `chol=0` or `trestbps=0` as potentially unavailable; **this does not convert the source data or impute** and follows source-flagged implausible values from the independent documentation.

The literal counts and the hypothetical counts make the cost of zero conventions and adding test stages explicit. **These counts are not model performance, statistical feature selection, proof of independence or a clinical suitability certificate.**

### How to run on the maintainer's authorized Windows machine (AFTER merge)

From `E:\CardioAssist_AI_GitHub_Starter`, on synced clean `main`, after confirming local authorizations and original files are present:

```powershell
& "E:\CardioAssist_PR11_Audit_Venv\Scripts\python.exe" -m research.audit.availability_scenarios `--auth-manifest data/manifests/gate_da_authorization.local.json `--provenance-manifest data/manifests/provenance_manifest.json
```

The PowerShell backticks shown here join a single command; the module has **no output-file flag** and writes nothing. It never uses `--train`, `--fit`, `--evaluate`, external services or new dependencies. **Share only the printed aggregate output, not any dataset or raw manifest.** Abort if governance, hash, byte identity, working-tree, or parser validation fails.

## What follows, with owners and evidence gates

1. **Engineering now:** use the above fixed measurement-stage availability counts to compare actual joint completeness by site instead of marginal estimates. Document where the zero sensitivity changes availability materially; interpret cross-site differences but do not pick a model input feature set by maximizing the counts.
2. **Research now:** independently verify that Hungary's processed 0/1 label equals raw `num>0` at aggregated level, record exact unresolved person-level mismatches without publishing records, and prepare a principled target harmonization proposal. Compare UCI-412 data dictionary/timepoint to UCI-45; UCI-411 is **the same 303 patients** as the UCI-412 extension, not 303 more.
3. **Supervisor review, once a complete team recommendation exists:** decide the clinical endpoint, measurement time, acceptable pre-Cath tests, source zero coding policy, 50% narrowing boundary and external validation intent. Freeze formal Gate PT protocol and obtain P-3 signoff **only before executing fitting or model-based feature selection/evaluation**.
4. **After formal authorization (not in this PR):** data transformations in a versioned, reversible in-memory derived layer; pre-specified logistic-regression baseline and one tree ensemble comparator; stratified development validation as methodologically appropriate, preprocessing within training folds, no leakage from test sites, repeatability checks, bootstrap uncertainty, calibration and AUPRC as appropriate, site-stratified reporting and bounded SHAP on a fixed compatible output scale. Do not claim an external-validation study without independent cohort verification and prospective purpose.

**Success criterion for this PR:** synthetic-only CI green, no source mutation, credible aggregate per-cohort feasibility table ready for scientific decision; not a measured AUC, deployment-ready clinical prediction tool, or permission to train.
