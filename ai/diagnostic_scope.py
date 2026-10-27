"""Independent scope authorization for bounded offline diagnostic inference.

This module is a **post-activation development change** (AI-6.1/v1). It did not
exist at the frozen Cleveland training revision ``A``. It is deliberately
separate from :mod:`ai.execution` (whose ratified training-scope registry is
frozen at ``A``) and from :mod:`ai.cli` (which remains a synthetic-only demo
surface and is not modified by this change).

Why a new scope is required
---------------------------
``AI2-OPERATIONAL-SCOPE-001`` (ratified at ``G``, activated at ``A``) authorized
exactly two operations on real Cleveland data: ``persistent_model_packaging``
and ``patient_level_shap_background``. Section 9 of that amendment explicitly
prohibits calling :class:`ai.inference.ResearchCadPredictor` on the accepted
real bundle -- *even with synthetic inputs*. A training authorization is not an
inference authorization. This module therefore defines a THIRD, narrowly
scoped operation whose trusted registry is EMPTY in production until a separate
maintainer ratification and a separate registry-only activation exist::

    offline_synthetic_input_diagnostic_inference

Three distinct revisions (no self-referential field)
----------------------------------------------------
The activation mechanism follows the already proven Cleveland D-047 ``G`` ->
``A`` pattern. A commit cannot contain its own SHA-1 in tracked content, so no
tracked field ever names the activation commit:

* ``I2`` -- **approved implementation revision**: the commit at which the
  reviewed diagnostic implementation was frozen. It is an ancestor of (or equal
  to) ``G2``, and only documentation may change between ``I2`` and ``G2``.
  Tracked in the registry as ``approved_implementation_commit_sha``.
* ``G2`` -- **governance baseline**: the immutable commit whose tree contains
  both the approved implementation and the ratified governance document. Its
  document bytes are bound by ``frozen_governance_document_sha256``. Tracked in
  the registry as ``governance_baseline_commit_sha``; it is the baseline for
  the ``G2..A2`` registry-only diff.
* ``A2`` -- **activation revision**: the registry-only commit that adds exactly
  one reviewed entry to :data:`RATIFIED_DIAGNOSTIC_INFERENCE_SCOPES`. Its SHA is
  known only AFTER it is merged, so it is stored ONLY in the ignored local
  operator authorization document (``activation_merge_commit_sha``), never in
  any tracked file. Runtime resolves HEAD independently and requires equality.

At activation time the tracked registry therefore contains only previously
known values (``I2``, ``G2``, the document hash at ``G2``, the maintainer's
bundle manifest digest, the operation and the bundle identity). There is no
circular dependency. Runtime additionally proves that ``G2..HEAD`` changed only
``ai/diagnostic_scope.py`` and that the change inside that file is exactly the
empty-registry -> one-record activation, so no training, inference, CLI,
security or unrelated code can be introduced by the activation commit.

What code can and cannot prove
------------------------------
Code enforces the empty registry, exact scope/identity bindings, an explicit
local operator authorization document, and independent local Git evidence
(baseline ancestry, frozen governance-document bytes, clean checked-out
activation revision, registry-only activation diff). Code CANNOT verify a human
signature, maintainer intent, GitHub comment authenticity, PR merged state,
NTFS ownership outside the platform API, or the lawfulness of external data
use. Those remain human controls; see the scope document. Nothing in this
module creates, forges, or infers approval.

The registry is EMPTY. With an empty registry every function that can lead to
bundle loading fails closed with ``diagnostic_scope_not_ratified`` BEFORE any
bundle verification, ``joblib.load``, or inference.
"""
from __future__ import annotations

import ast
from dataclasses import dataclass
from datetime import datetime
import hashlib
import json
import math
from pathlib import Path
import re
import subprocess
from types import MappingProxyType
from typing import Any, Final, Mapping

from ai.errors import AiPipelineError
from ai.filesystem_security import (
    has_reparse_between,
    is_reparse_or_symlink,
    relative_posix_if_within_directory,
)
from ai.packaging import REPOSITORY_ROOT
from ai.panels import DA_A2_RESTING_PANEL
from ai.training import EXECUTION_PROFILE_CLEVELAND_D047_FROZEN_V1

# --------------------------------------------------------------------------- #
# Versioning and frozen bindings (maintainer-supplied, never recomputed here)
# --------------------------------------------------------------------------- #

#: Development interface version. Distinct from the frozen training harness at A.
#: v1.1 replaces the circular ``approved_code_revision == A2`` design with the
#: realizable G2 (governance baseline / approved implementation) -> A2
#: (registry-only activation) binding.
DIAGNOSTIC_INTERFACE_VERSION: Final[str] = (
    "cardioassist.ai.bounded_offline_diagnostic_inference/v1.1"
)
#: Frozen training activation revision (PR #58 merge). Never used as the
#: executing revision for this development change.
FROZEN_TRAINING_REVISION_A: Final[str] = (
    "1c29c83cd07fcb0510ac37e185323c231b267670"
)
#: Governance merge of the ratified training amendment (PR #54 merge).
FROZEN_GOVERNANCE_MERGE_G: Final[str] = (
    "7f4b7a50d7fd423914e5bd98ed2b525bddbfc627"
)
FROZEN_TRAINING_AMENDMENT_ID: Final[str] = "CAI-AMEND-AI2-CLEVELAND-D047-V1"

#: Identifier of the NEW scope proposed for separate maintainer ratification.
DIAGNOSTIC_SCOPE_ID: Final[str] = (
    "CAI-SCOPE-BOUNDED-OFFLINE-DIAGNOSTIC-INFERENCE-CLEVELAND-D047-V1"
)
#: Governance document whose exact bytes at the ratified merge ``G2`` must be
#: bound in the trusted registry. Its status field changes at ratification, so
#: the filename deliberately contains no status word.
DIAGNOSTIC_GOVERNANCE_DOCUMENT_RELATIVE_PATH: Final[str] = (
    "docs/research/gate-pt/18_bounded_offline_diagnostic_inference_scope.md"
)
#: v1.1 renames the two ambiguous revision fields and adds the registration
#: path. ``activation_merge_commit_sha`` (A2) is local-only and is never part
#: of any tracked registry record.
DIAGNOSTIC_AUTHORIZATION_SCHEMA_VERSION: Final[str] = (
    "cardioassist.ai.diagnostic_authorization/v1.1"
)
#: The ONLY tracked file an activation commit may change.
DIAGNOSTIC_ACTIVATION_REGISTRY_RELATIVE_PATH: Final[str] = "ai/diagnostic_scope.py"
#: Name of the single tracked assignment an activation commit may change.
DIAGNOSTIC_REGISTRY_SYMBOL: Final[str] = "RATIFIED_DIAGNOSTIC_INFERENCE_SCOPES"
#: Between I2 and G2 only documentation may change (no implementation drift).
DIAGNOSTIC_IMPLEMENTATION_DOCUMENT_ONLY_PREFIX: Final[str] = "docs/"
DIAGNOSTIC_OPERATOR_CONFIRMATION: Final[str] = (
    "I_CONFIRM_BOUNDED_OFFLINE_CLEVELAND_D047_DIAGNOSTIC_INFERENCE"
)
DIAGNOSTIC_AUTHORIZATION_STATUS: Final[str] = "AUTHORIZED_BY_LOCAL_OPERATOR"
DIAGNOSTIC_ALLOWED_OPERATIONS: Final[tuple[str, ...]] = (
    "offline_synthetic_input_diagnostic_inference",
)
DIAGNOSTIC_ATTESTATION_TOKENS: Final[tuple[str, ...]] = (
    "SYNTHETIC_INPUTS_ONLY",
    "NO_PATIENT_DATA",
    "NO_CLINICAL_USE",
    "OFFLINE_ONLY",
)
DIAGNOSTIC_MAX_RECORDS: Final[int] = 8
DIAGNOSTIC_MAX_AUTHORIZATION_BYTES: Final[int] = 64 * 1024

