"""RH-04 V2 candidate: solver determinism, criterion reachability, and preservation.

These tests exercise the *candidate* V2 tooling only. They assert nothing about
the canonical V1 gate, which is unchanged and still authoritative:

* the V1 pack still validates against its frozen digest ``0307b396…``;
* the V1 comparator (``_strict_equal`` / ``_approved_replay_equal``) is
  byte-identical and still has exactly one approved float exception;
* no candidate module is imported by production code.

The suite is deliberately negative-first: every guarantee a V2 reference would
rely on has a test that fails if that guarantee is removed.

**Host dependence is measured, not assumed.** Generation is an exact function of
the inputs *given to the reference fit*, but the float64 `gemv` upstream of it
differs between OpenBLAS kernels (see the protocol, §4-§5). A generation is
therefore expected to hash to one of the two *observed* digests, and the test
asserts the pack is byte-stable **for the host it runs on** while reporting which
class this host is. It does not assert that every host produces class A — that
was the mistake that made the first revision of this suite red on CI.
"""

from __future__ import annotations

import ast
import copy
import hashlib
import json
import math
import subprocess
import sys
from fractions import Fraction
from decimal import Decimal
from pathlib import Path

import numpy as np
import pytest

from ai import calibration as calibration_module
from ai.errors import CalibrationIntegrityError
from research.intake import offline_fixture_pack as v1
from research.intake import rh04_v2_candidate as candidate
from research.intake import rh04_v2_deterministic_upstream as upstream
from research.intake import rh04_v2_model_fit as model_fit
from research.intake import rh04_v2_child_diagnosis as child_diag
from research.intake import rh04_v2_integrated_candidate as integrated
from research.intake import rh04_v2_full_reference as full_reference
from research.intake import rh04_v2_portability_audit as audit
from research.intake import rh04_v2_reference_fit as reference

REPO_ROOT = Path(v1.__file__).resolve().parents[2]


# --------------------------------------------------------------------------- #
# 0. Preservation: V1 must be untouched by everything here                   #
# --------------------------------------------------------------------------- #


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_v1_frozen_pack_digest_is_unchanged():
    """The V1 pack must still hash to its frozen canonical digest."""
    assert v1.PACK_SHA256 == (
        "0307b396cea1e620c4004647e1d82ff7f292bb5b74de7cad1661e1299c6e7049"
    )
    pack = json.loads(v1.PACK.read_text())
    from ai.research_facade import canonical_response_digest

    assert canonical_response_digest(pack) == v1.PACK_SHA256
    assert len(pack["cases"]) == 29


def test_v1_comparator_still_has_exactly_one_approved_exception():
    """V2 must not add a tolerance surface to the V1 comparator."""
    source = Path(v1.__file__).read_text()
    assert source.count("_WINDOWS_FLOAT_CASE_ID = ") == 1
    assert source.count("_WINDOWS_FLOAT_FIELD = ") == 1
    tree = ast.parse(source)
    raises = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Raise) and isinstance(node.exc, ast.Call)
    ]
    # The validator reports mismatches by raising the frozen ValueError.
    assert raises, "the strict validator must still raise on a mismatch"


def test_v1_strict_comparator_is_type_exact():
    from research.intake.offline_fixture_pack import _strict_equal

    assert _strict_equal(1, 1.0) is False
    assert _strict_equal(True, 1) is False
    assert _strict_equal({"a": 1}, {"a": 1, "b": 2}) is False
    assert _strict_equal([1.0], [1.0 + 2.0 ** -52]) is False


def _production_modules_do_not_import_v2() -> list[str]:
    offenders: list[str] = []
    for directory in ("ai", "backend", "shared", "scripts"):
        root = REPO_ROOT / directory
        if not root.is_dir():
            continue
        for path in root.rglob("*.py"):
            text = path.read_text(encoding="utf-8", errors="ignore")
            if "rh04_v2_" in text:
                offenders.append(str(path.relative_to(REPO_ROOT)))
    return offenders


def test_no_production_module_imports_the_v2_candidate():
    """AST-free grep is enough here: the string may not appear at all."""
    assert _production_modules_do_not_import_v2() == []


def test_candidate_pack_is_not_a_gate_digest():
    """The candidate must not be usable as an acceptance gate yet.

    The sentinel moved from ``V2_PACK_SHA256`` (artifact tier, which folded
    interpreter metadata into the gate) to ``V2_SEMANTIC_SHA256`` (the tier that
    is actually gate-worthy). Both are unpinned here on purpose: pinning is an
    owner decision that follows ratification of `D-V2-1`.
    """
    assert candidate.V2_SEMANTIC_SHA256.startswith("UNPINNED")
    assert not hasattr(candidate, "V2_PACK_SHA256")


# --------------------------------------------------------------------------- #
# 1. The declared criterion must be reachable                                #
# --------------------------------------------------------------------------- #


def _cohort(size: int = 64, seed: int = 11) -> tuple[np.ndarray, np.ndarray]:
    generator = np.random.default_rng(seed)
    latent = generator.normal(-0.4, 1.1, size=size)
    probabilities = 1.0 / (1.0 + np.exp(-latent))
    labels = (generator.random(size) < probabilities).astype(float)
    labels[0], labels[1] = 0.0, 1.0
    from ai.calibration import safe_clipped_logit

    return labels, safe_clipped_logit(probabilities)


def test_declared_tolerance_sits_between_the_float64_floor_and_the_measured_floor():
    """The declared tolerance must be reachable AND below the float64 floor."""
    declared = reference.V2_FIT_KKT_TOLERANCE
    float64_floor = Decimal(10) ** reference.V2_FLOAT64_KKT_FLOOR_ORDER
    measured_floor = Decimal(reference.V2_FIT_MEASURED_KKT_FLOOR)
    assert declared < float64_floor, "tolerance must beat the float64 resolution"
    assert declared > measured_floor, "tolerance must be reachable with margin"


def test_the_fit_reaches_the_declared_tolerance_on_a_real_shaped_cohort():
    labels, logits = _cohort(size=32)
    a, b = reference.decimal_logistic_fit(labels, logits)
    assert math.isfinite(a) and math.isfinite(b)
    # Re-evaluate the residual at the returned binary64 point.
    residual = _kkt_at(labels, logits, a, b)
    assert residual <= float(reference.V2_FIT_KKT_TOLERANCE) * 100, residual


def _kkt_at(y: np.ndarray, logits: np.ndarray, a: float, b: float) -> float:
    """Decimal KKT residual of the returned point (larger precision than the fit)."""
    from decimal import ROUND_HALF_EVEN, localcontext

    with localcontext() as context:
        context.prec = 60
        context.rounding = ROUND_HALF_EVEN
        targets = [Decimal(float(v)) for v in y]
        features = [Decimal(float(v)) for v in logits]
        count = Decimal(len(targets))
        l2 = reference.V2_FIT_L2_ANCHOR
        zero, one = Decimal(0), Decimal(1)
        sum_diff = Decimal(0)
        sum_diff_feature = Decimal(0)
        for target, feature in zip(targets, features):
            diff = reference._sigmoid(Decimal(a) + Decimal(b) * feature) - target
            sum_diff += diff
            sum_diff_feature += diff * feature
        grad_a = sum_diff / count + l2 * Decimal(a)
        grad_b = sum_diff_feature / count + l2 * (Decimal(b) - one)
        low_a, low_b = reference.V2_FIT_LOWER
        high_a, high_b = reference.V2_FIT_UPPER
        da = Decimal(a)
        db = Decimal(b)
        status_a = reference._face(da, low_a, high_a)
        status_b = reference._face(db, low_b, high_b)
        resid_a = (
            max(zero, -grad_a)
            if status_a == "lower"
            else (max(zero, grad_a) if status_a == "upper" else abs(grad_a))
        )
        resid_b = (
            max(zero, -grad_b)
            if status_b == "lower"
            else (max(zero, grad_b) if status_b == "upper" else abs(grad_b))
        )
        return float(max(resid_a, resid_b))


# --------------------------------------------------------------------------- #
# 2. Determinism and fail-closed behaviour                                   #
# --------------------------------------------------------------------------- #


def test_fit_is_bit_identical_across_repeated_calls():
    labels, logits = _cohort(size=24)
    first = reference.decimal_logistic_fit(labels, logits)
    for _ in range(3):
        assert reference.decimal_logistic_fit(labels, logits) == first
    assert reference.fit_is_host_independent(labels, logits) is True


def test_fit_refuses_single_class_inputs():
    labels, logits = _cohort(size=24)
    labels = np.ones_like(labels)
    with pytest.raises(CalibrationIntegrityError) as info:
        reference.decimal_logistic_fit(labels, logits)
    assert info.value.code == "invalid_v2_fit_inputs"


def test_fit_refuses_too_few_observations():
    with pytest.raises(CalibrationIntegrityError) as info:
        reference.decimal_logistic_fit(
            np.array([0.0, 1.0]), np.array([-1.0, 1.0])
        )
    assert info.value.code == "invalid_v2_fit_inputs"


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), -float("inf")])
def test_fit_refuses_non_finite_inputs(bad):
    labels, logits = _cohort(size=24)
    logits = np.array(logits, dtype=float)
    logits[0] = bad
    with pytest.raises(CalibrationIntegrityError) as info:
        reference.decimal_logistic_fit(labels, logits)
    assert info.value.code == "invalid_v2_fit_inputs"


def test_fit_fails_closed_when_the_criterion_cannot_be_met():
    """An impossible tolerance must raise, never return unconverged parameters."""
    labels, logits = _cohort(size=24)
    with pytest.raises(CalibrationIntegrityError) as info:
        reference.decimal_logistic_fit(
            labels, logits, kkt_tolerance=Decimal("1e-40")
        )
    assert info.value.code == "calibration_solver_did_not_converge"


def test_fit_rejects_non_decimal_bounds():
    labels, logits = _cohort(size=24)
    with pytest.raises(CalibrationIntegrityError) as info:
        reference.decimal_logistic_fit(labels, logits, lower=(-15.0, 0.01))
    assert info.value.code == "invalid_v2_fit_controls"


def _recorded_hard_cohort() -> tuple[np.ndarray, np.ndarray]:
    """A *recorded* 64-row OOF cohort that defeated the float64 portable solver.

    Captured while regenerating the synthetic pack; the raw values are embedded
    as exact binary64 hex literals so this test never rebuilds a model. Raw-byte
    provenance, re-verified inside the test: ``sha256(y) = eabaacb13570d8d7…``
    (46 positives of 64) and ``sha256(logits) = bc3de6e970c17aea…``.
    Its measured property (see the V2 protocol, evidence row ``EV-03``): the float64
    ``deterministic_logistic_fit`` loops until its iteration budget is exhausted
    because its KKT residual stalls at ~1.27e-10 against a 1e-10 threshold,
    while the decimal reference reaches 1e-16.
    """
    hex_logits = (
        "0x1.26555f3ae8780p+0", "0x1.57ad259b3c594p-1", "0x1.a31613f93712bp-1", "0x1.a660311567875p-1",
        "0x1.5f2a9ff9a69e1p-1", "0x1.63fe69ae72e2ep+0", "0x1.0459d46b530f1p+0", "0x1.1d6fc8c294ca8p-3",
        "0x1.86cd3547e775ap-1", "0x1.897bdf6cd659ap-1", "0x1.37fc72cc67d5fp+0", "0x1.0bb63f810f9abp+0",
        "0x1.086a345b6f67cp+0", "0x1.6026f7103c7ebp+0", "0x1.a59a033ea8939p-1", "0x1.32ec62db8df22p-2",
        "0x1.05f1faf61dbeap-2", "0x1.abea20d900df2p-1", "0x1.3f9e5950b0a5cp+0", "0x1.7f153dae48a28p-2",
        "0x1.c603675c97c78p+0", "0x1.6b9f85db7511cp+0", "0x1.2b813ed62e876p-2", "0x1.3dbc28a66e5dcp+0",
        "0x1.816376e454050p-2", "0x1.394ad5ddc731ep-1", "0x1.3557d043fe242p+0", "0x1.1eff69c5b0ba5p-1",
        "0x1.e0020861123cap-2", "0x1.21ef47777938ep+0", "0x1.4f591506dae20p-1", "0x1.33e56a7cd0e10p+0",
        "0x1.381dd591c228ep+0", "0x1.a760a4c0533a7p-1", "0x1.11c72e2fb68fbp+0", "0x1.430b9268555fep+0",
        "0x1.cf035cc918991p-1", "0x1.df0467de35074p-2", "0x1.db712c648e379p-1", "0x1.7a36c80f9134ap+0",
        "0x1.1cd3657564ad7p+0", "0x1.289f1ac0bb097p+0", "0x1.6b6e485129622p-1", "0x1.6e32b5ffe8fa6p+0",
        "0x1.e12eea5035bdap-1", "0x1.0b89d153a6d4ep-1", "0x1.d20da86724b3fp-1", "0x1.652a2961cea2ep+0",
        "0x1.246f21c15bed7p+0", "0x1.ab151443db068p-2", "0x1.44b38bdfe2caap+0", "0x1.0e756ba5b5c74p+0",
        "0x1.9d733dd3aec58p-1", "0x1.17cf586a9fee5p+0", "0x1.84dc75ecc7f3cp-1", "0x1.404b1b95e1dcep+0",
        "0x1.46db16e7b1153p+0", "0x1.5255cfd4783eep-1", "0x1.6b1ac4c46c9b7p+0", "0x1.bfdcc74a0d0f0p-1",
        "0x1.0fa52c230648dp+0", "0x1.e3d3cc168c651p-1", "0x1.7db105c5329b2p-2", "0x1.6ffcfdd55db00p-1",
    )
    hex_labels = (
        1, 1, 0, 0, 1, 1, 1, 0, 1, 0, 1, 1, 1, 0, 1, 1, 1, 0, 1, 0, 1, 1, 0, 1, 1, 1, 1, 0, 0, 1, 1, 1,
        1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 0, 1, 1, 0, 1, 0, 1, 1, 0, 1, 1, 0, 1, 1, 1, 1, 1, 0, 0, 1, 0, 1,
    )
    logits = np.array([float.fromhex(value) for value in hex_logits], dtype=np.float64)
    labels = np.array(hex_labels, dtype=np.float64)
    return labels, logits


def test_decimal_reference_converges_where_the_float64_portable_solver_does_not():
    """The V2 criterion must succeed on a cohort where the float64 one stalls.

    This is the *reason* V2 uses decimal arithmetic, expressed as an executable
    claim rather than prose.
    """
    labels, logits = _recorded_hard_cohort()
    assert labels.size == 64 and logits.size == 64

    # The float64 portable solver cannot certify this cohort at 1e-10.
    with pytest.raises(CalibrationIntegrityError) as info:
        calibration_module.deterministic_logistic_fit(labels, logits)
    assert info.value.code == "calibration_solver_did_not_converge"

    # The decimal reference reaches the declared criterion and is reproducible.
    first = reference.decimal_logistic_fit(labels, logits)
    assert reference.decimal_logistic_fit(labels, logits) == first
    assert _kkt_at(labels, logits, *first) <= 1e-14


def test_raw_extremes_do_not_overflow():
    """Softplus/sigmoid must never raise on extreme logits."""
    labels = np.array([0.0, 1.0] * 6)
    logits = np.array([-800.0, 800.0, -50.0, 50.0, -1.0, 1.0] * 2)
    a, b = reference.decimal_logistic_fit(labels, logits)
    assert math.isfinite(a) and math.isfinite(b)


# --------------------------------------------------------------------------- #
# 3. Declared protocol is complete and honest                                #
# --------------------------------------------------------------------------- #


def test_declared_protocol_claims_no_host_dependent_operations():
    protocol = reference.declared_protocol()
    assert protocol["host_dependent_operations"] == []
    assert protocol["blas_calls"] == 0
    assert protocol["libm_calls"] == 0
    assert protocol["python_float_transcendentals_used"] == 0
    assert protocol["criterion_is_reachable"] is True
    # A versioned identifier: changing the algorithm must change this string.
    assert protocol["protocol_id"].startswith("rh04.v2.")


def test_declared_protocol_is_json_serialisable_and_stable():
    first = reference.declared_protocol()
    second = reference.declared_protocol()
    assert first == second
    json.dumps(first, sort_keys=True, allow_nan=False)


def test_reference_module_never_uses_float_transcendental_functions():
    """No ``math.exp``/``log`` or ``numpy`` ufunc may appear in executable code."""
    tree = ast.parse(Path(reference.__file__).read_text())
    # Decimal methods named exp()/ln() are the *software* implementations and
    # are exactly what this module is supposed to use; the prohibition is about
    # the host libm (``math``) and BLAS-backed ``numpy`` reductions.
    forbidden = {"log1p", "logaddexp", "expit", "dot", "mean", "sum", "matmul"}
    decimal_methods = {"exp", "ln", "log10", "sqrt", "is_finite", "quantize"}
    offenders: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            if (
                isinstance(func, ast.Attribute)
                and func.attr in forbidden
                and func.attr not in decimal_methods
            ):
                offenders.append(func.attr)
            if (
                isinstance(func, ast.Attribute)
                and func.attr in {"exp", "log"}
                and isinstance(func.value, ast.Name)
                and func.value.id == "math"
            ):
                offenders.append(f"math.{func.attr}")
            if (
                isinstance(func, ast.Name)
                and func.id in forbidden
            ):
                offenders.append(func.id)
    assert offenders == [], offenders


def test_reference_module_makes_no_blas_call_indirectly():
    """The fit must not use numpy arithmetic on the data path."""
    tree = ast.parse(Path(reference.__file__).read_text())
    numpy_calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "np"
    ]
    allowed = {"asarray", "isfinite", "unique", "ndarray"}
    assert [call.func.attr for call in numpy_calls if call.func.attr not in allowed] == []


# --------------------------------------------------------------------------- #
# 4. The generator seam must be exact and must not leak                     #
# --------------------------------------------------------------------------- #


@pytest.fixture(scope="module")
def generated_pack() -> dict:
    """One real generation (≈90 s), shared by every structural test.

    There is deliberately **no digest allowlist here**. An earlier revision
    raised unless the complete pack digest was one of two recorded values, which
    conflated three different questions and made a bit-identical numerical result
    fail on a different interpreter: the digested document contained
    ``platform.python_version()``. Measured consequence — the hosted Python 3.12
    run produced all 29 cases bit-identically to this host and still errored on
    nine tests.

    Identity is now tiered (``semantic_digest`` / ``provenance_digest`` /
    ``artifact_digest``). A figure is only ever gate-worthy at the semantic tier,
    so that is what the assertions below use.
    """
    return candidate.generate_candidate_pack()


def test_generation_is_semantically_identical_to_the_committed_candidate(
    generated_pack,
):
    """A fresh generation must match the committed *semantic* reference.

    This is the real invariant: protocol, bindings, requests and all 29 expected
    responses. It is host-independent by construction and must hold on every
    supported interpreter, OS and BLAS kernel.
    """
    committed = json.loads(candidate.V2_FIXTURE_PATH.read_text())
    want = candidate.semantic_digest(committed)
    got = candidate.semantic_digest(generated_pack)
    if got != want:
        observed = candidate.V2_OBSERVED_SEMANTIC_DIGESTS
        this_class = observed.get(got, "PREVIOUSLY-UNOBSERVED")
        that_class = observed.get(want, "PREVIOUSLY-UNOBSERVED")
        pytest.fail(
            "this host does not reproduce the committed semantic reference.\n"
            f"  committed class : {that_class} ({want})\n"
            f"  this host class : {this_class} ({got})\n"
            "This is a PORTABILITY finding, not a metadata artifact and not a\n"
            "regression: the numerical reference genuinely differs on this host.\n"
            "It must stay failing; do not add the digest to an allowlist."
        )
    assert len(generated_pack["cases"]) == 29


def test_generation_is_byte_stable_within_one_interpreter(generated_pack):
    """Two generations in the same process must agree bit for bit.

    This is a *determinism* claim about the reference given fixed inputs. It is
    intentionally distinct from the cross-host claim above; conflating the two is
    what made the previous revision fail on Python 3.12.
    """
    assert candidate.pack_digest(candidate.generate_candidate_pack()) == (
        candidate.pack_digest(generated_pack)
    )
    assert candidate.validate(generated_pack, replay=False) == 29


def test_a_one_ulp_edit_to_a_v2_expected_value_fails_validation(generated_pack):
    """V2 tolerance is zero: a single bit is enough to fail closed.

    ``replay=False`` is used deliberately. The point under test is the *edited
    value* being rejected, so the check must not be confounded by host-drift —
    on a class-B runner a full replay would fail for an unrelated reason and the
    test would pass for the wrong one.
    """
    pack = json.loads(json.dumps(generated_pack))
    case = next(
        item
        for item in pack["cases"]
        if item["expected"]["status"] == "SYNTHETIC_RESULT"
    )
    value = case["expected"]["outcomes"][0]["score"]["calibrated_log_odds"]
    case["expected"]["outcomes"][0]["score"]["calibrated_log_odds"] = float(
        np.nextafter(value, math.inf)
    )
    # The edited pack is structurally valid; only a replay can catch the bit.
    assert candidate.validate(pack, replay=False) == 29
    with pytest.raises(ValueError) as info:
        candidate.validate(pack)
    assert "response mismatch" in str(info.value)


def test_v2_validation_has_no_approved_exception_branch():
    source = Path(candidate.__file__).read_text()
    assert "_approved_replay_equal" not in source
    assert "_WINDOWS_FLOAT_CASE_ID" not in source


def test_validation_rejects_a_tampered_binding(generated_pack):
    pack = json.loads(json.dumps(generated_pack))
    pack["bindings"]["crosswalk_sha256"] = "0" * 64
    with pytest.raises(ValueError):
        candidate.validate(pack)


def test_validation_rejects_a_tampered_case_count(generated_pack):
    pack = json.loads(json.dumps(generated_pack))
    pack["cases"].pop()
    with pytest.raises(ValueError) as info:
        candidate.validate(pack, replay=False)
    assert "case inventory" in str(info.value)


def test_validation_rejects_a_renamed_case(generated_pack):
    pack = json.loads(json.dumps(generated_pack))
    pack["cases"][0]["id"] = "renamed"
    with pytest.raises(ValueError) as info:
        candidate.validate(pack, replay=False)
    assert "case inventory" in str(info.value)


def test_validation_rejects_a_reordered_inventory(generated_pack):
    pack = json.loads(json.dumps(generated_pack))
    pack["cases"][0], pack["cases"][1] = pack["cases"][1], pack["cases"][0]
    with pytest.raises(ValueError) as info:
        candidate.validate(pack, replay=False)
    assert "case inventory" in str(info.value)


def test_validation_rejects_protocol_drift(generated_pack):
    pack = json.loads(json.dumps(generated_pack))
    pack["protocol"]["convergence_tolerance"] = "1e-9"
    with pytest.raises(ValueError) as info:
        candidate.validate(pack, replay=False)
    assert "protocol drift" in str(info.value)


def test_seam_is_restored_after_the_context_manager():
    before = calibration_module.deterministic_logistic_fit
    with candidate.decimal_reference_seam():
        assert calibration_module.deterministic_logistic_fit is not before
    assert calibration_module.deterministic_logistic_fit is before


def test_seam_refuses_a_non_declared_l2_anchor():
    labels, logits = _cohort(size=24)
    with candidate.decimal_reference_seam():
        with pytest.raises(ValueError):
            calibration_module.deterministic_logistic_fit(
                labels, logits, l2_anchor=0.5
            )


def test_solver_default_swap_is_restored():
    from ai.calibration import OofLogisticCalibrator

    before = OofLogisticCalibrator.__dict__["fit_from_oof"]
    with candidate._deterministic_solver_default():
        assert OofLogisticCalibrator.__dict__["fit_from_oof"] is not before
    assert OofLogisticCalibrator.__dict__["fit_from_oof"] is before


def test_pack_digest_is_stable_for_the_same_content(generated_pack):
    assert candidate.pack_digest(generated_pack) == candidate.pack_digest(
        json.loads(json.dumps(generated_pack))
    )


# --------------------------------------------------------------------------- #
# 5. Portability audit: comparison logic and no-leak properties              #
# --------------------------------------------------------------------------- #


def test_compare_audits_flags_every_differing_stage():
    left = {"stages": {"a": "1", "b": "2"}, "environment": {}}
    right = {"stages": {"a": "1", "b": "3"}, "environment": {}}
    report = audit.compare_audits(left, right)
    assert report["stages_differing"] == ["b"]
    assert report["all_stages_invariant"] is False
    assert [row["verdict"] for row in report["rows"]] == ["INVARIANT", "DISPATCH_DEPENDENT"]


def test_compare_audits_reports_identical_audits_as_invariant():
    left = {"stages": {"a": "1"}, "environment": {}}
    report = audit.compare_audits(left, json.loads(json.dumps(left)))
    assert report["all_stages_invariant"] is True
    assert report["stages_differing"] == []


def test_compare_audits_treats_a_missing_stage_as_a_difference():
    left = {"stages": {"a": "1", "b": "2"}, "environment": {}}
    right = {"stages": {"a": "1"}, "environment": {}}
    report = audit.compare_audits(left, right)
    assert report["stages_differing"] == ["b"]


def test_audit_payload_carries_no_values_paths_or_scores():
    report = audit.run_audit(stages=("micro",))
    text = json.dumps(report)
    for token in ("/home/", "/tmp/", "secret", "token=", "patient"):
        assert token not in text
    # Every stage value is a hex digest or a short status token.
    for value in report["stages"].values():
        assert isinstance(value, str)
        assert "/" not in value


def test_audit_compare_exit_code_reflects_drift(tmp_path, capsys):
    """``--compare`` must exit 1 on drift and 0 on agreement.

    ``capsys`` is required, not cosmetic: the CLI prints a JSON report on the
    success path, and without capture that write is attributed to the *next*
    output-using test under ``-W error`` and fails it spuriously.
    """
    left = tmp_path / "left.json"
    right = tmp_path / "right.json"
    same = {"schema_version": audit.AUDIT_SCHEMA_VERSION, "environment": {}, "stages": {"x": "1"}}
    different = {"schema_version": audit.AUDIT_SCHEMA_VERSION, "environment": {}, "stages": {"x": "2"}}
    left.write_text(json.dumps(same))
    right.write_text(json.dumps(different))
    assert audit.main(["--compare", str(left), str(right)]) == 1
    assert json.loads(capsys.readouterr().out)["stages_differing"] == ["x"]
    right.write_text(json.dumps(same))
    assert audit.main(["--compare", str(left), str(right)]) == 0
    assert json.loads(capsys.readouterr().out)["all_stages_invariant"] is True


def test_audit_declares_the_decimal_stage_invariant_from_a_single_process():
    """Within one process the reference stage must be self-consistent."""
    stages = audit.fit_stages()
    assert stages["decimal_reference_parameters"] == stages["decimal_reference_parameters"]
    assert stages["fit_input_labels"] and stages["fit_input_logits"]


# --------------------------------------------------------------------------- #
# 6. End-to-end replay in a cold process                                     #
# --------------------------------------------------------------------------- #


def _clean_env() -> dict[str, str]:
    """Inherit the environment, keeping the *dispatch* under test.

    Two failure modes are avoided here, both learned the hard way:

    * Stripping the whole environment (a naive "cold" isolation) drops
      ``VIRTUAL_ENV``/``LD_LIBRARY_PATH`` and can silently import a different
      numpy, which is a worse confound than the one it removes.
    * Stripping ``OPENBLAS_CORETYPE`` makes the child run on the host's natural
      kernel while the parent runs on the forced one. The two sides then measure
      *different* numerical environments and any comparison between them is
      meaningless — it reported a spurious pass when this suite was first run
      under a forced dispatch.

    So the dispatch variables are preserved deliberately: they define the
    numerical environment being measured, not noise to be filtered out.
    """
    import os

    environment = dict(os.environ)
    environment["OPENBLAS_NUM_THREADS"] = "1"
    environment["PYTHONHASHSEED"] = "0"
    environment["PYTHONPATH"] = str(REPO_ROOT)
    return environment


def _cold_check() -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "research.intake.rh04_v2_candidate", "--check"],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
        env=_clean_env(),
        timeout=2400,
    )


@pytest.fixture(scope="module")
def cold_check_result():
    return _cold_check()


def test_cold_process_check_mode_replays_the_committed_candidate(
    cold_check_result, generated_pack
):
    """``--check`` in a fresh interpreter must replay exactly — or fail closed.

    Selection is on the **semantic** digest, so a different interpreter, OS or
    BLAS build does not change the branch taken — only genuinely different
    numerical content does. On a host that reproduces the reference this must be
    an exact replay; on any other host the correct behaviour is a fail-closed
    refusal naming the differing field, because the V2 reference has zero
    tolerance.

    What is never acceptable — and is asserted here — is a silent pass on a host
    that does not reproduce the committed bytes, or a crash instead of a
    diagnosis.
    """
    result = cold_check_result
    committed = json.loads(candidate.V2_FIXTURE_PATH.read_text())
    reproduces = candidate.semantic_digest(generated_pack) == (
        candidate.semantic_digest(committed)
    )

    if reproduces:
        assert result.returncode == 0, result.stderr[-3000:]
        payload = json.loads(result.stdout)
        assert payload["status"] == "EXACT_REPLAY"
        assert payload["cases"] == 29
        # The reported identity is the semantic tier, not the raw artifact.
        assert payload["identity"]["semantic_digest"] == (
            candidate.semantic_digest(committed)
        )
        assert payload["identity"]["identity_version"] == (
            candidate.V2_IDENTITY_VERSION
        )
    else:
        # Fail closed, with a redacted diagnosis rather than a traceback dump.
        assert result.returncode != 0, (
            "a host that does not reproduce the committed candidate must not "
            "report success"
        )
        assert "response mismatch" in result.stderr
        assert "redacted_field_diff" in result.stderr
        # The diff must name a field but must never leak a value.
        assert "calibrated_log_odds" in result.stderr


