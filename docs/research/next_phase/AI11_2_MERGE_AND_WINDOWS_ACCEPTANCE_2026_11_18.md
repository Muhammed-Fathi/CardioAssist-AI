# AI-11.2 — merged native Windows engineering acceptance and reference-comparison disposition

**Date:** 2026-11-18  
**Evidence classification:** SYNTHETIC_TEST_NOT_CLINICAL_EVIDENCE  
**Source:** Maintainer-provided Windows PowerShell 5.1 results, independently checked against GitHub PR/tree metadata. The author of this docs-only closeout **did not** execute the Windows tests.  
**Status proposed for tracker:** `MERGED_ENGINEERING_COMPLETE_SYNTHETIC_ONLY` / `LOCALLY_ACCEPTED_ENGINEERING_ONLY`, subject to human review of this documentation PR.

## 1. Exact commit and product boundary

| Event | Immutable identity |
|---|---|
| Accepted implementation | [PR #85](https://github.com/Muhammed-Fathi/CardioAssist-AI/pull/85) |
| Exact reviewed PR head | `f5f5d5e9b08f5f930feb3275206c337545d7f318` |
| **Merged `main` SHA** (all post-merge checks) | `b49df50eb509b6daa8dad016f77c8cd6bfde7335` |
| Prior accepted scope | [PR #84](https://github.com/Muhammed-Fathi/CardioAssist-AI/pull/84) |
| Explicit provider boundary | Application `MOCK_SYNTHETIC` only; no HTTP real model activation |

AI-11.2 adds a **source-derived read-only, versioned catalog/export**, a JSON Schema and contract/negative tests: five registered slots, two eligible **offline synthetic-only**, two blocked and one locked external target. `registry_declared_capabilities` are policy metadata, **not** artifact-verified model abilities. The catalog loads no model, grants no credential, allows no real/patient data, and does not change clinical or governance decisions.

## 2. Pre-merge exact PR-head evidence

| Check | Observed maintainer or hosted result |
|---|---|
| Hosted GitHub CI | **7/7 jobs succeeded** (contract; audit x2; mock backend x2; synthetic runner x2) |
| Native Windows dependencies | `pip check` PASS |
| Focused tests | **178 passed**, 0 failed, **51.22 s** |
| Native Windows full suite | **2,553 passed, 3 skipped, 0 failed**, exit 0, **5,853.69 s** with `-W error` |
| Windows-native ACL/security | 8/8 PASSED |
| Legacy synthetic demo | 8/8 PASSED |
| External catalog reproducibility | Two byte-identical exports, **5 entries**, SHA-256 `5b0dbb39bf9e56238199f73ddb7936af12a1e8237ff527c36acad93a098cf3ec` |

The three skips reflect Windows-specific cross-platform tests separately covered by native DACL verification. **The full suite was run at the PR head, not the later merge SHA.** No claims about hypothetical future releases follow from this evidence.

## 3. Post-merge native Windows smoke on exactly `b49df50eb509b6daa8dad016f77c8cd6bfde7335`

The maintainer checked that the merge was on remote `main`, verified a **detached clean worktree** at the exact SHA and used an existing external pinned Python environment.

| Gate | Observed result |
|---|---|
| Dependencies | PASS |
| Post-merge focused tests | **57 passed**, 0 failed, **33.16 s**, exit 0 |
| Protected sources | Four hashes + 25-paper status census **PASS** |
| Native Windows ACL/security | **8/8 PASSED** |
| Eight-stage synthetic demo | **8/8 PASSED** |
| Two catalog exports | 5 entries, 2 active synthetic registrations, byte-identical, SHA-256 above |
| JSON Schema 2020-12 against actual export | **PASS** (re-run via standalone Python file after a PowerShell quoting error) |
| Generated offline synthetic evidence | `SYNTHETIC_E2E_COMPLETE`, 8/8, states `ABSTAIN`, `ERROR`, `SYNTHETIC_RESULT`, `UNAVAILABLE` |
| **Second evidence pack generated at same merge SHA** | **`MATCH`**, **0 differences**, **`exact_file_bytes_equal=true`**, exit 0 |
| Repeated source identity | Both `git_commit` values exact SHA above, both `ai_tree` equal, both source trees clean |
| Replay pack SHA-256 | `ff96bd66a9059532486a0b0ac0a5d80fd51ec8e2e67e3a7efbd1a8550a45c725` |
| Worktree at end | Clean |

**Scope of replay claim:** this establishes **bitwise repeatability of two evidence-pack executions on the same Windows environment with the same code**. It is not a claim of identical artifacts, computation or benchmark validation across Windows and Linux. The initially attempted `python -c` schema check failed due to argument quoting, was properly retried, and then passed; the first failed command is not hidden.

## 4. Released historical Linux reference remains STRICTLY `DIFFERENT`

`python -W error -m ai.research_evidence --compare <postmerge-pack>` compares with the **committed historical Linux evidence reference**, not a second freshly generated pack of the same commit. This strict comparison **returned `DIFFERENT` / exit 1** with **70 reported differences**:

| Difference category | Count |
|---|---:|
| Numeric `within_tolerance` | 53 |
| `environment` | 9 |
| `artifact_bytes` | 4 |
| `derived_digest` | 3 |
| **`invariant_mismatch`** | **1** |
| **Total** | **70** |

The sole invariant mismatch is at `/reproducibility/source/ai_tree`. The committed reference records `git_commit=b287713edda74c68e4793b80efef78cb5fb2ca39` with `ai_tree=9d4ecc81816b1ffca80f8a5f36a724375ec536ab`. GitHub comparison from that reference SHA to the merged `b49df50eb509b6daa8dad016f77c8cd6bfde7335` finds exactly **one added file under `ai/`: `ai/research_catalog.py` (129 lines)**; no pre-existing AI implementation file was edited. Thus the source tree is genuinely different, and the unchanged comparator is **correct** to flag a version-identity mismatch. The other 69 listed differences are allowed comparison categories, but that does **not** turn the overall historical cross-platform comparison into `MATCH`.

**No weakening of comparator/allowlist, no rewriting of signed/trusted artifacts, no replacing the historical Linux reference, no suppressing or re-labeling `DIFFERENT`.** A new same-revision Windows/Linux comparison would require independently trusted equivalent-source evidence on each OS and is outside this narrow closeout.

## 5. Decision, scope boundary and next research work

- **Engineering decision:** source-derived catalog, read-only handoff and mock-boundary controls meet the reviewed synthetic-only AI-11.2 acceptance on exact merged SHA. Close the **AI-11.2 engineering slice**, with the Linux reference distinction explicit. Parent **AI-11** offline/synthetic engineering scope is complete with AI-11.1 + AI-11.2; scientific evaluation remains **NOT_ESTABLISHED**.
- **The application backend remains `MOCK_SYNTHETIC` only.** No new real model provider, patient service or `/v1` contract was activated.
- **Unresolved research controls remain:** UCI-412 `SCIENTIFIC_HOLD` and feature/timing semantics, D-048, Gate PT and the locked Hungary external target. No claim of clinical accuracy, transportability, or care recommendation.
- Separate AI-9 (clinical vs labs research), AI-10 (external validation), and remaining AI-12 academic reporting/gated evidence work must be scoped and evaluated independently. The local acceptance status **does not approve real-data execution**.
- The tracker updates both the legacy top-level and current nested `last_locally_accepted_*` pointers to AI-11.2/`b49df50eb509b6daa8dad016f77c8cd6bfde7335`, avoiding an inconsistent historical pointer. There are no code/model/CI/security changes in this PR.

**Change control:** documentation-only `docs/research/ai_master_progress.json` and this ledger. Human review required. This documentation PR is **not** a replacement for Windows test execution and must not be self-merged.