_GIT_SHA_RE: Final[re.Pattern[str]] = re.compile(r"^[0-9a-f]{40}$")
_SHA256_RE: Final[re.Pattern[str]] = re.compile(r"^[0-9a-f]{64}$")

#: Exact identity of the single already-accepted real Cleveland bundle. These
#: values come from the maintainer's reported acceptance, the frozen execution
#: code at A, and the registered panel contract. ``expected_manifest_sha256``
#: is intentionally NOT here: Arena has never seen the private bundle. It must
#: be supplied as maintainer evidence in the registry-only activation.
DIAGNOSTIC_TARGET_BUNDLE: Final[Mapping[str, Any]] = MappingProxyType(
    {
        "expected_bundle_dir_name": (
            "cai_real_cleveland_d047_20261027T070610Z_deffa577"
        ),
        "expected_dataset_id": "DA-A2",
        "expected_panel_id": DA_A2_RESTING_PANEL.panel_id,
        "expected_panel_contract_sha256": DA_A2_RESTING_PANEL.contract_sha256,
        "expected_ordered_feature_names": DA_A2_RESTING_PANEL.feature_names,
        "expected_source_sha256": (
            "a74b7efa387bc9d108d7d0115d831fe9b414b29ae7124f331b622b4efa0427c8"
        ),
        "expected_execution_profile": EXECUTION_PROFILE_CLEVELAND_D047_FROZEN_V1,
        "expected_model_family": "l2_logistic_regression",
        "expected_selected_c": 10.0,
        "expected_model_id": "cai_real_da-a2_da_a2_resting_v1",
        "expected_protocol_id": "CAI-D047-CLEVELAND-EXPLORATORY-V1",
        "expected_model_version": "0.2.0",
    }
)

#: Trusted maintainer ratification registry for the NEW inference scope.
#:
#: EMPTY IN PRODUCTION. This is the independent-authorization gate: no local
#: manifest, no training amendment, no acceptance marker, no CLI flag and no
#: in-process token can substitute for an entry here. Activation is a SEPARATE,
#: registry-only, maintainer-ratified change to this dictionary (and only this
#: dictionary) after the governance document has been ratified at ``G2``. It is
#: intentionally not part of this engineering PR.
#:
#: The activation commit A2 may change ONLY this assignment. It contains the
#: previously known I2/G2 SHAs, the document hash at G2, the maintainer-supplied
#: bundle manifest digest, and the operation/identity bindings. It MUST NOT
#: contain its own A2 SHA (that would be circular): A2 lives only in the
#: ignored local operator authorization document.
RATIFIED_DIAGNOSTIC_INFERENCE_SCOPES: dict[str, dict[str, Any]] = {
    "CAI-SCOPE-BOUNDED-OFFLINE-DIAGNOSTIC-INFERENCE-CLEVELAND-D047-V1": {
        "governance_pr_number": 60,
        "governance_baseline_commit_sha": (
            "44f06091602f66078726fcc3b62b6ee1305abd83"
        ),
        "approved_implementation_commit_sha": (
            "40b544be79acc9099e565a0ede183e9b376a238f"
        ),
        "governance_document_relative_path": (
            "docs/research/gate-pt/"
            "18_bounded_offline_diagnostic_inference_scope.md"
        ),
        "frozen_governance_document_sha256": (
            "2fabbcf36451ff1e1564db76b5ce7c1bffe50e0c428a847d89c475169cf90f8c"
        ),
        "ratified_by": "Muhammed-Fathi",
        "ratification_comment_exact": (
            "RATIFY-BOUNDED-OFFLINE-DIAGNOSTIC-INFERENCE-SCOPE"
        ),
        "approved_operations": (
            "offline_synthetic_input_diagnostic_inference",
        ),
        "expected_manifest_sha256": (
            "089f931be27be67606b9d2622beea54208976f1743a70909029619f50a6e5d4a"
        ),
        "expected_bundle_dir_name": (
            "cai_real_cleveland_d047_20261027T070610Z_deffa577"
        ),
        "expected_source_sha256": (
            "a74b7efa387bc9d108d7d0115d831fe9b414b29ae7124f331b622b4efa0427c8"
        ),
        "expected_dataset_id": "DA-A2",
        "expected_panel_id": "da_a2_resting_v1",
        "expected_execution_profile": "CLEVELAND_D047_FROZEN_V1",
        "expected_model_family": "l2_logistic_regression",
        "expected_selected_c": 10.0,
        "expected_model_id": "cai_real_da-a2_da_a2_resting_v1",
        "expected_protocol_id": "CAI-D047-CLEVELAND-EXPLORATORY-V1",
        "expected_model_version": "0.2.0",
    },
}

#: Documentation-only shape of the record an activation would have to supply.
#: It contains no approval, no signature, and no usable digest. It is NEVER read
#: by the authorization validator; only ``RATIFIED_DIAGNOSTIC_INFERENCE_SCOPES``
#: is trusted. Note the absence of any activation-revision field.
DIAGNOSTIC_SCOPE_ACTIVATION_TEMPLATE: Final[Mapping[str, Any]] = MappingProxyType(
    {
        "governance_pr_number": None,
        "governance_baseline_commit_sha": None,  # G2, immutable, 40 lowercase hex
        "approved_implementation_commit_sha": None,  # I2, ancestor/equal G2
        "governance_document_relative_path": (
            DIAGNOSTIC_GOVERNANCE_DOCUMENT_RELATIVE_PATH
        ),
        "frozen_governance_document_sha256": None,  # 64 hex, bytes at G2
        "ratified_by": None,  # maintainer identity, human evidence
        "ratification_comment_exact": None,  # exact owner comment on PR
        "approved_operations": DIAGNOSTIC_ALLOWED_OPERATIONS,
        "expected_manifest_sha256": None,  # 64 hex, maintainer-supplied
        "expected_bundle_dir_name": DIAGNOSTIC_TARGET_BUNDLE[
            "expected_bundle_dir_name"
        ],
        "expected_source_sha256": DIAGNOSTIC_TARGET_BUNDLE[
            "expected_source_sha256"
        ],
        "expected_dataset_id": DIAGNOSTIC_TARGET_BUNDLE["expected_dataset_id"],
        "expected_panel_id": DIAGNOSTIC_TARGET_BUNDLE["expected_panel_id"],
        "expected_execution_profile": DIAGNOSTIC_TARGET_BUNDLE[
            "expected_execution_profile"
        ],
        "expected_model_family": DIAGNOSTIC_TARGET_BUNDLE[
            "expected_model_family"
        ],
        "expected_selected_c": DIAGNOSTIC_TARGET_BUNDLE["expected_selected_c"],
        "expected_model_id": DIAGNOSTIC_TARGET_BUNDLE["expected_model_id"],
        "expected_protocol_id": DIAGNOSTIC_TARGET_BUNDLE["expected_protocol_id"],
        "expected_model_version": DIAGNOSTIC_TARGET_BUNDLE[
            "expected_model_version"
        ],
    }
)


class DiagnosticScopeError(AiPipelineError):
    """Raised when the independent diagnostic-inference scope gate fails."""


