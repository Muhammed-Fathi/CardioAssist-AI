"""Synthetic metadata-only AI-8R regression; no protected source or manifest access."""
import copy
import json

import pytest

from research.uci412 import readiness
from research.uci412.errors import AuthorizationError, ProvenanceError, StorageProtectionError
from research.uci412.feature_schema import PRIMARY_PANEL_COLUMNS


def test_register_and_scientific_hold(monkeypatch):
    fields = readiness.load_eligibility()['fields']
    assert tuple(f['name'] for f in fields) == PRIMARY_PANEL_COLUMNS
    assert all(f['pre_angiography'] == 'UNVERIFIED' for f in fields)
    monkeypatch.setattr(readiness, 'run_preflight', lambda **kw: (_ for _ in ()).throw(AuthorizationError('private secret')))
    result = readiness.assess_readiness()
    assert result['status'] == 'SCIENTIFIC_HOLD'
    assert result['local_gate'] == 'REJECTED_AuthorizationError'
    assert 'secret' not in str(result)
    assert not result['authorization_granted_by_readiness']
    assert not result['execution_permitted_by_readiness']
    assert not result['source_rows_parsed'] and not result['model_fitting_started']


@pytest.mark.parametrize('mutate', [
    lambda d: d.update(source_id='UCI-411'),
    lambda d: d.update(panel_version='0.0.0'),
    lambda d: d['fields'].reverse(),
    lambda d: d['fields'][0].update(unit='furlongs'),
    lambda d: d['fields'][0].update(registered_encoding='text: 0, 1'),
    lambda d: d['fields'][0].update(eligibility='VERIFIED'),
    lambda d: d['fields'][0].update(eligibility='AUTHORIZED'),
    lambda d: d['fields'][0].update(evidence=[]),
    lambda d: d['fields'][0].update(source_position=99),
    lambda d: d.update(fields=[]),
])
def test_malformed_register_fails_before_local_gate(tmp_path, monkeypatch, mutate):
    data = copy.deepcopy(readiness.load_eligibility())
    mutate(data)
    path = tmp_path / 'register.json'
    path.write_text(json.dumps(data), encoding='utf-8')
    monkeypatch.setattr(readiness, 'run_preflight', lambda **kw: pytest.fail('local gate reached'))
    with pytest.raises(ValueError):
        readiness.assess_readiness(register=path)


def test_duplicate_keys_rejected(tmp_path):
    path = tmp_path / 'register.json'
    path.write_text('{"source_id":"UCI-412","source_id":"UCI-411"}', encoding='utf-8')
    with pytest.raises(ValueError, match='Duplicate'):
        readiness.load_eligibility(path)


@pytest.mark.parametrize('failure', [ProvenanceError, StorageProtectionError, AuthorizationError])
def test_no_local_failure_can_activate(tmp_path, monkeypatch, failure):
    data = readiness.load_eligibility()
    for field in data['fields']:
        field['eligibility'] = 'VERIFIED'  # synthetic future evidence state, not an approval
        field['pre_angiography'] = 'DOCUMENTED_PRE_ANGIOGRAPHY'
    path = tmp_path / 'register.json'
    path.write_text(json.dumps(data), encoding='utf-8')
    monkeypatch.setattr(readiness, 'run_preflight', lambda **kw: (_ for _ in ()).throw(failure('sensitive path')))
    result = readiness.assess_readiness(register=path)
    assert result['status'] == 'LOCAL_GATE_PENDING'
    assert result['local_gate'] == 'REJECTED_' + failure.__name__
    assert result['execution_permitted_by_readiness'] is False
    assert 'sensitive' not in str(result)


def test_even_successful_existing_gate_is_not_execution_permission(tmp_path, monkeypatch):
    data = readiness.load_eligibility()
    for field in data['fields']:
        field['eligibility'] = 'VERIFIED'
        field['pre_angiography'] = 'DOCUMENTED_PRE_ANGIOGRAPHY'
    path = tmp_path / 'register.json'
    path.write_text(json.dumps(data), encoding='utf-8')
    monkeypatch.setattr(readiness, 'run_preflight', lambda **kw: object())
    result = readiness.assess_readiness(register=path)
    assert result['local_gate'] == 'EXISTING_PREFLIGHT_PASS_NOT_EXECUTION_PERMISSION'
    assert result['authorization_granted_by_readiness'] is False
    assert result['execution_permitted_by_readiness'] is False
