"""RH-04 calibration dispatch-stability regression tests.

Background
----------
The frozen 29-case Golden Replay (``da_a1_basic_clinical_v1``) intermittently
failed on CI with a one-ULP drift in ``calibrated_log_odds`` (absolute delta
4.441e-16 / 1 ULP).  Empirically the drift entered through the
L-BFGS-B calibration fit in ``ai.calibration.OofLogisticCalibrator.fit_from_oof``,
which dispatches ``ddot_``/``daxpy_``/``dcopy_`` to OpenBLAS kernels selected
by the host's default dynamic-arch dispatch.  The frozen golden coefficients and
``calibrated_log_odds`` match the golden-generation host's (SkylakeX) dispatch,
so other hosts produce ~2 ULP-different intercept/slope and ~1 ULP-different
``calibrated_log_odds``.  OOF probabilities, cohort selection, model family,
preprocessor and SHAP are all bit-identical across dispatches.

The fix is the workflow pin ``OPENBLAS_CORETYPE=SkylakeX`` in the
``synthetic-runner-tests`` and ``rh04-fixture-diagnostic`` jobs (documented as
an uncommitted workflow patch in this PR; see docs/rh04-workflow-pin.md).  These
tests guard the structural calibration-consistency invariant so the invariant
cannot drift silently:

* the production bundle build reproduces the frozen intercept/slope,
* the golden case's calibrated_log_odds matches the frozen response exactly,
* the facade prediction-consistency contract (SHAP alignment, additive scale,
  probability sanity) holds for the golden case,
* the workflow environment pin stays in place,
* the frozen pack digest and case count are unchanged.

Per the frozen-golden rule these tests do NOT regenerate, weaken or relax the
fixture, its digest, the comparator or any tolerance.  They use the synthetic
-only path only and never patient data.
"""
from __future__ import annotations

import json
from pathlib import Path
import re

import pytest

from ai.calibration import OofLogisticCalibrator, safe_clipped_logit
from ai.filesystem_security import ensure_private_directory
from ai.packaging import CALIBRATION_FILENAME, get_or_create_local_signing_key
from ai.research_facade import (
    LocalSyntheticBundleSource,
    ResearchFacadeStatus,
    run_offline_research_inference_from_document,
)
from ai.uci412_research import (
    Uci412ResearchModelConfig,
    build_uci412_synthetic_research_model,
)
from research.intake import offline_fixture_pack as fixtures

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "experiment-runner-ci.yml"

# Frozen golden calibration coefficients for the da_a1_basic_clinical_v1
# fast fixture (per the frozen 29-case pack; recorded here only to assert the
# calibration fit is unchanged by this fix). These match the frozen response
# calibrated_log_odds / calibrated_research_score and the default golden
# build under the pinned SkylakeX dispatch.
FROZEN_CALIBRATION_INTERCEPT = -0.8264874886346654
FROZEN_CALIBRATION_SLOPE = 1.6547968324340276
FROZEN_CALIBRATED_LOG_ODDS = 2.6971396718292335
FROZEN_CALIBRATED_RESEARCH_SCORE = 0.9368576513885218
FROZEN_RAW_LOG_ODDS = 2.1293412528962987
FROZEN_RAW_MODEL_SCORE = 0.8937224550197632


@pytest.fixture(scope="module")
def _bundle(tmp_path_factory):
    work_root = ensure_private_directory(
        tmp_path_factory.mktemp("rh04_calibration_dispatch")
    )
    return build_uci412_synthetic_research_model(
        Uci412ResearchModelConfig.fast(package_bundle=True, work_root=work_root)
    )


def _read_calibration(bundle) -> OofLogisticCalibrator:
    payload = json.loads(
        (bundle.bundle_dir / CALIBRATION_FILENAME).read_text(encoding="utf-8")
    )
    return OofLogisticCalibrator.from_json_dict(payload)


def _golden_source(bundle) -> LocalSyntheticBundleSource:
    return LocalSyntheticBundleSource(
        bundle.bundle_dir,
        bundle.trusted_root,
        get_or_create_local_signing_key(bundle.signing_key_path),
    )


def _golden_request(pack: dict):
    case = next(c for c in pack["cases"] if c["id"] == "da_a1_basic_clinical_v1")
    return fixtures.materialize(pack["requests"][fixtures.BASIC], case["edits"])


def test_calibration_fit_reproduces_frozen_golden_coefficients(_bundle):
    """The production calibration fit preserves the frozen golden intercept/slope."""
    cal = _read_calibration(_bundle)
    assert cal.intercept == FROZEN_CALIBRATION_INTERCEPT
    assert cal.slope == FROZEN_CALIBRATION_SLOPE
    assert cal.input_link == "clipped_logit_of_raw_probability"
    assert cal.fit_scope == "FULL_DEVELOPMENT_OOF_FINAL"
    assert cal.status == "FITTED_OOF_MONOTONE_LOGISTIC"
    assert cal.development_prevalence > 0.0
    assert cal.n_oof_samples > 0
    assert cal.oof_brier_before >= cal.oof_brier_after