@dataclass(frozen=True, slots=True)
class DiagnosticScopeContext:
    """Non-bypassable result of a successful independent scope check.

    ``governance_baseline_commit_sha`` is G2, ``approved_implementation_commit_sha``
    is I2, and ``activation_merge_commit_sha`` is the independently resolved
    HEAD (A2) declared by the ignored local operator authorization. None of
    these is self-referential.
    """

    scope_id: str
    governance_pr_number: int
    governance_baseline_commit_sha: str
    approved_implementation_commit_sha: str
    activation_merge_commit_sha: str
    governance_document_relative_path: str
    frozen_governance_document_sha256: str
    ratified_by: str
    expected_manifest_sha256: str
    expected_bundle_dir_name: str
    expected_source_sha256: str
    expected_dataset_id: str
    expected_panel_id: str
    expected_execution_profile: str
    expected_model_family: str
    expected_selected_c: float
    expected_model_id: str
    expected_protocol_id: str
    expected_model_version: str
    approved_operations: tuple[str, ...]

    def identity(self) -> dict[str, Any]:
        """Aggregate-only identity summary (no local paths, no patient values)."""
        return {
            "scope_id": self.scope_id,
            "governance_pr_number": self.governance_pr_number,
            "governance_baseline_commit_sha": self.governance_baseline_commit_sha,
            "approved_implementation_commit_sha": (
                self.approved_implementation_commit_sha
            ),
            "activation_merge_commit_sha": self.activation_merge_commit_sha,
            "activation_registry_relative_path": (
                DIAGNOSTIC_ACTIVATION_REGISTRY_RELATIVE_PATH
            ),
            "expected_bundle_dir_name": self.expected_bundle_dir_name,
            "expected_manifest_sha256": self.expected_manifest_sha256,
            "expected_dataset_id": self.expected_dataset_id,
            "expected_panel_id": self.expected_panel_id,
            "expected_execution_profile": self.expected_execution_profile,
            "expected_model_family": self.expected_model_family,
            "expected_selected_c": self.expected_selected_c,
            "approved_operations": list(self.approved_operations),
        }


# --------------------------------------------------------------------------- #
# Strict local-document handling
# --------------------------------------------------------------------------- #

_AUTHORIZATION_KEYS: Final[frozenset[str]] = frozenset(
    {
        "schema_version",
        "authorization_status",
        "scope_id",
        "governance_pr_number",
        "governance_baseline_commit_sha",       # G2, trusted + local claim
        "approved_implementation_commit_sha",   # I2, trusted + local claim
        "activation_merge_commit_sha",          # A2, LOCAL ONLY, never tracked
        "activation_registry_relative_path",    # the one file A2 may change
        "governance_document_relative_path",
        "frozen_governance_document_sha256",
        "ratified_by",
        "ratification_comment_exact",
        "approved_operations",
        "supervisor_signoff_claimed",
        "human_attestation",
        "bundle_identity",
        "input_declaration",
        "execution_boundary",
        "local_signer",
        "local_signed_at_iso8601",
        "local_signature_attestation",
        "operator_confirmation",
    }
)
_BUNDLE_IDENTITY_KEYS: Final[frozenset[str]] = frozenset(
    {
        "bundle_dir_name",
        "expected_manifest_sha256",
        "expected_source_sha256",
        "expected_dataset_id",
        "expected_panel_id",
        "expected_model_family",
        "expected_execution_profile",
        "expected_selected_c",
    }
)
_INPUT_DECLARATION_KEYS: Final[frozenset[str]] = frozenset(
    {"origin", "contains_patient_data", "panel_id", "records_are_synthetic"}
)
_EXECUTION_BOUNDARY_KEYS: Final[frozenset[str]] = frozenset(
    {
        "offline_only",
        "api_serving",
        "telemetry",
        "uploads",
        "writes_bundle",
        "retraining_or_tuning",
        "patient_data_inputs",
    }
)
_TEMPLATE_TOKENS: Final[tuple[str, ...]] = (
    "TEMPLATE",
    "PROPOSED",
    "PENDING",
    "NOT_AUTHORIZED",
    "NOT_RATIFIED",
    "PLACEHOLDER",
)


def _fail(code: str, message: str, *, field: str | None = None) -> None:
    raise DiagnosticScopeError(code, message, field=field)


def _require(condition: bool, code: str, message: str, *, field: str | None = None) -> None:
    if not condition:
        _fail(code, message, field=field)


def _exact_keys(doc: Mapping[str, Any], expected: frozenset[str], *, field: str) -> None:
    actual = frozenset(doc)
    _require(
        actual == expected,
        "diagnostic_authorization_field_set_invalid",
        f"Local authorization '{field}' must declare exactly the registered "
        f"keys; missing={sorted(expected - actual)}, "
        f"unexpected={sorted(actual - expected)}.",
        field=field,
    )


def _lower_sha(value: Any) -> str:
    return str(value).strip().lower() if isinstance(value, str) else ""


def _reject_non_finite_constant(token: str) -> Any:
    _fail(
        "diagnostic_non_finite_json_constant",
        f"Local JSON document contains non-finite constant '{token}'.",
    )


def _no_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    obj: dict[str, Any] = {}
    for key, value in pairs:
        _require(
            key not in obj,
            "diagnostic_duplicate_json_key",
            "Local JSON document contains a duplicated object key.",
            field=str(key),
        )
        obj[key] = value
    return obj


def _parse_strict_json(raw: bytes, *, field: str) -> dict[str, Any]:
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise DiagnosticScopeError(
            "diagnostic_malformed_local_json",
            "Local JSON document is not valid UTF-8.",
            field=field,
        ) from exc
    try:
        doc = json.loads(
            text,
            object_pairs_hook=_no_duplicate_keys,
            parse_constant=_reject_non_finite_constant,
        )
    except AiPipelineError:
        raise
    except (json.JSONDecodeError, ValueError, TypeError, RecursionError) as exc:
        raise DiagnosticScopeError(
            "diagnostic_malformed_local_json",
            "Local JSON document is not valid JSON.",
            field=field,
        ) from exc
    _require(
        isinstance(doc, dict),
        "diagnostic_malformed_local_json",
        "Local JSON document must be a single object.",
        field=field,
    )
    return doc


def _assert_finite_json_tree(node: Any, *, field: str) -> None:
    """Reject NaN/Infinity anywhere in a parsed local document.

    ``json.loads`` turns ``1e400`` into ``inf`` without invoking
    ``parse_constant``; an explicit tree walk is therefore required.
    """
    if isinstance(node, float):
        _require(
            math.isfinite(node),
            "diagnostic_non_finite_local_value",
            "Local JSON document contains a non-finite numeric value.",
            field=field,
        )
    elif isinstance(node, Mapping):
        for key, value in node.items():
            _require(
                isinstance(key, str),
                "diagnostic_malformed_local_json",
                "Object keys must be strings.",
                field=field,
            )
            _assert_finite_json_tree(value, field=field)
    elif isinstance(node, (list, tuple)):
        for value in node:
            _assert_finite_json_tree(value, field=field)


