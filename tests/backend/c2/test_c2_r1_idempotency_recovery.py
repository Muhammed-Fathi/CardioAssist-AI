"""T2-R1 regressions: durable idempotency, in-flight ownership/lease/fence and
crash recovery that preserves the original replay identity, event and audit.

These exercise the corrections required by reviewer REQUEST CHANGES #7233518509:
simultaneous same-key requests never create two documents; DOC5 authorizes and
resolves replay BEFORE dispatch; recovery is ownership-based (expired lease),
re-checks consent, and publishes atomically with the ORIGINAL remember()/event.
"""

from __future__ import annotations

import threading
import uuid
from pathlib import Path

import pytest
from sqlalchemy import func, select

from backend.app.term1.models import ConsentRecord, DurableIdempotency, PatientProfile
from backend.app.term1.tx import read_transaction, write_transaction
from backend.app.term1_c2_documents import constants as C
from backend.app.term1_c2_documents.models import (
    DocumentInflightOperation,
    ExtractionEvent,
    MedicalDocument,
)
from backend.app.term1_c2_documents.service import Actor
from backend.app.term1_c2_documents.storage import make_storage_key
from backend.app.term1_c2_documents.worker_client import WorkerUnavailableError


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


def test_simultaneous_same_key_creates_exactly_one_document(document_service, actor_patient):
    key = f"same-{uuid.uuid4()}"
    barrier = threading.Barrier(2)
    outcomes = []

    def attempt():
        barrier.wait(timeout=10)
        try:
            outcomes.append(("ok", _upload(document_service, actor_patient, key)))
        except Exception as error:  # noqa: BLE001
            outcomes.append(("err", getattr(error, "code", type(error).__name__)))

    threads = [threading.Thread(target=attempt) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)

    with read_transaction(document_service.database) as session:
        count = session.execute(select(func.count(MedicalDocument.document_id))).scalar_one()
    assert count == 1  # never two documents under one key
    ok = [body for tag, body in outcomes if tag == "ok"]
    assert len({b["document_id"] for b in ok}) <= 1
    # The loser is either a replay of the same document or a live-lease conflict.
    for tag, body in outcomes:
        if tag == "err":
            assert body in ("concurrency_conflict", "idempotency_key_conflict")


def test_lost_response_replay_returns_remembered_body(document_service, actor_patient):
    key = f"lost-{uuid.uuid4()}"
    first = _upload(document_service, actor_patient, key)
    with read_transaction(document_service.database) as session:
        events_before = session.execute(select(func.count(ExtractionEvent.event_id))).scalar_one()
    # The original response was "lost"; the retry replays the durable record.
    replay = _upload(document_service, actor_patient, key)
    assert replay["document_id"] == first["document_id"]
    assert replay.get("idempotent_replay") is True
    with read_transaction(document_service.database) as session:
        events_after = session.execute(select(func.count(ExtractionEvent.event_id))).scalar_one()
        docs = session.execute(select(func.count(MedicalDocument.document_id))).scalar_one()
    assert events_after == events_before  # no duplicate UPLOADED event
    assert docs == 1


def test_doc5_revoked_consent_refused_before_worker_dispatch(document_service, actor_patient):
    doc = _upload(document_service, actor_patient, f"up-{uuid.uuid4()}")
    # Revoke consent BEFORE extraction.
    with write_transaction(document_service.database) as session:
        consent = session.execute(
            select(ConsentRecord).where(ConsentRecord.patient_id == actor_patient.patient_id)
        ).scalar_one()
        consent.revoked_at = document_service.clock.now_iso()

    called = {"extract": False}
    original = document_service.worker.extract

    def spy(**kwargs):
        called["extract"] = True
        return original(**kwargs)

    document_service.worker.extract = spy
    with pytest.raises(Exception) as exc:
        document_service.extract(actor=actor_patient, document_id=doc["document_id"],
                                 idempotency_key=f"ex-{uuid.uuid4()}")
    assert getattr(exc.value, "code", None) == "consent_required"
    assert called["extract"] is False  # worker NEVER dispatched without authorization


def test_doc5_replay_with_worker_unavailable_does_not_dispatch(document_service, actor_patient):
    doc = _upload(document_service, actor_patient, f"up-{uuid.uuid4()}")
    key = f"ex-{uuid.uuid4()}"
    first = document_service.extract(actor=actor_patient, document_id=doc["document_id"],
                                     idempotency_key=key)

    def unavailable(**kwargs):
        raise WorkerUnavailableError("down")

    document_service.worker.extract = unavailable
    # Same key: the remembered result is returned without touching the worker.
    replay = document_service.extract(actor=actor_patient, document_id=doc["document_id"],
                                      idempotency_key=key)
    assert replay["extraction_id"] == first["extraction_id"]
    assert replay.get("idempotent_replay") is True


