"""Residual P0-01 regressions: strict lease expiry/ownership/fence before EVERY
state-mutating action.

Reviewer residual review #7235517859 independently executed the real
``_assert_lease`` with an expired lease and observed ``Expired lease accepted:
True``. These deterministic regressions lock the corrected behaviour:

* expiry is strict (``lease_expires_at > now``); equality is already expired;
* an expired owner without a takeover cannot mutate state or release the lease;
* a stale failure after a takeover is a no-op (never discards the new owner's
  staging, never marks the document failed, never reclaims quota);
* staging publication and finalization are fenced — a stale attempt cannot
  publish a staging key or promote a blob it no longer owns;
* quota is reclaimed only AFTER the staging blob is actually removed;
* the orphan sweep checks ownership and unlinks in one transaction (no
  check/unlink race) and never charges an in-flight, not-yet-published blob.
"""

from __future__ import annotations

import hashlib
import os
import time
import uuid
from pathlib import Path

import pytest
from sqlalchemy import select

from backend.app.term1.models import PatientProfile
from backend.app.term1.tx import read_transaction, write_transaction
from backend.app.term1_c2_documents import constants as C
from backend.app.term1_c2_documents.admission import StructureInfo
from backend.app.term1_c2_documents.models import DocumentInflightOperation, MedicalDocument
from backend.app.term1_c2_documents.service import Actor
from backend.app.term1_c2_documents.storage import make_storage_key

FIXTURES = Path(__file__).resolve().parents[3] / "backend" / "app" / "term1_c2_documents" / "fixtures"


def _data():
    return (FIXTURES / "resting_text.pdf").read_bytes()


@pytest.fixture
def actor_patient(client, patient, c2_app):
    with read_transaction(c2_app.state.database) as session:
        user_id = session.execute(
            select(PatientProfile.user_id).where(
                PatientProfile.patient_id == patient["patient_id"])
        ).scalar_one()
    return Actor(user_id=user_id, role="patient", patient_id=patient["patient_id"])


def _upload(service, actor, key):
    return service.upload(
        actor=actor, data=_data(), declared_template_id=C.TEMPLATE_RESTING,
        declared_document_kind=C.DOC_KIND_RESTING, original_filename="resting_text.pdf",
        idempotency_key=key,
    )


def _reservation(service, doc_store, actor, *, stage=True):
    """A PENDING_SCAN reservation with a live lease and (optionally) a staged blob."""
    data = _data()
    sha = hashlib.sha256(data).hexdigest()
    document_id = str(uuid.uuid4())
    storage_key = make_storage_key(actor.patient_id, document_id)
    staging_key = doc_store.stage(data, storage_key) if stage else None
    public_fields = {"content_sha256": sha, "document_kind": C.DOC_KIND_RESTING,
                     "fixture_template_id": C.TEMPLATE_RESTING,
                     "declared_media_type": C.MEDIA_PDF, "byte_size": len(data)}
    identity = service._identity(actor=actor, operation=C.OP_DOC1_UPLOAD, target_ref="none",
                                 raw_key=f"res-{document_id}", public_fields=public_fields)
    key = identity.replay_key
    now = service.clock.now_iso()
    owner = str(uuid.uuid4())
    with write_transaction(service.database) as session:
        session.add(MedicalDocument(
            document_id=document_id, patient_id=actor.patient_id,
            uploaded_by_user_id=actor.user_id, document_kind=C.DOC_KIND_RESTING,
            fixture_template_id=C.TEMPLATE_RESTING, fixture_file_sha256=sha,
            original_filename_sanitized="resting_text.pdf", declared_media_type=C.MEDIA_PDF,
            byte_size=len(data), page_count=0, content_sha256=None,
            storage_key=storage_key, upload_status=C.UPLOAD_PENDING_SCAN,
            created_at=now, staging_key=staging_key,
        ))
        session.flush()
        session.add(DocumentInflightOperation(
            inflight_id=str(uuid.uuid4()), replay_scope=key.replay_scope,
            key_hash=key.key_hash, actor_binding=key.actor_binding, operation=key.operation,
            target_ref=key.target_ref, request_fingerprint=identity.request_fingerprint,
            actor_user_id=actor.user_id, patient_id=actor.patient_id, document_id=document_id,
            state=C.INFLIGHT_STATE_IN_FLIGHT, fence_token=1, lease_owner=owner,
            lease_expires_at=service.clock.plus(C.INFLIGHT_LEASE_SECONDS),
            attempt_count=1, failure_code=None, created_at=now, updated_at=now,
        ))
    return document_id, storage_key, staging_key, owner