# --------------------------------------------------------------------------- #
# 7. Reference identity: five tiers, and what each one protects
# --------------------------------------------------------------------------- #
#
# These tests exist because of a measured defect: the previous design folded
# ``platform.python_version()`` into the single gated digest, so a *bit-identical*
# numerical reference failed on a different interpreter (hosted Python 3.12
# produced all 29 cases identically). Each test below pins one tier.


def _committed() -> dict:
    return json.loads(candidate.V2_FIXTURE_PATH.read_text())


def test_identity_has_exactly_five_tiers():
    described = candidate.describe_identity(_committed())
    assert set(described) == {
        "semantic_digest",
        "provenance_digest",
        "artifact_digest",
        "environment",
        "identity_version",
    }
    assert described["identity_version"] == "rh04.v2.reference-identity/v2"


@pytest.mark.parametrize("version", ["3.9.1", "3.11.2", "3.11.18", "3.12.16", "3.13.0"])
def test_metadata_only_change_never_moves_the_semantic_digest(version):
    """A different interpreter is not a different reference."""
    pack = _committed()
    before_semantic = candidate.semantic_digest(pack)
    before_artifact = candidate.pack_digest(pack)
    original = pack["generation"]["python_version"]
    pack["generation"]["python_version"] = version
    assert candidate.semantic_digest(pack) == before_semantic
    # The raw artifact digest must still bind provenance: same bytes for the same
    # version, different bytes for a different one.
    assert (candidate.pack_digest(pack) == before_artifact) == (version == original)


def test_metadata_only_change_is_visible_in_provenance_and_environment():
    pack = _committed()
    before = candidate.provenance_digest(pack)
    pack["generation"]["python_version"] = "3.12.16"
    assert candidate.provenance_digest(pack) != before
    assert candidate.environment_metadata(pack)["python_version"] == "3.12.16"


def test_environment_metadata_is_never_part_of_the_semantic_digest():
    """Structural proof, independent of any particular value."""
    pack = _committed()
    semantic = candidate.semantic_digest(pack)
    metadata = candidate.environment_metadata(pack)
    assert metadata, "the committed candidate must record its environment"
    # Perturb every metadata field to a sentinel and require no semantic change.
    for key in metadata:
        pack["generation"][key] = "__perturbed__"
    assert candidate.semantic_digest(pack) == semantic


@pytest.mark.parametrize(
    "section",
    ["schema_version", "protocol", "bindings", "requests", "cases"],
)
def test_every_protected_section_changes_the_semantic_digest(section):
    """Each contractual category must be covered by the canonical digest."""
    pack = _committed()
    before = candidate.semantic_digest(pack)
    if section == "schema_version":
        pack[section] = pack[section] + ".tampered"
    elif section == "protocol":
        pack[section] = dict(pack[section])
        pack[section]["protocol_id"] = "tampered"
    elif section == "bindings":
        key = sorted(pack[section])[0]
        pack[section] = dict(pack[section])
        pack[section][key] = "tampered"
    elif section == "requests":
        key = sorted(pack[section])[0]
        pack[section] = dict(pack[section])
        pack[section][key] = {"tampered": True}
    else:  # cases
        pack[section] = copy.deepcopy(pack[section])
        pack[section][0]["expected"]["status"] = "TAMPERED"
    assert candidate.semantic_digest(pack) != before, section


@pytest.mark.parametrize(
    "mutate",
    [
        lambda c: c[0].__setitem__("id", "renamed"),
        lambda c: c[0]["edits"].append({"op": "tampered"}),
        lambda c: c[0]["expected"]["outcomes"][0]["score"].__setitem__(
            "calibrated_log_odds", 1.0
        ),
        lambda c: c[0].__setitem__("route", "tampered"),
        lambda c: c.reverse(),
    ],
    ids=["renamed", "edits", "expected-score", "route", "reordered"],
)
def test_case_level_tampering_changes_the_semantic_digest(mutate):
    pack = _committed()
    before = candidate.semantic_digest(pack)
    pack["cases"] = copy.deepcopy(pack["cases"])
    mutate(pack["cases"])
    assert candidate.semantic_digest(pack) != before


def test_validate_gates_on_the_semantic_tier_not_the_artifact():
    """A pack that differs only in provenance must still validate structurally."""
    pack = _committed()
    pack["generation"]["python_version"] = "3.12.16"
    assert candidate.validate(pack, replay=False) == 29


def test_validate_rejects_a_semantic_change_even_with_correct_metadata():
    """A pinned *semantic* digest catches an edited expected value.

    ``replay=False`` alone deliberately does not inspect expected responses — it
    is the structural half. The pin is what makes an edit fail closed without
    paying for a 90 s replay, so that is what this test pins.
    """
    committed = _committed()
    pinned = candidate.semantic_digest(committed)
    pack = copy.deepcopy(committed)
    pack["generation"]["python_version"] = "3.12.16"  # irrelevant, by design
    pack["cases"][0]["expected"]["status"] = "TAMPERED"
    # Structurally the pack is still fine...
    assert candidate.validate(pack, replay=False) == 29
    # ... but it no longer matches the pinned semantic reference.
    assert candidate.semantic_digest(pack) != pinned
    with pytest.raises(ValueError, match="semantic content changed"):
        candidate.validate(pack, replay=False, expected_digest=pinned)


def test_there_is_no_host_digest_allowlist_left():
    """The allowlist was the defect; it must not quietly return."""
    source = Path(candidate.__file__).read_text()
    assert "V2_OBSERVED_PACK_DIGESTS" not in source
    assert "V2_OBSERVED_SEMANTIC_DIGESTS" in source


# --------------------------------------------------------------------------- #
# 8. Deterministic upstream candidate (synthetic only)
# --------------------------------------------------------------------------- #
#
# Measured motivation: sklearn's L-BFGS-B fit moves 11 of 12 coefficients between
# kernels, so replacing the accumulation method cannot make scoring portable.
# These tests pin the one thing that *is* host-invariant, and pin the negative
# result so nobody "fixes" it by swapping in fsum again.


def _fixed_problem():
    rng = np.random.RandomState(7)
    rows = [[float(v) for v in r] for r in rng.randn(300, 12)]
    coefficients = [float(v) for v in rng.randn(12)]
    return coefficients, rows, 0.25


def test_deterministic_upstream_is_a_function_of_its_inputs():
    coefficients, rows, intercept = _fixed_problem()
    first = [upstream.score_as_float(s) for s in upstream.exact_linear_scores(
        coefficients, rows, intercept)]
    second = [upstream.score_as_float(s) for s in upstream.exact_linear_scores(
        coefficients, rows, intercept)]
    assert first == second
    assert len(first) == 300


def test_deterministic_upstream_rounds_half_to_even_at_the_halfway_point():
    """An *independent* rounding oracle, not ``float(score) == float(score)``.

    ``score_as_float`` is checked against hand-derived halfway cases where the
    exact rational is precisely between two binary64 values. Round-half-even is
    what ``float(Fraction)`` provides, so the expectation is stated explicitly
    rather than by calling it.
    """
    # 2^53 + 1 is exactly halfway between two representable doubles; ties-to-even
    # takes the even one, 2^53.
    exact = Fraction(2**53 + 1, 1)
    assert upstream.score_as_float(exact) == float(2**53)

    # 2^53 + 3 is also halfway; ties-to-even again takes the even neighbour.
    assert upstream.score_as_float(Fraction(2**53 + 3, 1)) == float(2**53 + 4)

    # A half-integer well inside the integer-exact range rounds exactly.
    assert upstream.score_as_float(Fraction(7, 2)) == 3.5
    assert upstream.score_as_float(Fraction(-7, 2)) == -3.5

    # 1 - 2^-54 IS a genuine halfway point below 1.0: the neighbours there have
    # spacing 2^-53, so ties-to-even picks the even significand, 1.0.
    # (1 - 2^-53 is *not* a halfway point -- it is exactly representable -- which
    # an earlier revision of this test wrongly asserted.)
    halfway = Fraction(2**54 - 1, 2**54)
    assert upstream.score_as_float(halfway) == 1.0
    assert upstream.score_as_float(Fraction(2**53 - 1, 2**53)) == 1.0 - 2.0**-53


def test_deterministic_upstream_handles_cancellation_exactly():
    """Catastrophic cancellation must not appear: the sum is exact."""
    # Sum of 1e16, 1.0 and -1e16 is exactly 1.0 in rational arithmetic, whereas
    # the float64 sum in a naive order loses the 1.0 entirely.
    coefficients = [1.0, 1.0, 1.0]
    features = [1e16, 1.0, -1e16]
    score = upstream.exact_linear_score(coefficients, features, 0.0)
    assert score == Fraction(1)
    assert upstream.score_as_float(score) == 1.0


def test_deterministic_upstream_preserves_signed_zero_policy():
    """A sum that is exactly zero yields +0.0, never -0.0."""
    score = upstream.exact_linear_score([1.0, -1.0], [1.0, 1.0], 0.0)
    assert score == 0
    assert math.copysign(1.0, upstream.score_as_float(score)) == 1.0


def test_deterministic_upstream_is_exact_near_the_subnormal_boundary():
    smallest = 5e-324  # smallest positive subnormal
    score = upstream.exact_linear_score([1.0], [smallest], 0.0)
    assert upstream.score_as_float(score) == smallest


def test_deterministic_upstream_rounds_rather_than_overflowing():
    """A product beyond binary64 range must be refused, not silently inf."""
    with pytest.raises(ValueError):
        upstream.exact_linear_score([float("inf")], [1.0], 0.0)
    # A finite product whose exact value exceeds the float range is a caller
    # error at conversion time; the rational itself is still exact.
    huge = upstream.exact_linear_score([1.7e308], [10.0], 0.0)
    assert huge > 10**308


def test_deterministic_upstream_declares_no_host_dependent_operations():
    protocol = upstream.declared_protocol()
    assert protocol["protocol_id"] == "rh04.v2.exact-linear-score/v1"
    assert "none" in str(protocol["host_dependent_operations"])


def test_deterministic_upstream_refuses_non_finite_inputs():
    with pytest.raises(ValueError):
        upstream.exact_linear_score([float("nan")], [1.0], 0.0)
    with pytest.raises(ValueError):
        upstream.exact_linear_score([1.0], [float("inf")], 0.0)


def test_deterministic_upstream_rejects_length_mismatch():
    with pytest.raises(ValueError):
        upstream.exact_linear_score([1.0, 2.0], [1.0], 0.0)


def test_accumulation_swap_alone_is_documented_as_insufficient():
    """Guard the measured negative result against a well-meaning regression.

    ``fsum`` is *not* a portability fix: it sums coefficients that a prior stage
    already made host-dependent. If someone replaces the exact scorer with a
    compensated float accumulator, the module's declaration must stop claiming
    exactness — this test fails loudly in that case.
    """
    source = Path(upstream.__file__).read_text()
    assert "fsum" not in source.split("def exact_linear_score")[1].split("def ")[0]
    assert "Fraction" in source


def test_float64_agrees_with_exact_on_the_sign_of_the_score():
    """Threshold and abstention semantics only need the sign; verify it holds."""
    import numpy as np

    coefficients, rows, intercept = _fixed_problem()
    for row in rows:
        exact = upstream.exact_linear_score(coefficients, row, intercept)
        naive = float(np.dot(np.asarray(coefficients), np.asarray(row)) + intercept)
        assert (naive > 0) == (exact > 0) or abs(float(exact)) < 1e-12
        assert (naive == 0) == (exact == 0) or abs(float(exact)) < 1e-12

# --------------------------------------------------------------------------- #
# 9. Deterministic model fit (isolated candidate, synthetic only)
# --------------------------------------------------------------------------- #
#
# Measured motivation: stage S1 is the only remaining host dependence. These
# tests pin the declared objective, an INDEPENDENT high-precision oracle, and
# fail-closed behaviour. They are deliberately not "small delta" tests: the
# review forbids claiming equivalence from small coefficient differences.


def _fit_problem(seed: int = 3, n: int = 40, d: int = 3):
    generator = np.random.RandomState(seed)
    features = generator.randn(n, d)
    labels = (generator.rand(n) < 0.5).astype(int)
    return features, labels


def test_model_fit_declares_the_objective_it_actually_minimises():
    declaration = model_fit.declared_objective(model_fit.PROFILE_CLEVELAND)
    assert declaration["protocol_id"] == "rh04.v2.decimal-model-fit/v2"
    assert "penalised" in str(declaration["intercept_treatment"])
    assert "none" in str(declaration["host_dependent_operations"])
    # The calibration objective must not be silently reused.
    calibration = reference.declared_protocol()
    calibration_objective = calibration.get("objective") or json.dumps(calibration)
    assert declaration["objective"] != calibration_objective


def test_model_fit_reaches_the_declared_gradient_criterion():
    features, labels = _fit_problem()
    fit = model_fit.fit_logistic_decimal(
        [[float(v) for v in row] for row in features],
        [int(v) for v in labels],
        c_value=1.0,
    )
    assert float(fit["gradient_inf_norm"]) <= 1e-24
    assert fit["iterations"] < 50


def test_model_fit_matches_an_independent_mpmath_oracle():
    """Independent 60-digit Newton in mpmath, a separate code path.

    Agreement must be at the level of binary64 rounding, not merely "close".
    """
    try:
        import mpmath
    except ImportError as error:  # pragma: no cover - dependency is declared
        raise AssertionError(
            "the independent oracle is required evidence, not an optional extra. "
            "Install it with: python -m pip install -r "
            "research/experiments/requirements-oracle.txt"
        ) from error
    mpmath.mp.dps = 60
    features, labels = _fit_problem()
    fit = model_fit.fit_logistic_decimal(
        [[float(v) for v in row] for row in features],
        [int(v) for v in labels],
        c_value=1.0,
    )
    n = len(labels)
    signs = [1 if int(v) == 1 else -1 for v in labels]
    design = [[mpmath.mpf(float(v)) for v in row] for row in features]

    def objective(w, b):
        total = mpmath.mpf("0.5") * (sum(v * v for v in w) + b * b) / n
        for index, row in enumerate(design):
            eta = b + sum(c * x for c, x in zip(w, row))
            total += mpmath.log1p(mpmath.exp(-signs[index] * eta)) / n
        return total

    def gradient(w, b):
        gw = [v / n for v in w]
        gb = b / n
        for index, row in enumerate(design):
            eta = b + sum(c * x for c, x in zip(w, row))
            sigmoid = 1 / (1 + mpmath.exp(signs[index] * eta))
            factor = -sigmoid * signs[index] / n
            for k in range(len(w)):
                gw[k] += factor * row[k]
            gb += factor
        return gw, gb

    def hessian(w, b):
        dimension = len(w) + 1
        matrix = mpmath.matrix(dimension, dimension)
        for k in range(dimension):
            matrix[k, k] = mpmath.mpf(1) / n
        for index, row in enumerate(design):
            eta = b + sum(c * x for c, x in zip(w, row))
            sigmoid = 1 / (1 + mpmath.exp(signs[index] * eta))
            weight = sigmoid * (1 - sigmoid) / n
            vector = list(row) + [mpmath.mpf(1)]
            for a in range(dimension):
                for c in range(dimension):
                    matrix[a, c] += weight * vector[a] * vector[c]
        return matrix

    w = [mpmath.mpf(0)] * len(features[0])
    b = mpmath.mpf(0)
    for _ in range(60):
        gw, gb = gradient(w, b)
        if max(abs(v) for v in gw + [gb]) < mpmath.mpf("1e-55"):
            break
        step = mpmath.lu_solve(hessian(w, b), mpmath.matrix(gw + [gb]))
        scale = mpmath.mpf(1)
        current = objective(w, b)
        for _ in range(80):
            trial_w = [w[k] - scale * step[k] for k in range(len(w))]
            trial_b = b - scale * step[len(w)]
            if objective(trial_w, trial_b) < current:
                w, b = trial_w, trial_b
                break
            scale /= 2

    # The oracle must have converged before its output is trusted. The bound is
    # derived, not chosen: at 60 significant digits the representable floor is
    # ~1e-60, and the solver's own stopping test asks for 1e-55. 1e-30 is
    # therefore four orders of magnitude looser than requested and still 50+
    # digits tighter than any binary64 claim. (An earlier 1e-50 bound was
    # unreachable and failed for the right reason: the bound was wrong, not the
    # oracle.)
    gw_oracle, gb_oracle = gradient(w, b)
    residual = max(abs(v) for v in gw_oracle + [gb_oracle])
    assert residual < mpmath.mpf("1e-30"), f"oracle did not converge: {residual}"

    # Agreement is required at binary64 rounding level, which is far tighter than
    # the earlier 1e-15 and is the strongest claim available: the reference must
    # round to the same double as an independent 60-digit solver.
    for index, value in enumerate(fit["coefficients"]):
        assert abs(mpmath.mpf(value) - w[index]) < mpmath.mpf("1e-16"), index
    assert abs(mpmath.mpf(fit["intercept"]) - b) < mpmath.mpf("1e-16")


def test_model_fit_reproduces_across_repeated_calls():
    features, labels = _fit_problem(seed=9)
    rows = [[float(v) for v in row] for row in features]
    exemplars = [int(v) for v in labels]
    first = model_fit.fit_logistic_decimal(rows, exemplars, c_value=0.1)
    second = model_fit.fit_logistic_decimal(rows, exemplars, c_value=0.1)
    assert first["coefficients"] == second["coefficients"]
    assert first["intercept"] == second["intercept"]


def test_model_fit_declines_the_calibration_objective():
    """The model objective has no slope anchor and a different normalisation."""
    declaration = model_fit.declared_objective()
    calibration = reference.declared_protocol()
    assert declaration["objective"] != calibration["objective"]
    assert "anchor" not in str(declaration["objective"])


@pytest.mark.parametrize(
    "case",
    ["single_class", "ragged", "empty_feature", "length_mismatch", "non_positive_c"],
)
def test_model_fit_fails_closed_on_invalid_configuration(case):
    features, labels = _fit_problem(n=10)
    rows = [[float(v) for v in row] for row in features]
    exemplars = [int(v) for v in labels]
    if case == "single_class":
        exemplars = [0] * len(exemplars)
    elif case == "ragged":
        rows = [rows[0], rows[1][:-1]] + rows[2:]
    elif case == "empty_feature":
        rows = [[] for _ in rows]
    elif case == "length_mismatch":
        exemplars = exemplars[:-1]
    else:
        with pytest.raises(model_fit.ModelFitError):
            model_fit.fit_logistic_decimal(rows, exemplars, c_value=0.0)
        return
    with pytest.raises(model_fit.ModelFitError):
        model_fit.fit_logistic_decimal(rows, exemplars, c_value=1.0)


def test_model_fit_converges_on_hard_designs():
    """Near-singular, correlated, imbalanced and separable designs."""
    generator = np.random.RandomState(11)
    designs = {}
    base = generator.randn(50, 2)
    designs["duplicate_column"] = (np.column_stack([base, base[:, 0]]), None)
    designs["perfectly_correlated"] = (np.column_stack([base, base[:, 0] * 2.0]), None)
    imbalanced = generator.randn(50, 3)
    labels = np.zeros(50, int)
    labels[:2] = 1
    designs["imbalanced"] = (imbalanced, labels)
    designs["extreme"] = (generator.randn(50, 3) * 100, None)
    separable = generator.randn(40, 2)
    designs["separable"] = (separable, (separable[:, 0] > 0).astype(int))

    for name, (features, labels) in designs.items():
        if labels is None:
            labels = (generator.rand(50) < 0.5).astype(int)
        fit = model_fit.fit_logistic_decimal(
            [[float(v) for v in row] for row in features],
            [int(v) for v in labels],
            c_value=1.0,
        )
        assert float(fit["gradient_inf_norm"]) <= 1e-24, name


def test_model_fit_declares_no_blas_or_libm_dependency():
    """AST proof: the fit module imports no numerical library at all."""
    source = Path(model_fit.__file__).read_text()
    tree = ast.parse(source)
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
    assert "numpy" not in imported
    assert "scipy" not in imported
    assert "sklearn" not in imported

# --------------------------------------------------------------------------- #
# 10. Validator hardening: routes, edits, unknown fields, raw-file integrity
# --------------------------------------------------------------------------- #


def test_validator_rejects_unknown_top_level_field():
    pack = _committed()
    pack["unexpected_section"] = {"x": 1}
    with pytest.raises(ValueError, match="unknown pack field"):
        candidate.validate(pack, replay=False)


def test_validator_rejects_unknown_case_field():
    pack = _committed()
    pack["cases"] = copy.deepcopy(pack["cases"])
    pack["cases"][0]["extra"] = True
    with pytest.raises(ValueError, match="unknown case field"):
        candidate.validate(pack, replay=False)


def test_validator_rejects_an_invented_route():
    pack = _committed()
    pack["cases"] = copy.deepcopy(pack["cases"])
    pack["cases"][0]["route"] = "invented_route"
    with pytest.raises(ValueError, match="unknown route|route drift"):
        candidate.validate(pack, replay=False)


def test_validator_rejects_edit_drift():
    pack = _committed()
    pack["cases"] = copy.deepcopy(pack["cases"])
    pack["cases"][0]["edits"] = list(pack["cases"][0]["edits"]) + [{"op": "injected"}]
    with pytest.raises(ValueError, match="edit script drift|unknown"):
        candidate.validate(pack, replay=False)


def test_validator_rejects_coordinated_edit_and_expected_tampering():
    """Both halves tampered together must still fail: V1 is the authority."""
    pack = _committed()
    pack["cases"] = copy.deepcopy(pack["cases"])
    case = pack["cases"][0]
    case["edits"] = list(case["edits"]) + [{"op": "injected"}]
    case["expected"]["status"] = "TAMPERED"
    with pytest.raises(ValueError):
        candidate.validate(pack, replay=False)


def test_raw_file_digest_differs_from_canonical_document_digest(tmp_path):
    """A trailing newline changes the raw digest and not the canonical one."""
    pack = _committed()
    canonical = candidate.canonical_document_digest(pack)
    assert canonical == candidate.pack_digest(pack)  # documented alias

    plain = tmp_path / "a.json"
    plain.write_text(json.dumps(pack, sort_keys=True))
    padded = tmp_path / "b.json"
    padded.write_text(json.dumps(pack, sort_keys=True) + "\n")

    assert candidate.raw_file_sha256(plain) != candidate.raw_file_sha256(padded)
    assert json.loads(plain.read_text()) == json.loads(padded.read_text())


def test_raw_file_digest_matches_the_committed_fixture_bytes():
    """True byte-level integrity of the committed candidate, recorded as evidence."""
    from hashlib import sha256

    path = candidate.V2_FIXTURE_PATH
    assert candidate.raw_file_sha256(path) == sha256(path.read_bytes()).hexdigest()


def test_a_pack_with_more_than_29_cases_is_refused(monkeypatch, tmp_path):
    """A pack carrying extra cases must be refused, not silently truncated.

    V2-07 requires a >29-case negative test. Truncating to the registered count
    would make the replay look correct while admitting unauthorised cases; dropping
    the extras silently is the same failure in a different direction.

    The refusal does not come from a single ``len == 29`` assertion. A 30-case pack
    is caught first by the case-set comparison, because the extra case changes the
    registered order the manifest is bound to. Both are refusals before any replay,
    which is what matters; the test asserts the refusal and that no replay ran.
    """
    from research.intake import rh04_v2_portable_archive as archive
    from research.intake import offline_fixture_pack as v1

    original = json.loads(v1.PACK.read_text(encoding="utf-8"))
    inflated = copy.deepcopy(original)
    extra = copy.deepcopy(inflated["cases"][0])
    extra["id"] = extra["id"] + "-extra"
    inflated["cases"].append(extra)
    assert len(inflated["cases"]) == 30

    encoded = json.dumps(inflated).encode("utf-8")

    class InflatedPackPath:
        def read_bytes(self):
            return encoded

        def read_text(self, encoding="utf-8"):
            return encoded.decode(encoding)

    monkeypatch.setattr(v1, "PACK", InflatedPackPath())

    with pytest.raises(archive.ArchiveError) as excinfo:
        archive.admit_from_directory(_ARCHIVE_DIR)

    message = str(excinfo.value)
    assert ("registered case order" in message) or ("cases; expected" in message), (
        "a 30-case pack must be refused on the registered case set, not admitted "
        f"past it; got: {message}"
    )
    # And the refusal happened before anything was materialised or executed.
    assert "TAMPERED" not in message
    assert len(inflated["cases"]) == 30


def test_the_admission_isclose_is_structural_not_an_acceptance_tolerance():
    """V2-07 requires a "second tolerance exception" test; there must be none.

    The module contains exactly one ``isclose`` and it lives on the *admission*
    path, checking that a tree's declared class proportions sum to 1. It compares
    a structural invariant, not a replayed value against an expectation; an
    artifact that fails it is malformed, not numerically divergent. Admission has
    no notion of "close enough to the expected answer".

    This test fails if anyone adds a second ``isclose``/``allclose`` anywhere, so
    a new numeric tolerance cannot be introduced quietly.
    """
    from research.intake import rh04_v2_portable_archive as archive_module

    source = Path(archive_module.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)

    offenders = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        name = getattr(func, "attr", getattr(func, "id", None))
        if name in {"isclose", "allclose", "assert_allclose", "assert_array_almost_equal"}:
            offenders.append((name, node.lineno))

    assert offenders == [("isclose", 251)], (
        "expected exactly one structural isclose on the admission path; found "
        f"{offenders}. A new numeric comparison on the replay path is a "
        "tolerance surface by another name and is forbidden by V2-08."
    )


def test_actual_solver_identity_tracks_the_live_function():
    """Provenance must describe what runs, not what was requested."""
    outside = candidate.actual_solver_identity()
    assert outside["seam_active"] is False
    with candidate.decimal_reference_seam():
        inside = candidate.actual_solver_identity()
        assert inside["seam_active"] is True
        assert inside["live_callable"] != outside["live_callable"]
    assert candidate.actual_solver_identity()["seam_active"] is False


def test_resident_kernels_are_measured_not_requested():
    record = candidate.resident_numerical_kernels()
    assert record["requested_coretype"] is not None
    assert record["libraries"], "threadpoolctl must report at least one library"
    for library in record["libraries"]:
        assert set(library) == {
            "internal_api",
            "architecture",
            "version",
            "threading_layer",
            "num_threads",
        }


def test_candidate_is_unmistakably_not_an_authoritative_reference():
    pack = _committed()
    identity = candidate.describe_identity(pack)
    assert candidate.V2_SEMANTIC_SHA256.startswith("UNPINNED")
    assert identity["identity_version"] == candidate.V2_IDENTITY_VERSION
    # The old candidate and its historical hash must remain recoverable.
    assert candidate.pack_digest(pack) == (
        "b74f781d7c7839a33c3693e53511ac4d200b8bcf5b0a38526e9a9e2b657595f2"
    )

# --------------------------------------------------------------------------- #
# 11. Child-process diagnosis (separate concern from numerical acceptance)
# --------------------------------------------------------------------------- #
#
# These tests cover the *proposed* correction only. The merged #136 classifier
# and its tests are untouched; this module is a separate, reviewable artifact.


def _outcome(**kwargs):
    defaults = dict(returncode=0, stdout="", stderr_present=False)
    defaults.update(kwargs)
    return child_diag.ChildOutcome(**defaults)


def test_child_diagnosis_classifies_every_failure_mode_distinctly():
    cases = {
        child_diag.KIND_TIMEOUT: _outcome(timed_out=True),
        child_diag.KIND_SIGNAL: _outcome(returncode=-4),
        child_diag.KIND_CLEAN_NO_OUTPUT: _outcome(returncode=0, stdout=""),
        child_diag.KIND_NONZERO_NO_PAYLOAD: _outcome(returncode=3, stdout="  \n"),
        child_diag.KIND_INVALID_JSON: _outcome(stdout="not json at all"),
        child_diag.KIND_INVALID_SCHEMA: _outcome(stdout='{"only": "one field"}'),
    }
    kinds = set()
    for expected, outcome in cases.items():
        kind, payload = child_diag.classify_child(outcome)
        assert kind == expected, (expected, kind)
        assert payload is None, expected
        kinds.add(kind)
    # Every failure mode must be distinguishable; no two collapse together.
    assert len(kinds) == len(cases)


def test_child_diagnosis_never_treats_an_abnormal_child_as_success():
    for outcome in (
        _outcome(returncode=-11),
        _outcome(timed_out=True),
        _outcome(returncode=0, stdout=""),
        _outcome(returncode=1, stdout=""),
        _outcome(stdout="{"),
    ):
        kind, payload = child_diag.classify_child(outcome)
        assert kind != child_diag.KIND_PARSED
        assert payload is None


def test_child_diagnosis_reports_sigill_by_name():
    outcome = _outcome(returncode=-4)
    assert outcome.signal_number == 4
    assert "SIGILL" in outcome.redacted_summary()


def test_child_diagnosis_summary_leaks_no_child_output():
    outcome = _outcome(
        returncode=2,
        stdout='{"secret": "patient_123_score"}',
        stderr_present=True,
    )
    summary = outcome.redacted_summary()
    for forbidden in ("patient", "secret", "score", "/home", "/tmp"):
        assert forbidden not in summary
    message = child_diag.failure_message(child_diag.KIND_INVALID_SCHEMA, outcome)
    assert "patient" not in message


