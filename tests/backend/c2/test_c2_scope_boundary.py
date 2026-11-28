"""Integrated SAFE_SCOPE routes preserve the no-AI/no-inference boundary."""

from __future__ import annotations

import re
import subprocess
import sys
import uuid
from pathlib import Path

import pytest
from sqlalchemy import text

from backend.app.term1.tx import read_transaction
from backend.app.term1_c2_documents import constants as C

ROOT = Path(__file__).resolve().parents[3]
PACKAGE = ROOT / "backend" / "app" / "term1_c2_documents"
FIXTURES = PACKAGE / "fixtures"


def test_create_app_registers_the_integrated_document_routes():
    from backend.app.main import create_app
    from backend.app.term1.openapi import SERVED_OPERATIONS

    app = create_app()
    served = {
        (method.lower(), path)
        for route in app.routes
        for path in [str(getattr(route, "path", ""))]
        for method in (getattr(route, "methods", None) or set())
        if path.startswith("/v1") and method.upper() in {"GET", "POST", "PATCH", "PUT", "DELETE"}
    }
    assert served == set(SERVED_OPERATIONS)
    assert len(served) == 34  # 2 legacy + 20 C1 + 5 core C2 + 7 DOC
    assert sum(1 for _method, path in served if "/documents" in path) == 7


def test_document_modules_import_no_ai_research_or_inference_runtime():
    # Static boundary: the Track 2 package never imports the AI bundle, the
    # offline research layer, or the inference provider/registry runtime.
    forbidden = re.compile(
        r"^\s*(?:from|import)\s+(?:backend\.app\.)?"
        r"(?:ai|research|inference|synthetic|calibration|panels)\b",
        re.MULTILINE,
    )
    offenders = []
    for path in PACKAGE.glob("*.py"):
        source = path.read_text(encoding="utf-8")
        if forbidden.search(source):
            offenders.append(path.name)
    assert offenders == []


def test_document_service_has_no_inference_dispatch_symbol():
    # AST-level: no inference/assessment-dispatch identifier is referenced in
    # code (docstring mentions of what the service does NOT do are ignored).
    import ast

    tree = ast.parse((PACKAGE / "service.py").read_text(encoding="utf-8"))
    identifiers = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            identifiers.add(node.id)
        elif isinstance(node, ast.Attribute):
            identifiers.add(node.attr)
    forbidden = {"build_active_provider", "dispatch_assessment", "submit_assessment",
                 "MockSyntheticProvider", "InferenceResult", "create_inference_result"}
    assert identifiers.isdisjoint(forbidden)


def test_confirmation_binds_no_assessment_and_dispatches_no_inference(client, patient, c2_app):
    token = patient["token"]
    data = (FIXTURES / "resting_text.pdf").read_bytes()
    up = client.post(
        "/v1/me/documents",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": f"up-{uuid.uuid4()}"},
        data={"contract_version": "v1", "document_kind": C.DOC_KIND_RESTING,
              "fixture_template_id": C.TEMPLATE_RESTING},
        files={"file": ("resting_text.pdf", data, "application/pdf")},
    )
    document_id = up.json()["document_id"]
    ext = client.post(f"/v1/me/documents/{document_id}/extract",
                      headers={"Authorization": f"Bearer {token}",
                               "Idempotency-Key": f"ex-{uuid.uuid4()}"}).json()
    confirm = client.post(
        f"/v1/me/documents/{document_id}/confirm",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": f"cf-{uuid.uuid4()}"},
        json={"contract_version": "v1", "extraction_id": ext["extraction_id"],
              "extraction_version": 1,
              "confirmed_inputs": {"age": 54, "sex": 1, "cp": 2, "trestbps": 130, "restecg": 0},
              "units": {"age": "years", "trestbps": "mmHg"}, "missing_reasons": {},
              "confirm_fabricated_demo_inputs": True},
    )
    assert confirm.status_code == 200
    # Patient confirmation is NOT assessment submission: no assessment_document
    # binding is created until S1 is explicitly submitted; no inference is dispatched.
    with read_transaction(c2_app.state.database) as session:
        bindings = session.execute(text("SELECT COUNT(*) FROM assessment_document")).scalar_one()
        assert bindings == 0


def test_worker_environment_excludes_ai_bundle_bindings():
    # The worker's fail-closed environment check refuses every AI bundle / key
    # binding, so the OCR process can never read private model material.
    from backend.app.term1_c2_documents.worker import WorkerStartupError, verify_sanitized_env
    for secret in ("CARDIOASSIST_LOCAL_BUNDLE_DIR", "CARDIOASSIST_LOCAL_TRUSTED_ROOT",
                   "CARDIOASSIST_LOCAL_HMAC_KEY_PATH"):
        with pytest.raises(WorkerStartupError):
            verify_sanitized_env({secret: "/private/ai"})


def test_backend_runtime_and_requirements_stay_free_of_ocr_and_ml_libraries():
    # Production backend requirements stay strictly free of OCR and ML/numerical
    # packages even though test-only requirements-dev.txt includes them.
    req_lines = [
        line.strip().lower()
        for line in (ROOT / "backend" / "requirements.txt").read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]
    forbidden_pins = (
        "pdfminer", "pypdfium2", "pillow", "pytesseract",
        "numpy", "scipy", "scikit-learn", "joblib", "torch", "onnxruntime",
    )
    for line in req_lines:
        pkg = re.split(r"[=<>!;\[ ]", line, maxsplit=1)[0]
        assert not any(pkg == f or pkg.startswith(f + ".") for f in forbidden_pins), line

    # Importing and building the production FastAPI app in a clean interpreter
    # must never load OCR worker modules, OCR libraries, or ML/research modules.
    probe = (
        "import sys; "
        "from backend.app.main import create_app; "
        "app = create_app(); "
        "forbidden = ("
        "'backend.app.term1_c2_documents.ocr_engine', "
        "'backend.app.term1_c2_documents.worker', "
        "'backend.app.term1_c2_documents.parser_process', "
        "'backend.app.artifact_admission', "
        "'pdfminer', 'pypdfium2', 'PIL', 'pytesseract', "
        "'numpy', 'scipy', 'sklearn', 'joblib', 'ai', 'research'"
        "); "
        "loaded = [m for m in sys.modules if any(m == f or m.startswith(f + '.') for f in forbidden)]; "
        "assert not loaded, f'Unexpected runtime imports: {loaded}'"
    )
    completed = subprocess.run(
        [sys.executable, "-c", probe], cwd=ROOT, capture_output=True, text=True, check=False
    )
    assert completed.returncode == 0, completed.stderr
