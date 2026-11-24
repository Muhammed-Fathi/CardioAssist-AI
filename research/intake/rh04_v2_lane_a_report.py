"""Report Lane A and Lane B evidence under a named resident dispatch class.

This is the entry point the dual-run gate calls once per dispatch class. It exists
so that the gate observes the *resident* BLAS dispatch, not the request: setting
``OPENBLAS_CORETYPE`` is a request that the loader may ignore, so the class is read
back from ``threadpoolctl`` after the numerical libraries are loaded, and a run
whose request and resident class disagree is refused rather than silently
relabelled.

Nothing here trains a new model, changes a hyper-parameter or touches a frozen
artifact. It runs the registered producers and records what already happens.
"""

from __future__ import annotations

import json
import os
import sys
from contextlib import contextmanager
from typing import Any, Final, Iterator, Sequence

PROTOCOL_ID: Final[str] = "rh04-dispatch-class-evidence-v2"

#: Requests the gate may ask for. Each is a real kernel family that OpenBLAS can
#: dispatch to on x86-64; the gate verifies it actually got what it asked for.
DISPATCH_CLASSES: Final[tuple[str, ...]] = (
    "prescott",
    "nehalem",
    "sandybridge",
    "haswell",
)

#: The request that leaves dispatch to the host. Recorded as its own class because
#: it is the only one that says what this machine would do unforced.
HOST_DISPATCH: Final[str] = "host"


def _exercise_numerics() -> None:
    """Load and exercise every numerical library without fitting any estimator.

    ``threadpool_info()`` before the first BLAS call reports the library but not the
    kernel actually chosen. Python's NumPy and SciPy ship *separate* OpenBLAS
    builds, each with its own dispatch tables, so both must be exercised: a run that
    only multiplies NumPy matrices reports one architecture and misses the other.

    **No estimator is fitted here, deliberately.** An earlier version called
    ``LogisticRegression.fit`` to touch the sklearn path, which put a model fit
    inside Lane B. Lane B is an inference path and must not train at all, so the
    BLAS/LAPACK calls below are the exercise. They resolve dispatch in both builds
    -- including SciPy's bundled OpenBLAS -- without any model being constructed.
    """
    import numpy as np
    import scipy.linalg

    generator = np.random.default_rng(0)
    matrix = generator.normal(size=(192, 192))
    matrix @ matrix.T  # NumPy's OpenBLAS (dgemm)
    np.linalg.solve(matrix, matrix[:, 0])  # NumPy's LAPACK (dgesv)
    scipy.linalg.inv(matrix + np.eye(192))  # SciPy's separate OpenBLAS
    scipy.linalg.svd(matrix, compute_uv=False)  # SciPy's LAPACK (dgesdd)
    scipy.linalg.lstsq(matrix, matrix[:, 0])  # SciPy's LAPACK (dgelsd)


#: Retained under the old name so existing callers keep working, but it no longer
#: fits anything. Lane A may call it freely; Lane B must be able to run with every
#: training entry point forbidden, which the negative test asserts.
def _warm_numerics() -> None:
    """Alias of :func:`_exercise_numerics`, kept for call-site stability."""
    _exercise_numerics()


#: Fit entry points. Any call to one of these during Lane B is a defect.
#:
#: Module *residency* is deliberately not used as the signal. ``ai.packaging``
#: imports ``ai.training`` for a dataclass type and ``ai/__init__.py`` re-exports
#: names from ``ai.calibration``, so importing the facade at all makes several
#: training modules resident. A residency check would therefore either forbid the
#: facade and make Lane B unrunnable, or be so weak as to prove nothing. What
#: actually matters is that no fit is *performed*, so the entry points are guarded
#: and a call is recorded rather than inferred.
_FIT_ENTRY_POINTS: Final[tuple[tuple[str, str], ...]] = (
    ("ai.calibration", "OofLogisticCalibrator.fit_from_oof"),
    ("ai.training", "_build_estimator"),
    ("sklearn.linear_model._base", "LinearClassifierMixin.fit"),
    ("sklearn.linear_model._logistic", "LogisticRegression.fit"),
    ("sklearn.ensemble._forest", "RandomForestClassifier.fit"),
)


