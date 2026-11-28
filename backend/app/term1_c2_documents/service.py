"""Track 2 document/OCR domain service (DOC1–DOC7 + crash recovery).

Reuses the C1 transaction (``BEGIN IMMEDIATE``), durable idempotency, session
authentication and consent mechanisms additively. Implements the accepted
upload lifecycle (durable ``PENDING_SCAN`` quota reservation -> bounded worker
validation outside the DB lock -> atomic ``STORED`` promotion), genuine
extraction, explicit patient confirmation with immutable versions, and safe
crash recovery that never promotes unverified or unauthorized content.

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
from sqlalchemy.orm import Session

from ..term1 import constants as c1
from ..term1.idempotency import (
    RequestIdentity,
    build_identity,
    precheck,
    remember,
    user_scope,
)
from ..term1.models import ConsentRecord, PatientProfile
from ..term1.timeutil import Clock
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

        # Phase 1: durable quota reservation under BEGIN IMMEDIATE.
        with write_transaction(self.database) as session:
            patient_id = self._patient_id(session, actor)
            identity = self._identity(
                actor=actor, operation=C.OP_DOC1_UPLOAD, target_ref="none",
                raw_key=idempotency_key, public_fields=public_fields,
            )
            decision = precheck(session, clock=self.clock, identity=identity)
            if decision.is_replay:
                self._require_consent(session, patient_id)  # live reauthorization
                return decision.body()
            self._require_consent(session, patient_id)
            # Stale PENDING_SCAN reservations count against quota (fail closed)
            # until crash recovery reclaims them; recovery never runs inside
            # this lock because it performs worker I/O.
            self._check_quota(session, patient_id, admission.byte_size)

            document_id = str(uuid.uuid4())
            storage_key = make_storage_key(patient_id, document_id)
            now = self.clock.now_iso()
            session.add(MedicalDocument(
                document_id=document_id, patient_id=patient_id,
                uploaded_by_user_id=actor.user_id, document_kind=admission.document_kind,
                fixture_template_id=admission.template_id,
                fixture_file_sha256=admission.content_sha256,
                original_filename_sanitized=sanitize_filename(original_filename),
                declared_media_type=admission.media_type, byte_size=admission.byte_size,
                page_count=0, content_sha256=None, storage_key=storage_key,
                upload_status=C.UPLOAD_PENDING_SCAN, created_at=now,
            ))
            session.flush()

        # Phase 2: stage + bounded worker validation OUTSIDE the DB lock.
        staging_key = self.store.stage(data, storage_key)
        try:
            with write_transaction(self.database) as session:
                row = session.get(MedicalDocument, document_id)
                row.staging_key = staging_key
            structure = self.worker.validate(
                storage_key=staging_key, content_sha256=admission.content_sha256,
                byte_size=admission.byte_size, media_type=admission.media_type,
            )
        except AdmissionRejection as error:
            self._fail_upload(document_id, staging_key, error.code)
            raise doc_api_error(error.code) from error
        except DocumentIntegrityMismatch as error:
            self._fail_upload(document_id, staging_key, "document_integrity_mismatch")
            raise doc_api_error("document_integrity_mismatch") from error
        except WorkerUnavailableError as error:
            self._fail_upload(document_id, staging_key, "worker_unavailable")
            raise doc_api_error("worker_unavailable") from error
        except BaseException:
            self._fail_upload(document_id, staging_key, "internal_error")
            raise

        # Phase 3: atomic promotion + idempotency + audit.
        with write_transaction(self.database) as session:
            patient_id = self._patient_id(session, actor)
            self._require_consent(session, patient_id)  # re-check at finalize
            row = session.get(MedicalDocument, document_id)
            if row is None or row.upload_status != C.UPLOAD_PENDING_SCAN:
                raise doc_api_error("concurrency_conflict")
            self.store.promote(staging_key, storage_key)
            now = self.clock.now_iso()
            row.upload_status = C.UPLOAD_STORED
            row.content_sha256 = admission.content_sha256
            row.page_count = structure.page_count
            row.staging_key = None
            row.validated_at = now
            response = self._document_projection(row)
            identity = self._identity(
                actor=actor, operation=C.OP_DOC1_UPLOAD, target_ref="none",
                raw_key=idempotency_key, public_fields=public_fields,
                public_response=response,
            )
            remember(session, clock=self.clock, identity=identity, status_code=201,
                     public_response=response, secret_disclosed=False)
            session.add(ExtractionEvent(
                event_id=str(uuid.uuid4()), document_id=document_id, extraction_id=None,
                extraction_version=None, event_type=C.EVENT_UPLOADED,
                actor_user_id=actor.user_id, actor_role=actor.role,
                field_diffs_json={"byte_size": admission.byte_size,
                                  "page_count": structure.page_count},
                recorded_at=now,
            ))
            doc_audit.record_document_event(
                session, clock=self.clock, event_type=C.AUDIT_EVENT_DOCUMENT_UPLOADED,
                outcome=c1.OUTCOME_SUCCESS, subject_type=C.AUDIT_SUBJECT_MEDICAL_DOCUMENT,
                subject_id=document_id, actor_user_id=actor.user_id,
                payload={"document_kind": admission.document_kind,
                         "media_type": admission.media_type, "byte_size": admission.byte_size},
            )
        return response

    def _fail_upload(self, document_id: str, staging_key: str | None, code: str) -> None:
        if staging_key:
            self.store.discard_staging(staging_key)
        with write_transaction(self.database) as session:
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
        # Simple opaque cursor over the ordered list.
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
        with read_transaction(self.database) as session:
            patient_id = self._patient_id(session, actor)
            row = self._owned_document(session, patient_id, document_id)
            if row.upload_status != C.UPLOAD_STORED or row.content_sha256 is None:
                raise doc_api_error("document_not_found")
            storage_key, sha, size = row.storage_key, row.content_sha256, row.byte_size
            media_type, template_id = row.declared_media_type, row.fixture_template_id

        # Genuine extraction outside the DB lock.
        try:
            raw = self.worker.extract(
                document_id=document_id, storage_key=storage_key, content_sha256=sha,
                byte_size=size, media_type=media_type, fixture_template_id=template_id,
            )
        except DocumentIntegrityMismatch as error:
            raise doc_api_error("document_integrity_mismatch") from error
        except WorkerUnavailableError as error:
            raise doc_api_error("worker_unavailable") from error
        except AdmissionRejection as error:
            raise doc_api_error(error.code) from error

        parsed = parse(raw, template_id)
        with write_transaction(self.database) as session:
            patient_id = self._patient_id(session, actor)
            self._require_consent(session, patient_id)
            row = self._owned_document(session, patient_id, document_id)
            identity = self._identity(
                actor=actor, operation=C.OP_DOC5_EXTRACT, target_ref=document_id,
                raw_key=idempotency_key, public_fields=public_fields,
            )
            decision = precheck(session, clock=self.clock, identity=identity)
            if decision.is_replay:
                self._require_consent(session, patient_id)
                return decision.body()
            # Re-verify the stored digest has not changed since extraction.
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
                confirmed_values_sha256=None, extracted_text_bytes=raw.extracted_text_bytes,
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
            identity = self._identity(
                actor=actor, operation=C.OP_DOC5_EXTRACT, target_ref=document_id,
                raw_key=idempotency_key, public_fields=public_fields, public_response=response,
            )
            remember(session, clock=self.clock, identity=identity, status_code=200,
                     public_response=response, secret_disclosed=False)
            doc_audit.record_document_event(
                session, clock=self.clock, event_type=C.AUDIT_EVENT_DOCUMENT_EXTRACTED,
                outcome=c1.OUTCOME_SUCCESS, subject_type=C.AUDIT_SUBJECT_DOCUMENT_EXTRACTION,
                subject_id=extraction_id, actor_user_id=actor.user_id,
                payload={"extraction_status": parsed.extraction_status, "mode": raw.mode},
            )
        return response

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
            return self._extraction_projection(extraction, fields)

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
                self._require_consent(session, patient_id)
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
            for name in C.PANEL_FIELD_ORDER:
                field = field_map.get(name)
                if field is None:
                    continue
                new_value = validated["inputs"].get(name)
                old_value = field.parsed_value_json
                edited = new_value != old_value
                field.confirmed_value_json = new_value
                if edited:
                    field.field_provenance = C.PROV_PATIENT_FROM_DRAFT
                    diffs[name] = {"from": old_value, "to": new_value}
                else:
                    field.field_provenance = C.PROV_OCR_CONFIRMED
            confirmed_doc = {
                "confirmed_inputs": validated["inputs"], "units": validated["units"],
                "missing_reasons": validated["missing_reasons"],
                "field_provenance": {n: field_map[n].field_provenance for n in field_map},
            }
            confirmed_sha = _sha256_text(confirmed_doc)
            extraction.is_confirmed = True
            extraction.extraction_status = C.STATUS_CONFIRMED
            extraction.confirmed_values_sha256 = confirmed_sha
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
            # Null, or a measured trestbps of 0, means unavailable (ED-DA-A2-01).
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
        """Reconcile abandoned ``PENDING_SCAN`` reservations.

        Worker validation runs OUTSIDE the DB write lock. Each candidate is then
        re-checked and transitioned atomically; a live upload that finalized in
        the meantime is left untouched (ownership/lease recheck), so recovery
        never races a live reservation.
        """
        from ..term1.timeutil import from_iso

        with read_transaction(self.database) as session:
            rows = session.execute(
                select(MedicalDocument).where(
                    MedicalDocument.upload_status == C.UPLOAD_PENDING_SCAN)
            ).scalars().all()
            candidates = [
                {
                    "document_id": row.document_id, "patient_id": row.patient_id,
                    "storage_key": row.storage_key, "staging_key": row.staging_key,
                    "sha": row.fixture_file_sha256, "size": row.byte_size,
                    "media_type": row.declared_media_type,
                    "uploaded_by": row.uploaded_by_user_id,
                    "age": (self.clock.now() - from_iso(row.created_at)).total_seconds(),
                }
                for row in rows
            ]
        recovered = 0
        for candidate in candidates:
            if not startup and candidate["age"] < C.PENDING_SCAN_RECOVERY_AGE_SECONDS:
                continue  # never race a live reservation
            # Validate outside the lock (worker I/O).
            structure = self._validate_recovery_candidate(candidate)
            with write_transaction(self.database) as session:
                row = session.get(MedicalDocument, candidate["document_id"])
                if row is None or row.upload_status != C.UPLOAD_PENDING_SCAN:
                    continue  # finalized or reclaimed by another path
                consent = session.execute(
                    select(ConsentRecord.consent_id).where(
                        ConsentRecord.patient_id == row.patient_id,
                        ConsentRecord.revoked_at.is_(None),
                    )
                ).first()
                if consent is None:
                    self._mark_failed(session, row, "consent_required")
                    recovered += 1
                    continue
                if structure is None:
                    self._mark_failed(session, row, "invalid_document_content")
                    recovered += 1
                    continue
                final_present = self.store.exists(row.storage_key)
                if not final_present:
                    if row.staging_key is None:
                        self._mark_failed(session, row, "invalid_document_content")
                        recovered += 1
                        continue
                    self.store.promote(row.staging_key, row.storage_key)
                row.upload_status = C.UPLOAD_STORED
                row.content_sha256 = row.fixture_file_sha256
                row.page_count = structure.page_count
                row.staging_key = None
                row.validated_at = self.clock.now_iso()
                doc_audit.record_document_event(
                    session, clock=self.clock, event_type=C.AUDIT_EVENT_DOCUMENT_RECOVERED,
                    outcome=c1.OUTCOME_SUCCESS, subject_type=C.AUDIT_SUBJECT_MEDICAL_DOCUMENT,
                    subject_id=row.document_id, actor_user_id=row.uploaded_by_user_id,
                )
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
            )
        except (AdmissionRejection, DocumentIntegrityMismatch, WorkerUnavailableError):
            return None

    def sweep_orphans(self) -> int:
        """Remove private blobs with no owning ``STORED``/``PENDING_SCAN`` row.

        Staging files older than the recovery grace period whose reservation no
        longer exists (crash between ``stage`` and the staging-key write) and
        final blobs whose row was never promoted are reclaimed. Live
        reservations are never touched.
        """
        import time as _time

        with read_transaction(self.database) as session:
            rows = session.execute(select(MedicalDocument)).scalars().all()
            live_staging = {row.staging_key for row in rows if row.staging_key}
            owned_final = {
                row.storage_key for row in rows
                if row.upload_status in (C.UPLOAD_STORED, C.UPLOAD_PENDING_SCAN)
            }
        now = _time.time()
        removed = 0
        for key, path in self.store.iter_files():
            if ".tmp-" in key:
                if key in live_staging:
                    continue  # a live reservation owns this staging blob
                try:
                    age = now - path.stat().st_mtime
                except OSError:
                    continue
                if age < C.PENDING_SCAN_RECOVERY_AGE_SECONDS:
                    continue
                self.store.discard_staging(key)
                removed += 1
            else:
                if key not in owned_final:
                    self.store.remove(key)
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
        # Bounded line metadata only; never logged. Full raw text is preserved by
        # its digest; the excerpt keeps the first lines for patient review.
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
                "unit": field.unit, "confidence": field.confidence,
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