def _read_private_local_json(
    path: Path, *, repo_root: Path, max_bytes: int, field: str
) -> dict[str, Any]:
    """Read a strict, finite, symlink-free local JSON document.

    Inside the checkout the file must be Git-ignored; outside the checkout it is
    a private workstation file. No file is written, no network is used.
    """
    candidate = Path(path)
    _require(
        not is_reparse_or_symlink(candidate) and candidate.is_file(),
        "diagnostic_local_file_untrusted",
        f"{field} must be an existing regular, non-symlink/non-reparse file.",
        field=field,
    )
    _require(
        not is_reparse_or_symlink(candidate.parent),
        "diagnostic_local_file_untrusted",
        f"The parent directory of {field} must not be a symlink/reparse point.",
        field=field,
    )
    rel = relative_posix_if_within_directory(candidate, Path(repo_root))
    if rel is not None:
        _require(
            not has_reparse_between(candidate.parent, Path(repo_root)),
            "diagnostic_local_file_untrusted",
            f"{field} is reached across a symlink/junction/reparse point.",
            field=field,
        )
        probe = subprocess.run(
            ["git", "check-ignore", "-q", "--", rel],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            check=False,
        )
        _require(
            probe.returncode == 0,
            "diagnostic_local_file_not_git_ignored",
            f"{field} lies inside the checkout but is not Git-ignored.",
            field=field,
        )
    try:
        size = candidate.stat().st_size
        _require(
            size <= max_bytes,
            "diagnostic_local_file_too_large",
            f"{field} exceeds its bounded local size ceiling.",
            field=field,
        )
        raw = candidate.read_bytes()
    except OSError as exc:
        raise DiagnosticScopeError(
            "diagnostic_local_file_unreadable",
            f"{field} could not be read.",
            field=field,
        ) from exc
    doc = _parse_strict_json(raw, field=field)
    _assert_finite_json_tree(doc, field=field)
    return doc


def load_diagnostic_authorization(
    authorization_path: Path, *, repo_root: Path = REPOSITORY_ROOT
) -> dict[str, Any]:
    """Load the explicit local operator authorization document (no approval invented)."""
    return _read_private_local_json(
        Path(authorization_path),
        repo_root=Path(repo_root),
        max_bytes=DIAGNOSTIC_MAX_AUTHORIZATION_BYTES,
        field="authorization",
    )


# --------------------------------------------------------------------------- #
# Local operator authorization (shape and declarations only)
# --------------------------------------------------------------------------- #


def validate_local_authorization(
    doc: Mapping[str, Any], *, operator_confirmation: str | None
) -> None:
    """Validate the operator's explicit, bounded, local declaration.

    This is an attestation, NOT a cryptographic signature and NOT proof of
    maintainer authority. The independent ratification check in
    :func:`validate_diagnostic_scope` is mandatory even when this passes.
    """
    _require(
        isinstance(doc, Mapping),
        "diagnostic_authorization_must_be_mapping",
        "Local authorization must be a mapping.",
        field="authorization",
    )
    _exact_keys(doc, _AUTHORIZATION_KEYS, field="authorization")

    _require(
        doc.get("schema_version") == DIAGNOSTIC_AUTHORIZATION_SCHEMA_VERSION,
        "diagnostic_authorization_schema_unsupported",
        "Unsupported local authorization schema version.",
        field="schema_version",
    )
    status = str(doc.get("authorization_status", "")).strip()
    _require(
        status == DIAGNOSTIC_AUTHORIZATION_STATUS
        and not any(token in status.upper() for token in _TEMPLATE_TOKENS),
        "diagnostic_authorization_not_effective",
        "Local authorization status is a template, proposal, or unratified state; "
        "no diagnostic inference is permitted.",
        field="authorization_status",
    )
    _require(
        str(doc.get("scope_id", "")).strip() == DIAGNOSTIC_SCOPE_ID,
        "diagnostic_scope_id_mismatch",
        "Local authorization names a different diagnostic scope.",
        field="scope_id",
    )
    _require(
        doc.get("supervisor_signoff_claimed") is False,
        "diagnostic_supervisor_signoff_claimed",
        "Gate PT P-3 remains CLOSED; no supervisor sign-off may be claimed.",
        field="supervisor_signoff_claimed",
    )
    _require(
        tuple(doc.get("approved_operations", ())) == DIAGNOSTIC_ALLOWED_OPERATIONS,
        "diagnostic_operations_not_bounded",
        "Local authorization must list exactly the single bounded diagnostic operation.",
        field="approved_operations",
    )
    _require(
        operator_confirmation == DIAGNOSTIC_OPERATOR_CONFIRMATION
        and doc.get("operator_confirmation") == DIAGNOSTIC_OPERATOR_CONFIRMATION,
        "diagnostic_operator_confirmation_required",
        "The exact local operator confirmation phrase must be supplied on the "
        "invocation AND declared in the local authorization document.",
        field="operator_confirmation",
    )

    attestation = str(doc.get("human_attestation", "")).strip()
    _require(
        all(token in attestation for token in DIAGNOSTIC_ATTESTATION_TOKENS),
        "diagnostic_human_attestation_invalid",
        "Local human attestation must explicitly declare synthetic-only inputs, "
        "no patient data, no clinical use, and offline-only execution.",
        field="human_attestation",
    )
    for field_name in ("local_signer", "local_signed_at_iso8601", "local_signature_attestation"):
        value = str(doc.get(field_name, "")).strip()
        _require(
            bool(value) and not any(t in value.upper() for t in _TEMPLATE_TOKENS),
            "diagnostic_local_attestation_incomplete",
            f"Local attestation field '{field_name}' is missing or is a template placeholder.",
            field=field_name,
        )
    signed_at = str(doc["local_signed_at_iso8601"]).strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(signed_at)
    except ValueError as exc:
        raise DiagnosticScopeError(
            "diagnostic_local_attestation_incomplete",
            "local_signed_at_iso8601 must be an ISO-8601 timestamp.",
            field="local_signed_at_iso8601",
        ) from exc
    _require(
        parsed.tzinfo is not None,
        "diagnostic_local_attestation_incomplete",
        "local_signed_at_iso8601 must include a UTC offset.",
        field="local_signed_at_iso8601",
    )
    signature_text = str(doc["local_signature_attestation"]).strip()
    _require(
        all(token in signature_text for token in DIAGNOSTIC_ATTESTATION_TOKENS),
        "diagnostic_local_attestation_incomplete",
        "local_signature_attestation does not restate the bounded execution terms.",
        field="local_signature_attestation",
    )

    for field_name in (
        "governance_baseline_commit_sha",
        "approved_implementation_commit_sha",
        "activation_merge_commit_sha",
    ):
        _require(
            bool(_GIT_SHA_RE.fullmatch(_lower_sha(doc.get(field_name)))),
            "diagnostic_git_evidence_malformed",
            f"'{field_name}' must be a 40-hex lowercase Git commit SHA.",
            field=field_name,
        )
    # A2 must be distinct from the previously known baselines; otherwise the
    # "activation" is just a renamed governance baseline and proves nothing.
    activation_sha = _lower_sha(doc.get("activation_merge_commit_sha"))
    _require(
        activation_sha not in {
            _lower_sha(doc.get("governance_baseline_commit_sha")),
            _lower_sha(doc.get("approved_implementation_commit_sha")),
        },
        "diagnostic_activation_revision_malformed",
        "activation_merge_commit_sha (A2) must be a distinct, later commit; it "
        "cannot equal the governance baseline G2 or implementation revision I2.",
        field="activation_merge_commit_sha",
    )
    _require(
        doc.get("activation_registry_relative_path")
        == DIAGNOSTIC_ACTIVATION_REGISTRY_RELATIVE_PATH,
        "diagnostic_activation_registry_path_mismatch",
        "Local authorization must name exactly the one tracked file an "
        "activation commit may change.",
        field="activation_registry_relative_path",
    )
    _require(
        isinstance(doc.get("governance_pr_number"), int)
        and not isinstance(doc.get("governance_pr_number"), bool)
        and int(doc["governance_pr_number"]) > 0,
        "diagnostic_git_evidence_malformed",
        "governance_pr_number must be a positive integer.",
        field="governance_pr_number",
    )
    _require(
        doc.get("governance_document_relative_path")
        == DIAGNOSTIC_GOVERNANCE_DOCUMENT_RELATIVE_PATH,
        "diagnostic_governance_document_path_mismatch",
        "Local authorization names the wrong governance document path.",
        field="governance_document_relative_path",
    )
    _require(
        bool(_SHA256_RE.fullmatch(_lower_sha(doc.get("frozen_governance_document_sha256")))),
        "diagnostic_governance_document_hash_malformed",
        "frozen_governance_document_sha256 must be 64 lowercase hex.",
        field="frozen_governance_document_sha256",
    )
    for field_name in ("ratified_by", "ratification_comment_exact"):
        value = str(doc.get(field_name, "")).strip()
        _require(
            bool(value) and not any(t in value.upper() for t in _TEMPLATE_TOKENS),
            "diagnostic_ratification_evidence_incomplete",
            f"Ratification evidence '{field_name}' is missing or a placeholder.",
            field=field_name,
        )

    bundle = doc.get("bundle_identity")
    _require(
        isinstance(bundle, Mapping),
        "diagnostic_bundle_identity_invalid",
        "bundle_identity must be a mapping.",
        field="bundle_identity",
    )
    _exact_keys(bundle, _BUNDLE_IDENTITY_KEYS, field="bundle_identity")
    expected_bundle: dict[str, Any] = {
        "bundle_dir_name": DIAGNOSTIC_TARGET_BUNDLE["expected_bundle_dir_name"],
        "expected_source_sha256": DIAGNOSTIC_TARGET_BUNDLE["expected_source_sha256"],
        "expected_dataset_id": DIAGNOSTIC_TARGET_BUNDLE["expected_dataset_id"],
        "expected_panel_id": DIAGNOSTIC_TARGET_BUNDLE["expected_panel_id"],
        "expected_model_family": DIAGNOSTIC_TARGET_BUNDLE["expected_model_family"],
        "expected_execution_profile": DIAGNOSTIC_TARGET_BUNDLE[
            "expected_execution_profile"
        ],
        "expected_selected_c": DIAGNOSTIC_TARGET_BUNDLE["expected_selected_c"],
    }
    for name, expected in expected_bundle.items():
        _require(
            bundle.get(name) == expected,
            "diagnostic_bundle_identity_invalid",
            f"bundle_identity.{name} does not match the single accepted bundle.",
            field=f"bundle_identity.{name}",
        )
    _require(
        bool(_SHA256_RE.fullmatch(_lower_sha(bundle.get("expected_manifest_sha256")))),
        "diagnostic_bundle_identity_invalid",
        "bundle_identity.expected_manifest_sha256 must be 64 lowercase hex.",
        field="bundle_identity.expected_manifest_sha256",
    )

    declaration = doc.get("input_declaration")
    _require(
        isinstance(declaration, Mapping),
        "diagnostic_input_declaration_invalid",
        "input_declaration must be a mapping.",
        field="input_declaration",
    )
    _exact_keys(declaration, _INPUT_DECLARATION_KEYS, field="input_declaration")
    _require(
        declaration.get("origin") == "EXPLICITLY_FABRICATED"
        and declaration.get("contains_patient_data") is False
        and declaration.get("records_are_synthetic") is True
        and declaration.get("panel_id") == DIAGNOSTIC_TARGET_BUNDLE["expected_panel_id"],
        "diagnostic_input_declaration_invalid",
        "Only explicitly fabricated, non-patient, synthetic five-field records "
        "are declared for this scope.",
        field="input_declaration",
    )

    boundary = doc.get("execution_boundary")
    _require(
        isinstance(boundary, Mapping),
        "diagnostic_execution_boundary_invalid",
        "execution_boundary must be a mapping.",
        field="execution_boundary",
    )
    _exact_keys(boundary, _EXECUTION_BOUNDARY_KEYS, field="execution_boundary")
    expected_boundary: dict[str, bool] = {
        "offline_only": True,
        "api_serving": False,
        "telemetry": False,
        "uploads": False,
        "writes_bundle": False,
        "retraining_or_tuning": False,
        "patient_data_inputs": False,
    }
    for name, expected in expected_boundary.items():
        _require(
            boundary.get(name) is expected,
            "diagnostic_execution_boundary_invalid",
            f"execution_boundary.{name} must be exactly {expected}; no serving, "
            "telemetry, upload, bundle mutation or patient record is permitted.",
            field=f"execution_boundary.{name}",
        )