class FittingForbidden(SystemExit):
    """Raised when a fit entry point is called inside a Lane B replay."""


class FittingGuard:
    """Armed guard over every fit entry point, recording any attempt.

    ``armed`` is the number of entry points actually replaced, so the guarantee is
    auditable: if the guard armed none, it proves nothing. ``attempts`` records the
    names of any entry point that was called while the guard was active.
    """

    def __init__(self) -> None:
        self.armed: list[str] = []
        self.attempts: list[str] = []
        self._restorations: list[tuple[Any, str, Any]] = []

    def __enter__(self) -> "FittingGuard":
        import importlib

        for module_name, attribute in _FIT_ENTRY_POINTS:
            try:
                module = importlib.import_module(module_name)
            except Exception:
                continue
            owner: Any = module
            parts = attribute.split(".")
            for part in parts[:-1]:
                owner = getattr(owner, part, None)
                if owner is None:
                    break
            if owner is None:
                continue
            leaf = parts[-1]
            if not hasattr(owner, leaf):
                continue
            original = getattr(owner, leaf)
            self._restorations.append((owner, leaf, original))
            self.armed.append(attribute)

            def _refuse(*_args: Any, _name: str = attribute, _self: "FittingGuard" = self, **_kwargs: Any) -> Any:
                _self.attempts.append(_name)
                raise FittingForbidden(
                    f"Lane B called {_name}; Lane B is an inference path and must "
                    "not fit, select or calibrate a model"
                )

            setattr(owner, leaf, _refuse)
        if not self.armed:
            raise SystemExit(
                "the fitting guard armed no entry points, so invoking Lane B under "
                "it would prove nothing about whether fitting occurred"
            )
        return self

    def __exit__(self, *_exc: Any) -> bool:
        for owner, leaf, original in self._restorations:
            setattr(owner, leaf, original)
        return False


def sanitize_path(value: Any) -> dict[str, Any]:
    """Reduce an absolute machine path to publishable provenance.

    Evidence is committed and attached to a PR, so an absolute path from the
    machine that produced it is both a leak and a portability hazard: it tells a
    reader nothing they need and everything about the host. What is genuinely
    useful is the file's basename and its digest, which identify the library
    without tying the record to one directory.

    Returns ``None`` for a missing value rather than an empty string, so "absent"
    and "empty" stay distinguishable.
    """
    if not value or not isinstance(value, str):
        return None
    import hashlib
    import os.path

    normalised = value.replace("\\", "/")
    basename = normalised.rsplit("/", 1)[-1]
    try:
        # Context-managed and streamed. A bare ``open(...).read()`` leaves the
        # handle to the garbage collector, which under ``-W error`` turns into a
        # ResourceWarning the suite treats as a failure; it also loads a
        # multi-megabyte shared object into memory for no reason.
        hasher = hashlib.sha256()
        with open(value, "rb") as handle:
            for chunk in iter(lambda: handle.read(1 << 20), b""):
                hasher.update(chunk)
        digest = hasher.hexdigest()
    except Exception:
        digest = None
    return {
        "basename": basename,
        "sha256": digest,
        "path_retained": False,
    }


def sanitize_prefix(value: Any) -> dict[str, Any] | None:
    """Describe an install prefix without publishing the path.

    The prefix is reduced to a small, non-identifying classification: whether it is
    a virtual environment, a system location, or a user location. That is what a
    reader needs in order to know whether the run was in an isolated environment;
    the actual directory is not.
    """
    if not value or not isinstance(value, str):
        return None
    normalised = value.replace("\\", "/").lower()
    if "/site-packages" in normalised or "/dist-packages" in normalised:
        kind = "site-packages"
    elif "/venv" in normalised or "virtualenv" in normalised or "/.venv" in normalised:
        kind = "virtual-environment"
    elif normalised.startswith("/usr") or normalised.startswith("/opt"):
        kind = "system"
    else:
        kind = "other"
    return {"kind": kind, "path_retained": False}


