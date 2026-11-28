"""Deterministic generator for the project-authored fabricated demo reports.

This module produces the *only* documents the bounded intake will ever admit:
visibly watermarked, fixed-template English educational fixtures. It never
reads, downloads or bundles any real medical record or patient data.

Variants per template:

* ``*_text.pdf``   — a genuine text-layer PDF (hand-written, stdlib only) that
  ``pdfminer.six`` extracts without OCR;
* ``*_raster.pdf`` — a scanned-style PDF whose single page is a JPEG image with
  **no text layer**, so extraction must rasterize (``pypdfium2``) and run real
  Tesseract OCR;
* ``*.png`` / ``*.jpg`` — raster image variants for genuine PNG/JPEG OCR.

Determinism: the PDF writer emits no timestamps or random IDs; raster rendering
uses pinned Pillow + the bundled DejaVu fonts at a fixed layout. The committed
fixture bytes are the allowlist; regeneration under the pinned environment must
reproduce them byte-for-byte (verified by ``tests/.../test_fixture_manifest.py``).
Cross-platform raster byte identity is **not** assumed — a differing digest is a
blocked verification result requiring manifest review, never a silent relaxation.

Run (in ``.venv-ocr-worker``)::

    python -m backend.app.term1_c2_documents.fixture_generation --write
"""

from __future__ import annotations

import argparse
import hashlib
import io
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from . import constants as C

FIXTURE_DIR: Final[Path] = Path(__file__).resolve().parent / "fixtures"

# A4 at 200 DPI for raster variants (matches the OCR rasterization DPI).
PAGE_W_PX: Final = 1654
PAGE_H_PX: Final = 2339
# A4 in PDF points for text-layer / raster PDF pages.
PAGE_W_PT: Final = 595
PAGE_H_PT: Final = 842

_FONT_DIR = Path("/usr/share/fonts/truetype/dejavu")


@dataclass(frozen=True)
class FixtureSpec:
    filename: str
    template_id: str
    document_kind: str
    media_type: str
    data: bytes
    page_count: int
    pixel_width: int | None
    pixel_height: int | None


# ---------------------------------------------------------------------------
# Canonical report content
# ---------------------------------------------------------------------------

def _resting_lines(
    *,
    age: str = "54 years",
    sex: str = "1 (Male)",
    cp: str = "2 (Atypical Angina)",
    trestbps: str = "130 mmHg",
    restecg: str = "0 (Normal)",
    extra_age: str | None = None,
) -> list[tuple[str, str]]:
    lines: list[tuple[str, str]] = [
        (C.DEMO_WATERMARK, "title"),
        ("CardioAssist AI - Educational Demonstration", "header"),
        ("", "body"),
        (f"Template ID: {C.TEMPLATE_RESTING}", "body"),
        ("Report Label: DEMO-RESTING-001", "body"),
        ("Patient Label: DEMO-ID-001 (fabricated)", "body"),
        ("--------------------------------------------------", "body"),
        (f"Age: {age}", "field"),
        (f"Sex: {sex}", "field"),
        (f"Chest Pain Category (cp): {cp}", "field"),
        (f"Resting Systolic BP (trestbps): {trestbps}", "field"),
        (f"Resting ECG Classification (restecg): {restecg}", "field"),
    ]
    if extra_age is not None:
        lines.append((f"Age: {extra_age}", "field"))
    lines += [
        ("--------------------------------------------------", "body"),
        ("Category codes (reference only):", "small"),
        ("sex 0=Female 1=Male", "small"),
        ("cp 1=Typical Angina 2=Atypical Angina", "small"),
        ("3=Non-Anginal Pain 4=Asymptomatic", "small"),
        ("restecg 0=Normal 1=ST-T Abnormality", "small"),
        ("2=Left Ventricular Hypertrophy", "small"),
        ("Fabricated educational fixture. Not a real patient record.", "small"),
    ]
    return lines


def _labs_lines() -> list[tuple[str, str]]:
    return [
        (C.DEMO_WATERMARK, "title"),
        ("CardioAssist AI - Educational Demonstration", "header"),
        ("", "body"),
        (f"Template ID: {C.TEMPLATE_LABS}", "body"),
        ("Report Label: DEMO-LABS-001", "body"),
        ("Patient Label: DEMO-ID-001 (fabricated)", "body"),
        ("--------------------------------------------------", "body"),
        ("Total Cholesterol: 210 mg/dL", "field"),
        ("Fasting Blood Sugar: 95 mg/dL", "field"),
        ("LDL Cholesterol: 130 mg/dL", "field"),
        ("HDL Cholesterol: 45 mg/dL", "field"),
        ("Triglycerides: 150 mg/dL", "field"),
        ("Creatinine: 0.9 mg/dL", "field"),
        ("Hemoglobin: 14.2 g/dL", "field"),
        ("White Blood Cells (WBC): 6.8 x10^9/L", "field"),
        ("--------------------------------------------------", "body"),
        ("These laboratory values are record-only attachments.", "small"),
        ("They are NOT model inputs and must never enter the", "small"),
        ("five-field resting assessment.", "small"),
        ("Fabricated educational fixture. Not a real patient record.", "small"),
    ]


