"""Contract tests for the Term 1 C1 surface.

These tests pin the *served* operation inventory and the closed error catalogue
so that the contract source modules under ``shared/contracts/term1/`` cannot
drift from the implementation in ``backend/app/term1/openapi.py`` and
``backend/app/term1/errors.py`` without failing a test.

* 20 C1 + 5 C2 operations, 27 served (2 legacy + 20 C1 + 5 C2).
* ``IDEMPOTENT_C1`` = 10 paths, ``AUTHENTICATED_C1`` = 18 paths.
* Error catalogue: 63 codes (C1 + C2), static messages, statuses consistent between
  ``errors.py::ERROR_CATALOGUE``, ``openapi.py::ERROR_CODES`` and
  ``shared/contracts/term1/errors.yaml``.
* Every schema under ``shared/contracts/term1/schemas/`` is a valid JSON Schema
  draft 2020-12 document.

The C1 path files are machine-readable YAML loaded with the frozen
``paths-*.yaml`` glob; the separately prefixed ``c2-paths-*.yaml`` module is
covered by the C2 contract tests. These files are proposed, not approved, not
deployed — they document the same frozen inventory the server serves.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import jsonschema
import pytest
import yaml

from backend.app.term1 import errors, openapi

# The C1 suite lives at tests/backend/c1/; the repository root is three levels
# up from this test module.
ROOT = Path(__file__).resolve().parents[3]
TERM1_DIR = ROOT / "shared" / "contracts" / "term1"

_OP_RE = re.compile(r"`(GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS) (/v1/[A-Za-z0-9_{}/-]+)`")

# ---------------------------------------------------------------------------
# Operation inventory (20 C1 + 5 C2, 27 served, C1 header sets)
# ---------------------------------------------------------------------------


def _load_paths_modules() -> list[dict]:
    """Load every paths-*.yaml contract module as machine-readable YAML."""
    modules = []
    for path in sorted(TERM1_DIR.glob("paths-*.yaml")):
        data = yaml.safe_load(path.read_text())
        assert isinstance(data, dict), f"{path.name} is not a YAML mapping"
        assert "operations" in data, f"{path.name} has no operations inventory"
        modules.append(data)
    return modules


def _contract_operations() -> set[tuple[str, str]]:
    """Extract declared C1 operations from the structured paths-*.yaml modules."""
    ops: set[tuple[str, str]] = set()
    for data in _load_paths_modules():
        for op in data["operations"]:
            ops.add((op["method"].lower(), op["path"]))
    return ops


def test_all_contract_yaml_is_valid_machine_readable_yaml():
    """Every paths-*.yaml and errors.yaml parses as valid YAML (Markdown is not
    accepted as a substitute for machine-readable contract source)."""
    for path in sorted(TERM1_DIR.glob("*.yaml")):
        yaml.safe_load(path.read_text())


def test_c1_operations_match_contract_modules():
    contract_ops = _contract_operations()
    impl_ops = set(openapi.C1_OPERATIONS)
    assert contract_ops == impl_ops, (
        "contract modules and openapi.py C1_OPERATIONS disagree:\n"
        f"  only in contracts: {sorted(contract_ops - impl_ops)}\n"
        f"  only in openapi.py: {sorted(impl_ops - contract_ops)}"
    )


def test_c1_operation_counts():
    assert len(openapi.C1_OPERATIONS) == 20
    assert len(openapi.SERVED_OPERATIONS) == 27  # 2 legacy + 20 C1 + 5 C2
    assert set(openapi.C1_OPERATIONS) <= set(openapi.SERVED_OPERATIONS)
    # Legacy ops are not C1.
    assert set(openapi.LEGACY_OPERATIONS).isdisjoint(set(openapi.C1_OPERATIONS))


def test_c1_auth_and_idempotency_per_method_and_path():
    """Auth/idempotency requirements are checked per method+path (not merely by
    path count), and every declared requirement is reflected in the served sets."""
    declared: dict[tuple[str, str], dict] = {}
    for data in _load_paths_modules():
        for op in data["operations"]:
            declared[(op["method"].lower(), op["path"])] = op

    # Every declared operation has an explicit authenticated/idempotent flag.
    for (method, path), op in declared.items():
        assert isinstance(op["authenticated"], bool), (method, path)
        assert isinstance(op["idempotent"], bool), (method, path)

    # Served header sets must cover exactly the declared authenticated paths.
    served_auth = {("/v1" + p if not p.startswith("/v1") else p): True
                   for p in openapi.AUTHENTICATED_C1}
    for (method, path), op in declared.items():
        if op["authenticated"]:
            assert path in openapi.AUTHENTICATED_C1, (
                f"{method.upper()} {path} declared authenticated but missing from AUTHENTICATED_C1"
            )
        else:
            assert path not in openapi.AUTHENTICATED_C1, (
                f"{method.upper()} {path} declared anonymous but present in AUTHENTICATED_C1"
            )
        if op["idempotent"]:
            assert path in openapi.IDEMPOTENT_C1, (
                f"{method.upper()} {path} declared idempotent but missing from IDEMPOTENT_C1"
            )
        else:
            assert path not in openapi.IDEMPOTENT_C1, (
                f"{method.upper()} {path} declared non-idempotent but present in IDEMPOTENT_C1"
            )

    assert len(openapi.IDEMPOTENT_C1) == 10
    assert len(openapi.AUTHENTICATED_C1) == 18
    c1_paths = {path for _method, path in openapi.C1_OPERATIONS}
    assert openapi.IDEMPOTENT_C1 <= c1_paths
    assert openapi.AUTHENTICATED_C1 <= c1_paths
    # The only idempotent-but-anonymous C1 operation is patient registration.
    assert openapi.IDEMPOTENT_C1 - openapi.AUTHENTICATED_C1 == {
        "/v1/patients/register"
    }


# ---------------------------------------------------------------------------
# Error catalogue (63 C1 + C2 codes, static messages, status consistency)
# ---------------------------------------------------------------------------


def _load_errors_yaml() -> dict[str, dict]:
    data = yaml.safe_load((TERM1_DIR / "errors.yaml").read_text())
    assert isinstance(data, dict) and "codes" in data
    return data["codes"]


def test_errors_yaml_matches_error_catalogue():
    yaml_codes = _load_errors_yaml()
    # Every catalogue code appears in errors.yaml with the same status/message.
    for code, (status, message) in errors.ERROR_CATALOGUE.items():
        assert code in yaml_codes, f"{code} missing from errors.yaml"
        entry = yaml_codes[code]
        assert entry["status"] == status, (code, status, entry["status"])
        assert entry["message"] == message, (code, message, entry["message"])
    # No extra codes in errors.yaml beyond the closed catalogue.
    assert set(yaml_codes) == set(errors.ERROR_CATALOGUE), (
        set(yaml_codes) ^ set(errors.ERROR_CATALOGUE)
    )


def test_error_codes_closed_and_status_consistent():
    total = 0
    for status, codes in openapi.ERROR_CODES.items():
        for code in codes:
            assert code in errors.ERROR_CATALOGUE, code
            assert str(errors.ERROR_CATALOGUE[code][0]) == status, (code, status)
            total += 1
    assert total == 63
    # Served catalogue covers every catalogue code exactly once per status.
    served = {c for codes in openapi.ERROR_CODES.values() for c in codes}
    assert served == set(errors.ERROR_CATALOGUE)


def test_errors_v1_json_matches_error_codes():
    data = json.loads((TERM1_DIR / "errors.v1.json").read_text())
    assert data["contract_version"] == "v1"
    assert data["source"] == "backend/app/term1/errors.py::ERROR_CATALOGUE"
    assert data["codes"] == {
        code: {"status": status, "message": message}
        for code, (status, message) in errors.ERROR_CATALOGUE.items()
    }
    assert data["served_by_status"] == openapi.ERROR_CODES


# ---------------------------------------------------------------------------
# Schemas under shared/contracts/term1/schemas/
# ---------------------------------------------------------------------------


def _schema_files() -> list[Path]:
    return sorted((TERM1_DIR / "schemas").glob("*.json"))


@pytest.mark.parametrize("path", _schema_files(), ids=lambda p: p.name)
def test_term1_schema_is_valid_draft_2020_12(path: Path):
    data = json.loads(path.read_text())
    # Must be a valid JSON Schema meta-schema.
    jsonschema.Draft202012Validator.check_schema(data)
    assert data["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert data["$id"].startswith("https://cardioassist.local/contracts/term1/schemas/")


def test_all_referenced_schemas_exist():
    """Every component schema key referenced by openapi.py has a file on disk.

    References are operation-specific (request + response schemas) plus the
    shared common components; no generic envelope schemas are referenced.
    """
    referenced = {
        "term1_error.schema.json",
    }
    for _method, path in openapi.C1_OPERATIONS:
        schemas = openapi.OP_SCHEMAS[(_method, path)]
        if schemas["request"] is not None:
            referenced.add(schemas["request"])
        referenced.add(schemas["response"])
    on_disk = {p.name for p in _schema_files()}
    missing = referenced - on_disk
    assert not missing, f"schemas missing for: {sorted(missing)}"