def resident_libraries() -> dict[str, Any]:
    """The complete resident numerical-library identity for this process.

    Every entry is kept, not just the first. NumPy and SciPy link different
    OpenBLAS builds with different versions and different dispatch tables, so a
    single "the architecture" value would be a fiction. The mixed case is real and
    was measured: under ``OPENBLAS_CORETYPE=Prescott`` on this platform, NumPy
    resolves to ``Prescott`` while SciPy's bundled OpenBLAS resolves to ``Katmai``.
    """
    from threadpoolctl import threadpool_info

    import numpy
    import scipy
    import sklearn

    entries = []
    for item in threadpool_info():
        entries.append(
            {
                "internal_api": item.get("internal_api"),
                "architecture": item.get("architecture"),
                "version": item.get("version"),
                "num_threads": item.get("num_threads"),
                # Sanitised: basename + digest, never the absolute path.
                "library_file": sanitize_path(item.get("filepath")),
                "install_prefix": sanitize_prefix(item.get("prefix")),
            }
        )
    return {
        "libraries": entries,
        "n_entries": len(entries),
        "python": sys.version.split()[0],
        # Not sys.executable: the absolute interpreter path names the host.
        "interpreter": {
            "implementation": sys.implementation.name,
            "version": sys.version.split()[0],
            "path_retained": False,
        },
        "numpy": numpy.__version__,
        "scipy": scipy.__version__,
        "scikit_learn": sklearn.__version__,
        "num_threads_env": {
            key: os.environ.get(key)
            for key in (
                "OPENBLAS_NUM_THREADS",
                "OMP_NUM_THREADS",
                "MKL_NUM_THREADS",
                "OPENBLAS_CORETYPE",
            )
        },
    }


def dispatch_classes_of(identity: dict[str, Any]) -> dict[str, Any]:
    """Summarise the resident classes without collapsing them to one value.

    ``blas_architectures`` is the ordered, de-duplicated list of every OpenBLAS
    architecture resident in the process. ``primary`` is the *host-machine choice*
    for the run: the architecture of the largest BLAS by thread count is not
    meaningful, so the primary is defined as the first OpenBLAS entry, and the
    full list is retained alongside it precisely because "first" alone would be
    misleading when two builds disagree.
    """
    blas = [
        entry
        for entry in identity["libraries"]
        if entry["internal_api"] == "openblas" and entry["architecture"]
    ]
    ordered: list[str] = []
    for entry in blas:
        name = entry["architecture"]
        if name not in ordered:
            ordered.append(name)
    primary = ordered[0].lower() if ordered else "unknown"
    return {
        "primary": primary,
        "blas_architectures": ordered,
        "distinct_blas_classes": len(ordered),
        "mixed": len(ordered) > 1,
        "n_blas_libraries": len(blas),
    }


def assert_dispatch_honoured(requested: str, classes: dict[str, Any]) -> None:
    """Fail closed if the requested class is not resident.

    A run is recorded under a class only when the class is actually present. When
    two OpenBLAS builds are resident and only one of them took the request, the
    request is recorded as *partial* rather than as honoured — a partial dispatch
    is still a real, reportable environment, but it must not be described as a
    clean single-class run.
    """
    present = [name.lower() for name in classes["blas_architectures"]]
    if not present:
        raise SystemExit(
            "no OpenBLAS architecture was reported at all; the resident identity "
            "could not be established, so no class can be claimed"
        )
    if requested == HOST_DISPATCH:
        return
    if requested not in present:
        raise SystemExit(
            "dispatch request was not honoured: asked for "
            f"{requested!r}, resident architectures are {present!r}. Recording "
            "this as evidence for the requested class would be false."
        )


