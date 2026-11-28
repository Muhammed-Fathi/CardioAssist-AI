# RH-04 V2 — exact verification commands

**Document ID:** CAI-RH04-VERIFY-v1
**Status:** candidate evidence package. Commands are runnable as written.

Every command below was executed in the review sandbox **except** those marked
`NOT MEASURED`. Nothing here is inferred from a different environment.

---

## 1. Environment construction

The repository already carries reviewed, pinned requirement files. **Do not
invent versions.** The research-verification scope needs exactly two of them.

### 1.1 Linux / macOS (bash)

```bash
python3.11 -m venv .venv-rh04
. .venv-rh04/bin/activate

# Scientific stack + the test-only oracle (both are reviewed, pinned files).
python -m pip install -r research/uci412/requirements.txt \
                       -r research/experiments/requirements-oracle.txt \
                       -r tests/contracts/requirements.txt
python -m pip check
```

Expected on success: `No broken requirements found.`

Measured result in the review sandbox (Python 3.11.2):

```
numpy 1.26.4  scipy 1.15.3  sklearn 1.6.1  mpmath 1.4.1  openpyxl 3.1.5
pip check -> No broken requirements found.
```

### 1.2 Python 3.12 variant

```bash
python3.12 -m venv .venv-rh04-312
. .venv-rh04-312/bin/activate
python -m pip install -r research/uci412/requirements.txt \
                       -r research/experiments/requirements-oracle.txt \
                       -r tests/contracts/requirements.txt
python -m pip check
python -m pytest tests/experiments/test_rh04_v2_reference.py -q
```

**NOT MEASURED.** Python 3.12 was not available in the review sandbox, and this
document does not predict its result. Report the actual counts.

### 1.3 Native Windows (PowerShell)

```powershell
py -3.11 -m venv .venv-rh04
.\.venv-rh04\Scripts\Activate.ps1
python -m pip install -r research\uci412\requirements.txt `
                       -r research\experiments\requirements-oracle.txt `
                       -r tests\contracts\requirements.txt
python -m pip check
```

Then the unified verification:

```powershell
$env:PYTHONPATH = "."
python -m research.intake.rh04_v2_portable_archive research/intake/fixtures/rh04_v2_portable
```

**NOT MEASURED.** No Windows host was available. This is not a "should work"
claim; it is an untested command that a reviewer with a Windows host must run and
report verbatim.

---

## 2. The single supported acceptance command

```bash
cd /home/user/CardioAssist-AI
PYTHONPATH=. python -m research.intake.rh04_v2_portable_archive \
  research/intake/fixtures/rh04_v2_portable
```

**Measured output (Linux, Python 3.11.2):**

```json
{"digest": "891d9e3b2a332c6efc251d97fee25ed46a627ed25b2a089594057b4c9896cdc8",
 "manifest_identity": "293c6e3f6e9aa74f1119a52b56d97af8774a76e90b162a41a222a46a07a63c70",
 "matches_reference": true,
 "n_cases": 29,
 "statuses": {"ABSTAIN": 2, "ERROR": 22, "SYNTHETIC_RESULT": 2, "UNAVAILABLE": 3}}
```

Exit code `0`. Any refusal prints `{"result": "REFUSED", "reason": ...}` and
exits `1`.

**Negative check — this must refuse.** A whitespace-only edit:

```bash
cp -r research/intake/fixtures/rh04_v2_portable /tmp/mut
python - <<'EOF'
p = "/tmp/mut/da_a2_resting_v1.archive.json"
s = open(p).read()
open(p, "w").write(s.replace('"slope": ', '"slope":  '))
EOF
PYTHONPATH=. python -m research.intake.rh04_v2_portable_archive /tmp/mut
```

Measured: `{"reason": "raw archive bytes for 'da_a2_resting_v1' do not match the
manifest; the file identity is enforced before parsing", "result": "REFUSED"}`,
exit `1`.

---

## 3. Test suites

### 3.1 Focused RH-04 V2 suite

```bash
PYTHONPATH=. python -m pytest tests/experiments/test_rh04_v2_reference.py -q
```

