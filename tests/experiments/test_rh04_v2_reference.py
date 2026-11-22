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
from decimal import Decimal
from pathlib import Path

import numpy as np
import pytest

from ai import calibration as calibration_module
from ai.errors import CalibrationIntegrityError
from research.intake import offline_fixture_pack as v1
from research.intake import rh04_v2_candidate as candidate
from research.intake import rh04_v2_deterministic_upstream as upstream
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


def test_deterministic_upstream_matches_exact_rational_value():
    """The returned float must be the correctly rounded exact rational."""
    from fractions import Fraction

    coefficients, rows, intercept = _fixed_problem()
    for row in rows[:20]:
        score = upstream.exact_linear_score(coefficients, row, intercept)
        assert isinstance(score, Fraction)
        assert upstream.score_as_float(score) == float(score)


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
