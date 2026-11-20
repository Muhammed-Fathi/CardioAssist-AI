"""RH-04.6 demo-card mapping validator (offline, synthetic-fixture only).

The versioned JSON mapping beside this module is a small consumer handoff, not
an API adapter.  It binds its 29 cards to the reviewed RH-04 offline fixture
pack and defines a fifth, deliberately separate ``MOCK_SYNTHETIC`` HTTP
presentation.  The validator is stdlib-only: it loads checked-in JSON/YAML
artifacts, performs no inference, opens no network connection, and never loads
an artifact, key, dataset, or patient record.

In particular, this module does *not* import ``ai``, ``backend`` or the offline
fixture replay module.  That keeps the mapping check suitable for backend CI
without importing the research/ML stack.  The existing experiment fixture test
is responsible for executing the offline facade; this validator makes sure a
consumer cannot relabel that fixture projection as the mock HTTP contract.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Final, Mapping, Sequence

PACKAGE_ROOT: Final[Path] = Path(__file__).resolve().parent
REPO_ROOT: Final[Path] = PACKAGE_ROOT.parent.parent
MAPPING_PATH: Final[Path] = PACKAGE_ROOT / "fixtures" / "offline_demo_cards.v1.json"
OFFLINE_PACK_PATH: Final[Path] = PACKAGE_ROOT / "fixtures" / "offline_io.v1.json"
MOCK_OPENAPI_PATH: Final[Path] = REPO_ROOT / "shared" / "contracts" / "openapi.yaml"
MOCK_FIXTURES_DIR: Final[Path] = REPO_ROOT / "shared" / "contracts" / "fixtures"
MOCK_FIXTURE_INDEX_PATH: Final[Path] = MOCK_FIXTURES_DIR / "index.json"
MOCK_STATIC_FIXTURE_ID: Final[str] = "F-01"
MOCK_STATIC_FIXTURE_FILE: Final[str] = "F-01-cad-tabular-valid-mock-clinical-v1.json"
MOCK_STATIC_FIXTURE_PATH: Final[Path] = MOCK_FIXTURES_DIR / MOCK_STATIC_FIXTURE_FILE
MOCK_STATIC_EXPECTED_STATUS: Final[int] = 200
MOCK_STATIC_MODEL_ID: Final[str] = "mock_model_a_v0.1.0"
MOCK_STATIC_FEATURE_SCHEMA_ID: Final[str] = "mock_clinical_v1"
MOCK_MODEL_REGISTRY_PATH: Final[Path] = (
    REPO_ROOT / "shared" / "contracts" / "registry" / "mock_model_registry.v1.json"
)
MOCK_CAD_RESPONSE_SCHEMA_PATH: Final[Path] = (
    REPO_ROOT
    / "shared"
    / "contracts"
    / "schemas"
    / "cad_tabular_prediction.response.schema.json"
)

SCHEMA_VERSION: Final[str] = "cardioassist.offline_demo_card_mapping/v1"
MAPPING_VERSION: Final[str] = "1.0.1"
OFFLINE_PRESENTATION_ID: Final[str] = "offline_research_fixture_pack_v1"
MOCK_PRESENTATION_ID: Final[str] = "approved_mock_http_v1"
PERSISTENT_WARNING: Final[str] = "Synthetic research fixture — not clinical"
OFFLINE_STATUSES: Final[tuple[str, ...]] = (
    "SYNTHETIC_RESULT",
    "ABSTAIN",
    "UNAVAILABLE",
    "ERROR",
)
MOCK_DATA_CLASS: Final[str] = "MOCK_SYNTHETIC"
MOCK_CAD_ENDPOINT: Final[str] = "POST /v1/predictions/cad-tabular"

# These are presentation paths, not JSON-schema paths.  Consumers must select
# only listed values from the safe, already-redacted offline fixture projection
# or from the approved mock HTTP response.  The list intentionally excludes
# submitted features, record identities, raw scores/log-odds, explanations,
# artifact provenance, local locations, and key material.
STATUS_ALLOWED_FIELDS: Final[Mapping[str, tuple[str, ...]]] = {
    "SYNTHETIC_RESULT": (
        "status",
        "route_id",
        "panel_id",
        "dataset_id",
        "evidence_level",
        "outcomes.status",
        "outcomes.score.score_kind",
        "outcomes.score.score_interpretation",
        "outcomes.score.calibrated_research_score",
    ),
    "ABSTAIN": (
        "status",
        "route_id",
        "panel_id",
        "dataset_id",
        "evidence_level",
        "outcomes.status",
        "outcomes.abstention_reason",
        "outcomes.missing_fields_with_reason",
    ),
    "UNAVAILABLE": (
        "status",
        "route_id",
        "panel_id",
        "dataset_id",
        "evidence_level",
        "error.code",
        "error.message",
    ),
    "ERROR": (
        "status",
        "error.code",
        "error.message",
        "outcomes.status",
        "outcomes.error.code",
        "outcomes.error.message",
    ),
}

STATUS_REFUSAL_REASON_FIELDS: Final[Mapping[str, tuple[str, ...]]] = {
    "SYNTHETIC_RESULT": (),
    "ABSTAIN": (
        "outcomes.abstention_reason",
        "outcomes.missing_fields_with_reason",
    ),
    "UNAVAILABLE": ("error.code",),
    "ERROR": ("error.code", "outcomes.error.code"),
}

STATUS_BEHAVIORS: Final[Mapping[str, Mapping[str, str]]] = {
    "SYNTHETIC_RESULT": {
        "safe_label": "Synthetic research result",
        "blocked_state_behavior": "Enable only the synthetic research fixture card; never promote it to a clinical result.",
        "error_behavior": "Clear a stale refusal before rendering this fixture result; retain the persistent warning.",
        "numeric_rendering": "A calibrated research score may be shown only as a neutral decimal labelled synthetic research score; never add a percent sign, risk band, prognosis, or advice.",
    },
    "ABSTAIN": {
        "safe_label": "No synthetic research score",
        "blocked_state_behavior": "Disable the result value; show the registered missing-field reason without imputation, retry, or fallback.",
        "error_behavior": "Keep this policy abstention distinct from ERROR and do not manufacture a score.",
        "numeric_rendering": "Do not render a numeric score, percentage, threshold, or risk band.",
    },
    "UNAVAILABLE": {
        "safe_label": "Synthetic research route unavailable",
        "blocked_state_behavior": "Render a disabled card with the registered refusal code; do not retry, load an artifact, or switch routes.",
        "error_behavior": "Clear prior result values and show only the static registered unavailable reason.",
        "numeric_rendering": "Do not render a numeric score, percentage, threshold, or risk band.",
    },
    "ERROR": {
        "safe_label": "Synthetic research fixture refused",
        "blocked_state_behavior": "Clear the result card and block fallback, artifact access, and route substitution.",
        "error_behavior": "Show only the static refusal code/message; never echo a request, exception detail, local location, or key material.",
        "numeric_rendering": "Do not render a numeric score, percentage, threshold, or risk band.",
    },
}

MOCK_ALLOWED_FIELDS: Final[tuple[str, ...]] = (
    "data_class",
    "track",
    "model_id",
    "feature_schema_id",
    "score.type",
    "score.scale",
    "score.rendering.display_unit",
    "score.rendering.percent_sign_allowed",
    "score.rendering.label",
    "score.rendering.absolute_population_probability_claim",
    "missing_features",
    "warnings",
    "validation_status",
    "review_state",
    "provenance.dataset_access_status",
    "disclaimer",
)

# Every item below is disallowed as a display value.  Prefix comparison closes
# a common loophole where a consumer might attempt to allow a child of a
# sensitive object (for example ``records.features`` or ``artifact.path``).
FORBIDDEN_DISPLAY_FIELDS: Final[tuple[str, ...]] = (
    "records",
    "features",
    "context",
    "patient_ref",
    "record_ref",
    "request_id",
    "audit_id",
    "generated_at",
    "units",
    "missing_reasons",
    "artifact",
    "model_source",
    "bundle_dir",
    "trusted_local_root",
    "signing_key",
    "private_key",
    "local_path",
    "path",
    "model_loader",
    "explanation",
    "outcomes.shap",
    "outcomes.lime",
    "outcomes.uncertainty",
    "outcomes.score.raw_model_score",
    "outcomes.score.raw_model_log_odds",
    "outcomes.score.calibrated_log_odds",
    "outcomes.score.exploratory_above_threshold_flag",
    "outcomes.score.exploratory_threshold",
    "score.value",
    "score.raw_margin",
    "score.calibration",
    "target",
    "model_performance_ref",
    "provenance.artifact_hashes",
    "clinical_probability_claim",
    "medical_advice",
    "unvalidated_performance_claim",
)


class DemoCardMappingError(ValueError):
    """Raised when a demo-card map is stale, ambiguous, or unsafe."""


def _fail(message: str) -> None:
    raise DemoCardMappingError(message)


def _canonical_sha256(payload: Any) -> str:
    encoded = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
    )
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _bytes_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise DemoCardMappingError(f"Could not read checked-in mapping source: {path.name}") from exc


def _mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        _fail(f"{label} must be an object.")
    return value


def _string(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value:
        _fail(f"{label} must be a non-empty string.")
    return value


def _string_list(value: Any, label: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not all(isinstance(item, str) and item for item in value):
        _fail(f"{label} must be a list of non-empty strings.")
    if len(set(value)) != len(value):
        _fail(f"{label} must not contain duplicates.")
    return tuple(value)


def _exact_keys(value: Mapping[str, Any], expected: set[str], label: str) -> None:
    if set(value) != expected:
        _fail(f"{label} members are not the reviewed exact set.")


def _paths_overlap(first: str, second: str) -> bool:
    return first == second or first.startswith(second + ".") or second.startswith(first + ".")


def _assert_safe_allowed_fields(fields: Sequence[str], label: str) -> None:
    for field in fields:
        if any(_paths_overlap(field, forbidden) for forbidden in FORBIDDEN_DISPLAY_FIELDS):
            _fail(f"{label} permits forbidden display field '{field}'.")


def _source_digests() -> dict[str, str]:
    pack = _read_json(OFFLINE_PACK_PATH)
    pack_map = _mapping(pack, "offline fixture pack")
    bindings = _mapping(pack_map.get("bindings"), "offline fixture pack bindings")
    return {
        "offline_fixture_pack_canonical_sha256": _canonical_sha256(pack_map),
        "offline_fixture_pack_bytes_sha256": _bytes_sha256(OFFLINE_PACK_PATH),
        "offline_fixture_pack_registry_sha256": _string(
            bindings.get("registry_sha256"), "offline fixture pack bindings.registry_sha256"
        ),
        "offline_fixture_pack_crosswalk_sha256": _string(
            bindings.get("crosswalk_sha256"), "offline fixture pack bindings.crosswalk_sha256"
        ),
        "mock_openapi_bytes_sha256": _bytes_sha256(MOCK_OPENAPI_PATH),
        "mock_fixture_index_bytes_sha256": _bytes_sha256(MOCK_FIXTURE_INDEX_PATH),
        "mock_model_registry_bytes_sha256": _bytes_sha256(MOCK_MODEL_REGISTRY_PATH),
        "mock_f01_fixture_bytes_sha256": _bytes_sha256(MOCK_STATIC_FIXTURE_PATH),
    }


def _assert_mock_contract_still_approved(static_fixture: Mapping[str, Any]) -> None:
    """Bind the fifth card to F-01 without reading or exposing its request body."""
    openapi_text = MOCK_OPENAPI_PATH.read_text(encoding="utf-8")
    if MOCK_CAD_ENDPOINT.split(" ", 1)[1] + ":" not in openapi_text:
        _fail("Approved mock CAD endpoint is absent from OpenAPI.")
    fixture_index = _mapping(_read_json(MOCK_FIXTURE_INDEX_PATH), "mock fixture index")
    registry = _mapping(_read_json(MOCK_MODEL_REGISTRY_PATH), "mock model registry")
    response_schema = _mapping(
        _read_json(MOCK_CAD_RESPONSE_SCHEMA_PATH), "mock CAD response schema"
    )
    if fixture_index.get("data_class") != MOCK_DATA_CLASS:
        _fail("Approved mock fixture index no longer declares MOCK_SYNTHETIC.")
    if registry.get("data_class") != MOCK_DATA_CLASS or registry.get("status") != "MOCK_ONLY":
        _fail("Approved mock registry is not MOCK_SYNTHETIC/MOCK_ONLY.")
    if '"MOCK_SYNTHETIC"' not in json.dumps(response_schema, sort_keys=True):
        _fail("Approved mock response schema does not pin MOCK_SYNTHETIC.")

    _exact_keys(
        static_fixture,
        {
            "fixture_id",
            "file",
            "endpoint",
            "expected_http_status",
            "model_id",
            "feature_schema_id",
            "data_class",
            "static_display_only",
        },
        "approved_mock_fixture",
    )
    expected_binding: Mapping[str, Any] = {
        "fixture_id": MOCK_STATIC_FIXTURE_ID,
        "file": MOCK_STATIC_FIXTURE_FILE,
        "endpoint": MOCK_CAD_ENDPOINT,
        "expected_http_status": MOCK_STATIC_EXPECTED_STATUS,
        "model_id": MOCK_STATIC_MODEL_ID,
        "feature_schema_id": MOCK_STATIC_FEATURE_SCHEMA_ID,
        "data_class": MOCK_DATA_CLASS,
        "static_display_only": True,
    }
    if dict(static_fixture) != expected_binding:
        _fail("The mock presentation must select the reviewed static F-01 binding exactly.")

    indexed = fixture_index.get("fixtures")
    if not isinstance(indexed, list):
        _fail("Approved mock fixture index has no fixture list.")
    matches = [
        _mapping(entry, "approved mock fixture index entry")
        for entry in indexed
        if isinstance(entry, Mapping) and entry.get("fixture_id") == MOCK_STATIC_FIXTURE_ID
    ]
    if len(matches) != 1:
        _fail("The reviewed mock fixture id is absent or ambiguous in the approved index.")
    catalog_entry = matches[0]
    if (
        catalog_entry.get("file") != MOCK_STATIC_FIXTURE_FILE
        or catalog_entry.get("endpoint") != MOCK_CAD_ENDPOINT
        or catalog_entry.get("expected_status") != MOCK_STATIC_EXPECTED_STATUS
    ):
        _fail("The approved fixture index no longer binds F-01 to its reviewed contract.")

    # Construct the file path only from the hard-wired reviewed catalog value.
    # A mapping field therefore cannot select an absolute path or traverse out
    # of the approved fixture directory.
    catalog_path = MOCK_FIXTURES_DIR / MOCK_STATIC_FIXTURE_FILE
    if catalog_path != MOCK_STATIC_FIXTURE_PATH or not catalog_path.is_file():
        _fail("The reviewed mock fixture file is unavailable.")
    fixture = _mapping(_read_json(catalog_path), "approved F-01 mock fixture")
    if fixture.get("endpoint") != MOCK_CAD_ENDPOINT:
        _fail("The reviewed mock fixture endpoint does not match the mapping.")
    steps = fixture.get("steps")
    if not isinstance(steps, list) or len(steps) != 1:
        _fail("The reviewed mock fixture must contain exactly one static response example.")
    step = _mapping(steps[0], "approved F-01 mock fixture step")
    expected = _mapping(step.get("expected"), "approved F-01 mock fixture expected response")
    body = _mapping(expected.get("body"), "approved F-01 mock fixture response body")
    if expected.get("status") != MOCK_STATIC_EXPECTED_STATUS:
        _fail("The reviewed mock fixture expected HTTP status does not match the mapping.")
    if (
        body.get("data_class") != MOCK_DATA_CLASS
        or body.get("model_id") != MOCK_STATIC_MODEL_ID
        or body.get("feature_schema_id") != MOCK_STATIC_FEATURE_SCHEMA_ID
    ):
        _fail("The reviewed mock fixture response does not match its MOCK_SYNTHETIC binding.")


def _assert_status_rule(status: str, rule: Mapping[str, Any]) -> None:
    _exact_keys(
        rule,
        {
            "safe_label",
            "allowed_display_fields",
            "refusal_reason_fields",
            "blocked_state_behavior",
            "error_behavior",
            "numeric_rendering",
        },
        f"status rule {status}",
    )
    expected_behavior = STATUS_BEHAVIORS[status]
    for name, expected in expected_behavior.items():
        if rule.get(name) != expected:
            _fail(f"status rule {status}.{name} differs from the reviewed safe behavior.")
    allowed = _string_list(rule.get("allowed_display_fields"), f"status rule {status}.allowed_display_fields")
    if allowed != STATUS_ALLOWED_FIELDS[status]:
        _fail(f"status rule {status} allowed fields differ from the reviewed exact set.")
    _assert_safe_allowed_fields(allowed, f"status rule {status}")
    reasons = _string_list(rule.get("refusal_reason_fields"), f"status rule {status}.refusal_reason_fields")
    if reasons != STATUS_REFUSAL_REASON_FIELDS[status]:
        _fail(f"status rule {status} refusal reason fields differ from the reviewed exact set.")
    if not set(reasons).issubset(allowed):
        _fail(f"status rule {status} refusal reason fields must be display allowlisted.")


def _assert_offline_cases(
    cards: Any, pack: Mapping[str, Any], statuses: Mapping[str, Any]
) -> int:
    if not isinstance(cards, list):
        _fail("offline_case_cards must be a list.")
    cases = pack.get("cases")
    if not isinstance(cases, list) or not cases:
        _fail("offline fixture pack cases must be a non-empty list.")
    source_by_id: dict[str, Mapping[str, Any]] = {}
    source_order: list[str] = []
    for source_case in cases:
        source_case_map = _mapping(source_case, "offline fixture case")
        case_id = _string(source_case_map.get("id"), "offline fixture case.id")
        expected = _mapping(source_case_map.get("expected"), f"offline fixture case {case_id}.expected")
        status = _string(expected.get("status"), f"offline fixture case {case_id}.expected.status")
        if status not in statuses:
            _fail(f"offline fixture case {case_id} has an unmapped status.")
        if case_id in source_by_id:
            _fail("offline fixture pack has duplicate case ids.")
        source_by_id[case_id] = source_case_map
        source_order.append(case_id)

    mapped_order: list[str] = []
    for card in cards:
        card_map = _mapping(card, "offline demo card")
        _exact_keys(
            card_map,
            {
                "case_id",
                "status",
                "expected_projection_sha256",
                "presentation_contract_id",
            },
            "offline demo card",
        )
        case_id = _string(card_map.get("case_id"), "offline demo card.case_id")
        mapped_order.append(case_id)
        if card_map.get("presentation_contract_id") != OFFLINE_PRESENTATION_ID:
            _fail("An offline fixture case may only select the offline fixture presentation.")
        source_case = source_by_id.get(case_id)
        if source_case is None:
            _fail(f"Demo card references unknown offline fixture case '{case_id}'.")
        expected = _mapping(source_case["expected"], f"offline fixture case {case_id}.expected")
        if card_map.get("status") != expected.get("status"):
            _fail(f"Demo card status does not match fixture case '{case_id}'.")
        digest = _string(
            card_map.get("expected_projection_sha256"),
            f"offline demo card {case_id}.expected_projection_sha256",
        )
        if digest != _canonical_sha256(expected):
            _fail(f"Demo card expected projection digest is stale for case '{case_id}'.")

    if mapped_order != source_order:
        _fail("Demo cards must map every offline case exactly once in fixture-pack order.")
    return len(cards)


def validate(document: Mapping[str, Any] | None = None) -> int:
    """Validate the map, all 29 fixture bindings, and mock-contract separation.

    Returns the number of linked offline cases.  Any stale source digest,
    missing/renamed case, unsafe display path, status drift, or cross-contract
    mapping raises :class:`DemoCardMappingError` before a consumer can use it.
    """
    if document is None:
        document = _read_json(MAPPING_PATH)
    mapping = _mapping(document, "demo-card mapping")
    _exact_keys(
        mapping,
        {
            "schema_version",
            "mapping_version",
            "artifact_kind",
            "persistent_warning",
            "source_digests",
            "forbidden_display_fields",
            "offline_research",
            "offline_case_cards",
            "mock_synthetic_backend",
        },
        "demo-card mapping",
    )
    if mapping.get("schema_version") != SCHEMA_VERSION:
        _fail("Unsupported demo-card mapping schema version.")
    if mapping.get("mapping_version") != MAPPING_VERSION:
        _fail("Unexpected demo-card mapping version.")
    if mapping.get("artifact_kind") != "OFFLINE_SYNTHETIC_RESEARCH_DEMO_CARD_MAPPING":
        _fail("Demo-card mapping artifact kind is unsafe or unrecognized.")
    if mapping.get("persistent_warning") != PERSISTENT_WARNING:
        _fail("The permanent synthetic-not-clinical warning is missing or changed.")
    forbidden = _string_list(mapping.get("forbidden_display_fields"), "forbidden_display_fields")
    if forbidden != FORBIDDEN_DISPLAY_FIELDS:
        _fail("forbidden_display_fields differs from the reviewed exact safety list.")

    source_digests = _mapping(mapping.get("source_digests"), "source_digests")
    actual_digests = _source_digests()
    if dict(source_digests) != actual_digests:
        _fail("One or more source digests are stale or do not bind approved sources.")

    offline = _mapping(mapping.get("offline_research"), "offline_research")
    _exact_keys(offline, {"presentation_contract_id", "status_rules"}, "offline_research")
    if offline.get("presentation_contract_id") != OFFLINE_PRESENTATION_ID:
        _fail("Offline research presentation id is not the reviewed fixture-only id.")
    statuses = _mapping(offline.get("status_rules"), "offline_research.status_rules")
    if tuple(statuses) != OFFLINE_STATUSES:
        _fail("Offline status rules must contain exactly the four ordered facade statuses.")
    for status in OFFLINE_STATUSES:
        _assert_status_rule(status, _mapping(statuses[status], f"status rule {status}"))

    mock = _mapping(mapping.get("mock_synthetic_backend"), "mock_synthetic_backend")
    _exact_keys(
        mock,
        {
            "presentation_contract_id",
            "data_class",
            "approved_http_contract",
            "approved_mock_fixture",
            "safe_label",
            "allowed_display_fields",
            "blocked_state_behavior",
            "error_behavior",
            "offline_case_links_forbidden",
        },
        "mock_synthetic_backend",
    )
    if mock.get("presentation_contract_id") != MOCK_PRESENTATION_ID:
        _fail("Mock presentation id must stay separate from the offline fixture presentation.")
    if mock.get("data_class") != MOCK_DATA_CLASS:
        _fail("Mock presentation must declare MOCK_SYNTHETIC exactly.")
    if mock.get("approved_http_contract") != MOCK_CAD_ENDPOINT:
        _fail("Mock presentation is not bound to the approved CAD HTTP contract.")
    static_fixture = _mapping(mock.get("approved_mock_fixture"), "approved_mock_fixture")
    if mock.get("safe_label") != "Mock synthetic backend result":
        _fail("Mock presentation safe label is not the reviewed label.")
    mock_allowed = _string_list(mock.get("allowed_display_fields"), "mock allowed_display_fields")
    if mock_allowed != MOCK_ALLOWED_FIELDS:
        _fail("Mock allowed_display_fields differs from the reviewed exact set.")
    _assert_safe_allowed_fields(mock_allowed, "mock presentation")
    if mock.get("blocked_state_behavior") != (
        "No offline status or fixture case may select this mock HTTP card."
    ):
        _fail("Mock blocked-state behavior permits cross-contract selection.")
    if mock.get("error_behavior") != (
        "Use only the approved mock HTTP error code/message and clear prior mock fields."
    ):
        _fail("Mock error behavior is not the reviewed safe behavior.")
    if mock.get("offline_case_links_forbidden") is not True:
        _fail("Mock presentation must forbid links from offline fixture cases.")
    _assert_mock_contract_still_approved(static_fixture)

    pack = _mapping(_read_json(OFFLINE_PACK_PATH), "offline fixture pack")
    return _assert_offline_cases(mapping.get("offline_case_cards"), pack, statuses)


def load_mapping() -> Mapping[str, Any]:
    """Load and fail-closed validate the checked-in mapping before consumer use."""
    document = _read_json(MAPPING_PATH)
    validate(document)
    return document


if __name__ == "__main__":
    print(f"{validate()} offline demo cards verified: {MAPPING_VERSION}")