**Measured on the delivery tree:** `276 passed` in 775.93 s.

### 3.2 Wider experiments suite

```bash
PYTHONPATH=. python -m pytest tests/experiments -q
```

**Measured**: see the delivery PR body for the exact command and result on the delivery SHA.

The two skips are genuinely platform-bound and are listed explicitly:

```
SKIPPED tests/experiments/test_ai_research_pipeline.py:2175
  Windows-only Win32 SDDL conversion and NTFS directory DACL regression test.
SKIPPED tests/experiments/test_private_directory_creation_regression.py:75
  Requires native Windows NTFS and Win32 SDDL APIs.
```

**No file is ignored, deselected or excluded.** An earlier round reported 35
errors and 1 failure here; those were unexecuted coverage from a missing
`openpyxl`, and installing the repository's own pinned requirements resolved them.

### 3.3 Contract tests

```bash
PYTHONPATH=. python -m pytest tests/contracts -q
```

**Measured:** `306 passed` in 1.35 s. This suite requires `jsonschema`,
`openapi-spec-validator` and `PyYAML` from `tests/contracts/requirements.txt`;
without them it fails to collect, which is how an earlier round mis-reported it as
"not run".

### 3.4 Backend tests

Deliberately **out of scope**. `tests/backend/` needs a database fixture and
belongs to a later roadmap stage. Do not install `alembic` to make it green in
this workstream.

---

## 4. Resident dispatch-class matrix

```bash
for cls in "" SkylakeX Sandybridge Nehalem Haswell Prescott; do
  echo "--- ${cls:-(unset)} ---"
  OPENBLAS_CORETYPE="$cls" PYTHONPATH=. python -m \
    research.intake.rh04_v2_portable_archive \
    research/intake/fixtures/rh04_v2_portable
done
```

**Measured on the delivery tree** — 6 requested classes → 5 distinct resident
classes → **1** digest, all `matches_reference: true`, all exit 0.

**Requested vs *resident* kernel** (resident read from
`threadpoolctl`, which reports the library the process actually loaded):

| requested | resident | digest | match |
|---|---|---|---|
| (unset) | SkylakeX | `891d9e3b…` | true |
| SkylakeX | SkylakeX | `891d9e3b…` | true |
| Sandybridge | Sandybridge | `891d9e3b…` | true |
| Nehalem | Nehalem | `891d9e3b…` | true |
| Haswell | Haswell | `891d9e3b…` | true |
| Prescott | **Katmai** + Prescott | `891d9e3b…` | true |

Two things this table is careful about:

1. **The resident kernel is measured, not requested.** `OPENBLAS_CORETYPE` is a
   request; `Prescott` resolved to `Katmai` in one of the two loaded OpenBLAS
   libraries, and that is recorded rather than smoothed over.
2. **Lane B does not fit.** Identity across dispatch classes is expected *by
   construction* here. This matrix is **not** evidence that the registered
   training path is bit-portable — it is not, and Lane A reports per-class.

---

## 5. Lineage verification (the checks that can fail)

```bash
# 1. Producer-order inner selection, verified against an observed producer run.
PYTHONPATH=. python -m pytest tests/experiments/test_rh04_v2_reference.py -q \
  -k "inner_selection_preserves or inner_selection_matches"

# 2. Calibrator input captured, not derived; and enforced.
PYTHONPATH=. python -m pytest tests/experiments/test_rh04_v2_reference.py -q \
  -k "calibration_input or calibrator_input_pin"

# 3. Complete forest structure + independent selection reproduction.
PYTHONPATH=. python -m pytest tests/experiments/test_rh04_v2_reference.py -q \
  -k "registered_producer_lineage or selection_is_reproduced or solver_provenance"
```

---

## 6. What remains unmeasured

| item | status |
|---|---|
| Python 3.12 | NOT MEASURED — no interpreter |
| native Windows | NOT MEASURED — no host |
| non-x86 | NOT MEASURED — no host |
| hosted CI, pre-correction run | **FAILED** — run `45231724257`, 3/3 jobs | 
| hosted CI, post-correction run | NOT YET RUN — logs must be read before claiming resolution |
| `tests/contracts` | **306 passed** — measured |
| `tests/backend` | OUT OF SCOPE — later roadmap stage |

