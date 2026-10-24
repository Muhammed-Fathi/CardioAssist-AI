# `research/uci412` — UCI-412 (Z-Alizadeh Sani) internal research benchmark

`PROPOSED · NOT AUTHORIZED · INTERNAL_EXPLORATORY_NOT_SUPERVISOR_APPROVED`

Source-specific, **single-dataset** research harness for UCI-412 (`DA-A1`). It is
deliberately separate from the frozen D-047 Cleveland package:
`research/experiments/**` is read-only for this milestone, and nothing here is
merged into the application runtime.

## Safety posture

- No real workbook is bundled, downloaded, or read by tests or CI. `tests/uci412`
  uses generated rows only; synthetic results are **software evidence**, never CAD
  performance evidence.
- The real-data path (`preflight`, `run`) is unusable outside an interactive local
  Windows console on a fixed drive, after a human-signed M3a authorization and the
  D-046 `DA-A1` read-only provenance chain both validate.
- Outputs are written only under `data/uci412-experiments/` (Git-ignored, private).
  `predictions.csv` is a patient-level derivative: never commit, upload, or paste it.

## Commands

```bash
python -m research.uci412 describe   # panels, exclusions, planning arithmetic, blockers
python -m research.uci412 dry-run    # in-memory synthetic smoke run, writes nothing
python -m research.uci412 preflight  # Windows-local gates; parses no rows
python -m research.uci412 run        # Windows-local; requires RUN M3A UCI412 LOCALLY
```

## Module map

| Module | Role |
|---|---|
| `source_spec.py` | frozen source identity, 56-column order, prohibited predictors, target tokens |
| `feature_schema.py` + `schemas/…v1.json` | versioned dictionary and executable panel allowlist |
| `config.py` + `…research_plan.v0.1.json` | frozen protocol/CV/model/grid/seeds; smoke profile |
| `adapter.py` | strict read-only workbook validation and mapping |
| `models.py` | fold-local preprocessing and the bounded model families |
| `evaluation.py` | repeated nested CV, metrics, calibration, bootstrap, negative controls |
| `sample_size.py` | R²-independent planning arithmetic (not an adequacy verdict) |
| `reporting.py` | aggregate-only report and protected output writing |
| `safety.py` | runtime/authorization/provenance/Git-ignore gates |
| `runner.py`, `cli.py` | orchestration and command-line entry point |
| `synthetic.py` | deterministic in-memory fixtures |
| `ci/experiment-runner-ci.uci412.patch` | maintainer-applied CI coverage; the workflow file itself is untouched (push identity lacks `workflows` permission) |

Specification, blockers, comparison with Cleveland, and the human authorization
proposal: `docs/research/gate-pt/08_m3a_uci412_source_specific_benchmark_SPECIFICATION.md`.
Ratification/activation packet: `docs/research/gate-pt/09_m3a_uci412_internal_research_RATIFICATION_PACKET.md`.

## Source encoding (Amendment A-1, dictionary schema 1.1.0 / panel 1.1.0)

A human-executed, read-only, SHA-256-verified audit of all 303 records showed that six admitted
categorical predictors — `DM`, `HTN`, `Current Smoker`, `EX-Smoker`, `FH`, `Typical Chest Pain` — are
delivered as **numeric `0`/`1`**, while `Sex`, `DLP`, `Atypical`, `Nonanginal`, `Exertional CP` and
`Dyspnea` hold registered text values. Those six now carry one explicit numeric-binary source encoding
(`0` → absent/false, `1` → present/true; model codes unchanged). Only an actual integer/numeric `0` or `1`
is accepted there: text tokens, booleans, non-binary or non-integral numbers, non-finite cells and mixed
representations **fail closed**, and no other column has a numeric conversion or any global coercion. The
direction is stated by peer-reviewed secondary literature (Tao et al. 2025, *Reviews in Cardiovascular
Medicine* 26(3):26204, doi:10.31083/RCM26204, Table 1: `True = 1; false = 0`) but is **not** confirmed by an
official dataset-owner codebook, so it stays provisional and needs explicit human acceptance (residual item
S-9). Every hash from the
pre-amendment freeze is superseded: the previous signed local manifest is **not** reusable and a new human
decision plus a new local manifest are required. See
`docs/research/gate-pt/10_m3a_uci412_source_encoding_AMENDMENT_A1.md`.