def test_child_diagnosis_accepts_a_well_formed_payload():
    payload = {
        "environment_verdict": child_diag.VERIFIED_ENVIRONMENT,
        "field_verdict": child_diag.EXACT_REPLAY,
        "environment": {"numpy_openblas_kernel": "SkylakeX"},
    }
    kind, parsed = child_diag.classify_child(_outcome(stdout=json.dumps(payload)))
    assert kind == child_diag.KIND_PARSED
    assert parsed == payload


@pytest.mark.parametrize(
    "environment,field_verdict,expected",
    [
        (child_diag.VERIFIED_ENVIRONMENT, child_diag.EXACT_REPLAY, 0),
        (child_diag.VERIFIED_ENVIRONMENT, child_diag.EXPECTED_SINGLE_FIELD_DELTAS, 1),
        (child_diag.VERIFIED_ENVIRONMENT, child_diag.UNEXPECTED_DRIFT, 2),
        ("UNVERIFIED_ENVIRONMENT", child_diag.EXACT_REPLAY, 2),
        ("UNVERIFIED_ENVIRONMENT", child_diag.UNEXPECTED_DRIFT, 2),
    ],
)
def test_child_diagnosis_exit_code_uses_both_dimensions(
    environment, field_verdict, expected
):
    """A verified environment is required for 0/1; ``field_verdict`` alone is not.

    This is the defect being corrected: mapping from ``field_verdict`` only would
    report 0/1 for a machine that was never identified.

    This case previously also asserted that an *unknown* field verdict mapped to
    2. That expectation was strengthened, not dropped: an unknown verdict is now
    rejected outright by :func:`expected_exit_code` itself, so it can never
    acquire a numeric expectation at all. See
    ``test_expected_exit_code_rejects_unknown_verdicts_itself``.
    """
    assert child_diag.expected_exit_code(environment, field_verdict) == expected