None of these is reported as passing. A reviewer who can measure them should
replace the `NOT MEASURED` entries with the actual output rather than
extrapolating from this table.

---

## CI finding — corrected, run 45231724257 at head f78f521

An earlier version of this section named a **single** cause (missing `mpmath`) and
reported the Python 3.12 structural diagnostic as passing. Both statements were
wrong. They are corrected here from the hosted run record.

**Run `45231724257`, head `f78f521`, conclusion `failure`.** All three jobs failed,
each at **step 6**:

| job | id | interpreter | step 6 name |
|---|---|---|---|
| `synthetic-runner-tests` | `137892736936` | 3.11 | suite |
| `rh04-fixture-diagnostic` | `137892737443` | 3.12 | Inspect canonical 29-case synthetic replay twice (strict, metadata only) |
| `synthetic-runner-tests` | `137892737724` | 3.12 | suite |

### Failure 1 — missing `mpmath` (3.11 and 3.12 job)

```
FAILED tests/experiments/test_rh04_v2_reference.py::test_model_fit_matches_an_independent_mpmath_oracle
ModuleNotFoundError: No module named 'mpmath'
```

The test fails closed when the oracle is absent — correct behaviour. No workflow
installs `research/experiments/requirements-oracle.txt`, the only file declaring
`mpmath`.

### Failure 2 — missing base reference (3.11 job)

```
FAILED tests/experiments/test_rh04_v2_reference.py::test_child_diagnosis_does_not_modify_the_merged_classifier_surface
```

That test compares the working tree against `origin/main`. A default Actions
checkout is **shallow and single-branch**, so no `origin/main` ref exists and the
test fails closed rather than asserting against nothing. This is a **checkout
provisioning** fault, not a test defect. Deleting the comparison or skipping it
when the ref is absent would destroy exactly the preservation guarantee it exists
to provide.

Stated 3.11 counts: **2 failed, 2094 passed, 2 skipped**.

### Failure 3 — genuine V1 divergence in the 3.12 diagnostic

`137892737443` **failed**, with `MISMATCH_FOUND` and **2 differing cases**, exit 1.
It is not a missing-dependency error.

This is reproducible and is **real behaviour of the frozen V1 replay**, not a
defect introduced by the V2 work. Running the diagnostic under different resident
kernels locally:

| resident kernel (`OPENBLAS_CORETYPE`) | result | differing cases |
|---|---|---|
| unset | `EXACT_REPLAY` | 0 |
| Prescott | `MISMATCH_FOUND` | **2** |
| Haswell | `MISMATCH_FOUND` | **2** |
| Nehalem | MISMATCH (1) | 1 |
| Sandybridge | MISMATCH (1) | 1 |

The CI runner's 2 differing cases are reproduced exactly under Prescott and
Haswell. This is a **host-dependence finding about V1**, and it is reported rather
than masked. It is also independent evidence for the amendment: Lane B is a fixed
reference replay, not a host-independent claim, and the absence of training in
Lane B says nothing about bitwise reproducibility across hosts.

Note: `OPENBLAS_CORETYPE` is only a *request*; the effective kernel must be read
from `threadpoolctl` at runtime, which the diagnostics do.

### What was corrected, and what was not

Authorized corrections only:

1. `fetch-depth: 0` plus an explicit fetch of the base branch — gives the
   preservation test its trusted reference.
2. Install the existing pinned `research/experiments/requirements-oracle.txt`.
3. Report resolved dependency versions and run `pip check`.

Not changed: the V1 comparator, fixtures, tolerances, numerical thread settings,
diagnostic verdicts, voting policy. No skip, xfail, `continue-on-error`,
rerun-to-green, or any mechanism that would conceal the V1 failure above.

### Verification status of this section

