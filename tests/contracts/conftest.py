"""Shared pytest fixtures and helpers for the CardioAssist AI contract tests.

The contract tests are deliberately lightweight: they read the committed
contract files and the committed fixture pack, and they never touch the
network, a database, a model artifact or a dataset.
"""

from __future__ import annotations

import json
import pathlib
import sys
from typing import Any, Dict, List, Tuple

import pytest
from jsonschema import Draft202012Validator
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012

TESTS_DIR = pathlib.Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parents[1]
CONTRACTS_DIR = REPO_ROOT / "shared" / "contracts"
SCHEMAS_DIR = CONTRACTS_DIR / "schemas"
REGISTRY_DIR = CONTRACTS_DIR / "registry"
FIXTURES_DIR = CONTRACTS_DIR / "fixtures"

# Make the reference implementation importable without installing the package.
if str(TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(TESTS_DIR))


def load_json(path: pathlib.Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def build_registry() -> Registry:
    """Registry of every local JSON Schema, under both its file URI and its $id."""
    resources: List[Tuple[str, Resource]] = []
    for path in sorted(SCHEMAS_DIR.glob("*.json")):
        document = load_json(path)
        resource = Resource.from_contents(document, default_specification=DRAFT202012)
        resources.append((path.resolve().as_uri(), resource))
        if "$id" in document:
            resources.append((document["$id"], resource))
    return Registry().with_resources(resources)


@pytest.fixture(scope="session")
def registry() -> Registry:
    return build_registry()


@pytest.fixture(scope="session")
def schema_documents() -> Dict[str, Any]:
    return {path.name: load_json(path) for path in sorted(SCHEMAS_DIR.glob("*.json"))}


@pytest.fixture(scope="session")
def openapi_document() -> Dict[str, Any]:
    import yaml

    with (CONTRACTS_DIR / "openapi.yaml").open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


@pytest.fixture(scope="session")
def fixture_index() -> Dict[str, Any]:
    return load_json(FIXTURES_DIR / "index.json")


@pytest.fixture(scope="session")
def fixtures() -> List[Dict[str, Any]]:
    """Every fixture file of the pack, in index order."""
    index = load_json(FIXTURES_DIR / "index.json")
    return [load_json(FIXTURES_DIR / entry["file"]) for entry in index["fixtures"]]


def validator_for(document: Dict[str, Any], registry: Registry) -> Draft202012Validator:
    return Draft202012Validator(
        document,
        registry=registry,
        format_checker=Draft202012Validator.FORMAT_CHECKER,
    )


def sub_validator(
    document: Dict[str, Any], registry: Registry, pointer: str
) -> Draft202012Validator:
    """Validator for a subschema of a root document.

    ``evolve`` keeps the registry and the base URI of the root document, so
    relative ``$ref``s inside the subschema still resolve.
    """
    root = validator_for(document, registry)
    target = document
    for part in pointer.strip("#/").split("/"):
        if part:
            target = target[part]
    return root.evolve(schema=target)


def iter_strings(value: Any, path: str = "") -> List[Tuple[str, str]]:
    """Yield (json-pointer-ish path, string value) for every string in a document."""
    found: List[Tuple[str, str]] = []
    if isinstance(value, dict):
        for key, item in value.items():
            found.extend(iter_strings(item, f"{path}.{key}"))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            found.extend(iter_strings(item, f"{path}[{index}]"))
    elif isinstance(value, str):
        found.append((path, value))
    return found