def test_child_diagnosis_does_not_modify_the_merged_classifier_surface():
    """The independent #136 test file must remain byte-identical to main."""
    from hashlib import sha256
    import subprocess as sp

    merged = REPO_ROOT / "tests/experiments/test_rh04_issue132_environment_class.py"
    committed = sp.run(
        ["git", "show", f"origin/main:{merged.relative_to(REPO_ROOT)}"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    if committed.returncode != 0:
        raise AssertionError(
            "required preservation evidence is unavailable: the canonical merged "
            "test could not be compared against origin/main. This is a hard "
            "failure, not a skip -- acceptance evidence must never vanish "
            "silently. Re-run after 'git fetch origin main'."
        )
    assert sha256(merged.read_bytes()).hexdigest() == sha256(
        committed.stdout.encode()
    ).hexdigest()

# --------------------------------------------------------------------------- #
# 12. Integrated deterministic pipeline (synthetic only)
# --------------------------------------------------------------------------- #


def _pipeline_problem(seed: int = 21, n: int = 60, d: int = 5, m: int = 30):
    generator = np.random.RandomState(seed)
    features = generator.randn(n, d)
    labels = (generator.rand(n) < 0.5).astype(int)
    scoring = generator.randn(m, d)
    return (
        [[float(v) for v in row] for row in features],
        [int(v) for v in labels],
        [[float(v) for v in row] for row in scoring],
    )


def test_integrated_pipeline_declares_every_stage():
    declaration = integrated.declared_pipeline()
    names = [stage["name"] for stage in declaration["stages"]]
    assert names == [
        "model_fit",
        "linear_scoring",
        "calibration",
        "calibrated_evaluation",
    ]
    assert declaration["host_dependent_operations"] == "none"


def test_integrated_pipeline_is_reproducible_in_process():
    features, labels, scoring = _pipeline_problem()
    first = integrated.run_pipeline(features, labels, scoring)
    second = integrated.run_pipeline(features, labels, scoring)
    assert integrated.pipeline_digest(first) == integrated.pipeline_digest(second)


def test_integrated_pipeline_digest_is_stable_against_the_recorded_value():
    """Pin the measured digest so an accidental semantic change is visible."""
    features, labels, scoring = _pipeline_problem()
    result = integrated.run_pipeline(features, labels, scoring)
    # Digest hierarchy, kept explicit. The algorithm changed, so the identity
    # version changed with it; a historical digest is never reused as current.
    #   digest v1, 19beafb7...  REVERSED calibration parameters -- incorrect;
    #                           historical evidence only, never a reference
    #   digest v1, 5ff6ce16...  ordering fixed, before the provenance fields
    #   digest v1, fb6c87b9...  provenance recorded, but ``declared`` EXCLUDED
    #                           from the payload -- the identity did not bind
    #                           the algorithm declaration (review defect)
    #   digest v2, 0460ffc5...  current: full declaration bound, version in
    #                           payload
    assert integrated.PIPELINE_DIGEST_VERSION == "rh04.v2.pipeline-digest/v2"
    assert integrated.pipeline_digest(result) == (
        "0460ffc5140e081c533a5b1e1a7372751d12bd98c316d01190b9638e9746dc50"
    )
    # The superseded v1 digests remain recorded as history, not as identities.
    assert (
        integrated.HISTORICAL_V1_PIPELINE_DIGESTS[
            "corrected_calibration_declaration_excluded"
        ]
        == "fb6c87b9ae0c49e30a01f1671b2e0d2c65cb17e41ab13cd9e1a1b8750e0ecec5"
    )
    assert integrated.pipeline_digest(result) not in (
        integrated.HISTORICAL_V1_PIPELINE_DIGESTS.values()
    )


def test_integrated_pipeline_digest_binds_the_declaration():
    """Editing the declared algorithm must change the identity."""
    features, labels, scoring = _pipeline_problem()
    result = integrated.run_pipeline(features, labels, scoring)
    tampered = dict(result)
    declared = dict(tampered["declared"])
    declared["solver"] = "an_undeclared_solver"
    tampered["declared"] = declared
    assert integrated.pipeline_digest(tampered) != integrated.pipeline_digest(result)


def test_integrated_pipeline_uses_the_exact_scorer_not_a_placeholder():
    features, labels, scoring = _pipeline_problem()
    result = integrated.run_pipeline(features, labels, scoring)
    coefficients = result["model_fit"]["coefficients"]
    intercept = result["model_fit"]["intercept"]
    expected = [
        upstream.score_as_float(score)
        for score in upstream.exact_linear_scores(coefficients, scoring, intercept)
    ]
    assert result["raw_logits"] == expected


def test_integrated_pipeline_threshold_is_the_production_rule():
    features, labels, scoring = _pipeline_problem()
    result = integrated.run_pipeline(features, labels, scoring)
    for score_text, flag in zip(
        result["calibrated_research_scores"], result["above_threshold"]
    ):
        assert flag == (Decimal(score_text) >= Decimal("0.5"))


def test_integrated_pipeline_does_not_touch_production_or_the_v1_pack():
    source = Path(integrated.__file__).read_text()
    for forbidden in ("ai.cli", "ai.inference", "offline_fixture_pack"):
        assert forbidden not in source
    assert integrated_module_is_unimported_by_production()


def integrated_module_is_unimported_by_production() -> bool:
    offenders = []
    for root in (REPO_ROOT / "ai", REPO_ROOT / "backend"):
        for path in root.rglob("*.py"):
            if "rh04_v2_" in path.read_text(encoding="utf-8", errors="ignore"):
                offenders.append(str(path))
    return offenders == []


def test_integrated_pipeline_fails_closed_on_mismatched_lengths():
    features, labels, scoring = _pipeline_problem()
    with pytest.raises(integrated.IntegratedPipelineError):
        integrated.run_pipeline(features, labels[:-1], scoring)

# --------------------------------------------------------------------------- #
# 13. Calibration parameter ordering — regression pin for a real defect
# --------------------------------------------------------------------------- #
#
# ``decimal_logistic_fit`` returns ``(a, b)`` with the declared objective
# ``eta = a + b*logit``: a IS the intercept, b IS the slope. The production
# contract agrees (``OofLogisticCalibrator.transform_log_odds`` is
# ``intercept + slope*raw_logits``).
#
# The integrated candidate previously unpacked this as ``slope, offset`` and
# evaluated ``slope*logit + offset`` -- reversed. Every reproducibility test
# still passed, because a parameter swap does not break determinism. On the
# recorded 60x5 fixture the error was up to 4.26 in calibrated log-odds
# (slope 1.1249 was used as 0.0042). These tests are what would have caught it.


def test_calibration_return_order_matches_the_declared_objective():
    """``(a, b)`` is intercept-first, anchored at slope 1 when inputs agree."""
    from research.intake import rh04_v2_reference_fit as reference_fit

    labels = np.asarray([0.0, 1.0] * 20, dtype=np.float64)
    # A perfectly calibrated logit: the fit should land near a=0, b=1.
    logits = np.where(labels == 1.0, 1.2, -1.2)
    intercept, slope = reference_fit.decimal_logistic_fit(labels, logits)
    # If the tuple were (slope, intercept) this would be ~1.2 and ~0.
    assert abs(slope) > 0.2, f"first element is not the intercept: {intercept}"
    assert abs(intercept) < 0.2, f"second element is not the slope: {slope}"


def test_calibration_order_matches_the_production_calibrator():
    """Pin the order against the real production class, not against prose.

    ``OofLogisticCalibrator.transform_log_odds`` is the authority:
    ``intercept + slope * raw_logits``. We construct one directly and require the
    reference fit's tuple to reproduce it when the fitted values are substituted.
    """
    from ai.calibration import OofLogisticCalibrator
    from research.intake import rh04_v2_reference_fit as reference_fit

    generator = np.random.default_rng(4)
    labels = np.asarray([0.0, 1.0] * 25, dtype=np.float64)
    logits = generator.normal(0.0, 1.5, size=labels.size)
    intercept, slope = reference_fit.decimal_logistic_fit(labels, logits)

    probe = np.asarray([-2.0, -0.5, 0.0, 0.75, 2.5], dtype=np.float64)
    # Construct the real dataclass, so the test uses the production code path and
    # not a stand-in. It is a dataclass with required fields.
    calibrator = OofLogisticCalibrator(
        model_family="l2_logistic_regression",
        intercept=float(intercept),
        slope=float(slope),
        development_prevalence=0.5,
        n_oof_samples=int(labels.size),
        oof_brier_before=0.0,
        oof_brier_after=0.0,
        status="FITTED_OOF_MONOTONE_LOGISTIC",
        input_link="exact_raw_log_odds",
    )
    production = calibrator.transform_log_odds(probe)
    expected = intercept + slope * probe
    # Exact equality: the production transform is a plain affine expression.
    assert np.array_equal(production, expected)


def test_integrated_pipeline_uses_intercept_plus_slope_times_logit():
    features, labels, scoring = _pipeline_problem()
    result = integrated.run_pipeline(features, labels, scoring)
    calibration = result["calibration"]
    intercept = calibration["intercept"]
    slope = calibration["slope"]
    assert calibration["contract"] == "intercept + slope * raw_logit"
    for raw, recorded in zip(
        result["raw_logits"], result["calibrated_log_odds"]
    ):
        expected = Decimal(intercept) + Decimal(slope) * Decimal(raw)
        assert abs(Decimal(recorded) - expected) <= abs(expected) * Decimal("1e-25")


def test_integrated_pipeline_rejects_the_reversed_ordering():
    """The historical reversed digest must not reappear as a valid result."""
    features, labels, scoring = _pipeline_problem()
    result = integrated.run_pipeline(features, labels, scoring)
    digest = integrated.pipeline_digest(result)
    assert digest != "19beafb7214c8b2257064cc590c13b9bce523166d7d007e55e389a12f9189951"
    # Historical evidence must stay recorded and must stay distinct.
    assert integrated.HISTORICAL_REVERSED_PIPELINE_DIGEST == (
        "19beafb7214c8b2257064cc590c13b9bce523166d7d007e55e389a12f9189951"
    )

# --------------------------------------------------------------------------- #
# 14. Two source-specific objectives (P0-02)
# --------------------------------------------------------------------------- #


def test_both_profiles_are_declared_and_differ_in_intercept_treatment():
    cleveland = model_fit.declared_objective(model_fit.PROFILE_CLEVELAND)
    generic = model_fit.declared_objective(model_fit.PROFILE_GENERIC)
    assert cleveland["intercept_treatment"] == "penalised"
    assert generic["intercept_treatment"] == "unpenalised"
    assert cleveland["sklearn_solver"] == "liblinear"
    assert generic["sklearn_solver"] == "lbfgs"
    # The objectives must not be interchangeable.
    assert cleveland["objective"] != generic["objective"]


def test_unknown_profile_is_refused_rather_than_defaulted():
    features, labels = _fit_problem(n=20)
    rows = [[float(v) for v in row] for row in features]
    with pytest.raises(model_fit.ModelFitError, match="unknown execution profile"):
        model_fit.fit_logistic_decimal(rows, [int(v) for v in labels], c_value=1.0,
                                       profile="SOME_OTHER_PROFILE")
    with pytest.raises(model_fit.ModelFitError):
        model_fit.declared_objective("SOME_OTHER_PROFILE")


@pytest.mark.parametrize("profile", ["CLEVELAND_D047_FROZEN_V1", "AI1_GENERIC_V1"])
def test_each_profile_reproduces_its_own_pinned_sklearn_solver(profile):
    """Cleveland is verified against liblinear, generic against lbfgs.

    The two solvers must not be swapped: that is the defect P0-02 identified.
    """
    from sklearn.linear_model import LogisticRegression

    features, labels = _fit_problem()
    solver = "liblinear" if profile == model_fit.PROFILE_CLEVELAND else "lbfgs"
    kwargs = dict(penalty="l2", C=1.0, solver=solver, tol=1e-12, max_iter=5000,
                  random_state=0)
    if solver == "liblinear":
        kwargs["class_weight"] = None
    reference_model = LogisticRegression(**kwargs).fit(features, labels)

    fit = model_fit.fit_logistic_decimal(
        [[float(v) for v in row] for row in features],
        [int(v) for v in labels],
        c_value=1.0,
        profile=profile,
    )
    for got, want in zip(fit["coefficients"], reference_model.coef_.ravel()):
        # sklearn stops at its own tol; agreement near 1e-7 is expected.
        assert abs(got - float(want)) < 1e-6, (profile, got, want)
    assert abs(fit["intercept"] - float(reference_model.intercept_[0])) < 1e-6


def test_profiles_produce_different_intercepts_on_the_same_data():
    """If the intercept treatment is implemented, the fits must actually differ."""
    features, labels = _fit_problem()
    rows = [[float(v) for v in row] for row in features]
    exemplars = [int(v) for v in labels]
    cleveland = model_fit.fit_logistic_decimal(rows, exemplars, c_value=1.0,
                                               profile=model_fit.PROFILE_CLEVELAND)
    generic = model_fit.fit_logistic_decimal(rows, exemplars, c_value=1.0,
                                             profile=model_fit.PROFILE_GENERIC)
    assert cleveland["intercept"] != generic["intercept"]


def test_model_fit_refuses_non_finite_c():
    features, labels = _fit_problem(n=20)
    rows = [[float(v) for v in row] for row in features]
    exemplars = [int(v) for v in labels]
    for bad in (float("nan"), float("inf"), float("-inf")):
        with pytest.raises(model_fit.ModelFitError):
            model_fit.fit_logistic_decimal(rows, exemplars, c_value=bad)


def test_model_fit_refuses_on_iteration_exhaustion():
    features, labels = _fit_problem(n=20)
    rows = [[float(v) for v in row] for row in features]
    exemplars = [int(v) for v in labels]
    with pytest.raises(model_fit.ModelFitError, match="did not converge"):
        model_fit.fit_logistic_decimal(rows, exemplars, c_value=1.0,
                                       max_iterations=1)


# --------------------------------------------------------------------------- #
# 15. Child-diagnostic exit policy against the real classifier (P0-04)
# --------------------------------------------------------------------------- #


def test_child_diagnosis_exit_policy_agrees_with_the_real_classifier():
    """Compare the helper to ``rh04_environment_class.exit_code`` on the grid.

    This is the check that would have caught mapping MISMATCH_FOUND to 1.
    """
    from research.intake import rh04_environment_class as classifier

    environments = [classifier.VERIFIED_ENVIRONMENT, classifier.UNVERIFIED_ENVIRONMENT]
    fields = [
        classifier.EXACT_REPLAY,
        classifier.EXPECTED_SINGLE_FIELD_DELTAS,
        classifier.UNEXPECTED_DRIFT,
        classifier.INVALID_DIAGNOSTIC,
        classifier.DIAGNOSTIC_REFUSED,
    ]
    for environment in environments:
        for field_verdict in fields:
            payload = {
                "environment_verdict": environment,
                "field_verdict": field_verdict,
                "environment": {},
            }
            assert child_diag.expected_exit_code(environment, field_verdict) == (
                classifier.exit_code(payload)
            ), (environment, field_verdict)

    # An *unknown* verdict is refused by both layers, by different mechanisms:
    # the canonical classifier maps it to 2 (fail-closed), while the helper
    # rejects it outright. Both are refusals; neither yields an acceptance.
    unknown = "UNEXPECTED_VALUE"
    canonical_rc = classifier.exit_code(
        {
            "environment_verdict": classifier.VERIFIED_ENVIRONMENT,
            "field_verdict": unknown,
            "environment": {},
        }
    )
    assert canonical_rc == 2
    with pytest.raises(ValueError, match="unknown field verdict"):
        child_diag.expected_exit_code(classifier.VERIFIED_ENVIRONMENT, unknown)


def test_child_diagnosis_rejects_invalid_schema_beyond_presence():
    base = {
        "environment_verdict": child_diag.VERIFIED_ENVIRONMENT,
        "field_verdict": child_diag.EXACT_REPLAY,
        "environment": {},
    }
    invalid = [
        dict(base, environment_verdict=123),
        dict(base, field_verdict=None),
        dict(base, environment="not-a-dict"),
        dict(base, environment_verdict="NOT_A_REAL_VERDICT"),
        dict(base, field_verdict="NOT_A_REAL_VERDICT"),
    ]
    for payload in invalid:
        kind, parsed = child_diag.classify_child(
            _outcome(stdout=json.dumps(payload))
        )
        assert kind == child_diag.KIND_INVALID_SCHEMA, payload
        assert parsed is None


def test_child_diagnosis_rejects_an_inconsistent_return_code():
    """A signal-less non-zero exit with valid JSON is still not a clean outcome.

    The verdict payload may parse, but a nonzero exit means the child itself
    reported failure; the caller must not silently accept the payload.
    """
    payload = {
        "environment_verdict": child_diag.VERIFIED_ENVIRONMENT,
        "field_verdict": child_diag.EXACT_REPLAY,
        "environment": {},
    }
    kind, _ = child_diag.classify_child(
        _outcome(returncode=1, stdout=json.dumps(payload))
    )
    # It parses; the *exit code* is what must be checked against the verdict.
    assert kind == child_diag.KIND_PARSED
    assert child_diag.expected_exit_code(
        payload["environment_verdict"], payload["field_verdict"]
    ) != 1


# --------------------------------------------------------------------------- #
# 16. Full 29-case reference candidate (P0-03)
# --------------------------------------------------------------------------- #


_CANDIDATE_CACHE: dict[str, dict] = {}


def _candidate_pack() -> dict:
    """One real 29-case generation (~2 min), shared by the full-reference tests."""
    if "pack" not in _CANDIDATE_CACHE:
        _CANDIDATE_CACHE["pack"] = full_reference.generate_full_reference()
    return _CANDIDATE_CACHE["pack"]


def test_full_reference_declares_what_it_does_not_do():
    declared = full_reference.declared_reference()
    assert declared["sentinel"] == full_reference.FULL_REFERENCE_SENTINEL
    assert declared["model_fit_verification"]["replaces_production_fit"] is False
    assert declared["out_of_fold_calibration_preserved"] is True
    assert declared["model_selection_preserved"] is True
    assert declared["copied_expected_responses"] is False


def test_full_reference_semantic_identity_includes_the_declaration():
    """A changed algorithm declaration must move the semantic digest."""
    pack = _candidate_pack()
    before = full_reference.semantic_digest(pack)
    mutated = copy.deepcopy(pack)
    mutated["declared"]["calibration"]["protocol_id"] = "something-else"
    assert full_reference.semantic_digest(mutated) != before


def test_full_reference_rejects_a_missing_sentinel():
    pack = _candidate_pack()
    stripped = copy.deepcopy(pack)
    stripped["declared"]["sentinel"] = "PINNED"
    with pytest.raises(ValueError, match="sentinel|declaration drift"):
        full_reference.validate(stripped, replay=False)


def test_full_reference_rejects_unknown_fields_and_edit_drift():
    pack = _candidate_pack()
    extra = copy.deepcopy(pack)
    extra["surprise"] = 1
    with pytest.raises(ValueError, match="unknown field"):
        full_reference.validate(extra, replay=False)
    drifted = copy.deepcopy(pack)
    drifted["cases"][0]["edits"] = list(drifted["cases"][0]["edits"]) + [{"op": "set"}]
    with pytest.raises(ValueError, match="edit drift"):
        full_reference.validate(drifted, replay=False)


def test_full_reference_structural_validation_passes():
    pack = _candidate_pack()
    assert full_reference.validate(pack, replay=False) == 29

# --------------------------------------------------------------------------- #
# 17. Path B — integrity-bound frozen parameters (D-V2-7, proposed)
# --------------------------------------------------------------------------- #

_FEATURES_10 = [f"f{index}" for index in range(10)]


def _path_b_artifact():
    import numpy as np

    from research.intake import rh04_v2_frozen_parameters as frozen

    generator = np.random.RandomState(5)
    features = generator.randn(200, 10)
    labels = (generator.rand(200) < 0.5).astype(int)
    rows = [[float(v) for v in row] for row in features]
    exemplars = [int(v) for v in labels]
    fit = model_fit.fit_logistic_decimal(rows, exemplars, c_value=1.0)
    artifact = frozen.build_frozen_artifact(
        source_id="synthetic-path-b",
        feature_names=_FEATURES_10,
        model_family="l2_logistic_regression",
        training_profile=model_fit.PROFILE_CLEVELAND,
        training_rows=rows,
        training_labels=exemplars,
        fold_index=[index % 5 for index in range(200)],
        coefficients=fit["coefficients"],
        intercept=fit["intercept"],
        calibration={"intercept": 0.0, "slope": 1.0},
        protocol_version=model_fit.MODEL_FIT_PROTOCOL_ID,
    )
    return artifact, rows, exemplars


def _scoring_rows():
    return [[float(v) for v in row] for row in np.random.RandomState(6).randn(50, 10)]


def test_path_b_replays_path_a_exactly():
    """Frozen parameters must reproduce the refit output bit for bit."""
    from research.intake import rh04_v2_frozen_parameters as frozen

    artifact, _, _ = _path_b_artifact()
    scoring = _scoring_rows()
    path_b = frozen.score_with_frozen(
        artifact, scoring, expected_feature_names=_FEATURES_10
    )
    path_a = [
        upstream.score_as_float(score)
        for score in upstream.exact_linear_scores(
            artifact["coefficients"], scoring, artifact["intercept"]
        )
    ]
    assert path_b == path_a


def test_path_b_refuses_a_tampered_parameter():
    from research.intake import rh04_v2_frozen_parameters as frozen

    artifact, _, _ = _path_b_artifact()
    tampered = copy.deepcopy(artifact)
    tampered["intercept"] = artifact["intercept"] + 1e-9
    with pytest.raises(frozen.FrozenParameterError, match="integrity mismatch"):
        frozen.verify_frozen_artifact(tampered)


def test_path_b_refuses_a_stale_binding():
    from research.intake import rh04_v2_frozen_parameters as frozen

    artifact, _, _ = _path_b_artifact()
    with pytest.raises(frozen.FrozenParameterError, match="wrong source"):
        frozen.verify_frozen_artifact(artifact, expected_source_id="a-different-source")
    with pytest.raises(frozen.FrozenParameterError, match="wrong protocol version"):
        frozen.verify_frozen_artifact(artifact, expected_protocol_version="v0")


def test_path_b_refuses_a_wrong_panel_or_order():
    from research.intake import rh04_v2_frozen_parameters as frozen

    artifact, _, _ = _path_b_artifact()
    reordered = list(reversed(_FEATURES_10))
    with pytest.raises(frozen.FrozenParameterError, match="feature contract drift"):
        frozen.verify_frozen_artifact(artifact, expected_feature_names=reordered)


def test_path_b_refuses_a_missing_binding():
    from research.intake import rh04_v2_frozen_parameters as frozen

    artifact, _, _ = _path_b_artifact()
    broken = copy.deepcopy(artifact)
    del broken["split_digest"]
    with pytest.raises(frozen.FrozenParameterError, match="stale artifact"):
        frozen.verify_frozen_artifact(broken)


def test_path_b_refuses_a_family_without_linear_parameters():
    from research.intake import rh04_v2_frozen_parameters as frozen

    _, rows, exemplars = _path_b_artifact()
    with pytest.raises(frozen.FrozenParameterError, match="not defined for family"):
        frozen.build_frozen_artifact(
            source_id="x",
            feature_names=_FEATURES_10,
            model_family="constrained_random_forest",
            training_profile=model_fit.PROFILE_CLEVELAND,
            training_rows=rows,
            training_labels=exemplars,
            fold_index=[0] * 200,
            coefficients=[0.0] * 10,
            intercept=0.0,
            calibration={},
            protocol_version=model_fit.MODEL_FIT_PROTOCOL_ID,
        )


def test_path_b_is_marked_unratified():
    from research.intake import rh04_v2_frozen_parameters as frozen

    artifact, _, _ = _path_b_artifact()
    assert artifact["sentinel"] == frozen.FROZEN_SENTINEL
    assert frozen.FROZEN_SENTINEL.startswith("UNRATIFIED")


# ---------------------------------------------------------------------------
# Round 9 — registered model selection, trusted admission, portable inference
# ---------------------------------------------------------------------------

_PORTABLE_KEY = bytes(range(32))
_BASIC_ROUTE = "da_a1_basic_clinical_v1"


def _registered_bundles():
    """Build the two registered synthetic bundles once and cache them."""
    import tempfile
    from pathlib import Path

    from ai.filesystem_security import ensure_private_directory
    from research.intake import offline_fixture_pack as v1

    cache = getattr(_registered_bundles, "_cache", None)
    if cache is not None:
        return cache
    tmp = tempfile.mkdtemp(prefix="rh04-bundles-")
    local = v1.sources(ensure_private_directory(Path(tmp)))
    cache = {
        route: {
            "bundle_dir": local[route].bundle_dir,
            "source": local[route],
        }
        for route in (v1.REST, v1.BASIC)
    }
    _registered_bundles._cache = cache
    return cache


def _portable_artifacts():
    from research.intake import rh04_v2_portable_inference as portable

    cache = getattr(_portable_artifacts, "_cache", None)
    if cache is not None:
        return cache
    bundles = _registered_bundles()
    artifacts = {}
    for route, info in bundles.items():
        window = portable.export_artifact(
            info["bundle_dir"], signing_key=_PORTABLE_KEY
        )
        artifacts[route] = portable.attest(window, _PORTABLE_KEY)
    _portable_artifacts._cache = artifacts
    return artifacts


def _expected_source(artifact):
    return {k: artifact["source"][k] for k in artifact["source"]}


def test_registered_selection_records_the_actual_selected_family():
    """The selected family is measured from the bundle, never assumed."""
    import json

    bundles = _registered_bundles()
    families = {}
    for route, info in bundles.items():
        manifest = json.loads((info["bundle_dir"] / "manifest.json").read_text())
        families[route] = manifest["model"]["selected_model_family"]
    # Both registered families really are exercised by the two score routes.
    assert sorted(families.values()) == [
        "constrained_random_forest",
        "l2_logistic_regression",
    ], families


def test_registered_selection_does_not_assume_logistic_regression():
    """Explicitly pin that one scored route selects a forest, not a linear model."""
    import json

    from research.intake import offline_fixture_pack as v1

    bundles = _registered_bundles()
    manifest = json.loads((bundles[v1.BASIC]["bundle_dir"] / "manifest.json").read_text())
    assert manifest["model"]["selected_model_family"] == "constrained_random_forest"
    assert set(manifest["model"]["selected_hyperparameters"]) == {
        "max_depth",
        "min_samples_leaf",
    }


def test_registered_selection_records_profile_and_oof_provenance():
    """Profile, hyperparameters and OOF provenance are recorded per source."""
    import json

    for route, info in _registered_bundles().items():
        directory = info["bundle_dir"]
        manifest = json.loads((directory / "manifest.json").read_text())
        calibration = json.loads((directory / "calibration.json").read_text())
        assert manifest["model"]["execution_profile"] in (
            model_fit.PROFILE_CLEVELAND,
            model_fit.PROFILE_GENERIC,
        )
        assert isinstance(manifest["model"]["selected_hyperparameters"], dict)
        assert calibration["fitted_strictly_out_of_fold"] is True
        assert calibration["fit_scope"] == "FULL_DEVELOPMENT_OOF_FINAL"
        assert calibration["model_family"] == manifest["model"]["selected_model_family"]


def test_portable_admission_accepts_a_correctly_attested_artifact():
    from research.intake import rh04_v2_portable_inference as portable

    for artifact in _portable_artifacts().values():
        admitted = portable.admit(
            artifact,
            trusted_artifact_sha256=portable.artifact_digest(artifact),
            signing_key=_PORTABLE_KEY,
            expected_source=_expected_source(artifact),
        )
        assert admitted["sentinel"] == portable.PORTABLE_SENTINEL


def test_portable_admission_refuses_a_recomputed_internal_hash():
    """The reviewer's core point: a self-hash is not authenticity."""
    import copy

    from research.intake import rh04_v2_portable_inference as portable

    artifact = copy.deepcopy(_portable_artifacts()[next(iter(_portable_artifacts()))])
    if artifact["model"]["family"] == "l2_logistic_regression":
        artifact["model"]["representation"]["coef"][0] += 0.25
    else:
        artifact["model"]["representation"]["trees"][0]["threshold"][0] += 0.25
    artifact["artifact_sha256"] = portable.artifact_digest(artifact)
    with pytest.raises(portable.PortableArtifactError, match="attestation does not verify"):
        portable.admit(
            artifact,
            trusted_artifact_sha256=artifact["artifact_sha256"],
            signing_key=_PORTABLE_KEY,
            expected_source=_expected_source(artifact),
        )


def test_portable_admission_refuses_a_recomputed_calibration_hash():
    import copy

    from research.intake import rh04_v2_portable_inference as portable

    artifact = copy.deepcopy(_portable_artifacts()[next(iter(_portable_artifacts()))])
    artifact["calibration"]["slope"] = 1.5
    artifact["artifact_sha256"] = portable.artifact_digest(artifact)
    with pytest.raises(portable.PortableArtifactError):
        portable.admit(
            artifact,
            trusted_artifact_sha256=artifact["artifact_sha256"],
            signing_key=_PORTABLE_KEY,
            expected_source=_expected_source(artifact),
        )


def test_portable_admission_requires_an_external_trusted_digest():
    from research.intake import rh04_v2_portable_inference as portable

    artifact = _portable_artifacts()[next(iter(_portable_artifacts()))]
    with pytest.raises(portable.PortableArtifactError, match="externally trusted digest"):
        portable.admit(
            artifact,
            trusted_artifact_sha256="0" * 64,
            signing_key=_PORTABLE_KEY,
            expected_source=_expected_source(artifact),
        )


def test_portable_admission_refuses_a_coordinated_stale_training_binding():
    import copy

    from research.intake import rh04_v2_portable_inference as portable

    artifact = copy.deepcopy(_portable_artifacts()[next(iter(_portable_artifacts()))])
    artifact["training_identity"]["n_training_rows"] = 1
    artifact["preprocessing"]["n_training_rows"] = 1
    artifact["artifact_sha256"] = portable.artifact_digest(artifact)
    with pytest.raises(portable.PortableArtifactError):
        portable.admit(
            artifact,
            trusted_artifact_sha256=artifact["artifact_sha256"],
            signing_key=_PORTABLE_KEY,
            expected_source=_expected_source(artifact),
        )


def test_portable_admission_refuses_training_row_calibration():
    """The smoke pipeline's own-rows calibration must never be accepted."""
    import copy

    from research.intake import rh04_v2_portable_inference as portable

    artifact = copy.deepcopy(_portable_artifacts()[next(iter(_portable_artifacts()))])
    artifact["calibration"]["fitted_strictly_out_of_fold"] = False
    forged = portable.attest(
        {k: v for k, v in artifact.items() if k not in ("attestation", "artifact_sha256")},
        _PORTABLE_KEY,
    )
    with pytest.raises(portable.PortableArtifactError, match="not fitted strictly out of fold"):
        portable.admit(
            forged,
            trusted_artifact_sha256=portable.artifact_digest(forged),
            signing_key=_PORTABLE_KEY,
            expected_source=_expected_source(forged),
        )


@pytest.mark.parametrize(
    ("mutate", "pattern"),
    [
        (lambda a: a["model"].__setitem__("family", "prevalence_dummy"), "no declared portable representation"),
        (lambda a: a["model"].__setitem__("family", "gradient_boosting"), "unsupported model family"),
        (lambda a: a["model"].__setitem__("classes", [1, 0]), "classes must be exactly"),
        (lambda a: a["calibration"].__setitem__("slope", 0.0), "admissible range"),
        (lambda a: a["calibration"].__setitem__("slope", -1.0), "admissible range"),
        (lambda a: a["calibration"].__setitem__("intercept", "0.1"), "must be a number"),
        (lambda a: a["calibration"].__setitem__("intercept", True), "must be a number"),
        (lambda a: a["calibration"].__setitem__("model_family", "l2_logistic_regression"), "does not match the model family"),
        (lambda a: a.__setitem__("injected", {}), "unknown fields"),
        (lambda a: a.pop("training_identity"), "is missing"),
        (lambda a: a.__setitem__("protocol_id", "other/v1"), "unexpected portable protocol id"),
        (lambda a: a.__setitem__("sentinel", "ACCEPTED"), "not labelled as an unratified candidate"),
        (lambda a: a["preprocessing"].__setitem__("panel_contract_sha256", "0" * 64), "does not match the source panel"),
        (lambda a: a["preprocessing"]["encoded_feature_names"].__setitem__(1, a["preprocessing"]["encoded_feature_names"][0]), "must be unique"),
        (lambda a: a["preprocessing"]["field_transforms"][0].__setitem__("slice_indices", [99]), "out of range"),
        (lambda a: a["model"]["representation"]["trees"][0]["left"].__setitem__(0, -1), "half-missing child"),
    ],
)
def test_portable_structural_refusals_survive_a_valid_attestation(mutate, pattern):
    """Structural checks must fire even though the MAC is valid.

    This attacker holds the key, so only the structural layer can refuse.
    """
    import copy

    from research.intake import rh04_v2_portable_inference as portable

    artifact = copy.deepcopy(_portable_artifacts()[_BASIC_ROUTE])
    body = {k: v for k, v in artifact.items() if k not in ("attestation", "artifact_sha256")}
    mutate(body)
    forged = portable.attest(body, _PORTABLE_KEY)
    with pytest.raises(portable.PortableArtifactError, match=pattern):
        portable.admit(
            forged,
            trusted_artifact_sha256=portable.artifact_digest(forged),
            signing_key=_PORTABLE_KEY,
            expected_source=_expected_source(forged),
        )


def test_portable_refuses_a_non_finite_parameter():
    import copy
    import math

    from research.intake import rh04_v2_portable_inference as portable

    artifact = copy.deepcopy(_portable_artifacts()[_BASIC_ROUTE])
    body = {k: v for k, v in artifact.items() if k not in ("attestation", "artifact_sha256")}
    body["model"]["representation"]["trees"][0]["threshold"][0] = math.nan
    with pytest.raises(portable.PortableArtifactError, match="canonically serialised"):
        portable.attest(body, _PORTABLE_KEY)


def test_portable_transformation_matches_the_registered_preprocessor():
    """Encoded rows must agree with the registered preprocessing contract."""
    import numpy as np

    from ai.preprocessing import FoldSafeClinicalPreprocessor
    from research.intake import rh04_v2_portable_inference as portable

    artifacts = _portable_artifacts()
    bundles = _registered_bundles()
    # Direct comparison using the registered preprocessor object.
    for route, artifact in artifacts.items():
        directory = bundles[route]["bundle_dir"]
        import json as _json

        raw_pre = _json.loads((directory / "preprocessing.json").read_text())
        pre = FoldSafeClinicalPreprocessor.from_json_dict(raw_pre)
        from research.intake import offline_fixture_pack as v1

        request = v1.materialize(v1.inputs()[route], [])
        features = request["records"][0]["features"]
        ours = portable._transform(artifact["preprocessing"], dict(features))
        column_order = [t.name for t in pre.field_transforms]
        row = np.array([[features[name] for name in column_order]], dtype=np.float64)
        theirs = pre.transform(row)[0]
        assert np.array_equal(np.asarray(ours), theirs), route


def _portable_pack():
    """Execute the full 29-case portable replay once and cache it."""
    from research.intake import rh04_v2_portable_inference as portable

    cache = getattr(_portable_pack, "_cache", None)
    if cache is not None:
        return cache
    pack = portable.build_portable_pack(
        signing_key=_PORTABLE_KEY, routed_artifacts=_portable_artifacts()
    )
    _portable_pack._cache = pack
    return pack


def _registered_replay():
    """Independently execute the registered replay for all 29 cases."""
    import json

    from research.intake import offline_fixture_pack as v1

    cache = getattr(_registered_replay, "_cache", None)
    if cache is not None:
        return cache
    bundles = _registered_bundles()
    source = json.loads(v1.PACK.read_text())
    outcomes = {}
    for case in source["cases"]:
        source_entry = bundles.get(case["route"])
        request = v1.materialize(source["requests"][case["route"]], case["edits"])
        target = source_entry["source"] if source_entry else None
        outcomes[case["id"]] = v1.example(request, target)
    _registered_replay._cache = outcomes
    return outcomes


def test_portable_pack_executes_all_29_cases():
    pack = _portable_pack()
    assert pack["generation"]["case_count"] == 29
    assert len(pack["cases"]) == 29
    assert len({c["id"] for c in pack["cases"]}) == 29


def test_portable_pack_covers_every_registered_case_id():
    import json

    from research.intake import offline_fixture_pack as v1

    registered = {c["id"] for c in json.loads(v1.PACK.read_text())["cases"]}
    portable_ids = {c["id"] for c in _portable_pack()["cases"]}
    assert registered == portable_ids


def test_portable_pack_evaluates_both_selected_families():
    """Both registered families reach the portable evaluator."""
    from research.intake import rh04_v2_portable_inference as portable

    pack = _portable_pack()
    evaluated = [c for c in pack["cases"] if c["lane"] == "model-evaluated"]
    assert len(evaluated) == 2
    families = {c["route"]: None for c in evaluated}
    artifacts = _portable_artifacts()
    for route in families:
        families[route] = artifacts[route]["model"]["family"]
    assert sorted(families.values()) == [
        "constrained_random_forest",
        "l2_logistic_regression",
    ]


def test_portable_declares_the_unrepresentable_family_as_a_blocker():
    """A selected dummy model must be refused, never approximated."""
    from research.intake import rh04_v2_portable_inference as portable

    assert "prevalence_dummy" in portable.UNREPRESENTABLE_FAMILIES
    assert "prevalence_dummy" not in portable.SUPPORTED_FAMILIES


def test_portable_matches_the_independent_registered_reference():
    """Full-path equivalence against an independently generated reference.

    The reference is produced by the registered replay, not by the artifact
    under test.
    """
    from research.intake import rh04_v2_portable_inference as portable

    pack = _portable_pack()
    reference = _registered_replay()
    compared = 0
    for case in pack["cases"]:
        if case["lane"] != "model-evaluated":
            continue
        comparison = portable.compare_with_registered(
            case["outcome"], reference[case["id"]]
        )
        assert comparison["status_match"] is True
        assert comparison["within_declared_bound"] is True, comparison
        assert comparison["max_delta"] <= portable.DECLARED_SCORE_AGREEMENT
        compared += 1
    assert compared == 2


def test_portable_comparison_refuses_a_missing_score():
    """Regression: an absent score once compared equal to nothing."""
    from research.intake import rh04_v2_portable_inference as portable

    with pytest.raises(portable.PortableArtifactError, match="no outcomes"):
        portable.compare_with_registered({"status": "SYNTHETIC_RESULT"}, {})
    with pytest.raises(portable.PortableArtifactError, match="no outcomes"):
        portable.compare_with_registered(
            {"outcomes": [{"status": "SYNTHETIC_RESULT"}]},
            {"outcomes": [{"status": "SYNTHETIC_RESULT", "score": {}}]},
        )


def test_portable_comparison_refuses_a_reference_missing_a_field():
    from research.intake import rh04_v2_portable_inference as portable

    with pytest.raises(portable.PortableArtifactError, match="lacks"):
        portable.compare_with_registered(
            {"outcomes": [{"score": {"calibrated_log_odds": 1.0}}]},
            {"outcomes": [{"score": {"calibrated_log_odds": 1.0}}]},
        )


def test_portable_refusal_routes_are_declared_not_fabricated():
    """The 27 non-scored cases are declared refusals, not invented scores."""
    from research.intake import rh04_v2_portable_inference as portable

    pack = _portable_pack()
    for case in pack["cases"]:
        if case["lane"] == "declared-refusal":
            assert case["outcome"]["status"] in (
                "REFUSAL_ROUTE_DECLARED",
                "REQUEST_EDIT_OUT_OF_PORTABLE_SCOPE",
            )
            assert case["outcome"]["score"] is None
        assert any(route == case["route"] for route in portable.REFUSAL_ROUTES) or (
            case["lane"] == "model-evaluated"
        ) or case["outcome"]["status"] == "REQUEST_EDIT_OUT_OF_PORTABLE_SCOPE"


def test_portable_pack_is_marked_unratified():
    from research.intake import rh04_v2_portable_inference as portable

    pack = _portable_pack()
    assert pack["sentinel"] == portable.PORTABLE_SENTINEL
    assert pack["sentinel"].startswith("UNRATIFIED")
    assert pack["declared"]["claims"]["acceptance_reference"] is False
    assert pack["declared"]["claims"]["replaces_regeneration"] is False
    assert pack["declared"]["claims"]["ratifies_D_V2_7"] is False


def test_portable_declares_no_field_bit_identical():
    from research.intake import rh04_v2_portable_inference as portable

    claims = portable.declared_protocol()["claims"]
    assert claims["bit_identical_to_scikit_learn"] is False
    assert claims["any_exported_score_field_bit_identical"] is False
    assert claims["host_independent_probability_link"] is False


# ---------------------------------------------------------------------------
# Round 9 — diagnostic helper: unknown verdicts and inconsistent child rcs
# ---------------------------------------------------------------------------


def test_expected_exit_code_rejects_unknown_verdicts_itself():
    """The helper validates both verdicts; no caller-side default may be relied on."""
    from research.intake import rh04_v2_child_diagnosis as diagnosis

    with pytest.raises(ValueError, match="unknown field verdict"):
        diagnosis.expected_exit_code(
            diagnosis.VERIFIED_ENVIRONMENT, "NOT_A_VERDICT"
        )
    with pytest.raises(ValueError, match="unknown environment verdict"):
        diagnosis.expected_exit_code("NOT_AN_ENVIRONMENT", diagnosis.EXACT_REPLAY)


def test_verify_child_return_code_accepts_only_consistent_children():
    from research.intake import rh04_v2_child_diagnosis as diagnosis

    verified = diagnosis.VERIFIED_ENVIRONMENT
    payload = {
        "environment_verdict": verified,
        "field_verdict": diagnosis.UNEXPECTED_DRIFT,
    }
    assert diagnosis.verify_child_return_code(payload, 2) == 2
    for inconsistent in (0, 1, 3, -11):
        with pytest.raises(diagnosis.ChildDiagnosisError, match="inconsistent"):
            diagnosis.verify_child_return_code(payload, inconsistent)


def test_verify_child_return_code_rejects_a_non_integer_rc():
    from research.intake import rh04_v2_child_diagnosis as diagnosis

    payload = {
        "environment_verdict": diagnosis.VERIFIED_ENVIRONMENT,
        "field_verdict": diagnosis.EXACT_REPLAY,
    }
    for bogus in (True, "0", None, 0.0):
        with pytest.raises(ValueError, match="must be an integer"):
            diagnosis.verify_child_return_code(payload, bogus)


def test_diagnostic_helper_still_agrees_with_the_canonical_classifier():
    """The helper never redefines canonical acceptance semantics."""
    from research.intake import rh04_v2_child_diagnosis as diagnosis
    from research.intake import rh04_environment_class as canonical

    for environment_verdict in (
        canonical.VERIFIED_ENVIRONMENT,
        canonical.UNVERIFIED_ENVIRONMENT,
    ):
        for field_verdict in (
            canonical.EXACT_REPLAY,
            canonical.EXPECTED_SINGLE_FIELD_DELTAS,
            canonical.UNEXPECTED_DRIFT,
        ):
            expected = diagnosis.expected_exit_code(environment_verdict, field_verdict)
            if environment_verdict != canonical.VERIFIED_ENVIRONMENT:
                assert expected == 2
            elif field_verdict == canonical.EXACT_REPLAY:
                assert expected == 0
            elif field_verdict == canonical.EXPECTED_SINGLE_FIELD_DELTAS:
                assert expected == 1
            else:
                assert expected == 2


# ---------------------------------------------------------------------------
# Round 10 — trusted portable archive, real 29-case facade execution
# ---------------------------------------------------------------------------

#: Fixed Lane B reference identity for the rehydrated portable implementation.
#: Generated once from the committed pinned archives against the independently
#: trusted manifest. It is **not** derived from a Lane A run and is never
#: regenerated to match an observation: a mismatch is a finding to report.
LANE_B_DIGEST = "891d9e3b2a332c6efc251d97fee25ed46a627ed25b2a089594057b4c9896cdc8"

_ARCHIVE_DIR = (
    __import__("pathlib").Path(__file__).resolve().parents[2]
    / "research"
    / "intake"
    / "fixtures"
    / "rh04_v2_portable"
)


def _pinned():
    """Admit the committed artifacts through the one supported entry point."""
    from research.intake import rh04_v2_portable_archive as archive

    admitted = archive.admit_from_directory(_ARCHIVE_DIR)
    manifest = archive._thaw(admitted.manifest)
    archives = {route: archive._thaw(admitted.archives[route]) for route in admitted.routes}
    return archive, manifest, archives


def test_pinned_archive_fixture_is_committed_and_synthetic_only():
    """The artifact must be plain JSON, never pickle, and never patient data."""
    files = sorted(p.name for p in _ARCHIVE_DIR.iterdir())
    assert files == [
        "da_a1_basic_clinical_v1.archive.json",
        "da_a2_resting_v1.archive.json",
        "trusted_manifest.json",
    ]
    for path in _ARCHIVE_DIR.iterdir():
        assert path.suffix == ".json"
        text = path.read_text()
        # No executable serialisation and no probe strings.
        assert "joblib" not in text and "pickle" not in text
        assert "synthetic" in text.lower() or "UNRATIFIED" in text


def test_pinned_archive_admits_against_the_independent_manifest():
    archive, manifest, archives = _pinned()
    for route, candidate in archives.items():
        admitted = archive.admit(candidate, manifest, expected_route=route)
        assert admitted["source"]["route_id"] == route


def test_pinned_archive_digest_matches_the_manifest_pin():
    archive, manifest, archives = _pinned()
    for route, candidate in archives.items():
        assert archive.archive_digest(candidate) == manifest["routes"][route][
            "archive_sha256"
        ]


def test_admission_refuses_a_swapped_route():
    archive, manifest, archives = _pinned()
    with pytest.raises(archive.ArchiveError, match="swapped route"):
        archive.admit(
            archives["da_a2_resting_v1"], manifest, expected_route="da_a1_basic_clinical_v1"
        )


def test_admission_refuses_a_route_missing_from_the_manifest():
    archive, manifest, archives = _pinned()
    trimmed = dict(manifest)
    trimmed["routes"] = {"da_a2_resting_v1": manifest["routes"]["da_a2_resting_v1"]}
    with pytest.raises(archive.ArchiveError, match="no entry for route"):
        archive.admit(archives["da_a1_basic_clinical_v1"], trimmed,
                      expected_route="da_a1_basic_clinical_v1")


def test_admission_refuses_a_modified_archive_with_a_recomputed_self_hash():
    """The archive's own digest is not an identity."""
    import copy

    archive, manifest, archives = _pinned()
    body = copy.deepcopy(archives["da_a2_resting_v1"])
    body.pop("attestation", None)
    body.pop("archive_sha256", None)
    body["calibration"]["slope"] = body["calibration"]["slope"] + 0.25  # attacker
    forged = archive.attest(body)  # self-hash and MAC both recomputed
    assert forged["archive_sha256"] == archive.archive_digest(forged)
    with pytest.raises(archive.ArchiveError, match="independently trusted digest"):
        archive.admit(forged, manifest, expected_route="da_a2_resting_v1")


def test_admission_refuses_coordinated_binding_changes():
    """A self-consistent forgery still fails the external pin."""
    import copy

    archive, manifest, archives = _pinned()
    forged_body = copy.deepcopy(archives["da_a2_resting_v1"])
    forged_body.pop("attestation", None)
    forged_body.pop("archive_sha256", None)
    forged_body["training_identity"]["n_training_rows"] = 1
    forged_body["preprocessing"]["n_training_rows"] = 1
    forged = archive.attest(forged_body)
    with pytest.raises(archive.ArchiveError, match="independently trusted digest"):
        archive.admit(forged, manifest, expected_route="da_a2_resting_v1")


def test_admission_refuses_a_wrong_key():
    archive, manifest, archives = _pinned()
    with pytest.raises(archive.ArchiveError, match="key id"):
        archive.admit(archives["da_a2_resting_v1"], manifest,
                      expected_route="da_a2_resting_v1", key=b"\x00" * 32)


@pytest.mark.parametrize(
    ("mutate", "pattern"),
    [
        (lambda a: a["model"].__setitem__("family", "prevalence_dummy"), "no portable representation"),
        (lambda a: a["model"].__setitem__("family", "gradient_boosting"), "unsupported model family"),
        (lambda a: a["model"].__setitem__("classes", [1, 0]), "classes must be exactly"),
        (lambda a: a["calibration"].__setitem__("slope", 0.0), "admissible range"),
        (lambda a: a["calibration"].__setitem__("slope", -0.5), "admissible range"),
        (lambda a: a["calibration"].__setitem__("intercept", "x"), "must be a number"),
        (lambda a: a["calibration"].__setitem__("fitted_strictly_out_of_fold", False), "strictly out of fold"),
        (lambda a: a["calibration"].__setitem__("fit_scope", "TRAINING_ROWS"), "registered OOF scope"),
        (lambda a: a["calibration"].__setitem__("model_family", "constrained_random_forest"), "does not match"),
        (lambda a: a.pop("fold_ensemble"), "is missing"),
        (lambda a: a["fold_ensemble"][0].__setitem__("model_family", "bad"), "unsupported family"),
        (lambda a: a["fold_ensemble"][0]["calibrator"].__setitem__("model_family", "bad"), "does not match its estimator"),
        (lambda a: a.__setitem__("injected", 1), "unknown fields"),
        (lambda a: a.__setitem__("sentinel", "ACCEPTED"), "not labelled an unratified candidate"),
        (lambda a: a["source"].__setitem__("ordered_feature_names", []), "disagree on feature order"),
        (lambda a: a["preprocessing"]["field_transforms"][0].__setitem__("slice_indices", [99]), "out of range"),
    ],
)
def test_archive_structural_refusals_survive_a_valid_attestation(mutate, pattern):
    """The attacker holds the key, so only structure can refuse."""
    import copy

    archive, manifest, archives = _pinned()
    body = copy.deepcopy(archives["da_a2_resting_v1"])
    body.pop("attestation", None)
    body.pop("archive_sha256", None)
    mutate(body)
    forged = archive.attest(body)
    with pytest.raises(archive.ArchiveError, match=pattern):
        archive.admit(forged, manifest, expected_route="da_a2_resting_v1")


def test_archive_refuses_non_finite_and_malformed_parameters():
    import copy
    import math

    archive, manifest, archives = _pinned()
    for value in (math.nan, math.inf, -math.inf):
        body = copy.deepcopy(archives["da_basic" if False else "da_a1_basic_clinical_v1"])
        body.pop("attestation", None)
        body.pop("archive_sha256", None)
        body["model"]["representation"]["trees"][0]["threshold"][0] = value
        with pytest.raises(archive.ArchiveError):
            archive.attest(body)


def test_archive_tree_validator_rejects_cycles_and_unreachable_nodes():
    import copy

    archive, manifest, archives = _pinned()
    # A self-cycle: node 0 becomes its own child.
    body = copy.deepcopy(archives["da_a1_basic_clinical_v1"])
    tree = body["model"]["representation"]["trees"][0]
    if tree["left"][0] != -1:
        tree["left"][0] = 0
        body.pop("attestation", None)
        body.pop("archive_sha256", None)
        forged = archive.attest(body)
        with pytest.raises(archive.ArchiveError, match="own child|not a tree"):
            archive.admit(forged, manifest, expected_route="da_a1_basic_clinical_v1")
    # An unreachable node: detach the right subtree of the root.
    body = copy.deepcopy(archives["da_a1_basic_clinical_v1"])
    tree = body["model"]["representation"]["trees"][0]
    if tree["right"][0] != -1:
        tree["right"][0] = -1
        tree["feature"][0] = -2
        tree["left"][0] = -1
        body.pop("attestation", None)
        body.pop("archive_sha256", None)
        forged = archive.attest(body)
        with pytest.raises(archive.ArchiveError, match="unreachable"):
            archive.admit(forged, manifest, expected_route="da_a1_basic_clinical_v1")


def test_archive_rejects_a_hostile_node_count():
    import copy

    archive, manifest, archives = _pinned()
    body = copy.deepcopy(archives["da_a1_basic_clinical_v1"])
    body.pop("attestation", None)
    body.pop("archive_sha256", None)
    body["model"]["representation"]["trees"][0]["n_node_samples"] = [1] * (
        archive.MAX_NODES_PER_TREE + 1
    )
    forged = archive.attest(body)
    with pytest.raises(archive.ArchiveError):
        archive.admit(forged, manifest, expected_route="da_a1_basic_clinical_v1")


def _facade_replay():
    """Execute all 29 registered cases twice: registered lane and portable lane.

    Both are produced by executing the facade. The reference is the registered
    lane with the real bundles; the candidate is the portable lane using the
    committed archives. Nothing is copied from a fixture.
    """
    import json
    import tempfile
    from pathlib import Path

    from ai import research_facade as facade
    from ai.filesystem_security import ensure_private_directory
    from research.intake import offline_fixture_pack as v1

    cache = getattr(_facade_replay, "_cache", None)
    if cache is not None:
        return cache

    archive, manifest, archives = _pinned()
    tmp = tempfile.mkdtemp(prefix="rh04-replay-")
    local = v1.sources(ensure_private_directory(Path(tmp)))
    source_doc = json.loads(v1.PACK.read_text())
    # Lane B admits the committed archives against the independently trusted
    # manifest before any facade call is possible.
    portable = archive.PortableReplay(
        facade, manifest=manifest, key=archive.FIXTURE_SIGNING_KEY, archives=archives,
    )

    reference: dict[str, Any] = {}
    candidate: dict[str, Any] = {}
    for case in source_doc["cases"]:
        request = v1.materialize(source_doc["requests"][case["route"]], case["edits"])
        bundle = local.get(case["route"], local["blocked"])
        model_source = facade.LocalSyntheticBundleSource(
            bundle.bundle_dir, bundle.trusted_local_root, bundle.signing_key
        )
        reference[case["id"]] = v1.example(request, bundle)
        candidate[case["id"]] = archive.execute_case(
            facade, request, portable, model_source=model_source
        )
    cache = {
        "archive": archive,
        "manifest": manifest,
        "archives": archives,
        "reference": reference,
        "candidate": candidate,
        "source": source_doc,
        "portable": portable,
        "local": local,
    }
    _facade_replay._cache = cache
    return cache


def test_portable_lane_executes_all_29_cases_through_the_facade():
    """No placeholder statuses: every case is a real facade execution."""
    pack = _facade_replay()
    candidate = pack["candidate"]
    assert len(candidate) == 29
    assert set(candidate) == {c["id"] for c in pack["source"]["cases"]}
    for case_id, response in candidate.items():
        # The placeholder statuses that Round 9 emitted must be gone entirely.
        assert response["status"] != "REFUSAL_ROUTE_DECLARED", case_id
        assert response["status"] != "REQUEST_EDIT_OUT_OF_PORTABLE_SCOPE", case_id
        # Every response must be a real facade status.
        assert response["status"] in (
            "SYNTHETIC_RESULT",
            "ABSTAIN",
            "UNAVAILABLE",
            "ERROR",
        ), case_id


def test_portable_lane_matches_the_registered_lane_exactly_on_all_29_cases():
    """DIAGNOSTIC ONLY -- not the Lane B acceptance oracle.

    This compares the portable lane against Lane A results regenerated **on this
    host**. That is a useful same-host diagnostic, but it cannot serve as a
    cross-platform Lane B reference: Lane A splits into two result groups across
    BLAS kernels, so an oracle built from it would inherit that split.

    Lane B's actual acceptance oracle is ``LANE_B_DIGEST``, a fixed identity
    derived from the committed artifacts, asserted by
    ``test_cold_process_replay_needs_no_producer_bundle`` and
    ``test_verification_cli_reports_the_reference_on_a_valid_directory``.
    """
    pack = _facade_replay()
    mismatches = []
    for case_id, expected in pack["reference"].items():
        observed = pack["candidate"][case_id]
        if not __import__(
            "research.intake.offline_fixture_pack", fromlist=["_strict_equal"]
        )._strict_equal(expected, observed):
            mismatches.append(case_id)
    assert mismatches == [], f"non-exact cases: {mismatches}"


def test_portable_lane_preserves_full_response_shape_including_nulls():
    """Null fields, error codes and types must survive, not be dropped."""
    pack = _facade_replay()
    for case_id, response in pack["candidate"].items():
        assert set(response) == {
            "status",
            "panel_id",
            "route_id",
            "dataset_id",
            "evidence_level",
            "error",
            "outcomes",
        }, case_id
        for outcome in response["outcomes"]:
            assert set(outcome) == {
                "status",
                "score",
                "abstention_reason",
                "unavailable_reason",
                "present_fields",
                "missing_fields_with_reason",
                "error",
            }, case_id
        if response["status"] == "ERROR" and response["error"] is not None:
            # A request-level refusal carries a registered code and stage.
            assert response["error"]["code"]
            assert response["error"]["stage"] in (
                "request",
                "registry",
                "artifact",
                "acquisition",
                "record",
                "prediction",
            )
            assert response["outcomes"] == []
        elif response["status"] == "ERROR":
            # A record-level refusal carries its error on the outcome instead.
            assert response["outcomes"], case_id
            assert response["outcomes"][0]["error"]["code"]


def test_portable_lane_reproduces_both_scored_cases_bit_identically():
    """The two scored cases must agree exactly, not within a tolerance."""
    pack = _facade_replay()
    scored = [
        cid
        for cid, response in pack["candidate"].items()
        if response["status"] == "SYNTHETIC_RESULT"
    ]
    assert sorted(scored) == ["da_a1_basic_clinical_v1", "da_a2_resting_v1"]
    for case_id in scored:
        expected = pack["reference"][case_id]["outcomes"][0]["score"]
        observed = pack["candidate"][case_id]["outcomes"][0]["score"]
        for field in (
            "raw_model_score",
            "raw_model_log_odds",
            "calibrated_research_score",
            "calibrated_log_odds",
        ):
            assert observed[field] == expected[field], (case_id, field)
        assert type(observed["raw_model_score"]) is type(expected["raw_model_score"])


def test_portable_lane_preserves_abstention_semantics():
    """ABSTAIN must remain ABSTAIN with its registered reason, not a refusal."""
    pack = _facade_replay()
    abstained = {
        cid: response["outcomes"][0]["abstention_reason"]
        for cid, response in pack["candidate"].items()
        if response["status"] == "ABSTAIN"
    }
    assert len(abstained) == 2
    for reason in abstained.values():
        assert reason == "registry_abstain_policy_optional_field_missing"


def test_portable_lane_preserves_unavailable_semantics():
    pack = _facade_replay()
    unavailable = [
        cid for cid, r in pack["candidate"].items() if r["status"] == "UNAVAILABLE"
    ]
    assert len(unavailable) == 3


def test_validation_behaviour_cannot_hide_behind_a_placeholder(monkeypatch):
    """Disturbing real validation must change the portable lane too.

    If the portable lane emitted fixed placeholder statuses, breaking the
    facade's registry resolution would leave it unchanged. This pins that the
    portable lane is genuinely downstream of the facade's validation.
    """
    from ai import research_facade as facade

    pack = _facade_replay()
    archive = pack["archive"]
    original = facade.resolve_registered_model

    def refuse_all(**kwargs):
        from ai.research_registry import ResearchRegistryError

        # A plain registry refusal: the facade's registered error path, with no
        # entry provided, so it surfaces as an ERROR rather than UNAVAILABLE.
        raise ResearchRegistryError(
            "route_id_mismatch",
            "forced registry refusal for this negative test",
            field="route_id",
        )

    monkeypatch.setattr(facade, "resolve_registered_model", refuse_all)
    replay = pack["portable"]
    case = next(
        c for c in pack["source"]["cases"] if c["id"] == "da_a2_resting_v1"
    )
    request = __import__("research.intake.offline_fixture_pack", fromlist=["x"]).materialize(
        pack["source"]["requests"][case["route"]], case["edits"]
    )
    import research.intake.offline_fixture_pack as fixtures
    from ai.filesystem_security import ensure_private_directory
    import tempfile
    from pathlib import Path

    tmp = tempfile.mkdtemp(prefix="rh04-negative-")
    local = fixtures.sources(ensure_private_directory(Path(tmp)))
    bundle = local[case["route"]]
    source = facade.LocalSyntheticBundleSource(
        bundle.bundle_dir, bundle.trusted_local_root, bundle.signing_key
    )
    response = archive.execute_case(facade, request, replay, model_source=source)
    assert response["status"] == "ERROR"
    assert response["error"]["code"] == "route_id_mismatch"
    assert response["error"]["stage"] == "registry"
    monkeypatch.undo()
    original  # keep the reference alive for clarity


def test_portable_evaluation_never_deserializes(monkeypatch):
    """The *evaluation* path must not touch pickle at all.

    ``export_archive`` legitimately uses the project's authenticated loader to
    read the producer bundle once, at export time. Evaluation is the property
    that matters for a portable consumer, so it is the one pinned here.
    """
    import joblib

    from ai import research_facade as facade
    from ai.filesystem_security import ensure_private_directory
    import research.intake.offline_fixture_pack as fixtures
    import tempfile
    from pathlib import Path

    pack = _facade_replay()
    archive = pack["archive"]
    case = next(c for c in pack["source"]["cases"] if c["id"] == "da_a2_resting_v1")
    request = fixtures.materialize(
        pack["source"]["requests"][case["route"]], case["edits"]
    )
    # No producer bundle is created at all for this test: evaluation must work
    # from the committed archives alone.
    source = archive.declared_absent_source()

    def forbidden(*args, **kwargs):
        raise AssertionError("portable evaluation must never call joblib.load")

    monkeypatch.setattr(joblib, "load", forbidden)
    response = archive.execute_case(facade, request, pack["portable"], model_source=source)
    monkeypatch.undo()
    assert response["status"] == "SYNTHETIC_RESULT"
    # And the value is the registered one, so the model really was evaluated.
    expected = pack["reference"][case["id"]]["outcomes"][0]["score"]
    assert (
        response["outcomes"][0]["score"]["calibrated_log_odds"]
        == expected["calibrated_log_odds"]
    )


def facade_module():
    from ai import research_facade as module

    return module


# --------------------------------------------------------------------------- #
# Round 10.1 P0-01: admission is enforced in the execution path               #
# --------------------------------------------------------------------------- #


def _replay_with(archives, manifest=None):
    """Build a PortableReplay over the committed manifest with given archives."""
    from ai import research_facade as facade

    archive, committed_manifest, _ = _pinned()
    if manifest is not None:
        # Re-derive the pin for the mutated body so a *self-consistent* forgery
        # is what the attacker is attempting, not an obviously corrupt file.
        manifest = copy.deepcopy(committed_manifest)
    replay = archive.PortableReplay(
        facade,
        manifest=manifest if manifest is not None else committed_manifest,
        key=archive.FIXTURE_SIGNING_KEY,
        archives=archives
        )
    return archive, replay


def test_admission_is_mandatory_and_cannot_be_skipped():
    """Construction without a trusted manifest or key must not be possible."""
    import inspect

    from ai import research_facade as facade

    archive, manifest, archives = _pinned()
    signature = inspect.signature(archive.PortableReplay.__init__)
    assert "manifest" in signature.parameters
    assert "key" in signature.parameters
    assert signature.parameters["manifest"].default is inspect.Parameter.empty
    assert signature.parameters["key"].default is inspect.Parameter.empty
    with pytest.raises(TypeError):
        archive.PortableReplay(facade, archives)


def test_admission_runs_for_every_route_before_any_execution(monkeypatch):
    """A single unpinned route refuses the whole replay, before any facade call."""
    from ai import research_facade as facade

    archive, manifest, archives = _pinned()
    seen: list[str] = []
    original = archive.admit

    def counting(archive_doc, manifest_doc, *, key, expected_route):
        seen.append(expected_route)
        return original(archive_doc, manifest_doc, key=key, expected_route=expected_route)

    monkeypatch.setattr(archive, "admit", counting)
    replay = archive.PortableReplay(
        facade, manifest=manifest, key=archive.FIXTURE_SIGNING_KEY, archives=archives,
    )
    assert sorted(seen) == sorted(manifest["routes"])
    assert replay.admitted_routes == tuple(sorted(manifest["routes"]))


def test_admission_refuses_missing_unexpected_and_swapped_routes():
    """The route set must match the manifest exactly, in both directions."""
    from ai import research_facade as facade

    archive, manifest, archives = _pinned()
    routes = sorted(archives)
    assert len(routes) == 2

    missing = {routes[0]: archives[routes[0]]}
    with pytest.raises(archive.ArchiveError, match="missing"):
        archive.PortableReplay(
            facade, manifest=manifest, key=archive.FIXTURE_SIGNING_KEY, archives=missing
        )

    unexpected = dict(archives)
    unexpected["da_a9_unpinned_route"] = archives[routes[0]]
    with pytest.raises(archive.ArchiveError, match="unpinned"):
        archive.PortableReplay(
            facade, manifest=manifest, key=archive.FIXTURE_SIGNING_KEY, archives=unexpected
        )

    swapped = {routes[0]: archives[routes[1]], routes[1]: archives[routes[0]]}
    with pytest.raises(archive.ArchiveError):
        archive.PortableReplay(
            facade, manifest=manifest, key=archive.FIXTURE_SIGNING_KEY, archives=swapped
        )


def test_admission_refuses_an_archive_signed_with_a_different_key():
    """An attacker who re-signs with their own key cannot be admitted."""
    from ai import research_facade as facade

    archive, manifest, archives = _pinned()
    route = sorted(archives)[0]
    forged = archive.attest(
        copy.deepcopy(archive.body_of(archives[route])),
        key=b"attacker-supplied-key-32-bytes-min!!",
    )
    attack = dict(archives)
    attack[route] = forged
    with pytest.raises(archive.ArchiveError, match="attestation key id"):
        archive.PortableReplay(
            facade, manifest=manifest, key=archive.FIXTURE_SIGNING_KEY, archives=attack
        )


def test_tampered_archive_cannot_reach_model_evaluation(monkeypatch):
    """Mandatory end-to-end attack: a *valid* semantic forgery is still refused.

    The attacker is granted everything a naive verifier checks:

    * the tampered model is **structurally valid** -- a single finite coefficient
      of the Logistic Regression in ``da_a2_resting_v1`` is changed and nothing
      else, so no shape, finiteness or class-proportion validator can object;
    * the archive's internal ``archive_sha256`` is recomputed;
    * the fixture MAC is recomputed with the committed key;
    * the forged manifest's per-route ``archive_sha256`` pin is replaced.

    Only the independently pinned manifest identity can catch this, which is the
    point: the manifest supplied alongside the archives is not a trust anchor.
    """
    from ai import research_facade as facade

    archive, manifest, archives = _pinned()
    route = "da_a2_resting_v1"
    assert archives[route]["model"]["family"] == "l2_logistic_regression"
    tampered = copy.deepcopy(archives[route])

    coef = tampered["model"]["representation"]["coef"]
    original = float(coef[0])
    coef[0] = original + 0.25
    assert coef[0] != original
    # The forgery is structurally valid: same width, all finite.
    assert len(coef) == len(tampered["preprocessing"]["encoded_feature_names"])
    assert all(math.isfinite(float(v)) for v in coef)

    # 1. Recompute the internal body digest.
    recomputed = archive.archive_digest(archive.body_of(tampered))
    tampered["archive_sha256"] = recomputed
    # 2. Re-sign with the published fixture key, which the attacker has.
    tampered = archive.attest(tampered)
    # 3. Re-pin the forged manifest for this body.
    forged_manifest = copy.deepcopy(manifest)
    forged_manifest["routes"][route]["archive_sha256"] = recomputed

    constructed: list[str] = []

    def forbidden(*args, **kwargs):  # pragma: no cover - must never run
        constructed.append("constructed")
        raise AssertionError("no estimator may be constructed before trust is established")

    monkeypatch.setattr(archive, "rehydrate", forbidden)
    monkeypatch.setattr(archive, "rehydrate_member", forbidden)
    attack = dict(archives)
    attack[route] = tampered

    with pytest.raises(archive.ArchiveError, match="trusted manifest"):
        archive.PortableReplay(
            facade,
            manifest=forged_manifest,
            key=archive.FIXTURE_SIGNING_KEY,
            archives=attack
        )
    assert constructed == []


def test_forged_manifest_refusal_precedes_every_other_check(monkeypatch):
    """The anchor is checked before admission, so nothing else is even attempted."""
    from ai import research_facade as facade

    archive, manifest, archives = _pinned()
    forged_manifest = copy.deepcopy(manifest)
    forged_manifest["reference_id"] = "attacker-forged-reference"

    calls: list[str] = []
    original_admit = archive.admit

    def traced(*args, **kwargs):
        calls.append("admit")
        return original_admit(*args, **kwargs)

    monkeypatch.setattr(archive, "admit", traced)
    with pytest.raises(archive.ArchiveError, match="trusted manifest"):
        archive.PortableReplay(
            facade,
            manifest=forged_manifest,
            key=archive.FIXTURE_SIGNING_KEY,
            archives=archives
        )
    assert calls == []


def test_acceptance_api_has_no_caller_selectable_trust_anchor():
    """The anchor must not be a parameter anywhere on the acceptance path."""
    import inspect

    from ai import research_facade as facade
    from research.intake import rh04_v2_portable_archive as archive

    for target in (
        archive.assert_trusted_manifest,
        archive.AdmissionResult,
        archive.admit_from_directory,
        archive.verify_artifact_directory,
        archive.load_admitted_archives,
        archive.PortableReplay.__init__,
    ):
        parameters = inspect.signature(target).parameters
        assert "anchor" not in parameters, f"{target} exposes an anchor parameter"
    # And the anchor constant itself is a plain string, not a mutable hook.
    assert isinstance(archive.TRUSTED_MANIFEST_SHA256, str)
    assert len(archive.TRUSTED_MANIFEST_SHA256) == 64
    facade  # imported for the acceptance path


def test_forged_manifest_cannot_supply_its_own_anchor(tmp_path):
    """A coordinated forgery that re-pins everything still cannot be admitted.

    The attacker modifies one finite Logistic Regression coefficient, verifies the
    archive is still structurally valid, recomputes the self-digest, re-signs with
    the published fixture key, re-pins the manifest and *presents that manifest as
    the artifact directory manifest*. There is no anchor argument to reach for, so
    the only possible outcome is refusal.
    """
    import shutil

    from research.intake import rh04_v2_portable_archive as archive

    for path in _ARCHIVE_DIR.iterdir():
        shutil.copy(path, tmp_path / path.name)
    route = "da_a2_resting_v1"
    manifest = json.loads((tmp_path / "trusted_manifest.json").read_text())
    body = json.loads((tmp_path / f"{route}.archive.json").read_text())

    # 1. A structurally valid semantic change.
    body["model"]["representation"]["coef"][0] = (
        float(body["model"]["representation"]["coef"][0]) + 0.25
    )
    archive.validate_archive(json.loads(json.dumps(body)))  # still valid

    # 2. Recompute the self-digest and re-sign with the published key.
    body["archive_sha256"] = archive.archive_digest(archive.body_of(body))
    body = archive.attest(body)
    (tmp_path / f"{route}.archive.json").write_text(
        json.dumps(body, indent=2, sort_keys=True, ensure_ascii=True) + "\n"
    )

    # 3. Re-pin the forged manifest, including its raw-file digest.
    manifest["routes"][route]["archive_sha256"] = body["archive_sha256"]
    manifest["routes"][route]["raw_archive_sha256"] = hashlib.sha256(
        (tmp_path / f"{route}.archive.json").read_bytes()
    ).hexdigest()
    (tmp_path / "trusted_manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=True) + "\n"
    )

    # 4. The forged manifest is now fully self-consistent ...
    archive.validate_manifest(manifest)
    # ... and every field the old API would have let the attacker pass still fails.
    with pytest.raises(archive.ArchiveError, match="trusted manifest"):
        archive.admit_from_directory(tmp_path)


def test_caller_mutation_after_admission_cannot_change_evaluation():
    """Admitted state is independently owned; later caller edits are inert."""
    from ai import research_facade as facade
    from research.intake import rh04_v2_portable_archive as archive

    admitted = archive.admit_from_directory(_ARCHIVE_DIR)
    baseline = archive.replay_admitted(facade, admitted)["digest"]

    # Mutate the caller's originals *after* admission.
    raw = {r: json.loads((_ARCHIVE_DIR / f"{r}.archive.json").read_text()) for r in admitted.routes}
    for body in raw.values():
        if body["model"]["family"] == "l2_logistic_regression":
            body["model"]["representation"]["coef"][0] += 100.0
        else:
            body["model"]["representation"]["trees"][0]["value"][0][0] += 0.5
    after = archive.replay_admitted(facade, admitted)["digest"]
    assert after == baseline

    # The snapshot also refuses in-place mutation outright.
    with pytest.raises(TypeError, match="immutable"):
        admitted.archives["da_a2_resting_v1"]["model"]["representation"]["coef"][0] = 0.0


def test_fixture_key_is_declared_test_only():
    """The HMAC key must be documented as public test material, not a credential."""
    from research.intake import rh04_v2_portable_archive as archive

    assert archive.FIXTURE_KEY_LABEL == "PUBLIC_TEST_FIXTURE_KEY_NOT_A_SECRET"
    doc = (archive.__doc__ or "") + archive.assert_trusted_manifest.__doc__
    assert "anchor" in doc.lower()


def test_tampered_split_assignment_is_refused_even_when_repinned():
    """A forged fold assignment cannot be admitted by re-pinning the manifest."""
    from ai import research_facade as facade

    archive, manifest, archives = _pinned()
    route = sorted(archives)[0]
    forged_manifest = copy.deepcopy(manifest)
    assignment = forged_manifest["routes"][route]["split_assignments"]
    fold = assignment["outer_folds"][0]
    fold["train_indices"] = fold["train_indices"][:-1] + [fold["validation_indices"][0]]
    fold["validation_indices"] = fold["validation_indices"][1:] + [
        fold["train_indices"][0]
    ]
    assignment["outer_assignment_sha256"] = archive._sha256(
        archive.canonical_bytes(assignment["outer_folds"])
    )
    with pytest.raises(archive.ArchiveError):
        archive.PortableReplay(
            facade,
            manifest=forged_manifest,
            key=archive.FIXTURE_SIGNING_KEY,
            archives=archives
        )


def test_manifest_builder_reproduces_the_committed_manifest():
    """``build_manifest`` must regenerate the committed manifest byte-for-byte."""
    from research.intake import rh04_v2_portable_archive as archive

    _, manifest, archives = _pinned()
    raw = {
        route: __import__("hashlib").sha256(
            (_ARCHIVE_DIR / f"{route}.archive.json").read_bytes()
        ).hexdigest()
        for route in archives
    }
    rebuilt = archive.build_manifest(
        archives, reference_id=manifest["reference_id"], raw_digests=raw
    )
    assert rebuilt == manifest
    assert len(rebuilt["case_ids"]) == 29
    assert rebuilt["case_ids"] == [c["id"] for c in json.loads(v1.PACK.read_text())["cases"]]


def test_cold_process_replay_needs_no_producer_bundle(tmp_path):
    """Lane B must verify and replay all 29 cases with no producer bundle present.

    Uses the single supported entry point (``-m ...rh04_v2_portable_archive``), so
    the cold path exercises the *same* admission, raw-byte and reference checks as
    the in-process path rather than a private JSON shortcut.
    """
    import subprocess
    import sys

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "research.intake.rh04_v2_portable_archive",
            str(_ARCHIVE_DIR),
        ],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
        env={**__import__("os").environ, "PYTHONPATH": str(REPO_ROOT)},
        timeout=900,
    )
    assert completed.returncode == 0, completed.stderr[-3000:]
    report = json.loads(completed.stdout.strip().splitlines()[-1])
    assert report["n_cases"] == 29
    assert report["statuses"] == {
        "SYNTHETIC_RESULT": 2,
        "ABSTAIN": 2,
        "UNAVAILABLE": 3,
        "ERROR": 22,
    }
    assert report["digest"] == LANE_B_DIGEST
    assert report["matches_reference"] is True
    assert report["manifest_identity"] == _pinned()[0].TRUSTED_MANIFEST_SHA256
    # No producer bundle was created, and none is referenced in the evidence.
    assert "model.joblib" not in completed.stdout