The workflow edits have **not yet run in hosted CI**. This section therefore
records the **pre-correction** run only. The post-correction 3.12 logs must be
read from the new run before infrastructure failures can be called resolved —
in particular the diagnostic is *expected* to still report `MISMATCH_FOUND`,
because that is a V1 finding this work does not paper over.

---

## 6. Local reproduction of each CI failure, and the fix verified against it

Every claim below was executed, not inferred.

### Failure 1 — missing oracle

| environment | command | result |
|---|---|---|
| CI-exact (3 requirement files, no `mpmath`) | `pytest tests/experiments tests/audit -q -W error` | **1 failed, 2095 passed, 2 skipped** |
| same, oracle test alone | — | `AssertionError: the independent oracle is required evidence, not an optional extra.` |
| with `requirements-oracle.txt` installed | oracle test alone | **1 passed** |

The failing test is `test_model_fit_matches_an_independent_mpmath_oracle`. It fails
closed with an actionable message. It does not skip.

### Failure 2 — missing base reference

Simulated with a real shallow single-branch clone
(`git clone --depth 1 --single-branch`), which reproduces the Actions default:

```
$ git rev-parse --verify origin/main
fatal: Needed a single revision

$ pytest tests/experiments/test_rh04_v2_reference.py -k child_diagnosis_does_not_modify
FAILED  AssertionError: required preservation evidence is unavailable: the canonical
merged test could not be compared against origin/main. This is a hard failure, not a
skip -- acceptance evidence must never vanish silently.
```

Then, in **the same clone**, the exact command the new workflow step runs:

```
$ git fetch origin main:refs/remotes/origin/main
$ git rev-parse --verify origin/main
c6a6bdee46a552a2b0d705a723c862ff8a95be4d

$ pytest ... -k child_diagnosis_does_not_modify
1 passed, 275 deselected in 0.76s
```

So failure 2 is a **checkout provisioning** fault, and the workflow step that fixes
it is verified against a reproduction of the fault. The test's assertion was not
touched.

### Failure 3 — the 3.12 diagnostic, still expected to fail

This one is **not** fixable by provisioning, and the workflow does not try to fix
it. `rh04-fixture-diagnostic` step 5 runs:

```bash
python -m research.intake.diagnose_fixture_replay
python -m research.intake.diagnose_fixture_replay
```

The diagnostic compares the frozen V1 replay against its recorded expectation. As
measured in §"CI finding", that comparison is kernel-sensitive: 2 differing cases
under Prescott and Haswell, 1 under Nehalem and Sandybridge, 0 unset. If the CI
runner resolves to a divergent kernel — which the observed 2 differing cases
indicate — the diagnostic exits 1 and **the job will fail again**.

That is the correct outcome. The divergence is a real property of the frozen V1
reference, and making this job green would require exactly the tolerance, skip or
expectation-regeneration moves that are forbidden.

**A second defect found while checking this, and deliberately not fixed:** the two
invocations share one `run:` block, which executes under `bash -e` semantics. A
non-zero exit from the *first* invocation aborts the step before the *second* one
runs. The step is named "Inspect ... **twice**", but when the replay diverges only
the first observation is ever produced. Fixing that would mean changing the
diagnostic step — a verdict-bearing step — which the narrow authorization for this
round does not cover. It is recorded here as an open defect for a separate decision
rather than silently altered.

### Summary of what the workflow change can and cannot achieve

| failure | fixed by the authorized change? | evidence |
|---|---|---|
| missing `mpmath` | **yes** | reproduces as 1 failed; passes with the oracle installed |
| missing `origin/main` | **yes** | reproduces as 1 failed in a shallow clone; passes after the fetch |
| 3.12 diagnostic `MISMATCH_FOUND` | **no — correctly not attempted** | genuine V1 host-dependence; masking it is forbidden |

Therefore the expected post-correction hosted result is: the two `synthetic-runner-tests`
jobs pass, and `rh04-fixture-diagnostic` **still fails** on a divergent runner. A
red diagnostic job after the fix is evidence that nothing was hidden, not evidence
that the fix failed.

**This section is a prediction only for the parts it has not executed in CI.** The
hosted run must be read before any resolution claim is made.

