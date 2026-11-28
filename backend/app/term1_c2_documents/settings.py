"""Track 2 operator settings (environment only; never committed).

``CARDIOASSIST_PRIVATE_DOC_DIR``   private blob root outside Git/web/AI roots.
``CARDIOASSIST_OCR_WORKER_URL``    loopback OCR worker base URL (exact origin).
``CARDIOASSIST_OCR_IPC_TOKEN``     CSPRNG bearer token shared with the worker.

Corrections (T2-R3):

* the worker URL is validated by *parsing* it, not a string prefix: the scheme
  must be ``http``, the host must be a literal loopback address (``127.0.0.1``
  or ``::1`` — ``localhost`` is rejected because it can resolve elsewhere), an
  explicit port in ``1..65535`` is required, and credentials, a non-root path,
  a query or a fragment are all refused. The normalized origin is what the
  client dials, so a non-loopback hostname can never slip through;
* the private document root must be absolute and must lie OUTSIDE the repository
  working tree (both directions) and outside any configured AI bundle / web root;
* the IPC token must be >= 32 characters and free of whitespace/control
  characters (no header injection).

When unset, the document surface fails closed per request (the legacy and C1
routes keep working).
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

ENV_PRIVATE_DOC_DIR = "CARDIOASSIST_PRIVATE_DOC_DIR"
ENV_OCR_WORKER_URL = "CARDIOASSIST_OCR_WORKER_URL"
ENV_OCR_IPC_TOKEN = "CARDIOASSIST_OCR_IPC_TOKEN"
ENV_AI_BUNDLE_DIR = "CARDIOASSIST_LOCAL_BUNDLE_DIR"
ENV_WEB_ROOT = "CARDIOASSIST_WEB_ROOT"

# Repository working tree root (backend/app/term1_c2_documents/settings.py).
_REPO_ROOT = Path(__file__).resolve().parents[3]
_LOOPBACK_HOSTS = frozenset({"127.0.0.1", "::1"})


class DocumentSettingsError(RuntimeError):
    """Document/OCR operator configuration is absent or unusable."""


def validate_worker_origin(url: str) -> str:
    """Return the normalized loopback origin or raise; never trust a prefix."""
    try:
        parts = urlsplit(url)
    except ValueError as error:
        raise DocumentSettingsError("OCR worker URL is not parseable.") from error
    if parts.scheme != "http":
        raise DocumentSettingsError("OCR worker URL must use http on loopback.")
    if parts.username is not None or parts.password is not None:
        raise DocumentSettingsError("OCR worker URL must not embed credentials.")
    host = parts.hostname
    if host not in _LOOPBACK_HOSTS:
        raise DocumentSettingsError("OCR worker host must be a literal loopback address.")
    try:
        port = parts.port
    except ValueError as error:
        raise DocumentSettingsError("OCR worker port is invalid.") from error
    if port is None or not (1 <= port <= 65535):
        raise DocumentSettingsError("OCR worker URL must specify an explicit valid port.")
    if parts.path not in ("", "/"):
        raise DocumentSettingsError("OCR worker URL must not carry a path.")
    if parts.query or parts.fragment:
        raise DocumentSettingsError("OCR worker URL must not carry a query or fragment.")
    bracketed = f"[{host}]" if ":" in host else host
    return f"http://{bracketed}:{port}"


def _is_within(child: Path, parent: Path) -> bool:
    return child == parent or parent in child.parents


def _validate_doc_root(doc_dir: Path, environ: dict[str, str]) -> None:
    resolved = doc_dir.resolve()
    if _is_within(resolved, _REPO_ROOT) or _is_within(_REPO_ROOT, resolved):
        raise DocumentSettingsError(
            "Private document root must be outside the repository working tree."
        )
    for env_name in (ENV_AI_BUNDLE_DIR, ENV_WEB_ROOT):
        value = (environ.get(env_name) or "").strip()
        if not value:
            continue
        other = Path(value).resolve()
        if _is_within(resolved, other) or _is_within(other, resolved):
            raise DocumentSettingsError(
                "Private document root must be disjoint from AI bundle / web roots."
            )


@dataclass(frozen=True)
class DocumentSettings:
    private_doc_dir: Path
    ocr_worker_url: str
    ocr_ipc_token: str

    def __post_init__(self) -> None:
        if not self.private_doc_dir.is_absolute():
            raise DocumentSettingsError("Private document root must be absolute.")
        # Normalize/validate the origin; store the canonical form.
        object.__setattr__(self, "ocr_worker_url", validate_worker_origin(self.ocr_worker_url))
        token = self.ocr_ipc_token
        if len(token) < 32:
            raise DocumentSettingsError("OCR IPC token must be >= 32 characters.")
        if any(ch.isspace() or ord(ch) < 0x20 or ord(ch) == 0x7F for ch in token):
            raise DocumentSettingsError("OCR IPC token must not contain whitespace/control chars.")


def load_document_settings(environ: dict[str, str] | None = None) -> DocumentSettings:
    source = os.environ if environ is None else environ
    doc_dir = (source.get(ENV_PRIVATE_DOC_DIR) or "").strip()
    worker_url = (source.get(ENV_OCR_WORKER_URL) or "").strip()
    token = (source.get(ENV_OCR_IPC_TOKEN) or "").strip()
    if not doc_dir or not worker_url or not token:
        raise DocumentSettingsError(
            "Document/OCR operator configuration is incomplete."
        )
    path = Path(doc_dir)
    _validate_doc_root(path, source)
    return DocumentSettings(
        private_doc_dir=path, ocr_worker_url=worker_url, ocr_ipc_token=token
    )