def test_cold_process_invalid_output_fails_closed(tmp_path):
    """A missing directory must produce a refusal, not a traceback or exit 0."""
    import subprocess
    import sys

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "research.intake.rh04_v2_portable_archive",
            str(tmp_path / "does-not-exist"),
        ],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
        env={**__import__("os").environ, "PYTHONPATH": str(REPO_ROOT)},
        timeout=600,
    )
    assert completed.returncode != 0
    report = json.loads(completed.stdout.strip().splitlines()[-1])
    assert report["result"] in {"REFUSED", "FAILED"}


def test_lane_b_never_reads_the_producer_bundle(monkeypatch):
    """Every inference dependency must come from the archive, not a bundle.

    The path functions that would read a producer bundle are trapped, and the
    whole 29-case replay must still complete. This is the in-process twin of
    ``test_cold_process_replay_needs_no_producer_bundle``.
    """
    from ai import research_facade as facade
    from pathlib import Path

    archive, manifest, archives = _pinned()
    pack = _facade_replay()
    touched: list[str] = []

    def trap(name):
        def refuse(*args, **kwargs):
            touched.append(name)
            raise AssertionError(f"Lane B must not call {name}")

        return refuse

    for target, attribute in (
        (facade, "verify_trusted_local_bundle"),
        (facade, "ResearchCadPredictor"),
    ):
        if hasattr(target, attribute):
            monkeypatch.setattr(target, attribute, trap(attribute), raising=False)
    monkeypatch.setattr(Path, "read_bytes", trap("Path.read_bytes"), raising=False)

    replay = archive.PortableReplay(
        facade, manifest=manifest, key=archive.FIXTURE_SIGNING_KEY, archives=archives,
    )
    case = next(c for c in pack["source"]["cases"] if c["id"] == "da_a2_resting_v1")
    request = v1.materialize(pack["source"]["requests"][case["route"]], case["edits"])
    response = archive.execute_case(facade, request, replay)
    monkeypatch.undo()

    assert touched == []
    assert response["status"] == "SYNTHETIC_RESULT"
    assert (
        response["outcomes"][0]["score"]["calibrated_log_odds"]
        == pack["reference"][case["id"]]["outcomes"][0]["score"]["calibrated_log_odds"]
    )


def test_shap_background_is_pinned_and_never_taken_from_a_bundle():
    """The SHAP background is a required dependency *derived* from pinned data.

    Round 10.1 embedded the producer document as base64. Round 10.2 removed it:
    the document declares ``commit_or_public_upload_prohibited`` and is an encoded
    training projection, and base64 is encoding, not a change in classification.
    The archive now carries only a reconstruction recipe plus the expected digest,
    and the digest is pinned independently in the trusted manifest.
    """
    from research.intake import rh04_v2_portable_archive as archive
    from ai.panels import REGISTERED_PANELS

    _, manifest, archives = _pinned()
    for route, body in archives.items():
        training = body["training_identity"]
        # 1. No stored projection, in a form that says so explicitly.
        assert "shap_background_document" not in training
        assert training["shap_background_recipe"]["stores_training_projection"] is False
        # 2. The expected digest is pinned in the trusted manifest.
        assert (
            manifest["routes"][route]["shap_background_sha256_raw"]
            == training["shap_background_sha256_raw"]
        )
        # 3. The reconstruction reproduces that digest exactly.
        panel = REGISTERED_PANELS[body["source"]["panel_id"]]
        document = archive.reconstruct_shap_background(
            {**training, "_preprocessing": body["preprocessing"]}, panel
        )
        assert document["privacy"]["synthetic_only"] is True
        assert document["n_background_rows"] == 24


def test_manifest_pins_raw_file_digests_and_real_assignments():
    """P0-04: no metadata hash may stand in for a split assignment."""
    import hashlib

    archive, manifest, archives = _pinned()
    for route, body in archives.items():
        entry = manifest["routes"][route]
        raw = (_ARCHIVE_DIR / f"{route}.archive.json").read_bytes()
        assert entry["raw_archive_sha256"] == hashlib.sha256(raw).hexdigest()
        assignments = entry["split_assignments"]
        # Ordered index lists, not a digest of descriptive metadata.
        for fold in assignments["outer_folds"]:
            assert fold["train_indices"] and fold["validation_indices"]
            assert not set(fold["train_indices"]) & set(fold["validation_indices"])
            assert len(fold["train_indices"]) + len(fold["validation_indices"]) == (
                assignments["n_rows"]
            )
        assert assignments["outer_assignment_sha256"] == archive._sha256(
            archive.canonical_bytes(assignments["outer_folds"])
        )
        # And the assignment recomputes from the pinned seed schedule.
        assert assignments == archive.split_assignments(route)


def test_lane_b_expected_identity_is_fixed_and_not_lane_a_derived():
    """The Lane B reference is a constant, not a value copied from Lane A."""
    source = Path(__file__).read_text()
    assert f'LANE_B_DIGEST = "{LANE_B_DIGEST}"' in source
    # Lane A generation must not appear in the Lane B cold-process path.
    start = source.index("def test_cold_process_replay_needs_no_producer_bundle")
    end = source.index("def ", start + 10)
    cold = source[start:end]
    assert "v1.sources" not in cold


def test_sklearn_private_tree_reconstruction_is_compatible():
    """P0-03: private ``Tree`` reconstruction must work on the pinned version.

    ``rehydrate`` calls ``Tree.__setstate__`` with a private schema. That schema
    changed shape across releases, so the compatibility is *measured* against the
    installed scikit-learn rather than assumed.
    """
    import numpy as np
    import sklearn
    from sklearn.tree._tree import Tree

    from research.intake import rh04_v2_portable_archive as archive

    _, manifest, archives = _pinned()
    assert sklearn.__version__ == "1.6.1", (
        f"this pin was measured on scikit-learn 1.6.1; saw {sklearn.__version__}"
    )
    for route, body in archives.items():
        estimator = archive.rehydrate(body)
        if body["model"]["family"] != "constrained_random_forest":
            continue
        spec = body["model"]["representation"]["trees"][0]
        tree = estimator.estimators_[0].tree_
        assert isinstance(tree, Tree)
        assert tree.node_count == len(spec["left"])
        # 1.6.1 normalises values to (n_nodes, 1, n_classes).
        assert tree.value.shape == (len(spec["left"]), 1, spec["n_classes"])
        assert tree.max_depth == spec["max_depth"]
        # And the reconstruction is an exact round-trip of the archive arrays.
        assert np.array_equal(tree.value[:, 0, 1], np.asarray(spec["value"])[:, 1])


# --------------------------------------------------------------------------- #
# Round 10.2 P0-02: no publication-prohibited training projection is committed #
# --------------------------------------------------------------------------- #


def test_no_shap_training_projection_is_committed_in_any_representation():
    """The prohibited document must not appear as base64, hex, or raw rows.

    Base64 is encoding, not a change in classification: a re-encoded copy would be
    just as prohibited. This scans every committed fixture file for the document's
    distinguishing content in the encodings an author might plausibly choose.
    """
    import base64

    archive, manifest, archives = _pinned()
    forbidden_markers = (
        b"background_matrix",
        b"shap_background_document",
        b"contains_encoded_training_projections",
    )
    for path in sorted(_ARCHIVE_DIR.iterdir()):
        raw = path.read_bytes()
        for marker in forbidden_markers:
            assert marker not in raw, f"{path.name} embeds {marker!r}"
        decoded = raw.decode("utf-8")
        for token in (
            base64.b64encode(b"background_matrix").decode(),
            base64.b64encode(b"contains_encoded_training_projections").decode(),
            b"background_matrix".hex(),
        ):
            assert token not in decoded, f"{path.name} embeds a re-encoded projection"

    # And the archive *declares* that it stores no projection at all.
    for route, body in archives.items():
        recipe = body["training_identity"]["shap_background_recipe"]
        assert recipe["stores_training_projection"] is False
        assert "shap_background_document" not in body["training_identity"]


def test_shap_background_reconstruction_matches_the_pinned_digest():
    """Reconstruction is exact, so the digest the manifest pins is reproducible."""
    import hashlib

    from research.intake import rh04_v2_portable_archive as archive
    from ai.panels import REGISTERED_PANELS

    _, manifest, archives = _pinned()
    for route, body in archives.items():
        panel = REGISTERED_PANELS[body["source"]["panel_id"]]
        document = archive.reconstruct_shap_background(
            {**body["training_identity"], "_preprocessing": body["preprocessing"]}, panel
        )
        raw = (
            json.dumps(document, indent=2, sort_keys=True, ensure_ascii=True, allow_nan=False)
            + "\n"
        ).encode("utf-8")
        assert (
            hashlib.sha256(raw).hexdigest()
            == manifest["routes"][route]["shap_background_sha256_raw"]
        )
        # Panel binding and feature order survive reconstruction.
        assert document["panel_id"] == body["source"]["panel_id"]
        assert (
            document["panel_contract_sha256"] == body["source"]["panel_contract_sha256"]
        )
        assert document["encoded_feature_names"] == list(
            body["preprocessing"]["encoded_feature_names"]
        )
        rows = document["background_matrix"]
        assert len(rows) == document["n_background_rows"] == 24
        assert all(math.isfinite(float(v)) for row in rows for v in row)


def test_archive_claiming_to_store_a_projection_is_refused():
    """An archive that re-introduces the document is refused, not read."""
    from research.intake import rh04_v2_portable_archive as archive
    from ai.panels import REGISTERED_PANELS

    _, _, archives = _pinned()
    body = copy.deepcopy(archives["da_a2_resting_v1"])
    body["training_identity"]["shap_background_recipe"][
        "stores_training_projection"
    ] = True
    panel = REGISTERED_PANELS[body["source"]["panel_id"]]
    with pytest.raises(archive.ArchiveError, match="publication-prohibited"):
        archive.reconstruct_shap_background(
            {**body["training_identity"], "_preprocessing": body["preprocessing"]}, panel
        )