# --------------------------------------------------------------------------- #
# Independent ratification + Git evidence
# --------------------------------------------------------------------------- #

_TRUSTED_STRING_FIELDS: Final[tuple[str, ...]] = (
    "governance_baseline_commit_sha",
    "approved_implementation_commit_sha",
    "governance_document_relative_path",
    "frozen_governance_document_sha256",
    "ratified_by",
    "ratification_comment_exact",
    "expected_manifest_sha256",
    "expected_bundle_dir_name",
    "expected_source_sha256",
    "expected_dataset_id",
    "expected_panel_id",
    "expected_execution_profile",
    "expected_model_family",
    "expected_model_id",
    "expected_protocol_id",
    "expected_model_version",
)


def _validated_trusted_record(record: Any, *, scope_id: str) -> dict[str, Any]:
    """Validate the reviewed registry entry itself (defence in depth)."""
    _require(
        isinstance(record, Mapping),
        "diagnostic_scope_registry_entry_invalid",
        "Trusted scope record must be a mapping.",
        field=scope_id,
    )
    missing = [k for k in (*_TRUSTED_STRING_FIELDS, "governance_pr_number",
                           "approved_operations", "expected_selected_c")
               if k not in record]
    _require(
        not missing,
        "diagnostic_scope_registry_entry_invalid",
        f"Trusted scope record lacks required fields: {sorted(missing)}.",
        field=scope_id,
    )
    for name in _TRUSTED_STRING_FIELDS:
        value = record.get(name)
        _require(
            isinstance(value, str) and bool(value.strip())
            and not any(t in value.upper() for t in _TEMPLATE_TOKENS),
            "diagnostic_scope_registry_entry_invalid",
            f"Trusted scope field '{name}' is empty or a placeholder.",
            field=name,
        )
    for name in (
        "governance_baseline_commit_sha",
        "approved_implementation_commit_sha",
    ):
        _require(
            bool(_GIT_SHA_RE.fullmatch(_lower_sha(record.get(name)))),
            "diagnostic_scope_registry_entry_invalid",
            f"Trusted scope field '{name}' must be 40 lowercase hex.",
            field=name,
        )
    # A tracked registry record MUST NOT name an activation revision: A2 cannot
    # be known before the commit containing this record exists. This is the
    # explicit guard against reintroducing the circular SHA dependency.
    forbidden_self_reference = (
        "approved_code_revision",
        "activation_merge_commit_sha",
        "activation_revision_commit_sha",
    )
    _require(
        not any(name in record for name in forbidden_self_reference),
        "diagnostic_scope_registry_self_referential",
        "A tracked registry record must not contain its own activation commit "
        "SHA (or any self-referential code-revision field). A2 belongs only in "
        "the ignored local operator authorization document.",
        field="activation_merge_commit_sha",
    )
    for name in (
        "frozen_governance_document_sha256",
        "expected_manifest_sha256",
        "expected_source_sha256",
    ):
        _require(
            bool(_SHA256_RE.fullmatch(_lower_sha(record.get(name)))),
            "diagnostic_scope_registry_entry_invalid",
            f"Trusted scope field '{name}' must be 64 lowercase hex.",
            field=name,
        )
    pr = record.get("governance_pr_number")
    _require(
        isinstance(pr, int) and not isinstance(pr, bool) and pr > 0,
        "diagnostic_scope_registry_entry_invalid",
        "governance_pr_number must be a positive integer.",
        field="governance_pr_number",
    )
    # This development change must never be represented as having existed at
    # the frozen training activation A, nor reuse its governance merge G.
    frozen_revisions = {FROZEN_TRAINING_REVISION_A, FROZEN_GOVERNANCE_MERGE_G}
    _require(
        _lower_sha(record.get("governance_baseline_commit_sha"))
        not in frozen_revisions
        and _lower_sha(record.get("approved_implementation_commit_sha"))
        not in frozen_revisions,
        "diagnostic_scope_reuses_training_activation",
        "A diagnostic scope cannot reuse the frozen training governance merge "
        "or activation revision as its G2/I2 baselines; a separate ratification "
        "and approved implementation revision are required.",
        field="governance_baseline_commit_sha",
    )
    _require(
        tuple(record.get("approved_operations", ())) == DIAGNOSTIC_ALLOWED_OPERATIONS,
        "diagnostic_scope_registry_entry_invalid",
        "Trusted scope must authorize exactly the single bounded operation.",
        field="approved_operations",
    )
    frozen: dict[str, Any] = {
        "governance_document_relative_path": (
            DIAGNOSTIC_GOVERNANCE_DOCUMENT_RELATIVE_PATH
        ),
        "expected_bundle_dir_name": DIAGNOSTIC_TARGET_BUNDLE[
            "expected_bundle_dir_name"
        ],
        "expected_source_sha256": DIAGNOSTIC_TARGET_BUNDLE[
            "expected_source_sha256"
        ],
        "expected_dataset_id": DIAGNOSTIC_TARGET_BUNDLE["expected_dataset_id"],
        "expected_panel_id": DIAGNOSTIC_TARGET_BUNDLE["expected_panel_id"],
        "expected_execution_profile": DIAGNOSTIC_TARGET_BUNDLE[
            "expected_execution_profile"
        ],
        "expected_model_family": DIAGNOSTIC_TARGET_BUNDLE[
            "expected_model_family"
        ],
        "expected_selected_c": DIAGNOSTIC_TARGET_BUNDLE["expected_selected_c"],
        "expected_model_id": DIAGNOSTIC_TARGET_BUNDLE["expected_model_id"],
        "expected_protocol_id": DIAGNOSTIC_TARGET_BUNDLE["expected_protocol_id"],
        "expected_model_version": DIAGNOSTIC_TARGET_BUNDLE[
            "expected_model_version"
        ],
    }
    for name, expected in frozen.items():
        _require(
            record.get(name) == expected,
            "diagnostic_scope_registry_entry_invalid",
            f"Trusted scope field '{name}' does not bind the single accepted "
            "Cleveland bundle; a broader registry entry is refused.",
            field=name,
        )
    return dict(record)