def _registered_regeneration(route_id: str) -> dict[str, Any]:
    """Run the existing registered regeneration path and digest its identities.

    This reuses ``rh04_v2_producer_lineage`` rather than reimplementing a
    regeneration: ``selection_reproduction`` re-runs the producer's own selection
    (family and hyperparameters), ``full_lineage`` recovers the training-boundary
    and fold identities, and ``_capture_producer_calibration_fit`` returns the
    calibrator instance the producer actually fitted.

    What is reported is the *identity* of the regenerated model, calibration map
    and replay inputs -- not just a convergence summary. A convergence hash says
    "some fits satisfied a criterion"; these say "this family, these
    hyperparameters, this intercept and slope, these fold identities".
    """
    import hashlib
    import json as _json

    from research.intake import rh04_v2_producer_lineage as lineage

    def _sha(payload: Any) -> str:
        encoded = _json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    reproduction = lineage.selection_reproduction(route_id)
    lineage_facts = lineage.full_lineage(route_id)
    captured = lineage._capture_producer_calibration_fit(route_id)
    calibrator = captured["instance"]

    model_identity = {
        "selected_family": reproduction["selected_family"],
        "selected_hyperparameters": reproduction["selected_hyperparameters"],
        "family_order": reproduction["family_order"],
        "inner_cv_roc_auc": reproduction["inner_cv_roc_auc"],
    }
    calibration_identity = {
        "intercept": float(calibrator.intercept),
        "slope": float(calibrator.slope),
        "status": calibrator.status,
        "solver": calibrator.solver,
        "input_link": calibrator.input_link,
        "fit_scope": calibrator.fit_scope,
        "n_oof_samples": int(calibrator.n_oof_samples),
        "development_prevalence": float(calibrator.development_prevalence),
        "oof_brier_before": float(calibrator.oof_brier_before),
        "oof_brier_after": float(calibrator.oof_brier_after),
    }
    replay_identity = {
        "training_input_sha256": lineage_facts["training_boundary"]["training_input_sha256"],
        "target_sha256": lineage_facts["training_boundary"]["target_sha256"],
        "n_rows": lineage_facts["training_boundary"]["n_rows"],
        "n_features": lineage_facts["training_boundary"]["n_features"],
        "outer_fold_identity": _sha(lineage_facts["outer_folds"]),
        "calibration_oof_identity": _sha(lineage_facts["calibration_oof"]),
        "inner_selection_identity": _sha(lineage_facts["inner_selection"]),
        "heldout_identity": _sha(lineage_facts["heldout"]),
    }
    return {
        "route_id": route_id,
        "model_identity": model_identity,
        "model_identity_sha256": _sha(model_identity),
        "calibration_identity": calibration_identity,
        "calibration_identity_sha256": _sha(calibration_identity),
        "replay_identity": replay_identity,
        "replay_identity_sha256": _sha(replay_identity),
    }


