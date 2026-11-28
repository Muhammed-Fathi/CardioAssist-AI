# RH-04 architecture amendment — final reconciliation

**Document ID:** CAI-RH04-AMEND-v4 (supersedes the unresolved parts of v3; v3's
§1 lane definitions and §2 clause intents are carried forward unchanged)
**Status:** proposed for **explicit owner ratification**. Nothing here is ratified,
accepted or closed by this document.
**Trigger:** hosted run `45446417665` at `73d9f9d`, 8 of 10 jobs failed.

---

## 1. The contradiction, stated precisely

v3's §1 table already said:

| outcome | classification |
|---|---|
| numbers differ between environments, fit converged and status valid | **diagnostic finding** — acceptable variation to report |
| fit failed to converge, status is not the successful value | **invalid** |
| evidence missing | **invalid** |
| output malformed or structurally wrong | **invalid** |

The implementation did not implement that table. It required
`lineage_established == true`, which reduced to `coefficients_exact`, which reduced
to `max|Δ| == 0.0` — **bitwise equality with the frozen archive**. That is the
*first* row being enforced as though it were a failure.

The consequence is exact and was predictable: bitwise equality holds on the host
that produced the archive (`SkylakeX`) and fails on every other required host, by
1–2 ulp. Under v3's own V2-04b the environment matrix is **≥3 resident dispatch
classes on Linux 3.11, ≥3 on 3.12, plus native Windows**. The implementation
therefore made the contract unsatisfiable on the majority of the environments the
contract names.

**The document was right and the code contradicted it.** The code is corrected to
the document; the document is clarified where it was underspecified.

## 2. What Lane A must establish — and what it must not

Lane A establishes **validity**. It does not establish cross-environment identity,
and it must never be read as doing so.

| property | required? | meaning |
|---|---|---|
| `source_provenance` | **required** | which registered producer, cohort, seeds, preprocessing, selected configuration |
| `parameter_identity` | **required** | the actual regenerated parameter vector, digested |
| `convergence` | **required** | independently evaluated: objective, gradient norm, iterations, status |
| `provenance_lineage_valid` | **required** | provenance is reconstructable and consistent |
| `archived_parameter_equality` | **measured, never required** | whether the vector is bit-for-bit the archived one, with its deltas |
| response structural integrity | **required** | same case set, same statuses, same field set — on both replays |
| cross-environment parameter identity | **explicitly NOT required** | a measured, classified finding |

**Provenance lineage and bitwise equality are different properties** and are
reported in different fields. Neither may be substituted for the other:

- A run can have valid provenance and non-identical parameters. This is the normal
  case on a non-SkylakeX host and is **acceptable**.
- A run can have identical parameters and broken provenance. This is **invalid**,
  because the numbers cannot be shown to have come from the registered path.

### 2.1 The five properties are recorded separately

`_regenerated_parameters()` emits five named sections. They are never merged into
a single boolean, because merging is what allowed the contradiction to hide.

### 2.2 The executable form of the §1 table

`assert_lane_a_valid(document)` returns `{valid, failures, findings, requirements}`.

- **failures** → raise. Missing convergence evidence, `any_failure is not False`,
  absent provenance, absent parameter identity, invalid lineage, unmeasured
  equality, absent replay identity.
- **findings** → returned, with magnitude. A converged regeneration whose
  parameters differ from the archive.

Mutating either direction is caught by the regression suite (§6).

## 3. Frozen-archive replay vs fresh-model regeneration

These are **not interchangeable evidence** and are now separately digested.

| | frozen-archive replay | fresh-model replay |
|---|---|---|
| what runs | admitted, manifest-verified archive bytes | models fitted by the registered producer in this process |
| fitting | none | the registered producer's own final fit |
| digest across 4 classes | **identical** (`8dd4388e…`) | **differs per class** (`d2aeb41b`, `f62f27a3`, `8013951c`, `13da544f`) |
| proves | the frozen artifacts replay deterministically | freshly regenerated models produce a stable, characterised response identity |
| does **not** prove | that regeneration still works | equality with the archive |

`replay_response_identity.fresh_and_frozen_are_equivalent` is `false` and is
asserted to be `false`. Reporting either as the other is a defect.

**Which lane owns which exactness claim.** Lane B owns exactness, and it is exact
against the frozen set on every measured class. Lane A owns regeneration validity,
and its fresh replay is *expected* to differ across environments. A supervisor
reading a Lane A fresh digest must not compare it to Lane B's fixed digest.

## 4. Retained without change

- **Lane B exactness, no numeric tolerance, any environment.** In full.
- **The complete environment matrix**: ≥3 resident dispatch classes per Linux
  Python minor version, plus native Windows. Not substituted by what happened to
  be measurable.
- **V2-01** owner ratification; **V2-05** dual-run window until V1 retirement;
  **V2-06** semantics restatement; **V2-07** all listed negative cases;
  **V2-08** no new tolerance.
- The approved V1 surface, the independent calibration evaluator, the convergence
  requirements, and the fixed Lane B digest `891d9e3b…`.
- **No new solver, model family, dataset or tolerance.**

## 5. What this amendment does not do

- It does not declare the gate passed. **0/10 gates closed.**
- It does not retire V1. V1's failure is real and stays recorded (§ transition doc).
- It does not ratify itself.
- It does not claim native Windows execution — not measured.
- It does not claim clinical validity, external calibration, or sklearn
  bit-identity across platforms.

## 6. Evidence that this amendment is implemented, not merely described

| property | measurement |
|---|---|
| Lane A valid under all 4 forced classes | `valid=True`, `failures=[]` on haswell/nehalem/sandybridge/prescott |
| Lane A valid on native host | `valid=True`, **0 findings** |
| difference classified, not failed | 1 finding per forced class, `WITHIN_ULP_DIAGNOSTIC`, magnitude recorded |
| frozen replay identical across classes | `8dd4388e…` ×4 |
| fresh replay differs across classes | 4 distinct digests |
| measured difference must not fail | mutation → `test_v2_04a_measured_difference_is_a_finding_never_a_failure` fails |
| invalid convergence must not pass | mutation → `test_v2_04a_invalid_convergence_fails_closed` fails |
| full suite, forced dispatch | **315 passed** |
| full suite, native | **315 passed** |

## 7. Owner decision required

1. Ratify or reject **CAI-RH04-AMEND-v4** as the acceptance contract.
2. Ratify or reject the §2 split (validity required, equality measured).
3. Acknowledge that **Lane B exactness is retained and is already satisfied**,
   while **Lane A cross-environment parameter identity is withdrawn as a
   requirement** and retained as a measured finding.

No gate closes and no ratification occurs until the owner states it explicitly.
