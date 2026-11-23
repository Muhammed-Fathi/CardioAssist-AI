# Portable reference replay — corrected evidence

**Document ID:** CAI-RH04-PORTABLE-v2
**Supersedes:** the portable-lane claims in
`RH04_V2_CROSS_ENVIRONMENT_MATRIX_2026_11_21.md` §3 and Round 9's PR evidence.
**Status:** unratified candidate. **No gate is closed.**

---

## 0. What Round 9 got wrong

Three defects, all found by review, all material:

| Claim made in Round 9 | Reality |
|---|---|
| "29 cases execute" | **27 were placeholders.** `build_portable_pack` emitted `REFUSAL_ROUTE_DECLARED` / `REQUEST_EDIT_OUT_OF_PORTABLE_SCOPE` without executing anything. |
| "full-path comparison" | Compared **2 of 29** cases, and only four numeric fields within them. |
| "external trusted digest" | `trusted_artifact_sha256=artifact_digest(artifact)` — the pin was the artifact's own hash, and `expected_source` was derived from the artifact under test. |
| "declared agreement bound 1e-14" | A numeric acceptance-tolerance surface by another name. |

The Round 9 module is retained with a superseded banner as historical evidence.
`RH04_V2_CROSS_ENVIRONMENT_MATRIX_2026_11_21.md` §3 reported "one pinned-artifact
digest group across five environments"; that was a *local* measurement of a lane
that never executed the refusal cases, and it is **not** an accepted 29-case
result.

## 1. The correction that removed the need for any tolerance

Round 9 evaluated the model with exact rational arithmetic and needed a bound to
compare against scikit-learn. The bound was the problem.

The replacement instead **rehydrates the declarative archive into a genuine
scikit-learn estimator** and lets the project's own registered inference code
score it. Construction from arrays is not deserialisation: no pickle is read and
no code executes from the archive.

Measured: rehydration is **bit-identical** to the original fitted estimator.

| family | comparison | rows | result |
|---|---|---|---|
| `l2_logistic_regression` | `decision_function` | 200 | **bit-identical** |
| `l2_logistic_regression` | `predict_proba` | 200 | **bit-identical** |
| `constrained_random_forest` | `predict_proba` | 500 | **bit-identical** |

Consequence: **there is no numeric comparison policy left to argue about
inside Lane B.** `DECLARED_SCORE_AGREEMENT` is gone from the new module; the
stale `EXACT_FIELDS = ("calibrated_log_odds",)` designation is gone with it.
Lane B compares exactly against its **own** fixed reference identity, with no
numeric exception surface.

One clarification added in Round 10.1: the table above is a *within-process*
equivalence between a fitted estimator and its rehydrated twin on the same host.
It does **not** license using freshly trained Lane A output as Lane B's expected
reference. Lane A and the registered path still differ from the portable lane at
the last bits on some kernels, and Lane B's reference is generated once from the
committed artifact and pinned as a constant.

## 1a. Round 10.1 — the two defects Round 10 still carried

Round 10 executed 29 cases for real, but review found that the *independence* it
claimed was not actually enforced. Both defects are now fixed.

| Defect | What was wrong | What changed |
|---|---|---|
| **P0-01** | `PortableReplay.__init__(self, facade, archives)` took raw archive JSON and never called `admit()`. A test could construct a replay over an archive that would have been refused by `admit()`, and the "admission" tests exercised a function the replay never called. | `PortableReplay` now **requires** the trusted manifest and key, checks the expected route set exactly (missing / unexpected / swapped / duplicate all refuse), and calls `admit()` for every route in the constructor. The archives are not even retained until every route has been admitted, so no scoring or estimator construction can precede admission. |
| **P0-02** | `_load_artifact_from_archive` obtained the descriptor, preprocessing, calibration and SHAP background through `verify_trusted_local_bundle(source.bundle_dir, …)` — the **freshly generated producer bundle**. Lane B was a hybrid that borrowed most of its inference state from a just-trained artifact. | The freshly-trained dependency is gone. Descriptor fields, eligibility, target block and the full calibration document are pinned *inside the archive*; the SHAP background travels as pinned canonical bytes with a SHA-256 in the independently trusted manifest; the panel and registry entry are the static reviewed declarations. `v1.sources()` is no longer called anywhere in the Lane B path. |