def _inflight(service, document_id):
    with read_transaction(service.database) as session:
        return session.execute(
            select(DocumentInflightOperation).where(
                DocumentInflightOperation.document_id == document_id)
        ).scalar_one()


def _takeover(service, document_id):
    """Simulate another attempt fencing out the current owner (expired lease)."""
    with write_transaction(service.database) as session:
        inflight = session.execute(
            select(DocumentInflightOperation).where(
                DocumentInflightOperation.document_id == document_id)
        ).scalar_one()
        inflight.fence_token += 1
        inflight.lease_owner = str(uuid.uuid4())
        inflight.lease_expires_at = service.clock.plus(C.INFLIGHT_LEASE_SECONDS)
        inflight.state = C.INFLIGHT_STATE_IN_FLIGHT
        inflight.updated_at = service.clock.now_iso()
        return inflight.lease_owner, inflight.fence_token


# --- strict expiry ----------------------------------------------------------
def test_lease_expiry_equality_is_expired(document_service, doc_store, actor_patient, clock):
    document_id, _, _, owner = _reservation(document_service, doc_store, actor_patient)
    inflight = _inflight(document_service, document_id)
    # Advance the clock so now == lease_expires_at exactly.
    expiry = inflight.lease_expires_at
    from backend.app.term1.timeutil import from_iso
    delta = (from_iso(expiry) - clock()).total_seconds()
    clock.advance(seconds=delta)
    with write_transaction(document_service.database) as session:
        row = session.get(DocumentInflightOperation, inflight.inflight_id)
        assert document_service.clock.now_iso() == expiry  # now equals expiry
        assert document_service._lease_held(row, owner, 1) is False
        with pytest.raises(Exception) as exc:
            document_service._assert_lease(session, inflight.inflight_id, owner, 1)
        assert getattr(exc.value, "code", None) == "concurrency_conflict"


def test_expired_owner_without_takeover_cannot_mutate(document_service, doc_store, actor_patient, clock):
    document_id, storage_key, staging_key, owner = _reservation(document_service, doc_store, actor_patient)
    inflight = _inflight(document_service, document_id)
    clock.advance(seconds=C.INFLIGHT_LEASE_SECONDS + 1)  # expired, NO takeover
    # The expired owner cannot release the lease...
    with write_transaction(document_service.database) as session:
        released = document_service._release_lease_failed(
            session, inflight.inflight_id, owner, 1, "internal_error")
        assert released is False
        row = session.get(DocumentInflightOperation, inflight.inflight_id)
        assert row.state == C.INFLIGHT_STATE_IN_FLIGHT  # unchanged
        assert row.lease_owner == owner and row.fence_token == 1
    # ...and _fail_upload is a complete no-op: staging intact, document untouched.
    document_service._fail_upload(document_id, inflight.inflight_id, owner, 1, staging_key, "internal_error")
    with read_transaction(document_service.database) as session:
        row = session.get(MedicalDocument, document_id)
        assert row.upload_status == C.UPLOAD_PENDING_SCAN
        assert row.staging_key == staging_key and row.reclaim_at is None
    assert doc_store.exists(staging_key)


