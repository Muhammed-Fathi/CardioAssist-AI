"""Track 2 document/OCR domain service (DOC1–DOC7 + crash recovery).

Reuses the C1 transaction (``BEGIN IMMEDIATE``), durable idempotency, session
authentication and consent mechanisms additively. Implements the accepted
upload lifecycle (durable ``PENDING_SCAN`` quota reservation -> bounded worker
validation outside the DB lock -> atomic ``STORED`` promotion), genuine
extraction, explicit patient confirmation with immutable versions, and safe
crash recovery that never promotes unverified or unauthorized content.

Corrections round (reviewer REQUEST CHANGES #7233518509):

* T2-R1 — every mutating operation durably reserves its complete C1 idempotency
  identity with a lease owner/expiry and a monotonic fence token in the SAME
  transaction as the guarded effect. Simultaneous same-key requests collide on
  the unique replay identity (one document, never two). DOC5 checks live consent
  and the durable replay record BEFORE dispatching the worker. Recovery takes
  over only an EXPIRED lease (ownership, not age/startup), re-checks consent /
  SHA / manifest / quota, and publishes atomically while reconstructing the
  ORIGINAL replay identity for ``remember()`` plus the original ``UPLOADED``
  event and audit. No DB lock is held across OCR.
* T2-R2 — confirmation persists the exact canonical envelope and typed per-field
  units/reasons/provenance for the COMPLETE field set; the digest is verified on
  confirmed reads and assessment binding; bindings reference verified bytes and
  the exact confirmed extraction identity.

No method here dispatches an assessment, writes an ``inference_result`` row,
reads a private AI bundle, or falls back to a mock provider. Patient
confirmation is not clinician verification and is not assessment submission.
"""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from dataclasses import dataclass
from typing import Any, Mapping

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError as SqlIntegrityError
from sqlalchemy.orm import Session

from ..term1 import constants as c1
from ..term1.idempotency import (
    ReplayKey,
    RequestIdentity,
    build_identity,
    precheck,
    remember,
    user_scope,
)
from ..term1.models import ConsentRecord, PatientProfile
from ..term1.timeutil import Clock, from_iso
from ..term1.tx import read_transaction, write_transaction
from . import constants as C
from . import audit as doc_audit
from .admission import AdmissionError, admit_bytes
from .errors import doc_api_error
from .extraction_types import ParsedField, RawExtraction
from .fixture_manifest import FixtureManifest
from .models import (
    AssessmentDocument,
    DocumentExtraction,
    DocumentInflightOperation,
    ExtractionEvent,
    ExtractionField,
    MedicalDocument,
)
from .storage import IntegrityError, PrivateDocStore, make_storage_key
from .template_parser import parse
from .worker_client import (
    AdmissionRejection,
    DocumentIntegrityMismatch,
    OcrWorkerClient,
    WorkerUnavailableError,
)

_FILENAME_SAFE = re.compile(r"[^A-Za-z0-9._-]")


@dataclass(frozen=True)
class Actor:
    user_id: str
    role: str
    patient_id: str | None


def _canonical(value: Mapping[str, Any]) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def _sha256_text(value: Mapping[str, Any]) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def sanitize_filename(name: str) -> str:
    base = name.replace("\\", "/").split("/")[-1]
    base = _FILENAME_SAFE.sub("_", base).strip("._") or "document"
    return base[:128]


def confirmation_envelope(field_rows) -> dict[str, Any]:
    """Canonical confirmation envelope reconstructible from persisted children.

    The exact normalized document digested by ``confirmed_values_sha256``. It is
    built identically at confirmation time and at verification time, so any
    tampering with a persisted child value/unit/reason/provenance breaks the
    digest (T2-R2).
    """
    by_name = {f.field_name: f for f in field_rows}
    inputs: dict[str, Any] = {}
    units: dict[str, Any] = {}
    reasons: dict[str, Any] = {}
    provenance: dict[str, Any] = {}
    for name in C.PANEL_FIELD_ORDER:
        field = by_name.get(name)
        if field is None:
            continue
        inputs[name] = field.confirmed_value_json
        if field.confirmed_unit is not None:
            units[name] = field.confirmed_unit
        if field.missing_reason is not None:
            reasons[name] = field.missing_reason
        provenance[name] = field.field_provenance
    return {
        "confirmed_inputs": inputs, "units": units,
        "missing_reasons": reasons, "field_provenance": provenance,
    }


