# CardioAssist AI — Protected Exploratory Research

**No real-data experiments have been run or authorized yet.** The merged M2b.2 intake and preprocessing tools were checked using synthetic-only fixtures, not CAD labels or performance estimates.

## First proposed internal run (D-047 / D-046-EP)

- [Research protocol proposed for maintainer ratification](../../docs/research/gate-pt/02_d047_internal_exploratory_cleveland_PROTOCOL_PROPOSED.md).
- [Human decision record](../../docs/DECISIONS.md), D-047 (proposed until explicit acceptance).
- [Pinned proposed machine-readable candidate model settings](cleveland_d047_exploratory_plan.v0.1.json) — fixed model grids, seeds, target and security constraints; proposal only, runner must still be authorized.
- [Next engineering assignment — Issue #32](https://github.com/Muhammed-Fathi/CardioAssist-AI/issues/32): guarded local training runner and synthetic-only CI; do not execute on real datasets in a remote agent.
- [Local authorization manifest template](internal_exploratory_authorization.template.json) — copy into ignored `data/manifests/internal_exploratory_authorization.local.json` ONLY after human governance approval; supply real source hash and protocol SHA privately, never in PR payloads.
- [Internal exploratory report template](../../docs/research/gate-pt/03_internal_exploratory_RESULTS_TEMPLATE.md) — placeholder only. No made-up results.

### Roles

**Remote Arena Agent:** prepares local-runner implementation and synthetic-only tests, may push code PRs, **never consumes real source patient rows**, never invokes real model fit/evaluation on remote systems.

**Human maintainer's Windows environment:** sole operator for authorized local dataset training after a signed/scoped D-047 authorization and guarded preflight. Preserve original bytes and all protected artifacts under Git-ignored `data/`. Do not print/upload/commit individual observations, per-row predictions, raw clinical text or model artifacts.

**Assistant/research reviewers:** scrutinize method and aggregate-only outputs, require leak controls, review source/target semantics and compare prespecified model families. No supervisor signoff may be inferred.

Current scope: **processed Cleveland only, 303** original records, source-specific historical CAD present/not-present classification with a candidate 5-field model and bounded nested CV. UCI-412 is reserved for a *separate future* internal study if authorized; UCI-411 and Statlog remain audit-only; no pooling, subgroup publication or clinical claims.

The proposed D-047 activation is not a new audit permission, and old D-046 local audit manifests explicitly keep model fitting disabled. The new runner must fail closed unless its **separate** exploratory authorization is recorded. Formal Gate PT P-3 remains CLOSED.
