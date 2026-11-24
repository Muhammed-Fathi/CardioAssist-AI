"""Report Lane A evidence under a named resident dispatch class.

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

PROTOCOL_ID: Final[str] = "rh04-lane-a-dispatch-class-v1"

#: Requests the gate may ask for. Each is a real kernel family that OpenBLAS can
#: dispatch to on x86-64; the gate verifies it actually got what it asked for.
DISPATCH_CLASSES: Final[tuple[str, ...]] = (
    "prescott",
    "nehalem",
    "haswell",
    "sandybridge",
    "skylakex",
)

#: The request that leaves dispatch to the host. Recorded as its own class because
#: it is the only one that says what this machine would do unforced.
HOST_DISPATCH: Final[str] = "host"


def _resident(architecture: str) -> None:
    """Load a numerical library before reading resident kernel identity."""
    import numpy as np

    matrix = np.random.default_rng(0).normal(size=(256, 256))
    matrix @ matrix.T  # force dispatch resolution


def resident_report() -> dict[str, Any]:
    """Read the numerical libraries actually loaded in this process."""
    from threadpoolctl import threadpool_info

    entries = []
    for item in threadpool_info():
        entries.append(
            {
                "internal_api": item.get("internal_api"),
                "architecture": item.get("architecture"),
                "version": item.get("version"),
                "num_threads": item.get("num_threads"),
                "filepath": item.get("filepath"),
            }
        )
    import numpy
    import scipy
    import sklearn

    return {
        "libraries": entries,
        "python": sys.version.split()[0],
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


def produce(requested: str) -> dict[str, Any]:
    """Produce Lane A evidence and the resident dispatch identity for one class."""
    requested = requested.strip().lower()
    if requested not in DISPATCH_CLASSES and requested != HOST_DISPATCH:
        raise SystemExit(
            f"unknown dispatch class {requested!r}; "
            f"expected one of {DISPATCH_CLASSES + (HOST_DISPATCH,)}"
        )

    _resident(requested)
    identity = resident_report()
    architectures = [
        entry["architecture"] for entry in identity["libraries"] if entry["architecture"]
    ]
    if requested == HOST_DISPATCH:
        observed_class = architectures[0].lower() if architectures else "unknown"
    else:
        observed_class = architectures[0].lower() if architectures else "unknown"
        # Fail closed. A run whose requested class is not the resident class is not
        # evidence for that class; it must not be recorded under the request.
        if observed_class != requested:
            raise SystemExit(
                "dispatch request was not honoured: asked for "
                f"{requested!r}, resident architecture is {observed_class!r}. "
                "Recording this as evidence for the requested class would be false."
            )

    from research.intake import rh04_v2_lane_a_convergence as lane_a

    routes = {}
    for route_id in ("da_a1_basic_clinical_v1", "da_a2_resting_v1"):
        document = lane_a.produce_complete_evidence(route_id)
        routes[route_id] = {
            "evidence_sha256": document["evidence_sha256"],
            "any_failure": document["any_failure"],
            "components": {
                name: {
                    "n_observations": component.get(
                        "n_fits_observed", component.get("n_optimizations")
                    ),
                    "any_failure": component["any_failure"],
                    "classifications": component["classifications"],
                }
                for name, component in document["components"].items()
            },
        }
    return {
        "protocol_id": PROTOCOL_ID,
        "requested_dispatch_class": requested,
        "observed_dispatch_class": observed_class,
        "identity": identity,
        "routes": routes,
        "any_failure": any(route["any_failure"] for route in routes.values()),
    }


def main(argv: Sequence[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    if len(arguments) != 1:
        print(f"usage: python -m {__name__} <dispatch-class>", file=sys.stderr)
        return 2
    document = produce(arguments[0])
    print(json.dumps(document, indent=2, sort_keys=True))
    return 0 if not document["any_failure"] else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