class DocumentService:
    def __init__(
        self,
        *,
        database,
        clock: Clock,
        pepper: bytes,
        store: PrivateDocStore,
        manifest: FixtureManifest,
        worker: OcrWorkerClient,
    ) -> None:
        self.database = database
        self.clock = clock
        self.pepper = pepper
        self.store = store
        self.manifest = manifest
        self.worker = worker

    # --- authorization helpers ---------------------------------------------
    def _patient_id(self, session: Session, actor: Actor) -> str:
        if actor.role != c1.ROLE_PATIENT:
            if actor.role == c1.ROLE_ADMIN:
                raise doc_api_error("admin_clinical_content_forbidden")
            raise doc_api_error("forbidden")
        if actor.patient_id is None:
            row = session.execute(
                select(PatientProfile.patient_id).where(PatientProfile.user_id == actor.user_id)
            ).scalar_one_or_none()
            if row is None:
                raise doc_api_error("forbidden")
            return row
        return actor.patient_id

    def _require_consent(self, session: Session, patient_id: str) -> None:
        active = session.execute(
            select(ConsentRecord.consent_id).where(
                ConsentRecord.patient_id == patient_id,
                ConsentRecord.kind == c1.CONSENT_KIND_SYNTHETIC_DEMO,
                ConsentRecord.revoked_at.is_(None),
            )
        ).first()
        if active is None:
            raise doc_api_error("consent_required")

    def _owned_document(self, session: Session, patient_id: str, document_id: str) -> MedicalDocument:
        row = session.get(MedicalDocument, document_id)
        if row is None or row.patient_id != patient_id:
            raise doc_api_error("document_not_found")
        return row

    # --- quota --------------------------------------------------------------
    def _quota_usage(self, session: Session, patient_id: str) -> tuple[int, int]:
        rows = session.execute(
            select(MedicalDocument.upload_status, MedicalDocument.byte_size,
                   MedicalDocument.reclaim_at).where(MedicalDocument.patient_id == patient_id)
        ).all()
        count = 0
        total = 0
        for status, size, reclaim_at in rows:
            if status not in C.QUOTA_COUNTED_STATUSES:
                continue
            if status == C.UPLOAD_FAILED and reclaim_at is not None:
                continue  # reclaimed failed rows no longer consume quota
            count += 1
            total += size
        return count, total

    def _check_quota(self, session: Session, patient_id: str, incoming_bytes: int) -> None:
        count, total = self._quota_usage(session, patient_id)
        if count + 1 > C.QUOTA_MAX_DOCUMENTS or total + incoming_bytes > C.QUOTA_MAX_BYTES:
            raise doc_api_error("document_limit_reached")

    # --- idempotency --------------------------------------------------------
    def _identity(self, *, actor: Actor, operation: str, target_ref: str,
                  raw_key: str, public_fields: Mapping[str, Any],
                  public_response: Mapping[str, Any] | None = None) -> RequestIdentity:
        return build_identity(
            pepper=self.pepper, scope=user_scope(actor.user_id), operation=operation,
            target_ref=target_ref, raw_key=raw_key, public_fields=public_fields,
            public_response=public_response,
        )

    # --- durable in-flight lease / fence (T2-R1) ----------------------------
    def _inflight_for(self, session: Session, identity: RequestIdentity) -> DocumentInflightOperation | None:
        key = identity.replay_key
        return session.execute(
            select(DocumentInflightOperation).where(
                DocumentInflightOperation.replay_scope == key.replay_scope,
                DocumentInflightOperation.key_hash == key.key_hash,
                DocumentInflightOperation.actor_binding == key.actor_binding,
                DocumentInflightOperation.operation == key.operation,
                DocumentInflightOperation.target_ref == key.target_ref,
            )
        ).scalar_one_or_none()

    def _acquire_lease(
        self, session: Session, *, identity: RequestIdentity, actor_user_id: str,
        patient_id: str, document_id: str,
    ) -> tuple[DocumentInflightOperation, str, int]:
        """Reserve or take over the durable lease; return (row, owner, fence).

        A live lease held by another attempt yields ``409 concurrency_conflict``;
        an expired lease or a FAILED attempt is fenced (token incremented) and
        taken over. A changed request fingerprint under the same key is a
        ``409 idempotency_key_conflict``.
        """
        now = self.clock.now()
        owner = str(uuid.uuid4())
        row = self._inflight_for(session, identity)
        key = identity.replay_key
        if row is None:
            row = DocumentInflightOperation(
                inflight_id=str(uuid.uuid4()), replay_scope=key.replay_scope,
                key_hash=key.key_hash, actor_binding=key.actor_binding,
                operation=key.operation, target_ref=key.target_ref,
                request_fingerprint=identity.request_fingerprint,
                actor_user_id=actor_user_id, patient_id=patient_id, document_id=document_id,
                state=C.INFLIGHT_STATE_IN_FLIGHT, fence_token=1, lease_owner=owner,
                lease_expires_at=self.clock.plus(C.INFLIGHT_LEASE_SECONDS),
                attempt_count=1, failure_code=None,
                created_at=self.clock.now_iso(), updated_at=self.clock.now_iso(),
            )
            session.add(row)
            try:
                session.flush()
            except SqlIntegrityError as error:
                # Another key already holds this document/operation.
                raise doc_api_error("concurrency_conflict") from error
            return row, owner, 1
        if row.request_fingerprint != identity.request_fingerprint:
            raise doc_api_error("idempotency_key_conflict")
        live = row.state == C.INFLIGHT_STATE_IN_FLIGHT and from_iso(row.lease_expires_at) > now
        if live:
            raise doc_api_error("concurrency_conflict")
        row.fence_token += 1
        row.lease_owner = owner
        row.lease_expires_at = self.clock.plus(C.INFLIGHT_LEASE_SECONDS)
        row.state = C.INFLIGHT_STATE_IN_FLIGHT
        row.attempt_count += 1
        row.failure_code = None
        row.updated_at = self.clock.now_iso()
        session.flush()
        return row, owner, row.fence_token

    def _assert_lease(self, session: Session, inflight_id: str, owner: str, fence: int) -> DocumentInflightOperation:
        row = session.get(DocumentInflightOperation, inflight_id)
        if row is None or row.lease_owner != owner or row.fence_token != fence \
                or row.state != C.INFLIGHT_STATE_IN_FLIGHT:
            raise doc_api_error("concurrency_conflict")
        return row

    def _release_lease_failed(self, session: Session, inflight_id: str, owner: str,
                              fence: int, code: str) -> None:
        row = session.get(DocumentInflightOperation, inflight_id)
        if row is not None and row.lease_owner == owner and row.fence_token == fence:
            row.state = C.INFLIGHT_STATE_FAILED
            row.failure_code = code
            row.updated_at = self.clock.now_iso()

    def _identity_from_inflight(self, row: DocumentInflightOperation) -> RequestIdentity:
        """Reconstruct the ORIGINAL replay identity for recovery ``remember()``."""
        return RequestIdentity(
            replay_key=ReplayKey(
                replay_scope=row.replay_scope, key_hash=row.key_hash,
                actor_binding=row.actor_binding, operation=row.operation,
                target_ref=row.target_ref,
            ),
            request_fingerprint=row.request_fingerprint,
            secret_fingerprints={}, secret_disclosed=False, public_body={},
        )

    # --- DOC1 upload --------------------------------------------------------
    def upload(
        self,
        *,
        actor: Actor,
        data: bytes,
        declared_template_id: str,
        declared_document_kind: str,
        original_filename: str,
        idempotency_key: str,
    ) -> dict[str, Any]:
        try:
            admission = admit_bytes(
                data,
                declared_template_id=declared_template_id,
                declared_document_kind=declared_document_kind, manifest=self.manifest,
            )
        except AdmissionError as error:
            raise doc_api_error(error.code) from error

        public_fields = {
            "content_sha256": admission.content_sha256,
            "document_kind": admission.document_kind,
            "fixture_template_id": admission.template_id,
            "declared_media_type": admission.media_type,
            "byte_size": admission.byte_size,
        }
        identity = self._identity(
            actor=actor, operation=C.OP_DOC1_UPLOAD, target_ref="none",
            raw_key=idempotency_key, public_fields=public_fields,
        )

        # Phase 1: durable reservation (document + lease) under BEGIN IMMEDIATE.
        with write_transaction(self.database) as session:
            patient_id = self._patient_id(session, actor)
            decision = precheck(session, clock=self.clock, identity=identity)
            if decision.is_replay:
                self._require_consent(session, patient_id)  # live reauthorization
                return decision.body()
            self._require_consent(session, patient_id)

            existing = self._inflight_for(session, identity)
            if existing is not None:
                # Same-key retry / recovery takeover of an existing reservation.
                inflight, owner, fence = self._acquire_lease(
                    session, identity=identity, actor_user_id=actor.user_id,
                    patient_id=patient_id, document_id=existing.document_id,
                )
                document_id = existing.document_id
                row = session.get(MedicalDocument, document_id)
                if row.upload_status == C.UPLOAD_STORED:
                    # Already finalized but the replay record was lost: rebuild it.
                    response = self._document_projection(row)
                    remember(session, clock=self.clock, identity=identity, status_code=201,
                             public_response=response, secret_disclosed=False)
                    session.delete(inflight)
                    return response
                # Re-arm a FAILED/PENDING reservation for a fresh bounded attempt.
                self._check_quota(session, patient_id, admission.byte_size)
                row.upload_status = C.UPLOAD_PENDING_SCAN
                row.staging_key = None
                row.reclaim_at = None
                row.content_sha256 = None
                row.validated_at = None
                row.page_count = 0
                row.pixel_width = None
                row.pixel_height = None
            else:
                self._check_quota(session, patient_id, admission.byte_size)
                document_id = str(uuid.uuid4())
                storage_key = make_storage_key(patient_id, document_id)
                row = MedicalDocument(
                    document_id=document_id, patient_id=patient_id,
                    uploaded_by_user_id=actor.user_id, document_kind=admission.document_kind,
                    fixture_template_id=admission.template_id,
                    fixture_file_sha256=admission.content_sha256,
                    original_filename_sanitized=sanitize_filename(original_filename),
                    declared_media_type=admission.media_type, byte_size=admission.byte_size,
                    page_count=0, content_sha256=None, storage_key=storage_key,
                    upload_status=C.UPLOAD_PENDING_SCAN, created_at=self.clock.now_iso(),
                )
                session.add(row)
                session.flush()
                inflight, owner, fence = self._acquire_lease(
                    session, identity=identity, actor_user_id=actor.user_id,
                    patient_id=patient_id, document_id=document_id,
                )
            storage_key = row.storage_key
            inflight_id = inflight.inflight_id

        # Phase 2: stage + bounded worker validation OUTSIDE the DB lock.
        staging_key = self.store.stage(data, storage_key)
        with write_transaction(self.database) as session:
            row = session.get(MedicalDocument, document_id)
            row.staging_key = staging_key
        try:
            structure = self.worker.validate(
                storage_key=staging_key, content_sha256=admission.content_sha256,
                byte_size=admission.byte_size, media_type=admission.media_type,
                fixture_file_sha256=admission.content_sha256,
            )
        except AdmissionRejection as error:
            self._fail_upload(document_id, inflight_id, owner, fence, staging_key, error.code)
            raise doc_api_error(error.code) from error
        except DocumentIntegrityMismatch as error:
            self._fail_upload(document_id, inflight_id, owner, fence, staging_key,
                              "document_integrity_mismatch")
            raise doc_api_error("document_integrity_mismatch") from error
        except WorkerUnavailableError as error:
            self._fail_upload(document_id, inflight_id, owner, fence, staging_key,
                              "worker_unavailable")
            raise doc_api_error("worker_unavailable") from error
        except BaseException:
            self._fail_upload(document_id, inflight_id, owner, fence, staging_key, "internal_error")
            raise

        # Phase 3: atomic promotion + idempotency + audit (fence-checked).
        with write_transaction(self.database) as session:
            self._assert_lease(session, inflight_id, owner, fence)
            patient_id = self._patient_id(session, actor)
            self._require_consent(session, patient_id)  # re-check at finalize
            row = session.get(MedicalDocument, document_id)
            if row is None or row.upload_status != C.UPLOAD_PENDING_SCAN:
                raise doc_api_error("concurrency_conflict")
            self.store.promote(staging_key, storage_key)
            response = self._publish_stored(
                session, row, structure.page_count, structure.pixel_width,
                structure.pixel_height, identity=identity,
                event_actor=actor.user_id, event_role=actor.role,
                audit_event=C.AUDIT_EVENT_DOCUMENT_UPLOADED,
            )
            session.delete(session.get(DocumentInflightOperation, inflight_id))
        return response

    def _publish_stored(
        self, session: Session, row: MedicalDocument, page_count: int,
        pixel_width: int | None, pixel_height: int | None, *, identity: RequestIdentity,
        event_actor: str, event_role: str, audit_event: str,
    ) -> dict[str, Any]:
        """Atomically mark STORED + remember + UPLOADED event + audit (T2-R1).

        Shared by the live finalize path and crash recovery so both produce the
        identical durable replay record, original event and audit association.
        """
        now = self.clock.now_iso()
        row.upload_status = C.UPLOAD_STORED
        row.content_sha256 = row.fixture_file_sha256
        row.page_count = page_count
        row.pixel_width = pixel_width
        row.pixel_height = pixel_height
        row.staging_key = None
        row.validated_at = now
        session.flush()
        response = self._document_projection(row)
        remember(session, clock=self.clock, identity=identity, status_code=201,
                 public_response=response, secret_disclosed=False)
        session.add(ExtractionEvent(
            event_id=str(uuid.uuid4()), document_id=row.document_id, extraction_id=None,
            extraction_version=None, event_type=C.EVENT_UPLOADED,
            actor_user_id=event_actor, actor_role=event_role,
            field_diffs_json={"byte_size": row.byte_size, "page_count": page_count},
            recorded_at=now,
        ))
        doc_audit.record_document_event(
            session, clock=self.clock, event_type=audit_event,
            outcome=c1.OUTCOME_SUCCESS, subject_type=C.AUDIT_SUBJECT_MEDICAL_DOCUMENT,
            subject_id=row.document_id, actor_user_id=event_actor,
            payload={"document_kind": row.document_kind,
                     "media_type": row.declared_media_type, "byte_size": row.byte_size},
        )
        return response

    def _fail_upload(self, document_id: str, inflight_id: str, owner: str, fence: int,
                     staging_key: str | None, code: str) -> None:
        if staging_key:
            self.store.discard_staging(staging_key)
        with write_transaction(self.database) as session:
            self._release_lease_failed(session, inflight_id, owner, fence, code)
            row = session.get(MedicalDocument, document_id)
            if row is not None and row.upload_status == C.UPLOAD_PENDING_SCAN:
                row.upload_status = C.UPLOAD_FAILED
                row.staging_key = None
                row.reclaim_at = self.clock.now_iso()
                doc_audit.record_document_event(
                    session, clock=self.clock, event_type=C.AUDIT_EVENT_DOCUMENT_UPLOAD_FAILED,
                    outcome=c1.OUTCOME_FAILED, subject_type=C.AUDIT_SUBJECT_MEDICAL_DOCUMENT,
                    subject_id=document_id, actor_user_id=row.uploaded_by_user_id, code=code,
                )

    # --- DOC2 / DOC3 --------------------------------------------------------
    def list_documents(self, *, actor: Actor, limit: int, cursor: str | None) -> dict[str, Any]:
        with read_transaction(self.database) as session:
            patient_id = self._patient_id(session, actor)
            query = select(MedicalDocument).where(
                MedicalDocument.patient_id == patient_id,
                MedicalDocument.upload_status == C.UPLOAD_STORED,
            ).order_by(MedicalDocument.created_at.desc(), MedicalDocument.document_id.desc())
            rows = session.execute(query).scalars().all()
        items = [self._document_projection(row, latest=self._latest_summary(row.document_id))
                 for row in rows]
        start = 0
        if cursor:
            start = int(cursor)
        page = items[start:start + limit]
        next_cursor = str(start + limit) if start + limit < len(items) else None
        return {"contract_version": C.CONTRACT_VERSION, "items": page, "next_cursor": next_cursor}

    def read_document(self, *, actor: Actor, document_id: str) -> dict[str, Any]:
        with read_transaction(self.database) as session:
            patient_id = self._patient_id(session, actor)
            row = self._owned_document(session, patient_id, document_id)
            projection = self._document_projection(row)
            projection["original_filename_sanitized"] = row.original_filename_sanitized
            projection["latest_extraction"] = self._latest_summary(document_id)
            projection["event_count"] = session.execute(
                select(func.count(ExtractionEvent.event_id)).where(
                    ExtractionEvent.document_id == document_id)
            ).scalar_one()
        return projection

    # --- DOC4 content (pre-header verified) ---------------------------------
    def read_content(self, *, actor: Actor, document_id: str) -> tuple[bytes, str, str]:
        with read_transaction(self.database) as session:
            patient_id = self._patient_id(session, actor)
            row = self._owned_document(session, patient_id, document_id)
            if row.upload_status != C.UPLOAD_STORED or row.content_sha256 is None:
                raise doc_api_error("document_not_found")
            storage_key, sha, size = row.storage_key, row.content_sha256, row.byte_size
            media_type = row.declared_media_type
            filename = row.original_filename_sanitized
        try:
            data = self.store.read_verified(storage_key, expected_sha256=sha, expected_size=size)
        except IntegrityError as error:
            with write_transaction(self.database) as session:
                doc_audit.record_document_event(
                    session, clock=self.clock,
                    event_type=C.AUDIT_EVENT_DOCUMENT_INTEGRITY_MISMATCH,
                    outcome=c1.OUTCOME_CONFLICT, subject_type=C.AUDIT_SUBJECT_MEDICAL_DOCUMENT,
                    subject_id=document_id, actor_user_id=actor.user_id,
                )
            raise doc_api_error("document_integrity_mismatch") from error
        return data, media_type, filename

    # --- DOC5 extract -------------------------------------------------------
    def extract(self, *, actor: Actor, document_id: str, idempotency_key: str) -> dict[str, Any]:
        public_fields = {"document_id": document_id}
        identity = self._identity(
            actor=actor, operation=C.OP_DOC5_EXTRACT, target_ref=document_id,
            raw_key=idempotency_key, public_fields=public_fields,
        )
        # Phase 1: live authorization + replay BEFORE any worker dispatch (T2-R1).
        with write_transaction(self.database) as session:
            patient_id = self._patient_id(session, actor)
            row = self._owned_document(session, patient_id, document_id)
            if row.upload_status != C.UPLOAD_STORED or row.content_sha256 is None:
                raise doc_api_error("document_not_found")
            self._require_consent(session, patient_id)
            decision = precheck(session, clock=self.clock, identity=identity)
            if decision.is_replay:
                return decision.body()  # remembered result; worker NOT dispatched
            inflight, owner, fence = self._acquire_lease(
                session, identity=identity, actor_user_id=actor.user_id,
                patient_id=patient_id, document_id=document_id,
            )
            storage_key, sha, size = row.storage_key, row.content_sha256, row.byte_size
            media_type, template_id = row.declared_media_type, row.fixture_template_id
            fixture_sha = row.fixture_file_sha256
            inflight_id = inflight.inflight_id

        # Phase 2: genuine extraction outside the DB lock.
        try:
            raw = self.worker.extract(
                document_id=document_id, storage_key=storage_key, content_sha256=sha,
                byte_size=size, media_type=media_type, fixture_template_id=template_id,
                fixture_file_sha256=fixture_sha,
            )
        except DocumentIntegrityMismatch as error:
            self._fail_extract(inflight_id, owner, fence, "document_integrity_mismatch")
            raise doc_api_error("document_integrity_mismatch") from error
        except WorkerUnavailableError as error:
            self._fail_extract(inflight_id, owner, fence, "worker_unavailable")
            raise doc_api_error("worker_unavailable") from error
        except AdmissionRejection as error:
            self._fail_extract(inflight_id, owner, fence, error.code)
            raise doc_api_error(error.code) from error

        parsed = parse(raw, template_id)
        # Phase 3: persist extraction + complete field set + replay (fence-checked).
        with write_transaction(self.database) as session:
            self._assert_lease(session, inflight_id, owner, fence)
            patient_id = self._patient_id(session, actor)
            self._require_consent(session, patient_id)  # re-check after worker
            row = self._owned_document(session, patient_id, document_id)
            if row.content_sha256 != sha:
                raise doc_api_error("document_integrity_mismatch")
            version = self._next_extraction_version(session, document_id)
            extraction_id = str(uuid.uuid4())
            now = self.clock.now_iso()
            extraction = DocumentExtraction(
                extraction_id=extraction_id, document_id=document_id,
                extraction_version=version, document_sha256=sha,
                extraction_mode=raw.mode, template_id=parsed.template_id,
                template_version=C.TEMPLATE_VERSION if parsed.template_matched else None,
                engine_name=raw.engine_name, engine_version=raw.engine_version,
                extraction_status=parsed.extraction_status, is_confirmed=False,
                confirmed_values_sha256=None, confirmed_envelope_json=None,
                extracted_text_bytes=raw.extracted_text_bytes,
                raw_text_sha256=raw.raw_text_sha256,
                raw_text_excerpt_json=self._raw_excerpt(raw), created_at=now,
            )
            session.add(extraction)
            session.flush()
            field_rows = []
            for field in parsed.fields:
                field_row = self._field_row(extraction_id, document_id, field)
                session.add(field_row)
                field_rows.append(field_row)
            session.add(ExtractionEvent(
                event_id=str(uuid.uuid4()), document_id=document_id,
                extraction_id=extraction_id, extraction_version=version,
                event_type=C.EVENT_EXTRACTED, actor_user_id=actor.user_id,
                actor_role=actor.role,
                field_diffs_json={"extraction_status": parsed.extraction_status,
                                  "mode": raw.mode, "conflict_flag": parsed.conflict_flag},
                recorded_at=now,
            ))
            response = self._extraction_projection(extraction, field_rows)
            remember(session, clock=self.clock, identity=identity, status_code=200,
                     public_response=response, secret_disclosed=False)
            doc_audit.record_document_event(
                session, clock=self.clock, event_type=C.AUDIT_EVENT_DOCUMENT_EXTRACTED,
                outcome=c1.OUTCOME_SUCCESS, subject_type=C.AUDIT_SUBJECT_DOCUMENT_EXTRACTION,
                subject_id=extraction_id, actor_user_id=actor.user_id,
                payload={"extraction_status": parsed.extraction_status, "mode": raw.mode},
            )
            session.delete(session.get(DocumentInflightOperation, inflight_id))
        return response

    def _fail_extract(self, inflight_id: str, owner: str, fence: int, code: str) -> None:
        with write_transaction(self.database) as session:
            self._release_lease_failed(session, inflight_id, owner, fence, code)

    # --- DOC6 read extraction -----------------------------------------------
    def read_extraction(self, *, actor: Actor, document_id: str) -> dict[str, Any]:
        with read_transaction(self.database) as session:
            patient_id = self._patient_id(session, actor)
            self._owned_document(session, patient_id, document_id)
            extraction = session.execute(
                select(DocumentExtraction).where(DocumentExtraction.document_id == document_id)
                .order_by(DocumentExtraction.extraction_version.desc())
            ).scalars().first()
            if extraction is None:
                raise doc_api_error("extraction_not_found")
            fields = session.execute(
                select(ExtractionField).where(ExtractionField.extraction_id == extraction.extraction_id)
            ).scalars().all()
            self._verify_confirmed_integrity(session, extraction, fields, actor.user_id)
            return self._extraction_projection(extraction, fields)

    def _verify_confirmed_integrity(self, session: Session, extraction: DocumentExtraction,
                                    fields, actor_user_id: str) -> None:
        """Reconstruct and verify the confirmation digest on read/bind (T2-R2)."""
        if not extraction.is_confirmed:
            return
        rebuilt = confirmation_envelope(fields)
        digest = _sha256_text(rebuilt)
        if digest != extraction.confirmed_values_sha256 or rebuilt != extraction.confirmed_envelope_json:
            with write_transaction(self.database) as audit_session:
                doc_audit.record_document_event(
                    audit_session, clock=self.clock,
                    event_type=C.AUDIT_EVENT_DOCUMENT_INTEGRITY_MISMATCH,
                    outcome=c1.OUTCOME_CONFLICT, subject_type=C.AUDIT_SUBJECT_DOCUMENT_EXTRACTION,
                    subject_id=extraction.extraction_id, actor_user_id=actor_user_id,
                )
            raise doc_api_error("document_integrity_mismatch")

    # --- DOC7 confirm -------------------------------------------------------
    def confirm(
        self,
        *,
        actor: Actor,
        document_id: str,
        extraction_id: str,
        extraction_version: int,
        confirmed_inputs: Mapping[str, Any],
        units: Mapping[str, Any],
        missing_reasons: Mapping[str, Any],
        confirm_fabricated_demo_inputs: bool,
        idempotency_key: str,
    ) -> dict[str, Any]:
        if confirm_fabricated_demo_inputs is not True:
            raise doc_api_error("validation_failed")
        if not isinstance(extraction_id, str) or not (1 <= len(extraction_id) <= 36):
            raise doc_api_error("validation_failed")
        if isinstance(extraction_version, bool) or not isinstance(extraction_version, int) \
                or extraction_version < 1:
            raise doc_api_error("validation_failed")
        if not isinstance(confirmed_inputs, Mapping) or not isinstance(units, Mapping) \
                or not isinstance(missing_reasons, Mapping):
            raise doc_api_error("validation_failed")
        public_fields = {
            "document_id": document_id, "extraction_id": extraction_id,
            "extraction_version": extraction_version,
            "confirmed_inputs": dict(confirmed_inputs), "units": dict(units),
            "missing_reasons": dict(missing_reasons),
        }
        with write_transaction(self.database) as session:
            patient_id = self._patient_id(session, actor)
            self._require_consent(session, patient_id)
            row = self._owned_document(session, patient_id, document_id)
            identity = self._identity(
                actor=actor, operation=C.OP_DOC7_CONFIRM, target_ref=document_id,
                raw_key=idempotency_key, public_fields=public_fields,
            )
            decision = precheck(session, clock=self.clock, identity=identity)
            if decision.is_replay:
                return decision.body()
            if row.fixture_template_id != C.TEMPLATE_RESTING:
                raise doc_api_error("unsupported_template_for_intake")
            extraction = session.get(DocumentExtraction, extraction_id)
            if extraction is None or extraction.document_id != document_id:
                raise doc_api_error("extraction_not_found")
            if extraction.extraction_version != extraction_version:
                raise doc_api_error("extraction_version_conflict")
            if extraction.is_confirmed:
                raise doc_api_error("extraction_already_confirmed")

            validated = self._validate_confirmed_inputs(confirmed_inputs, units, missing_reasons)
            field_rows = session.execute(
                select(ExtractionField).where(ExtractionField.extraction_id == extraction_id)
            ).scalars().all()
            field_map = {f.field_name: f for f in field_rows}

            now = self.clock.now_iso()
            diffs: dict[str, Any] = {}
            # Update the COMPLETE field set (no missing row skipped) while the
            # parent is still unconfirmed; the child trigger permits exactly this
            # confirmation transition and freezes everything afterwards.
            for name in C.PANEL_FIELD_ORDER:
                field = field_map.get(name)
                if field is None:
                    raise doc_api_error("document_integrity_mismatch")
                new_value = validated["inputs"].get(name)
                old_value = field.parsed_value_json
                edited = new_value != old_value
                field.confirmed_value_json = new_value
                field.confirmed_unit = validated["units"].get(name)
                field.missing_reason = validated["missing_reasons"].get(name)
                if edited:
                    field.field_provenance = C.PROV_PATIENT_FROM_DRAFT
                    diffs[name] = {"from": old_value, "to": new_value}
                else:
                    field.field_provenance = C.PROV_OCR_CONFIRMED
            session.flush()
            # Persist the exact canonical envelope reconstructed from children.
            envelope = confirmation_envelope(field_rows)
            confirmed_sha = _sha256_text(envelope)
            extraction.is_confirmed = True
            extraction.extraction_status = C.STATUS_CONFIRMED
            extraction.confirmed_values_sha256 = confirmed_sha
            extraction.confirmed_envelope_json = envelope
            extraction.confirmed_at = now
            event_type = C.EVENT_EDITED_AND_CONFIRMED if diffs else C.EVENT_PATIENT_CONFIRMED
            session.add(ExtractionEvent(
                event_id=str(uuid.uuid4()), document_id=document_id,
                extraction_id=extraction_id, extraction_version=extraction_version,
                event_type=event_type, actor_user_id=actor.user_id, actor_role=actor.role,
                field_diffs_json=diffs, recorded_at=now,
            ))
            response = {
                "contract_version": C.CONTRACT_VERSION, "document_id": document_id,
                "extraction_id": extraction_id, "extraction_version": extraction_version,
                "is_confirmed": True, "confirmed_values_sha256": confirmed_sha,
                "event_type": event_type, "confirmed_at": now,
            }
            identity = self._identity(
                actor=actor, operation=C.OP_DOC7_CONFIRM, target_ref=document_id,
                raw_key=idempotency_key, public_fields=public_fields, public_response=response,
            )
            remember(session, clock=self.clock, identity=identity, status_code=200,
                     public_response=response, secret_disclosed=False)
            doc_audit.record_document_event(
                session, clock=self.clock, event_type=C.AUDIT_EVENT_DOCUMENT_CONFIRMED,
                outcome=c1.OUTCOME_SUCCESS, subject_type=C.AUDIT_SUBJECT_DOCUMENT_EXTRACTION,
                subject_id=extraction_id, actor_user_id=actor.user_id,
                payload={"event_type": event_type, "edited_fields": sorted(diffs)},
            )
        return response

    def _validate_confirmed_inputs(
        self, inputs: Mapping[str, Any], units: Mapping[str, Any],
        missing_reasons: Mapping[str, Any],
    ) -> dict[str, Any]:
        """Strict typed validation of patient-confirmed resting values.

        Mandatory fields (age, sex, cp) must carry a valid typed value; optional
        fields may be null only with a closed-vocabulary missingness reason.
        Units are checked for continuous fields; a measured ``trestbps`` of 0 is
        treated as unavailable (ED-DA-A2-01), never as a numeric input.
        """
        allowed = set(C.PANEL_FIELD_ORDER)
        if set(inputs) - allowed:
            raise doc_api_error("prohibited_clinical_field")
        if set(units) - allowed or set(missing_reasons) - allowed:
            raise doc_api_error("validation_failed")
        clean_inputs: dict[str, Any] = {}
        clean_units: dict[str, Any] = {}
        clean_reasons: dict[str, Any] = {}
        for name in C.PANEL_FIELD_ORDER:
            rule = C.PANEL_FIELD_RULES[name]
            value = inputs.get(name)
            if isinstance(value, bool):
                raise doc_api_error("invalid_panel_input")
            unavailable = value is None or (
                name in C.ZERO_IS_UNAVAILABLE_FIELDS
                and isinstance(value, int) and value == 0
            )
            if unavailable:
                if name in C.MANDATORY_FIELDS:
                    raise doc_api_error("invalid_panel_input")
                reason = missing_reasons.get(name)
                if reason not in C.MISSING_REASONS:
                    raise doc_api_error("missing_reason_mismatch")
                clean_inputs[name] = None
                clean_reasons[name] = reason
                continue
            if name in missing_reasons:
                raise doc_api_error("missing_reason_mismatch")
            if not isinstance(value, int):
                raise doc_api_error("invalid_panel_input")
            if rule.role == "categorical":
                if value not in rule.codes:
                    raise doc_api_error("invalid_panel_input")
            else:
                if value <= 0:
                    raise doc_api_error("invalid_panel_input")
                declared_unit = units.get(name)
                if declared_unit != rule.unit:
                    raise doc_api_error("invalid_panel_input")
                clean_units[name] = rule.unit
            clean_inputs[name] = value
        return {"inputs": clean_inputs, "units": clean_units, "missing_reasons": clean_reasons}

    # --- assessment binding helper (called by Track 1 S1) -------------------
    def bind_assessment_document(
        self, session: Session, *, assessment_id: str, patient_id: str,
        document_id: str, attachment_role: str, extraction_id: str | None,
        extraction_version: int | None,
    ) -> AssessmentDocument:
        row = self._owned_document(session, patient_id, document_id)
        if row.upload_status != C.UPLOAD_STORED or row.content_sha256 is None:
            raise doc_api_error("document_not_found")
        # Bind VERIFIED bytes (T2-R2): re-read and verify the complete buffer
        # against the recorded digest before recording the binding identity.
        try:
            self.store.read_verified(
                row.storage_key, expected_sha256=row.content_sha256, expected_size=row.byte_size
            )
        except IntegrityError as error:
            raise doc_api_error("document_integrity_mismatch") from error
        if attachment_role == C.ROLE_OCR_SOURCE:
            if extraction_id is None or extraction_version is None:
                raise doc_api_error("validation_failed")
            extraction = session.get(DocumentExtraction, extraction_id)
            if extraction is None or extraction.document_id != document_id:
                raise doc_api_error("extraction_not_found")
            if not extraction.is_confirmed:
                raise doc_api_error("document_not_confirmed")
            if extraction.extraction_version != extraction_version:
                raise doc_api_error("extraction_version_conflict")
            fields = session.execute(
                select(ExtractionField).where(ExtractionField.extraction_id == extraction_id)
            ).scalars().all()
            self._verify_confirmed_integrity(session, extraction, fields, row.uploaded_by_user_id)
        binding = AssessmentDocument(
            binding_id=str(uuid.uuid4()), assessment_id=assessment_id,
            patient_id=patient_id, document_id=document_id, extraction_id=extraction_id,
            extraction_version=extraction_version, document_sha256_at_bind=row.content_sha256,
            attachment_role=attachment_role, created_at=self.clock.now_iso(),
        )
        session.add(binding)
        return binding

    # --- crash recovery -----------------------------------------------------
    def recover_pending(self, *, startup: bool = False) -> int:
        """Reconcile abandoned ``PENDING_SCAN`` reservations by lease ownership.

        Eligibility is an EXPIRED durable lease (T2-R1), never age alone or a
        startup boolean. Worker validation runs OUTSIDE the DB write lock. Each
        candidate is fenced (token incremented) before validation and re-checked
        at publish, so a live attempt that finalizes in the meantime is never
        raced. Recovery reconstructs the ORIGINAL replay identity and emits the
        original ``UPLOADED`` event + audit atomically with the STORED promotion.
        """
        with read_transaction(self.database) as session:
            rows = session.execute(
                select(MedicalDocument).where(
                    MedicalDocument.upload_status == C.UPLOAD_PENDING_SCAN)
            ).scalars().all()
            candidates = []
            now = self.clock.now()
            for row in rows:
                inflight = session.execute(
                    select(DocumentInflightOperation).where(
                        DocumentInflightOperation.document_id == row.document_id,
                        DocumentInflightOperation.operation == C.OP_DOC1_UPLOAD,
                    )
                ).scalar_one_or_none()
                if inflight is None:
                    continue  # no durable ownership record; nothing to recover
                if from_iso(inflight.lease_expires_at) > now:
                    continue  # a live attempt owns this reservation
                candidates.append({
                    "document_id": row.document_id, "patient_id": row.patient_id,
                    "storage_key": row.storage_key, "staging_key": row.staging_key,
                    "sha": row.fixture_file_sha256, "size": row.byte_size,
                    "media_type": row.declared_media_type,
                    "uploaded_by": row.uploaded_by_user_id,
                    "inflight_id": inflight.inflight_id,
                })
        recovered = 0
        for candidate in candidates:
            # Take over the expired lease (fence) before any worker I/O.
            with write_transaction(self.database) as session:
                row = session.get(MedicalDocument, candidate["document_id"])
                if row is None or row.upload_status != C.UPLOAD_PENDING_SCAN:
                    continue
                inflight = session.get(DocumentInflightOperation, candidate["inflight_id"])
                if inflight is None or from_iso(inflight.lease_expires_at) > self.clock.now():
                    continue
                owner = str(uuid.uuid4())
                inflight.fence_token += 1
                inflight.lease_owner = owner
                inflight.lease_expires_at = self.clock.plus(C.INFLIGHT_LEASE_SECONDS)
                inflight.state = C.INFLIGHT_STATE_IN_FLIGHT
                inflight.updated_at = self.clock.now_iso()
                fence = inflight.fence_token
                identity = self._identity_from_inflight(inflight)
                inflight_id = inflight.inflight_id
            structure = self._validate_recovery_candidate(candidate)
            with write_transaction(self.database) as session:
                try:
                    self._assert_lease(session, inflight_id, owner, fence)
                except Exception:
                    continue  # another path took over; leave it untouched
                row = session.get(MedicalDocument, candidate["document_id"])
                if row is None or row.upload_status != C.UPLOAD_PENDING_SCAN:
                    continue
                consent = session.execute(
                    select(ConsentRecord.consent_id).where(
                        ConsentRecord.patient_id == row.patient_id,
                        ConsentRecord.kind == c1.CONSENT_KIND_SYNTHETIC_DEMO,
                        ConsentRecord.revoked_at.is_(None),
                    )
                ).first()
                if consent is None:
                    self._mark_failed(session, row, "consent_required")
                    self._release_lease_failed(session, inflight_id, owner, fence, "consent_required")
                    recovered += 1
                    continue
                if structure is None:
                    self._mark_failed(session, row, "invalid_document_content")
                    self._release_lease_failed(session, inflight_id, owner, fence,
                                               "invalid_document_content")
                    recovered += 1
                    continue
                if not self.store.exists(row.storage_key):
                    if row.staging_key is None:
                        self._mark_failed(session, row, "invalid_document_content")
                        self._release_lease_failed(session, inflight_id, owner, fence,
                                                   "invalid_document_content")
                        recovered += 1
                        continue
                    self.store.promote(row.staging_key, row.storage_key)
                self._publish_stored(
                    session, row, structure.page_count, structure.pixel_width,
                    structure.pixel_height, identity=identity,
                    event_actor=row.uploaded_by_user_id, event_role=c1.ROLE_PATIENT,
                    audit_event=C.AUDIT_EVENT_DOCUMENT_RECOVERED,
                )
                session.delete(session.get(DocumentInflightOperation, inflight_id))
                recovered += 1
        return recovered

    def _validate_recovery_candidate(self, candidate: dict):
        """Return StructureInfo if the staged/final blob is valid, else None."""
        final_present = self.store.exists(candidate["storage_key"])
        key = candidate["storage_key"] if final_present else candidate["staging_key"]
        if key is None:
            return None
        if self.manifest.lookup(candidate["sha"]) is None:
            return None
        try:
            self.store.read_verified(
                key, expected_sha256=candidate["sha"], expected_size=candidate["size"]
            )
        except IntegrityError:
            return None
        try:
            return self.worker.validate(
                storage_key=key, content_sha256=candidate["sha"],
                byte_size=candidate["size"], media_type=candidate["media_type"],
                fixture_file_sha256=candidate["sha"],
            )
        except (AdmissionRejection, DocumentIntegrityMismatch, WorkerUnavailableError):
            return None

    def sweep_orphans(self) -> int:
        """Remove private blobs with no owning live reservation.

        Ownership is re-checked fresh per candidate (T2-R1): a staging blob whose
        document row still holds a live lease, or any STORED/PENDING_SCAN final
        blob, is never touched. Only truly orphaned staging older than the grace
        period and unowned final blobs are reclaimed, and a blob is counted only
        after a successful unlink.
        """
        import time as _time

        now = _time.time()
        removed = 0
        for key, path in self.store.iter_files():
            if ".tmp-" in key:
                final_key = key[: key.find(".bin.tmp-") + len(".bin")]
                document_id = final_key.split("/")[1][: -len(".bin")]
                with read_transaction(self.database) as session:
                    row = session.get(MedicalDocument, document_id)
                    if row is not None and row.staging_key == key:
                        continue  # a reservation owns this staging blob
                    if row is not None and row.upload_status in (
                        C.UPLOAD_STORED, C.UPLOAD_PENDING_SCAN
                    ):
                        continue  # live/owned; leave for finalize/recovery
                try:
                    age = now - path.stat().st_mtime
                except OSError:
                    continue
                if age < C.PENDING_SCAN_RECOVERY_AGE_SECONDS:
                    continue
                self.store.discard_staging(key)
                if not path.exists():
                    removed += 1
            else:
                document_id = key.split("/")[1][: -len(".bin")]
                with read_transaction(self.database) as session:
                    row = session.get(MedicalDocument, document_id)
                    if row is not None and row.upload_status in (
                        C.UPLOAD_STORED, C.UPLOAD_PENDING_SCAN
                    ):
                        continue
                self.store.remove(key)
                if not path.exists():
                    removed += 1
        return removed

    def _mark_failed(self, session: Session, row: MedicalDocument, code: str) -> None:
        if row.staging_key:
            self.store.discard_staging(row.staging_key)
        row.upload_status = C.UPLOAD_FAILED
        row.staging_key = None
        row.reclaim_at = self.clock.now_iso()
        doc_audit.record_document_event(
            session, clock=self.clock, event_type=C.AUDIT_EVENT_DOCUMENT_UPLOAD_FAILED,
            outcome=c1.OUTCOME_FAILED, subject_type=C.AUDIT_SUBJECT_MEDICAL_DOCUMENT,
            subject_id=row.document_id, actor_user_id=row.uploaded_by_user_id, code=code,
        )

    # --- projections / helpers ----------------------------------------------
    def _next_extraction_version(self, session: Session, document_id: str) -> int:
        current = session.execute(
            select(func.max(DocumentExtraction.extraction_version)).where(
                DocumentExtraction.document_id == document_id)
        ).scalar_one()
        return (current or 0) + 1

    def _raw_excerpt(self, raw: RawExtraction) -> dict[str, Any]:
        return {
            "mode": raw.mode,
            "line_count": len(raw.lines),
            "excerpt": [line.text for line in raw.lines[:40]],
        }

    def _field_row(self, extraction_id: str, document_id: str, field: ParsedField) -> ExtractionField:
        return ExtractionField(
            field_record_id=str(uuid.uuid4()), extraction_id=extraction_id,
            document_id=document_id, field_name=field.field_name,
            page_number=field.page_number, region_json=list(field.region) if field.region else None,
            raw_value_text=(field.raw_text[:128] if field.raw_text else None),
            parsed_value_json=field.typed_value, confirmed_value_json=None,
            unit=field.unit, confidence=field.confidence, parse_status=field.parse_status,
            conflict_flag=field.conflict_flag, field_provenance=field.field_provenance,
            confirmed_unit=None, missing_reason=field.missing_reason,
        )

    def _latest_summary(self, document_id: str) -> dict[str, Any] | None:
        with read_transaction(self.database) as session:
            extraction = session.execute(
                select(DocumentExtraction).where(DocumentExtraction.document_id == document_id)
                .order_by(DocumentExtraction.extraction_version.desc())
            ).scalars().first()
            if extraction is None:
                return None
            return {
                "extraction_id": extraction.extraction_id,
                "extraction_version": extraction.extraction_version,
                "extraction_status": extraction.extraction_status,
                "is_confirmed": extraction.is_confirmed,
            }

    def _document_projection(self, row: MedicalDocument, latest: dict | None = None) -> dict[str, Any]:
        document = {
            "contract_version": C.CONTRACT_VERSION, "document_id": row.document_id,
            "status": row.upload_status, "document_kind": row.document_kind,
            "fixture_template_id": row.fixture_template_id,
            "declared_media_type": row.declared_media_type, "byte_size": row.byte_size,
            "page_count": row.page_count, "content_sha256": row.content_sha256,
            "pixel_width": row.pixel_width, "pixel_height": row.pixel_height,
            "created_at": row.created_at,
        }
        if latest is not None:
            document["latest_extraction_id"] = latest["extraction_id"]
            document["latest_extraction_version"] = latest["extraction_version"]
            document["latest_extraction_status"] = latest["extraction_status"]
        return document

    def _extraction_projection(self, extraction: DocumentExtraction, fields) -> dict[str, Any]:
        field_list = []
        for field in fields:
            field_list.append({
                "field_name": field.field_name, "raw_text": field.raw_value_text,
                "typed_value_json": field.parsed_value_json,
                "confirmed_value_json": field.confirmed_value_json,
                "unit": field.unit, "confirmed_unit": field.confirmed_unit,
                "missing_reason": field.missing_reason,
                "confidence": field.confidence,
                "conflict_flag": field.conflict_flag, "parse_status": field.parse_status,
                "provenance_kind": field.field_provenance,
            })
        return {
            "contract_version": C.CONTRACT_VERSION, "document_id": extraction.document_id,
            "extraction_id": extraction.extraction_id,
            "extraction_version": extraction.extraction_version,
            "extraction_status": extraction.extraction_status,
            "template_id": extraction.template_id, "is_confirmed": extraction.is_confirmed,
            "confirmed_values_sha256": extraction.confirmed_values_sha256,
            "fields": field_list, "created_at": extraction.created_at,
        }
