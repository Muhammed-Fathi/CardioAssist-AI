"""AI-8R evidence-only readiness: never an authorization or execution route."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from research.uci412.config import DEFAULT_CONFIG, REPOSITORY_ROOT
from research.uci412.errors import Uci412Error
from research.uci412.feature_schema import (
    DICTIONARY_SCHEMA_VERSION, PRIMARY_PANEL_COLUMNS, PRIMARY_PANEL_ID,
    PRIMARY_PANEL_VERSION, load_feature_dictionary,
)
from research.uci412.safety import run_preflight

REGISTER = Path(__file__).parent / 'schemas' / 'ai8r_eligibility.v1.json'
# A JSON-only edit cannot promote a field to VERIFIED (or relabel its timing).
# A future scientific adjudication requires a reviewed code AND evidence change;
# even that would not authorize fitting or replace the signed local preflight.
REVIEWED_ELIGIBILITY = (
    'CONDITIONALLY_SUPPORTED', 'CONDITIONALLY_SUPPORTED', 'CONDITIONALLY_SUPPORTED',
    'CONDITIONALLY_SUPPORTED', 'CONDITIONALLY_SUPPORTED', 'CONDITIONALLY_SUPPORTED',
    'CONDITIONALLY_SUPPORTED', 'CONDITIONALLY_SUPPORTED', 'CONDITIONALLY_SUPPORTED',
    'UNRESOLVED', 'UNRESOLVED', 'UNRESOLVED', 'UNRESOLVED', 'UNRESOLVED',
    'UNRESOLVED', 'CONDITIONALLY_SUPPORTED',
)
REVIEWED_TIMING = 'UNVERIFIED'


def load_eligibility(path: Path = REGISTER) -> dict[str, Any]:
    """Validate evidence shape and binding; never interpret it as permission."""
    def unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('Duplicate eligibility key')
            result[key] = value
        return result

    data = json.loads(path.read_text(encoding='utf-8'), object_pairs_hook=unique)
    if not isinstance(data, dict) or set(data) != {
        'schema_id', 'schema_version', 'status', 'source_id', 'panel_id',
        'panel_version', 'dictionary_version', 'retrieved_utc_date', 'fields'
    } or any(data.get(k) != v for k, v in {
        'schema_id': 'uci412_ai8r_eligibility_register', 'schema_version': '1.0.0',
        'status': 'EVIDENCE_ONLY_NOT_AUTHORIZATION', 'source_id': 'UCI-412',
        'panel_id': PRIMARY_PANEL_ID, 'panel_version': PRIMARY_PANEL_VERSION,
        'dictionary_version': DICTIONARY_SCHEMA_VERSION,
    }.items()):
        raise ValueError('Eligibility register identity/version mismatch')
    fields = data['fields']
    if not isinstance(fields, list) or len(fields) != len(PRIMARY_PANEL_COLUMNS):
        raise ValueError('Eligibility register field count mismatch')
    dictionary = load_feature_dictionary()
    # The dictionary is separately validated against the source-specific allowlist.
    numeric_binary = frozenset({
        'DM', 'HTN', 'Current Smoker', 'EX-Smoker', 'FH', 'Typical Chest Pain'
    })
    for name, reviewed_status, field in zip(
        PRIMARY_PANEL_COLUMNS, REVIEWED_ELIGIBILITY, fields, strict=True
    ):
        if not isinstance(field, dict) or set(field) != {
            'name', 'source_position', 'definition', 'registered_encoding', 'unit',
            'collection_method', 'pre_angiography', 'proposed_workflow',
            'leakage_or_timing_risk', 'evidence', 'evidence_quality', 'unresolved',
            'eligibility'
        } or field['name'] != name or field['source_position'] != dictionary.features[name].position:
            raise ValueError('Eligibility register feature contract mismatch')
        spec = dictionary.features[name]
        encoding = (
            'numeric 0/1; direction provisional (0=absent, 1=present)'
            if name in numeric_binary else
            'numeric continuous' if spec.role == 'numeric' else
            'text: ' + ', '.join(spec.vocabulary)
        )
        if (field['unit'] != spec.unit or field['registered_encoding'] != encoding
                or field['eligibility'] != reviewed_status
                or field['pre_angiography'] != REVIEWED_TIMING):
            raise ValueError('Eligibility register contract/timing/status mismatch')
        if any(not isinstance(field[k], str) or not field[k].strip() for k in (
            'definition', 'registered_encoding', 'collection_method', 'pre_angiography',
            'proposed_workflow', 'leakage_or_timing_risk', 'evidence_quality', 'unresolved'
        )) or not isinstance(field['evidence'], list) or not field['evidence'] or any(
            not isinstance(e, str) or not e for e in field['evidence']
        ):
            raise ValueError('Eligibility register field evidence malformed')
    return data


def assess_readiness(*, repo_root: Path = REPOSITORY_ROOT, register: Path = REGISTER) -> dict[str, Any]:
    """No patient row reads; local gates delegated exclusively to the existing preflight.

    JSON-only promotion to VERIFIED is rejected. Even after future reviewed
    source evidence changes the code binding, signed local authorization,
    protected provenance, paths and protocol must still be checked separately.
    """
    data = load_eligibility(register)
    blockers = [f['name'] for f in data['fields'] if f['eligibility'] != 'VERIFIED']
    result: dict[str, Any] = {
        'status': 'SCIENTIFIC_HOLD' if blockers else 'LOCAL_GATE_PENDING',
        'source_identity': 'UCI-412/DA-A1; bytes checked only by protected local preflight',
        'feature_contract': 'uci412_basic_clinical_v1/1.1.0; 16 ordered fields',
        'unverified_fields': blockers,
        'scientific_evidence_review': 'NOT_INDEPENDENT_AUTHORIZATION',
        'local_gate': 'NOT_EVALUATED',
        'authorization_granted_by_readiness': False,
        'execution_permitted_by_readiness': False,
        'source_rows_parsed': False,
        'model_fitting_started': False,
    }
    try:
        run_preflight(repo_root=repo_root, config=DEFAULT_CONFIG)
    except Uci412Error as exc:
        # No exception details: protect paths, keys and local manifest contents.
        result['local_gate'] = 'REJECTED_' + type(exc).__name__
    except Exception:  # noqa: BLE001 - no local error contents leave this boundary
        result['local_gate'] = 'REJECTED_UNEXPECTED_LOCAL_ERROR'
    else:
        result['local_gate'] = 'EXISTING_PREFLIGHT_PASS_NOT_EXECUTION_PERMISSION'
    return result
