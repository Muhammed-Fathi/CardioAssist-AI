# 04 — Gate DA Approval Packet

**Status: REQUEST PACKAGE — Gate DA is NOT open. No acquisition is
authorized by this document.** Gate DA = P-2 / D-031 in
`docs/DECISIONS.md`: a *named human* authorization listing the **exact**
datasets, after which — and only after which — local-only acquisition and
a **read-only** audit may occur (Phase 0 §F-3, §R2-5.1). Gate DA permits
**no** model fitting, feature selection, tuning, calibration, explanation
generation, or performance evaluation.

## 1. Exact datasets named in this request

### Request DA-A (primary — approval requested for these, by official identifier)

| # | Dataset (official source) | Identifier | Files as listed at source | Licence as stated at source |
|---|---|---|---|---|
| DA-A1 | UCI Z-Alizadeh Sani | UCI id **412**, DOI 10.24432/C5Q31T | `Z-Alizadeh sani dataset.xlsx` (120.7 KB) | CC BY 4.0 **[VERIFIED 2026-10-20]** |
| DA-A2 | UCI Heart Disease (all four cohorts) | UCI id **45**, DOI 10.24432/C52P4X | `cleveland.data` (59.2 KB), `hungarian.data` (60.7 KB), `switzerland.data` (24.1 KB), `long-beach-va.data` (39 KB) | CC BY 4.0 **[VERIFIED 2026-10-20]** |

Source URLs: `https://archive.ics.uci.edu/dataset/412/z+alizadeh+sani`,
`https://archive.ics.uci.edu/dataset/45/heart+disease`. Acquisition, if
approved, is **from these official pages only** — never from Kaggle or
any mirror, even of the same dataset.

### Request DA-B (conditional — approval requested only for the stated audit purposes)

| # | Dataset | Identifier | Sole approved purposes if granted | Licence |
|---|---|---|---|---|
| DA-B1 | UCI Extension of Z-Alizadeh Sani | UCI id **411**, DOI 10.24432/C5461K | (a) Same-cohort feature-superset/dictionary audit against DA-A1; (b) preserving the *option* of a future supervisor-approved T2 protocol. **Never** external validation; LAD/LCX/RCA never T1 predictors (L-03/L-04) | CC BY 4.0 **[VERIFIED 2026-10-20]** |
| DA-B2 | UCI Statlog (Heart) | UCI id **145**, DOI 10.24432/C57303 | Overlap/duplicate audit against DA-A2 Cleveland (L-05). Sensitivity analyses only if the audit passes; otherwise exclusion is recorded | CC BY 4.0 **[VERIFIED 2026-10-20]** |

DA-B may be approved, deferred, or refused independently of DA-A. Refusing
DA-B does not block DA-A; approving DA-B does not upgrade either dataset's
role (document 02).

### Explicitly NOT requested in this packet

BRFSS 2015, NHANES, PTB-XL (separate-target tracks needing their own
Gate DA + protocol); official Framingham (controlled access; separate
ethics/access track); AngioCAD (D-021 scope decision first); **all Kaggle
mirrors/copies (prohibited as sources)**; all private cohorts. Naming a
dataset in documents 01–02 for assessment is not an acquisition request.

## 2. Prerequisites that must be true before any download

| # | Prerequisite | Evidence required | Status today |
|---|---|---|---|
| G1 | Named human Gate DA authorization (P-2) listing DA-A (and DA-B if granted) verbatim, with authorizer name/role/date | Signed entry appended to `docs/DECISIONS.md` or equivalent reviewed record | **OPEN — this packet is the request** |
| G2 | Provisional target T1 acknowledged as *provisional* (P-1 still pending; Gate PT will freeze it) | Authorization text states acquisition is target-conditional and no target claim is made yet | OPEN (depends on G1 wording) |
| G3 | Licence re-verification at acquisition time | Download-day snapshot: licence page text/URL, dataset page, DOI, file list, sizes, date, acquirer — stored with the audit log (out of git if it embeds data; the *snapshot metadata* may be committed) | Not started (2026-10-20 readings in document 01 are preparatory, not substitutes) |
| G4 | Storage location confirmed ignored & local (see §3) | `git check-ignore` output recorded for the chosen path before first download | Not started |
| G5 | Read-only audit plan + auditor named (see §4) | Named auditor(s); audit output template = updated documents 01/03 tables + counts | PROPOSED in this packet |
| G6 | $0 confirmation | No account, card, fee, or paid tier is required for UCI public downloads as listed | VERIFIED as listed 2026-10-20 (public download, no application); re-confirm at download |
| G7 | Environment capability | A team local environment that can reach `archive.ics.uci.edu` (this Arena sandbox cannot fetch dataset hosts directly) and run the audit with pinned, approved tooling | **UNVERIFIED** — to be confirmed by the named acquirer; no tooling install is authorized by this packet |

## 3. Local storage rules (binding if Gate DA opens)

1. **Location:** repository-root `/data/` tree only (e.g. `data/raw/uci-412/`),
   which is git-ignored (`/data/` in `.gitignore`, alongside `**/datasets/`,
   `**/raw_data/`). **Warning:** dataset `.xlsx`/`.csv`/`.data` files are
   *not* ignored by extension — placing them anywhere else in the repo
   (especially under `research/`) risks accidental commit. Verify with
   `git check-ignore -v <path>` **before** downloading, and `git status`
   immediately after.
2. **Never committed:** raw or processed patient-level data, model
   artifacts, weights (DATA_POLICY.md). No Git LFS by default (Phase 0
   §7.4). No upload to any third-party/AI service.
