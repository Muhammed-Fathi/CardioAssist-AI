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
| hosted CI | NOT RUN — requires separate owner authorization |
| `tests/contracts` | **306 passed** — measured |
| `tests/backend` | OUT OF SCOPE — later roadmap stage |

None of these is reported as passing. A reviewer who can measure them should
replace the `NOT MEASURED` entries with the actual output rather than
extrapolating from this table.
