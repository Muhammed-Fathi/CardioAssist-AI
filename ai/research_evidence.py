"""AI-12.1: publish evidence from ONE fixed offline AI-11.1 synthetic run.

    python -m ai.research_evidence --output pack.json
    python -m ai.research_evidence --compare other-pack.json

There is no input-record, artifact, authorization, or retained-workspace option.
The comparator's peer JSON is never passed to the demo or a model loader.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict
from importlib.metadata import version
import json
from pathlib import Path
import platform
import re
import subprocess
import sys
from typing import Any, Sequence

from threadpoolctl import threadpool_info

from ai import research_demo as demo
from ai.research_facade import canonical_response_digest
from ai.report_comparison import ComparisonError, compare_report, read_report, report_bytes

PACK_VERSION = "cardioassist.ai.synthetic_evidence_pack/v1"
CARD_VERSION = "cardioassist.ai.synthetic_model_card/v1"
ROOT = Path(__file__).resolve().parents[1]
REQUIREMENTS = "research/uci412/requirements.txt"
# The original linux-example.v1.json is historical evidence from the pre-guard ai tree.
RELEASED_EXAMPLE = ROOT / "docs/research/ai12_1/linux-uci45-envelope.v1.json"


def _source_revision() -> dict[str, Any]:
    # Do not collect remote URLs, branch/user names, paths, or Git configuration.
    def git(*args: str) -> str:
        return subprocess.run(
            ["git", *args], cwd=ROOT, capture_output=True, text=True, check=True, timeout=10
        ).stdout.strip()

    commit, ai_tree, research_tree = git(
        "rev-parse", "HEAD", "HEAD:ai", "HEAD:research"
    ).splitlines()
    if not all(re.fullmatch(r"[0-9a-f]{40}", oid) for oid in (commit, ai_tree, research_tree)):
        raise ValueError("Source revision unavailable.")
    return {
        "git_commit": commit,
        "ai_tree": ai_tree,
        "research_tree": research_tree,
        "source_trees_clean": not git(
            "status", "--porcelain", "--untracked-files=all", "--", "ai", "research"
        ),
    }


def _reproducibility(*, with_lime: bool) -> dict[str, Any]:
    # platform.platform(), uname(), pip freeze and library filepaths can include
    # a hostname, username or private package URL. Collect only these fields.
    return {
        "command": "python -W error -m ai.research_evidence" + ("" if with_lime else " --no-lime"),
        "source": _source_revision(),
        "requirements": REQUIREMENTS,
        "dependencies": {
            p: version(p)
            for p in (
                "numpy",
                "scipy",
                "scikit-learn",
                "joblib",
                "threadpoolctl",
                "openpyxl",
                "et-xmlfile",
            )
        },
        "environment": {
            "os": platform.system(),
            "architecture": platform.machine(),
            "python": platform.python_version(),
            "implementation": platform.python_implementation(),
            "numeric_libraries": [
                {k: lib.get(k) for k in ("internal_api", "version", "architecture", "num_threads")}
                for lib in threadpool_info()
            ],
        },
    }


def build_evidence_pack(*, with_lime: bool = True) -> dict[str, Any]:
    """Only publish a model card on completed, score-free-refusal, verified runs."""
    execution = demo.execute_research_facade_demo(with_lime=with_lime)
    report, success = execution.report, execution.response
    if success is None or not execution.fixture_sha256 or report["status"] != "PASSED":
        raise ValueError("Synthetic demonstration did not complete.")
    details = {stage["stage"]: stage["detail"] for stage in report["stage_results"]}
    abstain = details["5_abstention"]
    unavailable = details["6_unavailable_contracts"]
    errors = details["7_typed_error_refusals"]
    if (
        not abstain["no_score_produced"]
        or not unavailable["no_score_produced"]
        or errors["any_case_produced_a_score"]
    ):
        raise ValueError("Refused input produced a score.")
    # Retain the actual redaction-checked stage-8 preimage, not the rounded
    # stage-4 text summary. Never serialize training objects or bundle members.
    inference = success.to_dict()
    artifact = inference["artifact"]
    hashes = artifact["verified_artifact_hashes"]
    if not (
        artifact["verification"]["producer_authenticated"]
        and artifact["verification"]["safe_for_pickle_deserialization"]
        and canonical_response_digest(inference)
        == details["8_determinism_and_redaction"]["canonical_payload_sha256"]
    ):
        raise ValueError("Verified response evidence unavailable.")
    binding = success.binding
    if binding is None:
        raise ValueError("Successful response has no registry binding.")
    entry, route, panel = binding.entry, binding.route, binding.panel
    first = inference["records"][0]
    score, shap, lime = first["score"], first["shap_explanation"], first["lime_explanation"]
    config = {
        k: list(v) if isinstance(v, tuple) else v
        for k, v in asdict(demo.DEMO_TRAINING_CONFIG).items()
    }
    card = {
        "schema_version": CARD_VERSION,
        "evidence_level": inference["evidence_level"],
        "intended_use": "Offline software test on fabricated development fixtures; not a diagnostic test or a future-event risk estimate.",
        "source": {
            "dataset_id": entry.dataset_id,
            "source_family": entry.source_family,
            "contract_reference": "UCI Heart Disease / processed Cleveland (DOI 10.24432/C52P4X)",
            "license_inventory": "UCI-45 (CC BY 4.0) is a schema reference only. No UCI records downloaded, used, or redistributed. The fixture contains no third-party dataset contents.",
            "cohort_id": artifact["development_cohort_id"],
            "generator": demo.DEMO_GENERATOR_ID,
            "fixture_ref": demo.DEMO_FIXTURE_REF,
            "provenance": inference["provenance"]["input_provenance"],
            "seed": report["seed"],
            "row_count": report["n_records_development"],
            "records_and_labels_sha256": execution.fixture_sha256,
            "evaluation_basis": "First two rows of the generated development cohort, NOT independent or held out. Labels are fabricated by the generator.",
        },
        "model": {
            "id": entry.model_id,
            "version": entry.model_version,
            "family": inference["model_family"],
            "model_joblib_sha256": hashes["model.joblib"],
            "entry_sha256": entry.entry_sha256,
            "bundle_schema_version": artifact["bundle_schema_version"],
            "selection": "Explicit dataset/route/panel/version binding; nested CV on this synthetic cohort only. No cross-route ranking or fallback.",
        },
        "route": {
            "id": route.route_id,
            "version": route.route_version,
            "sha256": route.descriptor_sha256,
            "target": route.target_id,
            "definition": route.target_definition,
        },
        "panel": panel.to_contract_dict() | {"contract_sha256": panel.contract_sha256},
        "protocol": {
            "id": entry.protocol_id,
            "bundle_protocol_md_sha256": hashes["protocol.md"],
            "training_config": config,
            "training_config_sha256": canonical_response_digest(config),
        },
        "capabilities": {
            "calibration": inference["capabilities"]["calibration"]["supported"],
            "shap": inference["capabilities"]["explainability"]["shap"]["supported"],
            "lime": inference["capabilities"]["explainability"]["lime"]["supported"],
        },
        "score_interpretation": score["scale_declaration"],
        "calibration_absence_reason": score["calibration_reason"],
        "tested_refusals": {
            "abstention_code": abstain["code"],
            "unavailable_codes": [c["code"] for c in unavailable["cases"]],
            "error_cases": errors["case_count"],
            "score_produced": False,
        },
        "example_explanations": {
            "shap_scale": shap["scale"],
            "shap_sum_check_passed": shap["sum_check_passed"],
            "lime_scale": lime["scale"],
            "lime_quality": lime["quality_status"],
            "lime_absence_reason": lime["reason"],
            "interpretation": "SHAP additivity is on its declared scale, not calibrated probability. LIME is a local surrogate, not exact Shapley attribution; neither is causal.",
        },
        "governance": inference["governance"],
        "limitations": list(route.evidence_limitations),
    }
    pack = {
        "schema_version": PACK_VERSION,
        "evidence_status": "SYNTHETIC_E2E_COMPLETE",
        "report": report,
        "inference": inference,
        "model_card": card,
        "reproducibility": _reproducibility(with_lime=with_lime),
    }
    pack["pack_sha256"] = canonical_response_digest(pack)
    return pack


class _Parser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        self.exit(2, '{"status":"FAIL_CLOSED","code":"invalid_arguments"}\n')


def main(argv: Sequence[str] | None = None) -> int:
    parser = _Parser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--output", type=Path, help="write a NEW evidence-pack JSON file; never overwrites"
    )
    mode.add_argument(
        "--compare",
        type=Path,
        help="compare a saved pack or AI-11.1 JSON report to the released Linux example (no fit/load)",
    )
    parser.add_argument(
        "--no-lime", action="store_true", help="exercise the explicit not-requested explanation"
    )
    args = parser.parse_args(argv)
    try:
        if args.compare is not None:
            if args.no_lime:
                parser.error("Generation option in compare mode.")
            # The reviewed Linux example is a *file*, not a hash to match or
            # permission to load anything. The run path never reads this file.
            reference = read_report(RELEASED_EXAMPLE)
            comparison = compare_report(reference, read_report(args.compare))
            print(json.dumps(comparison, indent=2, sort_keys=True, allow_nan=False))
            return 0 if comparison["fixture_behavior"] == "MATCH" else 1
        pack = build_evidence_pack(with_lime=not args.no_lime)
        data = report_bytes(pack)
        if args.output is None:
            sys.stdout.buffer.write(data)
        else:
            if args.output.suffix.lower() != ".json":
                raise ValueError("Expected JSON destination.")
            with args.output.open("xb") as out:
                out.write(data)
            first = pack["inference"]["records"][0]
            print(
                json.dumps(
                    {
                        "status": pack["evidence_status"],
                        "stages_passed": pack["report"]["summary"]["stages_succeeded"],
                        "statuses": pack["report"]["summary"]["statuses_exercised"],
                        "raw": first["score"]["raw_model_score"],
                        "calibrated": first["score"]["calibrated_research_score"],
                        "shap_scale": first["shap_explanation"]["scale"],
                        "lime_quality": first["lime_explanation"]["quality_status"],
                        "pack_sha256": pack["pack_sha256"],
                    },
                    indent=2,
                )
            )
        return 0
    except ComparisonError as exc:
        code = exc.code  # static codes only; never print the peer document
    except FileExistsError:
        code = "output_already_exists"
    except Exception:
        code = "evidence_run_or_io_failed"  # no paths, library errors or partial results
    print(json.dumps({"status": "FAIL_CLOSED", "code": code}), file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
