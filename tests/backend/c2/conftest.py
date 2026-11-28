"""Fixtures for the Track 2 C2 SAFE_SCOPE suite.

Schema strategy (explicitly labelled disposable harness):
    Track 1's shared migration ``20261128_07`` is not yet published on this
    isolated contributor branch, so ``alembic upgrade head`` cannot resolve the
    ``06 -> 07 -> 08`` chain here. These tests therefore build a disposable
    schema WITHOUT alembic: the C1 tables are created from the registered ORM
    metadata, then migration ``20261128_08``'s own ``upgrade()`` is applied
    directly through a bound ``alembic.operations.Operations`` so the five C2
    tables AND the eight real immutability triggers exist exactly as the
    migration defines them. The ``assessment_document`` composite FK targets
    Track 1's ``assessment`` table (absent here); SQLite permits the CREATE and
    DOC1–DOC7 never insert into it, so the harness is faithful for Track 2.
    Migration 08 upgrade/downgrade *through alembic* remains an integration
    checkpoint pending Track 1's 07 (reported as a blocker, not faked).

Genuine OCR:
    The extraction tests run the REAL engine (pdfminer.six / pypdfium2 / Pillow /
    native Tesseract) through the in-process worker client. If the native
    Tesseract binary is unavailable the genuine-OCR tests are skipped and
    reported NOT_RUN with the owner-local procedure (never mocked).
"""

from __future__ import annotations

import importlib.util
import os
import shutil
from pathlib import Path

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine

from backend.app.storage.database import Database
from backend.app.storage.models import Base
import backend.app.term1.models  # noqa: F401 - register C1 metadata
import backend.app.term1_c2_documents.models as c2_models  # noqa: F401
from backend.app.term1.api import Term1Handler, register_term1_routes
from backend.app.term1.timeutil import Clock
from backend.app.term1_c2_documents.api import DocumentHandler, register_document_routes
from backend.app.term1_c2_documents.fixture_manifest import load_manifest
from backend.app.term1_c2_documents.ocr_engine import OcrEngineConfig
from backend.app.term1_c2_documents.service import DocumentService
from backend.app.term1_c2_documents.storage import PrivateDocStore
from backend.app.term1_c2_documents.worker_client import LocalOcrWorkerClient

# Reuse the deterministic C1 test material and helpers (synthetic only).
from tests.backend.c1.conftest import (  # noqa: F401
    MutableClock,
    test_settings,  # re-exported session fixture (pytest registers it by name)
)
from tests.backend.c1 import factories  # noqa: F401

ROOT = Path(__file__).resolve().parents[3]
MIGRATION_08 = ROOT / "backend" / "migrations" / "versions" / "20261128_08_c2_documents_ocr.py"
C2_TABLES = {
    "medical_document", "document_extraction", "extraction_field",
    "extraction_event", "assessment_document",
}

# Native Tesseract location (owner-local). Overridable for portability.
_NATIVE_TESSERACT = Path("/home/user/ocr-native/prefix/bin/tesseract")
_NATIVE_TESSDATA = Path("/home/user/ocr-native/prefix/share/tessdata")


def _tesseract_cmd() -> str:
    override = os.environ.get("CARDIOASSIST_TESSERACT_CMD")
    if override:
        return override
    if _NATIVE_TESSERACT.is_file():
        return str(_NATIVE_TESSERACT)
    return shutil.which("tesseract") or "tesseract"


def _tessdata_dir() -> str | None:
    override = os.environ.get("TESSDATA_PREFIX")
    if override:
        return override
    if _NATIVE_TESSDATA.is_dir():
        return str(_NATIVE_TESSDATA)
    return None


def ocr_engine_config() -> OcrEngineConfig:
    return OcrEngineConfig(
        tesseract_cmd=_tesseract_cmd(), tessdata_dir=_tessdata_dir()
    )


def native_ocr_available() -> bool:
    cmd = _tesseract_cmd()
    if not (Path(cmd).is_file() or shutil.which(cmd)):
        return False
    try:
        import pytesseract

        pytesseract.pytesseract.tesseract_cmd = cmd
        pytesseract.get_tesseract_version()
        return True
    except Exception:
        return False


requires_native_ocr = pytest.mark.skipif(
    not native_ocr_available(),
    reason="NOT_RUN: native Tesseract unavailable; see owner-local Windows procedure.",
)


@pytest.fixture
def clock() -> MutableClock:
    return MutableClock()


@pytest.fixture
def c2_database_url(tmp_path) -> str:
    return f"sqlite:///{(tmp_path / 'c2.sqlite3').as_posix()}"


@pytest.fixture
def c2_schema(c2_database_url) -> str:
    """Disposable C1+C2 schema with the real migration-08 triggers."""
    engine = create_engine(c2_database_url)
    try:
        c1_tables = [t for n, t in Base.metadata.tables.items() if n not in C2_TABLES]
        Base.metadata.create_all(engine, tables=c1_tables)
        spec = importlib.util.spec_from_file_location("mig08_harness", MIGRATION_08)
        mig = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mig)
        with engine.connect() as conn:
            ctx = MigrationContext.configure(conn)
            mig.op = Operations(ctx)
            mig.upgrade()
            conn.commit()
    finally:
        engine.dispose()
    return c2_database_url


@pytest.fixture
def doc_store(tmp_path) -> PrivateDocStore:
    # Private blob root outside the repository working tree / any web root.
    return PrivateDocStore(tmp_path / "private-docs")


@pytest.fixture
def manifest():
    return load_manifest()


@pytest.fixture
def ocr_worker(doc_store) -> LocalOcrWorkerClient:
    return LocalOcrWorkerClient(doc_store, ocr_engine_config())


@pytest.fixture
def document_service(c2_schema, clock, doc_store, manifest, ocr_worker, test_settings):
    database = Database(c2_schema)
    service = DocumentService(
        database=database, clock=Clock(clock), pepper=test_settings.pepper,
        store=doc_store, manifest=manifest, worker=ocr_worker,
    )
    yield service
    database.dispose()


def _source_key(request) -> str:
    client = request.client
    return client.host if client is not None and client.host else "unknown-source"


@pytest.fixture
def c2_app_factory(c2_schema, clock, test_settings, document_service):
    """Build a C1+DOC test application (no alembic verify_schema)."""

    def build() -> FastAPI:
        database = document_service.database
        term1_clock = Clock(clock)
        app = FastAPI(docs_url=None, redoc_url=None, redirect_slashes=False)
        app.state.database = database
        term1_handler = Term1Handler(
            database=database, clock=term1_clock, settings=test_settings,
            source_key_for=_source_key,
        )
        app.state.term1 = term1_handler
        register_term1_routes(app, handler=term1_handler)
        doc_handler = DocumentHandler(
            database=database, term1=term1_handler, service=document_service
        )
        app.state.doc = doc_handler
        register_document_routes(app, handler=doc_handler)
        return app

    return build


@pytest.fixture
def c2_app(c2_app_factory):
    return c2_app_factory()


@pytest.fixture
def client(c2_app):
    with TestClient(c2_app) as test_client:
        yield test_client


# --- provisioning helpers ----------------------------------------------------
@pytest.fixture
def patient(c2_app, client):
    """A registered synthetic-demo patient with active consent + session."""
    chain = factories.setup_doctor_with_invitation(c2_app, client)
    access_code = chain["invitation"]["access_code"]
    registered = factories.register_patient(client, access_code)
    return {
        "patient_id": registered["patient_id"],
        "token": registered["session_token"],
        "doctor": chain["doctor"],
        "chain": chain,
    }