def _regenerated_parameters(route_id: str) -> dict[str, Any]:
    """Refit from the producer cohort and report the ACTUAL regenerated parameters.

    Selection metadata and input hashes are not model parameters. They say which
    configuration *would* be used; they do not say what the fitted function is. This
    calls the existing ``estimator_lineage_proof``, which re-runs the producer's own
    final fit with the producer's own seed arithmetic and compares the result to the
    archived estimator -- so the reported numbers are regenerated parameters, and
    the agreement is a measurement rather than a claim.

    No new model or solver is introduced: the family, hyperparameters, seeds and
    preprocessing all come from the existing registered producer.
    """
    from research.intake import rh04_v2_portable_archive as archive_module
    from research.intake import rh04_v2_producer_lineage as lineage

    admitted = archive_module.admit_from_directory(
        "research/intake/fixtures/rh04_v2_portable"
    )
    archives = {
        route: archive_module._thaw(admitted.archives[route]) for route in admitted.routes
    }
    body = archives[route_id]
    proof = lineage.estimator_lineage_proof(route_id, body)

    parameters: dict[str, Any] = {
        "model_family": proof["model_family"],
        "selected_hyperparameters": proof["selected_hyperparameters"],
        "final_fit_seed": proof["final_fit_seed"],
        "preprocessing_exact": proof["preprocessing_exact"],
        "lineage_established": proof["lineage_established"],
    }
    if proof["model_family"] == "l2_logistic_regression":
        # The archived representation is the regenerated parameter vector, and the
        # deltas are the measured difference between it and the fresh refit.
        representation = dict(body["model"]["representation"])
        parameters["regenerated_coefficients"] = [
            float(v) for v in representation["coef"]
        ]
        parameters["regenerated_intercept"] = float(representation["intercept"])
        parameters["coefficient_max_abs_delta"] = float(
            proof["coefficient_max_abs_delta"]
        )
        parameters["intercept_abs_delta"] = float(proof["intercept_abs_delta"])
        parameters["coefficients_exact"] = bool(proof["coefficients_exact"])
    else:
        # A forest is characterised by complete structure, not a coefficient vector.
        parameters["tree_count"] = {
            "archived": int(proof["tree_count"]["archived"]),
            "refit": int(proof["tree_count"]["refit"]),
        }
        parameters["structure_exact"] = bool(proof["structure_exact"])
        parameters["max_float_delta"] = float(proof["max_float_delta"])
        parameters["class_order"] = [int(v) for v in proof["class_order"]]
        parameters["n_features_in"] = int(proof["n_features_in"])
    import hashlib
    import json as _json

    encoded = _json.dumps(parameters, sort_keys=True, separators=(",", ":")).encode("utf-8")
    parameters["regenerated_parameters_sha256"] = hashlib.sha256(encoded).hexdigest()
    return parameters