def _git(repo_root: Path, args: list[str]) -> subprocess.CompletedProcess[Any]:
    return subprocess.run(
        ["git", *args],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        check=False,
    )


def _git_bytes(
    repo_root: Path, args: list[str]
) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        ["git", *args],
        cwd=str(repo_root),
        capture_output=True,
        check=False,
    )


def _committed_source(repo_root: Path, revision: str) -> bytes:
    """Read the exact tracked bytes of the registry file at ``revision``."""
    proc = _git_bytes(
        repo_root, ["show", f"{revision}:{DIAGNOSTIC_ACTIVATION_REGISTRY_RELATIVE_PATH}"]
    )
    _require(
        proc.returncode == 0,
        "diagnostic_activation_git_evidence_unavailable",
        "Could not read the committed activation registry source via git.",
        field=DIAGNOSTIC_ACTIVATION_REGISTRY_RELATIVE_PATH,
    )
    return proc.stdout


_REGISTRY_MASK: Final[bytes] = b"__DIAGNOSTIC_ACTIVATION_RECORD__"


def _registry_value_span(source: bytes) -> tuple[ast.Dict, int, int]:
    """Locate the single literal registry assignment and its byte span."""
    try:
        tree = ast.parse(source.decode("utf-8"))
    except (UnicodeDecodeError, SyntaxError, ValueError) as exc:
        raise DiagnosticScopeError(
            "diagnostic_registry_source_unparsable",
            "The committed activation registry source is not parseable Python.",
            field=DIAGNOSTIC_ACTIVATION_REGISTRY_RELATIVE_PATH,
        ) from exc
    found: list[ast.Dict] = []
    for node in tree.body:
        if (
            isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
            and node.targets[0].id == DIAGNOSTIC_REGISTRY_SYMBOL
            and isinstance(node.value, ast.Dict)
        ):
            found.append(node.value)
        elif (
            isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == DIAGNOSTIC_REGISTRY_SYMBOL
            and isinstance(node.value, ast.Dict)
        ):
            found.append(node.value)
    _require(
        len(found) == 1,
        "diagnostic_registry_source_unparsable",
        "The committed registry source must contain exactly one literal dict "
        f"assignment to {DIAGNOSTIC_REGISTRY_SYMBOL}.",
        field=DIAGNOSTIC_REGISTRY_SYMBOL,
    )
    value = found[0]
    # ast line/column offsets are UTF-8 BYTE offsets, so splice on bytes.
    lines = source.splitlines(keepends=True)
    try:
        start = sum(len(line) for line in lines[: value.lineno - 1]) + value.col_offset
        end = (
            sum(len(line) for line in lines[: value.end_lineno - 1])
            + value.end_col_offset
        )
    except (IndexError, TypeError, AttributeError) as exc:
        raise DiagnosticScopeError(
            "diagnostic_registry_source_unparsable",
            "Could not resolve the registry assignment source span.",
            field=DIAGNOSTIC_REGISTRY_SYMBOL,
        ) from exc
    _require(
        0 <= start < end <= len(source),
        "diagnostic_registry_source_unparsable",
        "The registry assignment source span is out of bounds.",
        field=DIAGNOSTIC_REGISTRY_SYMBOL,
    )
    return value, start, end


def _parse_committed_registry(source: bytes) -> tuple[dict[str, Any], bytes]:
    """Return (literal registry, source with ONLY the registry value masked)."""
    value, start, end = _registry_value_span(source)
    try:
        literal = ast.literal_eval(value)
    except (ValueError, TypeError, SyntaxError, MemoryError, RecursionError) as exc:
        raise DiagnosticScopeError(
            "diagnostic_registry_literal_invalid",
            "The committed activation registry must be a plain literal dict "
            "(no names, calls, or computed values).",
            field=DIAGNOSTIC_REGISTRY_SYMBOL,
        ) from exc
    _require(
        isinstance(literal, dict),
        "diagnostic_registry_literal_invalid",
        "The committed activation registry literal must be a dict.",
        field=DIAGNOSTIC_REGISTRY_SYMBOL,
    )
    masked = source[:start] + _REGISTRY_MASK + source[end:]
    return literal, masked


def _changed_paths(repo_root: Path, first: str, second: str) -> list[str]:
    proc = _git(
        repo_root, ["diff", "--name-only", "--no-renames", first, second, "--"]
    )
    _require(
        proc.returncode == 0,
        "diagnostic_activation_git_evidence_unavailable",
        "Could not inspect a committed diff via git.",
        field="repo_root",
    )
    return sorted(
        line.strip().replace("\\", "/")
        for line in proc.stdout.splitlines()
        if line.strip()
    )