def test_stale_failure_after_takeover_is_noop(document_service, doc_store, actor_patient, clock):
    document_id, storage_key, staging_key, old_owner = _reservation(document_service, doc_store, actor_patient)
    inflight = _inflight(document_service, document_id)
    clock.advance(seconds=C.INFLIGHT_LEASE_SECONDS + 1)
    new_owner, new_fence = _takeover(document_service, document_id)
    assert new_fence == 2 and new_owner != old_owner
    # The stale (old owner/fence) failure must touch nothing the new owner holds.
    document_service._fail_upload(document_id, inflight.inflight_id, old_owner, 1, staging_key, "internal_error")
    with read_transaction(document_service.database) as session:
        row = session.get(MedicalDocument, document_id)
        assert row.upload_status == C.UPLOAD_PENDING_SCAN
        assert row.staging_key == staging_key and row.reclaim_at is None
        lease = session.get(DocumentInflightOperation, inflight.inflight_id)
        assert lease.lease_owner == new_owner and lease.fence_token == new_fence
        assert lease.state == C.INFLIGHT_STATE_IN_FLIGHT
    assert doc_store.exists(staging_key)  # new owner's staging preserved


# --- staging / finalization races -------------------------------------------
def test_staging_publication_race_fences_stale_attempt(document_service, doc_store, actor_patient, clock, monkeypatch):
    """A takeover between stage() and staging-key publication fences the attempt."""
    real_stage = doc_store.stage
    seen = {}

    def stage_then_takeover(data, storage_key):
        staging_key = real_stage(data, storage_key)
        # Another attempt takes over the lease right after we stage but BEFORE we
        # publish the staging identity.
        clock.advance(seconds=C.INFLIGHT_LEASE_SECONDS + 1)
        with read_transaction(document_service.database) as session:
            row = session.execute(select(MedicalDocument).where(
                MedicalDocument.storage_key == storage_key)).scalar_one()
            seen["document_id"] = row.document_id
        _takeover(document_service, seen["document_id"])
        return staging_key

    monkeypatch.setattr(doc_store, "stage", stage_then_takeover)
    with pytest.raises(Exception) as exc:
        _upload(document_service, actor_patient, f"race-{uuid.uuid4()}")
    assert getattr(exc.value, "code", None) == "concurrency_conflict"
    document_id = seen["document_id"]
    with read_transaction(document_service.database) as session:
        row = session.get(MedicalDocument, document_id)
        # The stale attempt never published its staging key.
        assert row.staging_key is None
        assert row.upload_status == C.UPLOAD_PENDING_SCAN
        lease = session.execute(select(DocumentInflightOperation).where(
            DocumentInflightOperation.document_id == document_id)).scalar_one()
        assert lease.fence_token == 2  # new owner intact
    # The stale attempt's unpublished staging blob was discarded.
    assert list(doc_store.iter_files()) == []


def test_finalization_race_fences_stale_attempt(document_service, doc_store, actor_patient, clock, monkeypatch):
    """A takeover during validation fences the attempt before promotion."""
    seen = {}

    def validate_then_takeover(**kwargs):
        with read_transaction(document_service.database) as session:
            row = session.execute(select(MedicalDocument).where(
                MedicalDocument.staging_key == kwargs["storage_key"])).scalar_one()
            seen["document_id"] = row.document_id
            seen["staging_key"] = row.staging_key
        clock.advance(seconds=C.INFLIGHT_LEASE_SECONDS + 1)
        _takeover(document_service, seen["document_id"])
        return StructureInfo(page_count=1, pixel_width=None, pixel_height=None)

    monkeypatch.setattr(document_service.worker, "validate", validate_then_takeover)
    with pytest.raises(Exception) as exc:
        _upload(document_service, actor_patient, f"fin-{uuid.uuid4()}")
    assert getattr(exc.value, "code", None) == "concurrency_conflict"
    document_id = seen["document_id"]
    with read_transaction(document_service.database) as session:
        row = session.get(MedicalDocument, document_id)
        # The stale attempt did NOT promote to STORED.
        assert row.upload_status == C.UPLOAD_PENDING_SCAN
        assert row.content_sha256 is None and row.validated_at is None
        lease = session.execute(select(DocumentInflightOperation).where(
            DocumentInflightOperation.document_id == document_id)).scalar_one()
        assert lease.fence_token == 2
    assert not doc_store.exists(row.storage_key)  # no final blob promoted