---

## 7. The admission test was verified by mutation, and the first version was wrong

The round required "a meaningful mutation test, not an AST count". Writing one is
not the same as proving it means anything, so the replacement test was run against
**both** implementations. It did not survive that check on the first attempt.

| version | assertion | new impl | old impl | discriminates? |
|---|---|---|---|---|
| first replacement | outer route mapping read once | pass | **pass** | **no** |
| second attempt | varying `__getitem__` returns tampered value | refuses | refuses | **no** |
| delivered | caller-owned nested container traversed once | **1** | **4** → fails | **yes** |

The first two attempts passed against the code they were supposed to indict. Both
read `archives[route]` exactly once — the bug was never about that outer read — and
in the second case the archive's HMAC attestation refused the tampered value before
any divergence could occur. Keeping either would have been exactly the decoration
the reviewer objected to.

The delivered test counts traversals of a *caller-owned nested* container, which is
where verification-then-snapshot and snapshot-then-verify actually differ:

```
new implementation: caller object traversals = 1
old implementation: caller object traversals = 4
old implementation, pytest:  FAILED  assert 4 == 1
```

### What this test does and does not establish

**Establishes:** verification no longer walks caller-owned mutable state after the
executed content has been fixed. The value executed comes from a single traversal.

**Does not establish:** that a value-divergence attack was previously possible. It
was not — measured, not assumed. Serving a different slope on the second read is
caught by the archive's HMAC with
`ArchiveError: attestation does not verify; parameters were modified or were not
produced by the trusted producer`. The fix removes repeated traversal as **defence
in depth**; the attestation was, and remains, the actual gate. Claiming this change
closed an exploitable hole would have been false, and is not claimed.

This distinction is recorded because the honest version is weaker than the
convenient one, and because a reader comparing traversal counts 4 → 1 could
otherwise reasonably infer an exploit was fixed.

---

## 8. The hosted 3.12 diagnostic was read, and it inverts the earlier reading

The workflow correction could not be pushed as a workflow edit (see §9), so the
workflow at `89b0a8f` is **byte-identical to `main`** — no oracle install, no base
fetch. A new run therefore exercised the *unchanged* workflow and produced the
cleanest evidence so far about the diagnostic.

### Run `45247762503` at `89b0a8f`, unchanged workflow

| job | conclusion | duration |
|---|---|---|
| RH-04 fixture structural drift diagnostic (3.12) | **success** | 13.6 min |
| Synthetic experiment runner (3.11) | **cancelled** | 13.6 min |
| Synthetic experiment runner (3.12) | **failure** | 13.6 min |

### The diagnostic passed here and failed at `f78f521`, with identical configuration

```
f78f521 workflow sha256: e77ab0089a8e4970…  (f78f521 ran the CORRECTED workflow)
89b0a8f workflow sha256: e77ab0089a8e4970…  (89b0a8f runs main's workflow)
```

The hashes are equal because `89b0a8f` restored the file to `main`, which is
exactly what `f78f521`'s corrected version was based on — so **both runs used the
same diagnostic command and the same pinned dependencies.** Nothing in the workflow
differs between them.

And the diagnostic cannot see the work that changed in between. It imports only V1
modules:

```python
from ai.report_comparison import ABS_TOL, REL_TOL
from ai.research_facade import canonical_response_digest
from research.intake import offline_fixture_pack as fixtures
```

The only files that changed between the two commits are
`research/intake/rh04_v2_portable_archive.py` and
`tests/experiments/test_rh04_v2_reference.py` — neither is imported by the
diagnostic, directly or transitively.

**Conclusion, and it is the opposite of the convenient one:** the diagnostic is
**non-deterministic across runners**, not deterministically red. The same command
on the same frozen fixture produced `MISMATCH_FOUND` (2 differing cases) on one
GitHub-hosted runner and `EXACT_REPLAY` on another 20 minutes later. That is
stronger evidence for the V1 host-dependence finding than the single failure was:
the divergence is real, it is environment-dependent, and it is not attributable to
anything in this delivery.

