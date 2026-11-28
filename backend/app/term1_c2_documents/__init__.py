"""Term 1 C2 — Track 2 bounded document intake and genuine local OCR.

This package is the isolated Track 2 contributor workstream of the authorized
``C2_SAFE_SCOPE`` (owner grant ``AUTHORIZE-TERM1-C2-SAFE-SCOPE-V1``, PR #147
comment 7232372420). It owns additive migration ``20261128_08`` and the bounded
document/OCR operations ``DOC1``–``DOC7`` only.

Hard boundaries (see ``docs/term1/TERM1_C2_TRACK2_DOCUMENTS_OCR_IMPLEMENTATION_20261128.md``):

* No OCR-derived model inference. ``EXC-TERM1-OCR-DEMO-V1`` and ``A3`` remain
  PENDING; this package never dispatches an assessment, never writes an
  ``inference_result`` row, never reads a private AI bundle or signing key, and
  never falls back to a mock provider.
* Patient confirmation of a fabricated demo extraction is **not** clinician
  verification and is **not** an assessment submission.
* Only project-generated, visibly watermarked, SHA-allowlisted fabricated demo
  reports are admitted. No arbitrary patient documents or real medical records.
* Track 1 owns shared application registration, core model registration and
  global error/OpenAPI composition. This package supplies additive modules and
  an explicit integration handoff; it does not edit those shared files.

The OCR runtime dependencies (``pdfminer.six``, ``pypdfium2``, ``Pillow``,
``pytesseract`` + the native Tesseract binary) live only in the isolated
``.venv-ocr-worker`` environment and the separate unprivileged OCR worker OS
account. ``backend/requirements.txt`` stays free of ML/OCR libraries.
"""

from __future__ import annotations

__all__ = ["__version__"]

__version__ = "0.1.0"
