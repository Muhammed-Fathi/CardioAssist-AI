"""Track 2 operator settings (environment only; never committed).

``CARDIOASSIST_PRIVATE_DOC_DIR``   private blob root outside Git/web roots.
``CARDIOASSIST_OCR_WORKER_URL``    loopback OCR worker base URL.
``CARDIOASSIST_OCR_IPC_TOKEN``     CSPRNG bearer token shared with the worker.

The private document root must be absolute and must not be inside the repository
working tree or a public web root. When unset, the document surface fails closed
per request (the legacy and C1 routes keep working).
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

ENV_PRIVATE_DOC_DIR = "CARDIOASSIST_PRIVATE_DOC_DIR"
ENV_OCR_WORKER_URL = "CARDIOASSIST_OCR_WORKER_URL"
ENV_OCR_IPC_TOKEN = "CARDIOASSIST_OCR_IPC_TOKEN"


class DocumentSettingsError(RuntimeError):
    """Document/OCR operator configuration is absent or unusable."""


@dataclass(frozen=True)
class DocumentSettings:
    private_doc_dir: Path
    ocr_worker_url: str
    ocr_ipc_token: str

    def __post_init__(self) -> None:
        if not self.private_doc_dir.is_absolute():
            raise DocumentSettingsError("Private document root must be absolute.")
        if not self.ocr_worker_url.startswith("http://127.0.0.1"):
            raise DocumentSettingsError("OCR worker URL must be loopback-only.")
        if len(self.ocr_ipc_token) < 32:
            raise DocumentSettingsError("OCR IPC token must be >= 32 characters.")


def load_document_settings(environ: dict[str, str] | None = None) -> DocumentSettings:
    source = os.environ if environ is None else environ
    doc_dir = (source.get(ENV_PRIVATE_DOC_DIR) or "").strip()
    worker_url = (source.get(ENV_OCR_WORKER_URL) or "").strip()
    token = (source.get(ENV_OCR_IPC_TOKEN) or "").strip()
    if not doc_dir or not worker_url or not token:
        raise DocumentSettingsError(
            "Document/OCR operator configuration is incomplete."
        )
    return DocumentSettings(
        private_doc_dir=Path(doc_dir), ocr_worker_url=worker_url, ocr_ipc_token=token
    )