3. **Read-only originals:** acquired files are kept byte-identical;
   SHA-256 recorded at download; any cleaned/derived file is a separate
   artifact with its own hash + generating code version (that derivation
   step belongs to Gate PT-approved work, not the Gate DA audit).
4. **Access:** named team members only, on local machines; no shared
   drives/cloud sync of patient-level files without a separate human
   decision. These are de-identified public benchmark data — they are
   still handled as patient-level research data, and re-identification
   is prohibited (UCI-45 identifiers are dummy-replaced at source; do
   not attempt linkage).
5. **Retention/deletion:** recorded in the audit log; deletion, if ever
   required, is a named-human act with a dated note. Nothing here creates
   a retention *policy* — Q-INT/privacy items stay open (document 07).

## 4. Verification steps the read-only audit must perform (in order)

For each approved dataset, producing a written audit report (the future
M2 deliverable — **not** part of this PR):

1. **Provenance & licence snapshot** (G3) + SHA-256 of every acquired file;
   confirm file list/sizes against the official page; record discrepancies.
2. **Schema & dictionary inspection:** verbatim feature list, types,
   units, categorical codings, label coding — resolving H-04 (incl. the
   DS-2 54/55/56 count and each UCI-45 cohort's 14-feature alignment,
   re-derived from the unprocessed files, not assumed).
3. **Counts:** rows, patients (as far as identifier-free data allow),
   outcome events per class, per site — reported separately, never as a
   single inflated "n" (L-04 discipline).
4. **Missingness/completeness:** per feature × per cohort; Switzerland/VA
   against pre-registered completeness rules *proposed by the audit for
   Gate PT to freeze* (the audit describes; it does not set modelling
   rules).
5. **Duplicate/overlap screening:** exact + near-duplicate matching on
   shared stable features within UCI-45, across its cohorts, vs Statlog
   (if DA-B2), and DS-411↔DS-412 identity confirmation (L-04/L-05).
   Publish counts and the resolution rule proposed for Gate PT.
6. **Target verification:** verbatim label definitions vs acquired coding;
   H-01 threshold ruling evidence (can exactly-50% records be identified?
   do raw stenosis/per-vessel fields survive?); H-02 binarization map.
7. **Feature-availability audit:** per-feature timing ruling table
   (knowable before the angiography decision: yes/no/unknown + evidence)
   closing L-01/L-02/L-03/L-06/L-07/L-08 as *audit findings* for Gate PT
   to rule on; `oldpeak` unit and all DS-2 lab/echo units resolved from
   the acquired dictionary or left explicitly UNVERIFIED.
8. **Descriptive-only outputs:** the audit may report counts, missingness,
   coding, and availability (these write the protocol). It must **not**
   fit models, select features by outcome association, tune, calibrate,
   generate explanations, or evaluate performance — outcome-linked
   exploration intended to choose features/models is Gate PT territory
   (Phase 0 §R2-5.1).

## 5. Approval requests (for named humans to grant, refuse, or amend)

| Req | Requested decision | Decision-maker | Effect if granted |
|---|---|---|---|
| R-DA-1 | Authorize acquisition + read-only audit of **DA-A1 + DA-A2** exactly as specified (§§1–4) | Named human data-access authorizer (P-2/D-031) + supervisor awareness | M2 audit task may be *scheduled* as a separate authorized task (document 08) |
| R-DA-2 | Authorize, defer, or refuse **DA-B1/DA-B2** for the audit-only purposes stated | Same as above | Scopes the overlap/T2-option audits; refusal is recorded, not worked around |
| R-DA-3 | Confirm local storage rules §3 and name the acquirer + auditor(s) and their environment (G7) | Same as above + backend/research lead for environment | Acquisition may proceed locally, out of git |
| R-DA-4 | Acknowledge that Gate DA grants **no** modelling permission: Gate PT (P-3, supervisor-approved frozen protocol, document 05 outline) must follow the audit before any fitting/selection/tuning/evaluation | Supervisor (P-3 owner) | Prevents gate-skipping; M3 remains blocked |
| R-DA-5 | Note unresolved items that Gate DA does **not** close: P-1 target freeze, clinician wording (P-4), external-validation claims (P-5, NOT MADE), D-021 (AngioCAD), contract Q1 real-schema decision | Recorded acknowledgement | Keeps the pending register honest (document 07) |

**Approval checklist (all boxes empty = Gate DA closed):**

- [ ] R-DA-1 granted for DA-A1 (UCI-412) — authorizer/date: ______
- [ ] R-DA-1 granted for DA-A2 (UCI-45, four cohorts) — authorizer/date: ______
- [ ] R-DA-2 decision recorded for DA-B1 (UCI-411) — grant / defer / refuse, date: ______
- [ ] R-DA-2 decision recorded for DA-B2 (Statlog-145) — grant / defer / refuse, date: ______
- [ ] R-DA-3 storage + named acquirer/auditor + environment confirmed — date: ______
- [ ] R-DA-4 Gate PT acknowledgement recorded — date: ______
- [ ] R-DA-5 non-closures acknowledged — date: ______

## 6. What happens if Gate DA is refused or partially granted

- Refusal of DA-A: the research track pauses at documentation. No
  substitute dataset (Kaggle, mirrors, private data) may be acquired
  instead — substitution would violate the provenance rules that motivated
  the refusal path. Backend/database milestones are unaffected.
- Partial grant (e.g. DA-A1 only): the audit proceeds for that dataset
  only; Strategy B external validation is postponed until a second
  independent cohort is authorized and audited, and all reporting uses
  internal-validation language only.
- Any change to the exact dataset list requires an amended authorization.
  Downloading a dataset "because it was mentioned in a paper" is never
  authorized.