def _verify_activation_revision_binding(
    *,
    repo_root: Path,
    governance_baseline: str,
    implementation_revision: str,
    activation_revision: str,
    governance_document_relative_path: str,
    governance_document_sha256: str,
    scope_id: str,
) -> str:
    """Prove a realizable G2 -> A2 registry-only activation; return resolved HEAD.

    The tracked registry at A2 contains only previously known values. A2 itself
    is supplied by the ignored local operator authorization and is checked
    against the independently resolved Git HEAD. No tracked field names A2.
    """
    root = Path(repo_root)

    # 1. HEAD is resolved by git, never accepted from a caller or manifest.
    head_proc = _git(root, ["rev-parse", "HEAD"])
    head = head_proc.stdout.strip().lower() if head_proc.returncode == 0 else ""
    _require(
        bool(_GIT_SHA_RE.fullmatch(head)) and head == activation_revision,
        "diagnostic_activation_revision_mismatch",
        "Independently resolved HEAD does not equal the locally declared A2 "
        "activation revision; refusing to execute.",
        field="activation_merge_commit_sha",
    )

    # 2. Clean tracked worktree (staged, unstaged, and status).
    status_proc = _git(root, ["status", "--porcelain", "--untracked-files=no"])
    _require(
        status_proc.returncode == 0 and not status_proc.stdout.strip(),
        "diagnostic_worktree_not_clean",
        "Tracked worktree files are not clean at the A2 activation revision.",
        field="repo_root",
    )
    for args in (["diff", "--quiet"], ["diff", "--cached", "--quiet"]):
        quiet = _git(root, args)
        _require(
            quiet.returncode == 0,
            "diagnostic_worktree_not_clean",
            "Tracked worktree or index contains uncommitted changes at A2.",
            field="repo_root",
        )

    # 3. I2 (approved implementation) and G2 (governance baseline) exist.
    for label, sha, missing_code in (
        ("approved implementation revision I2", implementation_revision,
         "diagnostic_implementation_baseline_missing"),
        ("governance baseline G2", governance_baseline,
         "diagnostic_governance_baseline_missing"),
    ):
        cat = _git(root, ["cat-file", "-e", f"{sha}^{{commit}}"])
        _require(
            cat.returncode == 0,
            missing_code,
            f"The trusted {label} is absent from local Git history.",
            field=sha[:12],
        )

    # 4. I2 is an ancestor of G2 and only documentation changed in between:
    #    the executing implementation is the reviewed implementation.
    impl_ancestor = _git(
        root, ["merge-base", "--is-ancestor", implementation_revision, governance_baseline]
    )
    _require(
        impl_ancestor.returncode == 0,
        "diagnostic_implementation_ancestry_failed",
        "The approved implementation revision I2 is not an ancestor of the "
        "governance baseline G2.",
        field="approved_implementation_commit_sha",
    )
    impl_to_baseline = _changed_paths(root, implementation_revision, governance_baseline)
    _require(
        all(
            path.startswith(DIAGNOSTIC_IMPLEMENTATION_DOCUMENT_ONLY_PREFIX)
            for path in impl_to_baseline
        ),
        "diagnostic_implementation_modified_after_approval",
        "Implementation code changed between the approved implementation "
        "revision I2 and the governance baseline G2.",
        field="approved_implementation_commit_sha",
    )

    # 5. G2 is an ancestor of the executing HEAD (A2).
    ancestor = _git(root, ["merge-base", "--is-ancestor", governance_baseline, head])
    _require(
        ancestor.returncode == 0,
        "diagnostic_governance_ancestry_failed",
        "The trusted governance baseline G2 is not an ancestor of HEAD.",
        field="governance_baseline_commit_sha",
    )

    # 6. G2 -> A2 changed ONLY ai/diagnostic_scope.py, as a modification.
    name_status = _git(
        root, ["diff", "--name-status", "--no-renames", governance_baseline, head, "--"]
    )
    _require(
        name_status.returncode == 0,
        "diagnostic_activation_git_evidence_unavailable",
        "Could not inspect the governance-to-activation diff via git.",
        field="repo_root",
    )
    diff_lines = [line for line in name_status.stdout.splitlines() if line.strip()]
    _require(
        diff_lines
        == [f"M\t{DIAGNOSTIC_ACTIVATION_REGISTRY_RELATIVE_PATH}"],
        "diagnostic_activation_diff_not_registry_only",
        "The G2 -> A2 diff is not exactly one modification of "
        f"{DIAGNOSTIC_ACTIVATION_REGISTRY_RELATIVE_PATH}; training, inference, "
        "CLI, security or unrelated changes are prohibited in the activation commit.",
        field=DIAGNOSTIC_ACTIVATION_REGISTRY_RELATIVE_PATH,
    )

    # 7. The content change inside that file is EXACTLY the registry activation.
    baseline_source = _committed_source(root, governance_baseline)
    head_source = _committed_source(root, head)
    baseline_literal, baseline_masked = _parse_committed_registry(baseline_source)
    head_literal, head_masked = _parse_committed_registry(head_source)
    _require(
        baseline_literal == {},
        "diagnostic_registry_baseline_not_empty",
        "The registry at G2 must be empty; activation is a single "
        "unactivated -> one-record transition, not a rewrite of an old scope.",
        field="governance_baseline_commit_sha",
    )
    _require(
        set(head_literal) == {scope_id},
        "diagnostic_registry_activation_not_single_scope",
        "The committed A2 registry must contain exactly the single ratified scope.",
        field=DIAGNOSTIC_REGISTRY_SYMBOL,
    )
    _require(
        baseline_masked == head_masked,
        "diagnostic_registry_content_change_unapproved",
        "The activation commit modified code other than the registry value "
        "inside ai/diagnostic_scope.py; security/validation logic must not change.",
        field=DIAGNOSTIC_ACTIVATION_REGISTRY_RELATIVE_PATH,
    )
    _require(
        dict(head_literal) == dict(RATIFIED_DIAGNOSTIC_INFERENCE_SCOPES),
        "diagnostic_registry_live_state_mismatch",
        "The in-process trusted registry does not equal the literal registry "
        "committed at HEAD; runtime registry injection is refused.",
        field=DIAGNOSTIC_REGISTRY_SYMBOL,
    )
    # Belt-and-braces: the tracked registry source at A2 must not contain the
    # A2 commit SHA anywhere (field, comment, or string). A2 is local-only.
    _require(
        head.encode("ascii") not in head_source,
        "diagnostic_scope_registry_self_referential",
        "The tracked activation registry source contains its own A2 commit "
        "SHA; the self-referential activation design is prohibited.",
        field=DIAGNOSTIC_ACTIVATION_REGISTRY_RELATIVE_PATH,
    )

    # 8. The ratified governance document's EXACT bytes at G2.
    doc_proc = _git_bytes(
        root, ["show", f"{governance_baseline}:{governance_document_relative_path}"]
    )
    _require(
        doc_proc.returncode == 0,
        "diagnostic_governance_document_missing",
        "The ratified governance document is absent at the G2 baseline commit.",
        field="governance_document_relative_path",
    )
    actual_doc_sha = hashlib.sha256(doc_proc.stdout).hexdigest()
    _require(
        actual_doc_sha == governance_document_sha256,
        "diagnostic_governance_document_hash_mismatch",
        "The governance document bytes at G2 do not match the frozen ratified "
        "SHA-256.",
        field="frozen_governance_document_sha256",
    )
    return head


