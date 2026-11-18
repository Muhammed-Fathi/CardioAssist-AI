# CardioAssist AI — Research Evidence Ledger & Result Recording Standard

**Document ID:** CAI-RH-EVIDENCE-PROCEDURE-2026-11-19-v1  
**Status:** proposed handoff-recording template (not evidence of completed runs)  
**Related:** [completion charter](AI_RESEARCH_PROTOTYPE_COMPLETION_CHARTER_2026_11_19.md) · [execution tracker JSON](AI_RESEARCH_COMPLETION_TRACKER_2026_11_19.json) · [final report blueprint](AI12_2_FINAL_REPORT_BLUEPRINT_2026_11_19.md)

## 1. Single-source-of-truth rule

- **Actual code**: merged reviewed GitHub commit.
- **Scientific source fact**: original primary dataset documentation or reviewed, source-specific archived protocol.
- **Observed performance**: original permitted result with accurate origin, cohort, metric, denominator, resampling/uncertainty. A source document carrying user-reported aggregates is not an independently re-executed test.
- **Canonical AI milestone state**: `docs/research/ai_master_progress.json`; never overwrite PR #91's currently pending AI-10.1 closeout using stale data.
- **RH execution status**: `AI_RESEARCH_COMPLETION_TRACKER_2026_11_19.json`; updated by separately reviewable PR, with evidence links and no asserted tests until human-local checks actually happen.
- **Final academic report**: `AI12_2_FINAL_REPORT_BLUEPRINT_2026_11_19.md` provides section/figure traceability; final manuscript must cite the source result (and the original scientific reference) not just this ledger.

The 2026-11-18 execution ledger is a snapshot at the time it was written, not a live status source. This file does not grant a new training, model serving, source access or clinical authorization.

## 2. Mandatory record for EVERY substantive task

Use a stable record identifier (`RH-XX-EV-NNN`) and record these fields in a PR comment or a small evidence-only Markdown file (plus the machine tracker pointer):

| Required entry | Required content |
|---|---|
| Task | `RH-XX`, scope, reason and linked blocker / decision |
| Code | source repository, exact PR-head full SHA, post-merge full SHA, changed files |
| Science | source/cohort/target ID, sample counts (if eligible), predictor panel, pre-index timing and permission/evidence grade |
| Test | OS, Python, dependency/version context, **exact command**, exit code, passed/failed/skipped, CI workflow/head SHA |
| Result | report/output SHA-256 and approved sanitized path/PR link, schema/determinism/negative-test outcome |
| Research method | comparison design, fold logic, leakage prevention, metric, calibration, CI/uncertainty/limitations |
| Safety | private records not uploaded; source hashes, strict paths/NTFS and actual security results; real model not served |
| Interpretation | exact claim category and what was NOT established; negative findings and no-go are not hidden |
| Review | reviewer, date, review decision, issues to fix, formal approvals if *actually* issued |
| Closure | machine tracker record ID, canonical progress update PR, next executable task |

A report whose local Windows results came from the maintainer must explicitly say **maintainer-reported Windows execution**; the cloud reviewer cannot claim that it ran those tests. Store original protected logs/reports exclusively in their authorized local locations and publish sanitized evidence metadata only.

## 3. Copy-paste PR evidence record template (fill blanks only with observed values)

~~~markdown
### RH-XX-EV-NNN — [short result title]

**Milestone:** RH-XX  
**Evidence state:** PENDING / OBSERVED / VERIFIED / REJECTED  
**Evidence class:** SYNTHETIC_SOFTWARE_TEST / DOCUMENTED_INTERNAL_EXPLORATORY /
ELIGIBLE_REAL_INTERNAL / ELIGIBLE_REAL_EXTERNAL / SOURCE_DOCUMENT_ONLY /
HUMAN_REVIEW_DECISION / NOT_APPLICABLE
**Scoped permission:** [original ratified decision, if any; NEVER inferred]
**Input source:** [named synthetic fixture OR authorized local source identity]
**Target and feature panel:** [source-specific IDs + hashes]
**Candidate PR:** [url]  
**Reviewed full head SHA:** [40 chars]  
**Merge SHA:** [40 chars or NOT_MERGED]
**Platform / interpreter / dependencies:** [actual versions]
**Commands actually executed:** [commands, exact revisions]
**Checks:** [actual PASS / FAIL / SKIP / NOT_RUN, counts and exit codes]
**Native Windows security:** [actual 8/8 or reason NOT_APPLICABLE / NOT_RUN]
**Reports and schema:** [sanitized source link and digest, no protected paths]
**Numerical result:** [only if source-linked and correctly classified]
**Assumptions / limitations:** [explicit]
**Clinical / external claim made:** NONE unless actually authorized and scientifically supported
**Privacy/source validation:** [actual outcomes]
**Reviewer + date + decision:** [named person, date, READY / REVISE / NO_GO]
**Canonical status PR:** [url or PENDING]
**Remaining exact blocker / next action:** [named]
~~~

