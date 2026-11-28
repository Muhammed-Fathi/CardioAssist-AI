"""Fixtures for the integrated C2 SAFE_SCOPE and document/OCR suite.

Every test gets a disposable SQLite database upgraded through the real
``06 → 07 → 08`` Alembic chain, including all core and document triggers. The
OCR tests exercise the genuine local engine (pdfminer.six / pypdfium2 / Pillow /
native Tesseract); if Tesseract is unavailable, only native-OCR cases are
reported NOT_RUN and skipped with the owner-local procedure (never mocked).
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.storage.database import Database
import backend.app.term1.models  # noqa: F401 - register C1 metadata
import backend.app.term1_c2_documents.models  # noqa: F401 - register document metadata
from backend.app.term1.api import Term1Handler, register_term1_routes
from backend.app.term1.c2_api import register_c2_routes
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
    """Disposable database upgraded through the integrated Alembic head."""
    config = Config(str(ROOT / "alembic.ini"))
    config.attributes["database_url"] = c2_database_url
    command.upgrade(config, "head")
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
    """Build the integrated C1+C2 test application over the migrated schema."""

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
        register_c2_routes(
            app, handler=term1_handler,
            document_service_provider=lambda: document_service,
        )
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
