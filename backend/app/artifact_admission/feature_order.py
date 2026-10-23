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


@dataclass(frozen=True)
class FeatureOrderPolicy:
    """Explicit ordered feature binding for one or more feature-schema ids.

    ``ordered_feature_names`` maps a shared feature-schema id to the exact
    tuple of feature names in approved input position order.
    """

    policy_id: str
    status: str
    ordered_feature_names: Mapping[str, tuple[str, ...]]
    note: str = ""

    def order_for(self, feature_schema_id: str) -> tuple[str, ...] | None:
        return self.ordered_feature_names.get(feature_schema_id)

    def __post_init__(self) -> None:
        if not self.policy_id or not isinstance(self.policy_id, str):
            raise ValueError("A feature-order policy requires a non-empty policy id.")
        if not self.status or not isinstance(self.status, str):
            raise ValueError("A feature-order policy requires an explicit status.")
        for schema_id, names in self.ordered_feature_names.items():
            if not isinstance(schema_id, str) or not schema_id:
                raise ValueError("Feature-order policy schema ids must be non-empty strings.")
            if not names or not all(isinstance(name, str) and name for name in names):
                raise ValueError("A registered feature order must be a non-empty list of names.")
            if len(set(names)) != len(names):
                raise ValueError("A registered feature order must not repeat a feature name.")


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

REGISTERED_FEATURE_ORDER_POLICIES: Mapping[str, FeatureOrderPolicy] = {
    SYNTHETIC_FIXTURE_INPUT_ORDER.policy_id: SYNTHETIC_FIXTURE_INPUT_ORDER,
}


def registered_feature_order_policy(policy_id: str) -> FeatureOrderPolicy | None:
    """Return the registered policy with this id, or ``None`` (fail closed)."""
    return REGISTERED_FEATURE_ORDER_POLICIES.get(policy_id)
