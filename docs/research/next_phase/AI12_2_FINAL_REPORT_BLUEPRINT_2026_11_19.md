# AI-12.2 — Final Graduation Research Report Blueprint and Evidence Map

> **2026-11-19 editorial cross-reference:** A **substantive 17-chapter scientific manuscript draft** now exists at [AI12_2_GRADUATION_RESEARCH_MANUSCRIPT_DRAFT_2026_11_19.md](AI12_2_GRADUATION_RESEARCH_MANUSCRIPT_DRAFT_2026_11_19.md), with [per-chapter evidence/review tracker](AI12_2_MANUSCRIPT_COVERAGE_2026_11_19.json). The `UNWRITTEN` baseline below records this blueprint's **original creation state**, not its current successor status. **No final acceptance or new real clinical validation is claimed.**

**Document ID:** CAI-AI12.2-REPORT-BLUEPRINT-2026-11-19-v1  
**State:** UNWRITTEN FINAL MANUSCRIPT / REVIEWABLE BLUEPRINT ONLY; completing this template is not completion of AI-12.2.  
**Baseline:** `main` `5786424593c5fa9387a1bf382b2233b02779de42`; this is a report specification, not a claim of fresh testing.  
**Related:** [RH completion charter](AI_RESEARCH_PROTOTYPE_COMPLETION_CHARTER_2026_11_19.md), [RH JSON tracker](AI_RESEARCH_COMPLETION_TRACKER_2026_11_19.json), [evidence log](AI_RESEARCH_EVIDENCE_LOG_TEMPLATE_2026_11_19.md).

## Non-negotiable reporting statement

**Title-level intended contribution:** source-specific, reproducible, fail-closed **research prototype** for internal retrospective evaluation of angiography-referenced cross-sectional CAD presence, integrating synthetic software validation and explicitly labeled historical internal exploratory analyses. NOT a patient-specific prognosis, clinical diagnosis, externally validated score or approved medical device. No performance claim based on fictional data; source-dependent endpoints not pooled.

## 1. Final manuscript sections — all required unless independently reviewed N/A

