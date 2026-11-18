"""Compare a saved JSON report to a trusted run of the fixed synthetic demo.

Never trust the peer to choose the schema, tolerance, output paths, or labels
in a diff. No comparison code opens a bundle or follows a reference in JSON.
Exact file bytes, canonical JSON, artifact bytes and measured fixture behavior
are four different questions. This is not a model-equivalence test.
"""

from __future__ import annotations

from decimal import Decimal
import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat
from typing import Any

from ai.research_demo import DEMO_ID, report_digest
from ai.research_facade import canonical_response_digest as digest

MAX_BYTES = 512 * 1024
ABS_TOL, REL_TOL = 1e-12, 1e-9


class ComparisonError(ValueError):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def report_bytes(document: dict) -> bytes:
    """The evidence writer's wire format, including its terminating LF."""
    return (
        json.dumps(document, indent=2, sort_keys=True, ensure_ascii=True, allow_nan=False) + "\n"
    ).encode("ascii")


def read_report(path: Path) -> bytes:
    # Bounded regular file only; O_NONBLOCK prevents a FIFO substitution from
    # hanging open on POSIX. All later operations use this one byte snapshot.
    info = path.lstat()
    if (
        path.suffix.lower() != ".json"
        or not stat.S_ISREG(info.st_mode)
        or getattr(info, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT
    ):
        raise ComparisonError("expected_regular_report_json")
    flags = (
        os.O_RDONLY
        | getattr(os, "O_NOFOLLOW", 0)
        | getattr(os, "O_NONBLOCK", 0)
        | getattr(os, "O_BINARY", 0)
    )
    with os.fdopen(os.open(path, flags), "rb") as stream:
        if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
            raise ComparisonError("expected_regular_report_json")
        data = stream.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise ComparisonError("report_size_limit")
    return data


def _parse(data: bytes) -> dict:
    def obj(pairs: list) -> dict:
        result = dict(pairs)
        if len(result) != len(pairs):
            raise ComparisonError("duplicate_report_key")
        return result

    def finite(token: str) -> float:
        if len(token) > 64:
            raise ComparisonError("report_number_limit")
        value = float(token)
        if not math.isfinite(value):
            raise ComparisonError("nonfinite_report_number")
        # Reports originate as Python binary64 -> shortest-roundtrip JSON.
        # Refuse higher-precision or underflowed peer numbers rather than
        # silently discarding a numerical difference during JSON parsing.
        if Decimal(token) != Decimal(repr(value)):
            raise ComparisonError("not_roundtrip_binary64")
        return value

    def integer(token: str) -> int:
        if len(token) > 20:
            raise ComparisonError("report_integer_limit")
        return int(token)

    if len(data) > MAX_BYTES:
        raise ComparisonError("report_size_limit")
    try:
        value = json.loads(
            data,
            object_pairs_hook=obj,
            parse_float=finite,
            parse_constant=finite,
            parse_int=integer,
        )
    except (UnicodeError, json.JSONDecodeError, RecursionError):
        raise ComparisonError("invalid_report_json") from None
    if not isinstance(value, dict):
        raise ComparisonError("unknown_report_format")
    return value


# Only measured, continuous outputs get a tolerance. In particular a seed,
# threshold, feature order, criterion outcome, scale, refusal, or governance
# flag can NEVER pass by proximity (even though bool subclasses int).
_SCORE = r"(?:raw_model_score|raw_model_log_odds|calibrated_research_score|calibrated_log_odds)"
_RECORD = r"/inference/records/\d+/"
_LIME = _RECORD + r"lime_explanation/explanation/"
_MEASUREMENTS = re.compile(
    "|".join(
        (
            r"/report/stage_results/3/detail/" + _SCORE,
            _RECORD + "score/" + _SCORE,
            r"/inference/capabilities/calibration/oof_brier_(?:before|after)",
            _RECORD + r"shap_explanation/max_abs_discrepancy",
            _RECORD
            + r"fold_dispersion/fold_(?:raw|calibrated)_score_dispersion/(?:iqr|max|mean|min|range|std)",
            _LIME + r"(?:linked_probability_value|attributions/\d+/lime_weight)",
            _LIME
            + r"surrogate/(?:intercept|design_condition_number|n_effective_samples|surrogate_prediction_at_instance)",
            _LIME
            + r"fidelity/(?:holdout_weighted_r2|(?:un)?weighted_(?:r2|rmse)|model_prediction_at_instance|"
            r"local_fidelity_(?:abs_error|relative_error|error_in_neighborhood_sigma)|neighborhood_output_weighted_sd)",
            _LIME
            + r"quality/stability_summary/(?:max_abs_weight_deviation_from_reference_seed|max_feature_weight_std|"
            r"max_local_prediction_abs_deviation|(?:mean|min)_pairwise_spearman|sign_agreement_fraction|top_k_overlap_fraction)",
        )
    )
)
_CONTINUOUS_CRITERIA = {
    "effective_samples",
    "design_condition_number",
    "local_fidelity_relative_error",
    "local_fidelity_error_in_neighborhood_sigma",
    "weighted_r2",
    "holdout_weighted_r2",
    "stability_min_pairwise_spearman",
    "stability_sign_agreement_fraction",
    "stability_top_k_overlap_fraction",
}
_ARTIFACT_MEMBERS = {
    "model.joblib",
    "preprocessing.json",
    "calibration.json",
    "evaluation_summary.json",
    "shap_background.json",
}
_DERIVED = {
    "/pack_sha256",
    "/report/deterministic_sha256",
    "/report/stage_results/7/detail/canonical_payload_sha256",
}
_HEX = re.compile(r"[0-9a-f]{64}")


def _environment_token(value: Any) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[a-zA-Z0-9_. +()-]{1,80}", value) is not None


def _verify(peer: dict, pack: bool) -> None:
    """Check checksum domains before interpreting a diff. Not authentication."""
    try:
        report = peer["report"] if pack else peer
        if (
            report["demo_id"] != DEMO_ID
            or report["status"] != "PASSED"
            or report["synthetic_only"] is not True
            or len(report["stage_results"]) != 8
            or report_digest(report) != report["deterministic_sha256"]
        ):
            raise ComparisonError("incomplete_or_inconsistent_demo")
        inner = report["stage_results"][7]["detail"]["canonical_payload_sha256"]
        if not _HEX.fullmatch(inner):
            raise ComparisonError("invalid_response_digest")
        if pack:
            if digest({k: v for k, v in peer.items() if k != "pack_sha256"}) != peer["pack_sha256"]:
                raise ComparisonError("pack_digest_mismatch")
            if digest(peer["inference"]) != inner:
                raise ComparisonError("response_digest_mismatch")
            repro = peer["reproducibility"]
            # Context (unlike a score) may legitimately differ, but it is
            # never an arbitrary metadata channel or a path to a shared library.
            if not re.fullmatch(r"[0-9a-f]{40}", repro["source"]["git_commit"]):
                raise ComparisonError("invalid_source_revision")
            env = repro["environment"]
            libs = env["numeric_libraries"]
            if (
                not isinstance(libs, list)
                or len(libs) > 32
                or not all(
                    _environment_token(env[k])
                    for k in ("os", "python", "architecture", "implementation")
                )
                or not all(
                    isinstance(lib, dict)
                    and set(lib) == {"internal_api", "version", "architecture", "num_threads"}
                    and type(lib["num_threads"]) is int
                    and lib["num_threads"] > 0
                    and _environment_token(lib["internal_api"])
                    and all(
                        lib[k] is None or _environment_token(lib[k])
                        for k in ("architecture", "version")
                    )
                    for lib in libs
                )
            ):
                raise ComparisonError("invalid_environment_metadata")
            card = peer["model_card"]
            hashes = peer["inference"]["artifact"]["verified_artifact_hashes"]
            if (
                not all(_HEX.fullmatch(value) for value in hashes.values())
                or card["model"]["model_joblib_sha256"] != hashes["model.joblib"]
                or card["protocol"]["bundle_protocol_md_sha256"] != hashes["protocol.md"]
                or digest(card["protocol"]["training_config"])
                != card["protocol"]["training_config_sha256"]
            ):
                raise ComparisonError("card_binding_mismatch")
    except (KeyError, IndexError, TypeError, AttributeError, RecursionError):
        raise ComparisonError("invalid_report_structure") from None


def compare_report(reference_bytes: bytes, peer_bytes: bytes) -> dict:
    """Only the reviewed release or a trusted fresh demo may supply reference_bytes."""
    local_pack = _parse(reference_bytes)
    _verify(local_pack, True)
    peer = _parse(peer_bytes)
    full = peer.get("schema_version") == local_pack["schema_version"]
    if not full and peer.get("demo_id") != DEMO_ID:
        raise ComparisonError("unknown_report_format")
    _verify(peer, full)
    local = local_pack if full else local_pack["report"]
    local_bytes = reference_bytes if full else report_bytes(local)
    differences: list[dict] = []

    def diff(path: str, a: Any, b: Any, parent: dict | None = None) -> None:
        # Paths are constructed ONLY from locally generated keys and indices.
        # Never echo a peer string, unknown key, exception, or filesystem path.
        def note(kind: str, **details: Any) -> None:
            differences.append(
                {"path": path if full else path.removeprefix("/report"), "kind": kind, **details}
            )

        if isinstance(a, dict) and isinstance(b, dict):
            if b.keys() - a.keys():
                note("unexpected_fields_withheld", count=len(b.keys() - a.keys()))
            for key in sorted(a):
                pointer = path + "/" + key.replace("~", "~0").replace("/", "~1")
                if key not in b:
                    diff(pointer, a[key], _MISSING)
                else:
                    diff(pointer, a[key], b[key], a)
            return
        if b is _MISSING:
            note("missing_field")
            return
        if isinstance(a, list) and isinstance(b, list):
            if len(a) != len(b):
                # OS wheels can load different numbers of BLAS/OpenMP libraries.
                context = path == "/reproducibility/environment/numeric_libraries"
                note(
                    "environment" if context else "length_mismatch",
                    reference_count=len(a),
                    peer_count=len(b),
                )
            for i, (v, w) in enumerate(zip(a, b)):
                diff(f"{path}/{i}", v, w)
            return
        if type(a) is not type(b):
            # Some BLAS libraries declare their architecture/version; others
            # leave it null. _verify has already checked this closed grammar.
            if path.startswith("/reproducibility/environment/numeric_libraries/"):
                note("environment")
            elif type(a) in (float, int) and type(b) in (float, int):
                note("type_mismatch", reference=a, peer=b, absolute_delta=abs(a - b))
            else:
                note("type_mismatch")
            return
        if json.dumps(a) == json.dumps(b):  # distinguish -0.0 and 0.0, True and 1
            return
        numeric = type(a) in (float, int)
        values = {"reference": a, "peer": b, "absolute_delta": abs(a - b)} if numeric else {}
        if path in _DERIVED:
            note(
                "derived_digest"
                if full or not path.endswith("canonical_payload_sha256")
                else "opaque_response_digest"
            )
        elif path == "/model_card/model/model_joblib_sha256" or (
            path.startswith("/inference/artifact/verified_artifact_hashes/")
            and path.rsplit("/", 1)[-1] in _ARTIFACT_MEMBERS
        ):
            note("artifact_bytes")
        elif (
            path.startswith("/reproducibility/environment/")
            or path == "/reproducibility/source/git_commit"
        ):
            note("environment", **values)
        elif numeric and (
            _MEASUREMENTS.fullmatch(path)
            or (
                re.fullmatch(_LIME + r"quality/criteria/\d+/observed", path)
                and parent
                and parent.get("name") in _CONTINUOUS_CRITERIA
            )
        ):
            close = math.isclose(a, b, abs_tol=ABS_TOL, rel_tol=REL_TOL)
            note("within_tolerance" if close else "outside_tolerance", **values)
        else:
            note("invariant_mismatch", **values)

    diff("" if full else "/report", local, peer)
    kinds = {d["kind"] for d in differences}
    if kinds - {
        "within_tolerance",
        "artifact_bytes",
        "environment",
        "derived_digest",
        "opaque_response_digest",
    }:
        behavior = "DIFFERENT"
    elif "opaque_response_digest" in kinds or (
        full and not local["reproducibility"]["source"]["source_trees_clean"]
    ):
        behavior = "INDETERMINATE"
    else:
        behavior = "MATCH"
    return {
        "comparison_version": "cardioassist.ai.fixture_comparison/v1",
        "scope": "synthetic_evidence_pack" if full else "AI-11.1_report_only",
        "exact_file_bytes_equal": local_bytes == peer_bytes,
        "file_sha256": {
            "reference": hashlib.sha256(local_bytes).hexdigest(),
            "peer": hashlib.sha256(peer_bytes).hexdigest(),
        },
        "canonical_json_equal": digest(local) == digest(peer),
        "demo_digest": {
            "reference": local_pack["report"]["deterministic_sha256"],
            "peer": (peer["report"] if full else peer)["deterministic_sha256"],
        },
        "artifact_member_hashes_equal": (
            local["inference"]["artifact"]["verified_artifact_hashes"]
            == peer["inference"]["artifact"]["verified_artifact_hashes"]
        )
        if full
        else None,
        "fixture_behavior": behavior,
        "absolute_tolerance": ABS_TOL,
        "relative_tolerance": REL_TOL,
        "differences": differences,
        "interpretation": "Fixed synthetic fixtures only. Report checksums are not signatures. Matching fixture behavior does not establish identical models, medical validity, or authenticity of a peer bundle.",
    }


_MISSING = object()
