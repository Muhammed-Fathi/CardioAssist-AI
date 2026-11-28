# C1 rollback policy — proposed, NOT owner accepted

Candidate inspected: `3d338a23d377f1dc3174d803892dd1ab65bf1ff6`.
PR #144 remains OPEN/DRAFT. C1 acceptance and C2 authorization remain pending.

## Native Windows evidence

Owner's native Windows verification reported 1157 backend/contract tests,
711 audit tests and 396 UCI-412 tests passing. Legacy HTTP seed, upgrade,
legacy preservation, schema verification and synthetic enrollment/restart
passed. Empty-C1 downgrade/re-upgrade passed.

Populated C1 downgrade failed with exit 1 at 20261126_06 -> 20261126_05:
SQLite CHECK ck_identity_key_check_purpose rejected the batch INSERT of
existing pepper_binding rows. The original failed result remains historical
evidence; do not relabel it a pass. Do not repair or retry that same database.

Exact-head hosted CI: backend 45908251153, contracts 45908255357,
audit 45908259230, synthetic 45908264226, all successful. These results
belong only to 3d338a2, not a later patch.

Windows experiments: 1093 passed, 9 failed, 4 skipped, 5 errors.
Failures confined to the unchanged RH-04 Issue #132 environment classifier
test module, including invalid Windows repository path handling and an
RTLD_NOLOAD AST assertion requiring an unavailable platform flag. These
remain separate unresolved research portability findings; no waiver,
research edits or AI gate change is implied.

## Proposed supported rollback semantics

- Online in-place downgrade only in a disposable database with no C1 state;
  preserve all legacy monitoring rows through upgrade/downgrade/re-upgrade.
- Refuse before DDL if any of the sixteen C1 tables contains a row.
  A previous schema cannot preserve the new binding invariant. Refuse offline
  downgrade generation rather than emit unchecked destructive SQL.
- Do not delete key checks, rebind keys, stamp revisions, clear attempts,
  discard replay records, or disable constraints to force downgrade success.
- For a populated operational database: stop all writers, preserve the
  current database, and use a separately verified SQLite-consistent
  pre-upgrade backup and matching original application/configuration.
  Restore into a new isolated location, validate integrity, foreign keys,
  exact schema and compatible application startup before any cutover.
  A pre-upgrade restore can omit subsequent writes; assess and explicitly
  accept that recovery point before any cutover. Never overwrite the only
  copy of a current database. No automatic production rollback is authorized.
- For a populated disposable verification database: prove controlled refusal
  leaves the full schema, every row and revision unchanged, and prove
  subsequent startup and authenticated operation with the original settings.
  This is a different acceptance invariant from successful populated
  in-place downgrade; it requires explicit owner approval.

## Required evidence before acceptance

1. Actual old candidate failure (already observed on Windows).
2. New guard regression and unchanged full database snapshot; exact-head
   successful empty C1/legacy preservation round-trip.
3. Native Windows focused verification and full candidate regression/CI.
4. Owner decision explicitly accepting the proposed rollback invariant
   instead of successful populated in-place downgrade. Backup restoration
   needs separate operator verification; this document does not certify it.
5. Append exact evidence and preserve outstanding research failures.
   No merge, gate closure, C2 work or research authorization is implied.

The reviewer patch is proposed and has not been executed by the reviewer.

---

# Addendum — owner decision recorded (appended 2026-11-27)

Append-only. The proposal above is preserved **verbatim** as written before the decision,
including its "proposed, NOT owner accepted" heading and its `3d338a2` candidate reference
and all of its `NOT_RUN`/pending evidence items. This addendum records what the owner
actually decided; it does not edit the proposal, and it does not retro-fit the proposal's
evidence list.

## Decision record

| Item | Value |
|---|---|
| Decision ID | `RB-C1` (see `TERM1_DECISION_REGISTER.md` Appendix A) |
| Status | **OWNER_RATIFIED** |
| Date | 2026-11-27T01:53:34Z |
| Source | `ACCEPT-TERM1-C1-BOUNDED-PROTOTYPE-BASELINE`, PR #144 [comment 7207660039](https://github.com/Muhammed-Fathi/CardioAssist-AI/pull/144#issuecomment-7207660039) |
| Scope | C1 rollback semantics for term1-prototype; no C2, C3, C4 or `main` implication |

## What the owner approved, exactly

> I approve the safe rollback policy. In-place downgrade is permitted only on disposable
> databases without C1 state. Populated operational databases require verified backup
> restoration and explicit recovery-point acceptance.

Recorded as three separate rules, because they have three separate implications:

1. **In-place downgrade** is permitted **only** on a disposable database with **no C1
   state**. Populated disposable verification databases must additionally prove that
   refusal leaves the full schema, every row, the revision, the foreign keys and integrity
   unchanged, and that the application then starts and operates with the original settings.
2. **Populated operational databases** require **verified backup restoration**, not a
   destructive in-place downgrade. Restoration must preserve the current database (never
   overwrite the only copy), restore into a new isolated location, and validate integrity,
   foreign keys, exact schema and compatible application startup before any cutover.
3. **Explicit recovery-point acceptance** is required. A pre-upgrade backup restore can
   omit subsequent writes; that recovery point must be assessed and accepted by the owner
   before any cutover. **No** automatic production rollback is authorized.

## What this decision does NOT certify

* It is **not** a live-recovery certification. The owner's isolated legacy backup-restore
  test exited 0; that is a restoration *test*, not an operational recovery drill.
* It does **not** authorize deleting key-check rows, rebinding keys, stamping revisions,
  clearing attempt counters, discarding replay records, or disabling constraints to force a
  downgrade to succeed. Those remain prohibited.
* It does **not** make a populated in-place downgrade a supported operation, and it does not
  convert the observed populated-downgrade exit 1 into a defect. That exit 1 was the
  correct, expected refusal.
* It does **not** close B-15/B-16 (hosted CI and native Windows for this closure branch).

## Evidence bound to this decision

| Evidence | Result |
|---|---|
| Original populated downgrade failure (`20261126_06 → 20261126_05`, SQLite `CHECK ck_identity_key_check_purpose`) | Preserved as historical failure; not relabelled |
| Guarded refusal regression + unchanged full schema/rows/revision snapshot | Passed in the owner's Windows retest; preservation check exit 0 |
| Empty-C1 / legacy-preservation round-trip on a disposable database | Exit 0 |
| Isolated pre-upgrade legacy backup restore | Exit 0 (test only) |
| Migration head unchanged by the C1 closure branch | `20261126_06`; no migration added or altered |

No migration, guard, regression or policy file is modified by this addendum.
