# RH-05 preparation handoff

**Document ID:** CAI-RH05-HANDOFF-v1
**Status:** HANDOFF. RH-05 is **not reopened, not re-scoped and not modified** by
this document. No RH-05 acceptance state changes here.

---

## 1. The most important fact first

**RH-05 engineering acceptance is already CLOSED** (Issue #121), at tested source
`64f34e4cb8580ced461237ffa46ba0a91e8fc1c5`.

That closure must **not** be treated as covering the future RH-04 delivery SHA.
Per the standing rule recorded in the manuscript draft itself: *"Do not re-label
RH-05's historical tested SHA as the later manuscript/merge SHA."* The same
applies to a new RH-04 release SHA.

| | historical | required for the new release |
|---|---|---|
| tested SHA | `64f34e4…` | the eventual RH-04 delivery SHA |
| Windows native | 3.12.9 / NTFS, 8/8 | **must be re-measured** |
| focused suite | 220 passed / 2 skipped | **must be re-measured** |
| full suite | 2909 passed / 3 skipped | **must be re-measured** |
| cross-OS | `09b8954…` | new comparison at the new SHA |

## 2. RH-05 engineering evidence that already exists

Reusable as *methodology and precedent*, not as evidence for a new SHA:

1. **A native-Windows compatibility validator** —
   `scripts/validate_ai_windows_compat.py`, producing eight named stages including
   `windows_ntfs_win32_security_descriptor_dacl`.
2. **A strict Linux/Windows synthetic comparison** — the reviewed
   `ai.report_comparison` classification, which separates invariant, within
   tolerance, environment, artifact-byte and derived-digest differences rather
   than collapsing them into "differs".
3. **A privacy/refusal suite** — `test_offline_research_boundary`,
   `test_research_facade`, `test_diagnose_fixture_replay`,
   `test_offline_fixture_pack`, `test_private_directory_creation_regression`.
4. **A documented skip policy** — three platform-bound skips, each named with a
   reason and a compensating native test, never silently absorbed.
5. **An exact-source evidence discipline** — every count attributed to the SHA
   that produced it, with PR-head CI never relabelled as a merge-SHA run.

## 3. What can be prepared independently of RH-04 acceptance

These do not depend on the RH-04 gates closing:

- **The Windows command set.** RH-05's PowerShell/native steps can be rewritten
  against the current tree today; only the *execution* waits for a final SHA.
- **The refusal-scenario matrix.** RH-05 wants ≥3 rejected scenarios per route.
  RH-04's V2-07 negatives (wrong reference digest, >29 cases, reordered/duplicate
  cases, non-calibration drift, planted tolerance, solver mismatch) are directly
  reusable as candidates — subject to RH-05's own review, not assumed inheritable.
- **The dependency reconciliation.** `RH04_VERIFICATION_DEPENDENCIES_PLAN` already
  names the reviewed requirement files; RH-05 can adopt them unchanged.
- **The dual-run workflow.** Specified in
  `RH04_V2_DUAL_RUN_AND_ROLLBACK_2026_11_21.md` §1 and independent of RH-04's gates.
- **The clean-delivery-line plan.** If the SHAP remediation is approved, RH-05's
  Windows evidence should be run against the *replacement* line, not the review
  branch. Deciding that now avoids a wasted native run.

## 4. What requires the final accepted RH-04 release

| RH-05 item | blocked on |
|---|---|
| native Windows full-suite run | a frozen delivery SHA |
| focused 8-module suite | a frozen delivery SHA |
| strict Linux/Windows comparison | two environments at one SHA |
| exact-head CI evidence | owner authorization + frozen SHA |
| post-merge smoke | an actual merge (not performed here) |

## 5. Remaining RH-05 deliverables and exit criteria

Unchanged from the charter (`AI_RESEARCH_PROTOTYPE_COMPLETION_CHARTER_2026_11_19.md`
§RH-05):

**Deliverables**
1. Reproduce the accepted synthetic pipelines at **exact recorded SHAs** in clean
   environments.
2. Positive and ≥3 rejected scenarios per applicable route: route/panel mismatch,
   invalid value/unit, unknown/unverified provenance, tampered bundle, leakage,
   missing calibration/XAI, privacy/path redaction.
3. Expected safe abstention/error behaviour recorded, not merely "no crash".
4. Source-SHA / key separation demonstrated.
5. Report schema and checksum verified.
6. Backend mock contract confirmed with no production switch.
7. Native Windows NTFS 8/8 where applicable.

**Evidence required**
- commands, OS, Python and dependency versions;
- result JSONs and digests;
- pass/fail/skip/error/exit counts;
- GitHub CI at the exact head;
- local Windows at the exact head and post-merge smoke;
- every skip with a reason and a compensating native test.

**Exit criteria**
Reproducible synthetic success and refusals; credible failure handling;
negative-path evidence; no unauthorized loading; independent re-run instructions;
no protected records or signing keys in remote CI or PRs.

## 6. What this handoff does not do

- It does not reopen Issue #121 or change RH-05's closure.
- It does not claim any historical evidence applies to the new release SHA.
- It does not perform application integration, dataset access or clinical work.
- It does not begin RH-05 execution. The next RH-05 action after RH-04 acceptance
  is to **re-measure**, not to cite.