def _crashed_reservation(service, doc_store, actor, *, promote_final):
    """Build the post-crash state: PENDING_SCAN + expired lease + staged blob.

    ``promote_final=True`` simulates a crash AFTER the atomic rename but BEFORE
    the DB commit (final blob present, staging gone, row still PENDING_SCAN).
    """
    import hashlib
    data = _data()
    sha = hashlib.sha256(data).hexdigest()
    document_id = str(uuid.uuid4())
    storage_key = make_storage_key(actor.patient_id, document_id)
    staging_key = doc_store.stage(data, storage_key)
    if promote_final:
        doc_store.promote(staging_key, storage_key)
    public_fields = {"content_sha256": sha, "document_kind": C.DOC_KIND_RESTING,
                     "fixture_template_id": C.TEMPLATE_RESTING,
                     "declared_media_type": C.MEDIA_PDF, "byte_size": len(data)}
    identity = service._identity(actor=actor, operation=C.OP_DOC1_UPLOAD, target_ref="none",
                                 raw_key=f"crash-{document_id}", public_fields=public_fields)
    key = identity.replay_key
    now = service.clock.now_iso()
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
            state=C.INFLIGHT_STATE_IN_FLIGHT, fence_token=1, lease_owner=str(uuid.uuid4()),
            lease_expires_at=service.clock.plus(C.INFLIGHT_LEASE_SECONDS),
            attempt_count=1, failure_code=None, created_at=now, updated_at=now,
        ))
    return document_id, storage_key, identity


def test_failed_recovery_after_rename_keeps_quota_until_verified_sweep(
    document_service, doc_store, actor_patient, clock, monkeypatch
):
    """A failed recovery cleans final + orphan stages before releasing quota."""
    document_id, storage_key, _identity = _crashed_reservation(
        document_service, doc_store, actor_patient, promote_final=True
    )
    extra_stage = doc_store.stage(_data(), storage_key)
    clock.advance(seconds=C.INFLIGHT_LEASE_SECONDS + 30)
    monkeypatch.setattr(document_service, "_validate_recovery_candidate", lambda _candidate: None)
    monkeypatch.setattr(doc_store, "discard_staging", lambda _key: False)

    assert document_service.recover_pending(startup=False) == 1
    with read_transaction(document_service.database) as session:
        row = session.get(MedicalDocument, document_id)
        assert row.upload_status == C.UPLOAD_FAILED
        assert row.reclaim_at is None
        assert document_service._quota_usage(session, actor_patient.patient_id) == (
            1, len(_data())
        )
    assert doc_store.exists(storage_key) and doc_store.exists(extra_stage)

    monkeypatch.undo()
    document_service.sweep_orphans()
    with read_transaction(document_service.database) as session:
        row = session.get(MedicalDocument, document_id)
        assert row.reclaim_at is not None and row.staging_key is None
        assert document_service._quota_usage(session, actor_patient.patient_id) == (0, 0)
    assert not doc_store.exists(storage_key) and not doc_store.exists(extra_stage)


@pytest.mark.parametrize("promote_final", [False, True])
def test_recovery_publishes_with_original_identity_event_audit(
        document_service, doc_store, actor_patient, clock, promote_final):
    document_id, storage_key, identity = _crashed_reservation(
        document_service, doc_store, actor_patient, promote_final=promote_final)
    clock.advance(seconds=C.INFLIGHT_LEASE_SECONDS + 30)  # lease expires -> eligible
    recovered = document_service.recover_pending(startup=False)
    assert recovered == 1
    with read_transaction(document_service.database) as session:
        row = session.get(MedicalDocument, document_id)
        assert row.upload_status == C.UPLOAD_STORED
        assert row.content_sha256 == row.fixture_file_sha256
        assert row.staging_key is None and row.validated_at is not None
        # Original UPLOADED event preserved.
        event = session.execute(
            select(ExtractionEvent).where(ExtractionEvent.document_id == document_id,
                                          ExtractionEvent.event_type == C.EVENT_UPLOADED)
        ).scalar_one()
        assert event.actor_user_id == actor_patient.user_id
        # Original replay identity remembered (reconstructible without raw key).
        replay = session.execute(
            select(DurableIdempotency).where(
                DurableIdempotency.key_hash == identity.replay_key.key_hash,
                DurableIdempotency.operation == C.OP_DOC1_UPLOAD)
        ).scalar_one()
        assert replay.request_fingerprint == identity.request_fingerprint
        assert replay.status_code == 201
        # In-flight reservation released.
        assert session.get(DocumentInflightOperation, row.document_id) is None
        inflight_count = session.execute(
            select(func.count(DocumentInflightOperation.inflight_id)).where(
                DocumentInflightOperation.document_id == document_id)
        ).scalar_one()
        assert inflight_count == 0
    assert doc_store.exists(storage_key)


def test_recovery_does_not_touch_live_lease(document_service, doc_store, actor_patient):
    document_id, _, _ = _crashed_reservation(
        document_service, doc_store, actor_patient, promote_final=False)
    # No clock advance: the lease is still live.
    recovered = document_service.recover_pending(startup=False)
    assert recovered == 0
    with read_transaction(document_service.database) as session:
        assert session.get(MedicalDocument, document_id).upload_status == C.UPLOAD_PENDING_SCAN


def test_stale_attempt_is_fenced_out_after_recovery(document_service, doc_store, actor_patient, clock):
    document_id, _, _ = _crashed_reservation(
        document_service, doc_store, actor_patient, promote_final=False)
    with read_transaction(document_service.database) as session:
        inflight = session.execute(
            select(DocumentInflightOperation).where(
                DocumentInflightOperation.document_id == document_id)
        ).scalar_one()
        stale_id, stale_owner, stale_fence = (inflight.inflight_id, inflight.lease_owner,
                                              inflight.fence_token)
    clock.advance(seconds=C.INFLIGHT_LEASE_SECONDS + 30)
    assert document_service.recover_pending(startup=False) == 1
    # The stale attempt (old owner/fence) can no longer publish.
    with write_transaction(document_service.database) as session:
        with pytest.raises(Exception) as exc:
            document_service._assert_lease(session, stale_id, stale_owner, stale_fence)
        assert getattr(exc.value, "code", None) == "concurrency_conflict"
