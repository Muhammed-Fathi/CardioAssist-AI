# Cross-environment evidence — requested ≠ resident ≠ result group

**Document ID:** CAI-RH04-XENV-v2
**Supersedes:** §4 of `RH04_V2_FULL_REFERENCE_2026_11_21.md` (Round 8)
**Status:** unratified candidate evidence. No gate closed.

## 0. Correcting Round 8

Round 8 reported "two distinct resident NumPy/SciPy kernel pairs and two distinct
output-digest groups" and described them as "two observed resident environments".
That conflated three different things. They are separated below:

- **requested** — the `OPENBLAS_CORETYPE` value asked for,
- **resident** — the kernel actually mapped in the process (read via `threadpoolctl`,
  after importing NumPy/SciPy/sklearn),
- **environment class** — the SHA-256 of the full resident kernel+version tuple list,
- **result group** — an *output digest*, which is a property of a code path, not of a host.

There are **five** environment classes here, not two. There are two *Lane A result
groups*. The Round 8 phrasing collapsed these.

## 1. Resident environment matrix

Cold process per row; NumPy and SciPy resident kernels and versions recorded
individually. Python 3.11.2, NumPy 1.26.4, SciPy 1.15.3, sklearn 1.6.1.

| requested | NumPy resident | SciPy resident | environment class | note |
|---|---|---|---|---|
| *(unset)* | SkylakeX `0.3.23.dev` | SkylakeX `0.3.28` | `22f82ac8bd04` | host default |
| `Sandybridge` | Sandybridge `0.3.23.dev` | Sandybridge `0.3.28` | `467f524dc72f` | agreed |
| `Prescott` | Prescott `0.3.23.dev` | **Katmai** `0.3.28` | `b57a27c32d19` | **request silently split** |
| `Nehalem` | Nehalem `0.3.23.dev` | Nehalem `0.3.28` | `78aa4d92b29b` | agreed |
| `Haswell` | Haswell `0.3.23.dev` | Haswell `0.3.28` | `89277cdf5d45` | agreed |

**Five resident environment classes from five requests.** The `Prescott` row is
the important one: the request was honoured by NumPy and **not** by SciPy, which
resolved to Katmai. A run that records only `OPENBLAS_CORETYPE` records a
*fiction*.

## 2. Result groups per lane

### Lane A — registered full regeneration (`generate_full_reference`)

| requested | environment class | Lane A semantic digest |
|---|---|---|
| *(unset)* | `22f82ac8bd04` | `aea7d6179f32f272` |
| `Sandybridge` | `467f524dc72f` | `3366be81d10361e3` |
| `Prescott` | `b57a27c32d19` | `3366be81d10361e3` |
| `Nehalem` | `78aa4d92b29b` | `aea7d6179f32f272` |
| `Haswell` | `89277cdf5d45` | `aea7d6179f32f272` |

**Two Lane A result groups across five environment classes.** The grouping is
*not* one-to-one with the environment class — `Sandybridge` and `Prescott` share a
result group despite being different environment classes. That is precisely why
"two result groups" must never be reported as "two environments".

### Lane B, artifact derived on each host (`export_artifact` then evaluate)

| requested | Lane B digest |
|---|---|
| *(unset)* | `41dc1235cb34c787` |
| `Sandybridge` | `cef38b8a12efcd9c` |
| `Prescott` | `4c8ff949f27e7a41` |
| `Nehalem` | `cef38b8a12efcd9c` |
| `Haswell` | `321414a6f1466e80` |

**Four result groups.** This is honest and expected: the *artifact* is derived
from a host-dependent training run, so re-deriving it on a new host propagates
that host's trained parameters. A portable *evaluator* does not make training
portable.

### Lane B, **pinned** artifact evaluated on each host

Artifacts exported once on the `Nehalem` class, then evaluated on every host:

| requested | environment class | Lane B pinned digest |
|---|---|---|
| *(unset)* | `22f82ac8bd04` | `cef38b8a12efcd9c` |
| `Sandybridge` | `467f524dc72f` | `cef38b8a12efcd9c` |
| `Prescott` | `b57a27c32d19` | `cef38b8a12efcd9c` |
| `Nehalem` | `78aa4d92b29b` | `cef38b8a12efcd9c` |
| `Haswell` | `89277cdf5d45` | `cef38b8a12efcd9c` |

