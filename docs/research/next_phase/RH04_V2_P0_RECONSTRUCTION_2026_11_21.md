# P0 reconstruction — what the hosted CI runs actually produced

**Status: MEASURED / DERIVED. No inference is presented as fact; every claim below
is marked either `MEASURED` (computed here) or `DERIVED` (forced by a measured
digest equality plus the reviewer's log counts).**

Inputs used, all independently supplied by the independent reviewer:

| Fact | Value |
|---|---|
| PR #138 head reviewed | `2469dc6063545e7b936e19c609bafc0bd64572d2` |
| CI run | `45021505713` |
| Python 3.11 job | `2 failed, 1840 passed, 2 skipped, 19 errors` |
| Python 3.12 job | `1852 passed, 2 skipped, 9 errors` |
| 3.11 V2 pack digest | `84179f839a261f20be18a632984888767cb32bf1fea836052adf0644134a4b57` |
| 3.12 V2 pack digest | `0a8bd8a63dfcb5c6df5a63ae8d0339ae1a0fc60382d4c32623b9db8e5e05c0bd` |
| 3.11 classifier failure | `test_cli_under_a_forced_dispatch_is_fail_closed_and_labelled[SkylakeX]`, `JSONDecodeError` on empty subprocess stdout |

## 1. The metadata experiment (item 2 of the review)

`generate_candidate_pack()` embeds `platform.python_version()` and
`platform.python_implementation()` in `pack["generation"]`, and `pack_digest()`
hashes the **entire** document. I varied only those two fields on the committed
candidate (numerical cases untouched):

| Variant | Complete pack digest | Meets CI 3.11 | Meets CI 3.12 |
|---|---|---|---|
| committed as-is (`3.11.2`) | `b74f781d…595f2` | no | no |
| metadata → `3.11.18` | `76d6771529f8be49fa2a7c2c3d5fd81382f0fa499f37ca9a6da52a89b8cbf60b` | **no** | no |
| metadata → `3.12.16` | `0a8bd8a63dfcb5c6df5a63ae8d0339ae1a0fc60382d4c32623b9db8e5e05c0bd` | no | **YES, exact** |

`MEASURED`. The `3.12.16` row reproduces the hosted Python 3.12 digest **exactly**.

### What that does and does not prove

A SHA-256 of a canonical JSON document is collision-resistant. An exact match
therefore implies that **every byte of the 3.12 document was identical to mine
except the two metadata fields I changed**. Since `pack["cases"]` is the only part
carrying the numerical payload, and I changed none of it, this is forced:

> **DERIVED: on the hosted Python 3.12 runner, all 29 expected cases were
> bit-identical to my local class-A generation.** The 3.12 runner is on the same
> numerical side as this host. It is **not** V2 class B.

This directly refutes my own §5.5/§5.6 claim that "the hosted runner is class B".
That claim was an inference from a *local* forced-`Sandybridge` run, and it was
wrong. The `0a8bd8a…` match is the correction.

## 2. Why Python 3.11 differs

The 3.11 digest is **not** reproduced by either of my two known payload classes
with `3.11.18` metadata:

| Payload | + metadata `3.11.18` | Meets CI 3.11 |
|---|---|---|
| class A (committed) | `76d67715…` | no |
| class B (`Sandybridge`) | `f86ed8f1…` | no |

`MEASURED`. So the hosted 3.11 payload is a **third** distinct numerical outcome
that I have not reproduced. This is a genuine, unresolved finding — and it is
exactly the kind of host-specific divergence the V2 work exists to eliminate.

### A second, independent derivation that constrains where the divergence is

The reviewer's 3.11 job reports **9 new V2 errors**; 3.12 reports **9 errors too**,
but on 3.12 the cases were bit-identical (so its 9 must be a *different* cause —
see §3). My module has exactly **9** tests that consume a generation fixture:

`test_generate_and_validate_round_trip_is_exact`,
`test_a_one_ulp_edit_to_a_v2_expected_value_fails_validation`,
`test_validation_rejects_a_tampered_binding`,
`test_validation_rejects_a_tampered_case_count`,
`test_validation_rejects_a_renamed_case`,
`test_validation_rejects_a_reordered_inventory`,
`test_validation_rejects_protocol_drift`,
`test_pack_digest_is_stable_for_the_same_content`,
`test_cold_process_check_mode_replays_the_committed_candidate`.

`DERIVED: on 3.11 the failure mechanism was the fixture guard rejecting an
unlisted digest` (7 tests) plus `validate()` failing structurally on a pack whose
`protocol` / `bindings` / `requests` also carry host-conditional content, and the
cold `--check` failing closed — consistent with every one of the 9 errors being in
my module and no other new errors appearing.

**Crucially:** on 3.12 the same 9 errors occurred even though the cases matched.
That means the 3.12 failures were **not** numerical at all — they were the
fixture guard rejecting a digest that differs only because
`platform.python_version()` is `3.12.16`. In other words:

> **The Python-version metadata inside the digested document converts a
> bit-identical numerical result into a test failure.** That is a design defect in
> my candidate, and it is the single most important thing this review found.

## 3. Failure-signature reconciliation (correcting my earlier claim)

My comment `#7080510290` said the CI red was "identical on main". That was wrong
for these reasons, now stated explicitly:

| Claim I made | Correction |
|---|---|
| "2 failed, 1849 passed, 10 errors on the PR matches CI" | **False.** CI 3.11 is `2 failed, 1840 passed, 19 errors`; CI 3.12 is `0 failed, 1852 passed, 9 errors`. Neither matches. |
| "The failing identities are identical" | **Partly false.** The 2 failures in 3.11 include `test_cli_under_a_forced_dispatch_is_fail_closed_and_labelled[SkylakeX]` (`JSONDecodeError`, empty stdout) — a test I never saw fail locally. My local classifier failure was `test_pre_replay_snapshot_is_labelled_and_not_used_for_the_verdict`. **Different tests, different mechanisms.** |
| "The hosted runner is class B" | **False.** Proven by the exact `0a8bd8a…` match on 3.12. |

What *does* survive from the A/B work, and should not be discarded:

* `main` `5549b31` with no V2 code at all, under a forced class-B dispatch, fails
  `test_golden_replay` and produces the same 10 `test_rh04_report_assembly.py`
  cascade errors. That is a real pre-existing class-B defect. But it is a
  **local-forced-dispatch** result, and it is **not** what the hosted jobs hit.
  The hosted jobs' 10 cascade errors on 3.11 are the canonical V1 pack mismatch
  from that runner's genuine kernel, not a class-B reproduction of my making.

So: a pre-existing V1 kernel sensitivity exists, **and** my candidate has its own
independent defects. Both are true; I previously reported only the first.

## 4. Consequence for the design

The defect is architectural: **one digest is being asked to do five different
jobs.** It must be split, which is what the review asks for and what §5 of the
corrected protocol specifies:

| Concern | Must change when | Must NOT change when |
|---|---|---|
| canonical semantic reference | protocol/bindings/requests/inventory/routes/edits/expected responses change | interpreter patch, OS, kernel, BLAS |
| strict reference-content digest | any protected content changes | metadata changes |
| generation provenance | always recorded | never gated on |
| environment metadata | informational | never a failure cause |
| raw artifact integrity | file bytes change | intentional, declared regeneration |

The immediate, concrete bug to remove: `platform.python_version()` must not be
inside the digested document, and a test must enforce that.

## 5. What remains unknown (and is reported as unknown)

| Item | Status |
|---|---|
| Hosted Python 3.11 numerical payload | **NOT REPRODUCED** — a third class, digest `84179f83…` |
| Whether 3.11's divergence is numerical or a structural/metadata difference | **NOT DETERMINED** — requires the 3.11 pack contents, which the logs do not provide |
| Cause of `[SkylakeX]` `JSONDecodeError` on 3.11 | **NOT DETERMINED** for the hosted job; SIGILL-class signal death is the leading hypothesis from #137/#134, unproven |
| Native Windows behaviour | **NOT MEASURED** |
| Whether an all-classes single exact digest is achievable | **OPEN** — addressed by the deterministic upstream candidate |
