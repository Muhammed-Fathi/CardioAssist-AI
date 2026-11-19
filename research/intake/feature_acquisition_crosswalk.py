"""RH-04.1/RH-04.2 — feature acquisition-evidence crosswalk (offline, read-only).

This module implements the first engineering slice of milestone **RH-04**
(*Versioned source-specific research-only feature and integration contracts*,
see ``docs/research/next_phase/RH06_ISSUE110_CONSOLIDATED_DECISION_REVIEW_2026_11_19.md``
section 10.1, work packages ``RH-04-1`` and ``RH-04-2``).

The reviewable record is
``schemas/feature_acquisition_evidence_crosswalk.v1.json``. It is a versioned,
machine-readable **evidence** artifact: for every feature already registered in
the four panels of :data:`ai.panels.REGISTERED_PANELS` it separates four
questions that projects routinely conflate:

1. **Original-source feature-definition evidence** — which document actually
   establishes that the source defines this feature (``definition_evidence_ids``
   and the ``evidence_register`` entries they resolve to).
2. **Proposed acquisition channel** — the channel through which a future
   reviewed intake would obtain the value, and whether that channel rests on a
   registered source domain or is only a proposal
   (``acquisition.channel`` / ``acquisition.channel_status``).
3. **Verified versus unverified pre-angiography measurement timing** —
   ``acquisition.timing_status`` with the explicit boolean
   ``owner_verified_pre_angiography``. In this version that count is **0/16 for
   UCI-412** and **0/7 for UCI-45**: no owner-signed acquisition codebook or
   owner-attested CRF timestamp exists in the evidence register.
4. **Source-specific permission and restrictions** — ``permission_id`` plus the
   resolved ``restriction_ids``, including the UCI-45 labs extension, the
   UCI-412 labs route and the locked Hungary evaluation, all of which stay
   blocked.

Hard separation rule (machine-enforced, not merely documented)
--------------------------------------------------------------
``VERIFIED_REGISTERED_SOURCE_DOMAIN`` verifies only that a channel matches the
``source_domain``/``input_owner`` already recorded in a frozen repository
register. It is **never** proof of owner-verified pre-angiography timing:

* every feature must declare ``timing_derived_from_channel_status: false``;
* a ``VERIFIED_REGISTERED_SOURCE_DOMAIN`` channel may only carry the
  ``UNVERIFIED_TIMING_REGISTERED_DOMAIN_CHANNEL`` timing status;
* ``OWNER_VERIFIED_PRE_ANGIOGRAPHY`` requires a resolution to an
  owner-signed/owner-attested timing evidence item, and
  :data:`OWNER_TIMING_EVIDENCE_CLASSES` is **empty** in this version, so no such
  claim can exist until a reviewed code-and-evidence change is made;
* the per-source owner-verified counts are frozen at ``0`` and recomputed from
  the feature records, so a JSON-only promotion fails closed.

Reuse, not duplication
----------------------
The crosswalk deliberately does **not** define a second clinical feature schema.
It never restates units, coding vocabularies, plausible ranges, missingness
rules, targets, model families, seeds or thresholds. Those remain authoritative
in ``ai.panels`` / ``research.intake.synthetic_stage_validator`` /
``research.uci412.feature_schema``. This module holds only:

* the four registered **panel ids** with their dataset, version and feature
  count (roster *names* only, duplicated in code so a JSON-only edit cannot
  quietly admit a feature — the same fail-closed pattern as
  :mod:`research.intake.uci412_field_contract`); and
* the five existing **route ids** with their frozen activation state and
  permitted-operation set (duplicated in code and cross-checked against
  :data:`ai.research_routes.RESEARCH_ROUTE_CATALOG` by
  ``tests/experiments/test_feature_acquisition_crosswalk_panel_binding.py``).

The live equality proof needs the ML stack, so it lives under
``tests/experiments``; the stdlib-only suite in
``tests/audit/test_feature_acquisition_crosswalk.py`` exercises every validator
rule in the minimal audit CI environment.

Offline and read-only
---------------------
The module is standard-library only. It reads exactly one file (its own JSON),
writes no file, opens no socket, imports neither the backend application nor the
``ai`` package, and contains no scoring, inference, prediction, calibration or
explanation path. It can never compute a CAD probability: every query returns
``METADATA_ONLY_NO_CAD_PROBABILITY_COMPUTED``.

Nothing here authorizes any real-data execution, model fitting, endpoint,
contract or governance change. Gate PT P-1 stays PENDING, P-3 stays CLOSED and
P-5 stays prohibited; D-046 stays read-only audit; D-047 stays Cleveland-only
internal exploratory; D-048/M3a stays procedurally unauthorized. This artifact
adds no decision-register entry and promotes no source status.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from types import MappingProxyType
from typing import Any, Final, Iterable, Mapping, Sequence

PACKAGE_ROOT: Final[Path] = Path(__file__).resolve().parent
REPO_ROOT: Final[Path] = PACKAGE_ROOT.parent.parent
CROSSWALK_PATH: Final[Path] = (
    PACKAGE_ROOT / "schemas" / "feature_acquisition_evidence_crosswalk.v1.json"
)

# --------------------------------------------------------------------------- #
# Frozen identity                                                             #
# --------------------------------------------------------------------------- #

CROSSWALK_SCHEMA_ID: Final[str] = (
    "cardioassist.feature_acquisition_evidence_crosswalk"
)
CROSSWALK_SCHEMA_VERSION: Final[str] = "1.0.0"
CROSSWALK_ID: Final[str] = "rh04_feature_acquisition_evidence_crosswalk.v1"
CROSSWALK_ARTIFACT_KIND: Final[str] = (
    "OFFLINE_READ_ONLY_FEATURE_ACQUISITION_EVIDENCE_CROSSWALK"
)
CROSSWALK_STATUS: Final[str] = "EVIDENCE_ONLY_NOT_APPROVED"
CROSSWALK_PREPARED_ON: Final[str] = "2026-11-19"
#: Verified ``main`` baseline this evidence artifact was prepared against.
CROSSWALK_BASELINE_MAIN_SHA: Final[str] = (
    "545d0d835ecb64a6b1aaeb3957705a30bb2ce760"
)

STATUS_STATEMENT: Final[str] = (
    "EVIDENCE ARTIFACT ONLY. This crosswalk records what repository-registered "
    "sources do and do not establish for each already-registered feature. It is "
    "not an approved clinical schema, not a model input contract, not an "
    "authorization, not owner-verified timing evidence, not supervisor, ethics "
    "or institutional approval, and not permission to process a real cohort. "
    "No feature is clinically verified, no route is activated, and no "
    "scientific hold is lifted by this document."
)

OFFLINE_CLAUSES: Final[tuple[str, ...]] = (
    "Read-only: the validator opens exactly one file (this crosswalk) and writes nothing.",
    "No network access, no subprocess, no environment switch and no telemetry.",
    "No backend route, database, migration, contract, frontend or model artifact is touched.",
    "No scoring, inference, prediction, calibration or explanation path exists in this module.",
    "No real patient data is read, stored or derived; every test fixture is invented in memory.",
    "The result state of every query is METADATA_ONLY_NO_CAD_PROBABILITY_COMPUTED.",
)

# --------------------------------------------------------------------------- #
# Frozen vocabularies                                                         #
# --------------------------------------------------------------------------- #

EVIDENCE_CLASS_TAXONOMY: Final[Mapping[str, str]] = MappingProxyType(
    {
        "OWNER_DATASET_DESCRIPTION": (
            "Public dataset-owner landing page or attribute documentation. "
            "Establishes dataset identity, groups and published column names; "
            "it does not document per-field collection protocols or timing."
        ),
        "FROZEN_FEATURE_DICTIONARY_REGISTRY": (
            "Repository-frozen feature dictionary or stage allowlist. "
            "Establishes the registered working definition, unit and coding of a "
            "feature; it is a repository record, not owner timing evidence."
        ),
        "FROZEN_PROTOCOL_REGISTRATION": (
            "Registered exploratory protocol or experiment plan. Establishes what "
            "was proposed and executed internally; it grants no new permission."
        ),
        "MAINTAINER_LOCAL_READ_ONLY_AUDIT": (
            "Maintainer-executed, read-only, aggregate audit record. Establishes "
            "observed representation (for example numeric 0/1 cells); it does not "
            "establish direction, case definition or acquisition moment."
        ),
        "PEER_REVIEWED_SECONDARY_PUBLICATION": (
            "Peer-reviewed secondary publication. May support a provisional reading; "
            "it is not an owner codebook and does not establish timing."
        ),
        "PROPOSED_RESEARCH_MAPPING": (
            "Repository PROPOSED research mapping specification. Establishes a "
            "proposal under review, never an approved acquisition workflow."
        ),
        "REPOSITORY_EVIDENCE_REGISTER": (
            "Repository evidence/adjudication register. Records unresolved questions "
            "and eligibility classes without approving them."
        ),
        "REPOSITORY_TIMING_GAP_REGISTER": (
            "Repository register that documents the ABSENCE of owner timing evidence "
            "for a field. It is the positive record of an unverified-timing finding, "
            "not proof of any acquisition moment."
        ),
    }
)

#: Evidence classes that could, in a future reviewed version, establish
#: owner-verified pre-angiography timing. Frozen empty: no such evidence exists
#: for any registered feature today, so no promotion is representable.
OWNER_TIMING_EVIDENCE_CLASSES: Final[frozenset[str]] = frozenset()

TIMING_STATUS_TAXONOMY: Final[Mapping[str, str]] = MappingProxyType(
    {
        "UNVERIFIED_TIMING_REGISTERED_DOMAIN_CHANNEL": (
            "The channel matches a registered source domain, but no owner-verified "
            "pre-angiography acquisition timing exists. A verified channel is not a "
            "verified measurement moment."
        ),
        "UNVERIFIED_TIMING_PROPOSED_CHANNEL": (
            "The acquisition channel is itself only proposed, and no owner-verified "
            "pre-angiography acquisition timing exists."
        ),
        "OWNER_VERIFIED_PRE_ANGIOGRAPHY": (
            "Reserved status: requires an owner-signed acquisition codebook or "
            "owner-attested CRF timestamp. No registered feature may carry it in "
            "schema version 1.0.0 because no such evidence item exists."
        ),
    }
)

CHANNEL_STATUS_TAXONOMY: Final[Mapping[str, str]] = MappingProxyType(
    {
        "VERIFIED_REGISTERED_SOURCE_DOMAIN": (
            "The proposed channel matches the source_domain/input_owner already "
            "recorded in a frozen repository register. Verifies domain only."
        ),
        "PROPOSED_FUTURE_ACQUISITION_CHANNEL": (
            "The channel is a reviewable proposal with no registered source-domain "
            "record behind it."
        ),
    }
)

ACQUISITION_CHANNEL_TAXONOMY: Final[Mapping[str, str]] = MappingProxyType(
    {
        "structured_history": (
            "Structured history capture by a clinician from the participant."
        ),
        "clinician_assessment": (
            "Clinician observation or interpretation recorded as a structured field."
        ),
        "measurement": (
            "Device or examination measurement recorded as a structured field."
        ),
        "laboratory_document": (
            "Routine laboratory report value transcribed into a structured field."
        ),
    }
)

DISPOSITION_TAXONOMY: Final[Mapping[str, str]] = MappingProxyType(
    {
        "EVIDENCE_RECORDED_NO_ACTIVATION_CHANGE": (
            "Evidence recorded only. The feature's panel membership, route "
            "activation, authorization status and scientific holds are unchanged."
        ),
        "EVIDENCE_RECORDED_EXTENSION_REMAINS_BLOCKED": (
            "Evidence recorded only. The feature belongs to a blocked extension "
            "that stays blocked."
        ),
    }
)

PERMISSION_STATUS_TAXONOMY: Final[Mapping[str, str]] = MappingProxyType(
    {
        "AUTHORIZED_INTERNAL_EXPLORATORY_NOT_SUPERVISOR_APPROVED": (
            "D-047 internal exploratory Cleveland scope, executed only under the "
            "historical label; no publication, clinical or external-validation claim."
        ),
        "SCIENTIFIC_HOLD_NEW_REAL_FIT": (
            "Scientific hold on new real-data fitting or panel extension pending "
            "owner/CRF timing evidence and independent review."
        ),
    }
)

#: Activation vocabulary for a route in this crosswalk. Nothing here can grant
#: an operation: the permitted-operation set is frozen per route.
ROUTE_ACTIVATION_STATES: Final[tuple[str, ...]] = (
    "ACTIVE_SYNTHETIC_ONLY",
    "BLOCKED_PENDING_AUTHORIZATION",
    "BLOCKED_TIMING_UNVERIFIED",
    "LOCKED_EXTERNAL_TARGET_NEVER_TRAIN",
)

#: Real-data and clinical operations that no route may ever permit here.
FORBIDDEN_OPERATIONS_ALWAYS: Final[frozenset[str]] = frozenset(
    {
        "real_data_training",
        "real_external_evaluation",
        "real_bundle_inference",
        "clinical_serving",
    }
)

#: Closed operation vocabulary (mirrors ``ai.research_routes``; equality is
#: asserted by the panel-binding test suite).
KNOWN_OPERATIONS: Final[frozenset[str]] = frozenset(
    {
        "synthetic_training",
        "synthetic_prediction",
        "synthetic_external_evaluation",
        "shap_attribution",
        "lime_assessment",
        "bundle_packaging",
        "route_contract_query",
        "synthetic_end_to_end_exercise",
    }
) | FORBIDDEN_OPERATIONS_ALWAYS

CONTRACT_QUERY_ONLY: Final[frozenset[str]] = frozenset({"route_contract_query"})

# --------------------------------------------------------------------------- #
# Frozen panel rosters (names only — never units, codes, ranges or targets)    #
# --------------------------------------------------------------------------- #

UCI45_RESTING_FEATURES: Final[tuple[str, ...]] = (
    "age",
    "sex",
    "cp",
    "trestbps",
    "restecg",
)
UCI45_LAB_FEATURES: Final[tuple[str, ...]] = ("chol", "fbs")
UCI412_BASIC_FEATURES: Final[tuple[str, ...]] = (
    "Age",
    "Sex",
    "BMI",
    "DM",
    "HTN",
    "Current Smoker",
    "EX-Smoker",
    "FH",
    "DLP",
    "BP",
    "PR",
    "Typical Chest Pain",
    "Atypical",
    "Nonanginal",
    "Exertional CP",
    "Dyspnea",
)
UCI412_LAB_FEATURES: Final[tuple[str, ...]] = (
    "FBS",
    "CR",
    "TG",
    "LDL",
    "HDL",
    "HB",
    "WBC",
)


@dataclass(frozen=True, slots=True)
class _PanelSpec:
    panel_id: str
    dataset_id: str
    panel_version: str
    features: tuple[str, ...]


PANEL_SPECS: Final[tuple[_PanelSpec, ...]] = (
    _PanelSpec(
        "da_a2_resting_v1", "DA-A2", "1.0.0", UCI45_RESTING_FEATURES
    ),
    _PanelSpec(
        "da_a2_resting_labs_v1",
        "DA-A2",
        "1.0.0",
        UCI45_RESTING_FEATURES + UCI45_LAB_FEATURES,
    ),
    _PanelSpec(
        "da_a1_basic_clinical_v1", "DA-A1", "1.1.0", UCI412_BASIC_FEATURES
    ),
    _PanelSpec(
        "da_a1_clinical_core_labs_v1",
        "DA-A1",
        "1.1.0",
        UCI412_BASIC_FEATURES + UCI412_LAB_FEATURES,
    ),
)
PANELS_BY_ID: Final[Mapping[str, _PanelSpec]] = MappingProxyType(
    {panel.panel_id: panel for panel in PANEL_SPECS}
)

#: Registry module the panel records are bound to (documentation string only;
#: this module never imports it).
PANEL_REGISTRY_REFERENCE: Final[str] = "ai.panels.REGISTERED_PANELS"

# --------------------------------------------------------------------------- #
# Frozen sources, permissions and routes                                       #
# --------------------------------------------------------------------------- #

SOURCE_UCI45: Final[str] = "UCI-45"
SOURCE_UCI412: Final[str] = "UCI-412"

SOURCES: Final[Mapping[str, Mapping[str, Any]]] = MappingProxyType(
    {
        SOURCE_UCI45: MappingProxyType(
            {
                "dataset_id": "DA-A2",
                "track": "A",
                "panel_ids": ("da_a2_resting_v1", "da_a2_resting_labs_v1"),
                "permission_id": "PERM-UCI45-INTERNAL-EXPLORATORY",
            }
        ),
        SOURCE_UCI412: MappingProxyType(
            {
                "dataset_id": "DA-A1",
                "track": "A",
                "panel_ids": (
                    "da_a1_basic_clinical_v1",
                    "da_a1_clinical_core_labs_v1",
                ),
                "permission_id": "PERM-UCI412-SCIENTIFIC-HOLD",
            }
        ),
    }
)

PERMISSIONS: Final[Mapping[str, Mapping[str, Any]]] = MappingProxyType(
    {
        "PERM-UCI45-INTERNAL-EXPLORATORY": MappingProxyType(
            {
                "source_id": SOURCE_UCI45,
                "permission_status": (
                    "AUTHORIZED_INTERNAL_EXPLORATORY_NOT_SUPERVISOR_APPROVED"
                ),
            }
        ),
        "PERM-UCI412-SCIENTIFIC-HOLD": MappingProxyType(
            {
                "source_id": SOURCE_UCI412,
                "permission_status": "SCIENTIFIC_HOLD_NEW_REAL_FIT",
            }
        ),
    }
)

RESTRICTIONS: Final[tuple[str, ...]] = (
    "RES-NO-POOLING",
    "RES-NO-CROSSWALK-TRANSLATION",
    "RES-SYNTHETIC-ONLY-NO-CLINICAL-CLAIM",
    "RES-NO-PERFORMANCE-RANKING",
    "RES-UCI45-NO-SELECTION-DECISION",
    "RES-UCI45-LABS-EXTENSION-BLOCKED",
    "RES-UCI412-OWNER-TIMING-UNVERIFIED",
    "RES-UCI412-LABS-BLOCKED",
    "RES-HUNGARY-LOCKED-NEVER-TRAIN",
)

ROUTE_SPECS: Final[Mapping[str, Mapping[str, Any]]] = MappingProxyType(
    {
        "da_a2_resting_v1": MappingProxyType(
            {
                "dataset_id": "DA-A2",
                "panel_id": "da_a2_resting_v1",
                "activation_state": "ACTIVE_SYNTHETIC_ONLY",
                "prediction_time_admissibility": (
                    "ADMISSIBLE_SYNTHETIC_TEST_ONLY"
                ),
                "authorization_status": (
                    "AUTHORIZED_SYNTHETIC_TESTS_ONLY_REAL_DATA_BLOCKED_GATE_PT"
                ),
                "evaluation_status": "SYNTHETIC_TEST",
                "blocked": False,
                "permitted_operations": frozenset(
                    {
                        "synthetic_training",
                        "synthetic_prediction",
                        "synthetic_external_evaluation",
                        "shap_attribution",
                        "lime_assessment",
                        "bundle_packaging",
                        "route_contract_query",
                        "synthetic_end_to_end_exercise",
                    }
                ),
                "required_restriction_ids": frozenset(
                    {
                        "RES-NO-POOLING",
                        "RES-SYNTHETIC-ONLY-NO-CLINICAL-CLAIM",
                        "RES-UCI45-NO-SELECTION-DECISION",
                    }
                ),
            }
        ),
        "da_a2_resting_labs_v1": MappingProxyType(
            {
                "dataset_id": "DA-A2",
                "panel_id": "da_a2_resting_labs_v1",
                "activation_state": "BLOCKED_PENDING_AUTHORIZATION",
                "prediction_time_admissibility": (
                    "PLANNED_BLOCKED_PENDING_AUTHORIZATION"
                ),
                "authorization_status": "PROPOSED_NOT_AUTHORIZED",
                "evaluation_status": "NOT_EVALUATED",
                "blocked": True,
                "permitted_operations": CONTRACT_QUERY_ONLY,
                "required_restriction_ids": frozenset(
                    {
                        "RES-NO-POOLING",
                        "RES-SYNTHETIC-ONLY-NO-CLINICAL-CLAIM",
                        "RES-UCI45-NO-SELECTION-DECISION",
                        "RES-UCI45-LABS-EXTENSION-BLOCKED",
                    }
                ),
            }
        ),
        "da_a1_basic_clinical_v1": MappingProxyType(
            {
                "dataset_id": "DA-A1",
                "panel_id": "da_a1_basic_clinical_v1",
                "activation_state": "ACTIVE_SYNTHETIC_ONLY",
                "prediction_time_admissibility": (
                    "ADMISSIBLE_SYNTHETIC_TEST_ONLY"
                ),
                "authorization_status": (
                    "ADMITTED_FOR_INTERNAL_RESEARCH_SUBJECT_TO_M3A_AUTHORIZATION"
                ),
                "evaluation_status": "SYNTHETIC_TEST",
                "blocked": False,
                "permitted_operations": frozenset(
                    {
                        "synthetic_training",
                        "synthetic_prediction",
                        "synthetic_external_evaluation",
                        "shap_attribution",
                        "lime_assessment",
                        "bundle_packaging",
                        "route_contract_query",
                        "synthetic_end_to_end_exercise",
                    }
                ),
                "required_restriction_ids": frozenset(
                    {
                        "RES-NO-POOLING",
                        "RES-SYNTHETIC-ONLY-NO-CLINICAL-CLAIM",
                        "RES-UCI412-OWNER-TIMING-UNVERIFIED",
                    }
                ),
            }
        ),
        "da_a1_clinical_core_labs_v1": MappingProxyType(
            {
                "dataset_id": "DA-A1",
                "panel_id": "da_a1_clinical_core_labs_v1",
                "activation_state": "BLOCKED_TIMING_UNVERIFIED",
                "prediction_time_admissibility": (
                    "PROPOSED_PRE_ANGIOGRAPHY_TIMING_UNVERIFIED_BLOCKED"
                ),
                "authorization_status": "PROPOSED_NOT_AUTHORIZED",
                "evaluation_status": "NOT_EVALUATED",
                "blocked": True,
                "permitted_operations": CONTRACT_QUERY_ONLY,
                "required_restriction_ids": frozenset(
                    {
                        "RES-NO-POOLING",
                        "RES-UCI412-OWNER-TIMING-UNVERIFIED",
                        "RES-UCI412-LABS-BLOCKED",
                    }
                ),
            }
        ),
        "da_a2_hungary_locked_transportability_v1": MappingProxyType(
            {
                "dataset_id": "DA-A2",
                "panel_id": "da_a2_resting_v1",
                "activation_state": "LOCKED_EXTERNAL_TARGET_NEVER_TRAIN",
                "prediction_time_admissibility": (
                    "LOCKED_EXTERNAL_TARGET_NEVER_TRAIN_ON_LOCKED_SET"
                ),
                "authorization_status": "PROPOSED_NOT_AUTHORIZED",
                "evaluation_status": "NOT_AUTHORIZED",
                "blocked": True,
                "permitted_operations": CONTRACT_QUERY_ONLY,
                "required_restriction_ids": frozenset(
                    {
                        "RES-NO-POOLING",
                        "RES-HUNGARY-LOCKED-NEVER-TRAIN",
                    }
                ),
            }
        ),
    }
)

BLOCKED_ITEMS: Final[Mapping[str, Mapping[str, str]]] = MappingProxyType(
    {
        "BLOCK-UCI45-LABS-EXTENSION": MappingProxyType(
            {
                "route_id": "da_a2_resting_labs_v1",
                "reason_restriction_id": "RES-UCI45-LABS-EXTENSION-BLOCKED",
            }
        ),
        "BLOCK-UCI412-LABS-ROUTE": MappingProxyType(
            {
                "route_id": "da_a1_clinical_core_labs_v1",
                "reason_restriction_id": "RES-UCI412-LABS-BLOCKED",
            }
        ),
        "BLOCK-HUNGARY-LOCKED-EVALUATION": MappingProxyType(
            {
                "route_id": "da_a2_hungary_locked_transportability_v1",
                "reason_restriction_id": "RES-HUNGARY-LOCKED-NEVER-TRAIN",
            }
        ),
    }
)

# --------------------------------------------------------------------------- #
# Frozen evidence register (exact ids, classes and reference paths)            #
# --------------------------------------------------------------------------- #

EVIDENCE_REGISTER: Final[Mapping[str, Mapping[str, Any]]] = MappingProxyType(
    {
        "EV-UCI412-PRIMARY-OWNER": MappingProxyType(
            {
                "evidence_class": "OWNER_DATASET_DESCRIPTION",
                "reference_path": "docs/research/ai8r/SOURCE_ADMISSIBILITY.md",
                "establishes_feature_definition": True,
            }
        ),
        "EV-UCI412-REGISTERED-DICTIONARY": MappingProxyType(
            {
                "evidence_class": "FROZEN_FEATURE_DICTIONARY_REGISTRY",
                "reference_path": (
                    "research/uci412/schemas/uci412_feature_dictionary.v1.json"
                ),
                "establishes_feature_definition": True,
            }
        ),
        "EV-UCI412-AI8R-ELIGIBILITY": MappingProxyType(
            {
                "evidence_class": "REPOSITORY_EVIDENCE_REGISTER",
                "reference_path": "research/uci412/schemas/ai8r_eligibility.v1.json",
                "establishes_feature_definition": True,
            }
        ),
        "EV-UCI412-LOCAL-ENCODING-AUDIT": MappingProxyType(
            {
                "evidence_class": "MAINTAINER_LOCAL_READ_ONLY_AUDIT",
                "reference_path": (
                    "docs/research/gate-pt/"
                    "10_m3a_uci412_source_encoding_AMENDMENT_A1.md"
                ),
                "establishes_feature_definition": True,
            }
        ),
        "EV-UCI412-M3A-SPECIFICATION": MappingProxyType(
            {
                "evidence_class": "FROZEN_PROTOCOL_REGISTRATION",
                "reference_path": (
                    "docs/research/gate-pt/"
                    "08_m3a_uci412_source_specific_benchmark_SPECIFICATION.md"
                ),
                "establishes_feature_definition": True,
            }
        ),
        "EV-RH02-Q04-UCI412-TIMING-GAP": MappingProxyType(
            {
                "evidence_class": "REPOSITORY_TIMING_GAP_REGISTER",
                "reference_path": (
                    "docs/research/next_phase/"
                    "RH02_SOURCE_QUESTION_REGISTER_2026_11_19.json"
                ),
                "establishes_feature_definition": False,
            }
        ),
        "EV-UCI45-PROCESSED-COLUMNS": MappingProxyType(
            {
                "evidence_class": "OWNER_DATASET_DESCRIPTION",
                "reference_path": "docs/research/ai8r/SOURCE_ADMISSIBILITY.md",
                "establishes_feature_definition": True,
            }
        ),
        "EV-UCI45-REGISTERED-STAGE": MappingProxyType(
            {
                "evidence_class": "FROZEN_FEATURE_DICTIONARY_REGISTRY",
                "reference_path": "research/intake/synthetic_stage_validator.py",
                "establishes_feature_definition": True,
            }
        ),
        "EV-UCI45-D047-PLAN": MappingProxyType(
            {
                "evidence_class": "FROZEN_PROTOCOL_REGISTRATION",
                "reference_path": (
                    "research/experiments/"
                    "cleveland_d047_exploratory_plan.v0.1.json"
                ),
                "establishes_feature_definition": False,
            }
        ),
        "EV-R1-CLEVELAND-MAPPING": MappingProxyType(
            {
                "evidence_class": "PROPOSED_RESEARCH_MAPPING",
                "reference_path": (
                    "research/intake/schemas/"
                    "cleveland_resting_five_field_mapping.v0.1.json"
                ),
                "establishes_feature_definition": True,
            }
        ),
    }
)

# --------------------------------------------------------------------------- #
# Frozen per-field expectations                                               #
# --------------------------------------------------------------------------- #

#: Registered source-domain claim quoted from the frozen UCI-412 dictionary.
#: ``UNRECORDED`` marks sources whose contract records no such claim at all.
CLAIM_UNRECORDED: Final[str] = "NOT_RECORDED_BY_REGISTERED_SOURCE_CONTRACT"

UCI412_CLAIMS: Final[Mapping[str, tuple[str, str]]] = MappingProxyType(
    {
        **{
            name: ("patient_history", "EXPECTED_AVAILABLE_BEFORE_ANGIOGRAPHY")
            for name in UCI412_BASIC_FEATURES
        },
        "BMI": ("physical_examination", "EXPECTED_AVAILABLE_BEFORE_ANGIOGRAPHY"),
        "BP": ("vital_signs", "EXPECTED_AVAILABLE_BEFORE_ANGIOGRAPHY"),
        "PR": ("vital_signs", "EXPECTED_AVAILABLE_BEFORE_ANGIOGRAPHY"),
        **{
            name: ("laboratory", "PLAUSIBLE_UNVERIFIED_TIMING")
            for name in UCI412_LAB_FEATURES
        },
    }
)

SOURCE_DOMAINS: Final[frozenset[str]] = frozenset(
    {
        "patient_history",
        "physical_examination",
        "vital_signs",
        "laboratory",
    }
)

AVAILABILITY_CLASSES: Final[frozenset[str]] = frozenset(
    {
        "EXPECTED_AVAILABLE_BEFORE_ANGIOGRAPHY",
        "PLAUSIBLE_UNVERIFIED_TIMING",
        CLAIM_UNRECORDED,
    }
)

#: Channel a registered source domain corresponds to. This map verifies
#: *domain*, never timing.
DOMAIN_TO_CHANNEL: Final[Mapping[str, str]] = MappingProxyType(
    {
        "patient_history": "structured_history",
        "physical_examination": "measurement",
        "vital_signs": "measurement",
        "laboratory": "laboratory_document",
    }
)

#: UCI-45 proposed channels (the UCI-45 stage contract records no source domain,
#: so every UCI-45 channel is an explicit proposal).
UCI45_PROPOSED_CHANNELS: Final[Mapping[str, str]] = MappingProxyType(
    {
        "age": "structured_history",
        "sex": "structured_history",
        "cp": "structured_history",
        "trestbps": "measurement",
        "restecg": "clinician_assessment",
        "chol": "laboratory_document",
        "fbs": "laboratory_document",
    }
)

#: Per-dataset definition-evidence requirement (exact set per feature).
UCI412_BASIC_DEFINITION_EVIDENCE: Final[tuple[str, ...]] = (
    "EV-UCI412-PRIMARY-OWNER",
    "EV-UCI412-REGISTERED-DICTIONARY",
    "EV-UCI412-AI8R-ELIGIBILITY",
)
UCI412_LAB_DEFINITION_EVIDENCE: Final[tuple[str, ...]] = (
    "EV-UCI412-PRIMARY-OWNER",
    "EV-UCI412-REGISTERED-DICTIONARY",
    "EV-UCI412-M3A-SPECIFICATION",
)
UCI45_DEFINITION_EVIDENCE: Final[tuple[str, ...]] = (
    "EV-UCI45-PROCESSED-COLUMNS",
    "EV-UCI45-REGISTERED-STAGE",
)

UCI412_BASIC_RESTRICTIONS: Final[tuple[str, ...]] = (
    "RES-UCI412-OWNER-TIMING-UNVERIFIED",
)
UCI412_LAB_RESTRICTIONS: Final[tuple[str, ...]] = (
    "RES-UCI412-OWNER-TIMING-UNVERIFIED",
    "RES-UCI412-LABS-BLOCKED",
)
UCI45_RESTING_RESTRICTIONS: Final[tuple[str, ...]] = (
    "RES-UCI45-NO-SELECTION-DECISION",
    "RES-SYNTHETIC-ONLY-NO-CLINICAL-CLAIM",
)
UCI45_LAB_RESTRICTIONS: Final[tuple[str, ...]] = (
    "RES-UCI45-NO-SELECTION-DECISION",
    "RES-SYNTHETIC-ONLY-NO-CLINICAL-CLAIM",
    "RES-UCI45-LABS-EXTENSION-BLOCKED",
)

#: Prohibited variables that may never appear as a crosswalk feature. These
#: names are re-used from the existing registered source contracts rather than
#: redefined here.
PROHIBITED_FEATURE_NAMES: Final[frozenset[str]] = frozenset(
    {
        # UCI-45 outcome, angiography, exercise-test and identifier fields.
        "num",
        "ca",
        "thal",
        "thalach",
        "exang",
        "oldpeak",
        "slope",
        "target",
        "id",
        "site",
        # UCI-412 / UCI-411 outcome, artery and identifier fields.
        "Cath",
        "LAD",
        "LCX",
        "RCA",
        "laddist",
        "ladprox",
        "lcxdist",
        "lcxprox",
        "rcadist",
        "rcaprox",
        "lmt",
        "ramus",
        "om1",
        "om2",
        "cxmain",
        "diag",
        "patient_id",
        "mrn",
        # Echocardiography and wearable/Track-B observations.
        "EF-TTE",
        "Region RWMA",
        "VHD",
        "wearable_ecg",
        "wearable_heart_rate",
        "monitoring_observation",
        "spo2",
        "hrv",
        "ppg",
        "synthetic_end_to_end_exercise",
    }
)

#: Frozen scientific holds. Any promotion fails closed.
EXPECTED_HOLDS: Final[Mapping[str, Any]] = MappingProxyType(
    {
        "gate_pt_p1_target_population_moment": "PENDING",
        "gate_pt_p3_formal_research": "CLOSED",
        "gate_pt_p5_clinical_readiness_claims": "NOT_MADE_PROHIBITED",
        "uci412_scientific_hold": True,
        "owner_verified_pre_angiography_feature_counts": {
            SOURCE_UCI45: 0,
            SOURCE_UCI412: 0,
        },
        "registered_feature_counts": {
            SOURCE_UCI45: 7,
            SOURCE_UCI412: 23,
        },
        "uci412_basic_clinical_owner_verified_pre_angiography": "0/16",
        "real_data_training_authorized": False,
        "real_model_artifacts_created": False,
        "patient_data_accessed": False,
        "new_endpoints_added": False,
        "frozen_contracts_modified": False,
        "github_workflows_modified": False,
    }
)

REQUIRED_TOP_LEVEL_KEYS: Final[tuple[str, ...]] = (
    "schema_id",
    "schema_version",
    "crosswalk_id",
    "artifact_kind",
    "status",
    "status_statement",
    "prepared_on",
    "baseline_main_sha",
    "offline_clauses",
    "holds",
    "evidence_class_taxonomy",
    "acquisition_channel_taxonomy",
    "channel_status_taxonomy",
    "timing_status_taxonomy",
    "disposition_taxonomy",
    "permission_status_taxonomy",
    "evidence_register",
    "sources",
    "permissions",
    "restrictions",
    "panels",
    "routes",
    "blocked_items",
    "features",
    "no_result_contract",
    "revision_history",
)

NO_RESULT_CONTRACT: Final[Mapping[str, str]] = MappingProxyType(
    {
        "result_state": "METADATA_ONLY_NO_CAD_PROBABILITY_COMPUTED",
        "cad_probability_computed": "false",
        "statement": (
            "Every query returns documentation metadata only. No CAD "
            "probability, score, calibration, explanation or clinical "
            "interpretation is produced, and none may be inferred from an "
            "empty or populated result set."
        ),
    }
)

QUERY_SCHEMA_ID: Final[str] = "cardioassist.feature_acquisition_evidence_query/v1"
RESULT_STATE: Final[str] = "METADATA_ONLY_NO_CAD_PROBABILITY_COMPUTED"

FEATURE_KEYS: Final[tuple[str, ...]] = (
    "feature_key",
    "source_id",
    "dataset_id",
    "feature_name",
    "panels",
    "definition_evidence_ids",
    "registered_source_claim",
    "acquisition",
    "permission_id",
    "restriction_ids",
    "disposition",
)
CLAIM_KEYS: Final[tuple[str, ...]] = (
    "register_evidence_id",
    "source_domain",
    "availability_at_decision_time",
)
ACQUISITION_KEYS: Final[tuple[str, ...]] = (
    "channel",
    "channel_status",
    "channel_evidence_ids",
    "timing_status",
    "owner_verified_pre_angiography",
    "timing_evidence_ids",
    "timing_derived_from_channel_status",
)


# --------------------------------------------------------------------------- #
# Errors                                                                      #
# --------------------------------------------------------------------------- #


class CrosswalkError(ValueError):
    """Base class for fail-closed crosswalk errors with a stable code."""

    def __init__(self, code: str, message: str, *, path: str = "$") -> None:
        super().__init__(f"{message} (code={code}, path={path})")
        self.code = code
        self.bare_message = message
        self.path = path


class CrosswalkValidationError(CrosswalkError):
    """The crosswalk document violates a frozen rule; nothing is accepted."""


class CrosswalkQueryError(CrosswalkError):
    """A metadata query filter is unknown, ambiguous or contradictory."""


# --------------------------------------------------------------------------- #
# Read model                                                                  #
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class EvidenceRecord:
    evidence_id: str
    evidence_class: str
    reference_path: str
    establishes_feature_definition: bool
    establishes_acquisition_timing: bool
    owner_attested_timing_evidence: bool
    summary: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "evidence_id": self.evidence_id,
            "evidence_class": self.evidence_class,
            "reference_path": self.reference_path,
            "establishes_feature_definition": self.establishes_feature_definition,
            "establishes_acquisition_timing": self.establishes_acquisition_timing,
            "owner_attested_timing_evidence": self.owner_attested_timing_evidence,
            "summary": self.summary,
        }


@dataclass(frozen=True, slots=True)
class SourceRecord:
    source_id: str
    dataset_id: str
    track: str
    panel_ids: tuple[str, ...]
    permission_id: str
    provenance_statement: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "dataset_id": self.dataset_id,
            "track": self.track,
            "panel_ids": list(self.panel_ids),
            "permission_id": self.permission_id,
            "provenance_statement": self.provenance_statement,
        }


@dataclass(frozen=True, slots=True)
class PermissionRecord:
    permission_id: str
    source_id: str
    permission_status: str
    real_data_execution_authorized_by_this_artifact: bool
    activation_by_this_artifact: str
    statement: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "permission_id": self.permission_id,
            "source_id": self.source_id,
            "permission_status": self.permission_status,
            "real_data_execution_authorized_by_this_artifact": (
                self.real_data_execution_authorized_by_this_artifact
            ),
            "activation_by_this_artifact": self.activation_by_this_artifact,
            "statement": self.statement,
        }


@dataclass(frozen=True, slots=True)
class RestrictionRecord:
    restriction_id: str
    statement: str
    applies_to_route_ids: tuple[str, ...]
    applies_to_source_ids: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "restriction_id": self.restriction_id,
            "statement": self.statement,
            "applies_to_route_ids": list(self.applies_to_route_ids),
            "applies_to_source_ids": list(self.applies_to_source_ids),
        }


@dataclass(frozen=True, slots=True)
class PanelBindingRecord:
    panel_id: str
    dataset_id: str
    panel_version: str
    feature_count: int
    registered_in: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "panel_id": self.panel_id,
            "dataset_id": self.dataset_id,
            "panel_version": self.panel_version,
            "feature_count": self.feature_count,
            "registered_in": self.registered_in,
        }


@dataclass(frozen=True, slots=True)
class RouteActivationRecord:
    route_id: str
    dataset_id: str
    panel_id: str
    activation_state: str
    prediction_time_admissibility: str
    authorization_status: str
    evaluation_status: str
    blocked: bool
    permitted_operations: tuple[str, ...]
    forbidden_operations: tuple[str, ...]
    restriction_ids: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "route_id": self.route_id,
            "dataset_id": self.dataset_id,
            "panel_id": self.panel_id,
            "activation_state": self.activation_state,
            "prediction_time_admissibility": self.prediction_time_admissibility,
            "authorization_status": self.authorization_status,
            "evaluation_status": self.evaluation_status,
            "blocked": self.blocked,
            "permitted_operations": list(self.permitted_operations),
            "forbidden_operations": list(self.forbidden_operations),
            "restriction_ids": list(self.restriction_ids),
        }


@dataclass(frozen=True, slots=True)
class BlockedItemRecord:
    item_id: str
    route_id: str
    state: str
    max_permitted_operation: str
    reason_restriction_id: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "item_id": self.item_id,
            "route_id": self.route_id,
            "state": self.state,
            "max_permitted_operation": self.max_permitted_operation,
            "reason_restriction_id": self.reason_restriction_id,
        }


@dataclass(frozen=True, slots=True)
class RegisteredSourceClaim:
    register_evidence_id: str
    source_domain: str
    availability_at_decision_time: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "register_evidence_id": self.register_evidence_id,
            "source_domain": self.source_domain,
            "availability_at_decision_time": self.availability_at_decision_time,
        }


@dataclass(frozen=True, slots=True)
class AcquisitionEvidence:
    channel: str
    channel_status: str
    channel_evidence_ids: tuple[str, ...]
    timing_status: str
    owner_verified_pre_angiography: bool
    timing_evidence_ids: tuple[str, ...]
    timing_derived_from_channel_status: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "channel": self.channel,
            "channel_status": self.channel_status,
            "channel_evidence_ids": list(self.channel_evidence_ids),
            "timing_status": self.timing_status,
            "owner_verified_pre_angiography": self.owner_verified_pre_angiography,
            "timing_evidence_ids": list(self.timing_evidence_ids),
            "timing_derived_from_channel_status": (
                self.timing_derived_from_channel_status
            ),
        }


@dataclass(frozen=True, slots=True)
class FeatureAcquisitionEvidence:
    feature_key: str
    source_id: str
    dataset_id: str
    feature_name: str
    panels: tuple[str, ...]
    definition_evidence_ids: tuple[str, ...]
    registered_source_claim: RegisteredSourceClaim
    acquisition: AcquisitionEvidence
    permission_id: str
    permission_status: str
    restriction_ids: tuple[str, ...]
    disposition: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "feature_key": self.feature_key,
            "source_id": self.source_id,
            "dataset_id": self.dataset_id,
            "feature_name": self.feature_name,
            "panels": list(self.panels),
            "definition_evidence_ids": list(self.definition_evidence_ids),
            "registered_source_claim": self.registered_source_claim.to_dict(),
            "acquisition": self.acquisition.to_dict(),
            "permission_id": self.permission_id,
            "permission_status": self.permission_status,
            "restriction_ids": list(self.restriction_ids),
            "disposition": self.disposition,
        }


@dataclass(frozen=True, slots=True)
class AcquisitionEvidenceCrosswalk:
    schema_id: str
    schema_version: str
    crosswalk_id: str
    artifact_kind: str
    status: str
    prepared_on: str
    baseline_main_sha: str
    document_digest_sha256: str
    holds: Mapping[str, Any]
    evidence: tuple[EvidenceRecord, ...]
    sources: tuple[SourceRecord, ...]
    permissions: tuple[PermissionRecord, ...]
    restrictions: tuple[RestrictionRecord, ...]
    panels: tuple[PanelBindingRecord, ...]
    routes: tuple[RouteActivationRecord, ...]
    blocked_items: tuple[BlockedItemRecord, ...]
    features: tuple[FeatureAcquisitionEvidence, ...]

    def feature(self, feature_key: str) -> FeatureAcquisitionEvidence:
        for entry in self.features:
            if entry.feature_key == feature_key:
                return entry
        raise CrosswalkQueryError(
            "unknown_feature_key",
            f"Feature key '{feature_key}' is not present in the crosswalk.",
        )

    def route(self, route_id: str) -> RouteActivationRecord:
        for entry in self.routes:
            if entry.route_id == route_id:
                return entry
        raise CrosswalkQueryError(
            "unknown_route_id",
            f"Route id '{route_id}' is not present in the crosswalk.",
        )

    def identity(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "schema_version": self.schema_version,
            "crosswalk_id": self.crosswalk_id,
            "artifact_kind": self.artifact_kind,
            "status": self.status,
            "prepared_on": self.prepared_on,
            "baseline_main_sha": self.baseline_main_sha,
            "document_digest_sha256": self.document_digest_sha256,
        }

    def to_dict(self) -> dict[str, Any]:
        """Full canonical crosswalk view (metadata only, no feature values)."""
        return {
            **self.identity(),
            "holds": _thaw(self.holds),
            "evidence_register": [item.to_dict() for item in self.evidence],
            "sources": [item.to_dict() for item in self.sources],
            "permissions": [item.to_dict() for item in self.permissions],
            "restrictions": [item.to_dict() for item in self.restrictions],
            "panels": [item.to_dict() for item in self.panels],
            "routes": [item.to_dict() for item in self.routes],
            "blocked_items": [item.to_dict() for item in self.blocked_items],
            "feature_count": len(self.features),
            "features": [item.to_dict() for item in self.features],
            "result_state": RESULT_STATE,
        }


@dataclass(frozen=True, slots=True)
class FeatureEvidenceQuery:
    filters: Mapping[str, Any]
    features: tuple[FeatureAcquisitionEvidence, ...]
    routes: tuple[RouteActivationRecord, ...]
    crosswalk: AcquisitionEvidenceCrosswalk

    def to_dict(self) -> dict[str, Any]:
        return {
            "query_schema": QUERY_SCHEMA_ID,
            "crosswalk_id": self.crosswalk.crosswalk_id,
            "crosswalk_schema_version": self.crosswalk.schema_version,
            "crosswalk_status": self.crosswalk.status,
            "crosswalk_digest_sha256": self.crosswalk.document_digest_sha256,
            "filters": _thaw(self.filters),
            "matched_feature_count": len(self.features),
            "matched_route_count": len(self.routes),
            "features": [item.to_dict() for item in self.features],
            "routes": [item.to_dict() for item in self.routes],
            "holds": _thaw(self.crosswalk.holds),
            "result_state": RESULT_STATE,
            "cad_probability_computed": False,
            "read_only": True,
            "files_written": False,
        }


# --------------------------------------------------------------------------- #
# Primitive helpers                                                           #
# --------------------------------------------------------------------------- #


def _fail(code: str, message: str, path: str) -> None:
    raise CrosswalkValidationError(code, message, path=path)


def _is_mapping(value: Any) -> bool:
    return isinstance(value, Mapping)


def _thaw(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _thaw(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw(item) for item in value]
    if isinstance(value, list):
        return [_thaw(item) for item in value]
    return value


def _freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType({key: _freeze(item) for key, item in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(item) for item in value)
    return value


def _require_mapping(value: Any, path: str, code: str = "expected_object") -> Mapping[str, Any]:
    if not _is_mapping(value):
        _fail(code, "Expected a JSON object.", path)
    return value


def _require_sequence(value: Any, path: str, code: str = "expected_array") -> Sequence[Any]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        _fail(code, "Expected a JSON array.", path)
    return value


def _require_str(value: Any, path: str, *, allow_empty: bool = False) -> str:
    if not isinstance(value, str):
        _fail("expected_string", "Expected a JSON string.", path)
    if not allow_empty and not value.strip():
        _fail("empty_string", "Expected a non-empty string.", path)
    return value


def _require_bool(value: Any, path: str) -> bool:
    if not isinstance(value, bool):
        _fail("expected_boolean", "Expected a JSON boolean.", path)
    return value


def _require_int(value: Any, path: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        _fail("expected_integer", "Expected a JSON integer.", path)
    return value


def _reject_unknown_keys(
    mapping: Mapping[str, Any], allowed: Iterable[str], path: str
) -> None:
    allowed_set = set(allowed)
    for key in mapping:
        if not isinstance(key, str):
            _fail("unknown_field", "Object keys must be strings.", path)
        if key not in allowed_set:
            _fail(
                "unknown_field",
                f"Unknown property '{key}' is not permitted in this block.",
                f"{path}.{key}",
            )


def _require_exact_keys(
    mapping: Mapping[str, Any], expected: Iterable[str], path: str
) -> None:
    expected_set = set(expected)
    actual = set(mapping)
    missing = sorted(expected_set - actual)
    if missing:
        _fail(
            "missing_field",
            f"Missing required property '{missing[0]}'.",
            f"{path}.{missing[0]}",
        )
    _reject_unknown_keys(mapping, expected_set, path)


def _require_unique(values: Sequence[str], path: str, code: str, label: str) -> None:
    seen: set[str] = set()
    for value in values:
        if value in seen:
            _fail(code, f"Duplicate {label} '{value}'.", path)
        seen.add(value)


def canonical_json(payload: Any) -> str:
    """Stable canonical JSON used for digests and determinism checks."""
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def crosswalk_document_digest(document: Mapping[str, Any]) -> str:
    return hashlib.sha256(canonical_json(document).encode("utf-8")).hexdigest()


def _reference_path_is_safe(reference: str, path: str) -> None:
    if not reference:
        _fail("invalid_reference_path", "Reference path is empty.", path)
    if reference.startswith(("/", "\\")) or "\\" in reference:
        _fail(
            "invalid_reference_path",
            "Reference paths must be repository-relative POSIX paths.",
            path,
        )
    segments = reference.split("/")
    if any(segment in ("", ".", "..") for segment in segments):
        _fail(
            "invalid_reference_path",
            "Reference paths may not contain '.', '..' or empty segments.",
            path,
        )
    target = (REPO_ROOT / reference).resolve()
    try:
        target.relative_to(REPO_ROOT.resolve())
    except ValueError:  # pragma: no cover - defensive containment guard
        _fail(
            "invalid_reference_path",
            "Reference path escapes the repository root.",
            path,
        )
    if not target.is_file():
        _fail(
            "missing_reference_document",
            "Referenced repository document does not exist.",
            path,
        )


# --------------------------------------------------------------------------- #
# Taxonomy and register validators                                            #
# --------------------------------------------------------------------------- #


def _validate_taxonomy(
    document: Mapping[str, Any],
    key: str,
    expected: Mapping[str, str],
    path: str,
) -> None:
    block = _require_mapping(document.get(key), f"{path}.{key}")
    _require_exact_keys(block, list(expected), f"{path}.{key}")
    for name, definition in expected.items():
        text = _require_str(block.get(name), f"{path}.{key}.{name}")
        if text != definition:
            _fail(
                "taxonomy_definition_mismatch",
                f"Frozen definition for '{name}' differs from the registered text.",
                f"{path}.{key}.{name}",
            )


def _validate_offline_clauses(document: Mapping[str, Any]) -> None:
    clauses = _require_sequence(document.get("offline_clauses"), "$.offline_clauses")
    actual = tuple(_require_str(item, f"$.offline_clauses[{index}]") for index, item in enumerate(clauses))
    if actual != OFFLINE_CLAUSES:
        _fail(
            "offline_clause_mismatch",
            "Offline/read-only clauses must match the frozen statements exactly.",
            "$.offline_clauses",
        )


def _validate_no_result_contract(document: Mapping[str, Any]) -> None:
    block = _require_mapping(document.get("no_result_contract"), "$.no_result_contract")
    _require_exact_keys(block, list(NO_RESULT_CONTRACT), "$.no_result_contract")
    for key, expected in NO_RESULT_CONTRACT.items():
        value = _require_str(block.get(key), f"$.no_result_contract.{key}")
        if value != expected:
            _fail(
                "no_result_contract_mismatch",
                "The no-result contract may not be weakened.",
                f"$.no_result_contract.{key}",
            )


def _validate_revision_history(document: Mapping[str, Any]) -> None:
    history = _require_sequence(document.get("revision_history"), "$.revision_history")
    if not history:
        _fail(
            "revision_history_missing",
            "At least one revision-history entry is required.",
            "$.revision_history",
        )
    for index, entry in enumerate(history):
        path = f"$.revision_history[{index}]"
        block = _require_mapping(entry, path)
        _require_exact_keys(
            block, ("version", "date", "change", "authorization_impact"), path
        )
        _require_str(block.get("version"), f"{path}.version")
        _require_str(block.get("date"), f"{path}.date")
        _require_str(block.get("change"), f"{path}.change")
        _require_str(
            block.get("authorization_impact"), f"{path}.authorization_impact"
        )
    first = _require_mapping(history[0], "$.revision_history[0]")
    if first.get("version") != CROSSWALK_SCHEMA_VERSION:
        _fail(
            "revision_history_version_mismatch",
            "The first revision entry must record the current schema version.",
            "$.revision_history[0].version",
        )


def _validate_holds(document: Mapping[str, Any]) -> Mapping[str, Any]:
    block = _require_mapping(document.get("holds"), "$.holds")
    _require_exact_keys(block, list(EXPECTED_HOLDS), "$.holds")

    for key in (
        "gate_pt_p1_target_population_moment",
        "gate_pt_p3_formal_research",
        "gate_pt_p5_clinical_readiness_claims",
    ):
        value = _require_str(block.get(key), f"$.holds.{key}")
        if value != EXPECTED_HOLDS[key]:
            _fail(
                "scientific_hold_promotion",
                f"Scientific hold '{key}' may not be changed or lifted here.",
                f"$.holds.{key}",
            )

    for key in (
        "uci412_scientific_hold",
        "real_data_training_authorized",
        "real_model_artifacts_created",
        "patient_data_accessed",
        "new_endpoints_added",
        "frozen_contracts_modified",
        "github_workflows_modified",
    ):
        value = _require_bool(block.get(key), f"$.holds.{key}")
        if value is not EXPECTED_HOLDS[key]:
            _fail(
                "scientific_hold_promotion",
                f"Holds flag '{key}' may not be changed or lifted here.",
                f"$.holds.{key}",
            )

    counts = _require_mapping(
        block.get("owner_verified_pre_angiography_feature_counts"),
        "$.holds.owner_verified_pre_angiography_feature_counts",
    )
    _require_exact_keys(
        counts,
        list(EXPECTED_HOLDS["owner_verified_pre_angiography_feature_counts"]),
        "$.holds.owner_verified_pre_angiography_feature_counts",
    )
    for source_id, expected in EXPECTED_HOLDS[
        "owner_verified_pre_angiography_feature_counts"
    ].items():
        value = _require_int(
            counts.get(source_id),
            f"$.holds.owner_verified_pre_angiography_feature_counts.{source_id}",
        )
        if value != expected:
            _fail(
                "timing_promotion_without_owner_evidence",
                "Owner-verified pre-angiography timing counts are frozen at zero.",
                f"$.holds.owner_verified_pre_angiography_feature_counts.{source_id}",
            )

    registered = _require_mapping(
        block.get("registered_feature_counts"), "$.holds.registered_feature_counts"
    )
    _require_exact_keys(
        registered,
        list(EXPECTED_HOLDS["registered_feature_counts"]),
        "$.holds.registered_feature_counts",
    )
    for source_id, expected in EXPECTED_HOLDS["registered_feature_counts"].items():
        value = _require_int(
            registered.get(source_id),
            f"$.holds.registered_feature_counts.{source_id}",
        )
        if value != expected:
            _fail(
                "registered_feature_count_mismatch",
                "Registered feature counts may not be restated.",
                f"$.holds.registered_feature_counts.{source_id}",
            )

    covered = _require_str(
        block.get("uci412_basic_clinical_owner_verified_pre_angiography"),
        "$.holds.uci412_basic_clinical_owner_verified_pre_angiography",
    )
    if covered != EXPECTED_HOLDS["uci412_basic_clinical_owner_verified_pre_angiography"]:
        _fail(
            "timing_promotion_without_owner_evidence",
            "UCI-412 owner-verified pre-angiography timing remains 0/16.",
            "$.holds.uci412_basic_clinical_owner_verified_pre_angiography",
        )
    return block


def _validate_evidence_register(
    document: Mapping[str, Any],
) -> tuple[EvidenceRecord, ...]:
    entries = _require_sequence(
        document.get("evidence_register"), "$.evidence_register"
    )
    records: list[EvidenceRecord] = []
    seen: set[str] = set()
    for index, entry in enumerate(entries):
        path = f"$.evidence_register[{index}]"
        block = _require_mapping(entry, path)
        _require_exact_keys(
            block,
            (
                "evidence_id",
                "evidence_class",
                "reference_path",
                "establishes_feature_definition",
                "establishes_acquisition_timing",
                "owner_attested_timing_evidence",
                "summary",
            ),
            path,
        )
        evidence_id = _require_str(block.get("evidence_id"), f"{path}.evidence_id")
        if evidence_id in seen:
            _fail("duplicate_evidence_id", "Duplicate evidence id.", path)
        seen.add(evidence_id)
        if evidence_id not in EVIDENCE_REGISTER:
            _fail(
                "unregistered_evidence_id",
                "Evidence id is not part of the frozen evidence register.",
                f"{path}.evidence_id",
            )
        frozen = EVIDENCE_REGISTER[evidence_id]

        evidence_class = _require_str(
            block.get("evidence_class"), f"{path}.evidence_class"
        )
        if evidence_class not in EVIDENCE_CLASS_TAXONOMY:
            _fail(
                "invalid_evidence_class",
                "Evidence class is not in the frozen taxonomy.",
                f"{path}.evidence_class",
            )
        if evidence_class != frozen["evidence_class"]:
            _fail(
                "evidence_class_mismatch",
                "Evidence class does not match the frozen register.",
                f"{path}.evidence_class",
            )
        if evidence_class in OWNER_TIMING_EVIDENCE_CLASSES:
            _fail(
                "timing_promotion_without_owner_evidence",
                "No owner-timing evidence class exists in schema version 1.0.0.",
                f"{path}.evidence_class",
            )

        reference_path = _require_str(
            block.get("reference_path"), f"{path}.reference_path"
        )
        _reference_path_is_safe(reference_path, f"{path}.reference_path")
        if reference_path != frozen["reference_path"]:
            _fail(
                "reference_path_mismatch",
                "Reference path does not match the frozen register.",
                f"{path}.reference_path",
            )

        definition_flag = _require_bool(
            block.get("establishes_feature_definition"),
            f"{path}.establishes_feature_definition",
        )
        if definition_flag is not frozen["establishes_feature_definition"]:
            _fail(
                "evidence_capability_mismatch",
                "Definition-evidence capability does not match the frozen register.",
                f"{path}.establishes_feature_definition",
            )
        timing_flag = _require_bool(
            block.get("establishes_acquisition_timing"),
            f"{path}.establishes_acquisition_timing",
        )
        if timing_flag:
            _fail(
                "evidence_class_cannot_establish_timing",
                "This evidence class cannot establish acquisition timing.",
                f"{path}.establishes_acquisition_timing",
            )
        owner_flag = _require_bool(
            block.get("owner_attested_timing_evidence"),
            f"{path}.owner_attested_timing_evidence",
        )
        if owner_flag:
            _fail(
                "timing_promotion_without_owner_evidence",
                "No owner-attested timing evidence exists for any registered feature.",
                f"{path}.owner_attested_timing_evidence",
            )
        summary = _require_str(block.get("summary"), f"{path}.summary")
        records.append(
            EvidenceRecord(
                evidence_id=evidence_id,
                evidence_class=evidence_class,
                reference_path=reference_path,
                establishes_feature_definition=definition_flag,
                establishes_acquisition_timing=timing_flag,
                owner_attested_timing_evidence=owner_flag,
                summary=summary,
            )
        )

    missing = sorted(set(EVIDENCE_REGISTER) - seen)
    if missing:
        _fail(
            "missing_evidence_id",
            f"Frozen evidence id '{missing[0]}' is missing from the register.",
            "$.evidence_register",
        )
    return tuple(records)


def _validate_sources(document: Mapping[str, Any]) -> tuple[SourceRecord, ...]:
    entries = _require_sequence(document.get("sources"), "$.sources")
    records: list[SourceRecord] = []
    seen: set[str] = set()
    for index, entry in enumerate(entries):
        path = f"$.sources[{index}]"
        block = _require_mapping(entry, path)
        _require_exact_keys(
            block,
            (
                "source_id",
                "dataset_id",
                "track",
                "panel_ids",
                "permission_id",
                "provenance_statement",
            ),
            path,
        )
        source_id = _require_str(block.get("source_id"), f"{path}.source_id")
        if source_id in seen:
            _fail("duplicate_source_id", "Duplicate source id.", path)
        seen.add(source_id)
        if source_id not in SOURCES:
            _fail(
                "unknown_source_id",
                "Source id is not one of the two registered feature sources.",
                f"{path}.source_id",
            )
        frozen = SOURCES[source_id]
        dataset_id = _require_str(block.get("dataset_id"), f"{path}.dataset_id")
        if dataset_id != frozen["dataset_id"]:
            _fail(
                "source_mismatch",
                "Dataset id does not belong to this source.",
                f"{path}.dataset_id",
            )
        track = _require_str(block.get("track"), f"{path}.track")
        if track != frozen["track"]:
            _fail("invalid_track", "Unexpected track.", f"{path}.track")
        panel_ids = _require_sequence(block.get("panel_ids"), f"{path}.panel_ids")
        panel_tuple = tuple(
            _require_str(item, f"{path}.panel_ids[{position}]")
            for position, item in enumerate(panel_ids)
        )
        if panel_tuple != tuple(frozen["panel_ids"]):
            _fail(
                "source_mismatch",
                "Panel membership does not match the frozen source registration.",
                f"{path}.panel_ids",
            )
        permission_id = _require_str(
            block.get("permission_id"), f"{path}.permission_id"
        )
        if permission_id != frozen["permission_id"]:
            _fail(
                "permission_mismatch",
                "Permission id does not match the frozen source registration.",
                f"{path}.permission_id",
            )
        statement = _require_str(
            block.get("provenance_statement"), f"{path}.provenance_statement"
        )
        records.append(
            SourceRecord(
                source_id=source_id,
                dataset_id=dataset_id,
                track=track,
                panel_ids=panel_tuple,
                permission_id=permission_id,
                provenance_statement=statement,
            )
        )
    missing = sorted(set(SOURCES) - seen)
    if missing:
        _fail(
            "missing_source_id",
            f"Registered source '{missing[0]}' is missing.",
            "$.sources",
        )
    return tuple(records)


def _validate_permissions(document: Mapping[str, Any]) -> tuple[PermissionRecord, ...]:
    entries = _require_sequence(document.get("permissions"), "$.permissions")
    records: list[PermissionRecord] = []
    seen: set[str] = set()
    for index, entry in enumerate(entries):
        path = f"$.permissions[{index}]"
        block = _require_mapping(entry, path)
        _require_exact_keys(
            block,
            (
                "permission_id",
                "source_id",
                "permission_status",
                "real_data_execution_authorized_by_this_artifact",
                "activation_by_this_artifact",
                "statement",
            ),
            path,
        )
        permission_id = _require_str(
            block.get("permission_id"), f"{path}.permission_id"
        )
        if permission_id in seen:
            _fail("duplicate_permission_id", "Duplicate permission id.", path)
        seen.add(permission_id)
        if permission_id not in PERMISSIONS:
            _fail(
                "unknown_permission_id",
                "Permission id is not part of the frozen permission register.",
                f"{path}.permission_id",
            )
        frozen = PERMISSIONS[permission_id]
        source_id = _require_str(block.get("source_id"), f"{path}.source_id")
        if source_id != frozen["source_id"]:
            _fail(
                "source_mismatch",
                "Permission is bound to a different source.",
                f"{path}.source_id",
            )
        permission_status = _require_str(
            block.get("permission_status"), f"{path}.permission_status"
        )
        if permission_status not in PERMISSION_STATUS_TAXONOMY:
            _fail(
                "invalid_permission_status",
                "Permission status is not in the frozen taxonomy.",
                f"{path}.permission_status",
            )
        if permission_status != frozen["permission_status"]:
            _fail(
                "permission_mismatch",
                "Permission status may not be promoted by this artifact.",
                f"{path}.permission_status",
            )
        authorized = _require_bool(
            block.get("real_data_execution_authorized_by_this_artifact"),
            f"{path}.real_data_execution_authorized_by_this_artifact",
        )
        if authorized:
            _fail(
                "unauthorized_activation",
                "This evidence artifact may not authorize real-data execution.",
                f"{path}.real_data_execution_authorized_by_this_artifact",
            )
        activation = _require_str(
            block.get("activation_by_this_artifact"),
            f"{path}.activation_by_this_artifact",
        )
        if activation != "NONE":
            _fail(
                "unauthorized_activation",
                "This evidence artifact may not activate any scope.",
                f"{path}.activation_by_this_artifact",
            )
        statement = _require_str(block.get("statement"), f"{path}.statement")
        records.append(
            PermissionRecord(
                permission_id=permission_id,
                source_id=source_id,
                permission_status=permission_status,
                real_data_execution_authorized_by_this_artifact=False,
                activation_by_this_artifact=activation,
                statement=statement,
            )
        )
    missing = sorted(set(PERMISSIONS) - seen)
    if missing:
        _fail(
            "missing_permission_id",
            f"Registered permission '{missing[0]}' is missing.",
            "$.permissions",
        )
    return tuple(records)


def _validate_restrictions(document: Mapping[str, Any]) -> tuple[RestrictionRecord, ...]:
    entries = _require_sequence(document.get("restrictions"), "$.restrictions")
    records: list[RestrictionRecord] = []
    seen: set[str] = set()
    for index, entry in enumerate(entries):
        path = f"$.restrictions[{index}]"
        block = _require_mapping(entry, path)
        _require_exact_keys(
            block,
            (
                "restriction_id",
                "statement",
                "applies_to_route_ids",
                "applies_to_source_ids",
            ),
            path,
        )
        restriction_id = _require_str(
            block.get("restriction_id"), f"{path}.restriction_id"
        )
        if restriction_id in seen:
            _fail("duplicate_restriction_id", "Duplicate restriction id.", path)
        seen.add(restriction_id)
        if restriction_id not in RESTRICTIONS:
            _fail(
                "unknown_restriction_id",
                "Restriction id is not part of the frozen restriction register.",
                f"{path}.restriction_id",
            )
        statement = _require_str(block.get("statement"), f"{path}.statement")
        route_ids = tuple(
            _require_str(item, f"{path}.applies_to_route_ids[{position}]")
            for position, item in enumerate(
                _require_sequence(
                    block.get("applies_to_route_ids"), f"{path}.applies_to_route_ids"
                )
            )
        )
        for route_id in route_ids:
            if route_id not in ROUTE_SPECS:
                _fail(
                    "unknown_route_id",
                    "Restriction references an unregistered route.",
                    f"{path}.applies_to_route_ids",
                )
        source_ids = tuple(
            _require_str(item, f"{path}.applies_to_source_ids[{position}]")
            for position, item in enumerate(
                _require_sequence(
                    block.get("applies_to_source_ids"),
                    f"{path}.applies_to_source_ids",
                )
            )
        )
        for source_id in source_ids:
            if source_id not in SOURCES:
                _fail(
                    "unknown_source_id",
                    "Restriction references an unregistered source.",
                    f"{path}.applies_to_source_ids",
                )
        records.append(
            RestrictionRecord(
                restriction_id=restriction_id,
                statement=statement,
                applies_to_route_ids=route_ids,
                applies_to_source_ids=source_ids,
            )
        )
    missing = sorted(set(RESTRICTIONS) - seen)
    if missing:
        _fail(
            "missing_restriction_id",
            f"Frozen restriction '{missing[0]}' is missing.",
            "$.restrictions",
        )
    return tuple(records)


def _validate_panel_bindings(document: Mapping[str, Any]) -> tuple[PanelBindingRecord, ...]:
    entries = _require_sequence(document.get("panels"), "$.panels")
    by_id = {panel.panel_id: panel for panel in PANEL_SPECS}
    records: list[PanelBindingRecord] = []
    seen: set[str] = set()
    for index, entry in enumerate(entries):
        path = f"$.panels[{index}]"
        block = _require_mapping(entry, path)
        _require_exact_keys(
            block,
            ("panel_id", "dataset_id", "panel_version", "feature_count", "registered_in"),
            path,
        )
        panel_id = _require_str(block.get("panel_id"), f"{path}.panel_id")
        if panel_id in seen:
            _fail("duplicate_panel_id", "Duplicate panel id.", path)
        seen.add(panel_id)
        if panel_id not in by_id:
            _fail(
                "unknown_panel_id",
                "Panel id is not one of the four registered panels.",
                f"{path}.panel_id",
            )
        spec = by_id[panel_id]
        dataset_id = _require_str(block.get("dataset_id"), f"{path}.dataset_id")
        if dataset_id != spec.dataset_id:
            _fail(
                "panel_dataset_mismatch",
                "Panel dataset id does not match the registered panel.",
                f"{path}.dataset_id",
            )
        version = _require_str(block.get("panel_version"), f"{path}.panel_version")
        if version != spec.panel_version:
            _fail(
                "panel_version_mismatch",
                "Panel version does not match the registered panel.",
                f"{path}.panel_version",
            )
        feature_count = _require_int(
            block.get("feature_count"), f"{path}.feature_count"
        )
        if feature_count != len(spec.features):
            _fail(
                "panel_feature_count_mismatch",
                "Panel feature count does not match the registered roster.",
                f"{path}.feature_count",
            )
        registered_in = _require_str(
            block.get("registered_in"), f"{path}.registered_in"
        )
        if registered_in != PANEL_REGISTRY_REFERENCE:
            _fail(
                "panel_registry_mismatch",
                "Panels must be referenced, not redefined.",
                f"{path}.registered_in",
            )
        records.append(
            PanelBindingRecord(
                panel_id=panel_id,
                dataset_id=dataset_id,
                panel_version=version,
                feature_count=feature_count,
                registered_in=registered_in,
            )
        )
    missing = sorted(set(by_id) - seen)
    if missing:
        _fail(
            "missing_panel_id",
            f"Registered panel '{missing[0]}' is missing.",
            "$.panels",
        )
    return tuple(records)


def _validate_routes(document: Mapping[str, Any]) -> tuple[RouteActivationRecord, ...]:
    entries = _require_sequence(document.get("routes"), "$.routes")
    records: list[RouteActivationRecord] = []
    seen: set[str] = set()
    for index, entry in enumerate(entries):
        path = f"$.routes[{index}]"
        block = _require_mapping(entry, path)
        _require_exact_keys(
            block,
            (
                "route_id",
                "dataset_id",
                "panel_id",
                "activation_state",
                "prediction_time_admissibility",
                "authorization_status",
                "evaluation_status",
                "blocked",
                "permitted_operations",
                "forbidden_operations",
                "restriction_ids",
            ),
            path,
        )
        route_id = _require_str(block.get("route_id"), f"{path}.route_id")
        if route_id in seen:
            _fail("duplicate_route_id", "Duplicate route id.", path)
        seen.add(route_id)
        if route_id not in ROUTE_SPECS:
            _fail(
                "unknown_route_id",
                "Route id is not one of the five registered research routes.",
                f"{path}.route_id",
            )
        frozen = ROUTE_SPECS[route_id]

        dataset_id = _require_str(block.get("dataset_id"), f"{path}.dataset_id")
        if dataset_id != frozen["dataset_id"]:
            _fail(
                "source_mismatch",
                "Route dataset does not match the registered route.",
                f"{path}.dataset_id",
            )
        panel_id = _require_str(block.get("panel_id"), f"{path}.panel_id")
        if panel_id != frozen["panel_id"]:
            _fail(
                "route_panel_mismatch",
                "Route panel does not match the registered route.",
                f"{path}.panel_id",
            )
        panel_spec = PANELS_BY_ID[panel_id]
        if panel_spec.dataset_id != dataset_id:
            _fail(
                "panel_dataset_mismatch",
                "Route crosses datasets through a foreign panel.",
                f"{path}.panel_id",
            )

        activation_state = _require_str(
            block.get("activation_state"), f"{path}.activation_state"
        )
        if activation_state not in ROUTE_ACTIVATION_STATES:
            _fail(
                "invalid_activation_state",
                "Activation state is not in the frozen vocabulary.",
                f"{path}.activation_state",
            )
        if activation_state != frozen["activation_state"]:
            _fail(
                "unauthorized_route_activation",
                "Route activation state may not be changed by this artifact.",
                f"{path}.activation_state",
            )

        for key in (
            "prediction_time_admissibility",
            "authorization_status",
            "evaluation_status",
        ):
            value = _require_str(block.get(key), f"{path}.{key}")
            if value != frozen[key]:
                _fail(
                    "route_status_mismatch",
                    f"Route {key} may not be changed by this artifact.",
                    f"{path}.{key}",
                )

        blocked = _require_bool(block.get("blocked"), f"{path}.blocked")
        if blocked is not frozen["blocked"]:
            _fail(
                "unauthorized_route_activation",
                "Route blocked flag may not be changed by this artifact.",
                f"{path}.blocked",
            )

        permitted = _require_sequence(
            block.get("permitted_operations"), f"{path}.permitted_operations"
        )
        permitted_tuple = tuple(
            _require_str(item, f"{path}.permitted_operations[{position}]")
            for position, item in enumerate(permitted)
        )
        if len(set(permitted_tuple)) != len(permitted_tuple):
            _fail(
                "duplicate_operation",
                "Permitted operations must be unique.",
                f"{path}.permitted_operations",
            )
        for operation in permitted_tuple:
            if operation not in KNOWN_OPERATIONS:
                _fail(
                    "unknown_operation",
                    "Operation is not part of the frozen operation vocabulary.",
                    f"{path}.permitted_operations",
                )
            if operation in FORBIDDEN_OPERATIONS_ALWAYS:
                _fail(
                    "unauthorized_route_activation",
                    "No route may permit a real-data or clinical operation.",
                    f"{path}.permitted_operations",
                )
        if frozenset(permitted_tuple) != frozenset(frozen["permitted_operations"]):
            _fail(
                "unauthorized_route_activation",
                "Permitted operation set may not be widened or narrowed here.",
                f"{path}.permitted_operations",
            )

        forbidden = _require_sequence(
            block.get("forbidden_operations"), f"{path}.forbidden_operations"
        )
        forbidden_tuple = tuple(
            _require_str(item, f"{path}.forbidden_operations[{position}]")
            for position, item in enumerate(forbidden)
        )
        if set(forbidden_tuple) & set(permitted_tuple):
            _fail(
                "operation_overlap",
                "An operation cannot be both permitted and forbidden.",
                f"{path}.forbidden_operations",
            )
        missing_forbidden = sorted(
            FORBIDDEN_OPERATIONS_ALWAYS - set(forbidden_tuple)
        )
        if missing_forbidden:
            _fail(
                "unauthorized_route_activation",
                f"Route must keep '{missing_forbidden[0]}' forbidden.",
                f"{path}.forbidden_operations",
            )

        restriction_ids = tuple(
            _require_str(item, f"{path}.restriction_ids[{position}]")
            for position, item in enumerate(
                _require_sequence(block.get("restriction_ids"), f"{path}.restriction_ids")
            )
        )
        for restriction_id in restriction_ids:
            if restriction_id not in RESTRICTIONS:
                _fail(
                    "unknown_restriction_id",
                    "Route references an unregistered restriction.",
                    f"{path}.restriction_ids",
                )
        missing_restrictions = sorted(
            set(frozen["required_restriction_ids"]) - set(restriction_ids)
        )
        if missing_restrictions:
            _fail(
                "missing_route_restriction",
                f"Route must declare restriction '{missing_restrictions[0]}'.",
                f"{path}.restriction_ids",
            )

        records.append(
            RouteActivationRecord(
                route_id=route_id,
                dataset_id=dataset_id,
                panel_id=panel_id,
                activation_state=activation_state,
                prediction_time_admissibility=frozen["prediction_time_admissibility"],
                authorization_status=frozen["authorization_status"],
                evaluation_status=frozen["evaluation_status"],
                blocked=blocked,
                permitted_operations=tuple(sorted(permitted_tuple)),
                forbidden_operations=tuple(sorted(forbidden_tuple)),
                restriction_ids=restriction_ids,
            )
        )
    missing = sorted(set(ROUTE_SPECS) - seen)
    if missing:
        _fail(
            "missing_route_id",
            f"Registered route '{missing[0]}' is missing.",
            "$.routes",
        )
    return tuple(records)


def _validate_blocked_items(
    document: Mapping[str, Any], routes: Sequence[RouteActivationRecord]
) -> tuple[BlockedItemRecord, ...]:
    entries = _require_sequence(document.get("blocked_items"), "$.blocked_items")
    routes_by_id = {route.route_id: route for route in routes}
    records: list[BlockedItemRecord] = []
    seen: set[str] = set()
    for index, entry in enumerate(entries):
        path = f"$.blocked_items[{index}]"
        block = _require_mapping(entry, path)
        _require_exact_keys(
            block,
            (
                "item_id",
                "route_id",
                "state",
                "max_permitted_operation",
                "reason_restriction_id",
            ),
            path,
        )
        item_id = _require_str(block.get("item_id"), f"{path}.item_id")
        if item_id in seen:
            _fail("duplicate_blocked_item", "Duplicate blocked item id.", path)
        seen.add(item_id)
        if item_id not in BLOCKED_ITEMS:
            _fail(
                "unknown_blocked_item",
                "Blocked item is not part of the frozen blocked set.",
                f"{path}.item_id",
            )
        frozen = BLOCKED_ITEMS[item_id]
        route_id = _require_str(block.get("route_id"), f"{path}.route_id")
        if route_id != frozen["route_id"]:
            _fail(
                "source_mismatch",
                "Blocked item is bound to a different route.",
                f"{path}.route_id",
            )
        state = _require_str(block.get("state"), f"{path}.state")
        if state != "BLOCKED":
            _fail(
                "unauthorized_route_activation",
                "This blocked item must remain BLOCKED.",
                f"{path}.state",
            )
        max_operation = _require_str(
            block.get("max_permitted_operation"), f"{path}.max_permitted_operation"
        )
        if max_operation != "route_contract_query":
            _fail(
                "unauthorized_route_activation",
                "A blocked item may permit contract-query metadata only.",
                f"{path}.max_permitted_operation",
            )
        reason = _require_str(
            block.get("reason_restriction_id"), f"{path}.reason_restriction_id"
        )
        if reason != frozen["reason_restriction_id"]:
            _fail(
                "missing_route_restriction",
                "Blocked item must reference its registered restriction.",
                f"{path}.reason_restriction_id",
            )
        route = routes_by_id[route_id]
        if frozenset(route.permitted_operations) != CONTRACT_QUERY_ONLY:
            _fail(
                "unauthorized_route_activation",
                "A blocked item's route must permit contract query only.",
                f"{path}.route_id",
            )
        records.append(
            BlockedItemRecord(
                item_id=item_id,
                route_id=route_id,
                state=state,
                max_permitted_operation=max_operation,
                reason_restriction_id=reason,
            )
        )
    missing = sorted(set(BLOCKED_ITEMS) - seen)
    if missing:
        _fail(
            "missing_blocked_item",
            f"Blocked item '{missing[0]}' is missing.",
            "$.blocked_items",
        )
    return tuple(records)


# --------------------------------------------------------------------------- #
# Feature validation                                                          #
# --------------------------------------------------------------------------- #


def _expected_feature_panels(
    dataset_id: str, feature_name: str
) -> tuple[str, ...]:
    panels = tuple(
        panel.panel_id
        for panel in PANEL_SPECS
        if panel.dataset_id == dataset_id and feature_name in panel.features
    )
    if not panels:
        _fail(
            "unregistered_feature",
            "Feature is not part of any registered panel for this dataset.",
            "$.features",
        )
    return panels


def _expected_feature_record(dataset_id: str, feature_name: str) -> dict[str, Any]:
    """Frozen expectations for one registered feature (no clinical schema)."""
    if dataset_id == "DA-A1":
        claim_domain, availability = UCI412_CLAIMS[feature_name]
        if feature_name in UCI412_BASIC_FEATURES:
            definition = UCI412_BASIC_DEFINITION_EVIDENCE
            restrictions = UCI412_BASIC_RESTRICTIONS
            disposition = "EVIDENCE_RECORDED_NO_ACTIVATION_CHANGE"
        else:
            definition = UCI412_LAB_DEFINITION_EVIDENCE
            restrictions = UCI412_LAB_RESTRICTIONS
            disposition = "EVIDENCE_RECORDED_EXTENSION_REMAINS_BLOCKED"
        claim = {
            "register_evidence_id": "EV-UCI412-REGISTERED-DICTIONARY",
            "source_domain": claim_domain,
            "availability_at_decision_time": availability,
        }
        channel = DOMAIN_TO_CHANNEL[claim_domain]
        return {
            "source_id": SOURCE_UCI412,
            "permission_id": "PERM-UCI412-SCIENTIFIC-HOLD",
            "definition_evidence_ids": definition,
            "registered_source_claim": claim,
            "channel": channel,
            "channel_status": (
                "VERIFIED_REGISTERED_SOURCE_DOMAIN"
                if feature_name in UCI412_BASIC_FEATURES
                else "PROPOSED_FUTURE_ACQUISITION_CHANNEL"
            ),
            "channel_evidence_ids": (
                ("EV-UCI412-REGISTERED-DICTIONARY",)
                if feature_name in UCI412_BASIC_FEATURES
                else ("EV-UCI412-M3A-SPECIFICATION",)
            ),
            "restriction_ids": restrictions,
            "disposition": disposition,
        }

    channel = UCI45_PROPOSED_CHANNELS[feature_name]
    if feature_name in UCI45_RESTING_FEATURES:
        restrictions = UCI45_RESTING_RESTRICTIONS
        disposition = "EVIDENCE_RECORDED_NO_ACTIVATION_CHANGE"
        channel_evidence = ("EV-R1-CLEVELAND-MAPPING",)
    else:
        restrictions = UCI45_LAB_RESTRICTIONS
        disposition = "EVIDENCE_RECORDED_EXTENSION_REMAINS_BLOCKED"
        channel_evidence = ("EV-UCI45-REGISTERED-STAGE",)
    return {
        "source_id": SOURCE_UCI45,
        "permission_id": "PERM-UCI45-INTERNAL-EXPLORATORY",
        "definition_evidence_ids": UCI45_DEFINITION_EVIDENCE,
        "registered_source_claim": {
            "register_evidence_id": "EV-UCI45-REGISTERED-STAGE",
            "source_domain": CLAIM_UNRECORDED,
            "availability_at_decision_time": CLAIM_UNRECORDED,
        },
        "channel": channel,
        "channel_status": "PROPOSED_FUTURE_ACQUISITION_CHANNEL",
        "channel_evidence_ids": channel_evidence,
        "timing_evidence_ids": (
            ("EV-R1-CLEVELAND-MAPPING",)
            if feature_name in UCI45_RESTING_FEATURES
            else ("EV-UCI45-REGISTERED-STAGE",)
        ),
        "restriction_ids": restrictions,
        "disposition": disposition,
    }


def _validate_feature(
    entry: Mapping[str, Any],
    *,
    index: int,
    evidence_by_id: Mapping[str, EvidenceRecord],
    permissions_by_id: Mapping[str, PermissionRecord],
) -> FeatureAcquisitionEvidence:
    path = f"$.features[{index}]"
    _require_exact_keys(entry, FEATURE_KEYS, path)

    feature_key = _require_str(entry.get("feature_key"), f"{path}.feature_key")
    source_id = _require_str(entry.get("source_id"), f"{path}.source_id")
    dataset_id = _require_str(entry.get("dataset_id"), f"{path}.dataset_id")
    feature_name = _require_str(entry.get("feature_name"), f"{path}.feature_name")

    if source_id not in SOURCES:
        _fail(
            "unknown_source_id",
            "Feature references an unregistered source.",
            f"{path}.source_id",
        )
    frozen_source = SOURCES[source_id]
    if dataset_id != frozen_source["dataset_id"]:
        _fail(
            "source_mismatch",
            "Feature dataset does not belong to its declared source.",
            f"{path}.dataset_id",
        )
    if feature_key != f"{dataset_id}:{feature_name}":
        _fail(
            "feature_key_mismatch",
            "Feature key must be '<dataset_id>:<feature_name>'.",
            f"{path}.feature_key",
        )

    if feature_name in PROHIBITED_FEATURE_NAMES:
        _fail(
            "prohibited_feature",
            "Outcome, angiography, identifier, wearable or exercise-test "
            "variables may never appear in this crosswalk.",
            f"{path}.feature_name",
        )

    roster = {
        "DA-A1": UCI412_BASIC_FEATURES + UCI412_LAB_FEATURES,
        "DA-A2": UCI45_RESTING_FEATURES + UCI45_LAB_FEATURES,
    }[dataset_id]
    if feature_name not in roster:
        _fail(
            "unregistered_feature",
            "Feature is not part of the registered feature roster for this dataset.",
            f"{path}.feature_name",
        )

    expected = _expected_feature_record(dataset_id, feature_name)
    expected_panels = _expected_feature_panels(dataset_id, feature_name)

    panels = tuple(
        _require_str(item, f"{path}.panels[{position}]")
        for position, item in enumerate(
            _require_sequence(entry.get("panels"), f"{path}.panels")
        )
    )
    if panels != expected_panels:
        _fail(
            "source_mismatch",
            "Panel membership does not match the registered panel rosters.",
            f"{path}.panels",
        )

    definition_ids = tuple(
        _require_str(item, f"{path}.definition_evidence_ids[{position}]")
        for position, item in enumerate(
            _require_sequence(
                entry.get("definition_evidence_ids"),
                f"{path}.definition_evidence_ids",
            )
        )
    )
    if definition_ids != tuple(expected["definition_evidence_ids"]):
        _fail(
            "evidence_set_mismatch",
            "Definition-evidence set does not match the frozen expectation.",
            f"{path}.definition_evidence_ids",
        )
    for evidence_id in definition_ids:
        record = evidence_by_id.get(evidence_id)
        if record is None:
            _fail(
                "unknown_evidence_id",
                "Feature references an unregistered evidence item.",
                f"{path}.definition_evidence_ids",
            )
        if not record.establishes_feature_definition:
            _fail(
                "evidence_not_definitional",
                "Referenced evidence item does not establish a feature definition.",
                f"{path}.definition_evidence_ids",
            )

    claim_block = _require_mapping(
        entry.get("registered_source_claim"), f"{path}.registered_source_claim"
    )
    _require_exact_keys(
        claim_block, CLAIM_KEYS, f"{path}.registered_source_claim"
    )
    expected_claim = expected["registered_source_claim"]
    claim = RegisteredSourceClaim(
        register_evidence_id=_require_str(
            claim_block.get("register_evidence_id"),
            f"{path}.registered_source_claim.register_evidence_id",
        ),
        source_domain=_require_str(
            claim_block.get("source_domain"),
            f"{path}.registered_source_claim.source_domain",
        ),
        availability_at_decision_time=_require_str(
            claim_block.get("availability_at_decision_time"),
            f"{path}.registered_source_claim.availability_at_decision_time",
        ),
    )
    if claim.register_evidence_id != expected_claim["register_evidence_id"]:
        _fail(
            "evidence_set_mismatch",
            "Registered-source claim must cite the registered source contract.",
            f"{path}.registered_source_claim.register_evidence_id",
        )
    if claim.register_evidence_id not in evidence_by_id:
        _fail(
            "unknown_evidence_id",
            "Registered-source claim cites an unregistered evidence item.",
            f"{path}.registered_source_claim.register_evidence_id",
        )
    if claim.source_domain not in SOURCE_DOMAINS and claim.source_domain != CLAIM_UNRECORDED:
        _fail(
            "invalid_source_domain",
            "Source domain is not part of the registered domain vocabulary.",
            f"{path}.registered_source_claim.source_domain",
        )
    if claim.availability_at_decision_time not in AVAILABILITY_CLASSES:
        _fail(
            "invalid_availability_class",
            "Availability class is not part of the frozen vocabulary.",
            f"{path}.registered_source_claim.availability_at_decision_time",
        )
    if (
        claim.source_domain != expected_claim["source_domain"]
        or claim.availability_at_decision_time
        != expected_claim["availability_at_decision_time"]
    ):
        _fail(
            "source_mismatch",
            "Registered-source claim does not match the frozen source record.",
            f"{path}.registered_source_claim",
        )

    acquisition_block = _require_mapping(
        entry.get("acquisition"), f"{path}.acquisition"
    )
    _require_exact_keys(acquisition_block, ACQUISITION_KEYS, f"{path}.acquisition")
    channel = _require_str(
        acquisition_block.get("channel"), f"{path}.acquisition.channel"
    )
    if channel not in ACQUISITION_CHANNEL_TAXONOMY:
        _fail(
            "invalid_acquisition_channel",
            "Acquisition channel is not in the frozen taxonomy.",
            f"{path}.acquisition.channel",
        )
    if channel != expected["channel"]:
        _fail(
            "source_mismatch",
            "Acquisition channel does not match the registered source record.",
            f"{path}.acquisition.channel",
        )
    channel_status = _require_str(
        acquisition_block.get("channel_status"), f"{path}.acquisition.channel_status"
    )
    if channel_status not in CHANNEL_STATUS_TAXONOMY:
        _fail(
            "invalid_channel_status",
            "Channel status is not in the frozen taxonomy.",
            f"{path}.acquisition.channel_status",
        )
    if channel_status != expected["channel_status"]:
        _fail(
            "source_mismatch",
            "Channel status does not match the frozen source record.",
            f"{path}.acquisition.channel_status",
        )
    channel_evidence_ids = tuple(
        _require_str(item, f"{path}.acquisition.channel_evidence_ids[{position}]")
        for position, item in enumerate(
            _require_sequence(
                acquisition_block.get("channel_evidence_ids"),
                f"{path}.acquisition.channel_evidence_ids",
            )
        )
    )
    if channel_evidence_ids != tuple(expected["channel_evidence_ids"]):
        _fail(
            "evidence_set_mismatch",
            "Channel-evidence set does not match the frozen expectation.",
            f"{path}.acquisition.channel_evidence_ids",
        )
    for evidence_id in channel_evidence_ids:
        if evidence_id not in evidence_by_id:
            _fail(
                "unknown_evidence_id",
                "Channel evidence id is not registered.",
                f"{path}.acquisition.channel_evidence_ids",
            )

    timing_status = _require_str(
        acquisition_block.get("timing_status"), f"{path}.acquisition.timing_status"
    )
    if timing_status not in TIMING_STATUS_TAXONOMY:
        _fail(
            "invalid_timing_status",
            "Timing status is not in the frozen taxonomy.",
            f"{path}.acquisition.timing_status",
        )
    owner_verified = _require_bool(
        acquisition_block.get("owner_verified_pre_angiography"),
        f"{path}.acquisition.owner_verified_pre_angiography",
    )
    derived_from_channel = _require_bool(
        acquisition_block.get("timing_derived_from_channel_status"),
        f"{path}.acquisition.timing_derived_from_channel_status",
    )
    if derived_from_channel:
        _fail(
            "timing_promotion_without_owner_evidence",
            "Timing may never be derived from a verified acquisition channel.",
            f"{path}.acquisition.timing_derived_from_channel_status",
        )
    if owner_verified:
        _fail(
            "timing_promotion_without_owner_evidence",
            "No registered feature has owner-verified pre-angiography timing.",
            f"{path}.acquisition.owner_verified_pre_angiography",
        )

    expected_timing = (
        "UNVERIFIED_TIMING_REGISTERED_DOMAIN_CHANNEL"
        if channel_status == "VERIFIED_REGISTERED_SOURCE_DOMAIN"
        else "UNVERIFIED_TIMING_PROPOSED_CHANNEL"
    )
    if timing_status != expected_timing:
        _fail(
            "timing_promotion_without_owner_evidence",
            "A verified channel never implies verified pre-angiography timing.",
            f"{path}.acquisition.timing_status",
        )
    if timing_status == "OWNER_VERIFIED_PRE_ANGIOGRAPHY" and not owner_verified:
        _fail(
            "timing_status_inconsistent",
            "Owner-verified timing status requires an owner-verified record.",
            f"{path}.acquisition.timing_status",
        )

    timing_evidence_ids = tuple(
        _require_str(item, f"{path}.acquisition.timing_evidence_ids[{position}]")
        for position, item in enumerate(
            _require_sequence(
                acquisition_block.get("timing_evidence_ids"),
                f"{path}.acquisition.timing_evidence_ids",
            )
        )
    )
    expected_timing_evidence = expected.get(
        "timing_evidence_ids",
        ("EV-RH02-Q04-UCI412-TIMING-GAP",),
    )
    if timing_evidence_ids != tuple(expected_timing_evidence):
        _fail(
            "evidence_set_mismatch",
            "Timing-evidence set does not match the frozen expectation.",
            f"{path}.acquisition.timing_evidence_ids",
        )
    for evidence_id in timing_evidence_ids:
        record = evidence_by_id.get(evidence_id)
        if record is None:
            _fail(
                "unknown_evidence_id",
                "Timing evidence id is not registered.",
                f"{path}.acquisition.timing_evidence_ids",
            )
        if record.establishes_acquisition_timing:
            _fail(
                "evidence_class_cannot_establish_timing",
                "Referenced evidence cannot establish acquisition timing.",
                f"{path}.acquisition.timing_evidence_ids",
            )

    permission_id = _require_str(
        entry.get("permission_id"), f"{path}.permission_id"
    )
    permission = permissions_by_id.get(permission_id)
    if permission is None:
        _fail(
            "unknown_permission_id",
            "Feature references an unregistered permission.",
            f"{path}.permission_id",
        )
    if permission_id != expected["permission_id"] or permission.source_id != source_id:
        _fail(
            "permission_mismatch",
            "Feature permission does not match the frozen source permission.",
            f"{path}.permission_id",
        )

    restriction_ids = tuple(
        _require_str(item, f"{path}.restriction_ids[{position}]")
        for position, item in enumerate(
            _require_sequence(entry.get("restriction_ids"), f"{path}.restriction_ids")
        )
    )
    if restriction_ids != tuple(expected["restriction_ids"]):
        _fail(
            "restriction_set_mismatch",
            "Restriction set does not match the frozen expectation.",
            f"{path}.restriction_ids",
        )
    for restriction_id in restriction_ids:
        if restriction_id not in RESTRICTIONS:
            _fail(
                "unknown_restriction_id",
                "Feature references an unregistered restriction.",
                f"{path}.restriction_ids",
            )

    disposition = _require_str(
        entry.get("disposition"), f"{path}.disposition"
    )
    if disposition not in DISPOSITION_TAXONOMY:
        _fail(
            "invalid_disposition",
            "Disposition is not in the frozen taxonomy.",
            f"{path}.disposition",
        )
    if disposition != expected["disposition"]:
        _fail(
            "disposition_mismatch",
            "Disposition does not match the frozen expectation.",
            f"{path}.disposition",
        )

    return FeatureAcquisitionEvidence(
        feature_key=feature_key,
        source_id=source_id,
        dataset_id=dataset_id,
        feature_name=feature_name,
        panels=panels,
        definition_evidence_ids=definition_ids,
        registered_source_claim=claim,
        acquisition=AcquisitionEvidence(
            channel=channel,
            channel_status=channel_status,
            channel_evidence_ids=channel_evidence_ids,
            timing_status=timing_status,
            owner_verified_pre_angiography=owner_verified,
            timing_evidence_ids=timing_evidence_ids,
            timing_derived_from_channel_status=derived_from_channel,
        ),
        permission_id=permission_id,
        permission_status=permission.permission_status,
        restriction_ids=restriction_ids,
        disposition=disposition,
    )


def _validate_features(
    document: Mapping[str, Any],
    evidence: Sequence[EvidenceRecord],
    permissions: Sequence[PermissionRecord],
) -> tuple[FeatureAcquisitionEvidence, ...]:
    entries = _require_sequence(document.get("features"), "$.features")
    evidence_by_id = {item.evidence_id: item for item in evidence}
    permissions_by_id = {item.permission_id: item for item in permissions}
    records: list[FeatureAcquisitionEvidence] = []
    seen: set[str] = set()
    for index, entry in enumerate(entries):
        block = _require_mapping(entry, f"$.features[{index}]")
        record = _validate_feature(
            block,
            index=index,
            evidence_by_id=evidence_by_id,
            permissions_by_id=permissions_by_id,
        )
        if record.feature_key in seen:
            _fail(
                "duplicate_feature_key",
                "Duplicate feature key.",
                f"$.features[{index}].feature_key",
            )
        seen.add(record.feature_key)
        records.append(record)

    expected = {
        f"{dataset_id}:{name}"
        for dataset_id, names in (
            ("DA-A2", UCI45_RESTING_FEATURES + UCI45_LAB_FEATURES),
            ("DA-A1", UCI412_BASIC_FEATURES + UCI412_LAB_FEATURES),
        )
        for name in names
    }
    missing = sorted(expected - seen)
    if missing:
        _fail(
            "missing_feature",
            f"Registered feature '{missing[0]}' is missing from the crosswalk.",
            "$.features",
        )
    unexpected = sorted(seen - expected)
    if unexpected:  # pragma: no cover - unreachable while rosters stay frozen
        _fail(
            "unregistered_feature",
            f"Feature '{unexpected[0]}' is not registered.",
            "$.features",
        )

    for dataset_id, source_id in (("DA-A1", SOURCE_UCI412), ("DA-A2", SOURCE_UCI45)):
        owner_verified = sum(
            1
            for record in records
            if record.dataset_id == dataset_id
            and record.acquisition.owner_verified_pre_angiography
        )
        if owner_verified != EXPECTED_HOLDS[
            "owner_verified_pre_angiography_feature_counts"
        ][source_id]:
            _fail(
                "timing_promotion_without_owner_evidence",
                "Owner-verified pre-angiography timing count must remain zero.",
                "$.features",
            )
        counted = sum(1 for record in records if record.dataset_id == dataset_id)
        if counted != EXPECTED_HOLDS["registered_feature_counts"][source_id]:
            _fail(
                "registered_feature_count_mismatch",
                "Registered feature count does not match the frozen roster.",
                "$.features",
            )

    basic_owner_verified = sum(
        1
        for record in records
        if record.dataset_id == "DA-A1"
        and record.feature_name in UCI412_BASIC_FEATURES
        and record.acquisition.owner_verified_pre_angiography
    )
    covered = (
        f"{basic_owner_verified}/{len(UCI412_BASIC_FEATURES)}"
    )
    if covered != EXPECTED_HOLDS[
        "uci412_basic_clinical_owner_verified_pre_angiography"
    ]:
        _fail(
            "timing_promotion_without_owner_evidence",
            "UCI-412 basic-clinical owner-verified timing count must remain 0/16.",
            "$.features",
        )

    return tuple(records)


# --------------------------------------------------------------------------- #
# Public validation entry points                                              #
# --------------------------------------------------------------------------- #


def validate_crosswalk(document: Mapping[str, Any]) -> AcquisitionEvidenceCrosswalk:
    """Fail-closed validation of one crosswalk document.

    Returns an immutable read model on success. Raises
    :class:`CrosswalkValidationError` with a stable code on any violation. The
    function performs no I/O and mutates nothing.
    """
    root = _require_mapping(document, "$", code="expected_document")
    _require_exact_keys(root, REQUIRED_TOP_LEVEL_KEYS, "$")

    if root.get("schema_id") != CROSSWALK_SCHEMA_ID:
        _fail("schema_id_mismatch", "Unexpected schema id.", "$.schema_id")
    if root.get("schema_version") != CROSSWALK_SCHEMA_VERSION:
        _fail(
            "schema_version_mismatch",
            "Unsupported crosswalk schema version.",
            "$.schema_version",
        )
    if root.get("crosswalk_id") != CROSSWALK_ID:
        _fail("crosswalk_id_mismatch", "Unexpected crosswalk id.", "$.crosswalk_id")
    if root.get("artifact_kind") != CROSSWALK_ARTIFACT_KIND:
        _fail(
            "artifact_kind_mismatch",
            "Unexpected artifact kind.",
            "$.artifact_kind",
        )
    if root.get("status") != CROSSWALK_STATUS:
        _fail(
            "status_promotion",
            "Crosswalk status may not be promoted by this artifact.",
            "$.status",
        )
    statement = _require_str(root.get("status_statement"), "$.status_statement")
    if statement != STATUS_STATEMENT:
        _fail(
            "status_statement_mismatch",
            "Status statement must not be reworded or weakened.",
            "$.status_statement",
        )
    if root.get("prepared_on") != CROSSWALK_PREPARED_ON:
        _fail(
            "prepared_on_mismatch",
            "Unexpected preparation date.",
            "$.prepared_on",
        )
    if root.get("baseline_main_sha") != CROSSWALK_BASELINE_MAIN_SHA:
        _fail(
            "baseline_sha_mismatch",
            "Unexpected baseline main SHA.",
            "$.baseline_main_sha",
        )

    _validate_offline_clauses(root)
    _validate_no_result_contract(root)
    _validate_revision_history(root)
    holds = _validate_holds(root)

    for key, taxonomy in (
        ("evidence_class_taxonomy", EVIDENCE_CLASS_TAXONOMY),
        ("acquisition_channel_taxonomy", ACQUISITION_CHANNEL_TAXONOMY),
        ("channel_status_taxonomy", CHANNEL_STATUS_TAXONOMY),
        ("timing_status_taxonomy", TIMING_STATUS_TAXONOMY),
        ("disposition_taxonomy", DISPOSITION_TAXONOMY),
        ("permission_status_taxonomy", PERMISSION_STATUS_TAXONOMY),
    ):
        _validate_taxonomy(root, key, taxonomy, "$")

    evidence = _validate_evidence_register(root)
    sources = _validate_sources(root)
    permissions = _validate_permissions(root)
    restrictions = _validate_restrictions(root)
    panels = _validate_panel_bindings(root)
    routes = _validate_routes(root)
    blocked_items = _validate_blocked_items(root, routes)
    features = _validate_features(root, evidence, permissions)

    return AcquisitionEvidenceCrosswalk(
        schema_id=CROSSWALK_SCHEMA_ID,
        schema_version=CROSSWALK_SCHEMA_VERSION,
        crosswalk_id=CROSSWALK_ID,
        artifact_kind=CROSSWALK_ARTIFACT_KIND,
        status=CROSSWALK_STATUS,
        prepared_on=CROSSWALK_PREPARED_ON,
        baseline_main_sha=CROSSWALK_BASELINE_MAIN_SHA,
        document_digest_sha256=crosswalk_document_digest(root),
        holds=_freeze(holds),
        evidence=evidence,
        sources=sources,
        permissions=permissions,
        restrictions=restrictions,
        panels=panels,
        routes=routes,
        blocked_items=blocked_items,
        features=features,
    )


@lru_cache(maxsize=1)
def load_crosswalk() -> AcquisitionEvidenceCrosswalk:
    """Read, validate and cache the registered crosswalk document."""
    try:
        raw = CROSSWALK_PATH.read_text(encoding="utf-8")
    except OSError as exc:  # pragma: no cover - missing-file guard
        raise CrosswalkValidationError(
            "crosswalk_unreadable",
            "Registered crosswalk document could not be read.",
        ) from exc
    try:
        document = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise CrosswalkValidationError(
            "crosswalk_malformed",
            "Registered crosswalk document is not valid JSON.",
        ) from exc
    return validate_crosswalk(document)


# --------------------------------------------------------------------------- #
# Deterministic metadata query                                                #
# --------------------------------------------------------------------------- #


def _resolve_route_scope(
    route_id: str,
) -> tuple[str, str, RouteActivationRecord]:
    if route_id not in ROUTE_SPECS:
        raise CrosswalkQueryError(
            "unknown_route_id",
            "Query route id is not one of the five registered research routes.",
        )
    frozen = ROUTE_SPECS[route_id]
    crosswalk = load_crosswalk()
    return frozen["dataset_id"], frozen["panel_id"], crosswalk.route(route_id)


def query_feature_evidence(
    *,
    dataset_id: str | None = None,
    panel_id: str | None = None,
    route_id: str | None = None,
    feature_name: str | None = None,
    timing_status: str | None = None,
    channel_status: str | None = None,
) -> FeatureEvidenceQuery:
    """Deterministic, read-only metadata query over the valid attestation set.

    Filters are exact-match and fail closed: an unknown value, an unknown
    feature name, a feature name that is ambiguous across datasets, or a
    route/dataset/panel combination that does not exist raises
    :class:`CrosswalkQueryError` instead of returning a partial guess. An empty
    match set is a valid, explicit zero-result answer.
    """
    crosswalk = load_crosswalk()
    filters: dict[str, Any] = {}

    if route_id is not None:
        if not isinstance(route_id, str):
            raise CrosswalkQueryError("invalid_filter", "route_id must be a string.")
        route_dataset, route_panel, _ = _resolve_route_scope(route_id)
        if dataset_id is not None and dataset_id != route_dataset:
            raise CrosswalkQueryError(
                "conflicting_filters",
                "route_id and dataset_id describe different sources.",
            )
        if panel_id is not None and panel_id != route_panel:
            raise CrosswalkQueryError(
                "conflicting_filters",
                "route_id and panel_id describe different panels.",
            )
        dataset_id, panel_id = route_dataset, route_panel
        filters["route_id"] = route_id

    if dataset_id is not None:
        if not isinstance(dataset_id, str) or dataset_id not in {"DA-A1", "DA-A2"}:
            raise CrosswalkQueryError(
                "unknown_filter_value", "dataset_id is not a registered dataset."
            )
        filters["dataset_id"] = dataset_id

    if panel_id is not None:
        if not isinstance(panel_id, str) or panel_id not in PANELS_BY_ID:
            raise CrosswalkQueryError(
                "unknown_filter_value", "panel_id is not a registered panel."
            )
        if dataset_id is None:
            dataset_id = PANELS_BY_ID[panel_id].dataset_id
            filters["dataset_id"] = dataset_id
        elif PANELS_BY_ID[panel_id].dataset_id != dataset_id:
            raise CrosswalkQueryError(
                "conflicting_filters",
                "panel_id and dataset_id describe different sources.",
            )
        filters["panel_id"] = panel_id

    if timing_status is not None:
        if not isinstance(timing_status, str) or timing_status not in TIMING_STATUS_TAXONOMY:
            raise CrosswalkQueryError(
                "unknown_filter_value", "timing_status is not a registered status."
            )
        filters["timing_status"] = timing_status

    if channel_status is not None:
        if (
            not isinstance(channel_status, str)
            or channel_status not in CHANNEL_STATUS_TAXONOMY
        ):
            raise CrosswalkQueryError(
                "unknown_filter_value", "channel_status is not a registered status."
            )
        filters["channel_status"] = channel_status

    if feature_name is not None:
        if not isinstance(feature_name, str) or not feature_name:
            raise CrosswalkQueryError(
                "invalid_filter", "feature_name must be a non-empty string."
            )
        candidates = [
            record
            for record in crosswalk.features
            if record.feature_name == feature_name
        ]
        if not candidates:
            raise CrosswalkQueryError(
                "unknown_feature_name", "feature_name is not a registered feature."
            )
        if dataset_id is None and len({c.dataset_id for c in candidates}) > 1:
            raise CrosswalkQueryError(
                "ambiguous_feature_name",
                "feature_name exists in more than one dataset; add dataset_id, "
                "panel_id or route_id.",
            )
        filters["feature_name"] = feature_name

    selected: list[FeatureAcquisitionEvidence] = []
    for record in crosswalk.features:
        if dataset_id is not None and record.dataset_id != dataset_id:
            continue
        if panel_id is not None and panel_id not in record.panels:
            continue
        if feature_name is not None and record.feature_name != feature_name:
            continue
        if (
            timing_status is not None
            and record.acquisition.timing_status != timing_status
        ):
            continue
        if (
            channel_status is not None
            and record.acquisition.channel_status != channel_status
        ):
            continue
        selected.append(record)
    selected.sort(key=lambda record: record.feature_key)

    if route_id is not None:
        routes = (crosswalk.route(route_id),)
    elif dataset_id is not None:
        routes = tuple(
            record for record in crosswalk.routes if record.dataset_id == dataset_id
        )
    else:
        routes = crosswalk.routes

    return FeatureEvidenceQuery(
        filters=_freeze(filters),
        features=tuple(selected),
        routes=tuple(routes),
        crosswalk=crosswalk,
    )


def describe_crosswalk() -> dict[str, Any]:
    """Deterministic metadata summary (no feature values, no scoring)."""
    crosswalk = load_crosswalk()
    owner_verified = sum(
        1
        for record in crosswalk.features
        if record.acquisition.owner_verified_pre_angiography
    )
    return {
        "query_schema": QUERY_SCHEMA_ID,
        **crosswalk.identity(),
        "panel_count": len(crosswalk.panels),
        "panels": [panel.to_dict() for panel in crosswalk.panels],
        "route_count": len(crosswalk.routes),
        "routes": [route.to_dict() for route in crosswalk.routes],
        "blocked_item_count": len(crosswalk.blocked_items),
        "blocked_items": [item.to_dict() for item in crosswalk.blocked_items],
        "feature_count": len(crosswalk.features),
        "owner_verified_pre_angiography_feature_count": owner_verified,
        "timing_status_counts": _count_by(
            record.acquisition.timing_status for record in crosswalk.features
        ),
        "channel_status_counts": _count_by(
            record.acquisition.channel_status for record in crosswalk.features
        ),
        "permission_status_counts": _count_by(
            record.permission_status for record in crosswalk.features
        ),
        "holds": _thaw(crosswalk.holds),
        "result_state": RESULT_STATE,
        "cad_probability_computed": False,
        "read_only": True,
        "files_written": False,
    }


def _count_by(values: Iterable[str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for value in values:
        counts[value] = counts.get(value, 0) + 1
    return {key: counts[key] for key in sorted(counts)}


# --------------------------------------------------------------------------- #
# CLI                                                                         #
# --------------------------------------------------------------------------- #


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m research.intake.feature_acquisition_crosswalk",
        description=(
            "Offline, read-only RH-04 feature acquisition-evidence crosswalk. "
            "Prints metadata only; never computes a CAD probability."
        ),
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("validate", help="Validate the registered crosswalk.")
    subparsers.add_parser("describe", help="Print the deterministic summary.")
    query = subparsers.add_parser("query", help="Deterministic metadata query.")
    query.add_argument("--dataset-id", choices=["DA-A1", "DA-A2"])
    query.add_argument(
        "--panel-id",
        choices=sorted(PANELS_BY_ID),
    )
    query.add_argument("--route-id", choices=sorted(ROUTE_SPECS))
    query.add_argument("--feature-name")
    query.add_argument("--timing-status", choices=sorted(TIMING_STATUS_TAXONOMY))
    query.add_argument("--channel-status", choices=sorted(CHANNEL_STATUS_TAXONOMY))
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point. Returns a process exit code; writes no files."""
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "validate":
            crosswalk = load_crosswalk()
            print(
                canonical_json(
                    {
                        "validated": True,
                        **crosswalk.identity(),
                        "feature_count": len(crosswalk.features),
                        "route_count": len(crosswalk.routes),
                        "result_state": RESULT_STATE,
                    }
                )
            )
            return 0
        if args.command == "describe":
            print(json.dumps(describe_crosswalk(), indent=2, sort_keys=True))
            return 0
        result = query_feature_evidence(
            dataset_id=args.dataset_id,
            panel_id=args.panel_id,
            route_id=args.route_id,
            feature_name=args.feature_name,
            timing_status=args.timing_status,
            channel_status=args.channel_status,
        )
        print(json.dumps(result.to_dict(), indent=2, sort_keys=True))
        return 0
    except CrosswalkError as exc:
        print(canonical_json({"validated": False, "code": exc.code}), file=sys.stderr)
        return 2