### Admission is in the execution path, and tampering is proven to fail before evaluation

The adversarial test is end-to-end, not a unit test of `admit()`:

1. modify a **semantic** field in a committed archive (a tree node value — not a
   bookkeeping field, which `archive_digest` would ignore);
2. recompute the archive's internal `archive_sha256`;
3. recompute the fixture MAC **with the committed key**, which the attacker has;
4. regenerate the manifest's per-route `archive_sha256` pin;
5. attempt a full `PortableReplay` construction.

Result: **refused**, and `rehydrate` / `rehydrate_member` are trapped for the
whole test and never fire, so no estimator was constructed and no record was
scored. The archive's own hash is not an identity, and a manifest that merely
echoes it is not an independent pin; the pinned split assignment and the SHAP
background digest are what still disagree.

### Lane B needs no producer bundle at all

`test_cold_process_replay_needs_no_producer_bundle` runs all 29 cases in a fresh
interpreter with `v1.sources()` never called, so no producer bundle exists on
disk. The result is identical to the in-process replay:

| | value |
|---|---|
| cases executed | **29 / 29** |
| statuses | 2 `SYNTHETIC_RESULT`, 2 `ABSTAIN`, 3 `UNAVAILABLE`, 22 `ERROR` |
| digest | `891d9e3b2a332c6efc251d97fee25ed46a627ed25b2a089594057b4c9896cdc8` |

`execute_case` now defaults `model_source` to a `LocalSyntheticBundleSource`
whose paths **do not exist**. The facade's request grammar needs the registered
source *type*; nothing in Lane B needs its contents. Any code that tried to read a
bundle would fail loudly instead of silently succeeding.

### The SHAP background: a deliberate, narrow exception

The producer bundle marks `shap_background.json` with
`commit_or_public_upload_prohibited: true` and declares it as *encoded training
projections*. Committing that document as a separate file would violate the
bundle's own policy. It is therefore **not** committed as a file. It travels as
canonical base64 inside the archive's `training_identity`, with its raw SHA-256
pinned twice (in the archive and in the independently trusted manifest), and it
is decoded and digest-checked at load time.

This is still a *recorded training projection*, and it is described as such
wherever it appears. It is a synthetic-cohort background (the document's own
privacy block declares `synthetic_only: true`), it is small — 2,687 B for the
10-feature REST panel and 4,281 B for the 16-feature BASIC panel — and the
alternative (recomputing it from a fresh training run) is exactly the dependency
P0-02 forbids. It is the narrowest way to satisfy both constraints, and it is
called out here rather than buried.

### Concurrency

The Round 10 adapter transported `_request` / `_binding` / `_panel` through
mutable function attributes. Those are gone; every value is passed as an explicit
argument, and concurrent execution of the same replay from eight threads returns
eight identical results with no route or request leakage.

## 2. All 29 cases now execute through the real facade

`PortableReplay` substitutes exactly one facade function — `_load_artifact`, the
single point where the registered pipeline transitions from verified metadata to
a deserialised model, and already the established test seam in this repository.
Everything else is the facade's own code:

request parsing → ordered field validation → registry resolution → source
binding → eligibility → abstention policy → scoring → error handling.

The adapter re-runs steps the registered path runs *before* the model is needed
(bundle verification, synthetic-provenance gate, registry identity cross-check,
request-versus-artifact agreement, capabilities), then obtains the estimator by
rehydration instead of `joblib.load`.

**Measured result: 29 of 29 exact, type-and-value.**

| response status | cases |
|---|---|
| `SYNTHETIC_RESULT` | 2 |
| `ABSTAIN` | 2 |
| `UNAVAILABLE` | 3 |
| `ERROR` | 22 |

Both scored cases reproduce **bit-identically**:

```
da_a2_resting_v1          calibrated_log_odds 1.1439672594951131  (identical)
da_a1_basic_clinical_v1   calibrated_log_odds 2.6971396718292335  (identical)
```