# --- quota reclamation ordering ---------------------------------------------
def test_fail_upload_reclaims_only_after_cleanup(document_service, doc_store, actor_patient, monkeypatch):
    document_id, storage_key, staging_key, owner = _reservation(document_service, doc_store, actor_patient)
    inflight = _inflight(document_service, document_id)

    # If cleanup fails, accounting must NOT happen (transaction rolls back).
    def boom(key):
        raise RuntimeError("cleanup failed")

    monkeypatch.setattr(doc_store, "discard_staging", boom)
    with pytest.raises(RuntimeError):
        document_service._fail_upload(document_id, inflight.inflight_id, owner, 1, staging_key, "internal_error")
    with read_transaction(document_service.database) as session:
        row = session.get(MedicalDocument, document_id)
        assert row.upload_status == C.UPLOAD_PENDING_SCAN  # not failed
        assert row.reclaim_at is None and row.staging_key == staging_key
        lease = session.get(DocumentInflightOperation, inflight.inflight_id)
        assert lease.state == C.INFLIGHT_STATE_IN_FLIGHT  # rolled back
    assert doc_store.exists(staging_key)

    # Successful cleanup: blob removed FIRST, then reclaim_at + FAILED.
    monkeypatch.undo()
    document_service._fail_upload(document_id, inflight.inflight_id, owner, 1, staging_key, "internal_error")
    with read_transaction(document_service.database) as session:
        row = session.get(MedicalDocument, document_id)
        assert row.upload_status == C.UPLOAD_FAILED
        assert row.staging_key is None and row.reclaim_at is not None
        lease = session.get(DocumentInflightOperation, inflight.inflight_id)
        assert lease.state == C.INFLIGHT_STATE_FAILED
    assert not doc_store.exists(staging_key)


# --- orphan sweep: no check/unlink race -------------------------------------
def test_sweep_protects_live_and_reclaims_only_abandoned_old(document_service, doc_store, actor_patient):
    # A live reservation's CURRENT staging blob is protected.
    live_id, live_key, live_staging, _ = _reservation(document_service, doc_store, actor_patient)
    # An abandoned EXTRA staging blob (not the current staging_key), aged past grace.
    extra_staging = doc_store.stage(_data(), live_key)
    extra_path = doc_store.root / extra_staging
    old = time.time() - (C.PENDING_SCAN_RECOVERY_AGE_SECONDS + 30)
    os.utime(extra_path, (old, old))
    # A fresh abandoned extra staging blob (within grace) is kept.
    fresh_staging = doc_store.stage(_data(), live_key)

    removed = document_service.sweep_orphans()
    assert removed == 1  # only the aged abandoned extra blob
    assert doc_store.exists(live_staging)        # current reservation staging protected
    assert not doc_store.exists(extra_staging)   # aged abandoned reclaimed
    assert doc_store.exists(fresh_staging)       # in-flight grace respected
    with read_transaction(document_service.database) as session:
        row = session.get(MedicalDocument, live_id)
        assert row.upload_status == C.UPLOAD_PENDING_SCAN
        assert row.staging_key == live_staging


def test_sweep_protects_stored_final_blob(document_service, doc_store, actor_patient):
    data = _data()
    sha = hashlib.sha256(data).hexdigest()
    document_id = str(uuid.uuid4())
    storage_key = make_storage_key(actor_patient.patient_id, document_id)
    doc_store.promote(doc_store.stage(data, storage_key), storage_key)
    now = document_service.clock.now_iso()
    with write_transaction(document_service.database) as session:
        session.add(MedicalDocument(
            document_id=document_id, patient_id=actor_patient.patient_id,
            uploaded_by_user_id=actor_patient.user_id, document_kind=C.DOC_KIND_RESTING,
            fixture_template_id=C.TEMPLATE_RESTING, fixture_file_sha256=sha,
            original_filename_sanitized="resting_text.pdf", declared_media_type=C.MEDIA_PDF,
            byte_size=len(data), page_count=1, content_sha256=sha, storage_key=storage_key,
            upload_status=C.UPLOAD_STORED, created_at=now, validated_at=now,
        ))
    assert document_service.sweep_orphans() == 0
    assert doc_store.exists(storage_key)
