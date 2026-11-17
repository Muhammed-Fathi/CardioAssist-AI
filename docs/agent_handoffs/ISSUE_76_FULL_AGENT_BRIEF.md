# Issue #76 — Complete Arena brief and two follow-up comments

> **Access workaround, snapshot 2026-11-17.** This is a verbatim copy of the body of [GitHub Issue #76](https://github.com/Muhammed-Fathi/CardioAssist-AI/issues/76) and all two comments returned at snapshot time. It is here only because Arena's GitHub Issues integration returned `403 Resource not accessible by integration`, while Git repository access worked. The live issue remains canonical if access is restored. **This handoff file is not a research deliverable or a governance approval.**
>
> **Agent instructions:** Read this file fully using Git, then follow all instructions in the Issue body and two comments below. In particular, PR #75 is already merged, so use up-to-date `main`. Conduct independent medical web research. Create a separate *new* research branch from the latest `main` and an OPEN PR containing ONLY the three requested `docs/research/next_phase/*` deliverables. Do NOT include this handoff file or branch in your research PR. Do not require GitHub Issues API access to continue; report the access limitation without blocking. Do not run fitting or touch private data.

---

## Original issue — #76: AI-Next: independent primary-source medical research + AI-9..12 execution decision (Arena handoff; research-only)

Original: https://github.com/Muhammed-Fathi/CardioAssist-AI/issues/76

# Independent Arena Agent research assignment — medical first, evidence-graded, no training

**Owner request (2026-11-17):** finish the CardioAssist AI workstream technically and scientifically for an academic *research-only* end-to-end demonstration, with every medical design choice derived from primary sources. The owner will not seek routine supervisor consultation for each research-design choice. **This does NOT allow the agent to impersonate clinical/institutional review, ratify D-048, access private patient records, enable clinical inference, or treat documentary evidence as legal/ethical approval.**

## Required repo-first read (do not skip)

At latest live `main`: `AGENTS.md`, `docs/DECISIONS.md`, `docs/research/CARDIOASSIST_AI_MASTER_COMPLETION_PLAN.md` + `docs/research/ai_master_progress.json` (also review pending v1.7 docs PR #75 and conflicts), `docs/research/ai8r/SOURCE_ADMISSIBILITY.md`, `research/uci412/schemas/ai8r_eligibility.v1.json`, `research/uci412/schemas/uci412_feature_dictionary.v1.json`, all relevant `docs/research/gate-pt/**`, 25-paper approval-color original materials, current adapters/inference/evaluation code and tested PR #74. PR #74 merged `5b3709ee6273f1c9c4fbf2a007921e8b4a73af7f`, **AI-8R engineering accepted on native Windows** (2,366 passed/3 skipped across two disjoint completed suites, not a completed monolithic suite; postmerge AI8R 22 passed + source integrity + expected fail-closed preflight). AI-8R **scientific** status is `SCIENTIFIC_HOLD`. PR #75 v1.7 docs tracking may still be OPEN. Preserve all existing signed/ignored local manifests, governance and source hashes; no `run` on real data.

## Independent web research: verify, disagree or qualify the proposed directions

Research *primary authoritative medical/methodological sources* first, with exact DOI/permalink, publication date, directly supporting passage/section, evidence quality, source access rights/licensing, and a **last checked on** date. Label (1) evidence-confirmed facts, (2) repository observations, (3) engineering/scientific recommendations, (4) unverified/blocked assumptions. Check updates through November 2026.

Starting leads; **these are candidates, not agent-approved decisions**:
- ESC 2024 Chronic Coronary Syndromes guideline for pre-test obstructive CAD likelihood and RF-CL: https://www.escardio.org/guidelines/clinical-practice-guidelines/all-esc-practice-guidelines/chronic-coronary-syndromes . Its website explicitly cautions about required formal licenses for embedding guideline content in software/algorithms. Citation and clinical-context comparison are not blanket permission to port a scoring algorithm into an app.
- Official UCI-412 `https://archive.ics.uci.edu/dataset/412/z`: 303 participants; cross-sectional angiography-defined CAD >=50%; no reliable per-field pre-angiography timing/codebook established.
- Official UCI-411 `https://archive.ics.uci.edu/dataset/411/extention+of+z+alizadeh+sani+dataset`: extension of the same 303 patients; not an independent validation cohort.
- Official UCI-45 `https://archive.ics.uci.edu/dataset/45/heart+disease`: Cleveland/Hungary/VA/Switzerland; label wording >50%; site-specific missingness/selection; Hungary is already a **locked** external candidate, do not evaluate/peek on outcomes.
- TRIPOD+AI reporting BMJ 2024 DOI 10.1136/bmj-2023-078378; PROBAST+AI appraisal BMJ 2025 DOI 10.1136/bmj-2024-082505; Riley et al. external validation BMJ 2024 DOI 10.1136/bmj-2023-074820, and model-development sample-size BMJ 2020 DOI 10.1136/bmj.m441.
- AngioCAD 2026 DOI https://doi.org/10.5281/zenodo.15826856 and publication https://www.sciencedirect.com/science/article/pii/S0169260726001331 : 413 *post-angiography imaging* records/video, not known suitable for a pre-reference-test **tabular** risk predictor. CADICA (Mendeley DOI 10.17632/p9bpx9ctcv.5) is also post-angiography, only 42 patients. Avoid accidental task/data leakage; check original data metadata and patient-level accessibility **without downloading**.

## Medical research questions (must answer, not just list sources)

1. Define an honest **research estimand**: suspected chronic coronary syndrome/pre-reference-test presence of **source-defined angiographic obstructive CAD** in *referral population*, not future heart attack, ACS triage, treatment advice, generic consumer prediction, or diagnosis. Discuss severe verification/referral/spectrum bias and cross-site prevalence/calibration transport.
2. Does UCI-412's **16-field** panel satisfy pre-test timing and variable semantics? Verify all 16, especially S-9 numeric binary directions, BP systolic/diastolic and conditions, PR units, Typical/Atypical/Nonanginal/Exertional CP relationships, U-6 pre-angiography timing. Give evidence level/source location for each field; NEVER mark `VERIFIED` without original owner documentation. Define a time-box-free alternative if source-owner clarification cannot be found. No exploratory fitting to "discover" source encoding.
3. Evaluate dataset candidates one by one with official download landing page (URL only), patient count, uniqueness, endpoint and stenosis convention, clinical acquisition timing, independent site, labels, pre-test predictors, outcome prevalence evidence, missingness, reuse conditions, suitable role (development / locked external / stress / imaging-only / rejected), confidence, exact blocker. Include Cleveland, Hungary, VA, Switzerland, UCI-412, UCI-411, Statlog, AngioCAD, CADICA, ARCADE and any stronger **public** alternatives found. Do **not** use same patients in both training and external validation; do not claim imaging-derived labels are pre-test variables. No dataset downloading or row-level exploration.
4. Choose the defensible model family/baselines for small tabular cohorts. Compare penalized logistic regression, modest boosting, calibrated/simple models, clinical comparator RF-CL *as allowable given inputs and licensing*, and explicit abstention; report methods rather than invented metrics. Riley sample-size justification with sample size, predictor complexity and outcome prevalence; nested CV vs naive random split; prohibit preprocessing leakage; use real scientific performance only when specifically authorized.
5. Define a prespecified evaluation plan: AUROC with CI, AUPRC where class imbalance relevant, Brier, calibration-in-the-large/intercept/slope/plots, net benefit/decision curve only with justified thresholds and support, sensitivity/specificity/PPV/NPV at **pre-specified** thresholds where appropriate; subgroup/drift with uncertainty; distinguish discrimination/calibration/clinical utility and explainability faithfulness. No claim that SHAP/LIME is causal or medical advice.
6. Evaluate risks and governance: patient data, raw files, ESC guideline copyright/software use, UCI licenses, restricted external validation/Hungary, D-046/D-047/D-048 and Gate PT, no self-authorized protected cohort access. When facts require clinician judgement, state precise decision, the best research recommendation and its conditional/education-only status; never silently promote to an approved clinical rule.
7. Scope AI-9 **clinical vs routine labs** same-source comparison only after temporally valid labs/labels, respecting sample-size budgets; give explicit NO-GO if not established. AI-10 frozen model + independent evaluation: plan only until authorized. AI-11 offline *research-only* model registry, versioned feature acquisition/validation/status/missingness/abstention, external model cards, backend interface with default `MOCK_SYNTHETIC` and absolutely no real clinical serving. AI-12 signed evidence inventory and reproducible demo with synthetic fixtures.
8. Provide **at least two coherent strategies** and explicit risk comparison: (A) Cleveland existing 5-field baseline + strict source-specific research-only system + conditional Hungary validation; (B) UCI-412 contingent on owner evidence; (C) newly identified independent cohorts if stronger. Make a single recommended path, exact why, why alternatives rejected or delayed, uncertainty and fallback.

## Required outputs and execution boundary

**Research/report only for this first issue, no implementation yet**:
- `docs/research/next_phase/INDEPENDENT_MEDICAL_ENGINEERING_RESEARCH.md`: all 8 answers, primary citations, dataset comparison table, risk/eligibility and recommendation, open decision register, quality ratings.
- `docs/research/next_phase/AI9_AI12_EXECUTION_SLICES.md`: sequenced PR-sized engineering milestones (AI-9, AI-10, AI-11, AI-12 plus source evidence). For each: scope, files/API boundaries, synthetic tests, local Windows runbook, CI, exact 'done', dataset permissions, forbidden actions, scientific claim levels; identify parallelizable safe engineering now vs externally gated work. No made-up dates.
- `docs/research/next_phase/INDEPENDENT_DISAGREEMENTS.md`: clearly challenge wrong, incomplete or outdated claims in the current master plan or this issue, independent proposed corrections with citations. If none, state tested points and evidence, not automatic agreement.
- **No edits outside the above new documents in this first research PR**; no `AGENTS.md`, `DECISIONS.md`, frozen protocol, clinical algorithms, training code, source files, baseline plan/progress/PR #75.
- Run `git diff --check`, doc links/JSON validations where applicable, relevant safe checks and report their real outcomes. PR must target latest `main`, be **OPEN for human review**, never self-merge, and include a handoff for the maintainer to review results here. Save no private data; do not start unapproved training, downloading, fitting or clinical inference.
- Output must explicitly separate `RESEARCH_DECISION_SUPPORTED`, `ENGINEERING_READY`, `REAL_EVALUATION_NOT_AUTHORIZED`, `CLINICALLY_UNVALIDATED` — these categories are not interchangeable.

## Next action for Arena

Using its **own web search** (not only this issue's suggested citations), perform an independent repo + medical research audit and open the **documentation-only research PR**. State its PR URL, exact SHA, strongest recommendation, major blockers, and what first *engineering code PR* should be scoped to **after** research review. Do not treat the user's desire to avoid supervisor conversations as an authorization to make claims that normally require specialist/regulatory/institutional approval.

**Owner's question to agent:** Which *scientifically and engineering-defensible* path lets this academic CAD AI prototype be completed end-to-end with $0, while explicitly preserving research-only restrictions and scientific uncertainty?

---

## Comment 1 — https://github.com/Muhammed-Fathi/CardioAssist-AI/issues/76#issuecomment-6959115941

**Live status update, 2026-11-17:** [PR #75](https://github.com/Muhammed-Fathi/CardioAssist-AI/pull/75) has now been **MERGED** into `main` at exact SHA `3110485712daf31515551f5e277d76d209c544e8`; all four PR-head CI checks completed successfully. `docs/research/ai_master_progress.json` on main is v1.7: AI-8R engineering `LOCALLY_ACCEPTED_ENGINEERING_ONLY`, real research `BLOCKED_RESEARCH_EXECUTION`. **Arena: base on latest `main`, not the old PR #74 merge SHA; check for any newer commits.**

**Independent preliminary research hypotheses to challenge, not rubber-stamp:**
1. Keep the established UCI-45 Cleveland 5-input pathway as a bounded **historical internal exploratory research baseline**, not a general-population or clinically calibrated CAD risk model. Hungary is a planned **locked** external test, not extra training data; clinical representativeness/missingness remain open (original UCI page https://archive.ics.uci.edu/dataset/45/heart+disease ).
2. UCI-412 (official https://archive.ics.uci.edu/dataset/412/z ) remains a methods-only candidate with `SCIENTIFIC_HOLD` until original owner confirms source collection/coding/timing for each field. No real fitting is authorized; UCI-411 duplicates the same 303-patient source (https://archive.ics.uci.edu/dataset/411/extention+of+z+alizadeh+sani+dataset ).
3. AngioCAD (https://doi.org/10.5281/zenodo.15826856 ; 413 angiography patients), CADICA (https://data.mendeley.com/datasets/p9bpx9ctcv/5 ; 42 patients), and ARCADE (https://doi.org/10.1038/s41597-023-02871-z ; angiographic images) involve invasive *post-test imaging*; they are **not established substitute pre-angiography clinical-tabular predictors**.
4. ESC 2024 CCS clinical likelihood guidance (https://www.escardio.org/guidelines/clinical-practice-guidelines/all-esc-practice-guidelines/chronic-coronary-syndromes ) is a scientific reference/comparator *concept*, **not automatically a licensed software algorithm**; the ESC page specifically requires formal license for guideline content embedded/transformed in software tools and algorithms. Explore lawful alternatives; do not paste guideline coefficients/tables into a free app without clearance.
5. Prioritize independently useful **AI-11 offline research-only registry, feature/provenance contracts, typed error/abstention and mock-only FastAPI compatibility** as first code-slice candidate; forbid default live model switching. AI-9 routine-lab real incremental study and AI-10 locked-site real external evaluation remain blocked until eligibility, sample-size, protocol and scoped access conditions are satisfied.
6. Clinical-model publication-grade evidence should consider TRIPOD+AI DOI 10.1136/bmj-2023-078378, PROBAST+AI DOI 10.1136/bmj-2024-082505, Riley external validation DOI 10.1136/bmj-2023-074820, Riley development sample-size DOI 10.1136/bmj.m441. Medical evidence & recommendation should be distinguished from permission/clinical approval.

---

## Comment 2 — https://github.com/Muhammed-Fathi/CardioAssist-AI/issues/76#issuecomment-6959352886

## Owner scope clarification — 2026-11-17 (prioritize academic research prototype, not clinical deployment)

The owner clarifies that the goal is **a technically complete, scientifically defensible end-to-end graduation-project AI research prototype**, NOT deployment on real patients or clinical certification. Please optimize recommendations for timely completion on a $0 budget. Avoid treating hospital deployment approvals, prospective patient studies, clinician sign-off, medical-device certification or supervised real-world workflows as prerequisites to making progress on academic engineering tasks.

**Operational interpretation:**
1. **Proceed in parallel now** on independent research-only engineering: AI-11 offline model registry + typed inference/feature/acquisition/abstention interface, synthetic end-to-end demo, auditability/test coverage/model cards, and AI-12 reproducible handoff. Plan AI-9/AI-10 protocols and suitability analysis; implement safe synthetic components as warranted.
2. Distinguish **scientific model validity** from **clinical deployment approval**. We can independently choose evidence-backed study design, baselines, evaluations, error handling and research-system architecture, document justifications, and use publicly accessible eligible data **only where existing repo governance/authorization actually allows that work**. Do not invent approvals or bypass frozen D-046/D-047/D-048/locked-cohort restrictions.
3. A disputed predictor source (UCI-412 timing/codebook) remains an **explicit model-route-specific scientific hold**, not a hold on the **whole project's engineering**. If owner-level source semantics cannot be resolved, recommend an alternative academically valid data route (Cleveland existing bounded research baseline, eligible other sources after audit), or provide a clearly labeled synthetic research demonstration. Never silently make up variables or treat synthetic scores as proven medical metrics.
4. Keep output medically coherent: specify the exact target, admissible features at inference time, absence of leakage, population/validation limitations, calibration methodology and uncertainty. Cite supporting clinical/research literature. No claim that SHAP/LIME gives a medical diagnosis.
5. Prioritize **working engineering deliverables + tests** over repeated governance documents after this initial research PR. Provide a **minimum viable academic E2E definition of done** (inputs → validation → versioned research model or safe synthetic fallback → calibrated output only if supported → XAI scope → backend mock/test interface → reproducible report/demo) and a ranked actionable sequence to deliver it.

In this issue’s first PR, independently research and propose. After review, subsequent code PRs should implement the safe parallel path quickly. This scope clarification does not authorize touching private patient files, protected model artifacts, locked test outcomes, or enabling real-model clinical serving.

---

**End of complete Issue #76 handoff snapshot (issue body + two comments).**