def validate_diagnostic_scope(
    doc: Mapping[str, Any], *, repo_root: Path = REPOSITORY_ROOT
) -> DiagnosticScopeContext:
    """Verify the independently ratified scope and its realizable activation.

    Fails closed FIRST on the empty trusted registry (no Git, bundle, or model
    work is attempted). Then checks every local authorization claim against the
    reviewed registry record, and independently verifies local Git evidence for
    the G2 -> A2 registry-only activation:

    * I2 (approved implementation) is an ancestor of G2 with only documentation
      changed in between;
    * G2 (governance baseline) exists, is an ancestor of HEAD, and carries the
      exact ratified governance-document bytes;
    * HEAD is resolved by git and equals A2 from the ignored local operator
      authorization, with a clean tracked worktree;
    * the G2 -> A2 diff modifies only ``ai/diagnostic_scope.py``, and the only
      change inside it is the empty-registry -> one-record activation;
    * the literal registry committed at HEAD equals the in-process registry.

    A2 is NEVER stored in a tracked file, so no commit needs to contain its own
    SHA. GitHub comment authenticity, PR merged state, human intent, and
    signature authority remain human-only evidence; see the scope document.
    """
    _require(
        isinstance(doc, Mapping),
        "diagnostic_authorization_must_be_mapping",
        "Local authorization must be a mapping.",
        field="authorization",
    )
    scope_id = str(doc.get("scope_id", "")).strip()
    _require(
        scope_id in RATIFIED_DIAGNOSTIC_INFERENCE_SCOPES,
        "diagnostic_scope_not_ratified",
        "No independently ratified scope for real-bundle diagnostic inference "
        "exists in the trusted registry. The accepted Cleveland bundle remains "
        "inference-prohibited; training authorization and post-run acceptance "
        "do not authorize inference. No bundle was verified or loaded.",
        field="scope_id",
    )
    trusted = _validated_trusted_record(
        RATIFIED_DIAGNOSTIC_INFERENCE_SCOPES[scope_id], scope_id=scope_id
    )

    # Every claim that CAN be checked against the reviewed tracked record is
    # checked. ``activation_merge_commit_sha`` (A2) is deliberately absent: it
    # is local-only evidence and is verified against independently resolved HEAD.
    comparisons: tuple[tuple[str, Any, Any], ...] = (
        ("governance_pr_number", doc.get("governance_pr_number"),
         trusted["governance_pr_number"]),
        ("governance_baseline_commit_sha",
         _lower_sha(doc.get("governance_baseline_commit_sha")),
         _lower_sha(trusted["governance_baseline_commit_sha"])),
        ("approved_implementation_commit_sha",
         _lower_sha(doc.get("approved_implementation_commit_sha")),
         _lower_sha(trusted["approved_implementation_commit_sha"])),
        ("activation_registry_relative_path",
         doc.get("activation_registry_relative_path"),
         DIAGNOSTIC_ACTIVATION_REGISTRY_RELATIVE_PATH),
        ("governance_document_relative_path",
         doc.get("governance_document_relative_path"),
         trusted["governance_document_relative_path"]),
        ("frozen_governance_document_sha256",
         _lower_sha(doc.get("frozen_governance_document_sha256")),
         _lower_sha(trusted["frozen_governance_document_sha256"])),
        ("ratified_by", doc.get("ratified_by"), trusted["ratified_by"]),
        ("ratification_comment_exact", doc.get("ratification_comment_exact"),
         trusted["ratification_comment_exact"]),
        ("approved_operations", tuple(doc.get("approved_operations", ())),
         DIAGNOSTIC_ALLOWED_OPERATIONS),
        ("bundle_identity.expected_manifest_sha256",
         _lower_sha(doc.get("bundle_identity", {}).get("expected_manifest_sha256"))
         if isinstance(doc.get("bundle_identity"), Mapping) else None,
         _lower_sha(trusted["expected_manifest_sha256"])),
    )
    for name, actual, expected in comparisons:
        _require(
            actual == expected,
            "diagnostic_scope_claim_mismatch",
            f"Local authorization field '{name}' does not match the independently "
            "ratified scope record; self-declared scope is not authorization.",
            field=name,
        )

    g2 = _lower_sha(trusted["governance_baseline_commit_sha"])
    i2 = _lower_sha(trusted["approved_implementation_commit_sha"])
    a2 = _lower_sha(doc.get("activation_merge_commit_sha"))
    doc_rel = str(trusted["governance_document_relative_path"])
    doc_sha = _lower_sha(trusted["frozen_governance_document_sha256"])
    _require(
        bool(_GIT_SHA_RE.fullmatch(a2)),
        "diagnostic_git_evidence_malformed",
        "activation_merge_commit_sha (A2) must be a 40-hex lowercase Git SHA.",
        field="activation_merge_commit_sha",
    )
    head = _verify_activation_revision_binding(
        repo_root=Path(repo_root),
        governance_baseline=g2,
        implementation_revision=i2,
        activation_revision=a2,
        governance_document_relative_path=doc_rel,
        governance_document_sha256=doc_sha,
        scope_id=scope_id,
    )

    return DiagnosticScopeContext(
        scope_id=scope_id,
        governance_pr_number=int(trusted["governance_pr_number"]),
        governance_baseline_commit_sha=g2,
        approved_implementation_commit_sha=i2,
        activation_merge_commit_sha=head,
        governance_document_relative_path=doc_rel,
        frozen_governance_document_sha256=doc_sha,
        ratified_by=str(trusted["ratified_by"]),
        expected_manifest_sha256=_lower_sha(trusted["expected_manifest_sha256"]),
        expected_bundle_dir_name=str(trusted["expected_bundle_dir_name"]),
        expected_source_sha256=_lower_sha(trusted["expected_source_sha256"]),
        expected_dataset_id=str(trusted["expected_dataset_id"]),
        expected_panel_id=str(trusted["expected_panel_id"]),
        expected_execution_profile=str(trusted["expected_execution_profile"]),
        expected_model_family=str(trusted["expected_model_family"]),
        expected_selected_c=float(trusted["expected_selected_c"]),
        expected_model_id=str(trusted["expected_model_id"]),
        expected_protocol_id=str(trusted["expected_protocol_id"]),
        expected_model_version=str(trusted["expected_model_version"]),
        approved_operations=DIAGNOSTIC_ALLOWED_OPERATIONS,
    )


def authorize_diagnostic_scope(
    doc: Mapping[str, Any],
    *,
    repo_root: Path = REPOSITORY_ROOT,
    operator_confirmation: str | None,
) -> DiagnosticScopeContext:
    """Run BOTH authorization gates; either failing closes the interface."""
    validate_local_authorization(doc, operator_confirmation=operator_confirmation)
    return validate_diagnostic_scope(doc, repo_root=repo_root)


__all__ = [
    "DIAGNOSTIC_ACTIVATION_REGISTRY_RELATIVE_PATH",
    "DIAGNOSTIC_ALLOWED_OPERATIONS",
    "DIAGNOSTIC_AUTHORIZATION_SCHEMA_VERSION",
    "DIAGNOSTIC_GOVERNANCE_DOCUMENT_RELATIVE_PATH",
    "DIAGNOSTIC_INTERFACE_VERSION",
    "DIAGNOSTIC_REGISTRY_SYMBOL",
    "DIAGNOSTIC_MAX_RECORDS",
    "DIAGNOSTIC_OPERATOR_CONFIRMATION",
    "DIAGNOSTIC_SCOPE_ACTIVATION_TEMPLATE",
    "DIAGNOSTIC_SCOPE_ID",
    "DIAGNOSTIC_TARGET_BUNDLE",
    "FROZEN_GOVERNANCE_MERGE_G",
    "FROZEN_TRAINING_AMENDMENT_ID",
    "FROZEN_TRAINING_REVISION_A",
    "RATIFIED_DIAGNOSTIC_INFERENCE_SCOPES",
    "DiagnosticScopeContext",
    "DiagnosticScopeError",
    "authorize_diagnostic_scope",
    "load_diagnostic_authorization",
    "validate_diagnostic_scope",
    "validate_local_authorization",
]