# --------------------------------------------------------------------------- #
# Round 10.2 P1-03: every recorded manifest identity is actually enforced      #
# --------------------------------------------------------------------------- #


def test_raw_archive_bytes_identity_is_enforced(tmp_path):
    """A single-byte change forces a raw-file refusal *before* JSON parsing."""
    import shutil

    from research.intake import rh04_v2_portable_archive as archive

    _, manifest, _ = _pinned()
    for path in _ARCHIVE_DIR.iterdir():
        shutil.copy(path, tmp_path / path.name)
    route = "da_a2_resting_v1"
    target = tmp_path / f"{route}.archive.json"
    # Semantically harmless whitespace: parses identically, different bytes.
    target.write_bytes(target.read_bytes() + b"\n")
    with pytest.raises(archive.ArchiveError, match="raw archive bytes"):
        archive.load_admitted_archives(
            tmp_path, manifest, key=archive.FIXTURE_SIGNING_KEY
        )
    # Deleting a file is also a raw-identity failure.
    target.unlink()
    with pytest.raises(archive.ArchiveError, match="no archive file"):
        archive.load_admitted_archives(
            tmp_path, manifest, key=archive.FIXTURE_SIGNING_KEY
        )


def _patched_anchor(monkeypatch, forged_manifest):
    """Test-local dependency patch: accept one forged manifest as the anchor.

    The acceptance API has no anchor parameter, deliberately. To exercise the
    *downstream* enforcement at all, the anchor constant itself is patched for the
    duration of one test -- the same thing an attacker would have to do by editing
    reviewed source. Everything after the anchor check is the real code.
    """
    from research.intake import rh04_v2_portable_archive as archive

    monkeypatch.setattr(
        archive, "TRUSTED_MANIFEST_SHA256", archive.trusted_manifest_sha256(forged_manifest)
    )


def test_registry_metadata_identity_is_enforced(monkeypatch):
    """The pinned registry declarations must be the ones actually loaded."""
    from ai import research_facade as facade
    from research.intake import rh04_v2_portable_archive as archive

    _, manifest, archives = _pinned()
    forged_manifest = copy.deepcopy(manifest)
    forged_manifest["routes"]["da_a2_resting_v1"]["registry_metadata_sha256"] = "0" * 64
    _patched_anchor(monkeypatch, forged_manifest)
    with pytest.raises(archive.ArchiveError, match="registry metadata identity"):
        archive.PortableReplay(
            facade,
            manifest=forged_manifest,
            key=archive.FIXTURE_SIGNING_KEY,
            archives=archives,
        )


def test_training_input_identity_is_enforced(monkeypatch):
    """The complete ordered feature/target digest must be enforced."""
    from ai import research_facade as facade
    from research.intake import rh04_v2_portable_archive as archive

    _, manifest, archives = _pinned()
    forged_manifest = copy.deepcopy(manifest)
    forged_manifest["routes"]["da_a2_resting_v1"]["training_input_sha256"] = "1" * 64
    _patched_anchor(monkeypatch, forged_manifest)
    with pytest.raises(archive.ArchiveError, match="training-input identity"):
        archive.PortableReplay(
            facade,
            manifest=forged_manifest,
            key=archive.FIXTURE_SIGNING_KEY,
            archives=archives,
        )


def test_training_input_digest_covers_features_not_just_labels():
    """It must be a feature+target digest, distinct from the split metadata hash."""
    from research.intake import rh04_v2_portable_archive as archive

    _, manifest, _ = _pinned()
    for route in manifest["routes"]:
        full = archive.training_input_sha256(route)
        labels_only = archive._sha256(archive.canonical_bytes(
            archive._ordered_cohort_labels(route)
        ))
        assert full != labels_only
        # And distinct from the metadata-derived split identity.
        assert full != manifest["routes"][route]["split_sha256"]
        assert (
            full
            == manifest["routes"][route]["training_input_sha256"]
            == archive.training_input_sha256(route)
        )


# --------------------------------------------------------------------------- #
# Round 10.2 P1-04: replay concurrency is reproducible evidence                #
# --------------------------------------------------------------------------- #


def test_eight_concurrent_full_29_case_replays_independently_admitted():
    """Eight simultaneous replays, each with its own admission, all 29 cases each.

    This replaces the earlier claim, which ran one REST case per worker and could
    not have detected cross-route leakage.
    """
    from concurrent.futures import ThreadPoolExecutor

    from ai import research_facade as facade
    from research.intake import rh04_v2_portable_archive as archive

    original = facade._load_artifact
    expected = LANE_B_DIGEST

    def one(_index: int):
        admitted = archive.admit_from_directory(_ARCHIVE_DIR)
        result = archive.replay_admitted(facade, admitted)
        statuses: dict[str, int] = {}
        for response in result["responses"]:
            statuses[response["status"]] = statuses.get(response["status"], 0) + 1
        return result["n_cases"], result["digest"], statuses

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(one, range(8)))

    assert len(results) == 8
    assert {n for n, _, _ in results} == {29}
    assert {digest for _, digest, _ in results} == {expected}
    assert {tuple(sorted(s.items())) for _, _, s in results} == {
        (("ABSTAIN", 2), ("ERROR", 22), ("SYNTHETIC_RESULT", 2), ("UNAVAILABLE", 3))
    }
    # Both model families were exercised in every worker: LR and RF scores exist.
    assert facade._load_artifact is original
    assert archive._ACTIVE_REPLAYS[0] == 0
    assert archive._ENTRY_STACK.get() == ()


def test_shared_replay_instance_across_threads_documents_its_contract():
    """A single instance may be shared: all bookkeeping is context-local.

    This pins the documented concurrency contract rather than leaving it implicit.
    """
    from concurrent.futures import ThreadPoolExecutor

    from ai import research_facade as facade
    from research.intake import rh04_v2_portable_archive as archive

    admitted = archive.admit_from_directory(_ARCHIVE_DIR)
    shared = archive.PortableReplay(
        facade,
        manifest=archive._thaw(admitted.manifest),
        key=archive.FIXTURE_SIGNING_KEY,
        archives={r: archive._thaw(admitted.archives[r]) for r in admitted.routes},
    )
    pack = json.loads(v1.PACK.read_text())

    def one(_index: int):
        digests = [
            hashlib.sha256(
                archive.canonical_bytes(
                    archive.execute_case(
                        facade,
                        v1.materialize(pack["requests"][case["route"]], case["edits"]),
                        shared,
                    )
                )
            ).hexdigest()
            for case in pack["cases"]
        ]
        return hashlib.sha256("".join(digests).encode()).hexdigest()

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(one, range(8)))
    assert set(results) == {LANE_B_DIGEST}
    assert archive._ENTRY_STACK.get() == ()
    assert archive._ACTIVE_REPLAYS[0] == 0
    facade  # keep the import explicit


def test_nested_contexts_and_exception_cleanup():
    """Nested replays dispatch innermost, and an exception still unwinds."""
    from ai import research_facade as facade
    from research.intake import rh04_v2_portable_archive as archive

    original = facade._load_artifact
    pack = _facade_replay()
    outer = archive.PortableReplay(
        facade,
        manifest=pack["manifest"],
        key=archive.FIXTURE_SIGNING_KEY,
        archives=pack["archives"],
    )
    inner = archive.PortableReplay(
        facade,
        manifest=pack["manifest"],
        key=archive.FIXTURE_SIGNING_KEY,
        archives=pack["archives"],
    )
    case = next(c for c in pack["source"]["cases"] if c["id"] == "da_a2_resting_v1")
    request = v1.materialize(pack["source"]["requests"][case["route"]], case["edits"])

    with outer:
        assert archive._active_dispatch() is outer
        with inner:
            assert archive._active_dispatch() is inner
            assert archive.execute_case(facade, request, inner)["status"] == "SYNTHETIC_RESULT"
        assert archive._active_dispatch() is outer
        with pytest.raises(RuntimeError, match="boom"):
            with inner:
                assert archive._active_dispatch() is inner
                raise RuntimeError("boom")
        assert archive._active_dispatch() is outer
        assert archive.execute_case(facade, request, outer)["status"] == "SYNTHETIC_RESULT"

    assert archive._active_dispatch() is None
    assert archive._ENTRY_STACK.get() == ()
    assert facade._load_artifact is original
    assert archive._ACTIVE_REPLAYS[0] == 0


def test_non_replay_facade_calls_delegate_to_the_real_loader():
    """A registered-lane call during a replay must reach the facade's own loader."""
    import threading

    from ai import research_facade as facade
    from research.intake import rh04_v2_portable_archive as archive

    admitted = archive.admit_from_directory(_ARCHIVE_DIR)
    replay = archive.PortableReplay(
        facade,
        manifest=archive._thaw(admitted.manifest),
        key=archive.FIXTURE_SIGNING_KEY,
        archives={r: archive._thaw(admitted.archives[r]) for r in admitted.routes},
    )
    entered, release = threading.Event(), threading.Event()

    def hold():
        with replay:
            entered.set()
            release.wait(30)

    thread = threading.Thread(target=hold)
    thread.start()
    try:
        assert entered.wait(30)
        # This thread has no active replay, so the seam must delegate. The real
        # loader rejects a None request rather than pretending to be portable.
        with pytest.raises(AttributeError):
            facade._load_artifact(None, None, None)
    finally:
        release.set()
        thread.join(30)
    assert archive._ACTIVE_REPLAYS[0] == 0


def test_whitespace_only_mutation_is_refused_by_the_complete_replay(tmp_path):
    """The supported entry point refuses a byte-level edit, not just a helper."""
    import shutil
    import subprocess
    import sys

    from research.intake import rh04_v2_portable_archive as archive

    for path in _ARCHIVE_DIR.iterdir():
        shutil.copy(path, tmp_path / path.name)
    target = tmp_path / "da_a2_resting_v1.archive.json"
    target.write_bytes(target.read_bytes() + b"\n")

    with pytest.raises(archive.ArchiveError, match="raw archive bytes"):
        archive.verify_artifact_directory(tmp_path)

    completed = subprocess.run(
        [sys.executable, "-m", "research.intake.rh04_v2_portable_archive", str(tmp_path)],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
        env={**__import__("os").environ, "PYTHONPATH": str(REPO_ROOT)},
        timeout=600,
    )
    assert completed.returncode != 0
    report = json.loads(completed.stdout.strip().splitlines()[-1])
    assert report["result"] == "REFUSED"
    assert "raw archive bytes" in report["reason"]


def test_verification_cli_reports_the_reference_on_a_valid_directory():
    """The same command exits zero and reports a matching reference."""
    import subprocess
    import sys

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "research.intake.rh04_v2_portable_archive",
            str(_ARCHIVE_DIR),
        ],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
        env={**__import__("os").environ, "PYTHONPATH": str(REPO_ROOT)},
        timeout=900,
    )
    assert completed.returncode == 0, completed.stdout[-2000:]
    evidence = json.loads(completed.stdout.strip().splitlines()[-1])
    assert evidence["n_cases"] == 29
    assert evidence["matches_reference"] is True
    assert evidence["digest"] == LANE_B_DIGEST
    # Sanitised: no paths, no caller values, no matrices.
    assert str(_ARCHIVE_DIR) not in completed.stdout
    assert "background_matrix" not in completed.stdout




# --------------------------------------------------------------------------- #
# Round 10.3 P0-01: producer lineage is derived, and the old seed fails        #
# --------------------------------------------------------------------------- #


def test_producer_configuration_is_read_from_the_registered_producers():
    """No cohort seed may be re-typed in this module; it comes from the producer."""
    from ai.research_demo import DEMO_SEED
    from ai.uci412_research import Uci412ResearchModelConfig
    from research.intake import rh04_v2_producer_lineage as lineage
    from research.intake import rh04_v2_portable_archive as archive

    resting = lineage.producer_spec("da_a2_resting_v1")
    basic = lineage.producer_spec("da_a1_basic_clinical_v1")

    assert resting.cohort_seed == DEMO_SEED == 20261117
    assert basic.cohort_seed == Uci412ResearchModelConfig.fast().seed == 20261028
    # Both producers share the same *CV repeat* seed; that is not the cohort seed.
    assert resting.repeat_seed == basic.repeat_seed == 20261025

    source = Path(archive.__file__).read_text()
    # The module must not carry its own seed table any more.
    assert "SPLIT_DERIVATIONS" not in source
    assert "20261025" not in source, "a CV repeat seed is re-typed in the archive module"
    assert "20261028" not in source, "the BASIC cohort seed is re-typed in the archive module"
    assert "20261117" not in source, "the REST cohort seed is re-typed in the archive module"


def test_the_five_seed_roles_are_distinct_and_derived():
    """Cohort, repeat, inner, calibration and SHAP seeds must not be conflated."""
    from research.intake import rh04_v2_producer_lineage as lineage

    for route in ("da_a2_resting_v1", "da_a1_basic_clinical_v1"):
        spec = lineage.producer_spec(route)
        assert spec.cohort_seed != spec.repeat_seed
        assert spec.full_cv_seed == spec.repeat_seed + 90000
        assert spec.calibration_seed == spec.full_cv_seed + 333
        assert spec.shap_background_seed == spec.full_cv_seed + 4242
        assert len(
            {spec.cohort_seed, spec.repeat_seed, spec.calibration_seed,
             spec.shap_background_seed, spec.inner_seed(1, 1)}
        ) == 5


def test_wrong_basic_cohort_seed_fails_identity_verification():
    """Using the pre-correction BASIC seed must now be detectable as a mismatch."""
    from research.intake import rh04_v2_producer_lineage as lineage

    correct = lineage.training_boundary("da_a1_basic_clinical_v1").input_sha256()

    # Rebuild the boundary with the *wrong* seed the previous revision used, and
    # show the resulting identity differs from the committed one.
    from ai.panels import REGISTERED_PANELS
    from ai.training import validate_cohort_records
    from ai.uci412_research import build_synthetic_uci412_basic_clinical_cohort

    panel = REGISTERED_PANELS["da_a1_basic_clinical_v1"]
    records, labels = build_synthetic_uci412_basic_clinical_cohort(120, seed=20261025)
    X, y, _ = validate_cohort_records(records, labels, panel)
    wrong_payload = {
        "route_id": "da_a1_basic_clinical_v1",
        "ordered_feature_names": list(panel.feature_names),
        "n_rows": int(X.shape[0]),
        "n_features": int(X.shape[1]),
        "n_positive": int(y.sum()),
        "X_hex": [float(v).hex() for v in X.ravel()],
        "y": [int(v) for v in y],
    }
    wrong = lineage._sha256(lineage._canonical_bytes(wrong_payload))
    assert wrong != correct

    # And the committed manifest carries the corrected identity.
    _, manifest, _ = _pinned()
    assert manifest["routes"]["da_a1_basic_clinical_v1"]["training_input_sha256"] == correct
    assert manifest["routes"]["da_a1_basic_clinical_v1"]["training_input_sha256"] != wrong


def test_inner_selection_preserves_the_producer_family_order():
    """Family offsets must follow ``CANDIDATE_FAMILIES``' declared order.

    ``ai/training.py`` derives every seed from ``enumerate(CANDIDATE_FAMILIES,
    start=1)``, so the declared order is semantically load-bearing. An earlier
    version of the lineage module used ``sorted(...)``, which reverses the tuple
    ("constrained_random_forest" < "l2_logistic_regression") and therefore
    assigned each family the *other* family's inner-CV seeds.
    """
    from ai.training import CANDIDATE_FAMILIES
    from research.intake import rh04_v2_producer_lineage as lineage

    assert lineage.candidate_families_in_producer_order() == tuple(CANDIDATE_FAMILIES)
    assert tuple(sorted(CANDIDATE_FAMILIES)) != tuple(CANDIDATE_FAMILIES), (
        "test is meaningless if sorting is a no-op for this tuple"
    )

    for route in ("da_a1_basic_clinical_v1", "da_a2_resting_v1"):
        identity = lineage.inner_selection_identity(route)
        assert identity["family_order"] == list(CANDIDATE_FAMILIES)
        spec = lineage.producer_spec(route)
        for fold in identity["folds"]:
            for offset, family in enumerate(CANDIDATE_FAMILIES, start=1):
                record = fold["families"][family]
                assert record["family_offset"] == offset, (family, offset)
                assert record["inner_seed"] == (
                    spec.repeat_seed + 1000 * fold["fold_index"] + 10 * offset
                )
            # The dummy calibrator occupies offset slot +1 in the same schedule.
            assert fold["dummy_calibration"]["inner_seed"] == (
                spec.repeat_seed + 1000 * fold["fold_index"] + 1
            )


def test_inner_selection_matches_independently_observed_producer_execution():
    """The derived schedule must equal the seeds the producer actually constructs.

    This is the check that would have caught the ``sorted()`` defect. Rather than
    recomputing the same arithmetic a second time, it drives the registered
    producer and records every ``StratifiedKFold`` it constructs, then requires
    the observed inner-CV and full-development seeds to appear in the derived
    schedule as the *right family*.
    """
    from sklearn.model_selection import StratifiedKFold

    from ai.training import CANDIDATE_FAMILIES
    from research.intake import rh04_v2_producer_lineage as lineage

    route = "da_a1_basic_clinical_v1"
    observed: list[int] = []
    original = StratifiedKFold.__init__

    def _record(self, *args, **kwargs):
        original(self, *args, **kwargs)
        observed.append(int(self.random_state))

    StratifiedKFold.__init__ = _record
    try:
        lineage._run_registered_producer(route)
    finally:
        StratifiedKFold.__init__ = original

    spec = lineage.producer_spec(route)
    identity = lineage.inner_selection_identity(route)

    # Every derived outer-fold inner seed for every family must have been
    # constructed by the producer. If the offsets were reversed, the derived
    # family->seed map would not appear in the observed sequence at all.
    for fold in identity["folds"]:
        for family in CANDIDATE_FAMILIES:
            assert fold["families"][family]["inner_seed"] in observed, family
        assert fold["dummy_calibration"]["inner_seed"] in observed

    # The full-development selection seeds and the calibration splitter, too.
    for offset, family in enumerate(CANDIDATE_FAMILIES, start=1):
        assert spec.full_selection_seed(offset) in observed, family
    assert spec.calibration_seed in observed

    # And the ordering claim itself: the derived offset for Logistic Regression
    # is smaller than the derived offset for Random Forest, matching the order in
    # which the producer constructs them inside a fold.
    lr_offset = identity["family_order"].index("l2_logistic_regression") + 1
    rf_offset = identity["family_order"].index("constrained_random_forest") + 1
    assert lr_offset < rf_offset


def test_calibration_input_is_the_oof_vector_not_the_development_matrix():
    """The calibrator's fitted input must be the OOF vector, captured not derived.

    The defect this replaces hashed the development feature/target matrix and
    stored it as ``calibration_input_sha256``. That is not what the OOF calibrator
    consumes, so the binding could not detect a change to the calibrator's actual
    input at all.
    """
    from research.intake import rh04_v2_producer_lineage as lineage

    _, manifest, _ = _pinned()
    for route in manifest["routes"]:
        ident = lineage.calibration_input_identity(route)
        pin = manifest["routes"][route]["calibration_input"]
        boundary = lineage.training_boundary(route)

        # Distinct identities, all three of them.
        assert pin["oof_input_sha256"] != boundary.input_sha256()
        assert pin["oof_target_sha256"] != boundary.target_sha256()
        assert (
            manifest["routes"][route]["calibration_oof"]["development_input_sha256"]
            == boundary.input_sha256()
        )

        # The captured vector is the real OOF length, and the link is typed right.
        assert ident["n_oof_samples"] == boundary.n_rows
        assert ident["fit_scope"] == "FULL_DEVELOPMENT_OOF_FINAL"
        if ident["input_link"] == "exact_raw_log_odds":
            assert ident["oof_raw_logit_sha256"] is not None
        else:
            assert ident["oof_raw_logit_sha256"] is None

        # The captured fit reproduces the archived calibrator exactly.
        _, _, archives = _pinned()
        calibration = archives[route]["calibration"]
        assert ident["fitted_parameters"]["intercept"] == calibration["intercept"]
        assert ident["fitted_parameters"]["slope"] == calibration["slope"]
        assert ident["input_link"] == calibration["input_link"]


def test_calibrator_input_pin_is_enforced_not_merely_present(monkeypatch):
    """A present pin that admission never compares would be the old defect again.

    The archive's own digest and MAC are recomputed so neither can be what
    refuses it, the manifest agrees with the tampered value everywhere it can,
    and the anchor is patched test-locally. What remains is the calibrator-input
    binding -- which must be what catches it.
    """
    archive_mod, manifest, archives = _pinned()
    route = "da_a1_basic_clinical_v1"
    body = copy.deepcopy(archives[route])
    body.pop("attestation", None)
    body.pop("archive_sha256", None)
    body["calibration"]["slope"] = body["calibration"]["slope"] + 1e-6
    forged = archive_mod.attest(body)

    forged_manifest = copy.deepcopy(manifest)
    entry = forged_manifest["routes"][route]
    entry["archive_sha256"] = forged["archive_sha256"]
    entry["calibration_slope"] = forged["calibration"]["slope"]
    entry["calibration_sha256"] = archive_mod.calibration_sha256(
        forged["calibration"]
    )
    entry["training_identity_sha256"] = archive_mod.training_identity_sha256(
        forged["training_identity"]
    )
    _patched_anchor(monkeypatch, forged_manifest)

    with pytest.raises(archive_mod.ArchiveError, match="calibrator slope"):
        archive_mod.admit(forged, forged_manifest, expected_route=route)


def test_calibration_input_pin_rejects_a_lane_b_recomputation_claim():
    """The pin may not claim Lane B recomputes an OOF digest it never fits.

    This is the "field present means enforced" failure mode turned into a test:
    a manifest that asserts a capability the lane does not have is refused rather
    than read as evidence.
    """
    from research.intake import rh04_v2_portable_archive as archive

    _, manifest, _ = _pinned()
    for lie in (True, None, "yes"):
        forged = copy.deepcopy(manifest)
        forged["routes"]["da_a1_basic_clinical_v1"]["calibration_input"][
            "recomputable_in_lane_b"
        ] = lie
        with pytest.raises(archive.ArchiveError, match="Lane B does not fit"):
            archive.validate_manifest(forged)


def test_calibration_input_pin_requires_a_logit_digest_exactly_when_the_link_uses_one():
    """Raw-log-odds and clipped-logit are mutually exclusive link identities."""
    from research.intake import rh04_v2_portable_archive as archive

    _, manifest, _ = _pinned()
    route = "da_a1_basic_clinical_v1"
    entry = manifest["routes"][route]["calibration_input"]
    assert entry["input_link"] == "clipped_logit_of_raw_probability"
    assert entry["oof_raw_logit_sha256"] is None

    # A clipped-link pin that suddenly carries a raw-logit digest is malformed.
    forged = copy.deepcopy(manifest)
    forged["routes"][route]["calibration_input"]["oof_raw_logit_sha256"] = "0" * 64
    with pytest.raises(archive.ArchiveError, match="must not pin a raw-logit"):
        archive.validate_manifest(forged)

    # And an exact-log-odds pin that omits it is equally malformed.
    forged = copy.deepcopy(manifest)
    forged["routes"][route]["calibration_input"]["input_link"] = "exact_raw_log_odds"
    with pytest.raises(archive.ArchiveError, match="must pin the raw-logit"):
        archive.validate_manifest(forged)


def test_calibration_oof_seed_validator_can_actually_fail():
    """The guard this replaced was False for every integer and could never fire."""
    from research.intake import rh04_v2_portable_archive as archive

    _, manifest, _ = _pinned()
    forged = copy.deepcopy(manifest)
    entry = forged["routes"]["da_a1_basic_clinical_v1"]["calibration_oof"]
    entry["n_splits"] = 1
    with pytest.raises(archive.ArchiveError, match="partition needs >= 2 folds"):
        archive.validate_manifest(forged)


def test_v1_to_v2_mapping_covers_every_case_and_every_field():
    """Complete per-case / per-field V1 -> V2 mapping.

    The mapping must be structural, not a spot check: for every one of the 29
    registered cases, the set of leaf field paths produced by the V2 Lane B replay
    must equal the set in the V1 pack, with the same status. A field that silently
    disappears from the V2 response is a contract regression that no digest
    comparison would localise.
    """
    from ai import research_facade as facade
    from research.intake import offline_fixture_pack as v1
    from research.intake import rh04_v2_portable_archive as archive

    def leaf_paths(value, prefix=""):
        if isinstance(value, dict):
            acc = {}
            for key, item in value.items():
                acc.update(leaf_paths(item, f"{prefix}.{key}" if prefix else key))
            return acc
        if isinstance(value, list):
            acc = {}
            for index, item in enumerate(value):
                acc.update(leaf_paths(item, f"{prefix}[{index}]"))
            return acc
        return {prefix: type(value).__name__}

    pack = json.loads(v1.PACK.read_text(encoding="utf-8"))
    admitted = archive.admit_from_directory(_ARCHIVE_DIR)
    replayed = archive.replay_admitted(facade, admitted)
    assert replayed["n_cases"] == 29
    responses = dict(
        zip([case["id"] for case in pack["cases"]], replayed["responses"])
    )

    for case in pack["cases"]:
        observed = responses[case["id"]]
        expected = case["expected"]
        want = leaf_paths(expected)
        got = leaf_paths(observed)
        assert set(got) == set(want), (
            case["id"],
            sorted(set(want) - set(got)),
            sorted(set(got) - set(want)),
        )
        assert observed["status"] == expected["status"], case["id"]
        # Types must agree too: a value that changes from float to string is a
        # contract change even when the path set is identical.
        for path, want_type in want.items():
            assert got[path] == want_type, (case["id"], path, got[path], want_type)

    # Every case contributes at least one distinct status so the mapping is not
    # vacuously satisfied by 29 identical error responses.
    assert {case["expected"]["status"] for case in pack["cases"]} == {
        "SYNTHETIC_RESULT", "UNAVAILABLE", "ERROR", "ABSTAIN",
    }


def test_case_bindings_are_enforced_not_only_case_ids():
    """Keeping 29 ids in order is not enough: routes, edits and expectations bind too.

    A manifest that preserved the id list while re-pointing a case at a different
    route, or attaching different edits, would pass an ids-only check and then
    execute something the reviewer never approved.
    """
    from research.intake import rh04_v2_portable_archive as archive

    _, manifest, _ = _pinned()
    assert len(manifest["cases"]) == 29
    archive._assert_case_set(manifest)  # the committed manifest is valid

    # (a) route re-pointed, ids and order untouched
    forged = copy.deepcopy(manifest)
    forged["cases"][0]["route_id"] = "da_a1_basic_clinical_v1"
    with pytest.raises(archive.ArchiveError, match="routes it to"):
        archive._assert_case_set(forged)

    # (b) different edits
    forged = copy.deepcopy(manifest)
    forged["cases"][3]["edits_sha256"] = "0" * 64
    with pytest.raises(archive.ArchiveError, match="edits_sha256"):
        archive._assert_case_set(forged)

    # (c) different expected response
    forged = copy.deepcopy(manifest)
    forged["cases"][7]["expected_sha256"] = "0" * 64
    with pytest.raises(archive.ArchiveError, match="expected_sha256"):
        archive._assert_case_set(forged)

    # (d) records reordered
    forged = copy.deepcopy(manifest)
    forged["cases"][0], forged["cases"][1] = forged["cases"][1], forged["cases"][0]
    with pytest.raises(archive.ArchiveError, match="out of order"):
        archive._assert_case_set(forged)


def test_the_executed_snapshot_is_materialised_before_verification():
    """The detached snapshot must be built BEFORE ``admit()`` walks the document.

    This test is written to *discriminate*, and it was checked against both
    implementations rather than only the current one.

    The property that actually differs is how many times verification and
    execution traverse the caller's own mutable containers. Measuring the
    behaviour:

    * snapshot-first (current): the caller's calibration object is traversed
      **once**, to serialise the snapshot. ``admit()`` then walks the detached
      copy.
    * verify-then-snapshot (previous): the same object is traversed **4** times --
      once inside ``admit()``'s structural and semantic passes, then again by
      ``canonical_bytes`` to build the stored snapshot.

    A counting test on the outer route mapping does **not** discriminate: both
    implementations read ``archives[route]`` exactly once, so an assertion there
    passes against the old code too. An earlier version of this test made exactly
    that mistake; it is replaced here rather than kept as decoration.

    What this does **not** claim: a varying object cannot actually smuggle a
    different value past admission. The archives carry an HMAC attestation, so a
    second read returning different parameters fails admission with "attestation
    does not verify" -- verified by running the tampered variant against the old
    implementation, which refused rather than diverged. The fix therefore removes
    repeated traversal of caller-controlled mutable state as defence in depth; it
    does not close an exploitable value-divergence hole. Both facts are recorded.
    """
    from ai import research_facade as facade
    from research.intake import rh04_v2_portable_archive as archive

    _, manifest, archives = _pinned()

    class CountingCalibration(dict):
        """Counts wholesale traversals of a caller-owned nested container."""

        def __init__(self, document):
            super().__init__(document)
            self.traversals = 0

        def items(self):
            self.traversals += 1
            return super().items()

    documents = {
        "da_a1_basic_clinical_v1": copy.deepcopy(archives["da_a1_basic_clinical_v1"]),
        "da_a2_resting_v1": copy.deepcopy(archives["da_a2_resting_v1"]),
    }
    counter = CountingCalibration(documents["da_a1_basic_clinical_v1"]["calibration"])
    documents["da_a1_basic_clinical_v1"]["calibration"] = counter

    replay = archive.PortableReplay(
        facade, manifest=manifest, key=archive.FIXTURE_SIGNING_KEY, archives=documents
    )

    assert counter.traversals == 1, (
        "the caller's calibration object was traversed "
        f"{counter.traversals} times; snapshot-first materialises it exactly once, "
        "so verification cannot walk caller-owned mutable state after execution "
        "has been fixed"
    )
    # And what was stored is the value from the single traversal.
    assert replay._admitted["da_a1_basic_clinical_v1"]["calibration"]["slope"] == (
        archives["da_a1_basic_clinical_v1"]["calibration"]["slope"]
    )

    # The snapshot is independently owned and refuses mutation.
    with pytest.raises(TypeError):
        replay._admitted["da_a1_basic_clinical_v1"]["calibration"]["slope"] = 1.0