**Never fill placeholder values with guessed numbers** and do not label a PR merged, suite passing, or review accepted until GitHub/local evidence confirms it.

## 4. Suggested evidence categories and allowable language

| Evidence | Allowed in final report | Forbidden upgrade |
|---|---|---|
| Synthetic test, fixture and invented cohort | Demonstrates reproducible engineering behavior, refusal handling, report/schema fidelity | Clinical model accuracy, real external performance, patient-specific probability |
| Maintainer-recorded within-source exploratory real aggregate | Historical source-specific internal methods/benchmark, with provenance and limitations | Independent source verification, cross-source superiority, deployment/clinical validity |
| Original source metadata / paper | Dataset definition and its documentary limits | Unknown per-record timing, owner codebook, participant identity or permission inferred from a paper |
| Actually authorized and executed real locked external study | Only its permitted, qualified source-specific result | Generalizability to a new population or clinical authorization without needed evidence |
| NO-GO / authorization BLOCKED | Methodologically justified exclusion and future requirements | Claim that blocked validation occurred |

## 5. Stage close transaction / guardrails

1. Start with exact `main`, current `ai_master_progress.json`, PR state and source decisions. Verify no redundant implementation already exists.
2. Open small scoped PR for code/report and add purpose, data and authorization boundaries, exact SHA.
3. Run applicable automated/focused/negative tests in CI, then **maintainer-native Windows** tests as required; report real skips. Any failures remain failures until fixed/retested on a new exact head.
4. Human reviews diff, claims and evidence and decides merge. **Do not self-merge** as an agent. Post-merge run scoped smoke on exact accepted SHA.
5. Open separate docs/metadata closeout PR to update the canonical AI tracker and this RH tracker (plus evidence file, if useful). Never change experimental authorizations in a status PR.
6. Final report number/figure IDs are entered in the claim-to-evidence table. If input evidence changed, re-review dependent report claims.
7. Keep all external AI and product serving claims RESEARCH_ONLY / MOCK_SYNTHETIC unless independently authorized and validated.

## 6. Scientific issue/NO-GO decision template

| ID | Unresolved requirement | Source authority tried | Why still unresolved | Consequence for research | Next owner / permitted action | Decision date |
|---|---|---|---|---|---|---|
| SCI-EXAMPLE | [e.g. pre-reference-test timestamp] | [original owner paper/codebook/response] | [specific gap] | [study HOLD; no real data fit] | [named owner, owner inquiry] | [actual date] |

A recorded `NO_GO_DOCUMENTED` may satisfy a **conditional-protocol disposition** in a complete academic research prototype, but it never changes the truth that an external or real comparison was **not performed**. If the graduating department requires such an experiment as a formal deliverable, escalate and revise the scope before final acceptance.

## 7. Final-report frozen claim index (required)

For each finding, add a row here or in the report's linked claim appendix:

| Claim ID | Human-readable conclusion | Population/source/target | Evidence class | Exact original file/PR/SHA | Original figure/table/report | Limitations and eligible wording | Reviewer |
|---|---|---|---|---|---|---|---|
| C-DA2-D047-PRIMARY-AUROC | Historical within-Cleveland selected procedure AUROC 0.8271 ± 0.0097 | D-047 Cleveland, 303 | DOCUMENTED_MAINTAINER_REPORTED_INTERNAL_EXPLORATORY | `docs/research/gate-pt/04_d047_first_internal_results_REVIEW_DRAFT.md` | `9`; full original method ``3–6` | Not externally validated; repeats reuse people; no between-dataset ranking | PENDING |
| C-DA1-M3A-PRIMARY-AUROC | Historical within-UCI-412 selected LR AUROC 0.9107 ± 0.0071 | M3a UCI-412, 303 | DOCUMENTED_MAINTAINER_REPORTED_INTERNAL_EXPLORATORY | `docs/research/gate-pt/11_two_dataset_scientific_evidence_synthesis_REVIEW_DRAFT.md` | `4`; frozen M3a method | 16-field timing unverified; not external; not directly comparable with Cleveland | PENDING |

These are **starting traceability examples from pre-existing documents**, not newly verified patient-level reports and not evidence of an accepted final report.

## 8. Release acceptance signature placeholders

- **Maintainer academic prototype acceptance:** NOT_SIGNED
- **Independent evidence review:** NOT_SIGNED
- **Clinical use approval:** NOT_GRANTED / OUT_OF_SCOPE
- **Real external validation:** NOT_PERFORMED as of this planning baseline
- **Final source SHA and report release hash:** NOT_ASSIGNED

Only named humans may complete their own actual review/signature entries. Hashes document integrity, **not** human authorization.