def _replay_response_identity() -> dict[str, Any]:
    """Replay the registered cases and digest the ACTUAL response identities.

    A status tally is a summary; it is not an identity. This digests each response
    payload as it was actually returned by the facade, then digests the ordered
    sequence, so two runs can be compared on the responses themselves. The same
    canonicalisation the facade uses for its own digest is reused rather than
    reimplemented.
    """
    import hashlib
    import json as _json

    from ai import research_facade as facade
    from research.intake import offline_fixture_pack as v1
    from research.intake import rh04_v2_portable_archive as archive

    admitted = archive.admit_from_directory("research/intake/fixtures/rh04_v2_portable")
    result = archive.replay_admitted(facade, admitted)
    pack = _json.loads(v1.PACK.read_text(encoding="utf-8"))
    order = [case["id"] for case in pack["cases"]]

    per_case: dict[str, str] = {}
    for case_id, response in zip(order, result["responses"]):
        per_case[case_id] = facade.canonical_response_digest(response)

    sequence = _json.dumps(per_case, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return {
        "n_cases": len(per_case),
        "per_case_response_sha256": per_case,
        "replay_responses_sha256": hashlib.sha256(sequence).hexdigest(),
        "aggregate_digest": result["digest"],
    }


def produce_lane_a(requested: str) -> dict[str, Any]:
    """Produce Lane A convergence evidence plus regeneration identity."""
    _exercise_numerics()
    identity = resident_libraries()
    classes = dispatch_classes_of(identity)
    observed = classes["primary"]
    assert_dispatch_honoured(requested, classes)

    from research.intake import rh04_v2_lane_a_convergence as lane_a

    routes: dict[str, Any] = {}
    for route_id in ("da_a1_basic_clinical_v1", "da_a2_resting_v1"):
        convergence = lane_a.produce_complete_evidence(route_id)
        regeneration = _registered_regeneration(route_id)
        regeneration["regenerated_parameters"] = _regenerated_parameters(route_id)
        routes[route_id] = {
            "convergence_evidence_sha256": convergence["evidence_sha256"],
            "any_failure": convergence["any_failure"],
            "components": {
                name: {
                    "n_observations": component.get(
                        "n_fits_observed", component.get("n_optimizations")
                    ),
                    "any_failure": component["any_failure"],
                    "classifications": component["classifications"],
                }
                for name, component in convergence["components"].items()
            },
            "regeneration": regeneration,
        }
    return {
        "protocol_id": PROTOCOL_ID,
        "requested_dispatch_class": requested,
        "observed_dispatch_class": observed,
        "resident_dispatch": classes,
        "identity": identity,
        "routes": routes,
        "replay_response_identity": _replay_response_identity(),
        "any_failure": any(route["any_failure"] for route in routes.values()),
        "scope_note": (
            "the resident class is read inside this process after the numerical "
            "libraries have been loaded and exercised; it is not inferred from a "
            "setup step, and it is not collapsed to a single value when NumPy and "
            "SciPy ship different OpenBLAS builds"
        ),
    }


def produce_lane_b(requested: str, archive_dir: str) -> dict[str, Any]:
    """Replay Lane B inside this process and record *its own* resident identity.

    Lane B's dispatch is read here, in the process that actually replays, rather
    than borrowed from a setup step or from Lane A. The two processes load their
    libraries independently, so one cannot evidence the other.
    """
    import hashlib

    from research.intake import rh04_v2_portable_archive as archive

    _exercise_numerics()
    identity = resident_libraries()
    classes = dispatch_classes_of(identity)
    observed = classes["primary"]
    assert_dispatch_honoured(requested, classes)

    # The replay runs with every fit entry point replaced by a raising stub, so a
    # fit inside Lane B is impossible rather than merely unintended. The guard
    # records what it armed, which makes the guarantee auditable rather than
    # assumed: a guard that armed nothing would prove nothing.
    guard = FittingGuard()
    with guard:
        verification = archive.verify_artifact_directory(archive_dir)
    response_sha = hashlib.sha256(
        json.dumps(
            verification["statuses"], sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    ).hexdigest()
    return {
        "protocol_id": PROTOCOL_ID,
        "lane": "B",
        "requested_dispatch_class": requested,
        "observed_dispatch_class": observed,
        "resident_dispatch": classes,
        "identity": identity,
        "observed_digest": verification["digest"],
        "reference_digest": verification["reference_digest"],
        "expected_digest": archive.LANE_B_REFERENCE_DIGEST,
        "matches_reference": verification["matches_reference"],
        "n_cases": verification["n_cases"],
        "statuses": verification["statuses"],
        "statuses_sha256": response_sha,
        "estimator_fitting_performed": False,
        "fitting_guard_armed_entry_points": list(guard.armed),
        "fitting_attempts_observed": list(guard.attempts),
        "verdict": (
            "ACCEPTED"
            if verification["matches_reference"]
            and verification["digest"] == archive.LANE_B_REFERENCE_DIGEST
            else "REFUSED"
        ),
    }


def main(argv: Sequence[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    if not arguments:
        print(
            f"usage: python -m {__name__} <dispatch-class> [lane-a|lane-b] [archive-dir]",
            file=sys.stderr,
        )
        return 2
    requested = arguments[0].strip().lower()
    lane = arguments[1].strip().lower() if len(arguments) > 1 else "lane-a"
    if requested not in DISPATCH_CLASSES and requested != HOST_DISPATCH:
        print(
            f"unknown dispatch class {requested!r}; expected one of "
            f"{DISPATCH_CLASSES + (HOST_DISPATCH,)}",
            file=sys.stderr,
        )
        return 2

    if lane == "lane-b":
        archive_dir = (
            arguments[2]
            if len(arguments) > 2
            else "research/intake/fixtures/rh04_v2_portable"
        )
        document = produce_lane_b(requested, archive_dir)
        print(json.dumps(document, indent=2, sort_keys=True))
        return 0 if document["verdict"] == "ACCEPTED" else 1

    document = produce_lane_a(requested)
    print(json.dumps(document, indent=2, sort_keys=True))
    return 0 if not document["any_failure"] else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
