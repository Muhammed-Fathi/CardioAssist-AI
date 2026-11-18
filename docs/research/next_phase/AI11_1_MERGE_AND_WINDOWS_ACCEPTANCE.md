# AI-11.1 Closeout — PR #79 merge and native Windows evidence

**Status: MERGED; PRE-MERGE WINDOWS ENGINEERING GATE PASSED; POST-MERGE LOCAL RECHECK PENDING.** Research-only / synthetic-only. This is a docs-only tracking proposal, not a governance act. Verified GitHub merge on 2026-11-18; test output was supplied by the maintainer in the conversation, not executed in this documentation PR.

| Evidence | Recorded value |
|---|---|
| Implementation PR | [#79](https://github.com/Muhammed-Fathi/CardioAssist-AI/pull/79) |
| Final PR source head | `46d079088a2d6f741ce7d64843c920a420d322fa` |
| Merge SHA | `83f51f67792d55634c3eca4ff150bae732f75e2b` |
| Reviewed scope | Six changed files; synthetic registry, typed facade, demo and regression tests; backend provider remained `MOCK_SYNTHETIC` |
| CI at source head | synthetic experiment runner, contract validation, audit toolchain, mock backend: **4/4 SUCCESS** (GitHub Actions queried independently) |
| Native Windows interpreter | Python **3.12.9**, pre-existing external isolated `AI8W_FullSuite_Venv` |
| Native Windows exact tested revision | Source PR head `46d0790...`, in clean detached `E:\CardioAssist_AI_AI111_PR79` |
| Focused Windows tests | `python -m pytest -W error -q tests/experiments/test_research_facade.py tests/backend/test_inference_provider.py` → **150 passed, zero failed**, exit 0, 50.01 seconds |
| Windows integrity | `pip check` passed; `scripts/verify_sources.py` passed four SHA-256 plus 25-paper census |
| Windows ACL/auth | `scripts/validate_ai_windows_compat.py` **8/8 PASSED**; mechanism `windows_ntfs_win32_security_descriptor_dacl`; includes signing-key protection, tamper/forged-pickle refusal and external evaluation ledger |
| Demo | `python -m ai.research_demo --format text` and `--format json` passed **8/8**, exercised all four statuses; same local canonical digest `d8e6f5d95ac5b1c01a1f5abddc2cca6b4db0fc8d1dd603c5e8194d735c86309e` |
| Clean Git state | The pre-merge detached Windows worktree remained clean |
| Limits | Not a monolithic full-suite Windows pass; no Windows execution **at merge SHA** has yet been reported |

## Open technical findings for AI-12.1

1. The Arena Linux demo reported `0722d728f756e589a3d97b4328e6dc106111835889e6b6387969cf0b0b99b853`, different from the Windows `d8e6f5d...`; cause **unverified**, do not assert cross-OS bitwise repeatability. Compare serialized stage fields/number formatting and numerical dependencies; keep evidence-grade distinctions and preserve strict integrity checks.
2. Running `python -m ai.research_demo` on Windows emits `RuntimeWarning: 'ai.research_demo' found in sys.modules after import of package 'ai'`, consistent with eager imports from `ai/__init__.py`. Address without removing public exports or weakening Python warnings.
3. A separate post-merge native Windows verification at exact merge SHA remains needed for `LOCALLY_ACCEPTED_ENGINEERING_ONLY` to be recorded. Do **not** infer this status from pre-merge execution alone.

## Next executable actions

- AI-12.1 implementation PR (separate): reproducible synthetic-only E2E evidence pack, versioned report/model card, 1-click/repeatable CLI and negative cases, mock-provider contract proof, no offline model serving by FastAPI.
- Follow the recorded repo stage-close policy: clean isolated post-merge worktree pinned to `83f51f67792d55634c3eca4ff150bae732f75e2b`; verify exact head and run focused tests, synthetic demo, source verification and Windows ACL harness, record true outcomes. Do not re-use/rewrite ignored real-data manifests.
- AI-9/AI-10 research/tooling proceed in separate reviewed synthetic-only PRs. UCI-412 `SCIENTIFIC_HOLD`, Hungary locked, no D-048/clinical activation.