Full exported shape is preserved, including nulls, error codes, stages,
`present_fields`, `missing_fields_with_reason` and exact types. Comparison uses
the project's own frozen strict comparator (`_strict_equal`), which rejects
`True == 1` and type coercion.

## 3. Trust is now external at the actual entry point

The committed fixture is three plain JSON files:

| file | bytes | SHA-256 |
|---|---|---|
| `da_a2_resting_v1.archive.json` | 151 958 | `d971b1078e8952c1695d9badb4661d62044ef5e58f7dbbcba1ab23707863faae` |
| `da_a1_basic_clinical_v1.archive.json` | 520 898 | `b81b9a80fea563fed06a1e697033cdd7f55995a6329d07cdab1c2ab5284fee90` |
| `trusted_manifest.json` | 5 695 | `e8256470bc57b08f1cbfd326be14cb3c465c9a57b4735229dc62e3db8ee372d3` |

The `trusted_manifest.json` is the identity. It pins, per route, 28 mandatory
values: archive digest, route/dataset/panel/version/contract, cohort, model and
protocol ids, ordered feature names, encoded feature order, family, execution
profile, selected hyperparameters, preprocessing digest, training-input digest,
split digest, calibration parameters and full OOF provenance, representation
version, and outer-fold ensemble digest.

**The verifier never derives an expectation from the artifact.** Every value
compared comes from the manifest.

### Artifact-family inventory (why this is not a general replacement)

| route | family | portable representation |
|---|---|---|
| `da_a2_resting_v1` | `l2_logistic_regression` | 10 coefficients + intercept |
| `da_a1_basic_clinical_v1` | `constrained_random_forest` | 50 trees, 1 658 nodes total, plus 3 outer-fold members |

No `prevalence_dummy` model is selected on these routes. The module nonetheless
**refuses** `prevalence_dummy` outright rather than approximating it, so the
bounded scope is explicit rather than silently assumed.

### Attestation

An HMAC over the same body the digest covers, using `hmac-sha256-local-producer-v1`
(reused from `ai/packaging.py`; no new scheme invented). The test key is a
**publicly labelled fixture**: `attestation.key_label` reads
`PUBLIC_TEST_FIXTURE_KEY_NOT_A_SECRET`, and the manifest must declare
`key_label == FIXTURE_KEY_LABEL` or admission fails. It demonstrates the
mechanism; it confers **no real-world authenticity**.

## 4. Deserialisation policy

| stage | pickle? |
|---|---|
| export (once, from a verified producer bundle) | **yes**, via `verify_trusted_local_bundle` → `ResearchCadPredictor.from_verified_bundle`, which re-verifies containment, ACLs, sibling digests and the producer HMAC *before* `joblib.load` |
| **evaluation / replay** | **no** — pinned by a test that makes `joblib.load` raise and requires the lane to still produce the registered value |

The archive itself contains no `joblib`, no `pickle` and no executable payload;
a test asserts the three committed files are JSON-only.

## 5. Adversarial evidence

19 structural refusals, each exercised **with the attacker holding the key** so
the MAC verifies and only structure can refuse:

unrepresentable family · unknown family · bad `classes` · zero slope · negative
slope · non-numeric intercept · `fitted_strictly_out_of_fold=False` · wrong
`fit_scope` · calibration/family mismatch · missing `fold_ensemble` · bad fold
member family · fold calibrator mismatch · unknown field · sentinel removed ·
feature-order disagreement · slice index out of range · self-cycle · unreachable
node · hostile node count.

Plus end-to-end: recomputed self-hash, coordinated binding change, wrong key,
swapped route, route absent from the manifest, non-finite parameters.

Tree validation enforces acyclicity (no node with two parents), reachability
(no unreachable nodes), correct child relationships, class-proportion sums, and
hard ceilings (200 000 nodes/tree, 2 000 trees) so evaluation terminates or
fails closed rather than looping.

## 6. Reproducible verification — two separate commands

### Lane A — registered regeneration and diagnostic report

