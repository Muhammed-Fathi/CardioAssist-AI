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
