"""Durable quota reservation, atomic transitions and safe crash recovery."""

from __future__ import annotations

import uuid
from pathlib import Path

import pytest
from sqlalchemy import select

from backend.app.term1.models import ConsentRecord
from backend.app.term1.tx import write_transaction
from backend.app.term1_c2_documents import constants as C
from backend.app.term1_c2_documents.models import DocumentInflightOperation, MedicalDocument
from backend.app.term1_c2_documents.service import Actor
from backend.app.term1_c2_documents.storage import make_storage_key

from .conftest import requires_native_ocr

FIXTURES = Path(__file__).resolve().parents[3] / "backend" / "app" / "term1_c2_documents" / "fixtures"


def _fixture(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


def _actor(patient):
    return Actor(user_id=patient["user_id"], role="patient", patient_id=patient["patient_id"])


@pytest.fixture
def patient_with_user(client, patient, c2_app):
    # Resolve the patient's user_id for service-level Actor construction.
    from backend.app.term1.models import PatientProfile
    from backend.app.term1.tx import read_transaction
    with read_transaction(c2_app.state.database) as session:
        user_id = session.execute(
            select(PatientProfile.user_id).where(
                PatientProfile.patient_id == patient["patient_id"])
        ).scalar_one()
    return {**patient, "user_id": user_id}


def _insert_document(service, patient, *, status, byte_size, storage_key=None,
                     staging_key=None, sha=None, created_at=None):
    document_id = str(uuid.uuid4())
    storage_key = storage_key or make_storage_key(patient["patient_id"], document_id)
    with write_transaction(service.database) as session:
        session.add(MedicalDocument(
            document_id=document_id, patient_id=patient["patient_id"],
            uploaded_by_user_id=patient["user_id"], document_kind=C.DOC_KIND_RESTING,
            fixture_template_id=C.TEMPLATE_RESTING,
            fixture_file_sha256=sha or "0" * 64,
            original_filename_sanitized="doc.pdf", declared_media_type=C.MEDIA_PDF,
            byte_size=byte_size, page_count=1, content_sha256=None,
            storage_key=storage_key, upload_status=status,
            created_at=created_at or service.clock.now_iso(),
            staging_key=staging_key,
        ))
    return document_id, storage_key


# --- quota -------------------------------------------------------------------
@requires_native_ocr
def test_document_count_quota_enforced(document_service, patient_with_user):
    patient = patient_with_user
    # 20 stored documents already consume the count quota.
    for _ in range(C.QUOTA_MAX_DOCUMENTS):
        _insert_document(document_service, patient, status=C.UPLOAD_STORED, byte_size=1000)
    with pytest.raises(Exception) as exc:
        document_service.upload(
            actor=_actor(patient), data=_fixture("resting_text.pdf"),
            declared_template_id=C.TEMPLATE_RESTING,
            declared_document_kind=C.DOC_KIND_RESTING,
            original_filename="resting_text.pdf", idempotency_key=f"up-{uuid.uuid4()}",
        )
    assert getattr(exc.value, "code", None) == "document_limit_reached"


@requires_native_ocr
def test_byte_quota_enforced(document_service, patient_with_user):
    patient = patient_with_user
    # Ten 5 MiB documents sum to exactly the 50 MiB byte quota (each file is
    # individually bounded by the 5 MiB per-file CHECK).
    for _ in range(C.QUOTA_MAX_BYTES // C.FILE_CAP_BYTES):
        _insert_document(document_service, patient, status=C.UPLOAD_STORED,
                         byte_size=C.FILE_CAP_BYTES)
    with pytest.raises(Exception) as exc:
        document_service.upload(
            actor=_actor(patient), data=_fixture("resting_text.pdf"),
            declared_template_id=C.TEMPLATE_RESTING,
            declared_document_kind=C.DOC_KIND_RESTING,
            original_filename="resting_text.pdf", idempotency_key=f"up-{uuid.uuid4()}",
        )
    assert getattr(exc.value, "code", None) == "document_limit_reached"


@requires_native_ocr
def test_pending_scan_reservation_counts_toward_quota(document_service, patient_with_user):
    patient = patient_with_user
    # A durable PENDING_SCAN reservation occupies quota even before promotion.
    for _ in range(C.QUOTA_MAX_DOCUMENTS):
        _insert_document(document_service, patient, status=C.UPLOAD_PENDING_SCAN, byte_size=1000)
    with pytest.raises(Exception) as exc:
        document_service.upload(
            actor=_actor(patient), data=_fixture("resting_text.pdf"),
            declared_template_id=C.TEMPLATE_RESTING,
            declared_document_kind=C.DOC_KIND_RESTING,
            original_filename="resting_text.pdf", idempotency_key=f"up-{uuid.uuid4()}",
        )
    assert getattr(exc.value, "code", None) == "document_limit_reached"


@requires_native_ocr
def test_failed_upload_releases_quota(document_service, patient_with_user):
    patient = patient_with_user
    # An unlisted file fails admission BEFORE any reservation, so quota is intact.
    bad = _fixture("resting_text.pdf")[:-1] + b"\x00"
    with pytest.raises(Exception) as exc:
        document_service.upload(
            actor=_actor(patient), data=bad,
            declared_template_id=C.TEMPLATE_RESTING,
            declared_document_kind=C.DOC_KIND_RESTING,
            original_filename="bad.pdf", idempotency_key=f"up-{uuid.uuid4()}",
        )
    assert getattr(exc.value, "code", None) == "invalid_document_content"
    # A valid upload still succeeds (no leaked reservation).
    result = document_service.upload(
        actor=_actor(patient), data=_fixture("resting_text.pdf"),
        declared_template_id=C.TEMPLATE_RESTING,
        declared_document_kind=C.DOC_KIND_RESTING,
        original_filename="resting_text.pdf", idempotency_key=f"up-{uuid.uuid4()}",
    )
    assert result["status"] == C.UPLOAD_STORED


@requires_native_ocr
def test_concurrent_uploads_race_for_last_quota_slot(document_service, patient_with_user):
    from concurrent.futures import ThreadPoolExecutor

    patient = patient_with_user
    # 19 stored documents leave exactly one count-quota slot.
    for _ in range(C.QUOTA_MAX_DOCUMENTS - 1):
        _insert_document(document_service, patient, status=C.UPLOAD_STORED, byte_size=1000)

    def attempt(seq):
        try:
            result = document_service.upload(
                actor=_actor(patient), data=_fixture("resting_text.pdf"),
                declared_template_id=C.TEMPLATE_RESTING,
                declared_document_kind=C.DOC_KIND_RESTING,
                original_filename="resting_text.pdf",
                idempotency_key=f"race-{seq}-{uuid.uuid4()}",
            )
            return ("stored", result["status"])
        except Exception as error:  # noqa: BLE001
            return ("rejected", getattr(error, "code", type(error).__name__))

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(attempt, range(2)))
    stored = [o for o in outcomes if o[0] == "stored"]
    rejected = [o for o in outcomes if o[0] == "rejected"]
    # BEGIN IMMEDIATE serializes the quota check + reservation: exactly one wins.
    assert len(stored) == 1
    assert len(rejected) == 1
    assert rejected[0][1] == "document_limit_reached"


# --- crash recovery ----------------------------------------------------------
def _stage_pending(service, doc_store, patient, *, age_seconds):
    """Create a durable PENDING_SCAN reservation + in-flight lease + staged blob.

    The lease is created live (expires ``INFLIGHT_LEASE_SECONDS`` from now); a
    test that advances the clock past the lease expiry makes it eligible for
    ownership-based recovery, while a fresh lease protects a live reservation.
    """
    data = _fixture("resting_text.pdf")
    import hashlib
    sha = hashlib.sha256(data).hexdigest()
    document_id = str(uuid.uuid4())
    storage_key = make_storage_key(patient["patient_id"], document_id)
    staging_key = doc_store.stage(data, storage_key)
    created = service.clock.now_iso()
    public_fields = {
        "content_sha256": sha, "document_kind": C.DOC_KIND_RESTING,
        "fixture_template_id": C.TEMPLATE_RESTING,
        "declared_media_type": C.MEDIA_PDF, "byte_size": len(data),
    }
    identity = service._identity(
        actor=_actor(patient), operation=C.OP_DOC1_UPLOAD, target_ref="none",
        raw_key=f"recover-{document_id}", public_fields=public_fields,
    )
    key = identity.replay_key
    with write_transaction(service.database) as session:
        session.add(MedicalDocument(
            document_id=document_id, patient_id=patient["patient_id"],
            uploaded_by_user_id=patient["user_id"], document_kind=C.DOC_KIND_RESTING,
            fixture_template_id=C.TEMPLATE_RESTING, fixture_file_sha256=sha,
            original_filename_sanitized="resting_text.pdf", declared_media_type=C.MEDIA_PDF,
            byte_size=len(data), page_count=0, content_sha256=None,
            storage_key=storage_key, upload_status=C.UPLOAD_PENDING_SCAN,
            created_at=created, staging_key=staging_key,
        ))
        session.flush()  # document row must exist before the reservation FK
        session.add(DocumentInflightOperation(
            inflight_id=str(uuid.uuid4()), replay_scope=key.replay_scope,
            key_hash=key.key_hash, actor_binding=key.actor_binding,
            operation=key.operation, target_ref=key.target_ref,
            request_fingerprint=identity.request_fingerprint,
            actor_user_id=patient["user_id"], patient_id=patient["patient_id"],
            document_id=document_id, state=C.INFLIGHT_STATE_IN_FLIGHT, fence_token=1,
            lease_owner=str(uuid.uuid4()),
            lease_expires_at=service.clock.plus(C.INFLIGHT_LEASE_SECONDS),
            attempt_count=1, failure_code=None, created_at=created, updated_at=created,
        ))
    return document_id, storage_key, staging_key


@requires_native_ocr
def test_recovery_promotes_valid_abandoned_reservation(document_service, doc_store,
                                                       patient_with_user, clock):
    patient = patient_with_user
    document_id, storage_key, staging_key = _stage_pending(
        document_service, doc_store, patient, age_seconds=120)
    clock.advance(seconds=C.PENDING_SCAN_RECOVERY_AGE_SECONDS + 60)
    recovered = document_service.recover_pending(startup=False)
    assert recovered == 1
    with write_transaction(document_service.database) as session:
        row = session.get(MedicalDocument, document_id)
        assert row.upload_status == C.UPLOAD_STORED
        assert row.content_sha256 == row.fixture_file_sha256
        assert row.staging_key is None
        assert row.validated_at is not None
    assert doc_store.exists(storage_key)
    assert not doc_store.exists(staging_key)


@requires_native_ocr
def test_recovery_never_races_live_reservation(document_service, doc_store,
                                               patient_with_user, clock):
    patient = patient_with_user
    document_id, storage_key, staging_key = _stage_pending(
        document_service, doc_store, patient, age_seconds=0)
    # Fresh reservation (age < grace): non-startup recovery must leave it alone.
    recovered = document_service.recover_pending(startup=False)
    assert recovered == 0
    with write_transaction(document_service.database) as session:
        row = session.get(MedicalDocument, document_id)
        assert row.upload_status == C.UPLOAD_PENDING_SCAN
        assert row.staging_key == staging_key


@requires_native_ocr
def test_recovery_refuses_revoked_consent(document_service, doc_store,
                                          patient_with_user, clock):
    patient = patient_with_user
    document_id, storage_key, staging_key = _stage_pending(
        document_service, doc_store, patient, age_seconds=120)
    # Revoke consent before recovery runs.
    with write_transaction(document_service.database) as session:
        consent = session.execute(
            select(ConsentRecord).where(ConsentRecord.patient_id == patient["patient_id"])
        ).scalar_one()
        consent.revoked_at = document_service.clock.now_iso()
    clock.advance(seconds=C.PENDING_SCAN_RECOVERY_AGE_SECONDS + 60)
    recovered = document_service.recover_pending(startup=False)
    assert recovered == 1
    with write_transaction(document_service.database) as session:
        row = session.get(MedicalDocument, document_id)
        # Never promoted without current authorization.
        assert row.upload_status == C.UPLOAD_FAILED
        assert row.content_sha256 is None
    assert not doc_store.exists(storage_key)


@requires_native_ocr
def test_recovery_refuses_tampered_staged_blob(document_service, doc_store,
                                               patient_with_user, clock):
    patient = patient_with_user
    document_id, storage_key, staging_key = _stage_pending(
        document_service, doc_store, patient, age_seconds=120)
    # Tamper the staged blob (same length) so the digest no longer matches.
    target = doc_store.root / staging_key
    blob = bytearray(target.read_bytes())
    blob[50] ^= 0xFF
    target.write_bytes(bytes(blob))
    clock.advance(seconds=C.PENDING_SCAN_RECOVERY_AGE_SECONDS + 60)
    recovered = document_service.recover_pending(startup=False)
    assert recovered == 1
    with write_transaction(document_service.database) as session:
        row = session.get(MedicalDocument, document_id)
        assert row.upload_status == C.UPLOAD_FAILED
    assert not doc_store.exists(storage_key)


@requires_native_ocr
def test_orphan_sweep_removes_unowned_staging_blob(document_service, doc_store,
                                                   patient_with_user, clock):
    patient = patient_with_user
    # A staging blob with NO owning reservation (crash before the DB write).
    document_id = str(uuid.uuid4())
    storage_key = make_storage_key(patient["patient_id"], document_id)
    staging_key = doc_store.stage(_fixture("resting_text.pdf"), storage_key)
    assert doc_store.exists(staging_key)
    # Make the file old enough to be reclaimed.
    import os
    old = clock().timestamp() - (C.PENDING_SCAN_RECOVERY_AGE_SECONDS + 120)
    os.utime(doc_store.root / staging_key, (old, old))
    removed = document_service.sweep_orphans()
    assert removed >= 1
    assert not doc_store.exists(staging_key)