| Section ID | Required chapter / subsection | Must include and where to get it | Completion evidence |
|---|---|---|---|
| FR-01 | Title, authors/contributors, abstract, keywords | Goal, population, engineering contribution and bounded findings. No unearned clinical use language. | Reviewed manuscript and abstract |
| FR-02 | Clinical background and precise research question | Source-defined obstructive angiographic CAD, historical referral population, timing, exclusions, Track A vs Track B and limitations of historical sites | Master Plan `1 + reviewed medical sources |
| FR-03 | Literature and evidence policy | Existing approved/conditional/rejected 25-paper register; original dataset papers; TRIPOD+AI reporting and PROBAST+AI appraisal; standards distinguished from claims of compliance | Source-linked reference list with statuses |
| FR-04 | Dataset provenance and suitability | Cleveland/DA-A2, Z-Alizadeh Sani/DA-A1, Hungary, VA, Switzerland, UCI-411, Statlog, AngioCAD; license/access; recruitment/era, unique subjects, target thresholds, overlap and missingness | Source-cohort decision table with formal no-go reasons |
| FR-05 | Clinical predictors and acquisition timing | Exact five Cleveland and 16 UCI-412 fields; types, units, source evidence, unresolved BP/PR/chest-pain coding/timing; prohibited target-derived fields; proposed UI/OCR acquisition | Versioned feature-to-acquisition contract and status map |
| FR-06 | Experimental design and implementation | Frozen D-047/M3a descriptions; nested/repeated CV, train-fold fitting, class baselines, L2-LR/RF, hyperparameter selection, shuffles, calibration, uncertainty and repeat dependence | File/commit-linked protocol, code and run parameters |
| FR-07 | Internal exploratory real-data findings | Cleveland D-047, UCI-412 M3a: counts, positive class, AUROC and secondary metrics/calibration as actually available, label shuffle, class fractions, SD definition; no head-to-head cross-source ranking | Source-linked tables and original aggregate report references |
| FR-08 | Synthetic system engineering results | AI-7/8/8R/9.1/10.1/11/12.1 implemented behavior, invented cohort descriptions, reproducibility, numerical report hashes, CLI and explicit refusals | Tested code SHA, PR, CI and maintainer Windows records |
| FR-09 | Explainability QA | SHAP background/source and scale/additivity; LIME local fidelity/stability/unavailability; difference between genuine offline research XAI and mock backend SHAP-shaped fixtures | Exact tests/plots/artifact IDs and fidelity limits |
| FR-10 | Model selection, calibration and statistical adequacy | Brier, calibration intercept/slope/CITL availability, illustrative vs assessed precision, Riley-dependent sample size limitations, confusion matrix thresholds exploratory only | Metric-to-report mapping; not-assessed outcomes explicitly stated |
| FR-11 | Conditional incremental labs (AI-9.2) | Eligibility, same-source paired analysis if approved; otherwise defensible NO-GO and explicit synthetic-only AI-9.1 result | Approved study evidence OR reviewed no-go and no claim of improvement |
| FR-12 | Conditional external transportability (AI-10.2) | Hungary/source gate, target/panel/missingness/overlap/precision, locked model/one-shot design; actual authorized results only if performed | Approved locked study OR reviewed no-go, explicitly NOT VALIDATED |
| FR-13 | AI/backend/OCR/app integration boundaries | Registry/route/panel IDs, versioned feature schema, typed input/output, synthetic result vs unavailable/abstain/error, provenance and UI copy limits; F03/F04/F13/F14/F15 and monitoring distinct | Machine contracts/sample payloads, proof mock-only provider |
| FR-14 | Software QA, reproducibility and security | Git PR/merge SHAs, CI and local Windows exact SHA, dependencies/pip check, test coverage/negative paths, source hashes, ACL/HMAC, no patient data committed, redaction and residual skips | Reproduction runbook, logs/digests, accepted review |
| FR-15 | Bias, threats to validity, ethics and governance | Referral/spectrum bias, old cohorts, case-mix/prevalence, target non-equivalence, uncertainty/calibration instability, sample N, lab availability, source chronology, approvals not obtained, no deployment | PROBAST+AI-style structured applicability/risk discussion and exact gate statuses |
| FR-16 | Discussion, limitations, conclusions and next research | Distinguish engineering vs internal exploratory vs external/clinical evidence; answer original question within admitted scope; what is not proven; future real-data requirements | Reviewer-reviewed conclusion without overclaim |
| FR-17 | Appendices / defense packet | Dataset dictionary, routes, lineage, evidence register, rejected inputs, sample synthetic success/abstain, tests, figure data, checklists, references, glossary and Q&A | Fresh reader reproduces without protected data |

**Do not leave empty chapters** in the released manuscript. If a conditional study cannot legally/scientifically run, the corresponding chapter must still contain its precise methodology, eligibility assessment, actual NO-GO outcome and the effects on the manuscript's claims. This is not equivalent to the experiment being performed.

## 2. Predeclared core results and claims — original evidence, not a new execution

| Report table | Permissible data source | Baseline finding to trace | Evidence warning |
|---|---|---|---|
| T-01 Cohort/suitability | Gate DA 01/02/12/14 and source metadata | Each dataset role, sample counts and admissibility | Avoid converting row counts into independent people across overlapping sources |
| T-02 D-047 methods/metrics | `docs/research/gate-pt/04_d047_first_internal_results_REVIEW_DRAFT.md` | Historical Cleveland primary selected AUROC **0.8271 ± 0.0097**, N=303 | INTERNAL_EXPLORATORY; ± = descriptive repeat SD; no external comparison |
| T-03 M3a methods/metrics | `docs/research/gate-pt/11_two_dataset_scientific_evidence_synthesis_REVIEW_DRAFT.md` | Historical UCI-412 selected LR AUROC **0.9107 ± 0.0071**, N=303 | INTERNAL_EXPLORATORY; 16 feature timing meanings unresolved; not a better model conclusion |
| T-04 UCI-412 field ambiguity | `docs/research/ai8r/SOURCE_ADMISSIBILITY.md` | None of 16 pre-angiography collection times owner-verified | New real route stays on SCIENTIFIC_HOLD |
| T-05 Synthetic clinical/labs | PR #87 and #89 + recorded JSON | Invented paired comparison only | Never report synthetic incremental value as a medical finding |
| T-06 Synthetic locked-site | PR #90 and, only when merged/reviewed, #91 | Invented external rehearsal | No real Hungary assessment or transport claim |
| T-07 Integration and safety | AI-11 / AI-12.1 contracts/tests/source SHA | Synthetic-only offline facade, five-slot catalog, E2E refusal paths | Backend still MOCK_SYNTHETIC |
| T-08 Study dispositions | New RH-02/RH-06 reviewed records | GO/RUN vs NO-GO reasons for real AI-9.2 and AI-10.2 | NO-GO = NOT PERFORMED, not validation |
| T-09 CI + Windows evidence | Actual exact-head and postmerge PR/test reports | Pass/fail/skip/exit/security/schema digest | Do not invent results or treat split tests as single monolithic suite |

Each result table must include source file + exact version/SHA, cohort and target identity, eligible metric numerator/denominator, estimator/uncertainty meaning, limitations and **the precise human-verified claim category**.

## 3. Figures and visuals — do not fabricate research plots

| Figure ID | Suggested visualization | Requires actual source |
|---|---|---|
| F-01 | Research architecture: source → panel → validator → research facade → synthetic demo; Track B isolated | Versioned code and tests |
| F-02 | Cohort and source-admissibility flow chart, accepted vs held/rejected | Gate DA/PT + owner metadata |
| F-03 | Nested CV/train-test preprocessing and model-selection boundary | Frozen experiments/code |
| F-04 | Within-Cleveland ROC/calibration results **only if original permitted aggregate/plot supports them** | Original D-047 sanitized report or mark unavailable |
| F-05 | Within-UCI-412 ROC/calibration results **only if permitted sources actually support them** | Original M3a sanitized report or mark unavailable |
| F-06 | SHAP/LIME QA schematic or actual synthetic fidelity charts | Exact executable/test evidence |
| F-07 | Research-only demo input → output + representative abstention/error (synthetic, not patient) | Generated deterministic fixture output |
| F-08 | Evidence maturity/limitations and source-dependent conditional research paths | Exact reviewed source/decision matrix |

Do **not** regenerate patient-level ROC/calibration plots from protected records in the cloud or invent curves from rounded reported AUROC. If a figure requires unpublishable or unavailable data, mark it unavailable with reason and use only an alternative backed by actual permitted aggregates.

## 4. Final scientific traceability and review forms

For EVERY numbered claim, table and figure, record:

- Claim/figure/table ID and exact statement.
- Source-specific target/feature panel and number of unique people (if known).
- Reference file, section and **exact Git SHA** plus original owner paper/official source where applicable.
- Evidence class: primary source; historical maintainer-reported internal exploratory; independently reproduced synthetic; formally approved real internal; formally approved real external; or unresolved/no-go.
- Code/run parameters; source pre-index evidence and authorization.
- Exact report digest, output path only if reviewed and sanitized; no private rows/reports in repository.
- Assumptions, bias, uncertainty meaning and claim restrictions.
- Reviewer, decision, resolution date, link to RH machine-tracker entry.

Final model card(s) must contain intended research use, ineligible populations, source contract, predictor types/missingness/timing, training/evaluation cohort, performance evidence grade, calibration status, explainability model/fidelity/limitations, software reproducibility, version hashes, restrictions and behavior on invalid inputs. Do not mislabel the five-entry research registry as five real trained deployable models.

## 5. Final acceptance checks — no report shipped half-written

1. All FR-01…FR-17 chapters complete, reviewed or narrowly marked **N/A with documented rationale**; conditional study chapters are never omitted.
2. Every numerical value/figure has traceability into actual committed source evidence; no synthetic vs real confusion; no manufactured curve, confidence interval, trial or approval.
3. Complete methodology/design limitations and independent review of the accuracy, safety and scope of **all** scientific claims.
4. All 15 acceptance criteria in the RH tracker have evidence IDs and named reviewers; RH-08 not accepted merely because this template exists.
5. Final abstract, conclusion, slide/demo claims and README use identical carefully scoped language.
6. Final report file/artifact receives source release SHA, document version, actual review date and an integrity hash, recorded in the repository.
7. Independent reader can run the accepted synthetic demonstration and refused-input checks on a clean local environment without private data or paid infrastructure.

## 6. Actions after manuscript freeze (separate workstream)

An optional Flutter/Web + FastAPI + local database **synthetic research demonstration** may be created against the reviewed typed contracts after RH-08. It is **not** the same thing as real clinical model serving. OCR and doctor/patient workflow implementation require separately reviewed app contracts and simulated data. Track B monitoring cannot modify the historical Track A CAD score. Any future real-model provider, clinically oriented patient output or new real-data training remains separately gated.

**This document is a blueprint. The completed manuscript, actual executed/reviewed results and release package still need to be produced in future reviewed milestones.**
