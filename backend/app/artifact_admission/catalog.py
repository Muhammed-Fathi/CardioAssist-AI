"""Feature-schema catalogue derived from the approved shared contracts.

The catalogue intentionally reuses ``ContractFiles.feature_schemas`` (the same
mapping the runtime uses to validate CAD requests) and hashes the exact
``shared/contracts/schemas`` file bytes. There is no second, parallel clinical
feature dictionary in the backend or in the descriptor format: names, value
types, units and required flags always come from the pinned shared schema.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any, Mapping

from ..contracts import CONTRACTS_DIR, ContractFiles

SCHEMAS_DIR = CONTRACTS_DIR / "schemas"


@dataclass(frozen=True)
class FeatureSchemaCatalog:
    """Feature-schema documents plus the SHA-256 of their on-disk bytes."""

    schemas: Mapping[str, Mapping[str, Any]]
    digests: Mapping[str, str]

    @classmethod
    def from_shared_contracts(cls, contracts: ContractFiles | None = None) -> "FeatureSchemaCatalog":
        contracts = contracts or ContractFiles()
        schemas: dict[str, Mapping[str, Any]] = dict(contracts.feature_schemas)
        digests: dict[str, str] = {}
        for schema_id, document in schemas.items():
            identifier = str(document.get("$id", ""))
            # Local path handling only: no URL parsing, no retriever.
            filename = identifier.rsplit("/", 1)[-1]
            if not filename:
                raise ValueError(
                    "A shared feature schema is missing a resolvable $id; "
                    "artifact admission cannot pin its digest."
                )
            digests[schema_id] = hashlib.sha256(
                (SCHEMAS_DIR / filename).read_bytes()
            ).hexdigest()
        return cls(schemas=schemas, digests=digests)