def test_calibration_affine_map_is_consistent_with_frozen_response(_bundle):
    """Calibrated log-odds must equal intercept + slope * clipped_logit(raw_score)."""
    cal = _read_calibration(_bundle)
    raw_logit_input = safe_clipped_logit(FROZEN_RAW_MODEL_SCORE)
    calibrated = cal.transform_log_odds(raw_logit_input)
    assert float(calibrated) == FROZEN_CALIBRATED_LOG_ODDS
    from scipy.special import expit
    assert float(expit(FROZEN_CALIBRATED_LOG_ODDS)) == FROZEN_CALIBRATED_RESEARCH_SCORE


def test_golden_case_matches_frozen_response_exactly(_bundle):
    """End-to-end: the facade replays the frozen golden exactly."""
    pack = json.loads(fixtures.PACK.read_text(encoding="utf-8"))
    request = _golden_request(pack)
    response = run_offline_research_inference_from_document(
        request, model_source=_golden_source(_bundle)
    )
    assert response.status is ResearchFacadeStatus.SYNTHETIC_RESULT
    (outcome,) = response.outcomes
    assert outcome.status is ResearchFacadeStatus.SYNTHETIC_RESULT
    assert outcome.score is not None
    assert outcome.score.calibrated_log_odds == FROZEN_CALIBRATED_LOG_ODDS
    assert outcome.score.calibrated_research_score == FROZEN_CALIBRATED_RESEARCH_SCORE
    assert outcome.score.raw_model_log_odds == FROZEN_RAW_LOG_ODDS
    assert outcome.score.raw_model_score == FROZEN_RAW_MODEL_SCORE
    assert outcome.score.exploratory_threshold == 0.5
    assert outcome.score.exploratory_above_threshold is True
    assert outcome.score.threshold_clinically_validated is False
    assert outcome.score.clinical_probability_claim is False


def test_golden_case_shap_alignment_contract_holds(_bundle):
    """SHAP alignment: the golden outcome passes the facade consistency check.

    The facade only returns ``SYNTHETIC_RESULT`` when ``_assert_prediction_consistency``
    passes (SHAP sum check, scale/additivity, calibrated probability sanity).
    A failure raises a refusal and the outcome would not be SYNTHETIC_RESULT.
    """
    pack = json.loads(fixtures.PACK.read_text(encoding="utf-8"))
    request = _golden_request(pack)
    response = run_offline_research_inference_from_document(
        request, model_source=_golden_source(_bundle)
    )
    assert response.status is ResearchFacadeStatus.SYNTHETIC_RESULT
    (outcome,) = response.outcomes
    assert outcome.shap is not None
    assert outcome.error is None


def test_workflow_pins_openblas_core_type_and_threads():
    """Fail closed if either CI job loses its pinned, hardware-gated BLAS kernel.

    This test must NOT skip when the workflow is missing or incomplete.  The
    job-level settings matter: a stray string elsewhere in a YAML file is not
    sufficient proof of a reproducibility contract.
    """
    text = WORKFLOW_PATH.read_text(encoding="utf-8")
    for job in ("synthetic-runner-tests", "rh04-fixture-diagnostic"):
        match = re.search(
            rf"(?ms)^  {re.escape(job)}:\n(.*?)(?=^  [a-zA-Z][a-zA-Z0-9_-]*:\n|\Z)",
            text,
        )
        assert match is not None, f"Missing RH-04 CI job: {job}"
        section = match.group(1)
        env = re.search(r"(?ms)^    env:\n((?:^      [A-Z0-9_]+:.*\n)+)", section)
        assert env is not None, f"Missing job-level numeric environment: {job}"
        values = dict(
            re.findall(r"(?m)^      ([A-Z0-9_]+): '([^']+)'$", env.group(1))
        )
        assert values.get("OPENBLAS_CORETYPE") == "SkylakeX", job
        for var in (
            "OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS",
            "BLIS_NUM_THREADS", "NUMEXPR_NUM_THREADS", "VECLIB_MAXIMUM_THREADS",
        ):
            assert values.get(var) == "1", f"{job}: {var}"
        assert "Verify hardware supports pinned SkylakeX dispatch" in section
        assert "avx512f avx512dq avx512bw avx512vl" in section
        assert "OpenBLAS kernel is not the pinned SkylakeX architecture" in section


def test_frozen_pack_digest_and_case_count_unchanged():
    """Frozen fixture digest and 29-case count are unchanged by this fix.

    This is a hard roll-back guard: the frozen pack and its digest must remain
    exactly as they are. If this test fails, the fix is invalid — do not
    regenerate, weaken or relax the pack.
    """
    pack = json.loads(fixtures.PACK.read_text(encoding="utf-8"))
    from ai.research_facade import canonical_response_digest

    assert canonical_response_digest(pack) == fixtures.PACK_SHA256
    assert len(pack["cases"]) == 29