**One result group across five environment classes, including the split-dispatch
host.** This is the only configuration in the whole workstream that produces a
genuine host-independent result — and it is honest about *why*: model evaluation
and calibration are exact rational arithmetic over recorded binary64 parameters,
with a single final rounding.

## 3. What each configuration proves

| Configuration | Establishes | Does **not** establish |
|---|---|---|
| Lane A | scientific regeneration fidelity | host-independent replay (2 groups) |
| Lane B, derived per host | evaluator portability given native parameters | training reproducibility |
| Lane B, pinned artifact | **host-independent inference** | that the artifact's training is reproducible |

The pinned-artifact row is the candidate's actual contribution: it converts "the
scores moved because the host changed" into "the scores cannot move because the
arithmetic is rational", while leaving Lane A as the sole scientific reference.

## 4. What this does *not* claim

- It is **not** `EXACT_REPLAY` with scikit-learn. scikit-learn's own output still
  differs by up to 6.661e-15; the portable lane and the registered lane are
  different, declared computations.
- It does **not** satisfy V2-04 as written, which demands `EXACT_REPLAY` for the
  registered path across ≥3 classes × 3.11/3.12 plus Windows. That gate remains
  **not met**.
- `1e-14` is a declared candidate agreement bound, not a relaxation of any
  existing tolerance and not consumed by any gate.

## 5. Not measured

| Item | Status |
|---|---|
| Python 3.12 | **NOT MEASURED** — no interpreter available locally |
| Native Windows | **NOT MEASURED** — no Windows host |
| Non-x86 / rebuilt wheels | **NOT MEASURED** |
| A sixth distinct class | not found in the wheel's dispatch set locally |

## 6. Exact-head checks for a reviewer

Run these on the delivered commit. Lane A and Lane B are checked **separately**,
because they answer different questions.

```bash
git checkout <delivered-sha>
python -m pip install -r research/experiments/requirements.txt
python -m pip install -r research/experiments/requirements-oracle.txt

# Resident kernels FIRST (redacted: no filesystem paths in the output)
python - <<'PY'
import numpy, scipy, sklearn
from threadpoolctl import threadpool_info
for x in threadpool_info() or []:
    print({k: x.get(k) for k in ('internal_api','architecture','version','num_threads')})
PY

# Lane A -- registered regeneration. Expect aea7d617... or 3366be81...
# depending on your dispatch class. A THIRD value is a portability FINDING:
# report it, never regenerate the expectation.
python - <<'PY'
from research.intake import rh04_v2_full_reference as FR
pack = FR.generate_full_reference()
print('laneA:', FR.semantic_digest(pack))
PY

# Lane B -- pinned-artifact inference. Expect cef38b8a12efcd9c on ANY host.
pytest tests/experiments/test_rh04_v2_reference.py -q -W error -k portable
```

Report a mismatch. Do not adjust the expectation to match the run.

## 7. Corrected Windows instructions

The Round 8 block checked out `1aa0b28`, which does not contain this candidate.
Load the numerical libraries **before** reading resident kernels — the G-08 defect
was precisely a kernel read from a library that was not resident.

```powershell
git clone https://github.com/Muhammed-Fathi/CardioAssist-AI.git
cd CardioAssist-AI
git fetch origin review/rh04-v2-p0-corrections-20261121
git checkout <DELIVERED_SHA>            # see the round-9 delivery record
git rev-parse HEAD                      # MUST equal <DELIVERED_SHA>

py -3.12 -m venv .venv-rh04
.\.venv-rh04\Scripts\Activate.ps1
python -m pip install -r research/experiments/requirements.txt
python -m pip install -r research/experiments/requirements-oracle.txt
python -m pip check

# Import the libraries FIRST, then record resident kernels (sanitised output only)
python -c @"
import numpy, scipy, sklearn
from threadpoolctl import threadpool_info
for x in threadpool_info() or []:
    print({k: x.get(k) for k in ('internal_api','architecture','version','num_threads')})
"@

# Lane B, pinned-artifact evaluation -- must be identical on Windows
python -m pytest tests/experiments/test_rh04_v2_reference.py -q -W error -k portable

# Lane A, registered regeneration -- host-dependent; report what you get
python -c @"
from research.intake import rh04_v2_full_reference as FR
print('laneA:', FR.semantic_digest(FR.generate_full_reference()))
"@
```

Never print a full `threadpool_info()` dump: it contains filesystem paths and
build hashes. Only the four sanitised keys above.
