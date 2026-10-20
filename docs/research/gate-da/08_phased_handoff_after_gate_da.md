# 08 — Phased Handoff: What Happens After Gate DA

**Status: PROPOSED handoff plan. Each phase below requires its own
authorization; completing one phase never starts the next.** This package
(this PR) is Phase R0. It ends with a human Gate DA decision — nothing
else in this document is current work.

## Phase map

| Phase | Name | Entry condition | Work (bounded) | Exit artifact | Explicitly forbidden in this phase |
|---|---|---|---|---|---|
| **R0** | Dataset suitability & Gate DA preparation | This task's authorization (documentation only) | This package (documents 01–08) | Reviewed PR; Gate DA decision recorded (grant/defer/refuse per dataset) | Downloads, training, code/schema/DB changes |
| **R1 (= M2)** | Local acquisition + **read-only** dataset audit | Gate DA granted for named datasets (document 04 checklist complete: authorizer, storage, acquirer/auditor, environment) | Download **only** the authorized files from official UCI pages into `/data/` (verified ignored); licence snapshots; SHA-256 manifest; dictionary/counts/missingness/duplicate/availability audit per document 04 §4; update documents 01/03 tables with findings (dated audit report in `docs/research/` or `research/experiments/` per team convention) | Written audit report closing or escalating every H/L register item as a *finding*; rows/patients/events/sites counts; H-01 threshold evidence | **Any** fitting, feature selection by outcome, tuning, calibration, explanation, or performance evaluation; acquiring unlisted datasets "while we're at it" |
| **R2** | Gate PT protocol freeze | R1 audit report reviewed | Convert document 05's outline into the frozen protocol using audit findings (target wording, dictionary + availability rulings, prediction moment, completeness/duplicate rules, Strategy A–D decisions, models/metrics/calibration/subgroups, seeds, stopping rules); supervisor sign-off recorded (P-3) | Timestamped frozen protocol + signed leakage sign-off (document 05 §10 checklist) | Any model work before sign-off; amending the protocol after seeing results (dated amendments only) |
| **R3 (= M3)** | Modelling under the frozen protocol | Gate PT signed | Strategy A per-cohort models (nested CV, within-fold preprocessing, label-shuffle control); Strategy B external evaluations where document 02 §3 conditions pass; calibration (cross-fitted); real SHAP/LIME with stability checks; subgroup analyses per minimum-cell rule; model cards + run registry in `research/experiments/` | Reproducible experiment package: code + configs + hashes + model cards with CIs (data and weights stay out of git) | Locked-holdout improvisation at n≈300; test-set peeking; reporting mock numbers or literature numbers as project results; clinical claims |
| **R4 (= M4)** | Integration readiness + write-up | R3 model cards reviewed | Contract-first proposal for a **new** real feature schema + model registry (new identifiers, never `mock_*`; contracts Q1 process); backend integration slice (separately authorized PR); TRIPOD+AI write-up with internal/external labelling law | Reviewed integration PR (future); research report with honest limitations (era/spectrum, H-01 ruling, subgroup minimums) | Changing existing `/v1` mock contracts/fixtures in place; serving a model whose `validation_status` overstates its evaluation; "% risk" rendering of uncalibrated scores |
| Parallel | Platform workstreams (Auth/RBAC, durable idempotency, consent, patient records, DB expansion, entitlements planning) | Their own maintainer authorizations | Per D-045 sequencing and document 07 DQ-INT-4/5 boundaries: entitlement tiers (Free 2-use lifetime quota; 14-day Doctor Trial via doctor-issued code returning to Free with remaining quota; Premium locally simulated) are implemented, if at all, in that workstream — never as clinical authorization or doctor–patient linking | Separate reviewed PRs | Using subscription state to alter clinical inputs, inference eligibility (beyond product access control), or Track A/B separation |
| Parallel | Frontend (frontend-team owned) | Frontend team's schedule; M1a.3 thin-demo slice only when separately authorized (D-045) | Thin local integration demos against mock contracts; full React/Flutter apps against document 06's plausibility spec for *planning*, and against the R4-approved real schema only when it exists | Frontend-team PRs | Presenting mock outputs as clinical results; soliciting leakage features (L-01…L-03) as inputs; wearable-to-CAD flows |

## The exact next authorized research task (if Gate DA is granted)

One sentence, for the avoidance of doubt:

> **"M2 — Gate DA read-only dataset audit": a named acquirer downloads
> exactly DA-A1 (UCI-412) and DA-A2 (UCI-45, four files) — plus DA-B1/
> DA-B2 only if separately granted — from the official UCI pages into
> git-ignored local `/data/` storage, snapshots licences and SHA-256
> hashes, and produces the read-only audit report specified in
> document 04 §4 (dictionary, counts, missingness, duplicates/overlap,
> target verification, per-feature availability), updating the
> document 03 register with findings. No model is fitted, selected,
> tuned, calibrated, explained, or evaluated. The audit report is
> reviewed as its own PR, and Gate PT (Phase R2) is requested only
> after that review."**

If Gate DA is refused or deferred, there is **no** next research task:
the track waits, and no substitute dataset is acquired (document 04 §6).

## Handoff checklist for the reviewer of this PR

- [ ] Gate DA decision recorded per dataset (DA-A1, DA-A2, DA-B1, DA-B2)
      in `docs/DECISIONS.md` or the PR record — grant / defer / refuse
- [ ] If granted: acquirer, auditor(s), storage path (`git check-ignore`
      verified), and target environment named
- [ ] Acknowledgement recorded that Gate PT + supervisor sign-off remain
      required before any modelling (P-3), and P-1/P-4/P-5 remain open
- [ ] This PR left **OPEN** for independent human review; not self-merged