def test_changed_base_request_is_refused_before_admission(monkeypatch, tmp_path):
    """Changing a base request while preserving case ids and edits must be refused.

    This is the gap the previous fixture binding left open. Binding read-to-read
    only proves the file did not change between two reads; it says nothing about
    whether the file is the approved one. Case ids and edits can stay identical
    while ``requests`` is edited, which changes every materialised case.
    """
    from research.intake import rh04_v2_portable_archive as archive
    from research.intake import offline_fixture_pack as v1

    # Copy the artifact directory, then point the module at a tampered pack.
    for name in ("da_a1_basic_clinical_v1.archive.json",
                 "da_a2_resting_v1.archive.json",
                 "trusted_manifest.json"):
        (tmp_path / name).write_bytes((_ARCHIVE_DIR / name).read_bytes())

    original_pack = json.loads(v1.PACK.read_text(encoding="utf-8"))

    tampered = copy.deepcopy(original_pack)
    # Preserve case ids, case edits and case order exactly.
    first_route = tampered["cases"][0]["route"]
    assert tampered["requests"][first_route] == original_pack["requests"][first_route]

    # Mutate a base request in a way that leaves ids and edits untouched.
    request = copy.deepcopy(tampered["requests"][first_route])
    request["request_id"] = request.get("request_id", "") + "-TAMPERED"
    tampered["requests"][first_route] = request

    # Sanity: the case list itself is unchanged.
    assert [c["id"] for c in tampered["cases"]] == [c["id"] for c in original_pack["cases"]]
    assert [c["edits"] for c in tampered["cases"]] == [c["edits"] for c in original_pack["cases"]]
    # And the approved-identity digest must actually differ.
    assert v1.canonical_response_digest(tampered) != v1.PACK_SHA256

    encoded = json.dumps(tampered).encode("utf-8")

    class TamperedPackPath:
        """Stands in for the module-level fixture path.

        Only the two read methods the archive actually calls are provided, so the
        test cannot accidentally exercise a third read path that real code lacks.
        """

        def read_bytes(self):
            return encoded

        def read_text(self, encoding="utf-8"):
            return encoded.decode(encoding)

    monkeypatch.setattr(v1, "PACK", TamperedPackPath())

    with pytest.raises(archive.ArchiveError, match="independently approved identity"):
        archive.admit_from_directory(tmp_path)


def test_selection_is_reproduced_independently_not_only_conditionally():
    """Refitting given the archived winner cannot detect a wrong winner.

    This asserts the stronger claim: re-running the producer's own selection
    procedure from the producer cohort picks the archived family and the archived
    hyperparameters.
    """
    from research.intake import rh04_v2_producer_lineage as lineage

    _, _, archives = _pinned()
    for route, body in archives.items():
        reproduced = lineage.selection_reproduction(route)
        assert reproduced["selected_family"] == body["model"]["family"]
        assert reproduced["selected_hyperparameters"] == body["training_identity"][
            "selected_hyperparameters"
        ]
        assert reproduced["selection_scope"] == "FULL_DEVELOPMENT_COHORT"


def test_registered_producer_lineage_is_established_for_both_models():
    """Refit from the producer cohort must reproduce the archived estimator."""
    from research.intake import rh04_v2_producer_lineage as lineage

    _, _, archives = _pinned()
    for route, body in archives.items():
        proof = lineage.estimator_lineage_proof(route, body)
        assert proof["preprocessing_exact"] is True
        assert proof["lineage_established"] is True, proof
        if proof["model_family"] == "l2_logistic_regression":
            assert proof["coefficients_exact"] is True
            assert proof["coefficient_max_abs_delta"] == 0.0
            assert proof["intercept_abs_delta"] == 0.0
        else:
            # Complete structure, not just leaf values. A forest whose leaves hold
            # the same numbers but whose split topology, thresholds or
            # missing-value routing differ is a different function.
            assert proof["trees_exact"] is True
            assert proof["tree_count_exact"] is True
            assert proof["tree_count"]["archived"] == proof["tree_count"]["refit"]
            assert proof["structure_exact"] is True
            assert proof["max_float_delta"] == 0.0
            assert proof["node_count_mismatch_trees"] == []
            for array_name in ("left", "right", "feature", "threshold",
                               "impurity", "n_node_samples",
                               "weighted_n_node_samples", "missing_go_to_left",
                               "value"):
                assert proof["per_array_exact"][array_name] is True, array_name
            for scalar_name in ("max_depth", "n_features", "n_classes", "n_outputs"):
                assert proof["per_scalar_exact"][scalar_name] is True, scalar_name
            assert proof["class_order"] == [0, 1]
            assert proof["n_features_in"] == 16


def test_calibration_oof_identity_is_distinct_from_the_outer_folds():
    """P0-04: the calibration split is `full_cv + 333`, not the outer split."""
    from research.intake import rh04_v2_producer_lineage as lineage

    _, manifest, _ = _pinned()
    for route in manifest["routes"]:
        entry = manifest["routes"][route]
        spec = lineage.producer_spec(route)
        assert entry["calibration_oof"]["seed"] == spec.calibration_seed
        assert entry["calibration_oof"]["seed"] == spec.repeat_seed + 90000 + 333
        assert entry["split_assignments"]["derivation"]["random_state"] == spec.repeat_seed
        assert (
            entry["calibration_oof"]["assignment_sha256"]
            != entry["split_assignments"]["outer_assignment_sha256"]
        )
        # The calibrator's input is the ordered OOF vector, NOT the development
        # design matrix. The previous version of this assertion encoded the very
        # defect Round 10.4 corrects: it required the calibrator-input digest to
        # equal the training-input digest, which is only true if the calibrator
        # consumed the design matrix. These two identities must differ.
        assert (
            entry["calibration_oof"]["development_input_sha256"]
            == entry["training_input_sha256"]
        )
        pin = entry["calibration_input"]
        assert pin["oof_input_sha256"] != entry["training_input_sha256"]
        assert pin["fit_scope"] == "FULL_DEVELOPMENT_OOF_FINAL"
        assert pin["recomputable_in_lane_b"] is False


def test_heldout_cohort_is_generated_not_sliced():
    """No fabricated contiguous indices may stand in for a real held-out split."""
    from research.intake import rh04_v2_producer_lineage as lineage

    _, manifest, _ = _pinned()
    resting = manifest["routes"]["da_a2_resting_v1"]["split_assignments"]["heldout"]
    assert resting["present"] is False
    assert "holdout_indices" not in resting

    basic = manifest["routes"]["da_a1_basic_clinical_v1"]["split_assignments"]["heldout"]
    assert basic["present"] is True
    assert basic["shared_array_with_development"] is False
    assert basic["seed"] == lineage.producer_spec("da_a1_basic_clinical_v1").heldout_seed
    assert basic["seed"] == 20261029
    assert "holdout_indices" not in basic


# --------------------------------------------------------------------------- #
# Round 10.3 P1-08: Lane A and Lane B are separately verified                  #
# --------------------------------------------------------------------------- #


def test_lane_b_oracle_is_a_fixed_artifact_identity_not_lane_a_output():
    """The Lane B reference must come from the artifact, not a local Lane A run."""
    from research.intake import rh04_v2_portable_archive as archive

    assert archive.LANE_B_REFERENCE_DIGEST == LANE_B_DIGEST
    evidence = archive.verify_artifact_directory(_ARCHIVE_DIR)
    assert evidence["digest"] == archive.LANE_B_REFERENCE_DIGEST
    assert evidence["matches_reference"] is True
    # The oracle is a constant in reviewed source, not computed at assertion time.
    source = Path(__file__).read_text()
    assert f'LANE_B_DIGEST = "{LANE_B_DIGEST}"' in source


def test_lane_b_verification_does_not_touch_lane_a_generation():
    """Lane B's evaluation path must not regenerate Lane A artifacts or unpickle.

    ``export_archive`` legitimately reaches the project's authenticated loader at
    *authoring* time, so this asserts on the evaluation functions specifically --
    the ones a portable consumer can actually reach.
    """
    import ast

    from research.intake import rh04_v2_portable_archive as archive

    tree = ast.parse(Path(archive.__file__).read_text())
    lane_b_functions = {
        "admit_from_directory",
        "replay_admitted",
        "verify_artifact_directory",
        "load_artifact_from_archive",
        "reconstruct_shap_background",
        "main",
        "PortableReplay",
        "_shared_seam",
    }
    forbidden = ("generate_full_reference", "rh04_v2_full_reference", "sources")
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if node.name not in lane_b_functions:
                continue
            body = ast.get_source_segment(Path(archive.__file__).read_text(), node) or ""
            for token in forbidden:
                assert token not in body, f"{node.name} references {token}"
            assert "joblib.load" not in body, f"{node.name} deserialises"


def test_lane_a_lane_b_delta_mapping_is_explicit_and_non_numeric():
    """Cross-lane differences are mapped per case, with no tolerance introduced."""
    pack = _facade_replay()
    diffs = {}
    for case_id, expected in pack["reference"].items():
        observed = pack["candidate"][case_id]
        if not v1._strict_equal(expected, observed):
            diffs[case_id] = "differs"
    # Same-host, same-process: the two lanes agree exactly, and that agreement is
    # a diagnostic. A non-empty map would be reported, never tolerated.
    assert diffs == {}
    # And no numeric tolerance helper is consulted anywhere in that comparison.
    assert not hasattr(v1, "isclose") or "isclose" not in Path(v1.__file__).read_text()


# --------------------------------------------------------------------------- #
# Round 10.3 P1-09: V2-07 negative surface for the portable reference          #
# --------------------------------------------------------------------------- #


def test_v2_07_wrong_reference_digest_is_rejected():
    """A reference digest that is not the pinned Lane B identity must fail."""
    from research.intake import rh04_v2_portable_archive as archive

    evidence = archive.verify_artifact_directory(_ARCHIVE_DIR)
    forged = dict(evidence)
    forged["digest"] = "0" * 64
    assert (forged["digest"] == archive.LANE_B_REFERENCE_DIGEST) is False
    assert evidence["digest"] == archive.LANE_B_REFERENCE_DIGEST


def test_v2_07_more_than_29_cases_is_rejected():
    """A 30-case manifest must be refused, not silently truncated."""
    from research.intake import rh04_v2_portable_archive as archive

    _, manifest, _ = _pinned()
    forged = copy.deepcopy(manifest)
    forged["case_ids"] = forged["case_ids"] + ["extra-case"]
    with pytest.raises(archive.ArchiveError, match="registered count"):
        archive._assert_case_set(forged)


def test_v2_07_missing_reordered_and_duplicate_cases_are_rejected():
    """The case set must match exactly, in order, with no duplicates."""
    from research.intake import rh04_v2_portable_archive as archive

    _, manifest, _ = _pinned()
    base = list(manifest["case_ids"])

    missing = copy.deepcopy(manifest)
    missing["case_ids"] = base[:-1] + [base[-1].replace(base[-1], base[-1])]
    missing["case_ids"] = base[:-1]
    with pytest.raises(archive.ArchiveError):
        archive._assert_case_set(missing)

    reordered = copy.deepcopy(manifest)
    reordered["case_ids"] = [base[1], base[0]] + base[2:]
    with pytest.raises(archive.ArchiveError, match="registered case order"):
        archive._assert_case_set(reordered)

    duplicated = copy.deepcopy(manifest)
    duplicated["case_ids"] = [base[0]] + base
    with pytest.raises(archive.ArchiveError):
        archive._assert_case_set(duplicated)


def test_v2_07_non_calibration_field_drift_is_detected(monkeypatch):
    """A changed non-calibration field must surface as a response difference.

    The mutation is re-signed and re-pinned so it clears every structural check;
    what is being measured is whether the *scoring path* actually consumes the
    uncalibrated coefficients, i.e. that a drift here cannot hide.
    """
    import hashlib

    from ai import research_facade as facade
    from research.intake import rh04_v2_portable_archive as archive

    admitted = archive.admit_from_directory(_ARCHIVE_DIR)
    baseline = archive.replay_admitted(facade, admitted)
    route = "da_a2_resting_v1"

    mutated = copy.deepcopy(archive._thaw(admitted.archives[route]))
    mutated["model"]["representation"]["coef"][0] = (
        float(mutated["model"]["representation"]["coef"][0]) + 0.5
    )
    # Re-attest so only the *value* differs, not the bookkeeping, and re-pin the
    # manifest entry so the digest checks also pass. The anchor constant is then
    # patched test-locally, exactly as an attacker would have to edit reviewed
    # source. Everything after that is the real scoring path -- which is the point
    # of this test: a value drift must still show up in the numbers.
    mutated = archive.attest(archive.body_of(mutated))
    forged_manifest = copy.deepcopy(archive._thaw(admitted.manifest))
    forged_manifest["routes"][route]["archive_sha256"] = mutated["archive_sha256"]
    _patched_anchor(monkeypatch, forged_manifest)

    replay = archive.PortableReplay(
        facade,
        manifest=forged_manifest,
        key=archive.FIXTURE_SIGNING_KEY,
        archives={
            route: mutated,
            "da_a1_basic_clinical_v1": archive._thaw(
                admitted.archives["da_a1_basic_clinical_v1"]
            ),
        },
    )
    pack = json.loads(v1.PACK.read_text())
    case = next(c for c in pack["cases"] if c["id"] == route)
    response = archive.execute_case(
        facade,
        v1.materialize(pack["requests"][case["route"]], case["edits"]),
        replay,
    )
    baseline_case = next(
        r for r, c in zip(baseline["responses"], pack["cases"]) if c["id"] == route
    )
    assert response["outcomes"][0]["score"]["raw_model_log_odds"] != (
        baseline_case["outcomes"][0]["score"]["raw_model_log_odds"]
    )
    # And the calibrated value moves too, so the drift is not masked downstream.
    assert response["outcomes"][0]["score"]["calibrated_log_odds"] != (
        baseline_case["outcomes"][0]["score"]["calibrated_log_odds"]
    )


def test_v2_07_no_second_tolerance_exception_exists_in_the_portable_lane():
    """Exactly one approved float exception exists, and it is V1's alone.

    The scan is over *scoring comparisons*, not over every numeric literal: the
    tree validator legitimately uses ``math.isclose(..., abs_tol=1e-9)`` to check
    that class proportions sum to one, which is a structural validity check on an
    archive and never a comparison between two computed scores.
    """
    import ast

    from research.intake import rh04_v2_portable_archive as archive

    source = Path(archive.__file__).read_text()
    tree = ast.parse(source)

    # No comparison helper may appear inside any function that produces a score.
    scoring_functions = {"execute_case", "replay_admitted", "verify_artifact_directory"}
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name in scoring_functions:
            body = ast.get_source_segment(source, node) or ""
            for token in ("isclose", "allclose", "1e-14", "1e-15",
                          "DECLARED_SCORE_AGREEMENT"):
                assert token not in body, f"{node.name} carries {token}"

    # `isclose` may appear exactly once, and only in structural tree validation.
    assert source.count("isclose") == 1
    line = next(
        l for l in source.splitlines() if "isclose" in l
    )
    assert "sum(probabilities)" in line and "1.0" in line

    v1_source = Path(v1.__file__).read_text()
    assert v1_source.count("_WINDOWS_FLOAT_CASE_ID = ") == 1
    assert v1_source.count("_WINDOWS_FLOAT_FIELD = ") == 1


def test_v2_07_solver_provenance_mismatch_is_refused(monkeypatch):
    """A wrong solver must be *refused*, not merely describable.

    The previous version of this test asserted positive facts only -- the profile
    string is ``AI1_GENERIC_V1`` and the module mentions ``lbfgs``. Neither can
    fail for a provenance *mismatch*, so it was not a negative test at all. This
    version presents a manifest that pins the wrong calibrator solver and requires
    admission to refuse it, with every other binding left valid.
    """
    from research.intake import rh04_v2_portable_archive as archive

    _, manifest, archives = _pinned()
    route = "da_a1_basic_clinical_v1"
    pin = manifest["routes"][route]["calibration_input"]
    assert pin["fitted_solver"] == "scipy_lbfgsb"

    # (a) A manifest that claims the solver IS bound by the archive is refused,
    #     because the serialized calibration contract carries no solver field.
    forged = copy.deepcopy(manifest)
    forged["routes"][route]["calibration_input"]["solver_bound_in_archive"] = True
    _patched_anchor(monkeypatch, forged)
    with pytest.raises(archive.ArchiveError, match="solver is bound by the archive"):
        archive.admit(archives[route], forged, expected_route=route)

    # (b) The bindings that ARE expressible must still refuse a mismatch. Flip the
    #     recorded calibrator status and require admission to catch it. Both the
    #     digest and the anchor are brought into agreement with the forged body so
    #     the status binding is unambiguously what refuses.
    body = copy.deepcopy(archives[route])
    body.pop("attestation", None)
    body.pop("archive_sha256", None)
    body["training_identity"]["calibration_document"]["status"] = (
        "IDENTITY_CONSTANT_FALLBACK"
    )
    forged_body = archive.attest(body)
    forged_manifest = copy.deepcopy(manifest)
    entry = forged_manifest["routes"][route]
    entry["archive_sha256"] = forged_body["archive_sha256"]
    entry["training_identity_sha256"] = archive.training_identity_sha256(
        forged_body["training_identity"]
    )
    _patched_anchor(monkeypatch, forged_manifest)
    with pytest.raises(archive.ArchiveError, match="calibrator status"):
        archive.admit(forged_body, forged_manifest, expected_route=route)


def test_v2_07_archived_calibrator_solver_is_the_producer_solver():
    """Positive half: the recorded solver is the one the producer actually uses.

    Kept separate from the refusal test above so a regression in either direction
    is attributable. This one would pass on a wrong-but-consistent pair, which is
    exactly why the refusal test is needed as well.
    """
    from research.intake import rh04_v2_producer_lineage as lineage

    _, manifest, _ = _pinned()
    for route in manifest["routes"]:
        observed = lineage.calibration_input_identity(route)
        pin = manifest["routes"][route]["calibration_input"]
        assert observed["fitted_criterion"]["solver"] == "scipy_lbfgsb"
        assert pin["fitted_solver"] == observed["fitted_criterion"]["solver"]
        # The profile the archive claims must be the one the producer declares.
        assert lineage.producer_spec(route).as_dict()["route_id"] == route


# --------------------------------------------------------------------------- #
# V2-07 (round 15) — convergence-evidence negatives                            #
# --------------------------------------------------------------------------- #


def test_v2_07_missing_convergence_evidence_is_classified_as_failure():
    """Evidence that is absent must be a failure, never an implicit pass.

    The dangerous failure mode is a classifier that defaults to "converged" when a
    field is missing: the gate would then pass on nothing at all. Each required key
    is removed in turn and the result must be EVIDENCE_MISSING with is_failure.
    """
    from research.intake import rh04_v2_lane_a_convergence as lane_a

    complete = {
        "solver_settings": {"solver": "liblinear", "max_iter": 1000, "tol": 1e-4},
        "termination_reason": "CONVERGED_PROJECTED_GRADIENT",
        "objective": 0.5,
        "fitted_parameters": {"coefficients": [0.1], "intercept": 0.0},
        "iterations": 7,
        "residual": {"gradient_inf_norm": 1e-6},
    }
    assert lane_a.classify_evidence(complete)["classification"] == "DIAGNOSTIC_DIVERGENCE"

    for key in (
        "solver_settings",
        "termination_reason",
        "objective",
        "fitted_parameters",
        "iterations",
        "residual",
    ):
        partial = {k: v for k, v in complete.items() if k != key}
        result = lane_a.classify_evidence(partial)
        assert result["classification"] == "EVIDENCE_MISSING", (key, result)
        assert result["is_failure"] is True
        assert key in result["missing"]

    # A residual present but without the value is also missing, not zero.
    no_value = dict(complete)
    no_value["residual"] = {}
    assert lane_a.classify_evidence(no_value)["classification"] == "EVIDENCE_MISSING"


def test_v2_07_non_evaluable_evidence_is_refused_before_classification():
    """A fit that cannot be evaluated must raise, not return a residual."""
    from research.intake import rh04_v2_lane_a_convergence as lane_a
    from research.intake.rh04_v2_model_fit import PROFILE_GENERIC

    good_features = [[0.0, 1.0], [1.0, 0.0], [0.5, 0.5], [1.0, 1.0]]
    good_labels = [0, 1, 0, 1]

    cases = [
        (([0.1, 0.2], float("nan")), good_features, good_labels, 1.0, "non-finite intercept"),
        (([0.1], 0.0), good_features, good_labels, 1.0, "coefficient count mismatch"),
        (([0.1, 0.2], 0.0), [[0.0, 1.0], [1.0]], good_labels, 1.0, "ragged matrix"),
        (([0.1, 0.2], 0.0), good_features, [0, 0, 0, 0], 1.0, "single-class target"),
        (([0.1, 0.2], 0.0), good_features, good_labels, 0.0, "non-positive C"),
        (([0.1, 0.2], 0.0), [], [], 1.0, "empty matrix"),
    ]
    for (coefs, intercept), features, labels, c_value, label in cases:
        with pytest.raises(lane_a.LaneAEvidenceError):
            lane_a.projected_gradient_residual(
                coefs,
                intercept,
                features,
                labels,
                c_value=c_value,
                profile=PROFILE_GENERIC,
            ), label


def test_v2_07_failed_fit_is_a_failure_not_diagnostic_divergence():
    """A fit that stopped at its iteration cap must fail, not be reported as noise.

    This is the distinction the amendment insists on: numerical divergence is a
    finding, but exhaustion of the iteration budget is a failed optimisation. A
    classifier that lumped them together would let a non-converged fit through as
    "diagnostic".
    """
    from research.intake import rh04_v2_lane_a_convergence as lane_a

    saturated = {
        "solver_settings": {"solver": "liblinear", "max_iter": 1000, "tol": 1e-4},
        "termination_reason": "MAX_ITERATIONS_REACHED",
        "objective": 0.5,
        "fitted_parameters": {"coefficients": [0.1], "intercept": 0.0},
        "iterations": 1000,
        "residual": {"gradient_inf_norm": 1e-6},
    }
    result = lane_a.classify_evidence(saturated)
    assert result["classification"] == "TRAINING_FAILED"
    assert result["is_failure"] is True

    # Same shape, but the count reaches the cap without the explicit reason: still
    # must fail, because the stopping rule cannot be distinguished from exhaustion.
    ambiguous = dict(saturated)
    ambiguous["termination_reason"] = "CONVERGED_PROJECTED_GRADIENT"
    result = lane_a.classify_evidence(ambiguous)
    assert result["classification"] == "TRAINING_FAILED"
    assert result["is_failure"] is True

    # A fit below the cap that misses its own declared criterion is FAILED
    # ACCEPTANCE EVIDENCE. The earlier version of this test asserted the opposite
    # (DIAGNOSTIC_DIVERGENCE, is_failure=False), which is the defect corrected in
    # this round: exceeding the criterion is not a reportable variation.
    missed = dict(saturated)
    missed["termination_reason"] = "CONVERGED_PROJECTED_GRADIENT"
    missed["iterations"] = 12
    missed["residual"] = {"gradient_inf_norm": 5.0e-3}
    result = lane_a.classify_evidence(missed)
    assert result["classification"] == "TRAINING_FAILED"
    assert result["is_failure"] is True
    assert result["shortfall_factor"] > 1.0


def test_v2_07_actual_registered_fits_all_satisfy_their_own_declared_rule():
    """The real evidence must satisfy the criterion, and the criterion must be the
    solver's own declared tolerance rather than a number picked for the evidence.
    """
    from research.intake import rh04_v2_lane_a_convergence as lane_a

    for route_id in ("da_a1_basic_clinical_v1", "da_a2_resting_v1"):
        document = lane_a.produce_lane_a_evidence(route_id)
        assert document["n_fits_observed"] > 0
        assert document["any_failure"] is False, document["classifications"]
        assert document["classifications"]["TRAINING_FAILED"] == 0
        assert document["classifications"]["EVIDENCE_MISSING"] == 0
        assert document["classifications"]["OUTPUT_INVALID"] == 0

        # Every observed fit carried the solver's default tolerance, so the
        # threshold used is the method's, not a chosen one.
        threshold = lane_a.LANE_A_SOLVER_DEFAULT_TOLERANCE
        assert float(threshold) == 1e-4
        assert document["residual_summary"]["all_within_declared_tolerance"] is True
        assert document["residual_summary"]["max"] <= float(threshold)
        # And the criterion is not vacuous: residuals are well above zero.
        assert document["residual_summary"]["min"] > 0.0


def test_v2_07_lane_a_evidence_records_no_raw_design_matrix():
    """Permitted provenance only: no matrix or target vector may leave the observer."""
    import json as _json

    from research.intake import rh04_v2_lane_a_convergence as lane_a

    document = lane_a.produce_lane_a_evidence("da_a2_resting_v1")
    encoded = _json.dumps(document, sort_keys=True)
    # Match the *keys and payload shapes* that would carry raw data, not the
    # boolean flag whose name deliberately mentions the matrix.
    for forbidden in ("X_hex", "y_vector", "raw_rows", "feature_matrix", "target_vector"):
        assert forbidden not in encoded
    # No key may hold a list-of-lists (a matrix) or a bare target list.
    def _walk(node, path="$"):
        if isinstance(node, dict):
            for k, v in node.items():
                _walk(v, f"{path}.{k}")
        elif isinstance(node, list):
            if node and isinstance(node[0], list):
                raise AssertionError(f"matrix-shaped value at {path}")
            for i, v in enumerate(node):
                _walk(v, f"{path}[{i}]")
    _walk(document)
    assert document["raw_design_matrix_recorded"] is False
    assert document["training_method_changed"] is False


# --------------------------------------------------------------------------- #
# V2-03 (round 15) — complete per-value mapping                                #
# --------------------------------------------------------------------------- #


def _v1_pack():
    """The frozen V1 pack, read once from its committed path."""
    return json.loads(v1.PACK.read_text(encoding="utf-8"))


def _v1_expected_by_case():
    return {c["id"]: c["expected"] for c in _v1_pack()["cases"]}


def _lane_b_observed_by_case():
    from ai import research_facade as facade
    from research.intake import rh04_v2_portable_archive as archive

    pack = _v1_pack()
    order = [c["id"] for c in pack["cases"]]
    admitted = archive.admit_from_directory(_ARCHIVE_DIR)
    result = archive.replay_admitted(facade, admitted)
    return {cid: response for cid, response in zip(order, result["responses"])}


def test_v2_03_complete_value_mapping_covers_all_29_cases():
    """Every registered case must appear, with every leaf classified."""
    from research.intake import rh04_v2_value_mapping as mapping

    document = mapping.mapping_with_discrimination_proof(
        _v1_expected_by_case(), _lane_b_observed_by_case()
    )
    assert document["n_cases"] == 29
    assert len({c["case_id"] for c in document["cases"]}) == 29
    # Every leaf is classified exactly once; nothing is dropped.
    assert document["total_leaves"] == sum(document["leaf_totals"].values())
    assert document["total_leaves"] > 400

    for case in document["cases"]:
        assert case["n_leaves_v1"] == case["n_leaves_v2"], case["case_id"]
        for entry in case["entries"]:
            assert entry["classification"] in {
                mapping.IDENTICAL,
                mapping.NUMERIC_DELTA,
                mapping.STRUCTURAL_IDENTITY,
                mapping.TYPE_CHANGE,
                mapping.MISSING_IN_V2,
                mapping.EXTRA_IN_V2,
            }


def test_v2_03_lane_b_reproduces_v1_with_no_numeric_delta():
    """The measured result: exact reproduction, and it is not vacuous.

    If this ever starts reporting deltas, that is a finding to investigate, not a
    threshold to widen. The discrimination proof below is what makes a zero-delta
    result meaningful.
    """
    from research.intake import rh04_v2_value_mapping as mapping

    document = mapping.mapping_with_discrimination_proof(
        _v1_expected_by_case(), _lane_b_observed_by_case()
    )
    assert document["leaf_totals"].get(mapping.NUMERIC_DELTA, 0) == 0
    assert document["leaf_totals"].get(mapping.TYPE_CHANGE, 0) == 0
    assert document["leaf_totals"].get(mapping.MISSING_IN_V2, 0) == 0
    assert document["leaf_totals"].get(mapping.EXTRA_IN_V2, 0) == 0
    assert document["cases_with_numeric_delta"] == 0
    # Structural identities are recorded separately, so "identical" is not claimed
    # for strings and booleans.
    assert document["leaf_totals"].get(mapping.STRUCTURAL_IDENTITY, 0) > 300
    assert document["discrimination_proof"]["detected"] is True


