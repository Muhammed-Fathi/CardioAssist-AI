"""Versioned admission input-order policy for offline artifact descriptors.

Why this module exists
----------------------
An artifact's ML input order is a *contract*, not an accident of serialization.
JSON Schema object property order is **not** normative: it can change with a
formatter, a refactor, or a schema `$defs` reshuffle without any semantic
change. Treating the key order of ``properties`` as the model's input order
would therefore let a reordering slip in silently.

So the approved order is declared here, explicitly, in code, under review —
and it is checked by position: the feature declared at index *i* of a
descriptor must be exactly the feature this policy places at index *i*.
Exchanging the order numbers of two valid features is rejected even though the
resulting index set remains contiguous.

Scope warning — SYNTHETIC ONLY
------------------------------
``synthetic_fixture_input_order/v1`` describes only the **mock fixture**
feature schemas of the current wire contract. It is *not* a clinical feature
dictionary, *not* a scientific input ordering, and *not* the D-047 Cleveland
predictor order (``age, sex, cp, trestbps, restecg``). A real research
pipeline must register its own reviewed order in its own protocol/feature
registry; nothing here may be reused as that authority.

Deliberate design choices:

* the order is unrelated to schema serialization order -- for
  ``mock_clinical_v2`` it intentionally differs from the order in which the
  schema declares its ``properties``;
* no order is inferred for an unknown or future feature schema: admission
  fails closed instead of guessing;
* adding, removing or reordering an entry requires a new policy id and a
  reviewed code change, because descriptors must name the policy id they were
  built against.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping

#: Status reserved for a future clinically reviewed ordering. **No policy with
#: this status exists in this repository**, and nothing here may be relabelled to
#: claim it.
CLINICAL_APPROVED_ORDER_STATUS = "CLINICAL_APPROVED"

SYNTHETIC_FIXTURE_ORDER_POLICY_ID = "synthetic_fixture_input_order/v1"
SYNTHETIC_FIXTURE_ORDER_POLICY_STATUS = "SYNTHETIC_ONLY_NOT_CLINICAL"
SYNTHETIC_FIXTURE_ORDER_POLICY_NOTE = (
    "Mock-fixture admission order only. Not a clinical feature dictionary, not a "
    "scientific input ordering, and not the D-047 Cleveland predictor order."
)


@dataclass(frozen=True, slots=True)
class FeatureOrderPolicy:
    """Explicit ordered feature binding for one or more feature-schema ids.

    ``ordered_feature_names`` maps a shared feature-schema id to the exact
    tuple of feature names in approved input position order.

    Instances are immutable in practice, not only by convention:

    * ``frozen=True`` blocks attribute assignment and ``slots=True`` blocks
      adding new attributes;
    * the mapping is copied into a :class:`types.MappingProxyType` and every
      value into a ``tuple``, so item assignment, ``del``, ``update`` and
      tuple mutation all raise instead of silently changing an order.

    The copy also detaches the instance from the caller's dictionary: mutating
    the original dict afterwards cannot alter this policy.
    """

    policy_id: str
    status: str
    ordered_feature_names: Mapping[str, tuple[str, ...]]
    note: str = ""

    def __post_init__(self) -> None:
        if not self.policy_id or not isinstance(self.policy_id, str):
            raise ValueError("A feature-order policy requires a non-empty policy id.")
        if not self.status or not isinstance(self.status, str):
            raise ValueError("A feature-order policy requires an explicit status.")
        if not isinstance(self.note, str):
            raise ValueError("A feature-order policy note must be a string.")
        if not isinstance(self.ordered_feature_names, Mapping):
            raise ValueError("A feature-order policy requires a schema-id mapping.")

        frozen_order: dict[str, tuple[str, ...]] = {}
        for schema_id, names in self.ordered_feature_names.items():
            if not isinstance(schema_id, str) or not schema_id:
                raise ValueError("Feature-order policy schema ids must be non-empty strings.")
            if isinstance(names, (str, bytes)) or not isinstance(names, (tuple, list)):
                raise ValueError("A registered feature order must be a sequence of names.")
            frozen_names = tuple(names)
            if not frozen_names or not all(isinstance(name, str) and name for name in frozen_names):
                raise ValueError("A registered feature order must be a non-empty list of names.")
            if len(set(frozen_names)) != len(frozen_names):
                raise ValueError("A registered feature order must not repeat a feature name.")
            frozen_order[schema_id] = frozen_names

        # Detach from the caller's objects and make the contents read-only.
        object.__setattr__(self, "ordered_feature_names", MappingProxyType(frozen_order))

    def order_for(self, feature_schema_id: str) -> tuple[str, ...] | None:
        return self.ordered_feature_names.get(feature_schema_id)


#: The single registered admission order. Mock-fixture scope only.
SYNTHETIC_FIXTURE_INPUT_ORDER = FeatureOrderPolicy(
    policy_id=SYNTHETIC_FIXTURE_ORDER_POLICY_ID,
    status=SYNTHETIC_FIXTURE_ORDER_POLICY_STATUS,
    note=SYNTHETIC_FIXTURE_ORDER_POLICY_NOTE,
    ordered_feature_names={
        # v1 declares its properties in this order; the policy agrees with the
        # approved fixture pack. It is still an independent declaration.
        "mock_clinical_v1": (
            "mock_feature_demographic_age",
            "mock_feature_demographic_sex",
            "mock_feature_vital_systolic",
            "mock_feature_lab_concentration",
            "mock_feature_binary_flag",
            "mock_feature_count",
            "mock_feature_fraction",
        ),
        # v2 declares `mock_feature_fraction` third (it was added later as a
        # required slot). The admission order deliberately keeps measurement
        # grouping, so this policy differs from the schema's serialization
        # order. That difference is the point: position comes from here.
        "mock_clinical_v2": (
            "mock_feature_demographic_age",
            "mock_feature_demographic_sex",
            "mock_feature_vital_systolic",
            "mock_feature_lab_concentration",
            "mock_feature_binary_flag",
            "mock_feature_count",
            "mock_feature_fraction",
        ),
    },
)

#: Read-only registry: adding, replacing or deleting a registration at runtime
#: raises instead of silently redefining an approved input order.
REGISTERED_FEATURE_ORDER_POLICIES: Mapping[str, FeatureOrderPolicy] = MappingProxyType(
    {SYNTHETIC_FIXTURE_INPUT_ORDER.policy_id: SYNTHETIC_FIXTURE_INPUT_ORDER}
)


def registered_feature_order_policy(policy_id: str) -> FeatureOrderPolicy | None:
    """Return the registered policy with this id, or ``None`` (fail closed)."""
    return REGISTERED_FEATURE_ORDER_POLICIES.get(policy_id)


def is_registered_definition(candidate: FeatureOrderPolicy, registered: FeatureOrderPolicy) -> bool:
    """Return whether ``candidate`` is byte-for-byte the registered definition.

    Compares every registered field with strict semantics, so a caller cannot
    reuse a registered ``policy_id`` while changing its feature ordering,
    schema coverage, status or metadata:

    * ``policy_id``, ``status`` and ``note`` must match exactly;
    * the schema-id key set must match exactly (no added or removed schemas);
    * every schema's ordered name tuple must match exactly.

    Anything unreadable or unexpected fails closed (returns ``False``) rather
    than raising, so callers report one uniform rejection.
    """

    if not isinstance(candidate, FeatureOrderPolicy):
        return False
    if candidate.policy_id != registered.policy_id:
        return False
    if candidate.status != registered.status:
        return False
    if candidate.note != registered.note:
        return False
    candidate_order = candidate.ordered_feature_names
    registered_order = registered.ordered_feature_names
    if not isinstance(candidate_order, Mapping):
        return False
    if set(candidate_order) != set(registered_order):
        return False
    for schema_id, names in registered_order.items():
        candidate_names = candidate_order[schema_id]
        if not isinstance(candidate_names, (tuple, list)):
            return False
        if tuple(candidate_names) != tuple(names):
            return False
    return True