### Consequences

1. **The earlier prediction in §6 was wrong.** I wrote that the diagnostic "will
   fail again" on a divergent runner. It can, but it need not — it flipped to
   green without any change to it. The prediction is corrected here rather than
   left standing.
2. **A green diagnostic is not evidence of correctness.** It is one draw from a
   distribution that has now been observed in both states. Reporting it as a pass
   without that context would repeat exactly the error this round exists to fix.
3. **No claim of resolution is made.** The oracle and base-ref failures are
   reproduced and their fixes are verified locally, but the corrected workflow has
   never run in CI, because it cannot be pushed (§9).

### The 3.12 test failure — attribution is NOT available

The 3.12 runner's step 6 (`Run synthetic experiment-runner and dataset-audit
tests`) failed, and step 7 — the `if: failure() && 3.12` diagnostic — **succeeded**.
The only annotation is `Process completed with exit code 1` at `.github` line 108,
which is a file-level position, not a test name. **The job logs are unreachable**
(blob storage returns `EOF` on every attempt; see §9). The failing test is therefore
**not identified**, and it is not attributed to `mpmath` here.

That distinction matters: at `f78f521` the 3.11 job showed 2 failed with one being
the oracle test. At `89b0a8f` the 3.11 job was **cancelled** before step 6 completed,
so no count exists for it at all.

### Why 3.11 was cancelled despite `fail-fast: false`

`fail-fast: false` is set, and no newer run superseded this one (`cancel-in-progress`
had nothing to cancel). All three jobs stopped at 13.6 minutes against a
`timeout-minutes: 20` budget, so it is not the job timeout either. The 3.11 job's
own `conclusion` is `cancelled` with `Complete job: success`. The cause is **not
determined** from the available data; it is recorded as an unexplained
cancellation of a job that had already passed dependency installation and thread
verification.

---

## 9. Blocker — the workflow correction cannot be pushed or dispatched

**This is a hard blocker, and it is external to the work.**

### What happened

```
$ git push origin delivery/rh04-v2-final
! [remote rejected] ... (refusing to allow a GitHub App to create or update
  workflow `.github/workflows/experiment-runner-ci.yml` without `workflows` permission)
```

The App token used here has no `workflows` scope. `workflow_dispatch` is refused
as well:

```
$ gh workflow run experiment-runner-ci.yml --ref delivery/rh04-v2-final
could not create workflow dispatch event: HTTP 403: Resource not accessible by
integration
```

Both routes to executing the correction are closed. Reading job logs is also
blocked independently: every `actions/jobs/<id>/logs` call redirects to Azure blob
storage and returns `EOF`, so the 3.12 failure text cannot be retrieved either.

### What was delivered instead

The rest of the round's work was pushed and is under review at `89b0a8f`. The
workflow edit was extracted to:

```
docs/research/next_phase/ci-oracle-and-base-ref.patch
```

Verified with `patch --dry-run -p1` against `main`'s copy of the workflow:
**applies cleanly.** It contains exactly the three authorized items and nothing
else:

| hunk | content |
|---|---|
| `fetch-depth: 0` + comment | full history for the preservation comparison |
| new "Fetch trusted base reference" step | `git fetch --no-tags origin "+refs/heads/main:refs/remotes/origin/main"`, prints checkout and base SHAs |
| oracle install + `pip check` + version printout | installs the existing pinned `requirements-oracle.txt`, then reports resolved versions |

No tolerance, thread setting, comparator, fixture, verdict or voting policy appears
in the diff. `yaml.safe_load` parses it.

### What is required to unblock

Either:

1. a token with `workflows` permission, so the patch can be applied and pushed; or
2. a maintainer applies `ci-oracle-and-base-ref.patch` and triggers a run;

in either case followed by reading the resulting logs. **Until then:**

- the two reproduced-and-fixed failures (oracle, base ref) remain unfixed **in
  hosted CI**;
- the 3.12 diagnostic's state remains whatever the next runner happens to draw;
- no claim of resolved CI infrastructure is made, and none should be attributed to
  this delivery.