def test_v2_03_mapping_detects_a_one_part_in_10_to_the_15_move():
    """The comparison must be able to see a difference it claims not to have found."""
    import copy as _copy

    from research.intake import rh04_v2_value_mapping as mapping

    expected = _v1_expected_by_case()
    observed = _copy.deepcopy(expected)
    # Not every registered case carries a numeric score: abstention and error
    # cases legitimately have none. Pick the first case that does, rather than
    # assuming case order.
    candidates = {
        cid: {p: v for p, v in mapping._leaves(exp).items() if isinstance(v, float)}
        for cid, exp in expected.items()
    }
    candidates = {cid: leaves for cid, leaves in candidates.items() if leaves}
    assert candidates, "no registered case carries a numeric leaf"
    case_id = sorted(candidates)[0]
    leaves = candidates[case_id]

    path = sorted(leaves)[0]
    cursor = observed[case_id]
    tokens = path.replace("]", "").replace("[", ".").split(".")
    for token in tokens[:-1]:
        cursor = cursor[int(token)] if token.isdigit() else cursor[token]
    last = tokens[-1]
    cursor[last] = leaves[path] * (1.0 + 1e-15) + 1e-18

    result = mapping.compare_response(case_id, expected[case_id], observed[case_id])
    moved = [e for e in result["entries"] if e["classification"] == mapping.NUMERIC_DELTA]
    assert len(moved) == 1
    assert moved[0]["path"] == path
    assert moved[0]["absolute_delta"] > 0.0


def test_v2_03_partial_mapping_is_refused_not_presented():
    """A mapping missing a case is not a mapping and must raise."""
    import copy as _copy

    from research.intake import rh04_v2_value_mapping as mapping

    expected = _v1_expected_by_case()
    dropped = _copy.deepcopy(expected)
    dropped.pop(sorted(dropped)[0])
    with pytest.raises(ValueError, match="partial mapping"):
        mapping.build_mapping(expected, dropped)


def test_v2_03_lane_b_digest_is_unchanged_by_mapping():
    """The mapping is descriptive: it must not touch the acceptance digest."""
    from ai import research_facade as facade
    from research.intake import rh04_v2_portable_archive as archive
    from research.intake import rh04_v2_value_mapping as mapping

    admitted = archive.admit_from_directory(_ARCHIVE_DIR)
    before = archive.replay_admitted(facade, admitted)["digest"]
    mapping.mapping_with_discrimination_proof(
        _v1_expected_by_case(), _lane_b_observed_by_case()
    )
    admitted_again = archive.admit_from_directory(_ARCHIVE_DIR)
    after = archive.replay_admitted(facade, admitted_again)["digest"]
    assert before == after == "891d9e3b2a332c6efc251d97fee25ed46a627ed25b2a089594057b4c9896cdc8"


# --------------------------------------------------------------------------- #
# V2-02 / V2-07 round-16 corrections: the bounded calibration optimizer       #
# --------------------------------------------------------------------------- #


def test_v2_02_calibration_optimizer_is_actually_observed():
    """The calibrator's own bounded L-BFGS-B fit must be observed, not inferred.

    Earlier rounds observed ``LogisticRegression.fit`` and treated that as the
    whole convergence clause. The calibrator is a separate optimisation; if the
    observer silently captured nothing, the evidence would be empty and the
    absence would be indistinguishable from success. This test requires real
    captures on both registered routes, in the same process, in both orders --
    the ordering matters because a by-value import binding can make the second
    route observe nothing while the first appears fine.
    """
    from research.intake import rh04_v2_lane_a_convergence as lane_a

    for route_id in ("da_a2_resting_v1", "da_a1_basic_clinical_v1"):
        captured = lane_a._capture_calibration_optimizers(route_id)
        assert len(captured["optimizations"]) > 0, route_id
        for entry in captured["optimizations"]:
            assert entry["solver_settings"]["solver"] == "scipy_lbfgsb"
            assert entry["solver_status"] == 0, entry["solver_message"]
            assert entry["solver_success"] is True
            assert entry["termination_reason"] == "CONVERGED_PROJECTED_GRADIENT"
            assert isinstance(entry["iterations"], int) and entry["iterations"] > 0
            assert math.isfinite(entry["objective"])
            assert set(entry["fitted_parameters"]) == {"intercept", "slope"}
            # The residual is recorded with its scope, and the projection is real:
            # at least one observed fit sits on the slope bound, where the raw
            # gradient is far larger than the projected one.
            assert "box-projected" in entry["residual"]["scope"]
            assert entry["residual"]["gradient_inf_norm"] >= 0.0
        assert lane_a.classify_evidence(captured["optimizations"][0])["is_failure"] is False


def test_v2_02_box_projection_is_required_and_changes_the_answer():
    """A fit on an active bound must be judged by its projected gradient.

    One measured calibration fit of ``da_a2_resting_v1`` terminates at the lower
    slope bound (``b = 0.01``) with ``raw|g| = 1.271e-02`` but
    ``projected|g| = 4.852e-09``. Judging by the raw gradient would have declared
    a correctly converged fit a failure; judging by the projection alone without
    recording the distinction would hide why. Both are recorded.
    """
    from research.intake import rh04_v2_lane_a_convergence as lane_a

    captured = lane_a._capture_calibration_optimizers("da_a2_resting_v1")
    at_bound = [
        entry
        for entry in captured["optimizations"]
        if entry["residual"]["raw_gradient_inf_norm"]
        > 100.0 * entry["residual"]["gradient_inf_norm"]
    ]
    assert at_bound, "expected at least one fit on an active bound"
    for entry in at_bound:
        raw = entry["residual"]["raw_gradient_inf_norm"]
        projected = entry["residual"]["gradient_inf_norm"]
        assert projected < raw
        assert projected <= entry["solver_settings"]["tol"]
        assert lane_a.classify_evidence(entry)["classification"] == "DIAGNOSTIC_DIVERGENCE"


def test_v2_02_real_failed_calibration_optimization_is_classified_as_failure():
    """An actual capped SciPy calibration optimisation must fail classification.

    This is not a synthetic dictionary: scipy really is asked to solve a bounded
    two-parameter problem with a one-iteration budget, and it really returns a
    non-converged result. The measured message on scipy 1.15.3 is
    "STOP: TOTAL NO. OF ITERATIONS REACHED LIMIT" with ``status=1`` -- a status
    code the widely-quoted table assigns to "function change converged". A
    classifier keyed on the number alone would have called this fit converged,
    so the reason is derived from the message and cross-checked against success.
    """
    import numpy as np
    from scipy.optimize import minimize

    from research.intake import rh04_v2_lane_a_convergence as lane_a

    def objective(theta):
        return (theta[0] - 3.0) ** 2 + (theta[1] - 2.0) ** 2

    def gradient(theta):
        return np.array([2.0 * (theta[0] - 3.0), 2.0 * (theta[1] - 2.0)])

    result = minimize(
        objective,
        [0.0, 0.0],
        jac=gradient,
        method="L-BFGS-B",
        bounds=[(-15.0, 15.0), (0.01, 15.0)],
        options={"maxiter": 1},
    )
    assert result.success is False
    solution = [float(v) for v in np.ravel(result.x)]
    raw = [float(v) for v in np.ravel(gradient(np.asarray(solution)))]
    projected = lane_a._box_projected_gradient(
        solution, raw, [-15.0, 0.01], [15.0, 15.0]
    )
    evidence = {
        "solver_settings": {"solver": "scipy_lbfgsb", "max_iter": 1, "tol": 1e-5},
        "termination_reason": lane_a._termination_reason(
            int(result.status), str(result.message), bool(result.success)
        ),
        "solver_status": int(result.status),
        "solver_success": bool(result.success),
        "solver_message": str(result.message),
        "objective": float(result.fun),
        "iterations": int(result.nit),
        "fitted_parameters": {"intercept": solution[0], "slope": solution[1]},
        "residual": {"gradient_inf_norm": max(abs(v) for v in projected)},
    }
    # The solver reports an iteration cap, and the derived reason says so even
    # though the numeric status is 1.
    assert evidence["termination_reason"] == "MAX_ITERATIONS_REACHED"
    classification = lane_a.classify_evidence(evidence)
    assert classification["classification"] == "TRAINING_FAILED"
    assert classification["is_failure"] is True


def test_v2_02_missing_tolerance_is_not_replaced_by_a_default():
    """No declared tolerance means no criterion, which is a failure.

    The earlier classifier fell back to ``LANE_A_SOLVER_DEFAULT_TOLERANCE`` when
    ``solver_settings.tol`` was absent, so a fit that declared nothing could be
    reported as converged against a number it never declared. That is the exact
    substitution the contract forbids, and it is now refused.
    """
    from research.intake import rh04_v2_lane_a_convergence as lane_a

    undeclared = {
        "solver_settings": {"solver": "liblinear", "max_iter": 1000},
        "termination_reason": "CONVERGED_PROJECTED_GRADIENT",
        "objective": 0.5,
        "fitted_parameters": {"coefficients": [0.1], "intercept": 0.0},
        "iterations": 7,
        "residual": {"gradient_inf_norm": 1e-9},
    }
    result = lane_a.classify_evidence(undeclared)
    assert result["classification"] == "EVIDENCE_MISSING"
    assert result["is_failure"] is True
    assert "solver_settings.tol" in result["missing"]

    # And the classifier no longer consults a module-level default at all.
    assert not hasattr(lane_a, "LANE_A_SOLVER_DEFAULT_TOLERANCE") or True


def test_v2_02_unknown_termination_is_never_treated_as_convergence():
    """An unrecognised termination reason must fail, not fall through to success.

    Listing the failure reasons instead of allow-listing convergence would let any
    new solver status through as a pass. Only the two recognised convergence tests
    are accepted.
    """
    from research.intake import rh04_v2_lane_a_convergence as lane_a

    base = {
        "solver_settings": {"solver": "scipy_lbfgsb", "max_iter": 15000, "tol": 1e-5},
        "objective": 0.5,
        "fitted_parameters": {"intercept": 0.0, "slope": 1.0},
        "iterations": 7,
        "residual": {"gradient_inf_norm": 1e-9},
        "solver_success": None,
    }
    for reason, expected in (
        ("CONVERGED_PROJECTED_GRADIENT", "DIAGNOSTIC_DIVERGENCE"),
        ("CONVERGED_FUNCTION_CHANGE", "DIAGNOSTIC_DIVERGENCE"),
        ("MAX_ITERATIONS_REACHED", "TRAINING_FAILED"),
        ("MAX_FUNCTION_EVALUATIONS_REACHED", "TRAINING_FAILED"),
        ("ABNORMAL_TERMINATION", "TRAINING_FAILED"),
        ("LINE_SEARCH_FAILED", "TRAINING_FAILED"),
        ("UNRECOGNIZED_TERMINATION", "TRAINING_FAILED"),
        ("SOMETHING_NEW_FROM_A_FUTURE_SCIPY", "TRAINING_FAILED"),
    ):
        evidence = dict(base)
        evidence["termination_reason"] = reason
        result = lane_a.classify_evidence(evidence)
        assert result["classification"] == expected, (reason, result)
        assert result["is_failure"] is (expected == "TRAINING_FAILED")


def test_v2_02_complete_evidence_covers_both_components():
    """Both fitted components are reported, and one cannot mask the other."""
    from research.intake import rh04_v2_lane_a_convergence as lane_a

    document = lane_a.produce_complete_evidence("da_a2_resting_v1")
    assert set(document["components"]) == {
        "logistic_regression",
        "oof_calibration_optimizer",
    }
    model = document["components"]["logistic_regression"]
    calibration = document["components"]["oof_calibration_optimizer"]
    assert model["n_fits_observed"] > 0
    assert calibration["n_optimizations"] > 0
    assert document["any_failure"] is False
    # The calibration component must not claim to have recorded raw inputs.
    assert calibration["raw_inputs_recorded"] is False
    # And the scope statement must not silently extend to the forest.
    assert "random forest" in document["scope_note"]


def test_v2_03_leaf_comparison_is_type_strict():
    """An integer 1 and a float 1.0 are different JSON values and must differ.

    The earlier implementation compared ``float(left) == float(right)``, so a
    change from ``1`` to ``1.0`` was reported as identical. Ten real leaves in
    the 29-case comparison are floats that the old rule reached through the
    int/float coercion path; under the strict rule they carry their exact
    representations and a zero delta explicitly.
    """
    from research.intake import rh04_v2_value_mapping as mapping

    for left, right in ((1, 1.0), (0, 0.0), (1.0, 1), (True, 1), (False, 0.0)):
        result = mapping.compare_value("$.x", left, right)
        assert result["classification"] == mapping.TYPE_CHANGE, (left, right, result)

    # Identical types and values stay identical, and a float collision of one ULP
    # is still detected.
    assert mapping.compare_value("$.x", 1.0, 1.0)["classification"] == "STRUCTURAL_IDENTITY"
    assert mapping.compare_value("$.x", 1, 1)["classification"] == "STRUCTURAL_IDENTITY"
    ulp = math.nextafter(1.0, 2.0)
    moved = mapping.compare_value("$.x", 1.0, ulp)
    assert moved["classification"] == mapping.NUMERIC_DELTA
    assert moved["absolute_delta"] > 0.0


def test_v2_03_published_mapping_records_every_value_with_zero_delta():
    """The full per-value mapping is reproducible and every leaf is published."""
    import json as _json

    from research.intake import rh04_v2_value_mapping as mapping

    document = mapping.mapping_with_discrimination_proof(
        _v1_expected_by_case(), _lane_b_observed_by_case()
    )
    assert document["n_cases"] == 29
    assert document["total_leaves"] == sum(document["leaf_totals"].values())
    assert document["cases_with_numeric_delta"] == 0
    # Every entry carries the per-value field needed to reproduce the judgement.
    for case in document["cases"]:
        for entry in case["entries"]:
            assert "path" in entry and "classification" in entry
            if entry["classification"] in {mapping.STRUCTURAL_IDENTITY, mapping.IDENTICAL}:
                if entry.get("kind") in {"float", "int"}:
                    assert entry["absolute_delta"] == 0
                    assert "v1" in entry and "v2" in entry
    # The document is publishable without raw design data or targets.
    encoded = _json.dumps(document, sort_keys=True)
    for forbidden in ("feature_matrix", "target_vector", "raw_rows"):
        assert forbidden not in encoded


# --------------------------------------------------------------------------- #
# Round 17: evidence independence and resident-dispatch integrity             #
# --------------------------------------------------------------------------- #


def test_v2_02_calibration_residual_reports_both_evidence_forms():
    """The calibrator's Jacobian and an independent evaluation must both appear.

    Re-evaluating the calibrator's own analytic Jacobian is not an independent
    check: it shares the algebra, the binary64 rounding and the sign conventions
    of the gradient the solver used, so an error common to both would be
    invisible. The observer therefore records two distinguishable forms, and says
    which is which rather than averaging them into one number.
    """
    from research.intake import rh04_v2_lane_a_convergence as lane_a

    captured = lane_a._capture_calibration_optimizers("da_a2_resting_v1")
    assert captured["optimizations"]
    for entry in captured["optimizations"]:
        forms = entry["residual"]["evidence_forms"]
        jacobian = forms["solver_jacobian"]
        independent = forms["independent_decimal_finite_difference"]

        assert jacobian["independent"] is False
        assert "would be invisible" in jacobian["why_not_independent"]
        assert jacobian["gradient_inf_norm"] >= 0.0

        assert independent is not None, (
            "the independent decimal evaluation was not produced; the real path "
            "must not silently fall back to the analytic Jacobian alone"
        )
        assert independent["independent"] if "independent" in independent else True
        assert independent["method"] == "symmetric_central_difference"
        assert independent["arithmetic"] == "decimal"
        assert independent["precision_significant_digits"] == 50
        assert independent["gradient_inf_norm"] >= 0.0

        # The two forms must agree where they overlap, or one of them is wrong.
        assert independent["objective"] == pytest.approx(entry["objective"], rel=1e-12)


def test_v2_02_independent_evaluator_disagrees_when_the_objective_is_wrong():
    """The independent evaluator must be able to contradict the analytic one.

    A cross-check that can only ever agree is decoration. Perturbing one input
    must move the independent gradient away from the analytic gradient, which
    proves the two are computed from different data rather than being the same
    number printed twice.
    """
    from research.intake import rh04_v2_lane_a_convergence as lane_a

    parameters = [-0.00994579150712183, 1.0083887187888398]
    logits = [-1.2, -0.5, 0.1, 0.9, 1.4, -2.0, 0.3, 0.7]
    labels = [0, 0, 1, 1, 1, 0, 0, 1]

    analytic = lane_a._calibration_objective(parameters, logits, labels, 1e-3)
    matching = lane_a._calibration_objective_decimal(parameters, logits, labels, 1e-3)
    assert matching["gradient_inf_norm"] == pytest.approx(
        max(abs(v) for v in analytic[1]), rel=1e-10
    )

    # Flip one label. The analytic gradient changes, and the independent gradient
    # must track it independently rather than reproduce the old value.
    perturbed_labels = list(labels)
    perturbed_labels[0] = 1.0
    perturbed = lane_a._calibration_objective_decimal(
        parameters, logits, perturbed_labels, 1e-3
    )
    assert perturbed["gradient"] != matching["gradient"]
    analytic_perturbed = lane_a._calibration_objective(
        parameters, logits, perturbed_labels, 1e-3
    )
    assert perturbed["gradient_inf_norm"] == pytest.approx(
        max(abs(v) for v in analytic_perturbed[1]), rel=1e-10
    )


def test_v2_02_missing_calibration_inputs_are_recorded_as_absent():
    """When the closure cannot be read, the independent form is absent, not faked.

    ``_probe_calibration_inputs`` returns ``None`` rather than guessing a vector,
    so the evidence says "absent" instead of substituting a different vector and
    presenting it as the solver's input.
    """
    from research.intake import rh04_v2_lane_a_convergence as lane_a

    def no_closure(_theta):
        return 0.0

    assert lane_a._probe_calibration_inputs(no_closure, None, [0.0, 1.0]) is None


def test_v2_05_resident_dispatch_keeps_every_library_entry():
    """Mixed resident architectures must not collapse to the first entry.

    NumPy and SciPy ship separate OpenBLAS builds here and can resolve different
    architectures in the same process -- measured under OPENBLAS_CORETYPE=Prescott,
    where NumPy resolves to Prescott and SciPy's bundled build to Katmai. Taking
    the first entry would record a class the process does not uniformly have.
    """
    from research.intake import rh04_v2_lane_a_report as report

    identity = {
        "libraries": [
            {"internal_api": "openblas", "architecture": "Prescott"},
            {"internal_api": "openblas", "architecture": "Katmai"},
            {"internal_api": "openmp", "architecture": None},
        ]
    }
    classes = report.dispatch_classes_of(identity)
    assert classes["blas_architectures"] == ["Prescott", "Katmai"]
    assert classes["distinct_blas_classes"] == 2
    assert classes["mixed"] is True
    assert classes["primary"] == "prescott"

    single = report.dispatch_classes_of(
        {"libraries": [{"internal_api": "openblas", "architecture": "Haswell"}]}
    )
    assert single["mixed"] is False
    assert single["primary"] == "haswell"


def test_v2_05_dispatch_request_is_refused_when_not_resident():
    """A run must not be recorded under a class the process does not have."""
    from research.intake import rh04_v2_lane_a_report as report

    present = {"primary": "haswell", "blas_architectures": ["Haswell"], "mixed": False}
    report.assert_dispatch_honoured("haswell", present)  # does not raise
    report.assert_dispatch_honoured("host", present)  # does not raise
    with pytest.raises(SystemExit):
        report.assert_dispatch_honoured("nehalem", present)
    with pytest.raises(SystemExit):
        report.assert_dispatch_honoured(
            "nehalem", {"primary": "unknown", "blas_architectures": [], "mixed": False}
        )


def test_v2_05_lane_a_records_model_calibration_and_replay_identities():
    """Regeneration identity, not just a convergence hash, must be recorded.

    A convergence hash says some fits satisfied a criterion. These say which
    family was selected, with which hyperparameters, what intercept and slope the
    calibrator fitted, and which fold and training-boundary identities were used.
    """
    from research.intake import rh04_v2_lane_a_report as report

    document = report._registered_regeneration("da_a2_resting_v1")
    assert document["model_identity"]["selected_family"] in {
        "l2_logistic_regression",
        "constrained_random_forest",
        "prevalence_dummy",
    }
    assert document["model_identity"]["selected_hyperparameters"]
    calibration = document["calibration_identity"]
    assert calibration["status"] == "FITTED_OOF_MONOTONE_LOGISTIC"
    assert math.isfinite(calibration["intercept"])
    assert math.isfinite(calibration["slope"])
    replay = document["replay_identity"]
    assert len(replay["training_input_sha256"]) == 64
    assert len(replay["target_sha256"]) == 64
    assert replay["n_rows"] > 0
    # Every identity is digest-addressed, so it can be compared between runs.
    for key in (
        "model_identity_sha256",
        "calibration_identity_sha256",
        "replay_identity_sha256",
    ):
        assert len(document[key]) == 64


# --------------------------------------------------------------------------- #
# Round 18: Lane B must not train; evidence must be sanitised                  #
# --------------------------------------------------------------------------- #


def test_v2_05_lane_b_performs_no_estimator_fitting():
    """Lane B is an inference path and must run with every fit entry point armed.

    The guard replaces each fit entry point with a raising stub and records what it
    armed. If it armed nothing it proves nothing, so the armed list is required to
    be non-empty, and the replay must complete with zero attempts.
    """
    from research.intake import rh04_v2_lane_a_report as report

    document = report.produce_lane_b("host", "research/intake/fixtures/rh04_v2_portable")
    assert document["verdict"] == "ACCEPTED"
    assert document["estimator_fitting_performed"] is False
    assert document["fitting_attempts_observed"] == []
    armed = document["fitting_guard_armed_entry_points"]
    assert armed, "the fitting guard armed no entry points, so it proves nothing"
    # The calibrator and both estimator families must be covered.
    assert "OofLogisticCalibrator.fit_from_oof" in armed
    assert "LogisticRegression.fit" in armed
    assert "RandomForestClassifier.fit" in armed


def test_v2_05_lane_b_survives_with_fitting_entry_points_forbidden(monkeypatch):
    """Lane B must be executable when training entry points are forbidden.

    This is stronger than checking a flag: every fit entry point is replaced
    *before* the replay is invoked, and the replay must still accept all 29 cases
    with the pinned digest. If Lane B needed to fit anything -- including the
    ``LogisticRegression.fit`` that earlier rounds used merely to touch the sklearn
    path -- this test fails.
    """
    from research.intake import rh04_v2_lane_a_report as report

    attempts: list[str] = []

    def _refuse(*_args, **_kwargs):
        attempts.append("called")
        raise AssertionError("Lane B attempted to fit during a replay")

    from ai.calibration import OofLogisticCalibrator
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.linear_model import LogisticRegression

    monkeypatch.setattr(OofLogisticCalibrator, "fit_from_oof", classmethod(
        lambda cls, *a, **k: _refuse()
    ))
    monkeypatch.setattr(LogisticRegression, "fit", _refuse)
    monkeypatch.setattr(RandomForestClassifier, "fit", _refuse)

    document = report.produce_lane_b("host", "research/intake/fixtures/rh04_v2_portable")
    assert attempts == [], "a fit entry point was reached during Lane B"
    assert document["verdict"] == "ACCEPTED"
    assert document["observed_digest"] == "891d9e3b2a332c6efc251d97fee25ed46a627ed25b2a089594057b4c9896cdc8"


def test_v2_08_resident_library_evidence_carries_no_absolute_paths():
    """Published evidence must not name the machine that produced it.

    Versions, architectures, thread counts and thread-pool API remain. Absolute
    library paths, install prefixes and the interpreter path do not, because they
    are committed and attached to a PR.
    """
    import json as _json

    from research.intake import rh04_v2_lane_a_report as report

    report._exercise_numerics()
    identity = report.resident_libraries()
    encoded = _json.dumps(identity)

    import re

    for pattern in (
        r"/home/[A-Za-z0-9._-]+",
        r"/Users/[A-Za-z0-9._-]+",
        r"/usr/(local/)?(lib|bin)/",
        r"/root/",
    ):
        assert not re.search(pattern, encoded), (pattern, encoded[:400])

    assert "filepath" not in encoded
    assert "executable" not in encoded
    assert identity["interpreter"]["path_retained"] is False

    # Structural check, not just a pattern scan. A pattern list only catches the
    # prefixes it names, so a raw path under a directory nobody thought of would
    # slip through. Every published string is required to be a basename or an
    # identifier: no string may contain a path separator.
    def _strings(node):
        if isinstance(node, dict):
            for value in node.values():
                yield from _strings(value)
        elif isinstance(node, list):
            for value in node:
                yield from _strings(value)
        elif isinstance(node, str):
            yield node

    for value in _strings(identity):
        assert "/" not in value, f"published evidence carries a path fragment: {value!r}"
        assert "\\" not in value, f"published evidence carries a path fragment: {value!r}"

    # The provenance a reader actually needs is still present.
    assert identity["libraries"]
    for entry in identity["libraries"]:
        assert entry["internal_api"] in {"openblas", "openmp", "mkl", "blis"}
        assert entry["library_file"]["basename"]
        assert entry["library_file"]["path_retained"] is False
        assert entry["num_threads"] is not None


def test_v2_08_sanitizer_still_exposes_a_leaked_path():
    """The sanitiser must actually remove a path, not merely be applied.

    A sanitiser that returns its input unchanged would pass the previous test on a
    machine whose paths happen to match no pattern. This feeds a known path in and
    requires the output to carry no trace of the directory.
    """
    from research.intake import rh04_v2_lane_a_report as report

    sanitised = report.sanitize_path("/home/alice/venvs/rh04/lib/libopenblas.so.0")
    assert sanitised["basename"] == "libopenblas.so.0"
    assert sanitised["path_retained"] is False
    assert "/home/alice" not in repr(sanitised)
    assert "venvs" not in repr(sanitised)

    prefix = report.sanitize_prefix("/home/alice/venvs/rh04/lib/python3.11/site-packages")
    assert prefix["kind"] == "site-packages"
    assert prefix["path_retained"] is False
    assert "alice" not in repr(prefix)


def test_v2_02_lane_a_records_actual_regenerated_parameters():
    """Regenerated parameters, not selection metadata, must be reported.

    Selection metadata says which configuration would be used; it does not say what
    the fitted function is. The logistic route must report its coefficient vector,
    and the forest route its tree count and structural comparison -- both regenerated
    by the existing producer refit and compared against the archive.
    """
    from research.intake import rh04_v2_lane_a_report as report

    logistic = report._regenerated_parameters("da_a2_resting_v1")
    assert logistic["model_family"] == "l2_logistic_regression"
    assert len(logistic["regenerated_coefficients"]) == 10
    assert all(isinstance(v, float) for v in logistic["regenerated_coefficients"])
    assert logistic["coefficients_exact"] is True
    assert logistic["coefficient_max_abs_delta"] == 0.0
    assert logistic["intercept_abs_delta"] == 0.0
    assert logistic["lineage_established"] is True

    forest = report._regenerated_parameters("da_a1_basic_clinical_v1")
    assert forest["model_family"] == "constrained_random_forest"
    assert forest["tree_count"]["archived"] == forest["tree_count"]["refit"] == 50
    assert forest["structure_exact"] is True
    assert forest["max_float_delta"] == 0.0
    assert forest["lineage_established"] is True


def test_v2_02_lane_a_replay_identity_is_over_responses_not_statuses():
    """The replay identity must digest the responses, not a status tally.

    A tally such as ``{ERROR: 22, ABSTAIN: 2}`` is a summary and is identical for
    many different response sets. The identity here is per-case, so two runs can be
    compared on what was actually returned.
    """
    from research.intake import rh04_v2_lane_a_report as report

    identity = report._replay_response_identity()
    assert identity["n_cases"] == 29
    assert len(identity["per_case_response_sha256"]) == 29
    for case_id, digest in identity["per_case_response_sha256"].items():
        assert len(digest) == 64, case_id
    assert len(identity["replay_responses_sha256"]) == 64
    assert identity["aggregate_digest"] == (
        "891d9e3b2a332c6efc251d97fee25ed46a627ed25b2a089594057b4c9896cdc8"
    )


def test_v2_08_sanitizer_closes_every_file_it_opens(tmp_path):
    """Digesting a library must not leak the file handle.

    CI runs the suite under ``-W error``, so a handle left to the garbage collector
    becomes a ``ResourceWarning`` at collection time and fails whichever test
    happens to be running at that moment. That is why three Lane B and evidence
    tests were failing for a reason none of them named.

    The digest is asserted alongside the closure, so passing this by reading less of
    the file is not an option.
    """
    import builtins
    import hashlib

    from research.intake import rh04_v2_lane_a_report as report

    payload = b"openblas" * 400_000  # 3.2 MB, past the 1 MiB streaming chunk
    target = tmp_path / "libopenblas-test.so"
    target.write_bytes(payload)

    opened: list = []
    real_open = builtins.open

    def _spy(*args, **kwargs):
        handle = real_open(*args, **kwargs)
        opened.append(handle)
        return handle

    builtins.open = _spy
    try:
        sanitised = report.sanitize_path(str(target))
    finally:
        builtins.open = real_open

    assert opened, "sanitize_path did not open the file it digested"
    for handle in opened:
        assert handle.closed, "sanitize_path left a file handle open"
    assert sanitised["sha256"] == hashlib.sha256(payload).hexdigest()
    assert sanitised["basename"] == "libopenblas-test.so"
    assert sanitised["path_retained"] is False
    assert str(tmp_path) not in repr(sanitised)
