"""Semantic PDF admission inspection (worker/admission-side; pdfminer + pypdfium2).

Defence-in-depth structural and semantic screening of every admitted PDF:

* magic-byte verification (``%PDF-``), never the filename or Content-Type;
* refusal of encrypted / password-protected PDFs;
* genuine indirect-object & dictionary inspection (``/Catalog``, ``/Pages``,
  page trees, stream dictionaries and resolved references) rejecting active,
  scripted or embedded content: ``/JavaScript``, ``/JS``, ``/OpenAction``,
  ``/AA``, ``/Launch``, ``/RichMedia``, ``/EmbeddedFile``, ``/XFA``,
  ``/SubmitForm``, ``/URI`` and related action subtypes;
* bounded object count (<= 5000) and decompressed stream size (<= 32 MiB);
* bounded page count (<= 3) via pypdfium2.

This module never executes document content. It is only reached after the exact
file SHA-256 allowlist check, so it is a second, independent gate.
"""

from __future__ import annotations

import io
from dataclasses import dataclass

import pypdfium2 as pdfium
from pdfminer.pdfdocument import PDFDocument
from pdfminer.pdfparser import PDFParser
from pdfminer.pdftypes import PDFStream, PDFObjRef
from pdfminer.psparser import PSLiteral

from . import constants as C


class PdfRejectedError(RuntimeError):
    """A PDF failed admission. ``code`` is the closed API error code."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class PdfInfo:
    page_count: int
    object_count: int
    decompressed_bytes: int


# Forbidden dictionary keys / action subtypes (active, scripted, embedded).
_FORBIDDEN_NAMES: frozenset[str] = frozenset(
    {
        "JavaScript", "JS", "OpenAction", "AA", "Launch", "RichMedia",
        "EmbeddedFile", "EmbeddedFiles", "XFA", "SubmitForm", "URI",
        "GoToR", "GoToE", "ImportData", "ResetForm", "Hide", "Named",
        "Movie", "Sound", "Trans", "SetOCGState", "RichMediaExecute",
    }
)
# Byte tokens scanned inside decoded streams (object streams may hide objects).
_FORBIDDEN_TOKENS: tuple[bytes, ...] = tuple(
    b"/" + name.encode("ascii") for name in _FORBIDDEN_NAMES
)


def _name_of(key: object) -> str:
    if isinstance(key, PSLiteral):
        name = key.name
        return name.decode("latin-1") if isinstance(name, bytes) else str(name)
    return str(key)


def has_pdf_magic(data: bytes) -> bool:
    # The header may be preceded by a short junk prefix; search the first 1024.
    return data[:1024].find(b"%PDF-") >= 0


def inspect_pdf(data: bytes) -> PdfInfo:
    """Screen a PDF; raise :class:`PdfRejectedError` on any violation."""
    if not has_pdf_magic(data):
        raise PdfRejectedError("invalid_document_content")

    # Page count via the robust pdfium parser (also rejects malformed files).
    try:
        pdf = pdfium.PdfDocument(io.BytesIO(data))
    except Exception as error:  # noqa: BLE001
        raise PdfRejectedError("invalid_document_content") from error
    try:
        page_count = len(pdf)
    finally:
        pdf.close()
    if page_count < 1 or page_count > C.MAX_PDF_PAGES:
        raise PdfRejectedError("invalid_document_content")

    # Semantic object-graph inspection via pdfminer.
    try:
        document = PDFDocument(PDFParser(io.BytesIO(data)))
    except Exception as error:  # noqa: BLE001
        raise PdfRejectedError("invalid_document_content") from error

    # Encrypted / password-protected PDFs are refused.
    try:
        if not document.is_extractable:
            raise PdfRejectedError("active_pdf_content_rejected")
    except PdfRejectedError:
        raise
    except Exception as error:  # noqa: BLE001
        raise PdfRejectedError("active_pdf_content_rejected") from error
    for xref in document.xrefs:
        trailer = xref.trailer or {}
        if "Encrypt" in {_name_of(k) for k in trailer}:
            raise PdfRejectedError("active_pdf_content_rejected")

    objids: set[int] = set()
    for xref in document.xrefs:
        try:
            objids.update(int(oid) for oid in xref.get_objids())
        except Exception:  # noqa: BLE001
            continue
    if len(objids) > C.PDF_MAX_OBJECTS:
        raise PdfRejectedError("invalid_document_content")

    state = {"decompressed": 0, "visited": set()}

    def walk(obj: object, depth: int = 0) -> None:
        if depth > 64:
            raise PdfRejectedError("invalid_document_content")
        if isinstance(obj, PDFObjRef):
            if obj.objid in state["visited"]:
                return
            state["visited"].add(obj.objid)
            try:
                resolved = obj.resolve()
            except Exception:  # noqa: BLE001
                return
            walk(resolved, depth + 1)
            return
        if isinstance(obj, dict):
            for key, value in obj.items():
                if _name_of(key) in _FORBIDDEN_NAMES:
                    raise PdfRejectedError("active_pdf_content_rejected")
                walk(value, depth + 1)
            return
        if isinstance(obj, (list, tuple)):
            for item in obj:
                walk(item, depth + 1)
            return
        if isinstance(obj, PDFStream):
            for key, value in obj.attrs.items():
                if _name_of(key) in _FORBIDDEN_NAMES:
                    raise PdfRejectedError("active_pdf_content_rejected")
                walk(value, depth + 1)
            try:
                decoded = obj.get_data()
            except Exception:  # noqa: BLE001
                decoded = b""
            state["decompressed"] += len(decoded)
            if state["decompressed"] > C.PDF_MAX_DECOMPRESSED_BYTES:
                raise PdfRejectedError("invalid_document_content")
            for token in _FORBIDDEN_TOKENS:
                if token in decoded:
                    raise PdfRejectedError("active_pdf_content_rejected")
            return
        # Scalars (int, float, bytes, PSLiteral, bool, None) carry no actions.

    for oid in sorted(objids):
        try:
            obj = document.getobj(oid)
        except Exception:  # noqa: BLE001
            continue
        walk(obj)

    return PdfInfo(
        page_count=page_count, object_count=len(objids),
        decompressed_bytes=state["decompressed"],
    )