__all__ = [
    "ACQUISITION_CHANNEL_TAXONOMY",
    "AcquisitionEvidence",
    "AcquisitionEvidenceCrosswalk",
    "BLOCKED_ITEMS",
    "BlockedItemRecord",
    "CHANNEL_STATUS_TAXONOMY",
    "CROSSWALK_ID",
    "CROSSWALK_PATH",
    "CROSSWALK_SCHEMA_ID",
    "CROSSWALK_SCHEMA_VERSION",
    "CROSSWALK_STATUS",
    "CrosswalkError",
    "CrosswalkQueryError",
    "CrosswalkValidationError",
    "DISPOSITION_TAXONOMY",
    "EVIDENCE_CLASS_TAXONOMY",
    "EVIDENCE_REGISTER",
    "EXPECTED_HOLDS",
    "EvidenceRecord",
    "FORBIDDEN_OPERATIONS_ALWAYS",
    "FeatureAcquisitionEvidence",
    "FeatureEvidenceQuery",
    "KNOWN_OPERATIONS",
    "OWNER_TIMING_EVIDENCE_CLASSES",
    "PANELS_BY_ID",
    "PANEL_SPECS",
    "PERMISSIONS",
    "PROHIBITED_FEATURE_NAMES",
    "PermissionRecord",
    "RESULT_STATE",
    "RESTRICTIONS",
    "ROUTE_ACTIVATION_STATES",
    "ROUTE_SPECS",
    "RegisteredSourceClaim",
    "RestrictionRecord",
    "RouteActivationRecord",
    "SOURCES",
    "TIMING_STATUS_TAXONOMY",
    "canonical_json",
    "crosswalk_document_digest",
    "describe_crosswalk",
    "load_crosswalk",
    "main",
    "query_feature_evidence",
    "validate_crosswalk",
]


if __name__ == "__main__":  # pragma: no cover - exercised via ``python -m``
    raise SystemExit(main())