```bash
python -m research.intake.rh04_v2_full_reference   # or import and call
python - <<'PY'
from research.intake import rh04_v2_full_reference as FR
from research.intake import rh04_v2_portable_archive as A
from research.intake import offline_fixture_pack as v1
import tempfile, json
from pathlib import Path
from ai.filesystem_security import ensure_private_directory

pack = FR.generate_full_reference()
print("laneA_semantic:", FR.semantic_digest(pack))
with tempfile.TemporaryDirectory() as t:
    local = v1.sources(ensure_private_directory(Path(t)))
    for r in (v1.REST, v1.BASIC):
        print(r, "family:", json.loads((local[r].bundle_dir/'manifest.json').read_text())["model"]["selected_model_family"])
PY
```

### Lane B — cold-process pinned-artifact verification

```bash
OPENBLAS_NUM_THREADS=1 python - <<'PY'
import json, hashlib
from pathlib import Path
from threadpoolctl import threadpool_info
import numpy, scipy, sklearn              # load BEFORE reading kernels
from ai import research_facade as facade
from research.intake import offline_fixture_pack as v1
from research.intake import rh04_v2_portable_archive as A

FIX = Path("research/intake/fixtures/rh04_v2_portable")
man = json.loads((FIX/"trusted_manifest.json").read_text())
arcs = {r: json.loads((FIX/f"{r}.archive.json").read_text()) for r in man["routes"]}
for r, a in arcs.items():
    A.admit(a, man, expected_route=r)     # independent admission
print("resident:", [[x.get("architecture"), x.get("version")]
                    for x in (threadpool_info() or []) if x.get("internal_api")=="openblas"])
print("manifest_sha256:", A._sha256((FIX/"trusted_manifest.json").read_bytes()))
for r,a in arcs.items():
    print(r, "archive_sha256:", A._sha256((FIX/f"{r}.archive.json").read_bytes()))
PY
pytest tests/experiments/test_rh04_v2_reference.py -q -W error -k "portable_lane or pinned_archive"
```

Expect, on any host: `29/29` exact, `responses_digest
891d9e3b2a332c6efc251d97fee25ed46a627ed25b2a089594057b4c9896cdc8` for the replay
in this probe, and the three file digests above. **A mismatch is a finding —
report it; never regenerate the expectation from your own run.**

## 7. Evidence matrix — environment vs result are different things

Requested dispatch, resident kernels, environment class and output digest are
recorded separately; an output-digest group is **not** an environment class.

| requested | resident NumPy | resident SciPy | environment class | Lane A digest | Lane B digest |
|---|---|---|---|---|---|
| *(unset)* | SkylakeX 0.3.23.dev | SkylakeX 0.3.28 | `22f82ac8bd04` | `aea7d617…` | pinned `cef38b8a…` |
| `Sandybridge` | Sandybridge 0.3.23.dev | Sandybridge 0.3.28 | `467f524dc72f` | `3366be81…` | pinned `cef38b8a…` |
| `Prescott` | Prescott 0.3.23.dev | **Katmai** 0.3.28 | `b57a27c32d19` | `3366be81…` | pinned `cef38b8a…` |
| `Nehalem` | Nehalem 0.3.23.dev | Nehalem 0.3.28 | `78aa4d92b29b` | `aea7d617…` | pinned `cef38b8a…` |
| `Haswell` | Haswell 0.3.23.dev | Haswell 0.3.28 | `89277cdf5d45` | `aea7d617…` | pinned `cef38b8a…` |

Five environment classes, two Lane A result groups, one Lane B result group. The
`Prescott` row is the proof that a request is not a fact: NumPy resolved to
Prescott and SciPy to Katmai.

**Not measured:** Python 3.12 (no interpreter), native Windows (no host),
non-x86 wheels.

## 8. Non-claims

- This is **not** an acceptance pack and closes **no** gate.
- It does **not** prove training reproducibility. Lane B is inference over a
  fixed artifact; training still runs on Lane A and remains host-sensitive.
- It does **not** ratify D-V2-7.
- The fixture key confers no authenticity.
- No clinical validity, no model equivalence, no patient readiness.
- `prevalence_dummy` is refused, not supported — the bounded scope is stated,
  not hidden.
