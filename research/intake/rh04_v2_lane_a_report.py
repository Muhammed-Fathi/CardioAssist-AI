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
from typing import Any, Final, Sequence

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


def _warm_numerics() -> None:
    """Load and exercise every numerical library before reading its identity.

    ``threadpool_info()`` before the first BLAS call reports the library but not
    the kernel actually chosen. Python's NumPy and SciPy ship *separate* OpenBLAS
    builds here, each with its own dispatch tables, so both must be exercised:
    a run that only multiplies NumPy matrices reports one architecture and misses
    the other entirely.
    """
    import numpy as np
    import scipy.linalg
    from sklearn.linear_model import LogisticRegression

    generator = np.random.default_rng(0)
    matrix = generator.normal(size=(192, 192))
    matrix @ matrix.T  # NumPy's OpenBLAS
    scipy.linalg.inv(matrix + np.eye(192))  # SciPy's separate OpenBLAS/LAPACK
    features = generator.normal(size=(48, 3))
    labels = (features[:, 0] > 0.0).astype(int)
    LogisticRegression(solver="lbfgs", max_iter=200).fit(features, labels)


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
                "filepath": item.get("filepath"),
                "prefix": item.get("prefix"),
            }
        )
    return {
        "libraries": entries,
        "n_entries": len(entries),
        "python": sys.version.split()[0],
        "executable": sys.executable,
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


def produce_lane_a(requested: str) -> dict[str, Any]:
    """Produce Lane A convergence evidence plus regeneration identity."""
    _warm_numerics()
    identity = resident_libraries()
    classes = dispatch_classes_of(identity)
    observed = classes["primary"]
    assert_dispatch_honoured(requested, classes)

    from research.intake import rh04_v2_lane_a_convergence as lane_a

    routes: dict[str, Any] = {}
    for route_id in ("da_a1_basic_clinical_v1", "da_a2_resting_v1"):
        convergence = lane_a.produce_complete_evidence(route_id)
        regeneration = _registered_regeneration(route_id)
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

    _warm_numerics()
    identity = resident_libraries()
    classes = dispatch_classes_of(identity)
    observed = classes["primary"]
    assert_dispatch_honoured(requested, classes)

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