# ---------------------------------------------------------------------------
# Minimal deterministic PDF writer (stdlib only)
# ---------------------------------------------------------------------------

def _pdf_escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _build_pdf(objects: list[bytes], root_ref: int = 1) -> bytes:
    """Assemble a PDF 1.4 file from numbered object bodies (1-based)."""
    out = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets: list[int] = []
    for index, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{index} 0 obj\n".encode("ascii")
        out += body
        out += b"\nendobj\n"
    xref_pos = len(out)
    count = len(objects) + 1
    out += f"xref\n0 {count}\n".encode("ascii")
    out += b"0000000000 65535 f \n"
    for offset in offsets:
        out += f"{offset:010d} 00000 n \n".encode("ascii")
    out += (
        f"trailer\n<< /Size {count} /Root {root_ref} 0 R >>\n"
        f"startxref\n{xref_pos}\n%%EOF\n"
    ).encode("ascii")
    return bytes(out)


def _text_pdf(lines: list[tuple[str, str]]) -> bytes:
    """A genuine text-layer PDF using base-14 Helvetica fonts."""
    style_font = {"title": ("/F2", 15), "header": ("/F2", 12), "field": ("/F1", 12),
                  "body": ("/F1", 11), "small": ("/F1", 9)}
    content = bytearray()
    y = PAGE_H_PT - 60
    for text, style in lines:
        font, size = style_font[style]
        if text:
            content += f"BT {font} {size} Tf 1 0 0 1 56 {y} Tm ({_pdf_escape(text)}) Tj ET\n".encode("latin-1")
        y -= size + 8 if style != "small" else size + 5
    stream = bytes(content)
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {PAGE_W_PT} {PAGE_H_PT}] "
            f"/Resources << /Font << /F1 4 0 R /F2 5 0 R >> >> /Contents 6 0 R >>"
        ).encode("ascii"),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >>",
        f"<< /Length {len(stream)} >>\nstream\n".encode("ascii") + stream + b"\nendstream",
    ]
    return _build_pdf(objects)


def _raster_pdf(jpeg_bytes: bytes, width_px: int, height_px: int) -> bytes:
    """A scanned-style PDF: one page whose only content is a JPEG XObject."""
    content = f"q {PAGE_W_PT} 0 0 {PAGE_H_PT} 0 0 cm /Im0 Do Q\n".encode("ascii")
    image_obj = (
        f"<< /Type /XObject /Subtype /Image /Width {width_px} /Height {height_px} "
        f"/ColorSpace /DeviceRGB /BitsPerComponent 8 /Filter /DCTDecode "
        f"/Length {len(jpeg_bytes)} >>\nstream\n"
    ).encode("ascii") + jpeg_bytes + b"\nendstream"
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {PAGE_W_PT} {PAGE_H_PT}] "
            f"/Resources << /XObject << /Im0 7 0 R >> >> /Contents 6 0 R >>"
        ).encode("ascii"),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >>",
        f"<< /Length {len(content)} >>\nstream\n".encode("ascii") + content + b"\nendstream",
        image_obj,
    ]
    return _build_pdf(objects)


# ---------------------------------------------------------------------------
# Raster rendering (Pillow, pinned)
# ---------------------------------------------------------------------------

def _render_image(lines: list[tuple[str, str]]) -> "object":
    from PIL import Image, ImageDraw, ImageFont

    img = Image.new("RGB", (PAGE_W_PX, PAGE_H_PX), "white")
    draw = ImageDraw.Draw(img)
    regular = _load_font("DejaVuSans.ttf")
    bold = _load_font("DejaVuSans-Bold.ttf")
    style_size = {"title": 40, "header": 32, "field": 32, "body": 28, "small": 24}
    y = 110
    for text, style in lines:
        size = style_size[style]
        font = bold if style in ("title", "header") else regular
        sized = ImageFont.truetype(str(font), size) if isinstance(font, Path) else font
        if text:
            draw.text((110, y), text, font=sized, fill="black")
        y += size + (22 if style != "small" else 14)
    return img


def _load_font(name: str) -> Path:
    candidate = _FONT_DIR / name
    if candidate.exists():
        return candidate
    # Fallback search for non-Debian owner-local environments.
    for root in ("/usr/share/fonts", "C:/Windows/Fonts"):
        found = list(Path(root).rglob(name)) if Path(root).exists() else []
        if found:
            return found[0]
    raise FileNotFoundError(f"Font {name} not found; install DejaVu or set a font path.")


def _png_bytes(img: "object") -> bytes:
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=False)
    return buf.getvalue()


def _jpeg_bytes(img: "object") -> bytes:
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=95, optimize=False, progressive=False)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Fixture set + manifest
# ---------------------------------------------------------------------------

def generate_fixtures() -> list[FixtureSpec]:
    """Generate the full authored fixture set deterministically."""
    specs: list[FixtureSpec] = []

    def add(filename: str, template: str, media: str, data: bytes,
            pages: int, w: int | None, h: int | None) -> None:
        specs.append(FixtureSpec(filename, template, C.TEMPLATE_TO_KIND[template],
                                 media, data, pages, w, h))

    resting = _resting_lines()
    resting_missing = _resting_lines(restecg="NOT_MEASURED")
    resting_conflict = _resting_lines(extra_age="61 years")
    labs = _labs_lines()

    # Text-layer PDFs (genuine pdfminer.six extraction, no OCR).
    add("resting_text.pdf", C.TEMPLATE_RESTING, C.MEDIA_PDF, _text_pdf(resting), 1, None, None)
    add("resting_missing_text.pdf", C.TEMPLATE_RESTING, C.MEDIA_PDF, _text_pdf(resting_missing), 1, None, None)
    add("resting_conflict_text.pdf", C.TEMPLATE_RESTING, C.MEDIA_PDF, _text_pdf(resting_conflict), 1, None, None)
    add("labs_text.pdf", C.TEMPLATE_LABS, C.MEDIA_PDF, _text_pdf(labs), 1, None, None)

    # Raster images + scanned PDFs (genuine Tesseract OCR).
    for stem, lines, template in (
        ("resting", resting, C.TEMPLATE_RESTING),
        ("labs", labs, C.TEMPLATE_LABS),
    ):
        img = _render_image(lines)
        png = _png_bytes(img)
        jpeg = _jpeg_bytes(img)
        add(f"{stem}.png", template, C.MEDIA_PNG, png, 1, PAGE_W_PX, PAGE_H_PX)
        add(f"{stem}.jpg", template, C.MEDIA_JPEG, jpeg, 1, PAGE_W_PX, PAGE_H_PX)
        add(f"{stem}_raster.pdf", template, C.MEDIA_PDF, _raster_pdf(jpeg, PAGE_W_PX, PAGE_H_PX), 1, None, None)

    return specs


def build_manifest(specs: list[FixtureSpec]) -> dict:
    """Server-owned exact file SHA-256 allowlist manifest.

    The manifest maps ``sha256 -> (template_id, document_kind, media_type)`` plus
    structural metadata. It deliberately contains **no expected field values**:
    admission trusts only the digest, and extraction must genuinely parse the
    document. Expected values live in tests, never in the admission allowlist.
    """
    entries = []
    for spec in specs:
        entries.append(
            {
                "sha256": hashlib.sha256(spec.data).hexdigest(),
                "filename": spec.filename,
                "template_id": spec.template_id,
                "document_kind": spec.document_kind,
                "media_type": spec.media_type,
                "byte_size": len(spec.data),
                "page_count": spec.page_count,
                "pixel_width": spec.pixel_width,
                "pixel_height": spec.pixel_height,
            }
        )
    entries.sort(key=lambda e: e["sha256"])
    return {
        "manifest_version": "cardioassist.demo_fixture_manifest/v1",
        "generator": "backend.app.term1_c2_documents.fixture_generation",
        "generator_version": C.DOCUMENT_SCHEMA_VERSION,
        "watermark": C.DEMO_WATERMARK,
        "note": (
            "Project-generated fabricated educational fixtures only. No real "
            "patient records. Admission is by exact file SHA-256; expected field "
            "values are intentionally absent so OCR is never hardcoded autofill."
        ),
        "files": entries,
    }


def write_fixtures(directory: Path = FIXTURE_DIR) -> dict:
    import json

    directory.mkdir(parents=True, exist_ok=True)
    specs = generate_fixtures()
    for spec in specs:
        (directory / spec.filename).write_bytes(spec.data)
    manifest = build_manifest(specs)
    (directory / "fixture_manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="Write fixtures + manifest to disk.")
    parser.add_argument("--dir", type=Path, default=FIXTURE_DIR)
    args = parser.parse_args()
    if args.write:
        manifest = write_fixtures(args.dir)
        print(f"Wrote {len(manifest['files'])} fixtures to {args.dir}")
        for entry in manifest["files"]:
            print(f"  {entry['sha256']}  {entry['filename']}")
    else:
        specs = generate_fixtures()
        for spec in specs:
            print(f"{hashlib.sha256(spec.data).hexdigest()}  {spec.filename}  {len(spec.data)} bytes")


if __name__ == "__main__":
    main()
