"""Safe, read-only .xlsx workbook reader with both openpyxl and stdlib OOXML support."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence
import xml.etree.ElementTree as ET
from xml.sax.saxutils import escape as xml_escape
import zipfile

from research.audit.exceptions import FormatValidationError

MAX_XLSX_UNCOMPRESSED_BYTES = 64 * 1024 * 1024  # 64 MiB zip-bomb guard
MAIN_NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
REL_NS = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
PKG_REL_NS = "{http://schemas.openxmlformats.org/package/2006/relationships}"


@dataclass(frozen=True)
class SheetData:
    """In-memory representation of a single worksheet (never printed or logged)."""

    name: str
    headers: tuple[str, ...]
    rows: tuple[tuple[Any, ...], ...]


@dataclass(frozen=True)
class WorkbookData:
    """In-memory representation of an inspected .xlsx workbook."""

    sheet_names: tuple[str, ...]
    sheets: dict[str, SheetData]


def _guard_xml_bytes(raw_xml: bytes, member_name: str) -> ET.Element:
    head = raw_xml[:4096].upper()
    if b"<!DOCTYPE" in head or b"<!ENTITY" in head:
        raise FormatValidationError(
            f"Rejected unsafe XML DTD/ENTITY declaration in '{member_name}'."
        )
    try:
        return ET.fromstring(raw_xml)
    except ET.ParseError as exc:
        raise FormatValidationError(f"Corrupt XML in '{member_name}': {exc}") from exc


def _col_letters_to_index(cell_ref: str) -> int:
    letters = "".join(ch for ch in cell_ref if ch.isalpha()).upper()
    if not letters:
        return 0
    idx = 0
    for ch in letters:
        idx = idx * 26 + (ord(ch) - ord("A") + 1)
    return idx - 1


def _parse_numeric_or_str(text: str | None) -> Any:
    if text is None:
        return None
    stripped = text.strip()
    if stripped == "":
        return None
    try:
        as_float = float(stripped)
        if as_float.is_integer() and "." not in stripped and "e" not in stripped.lower():
            return int(stripped)
        return int(as_float) if as_float.is_integer() else as_float
    except ValueError:
        return stripped


def read_xlsx_stdlib(path: Path) -> WorkbookData:
    """Read an .xlsx file using Python's standard library (zipfile + ElementTree) in read-only mode."""
    if not path.exists() or not path.is_file():
        raise FormatValidationError(f"Workbook file not found: '{path}'")
    if path.suffix.lower() != ".xlsx":
        raise FormatValidationError(f"Expected '.xlsx' file extension, got '{path.name}'.")
    if not zipfile.is_zipfile(path):
        raise FormatValidationError(f"Corrupt or non-ZIP .xlsx workbook: '{path.name}'.")

    with zipfile.ZipFile(path, "r") as zf:
        total_uncompressed = sum(info.file_size for info in zf.infolist())
        if total_uncompressed > MAX_XLSX_UNCOMPRESSED_BYTES:
            raise FormatValidationError(
                f"Workbook '{path.name}' exceeds maximum uncompressed size limit ({MAX_XLSX_UNCOMPRESSED_BYTES} bytes)."
            )
        names = set(zf.namelist())
        if "xl/workbook.xml" not in names:
            raise FormatValidationError(f"Corrupt .xlsx file '{path.name}': missing 'xl/workbook.xml'.")

        shared_strings: list[str] = []
        if "xl/sharedStrings.xml" in names:
            sst_root = _guard_xml_bytes(zf.read("xl/sharedStrings.xml"), "xl/sharedStrings.xml")
            for si in sst_root.findall(f"{MAIN_NS}si"):
                parts = [t.text or "" for t in si.iter(f"{MAIN_NS}t")]
                shared_strings.append("".join(parts))

        rels_map: dict[str, str] = {}
        if "xl/_rels/workbook.xml.rels" in names:
            rels_root = _guard_xml_bytes(zf.read("xl/_rels/workbook.xml.rels"), "xl/_rels/workbook.xml.rels")
            for rel in rels_root.findall(f"{PKG_REL_NS}Relationship"):
                r_id = rel.attrib.get("Id", "")
                target = rel.attrib.get("Target", "").lstrip("/")
                if not target.startswith("xl/"):
                    target = f"xl/{target}"
                rels_map[r_id] = target

        wb_root = _guard_xml_bytes(zf.read("xl/workbook.xml"), "xl/workbook.xml")
        sheets_elem = wb_root.find(f"{MAIN_NS}sheets")
        if sheets_elem is None:
            raise FormatValidationError(f"Workbook '{path.name}' contains no <sheets> element.")

        sheet_entries: list[tuple[str, str]] = []
        for idx, sh in enumerate(sheets_elem.findall(f"{MAIN_NS}sheet"), start=1):
            sh_name = sh.attrib.get("name", f"Sheet{idx}")
            r_id = sh.attrib.get(f"{REL_NS}id", "")
            target_path = rels_map.get(r_id, f"xl/worksheets/sheet{idx}.xml")
            sheet_entries.append((sh_name, target_path))

        if not sheet_entries:
            raise FormatValidationError(f"Workbook '{path.name}' has zero worksheets.")

        parsed_sheets: dict[str, SheetData] = {}
        sheet_names: list[str] = []

        for sh_name, target_path in sheet_entries:
            if target_path not in names:
                raise FormatValidationError(
                    f"Workbook '{path.name}' references missing worksheet XML '{target_path}'."
                )
            ws_root = _guard_xml_bytes(zf.read(target_path), target_path)
            sheet_data_elem = ws_root.find(f"{MAIN_NS}sheetData")
            if sheet_data_elem is None:
                raise FormatValidationError(
                    f"Worksheet '{sh_name}' in '{path.name}' is missing <sheetData>."
                )

            raw_rows: list[list[Any]] = []
            max_cols = 0
            for row_elem in sheet_data_elem.findall(f"{MAIN_NS}row"):
                cells_by_col: dict[int, Any] = {}
                next_col = 0
                for c_elem in row_elem.findall(f"{MAIN_NS}c"):
                    ref = c_elem.attrib.get("r", "")
                    col_idx = _col_letters_to_index(ref) if ref else next_col
                    next_col = col_idx + 1
                    c_type = c_elem.attrib.get("t", "n")
                    v_elem = c_elem.find(f"{MAIN_NS}v")
                    is_elem = c_elem.find(f"{MAIN_NS}is")
                    val: Any = None
                    if c_type == "s":
                        if v_elem is not None and v_elem.text is not None:
                            try:
                                s_idx = int(v_elem.text.strip())
                                val = shared_strings[s_idx]
                            except (ValueError, IndexError) as exc:
                                raise FormatValidationError(
                                    f"Invalid sharedString index in worksheet '{sh_name}'."
                                ) from exc
                    elif c_type == "inlineStr":
                        if is_elem is not None:
                            val = "".join(t.text or "" for t in is_elem.iter(f"{MAIN_NS}t"))
                    elif c_type == "b":
                        if v_elem is not None and v_elem.text is not None:
                            val = 1 if v_elem.text.strip() in ("1", "true", "TRUE") else 0
                    elif c_type == "str":
                        val = v_elem.text if v_elem is not None else None
                    else:
                        val = _parse_numeric_or_str(v_elem.text if v_elem is not None else None)
                    cells_by_col[col_idx] = val

                if cells_by_col:
                    row_width = max(cells_by_col.keys()) + 1
                    max_cols = max(max_cols, row_width)
                    row_list = [cells_by_col.get(i, None) for i in range(row_width)]
                    raw_rows.append(row_list)

            if not raw_rows:
                parsed_sheets[sh_name] = SheetData(name=sh_name, headers=(), rows=())
                sheet_names.append(sh_name)
                continue

            header_raw = raw_rows[0]
            headers: list[str] = []
            for h_idx, h_val in enumerate(header_raw):
                if h_val is None or str(h_val).strip() == "":
                    raise FormatValidationError(
                        f"Worksheet '{sh_name}' in '{path.name}' has an empty header at column {h_idx + 1}."
                    )
                headers.append(str(h_val).strip())

            num_headers = len(headers)
            data_rows: list[tuple[Any, ...]] = []
            for r_idx, r_vals in enumerate(raw_rows[1:], start=2):
                if len(r_vals) > num_headers:
                    extra = r_vals[num_headers:]
                    if any(v is not None and str(v).strip() != "" for v in extra):
                        raise FormatValidationError(
                            f"Worksheet '{sh_name}' row {r_idx} has values beyond the {num_headers} header columns."
                        )
                padded = tuple(
                    r_vals[c_i] if c_i < len(r_vals) else None for c_i in range(num_headers)
                )
                if all(v is None or (isinstance(v, str) and v.strip() == "") for v in padded):
                    continue
                data_rows.append(padded)

            parsed_sheets[sh_name] = SheetData(
                name=sh_name,
                headers=tuple(headers),
                rows=tuple(data_rows),
            )
            sheet_names.append(sh_name)

        return WorkbookData(sheet_names=tuple(sheet_names), sheets=parsed_sheets)


def read_xlsx_workbook(path: Path, *, prefer_openpyxl: bool = True) -> WorkbookData:
    """Read an .xlsx workbook in read-only mode, validating structural integrity first."""
    # Always run stdlib structural/XXE/zip-bomb/header check first so corrupt files fail closed deterministically
    stdlib_wb = read_xlsx_stdlib(path)
    if not prefer_openpyxl:
        return stdlib_wb

    try:
        import openpyxl  # type: ignore[import-untyped]
    except ImportError:
        return stdlib_wb

    try:
        wb = openpyxl.load_workbook(filename=str(path), read_only=True, data_only=True)
    except Exception as exc:
        raise FormatValidationError(f"openpyxl failed to open '{path.name}': {exc}") from exc

    try:
        sheet_names = tuple(wb.sheetnames)
        if not sheet_names:
            raise FormatValidationError(f"Workbook '{path.name}' has zero worksheets.")

        parsed_sheets: dict[str, SheetData] = {}
        for sh_name in sheet_names:
            ws = wb[sh_name]
            iter_rows = list(ws.iter_rows(values_only=True))
            if not iter_rows:
                parsed_sheets[sh_name] = SheetData(name=sh_name, headers=(), rows=())
                continue
            header_row = iter_rows[0]
            headers: list[str] = []
            for h_idx, h_val in enumerate(header_row):
                if h_val is None or str(h_val).strip() == "":
                    raise FormatValidationError(
                        f"Worksheet '{sh_name}' in '{path.name}' has an empty header at column {h_idx + 1}."
                    )
                headers.append(str(h_val).strip())

            num_headers = len(headers)
            data_rows: list[tuple[Any, ...]] = []
            for r_idx, row_tuple in enumerate(iter_rows[1:], start=2):
                if len(row_tuple) > num_headers:
                    extra = row_tuple[num_headers:]
                    if any(v is not None and str(v).strip() != "" for v in extra):
                        raise FormatValidationError(
                            f"Worksheet '{sh_name}' row {r_idx} has values beyond the {num_headers} header columns."
                        )
                padded = tuple(
                    row_tuple[c_i] if c_i < len(row_tuple) else None
                    for c_i in range(num_headers)
                )
                if all(v is None or (isinstance(v, str) and v.strip() == "") for v in padded):
                    continue
                data_rows.append(padded)

            parsed_sheets[sh_name] = SheetData(
                name=sh_name,
                headers=tuple(headers),
                rows=tuple(data_rows),
            )
        return WorkbookData(sheet_names=sheet_names, sheets=parsed_sheets)
    finally:
        wb.close()


def _index_to_col_letters(idx: int) -> str:
    n = idx + 1
    chars: list[str] = []
    while n > 0:
        n, rem = divmod(n - 1, 26)
        chars.append(chr(ord("A") + rem))
    return "".join(reversed(chars))


def write_synthetic_xlsx(
    path: Path,
    sheets: Sequence[tuple[str, Sequence[str], Sequence[Sequence[Any]]]],
) -> None:
    """Write a minimal valid OOXML .xlsx file for synthetic unit tests without requiring external packages."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        sheet_overrides = "".join(
            f'<Override PartName="/xl/worksheets/sheet{i}.xml" '
            'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
            for i in range(1, len(sheets) + 1)
        )
        content_types = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/xl/workbook.xml" '
            'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
            f"{sheet_overrides}"
            "</Types>"
        )
        zf.writestr("[Content_Types].xml", content_types)

        root_rels = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" '
            'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
            'Target="xl/workbook.xml"/>'
            "</Relationships>"
        )
        zf.writestr("_rels/.rels", root_rels)

        wb_sheets_xml = "".join(
            f'<sheet name="{xml_escape(sh_name)}" sheetId="{i}" r:id="rId{i}"/>'
            for i, (sh_name, _, _) in enumerate(sheets, start=1)
        )
        workbook_xml = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
            'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
            f"<sheets>{wb_sheets_xml}</sheets>"
            "</workbook>"
        )
        zf.writestr("xl/workbook.xml", workbook_xml)

        wb_rels_items = "".join(
            f'<Relationship Id="rId{i}" '
            'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
            f'Target="worksheets/sheet{i}.xml"/>'
            for i in range(1, len(sheets) + 1)
        )
        wb_rels = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            f"{wb_rels_items}"
            "</Relationships>"
        )
        zf.writestr("xl/_rels/workbook.xml.rels", wb_rels)

        for s_idx, (_, headers, rows) in enumerate(sheets, start=1):
            all_rows: list[Sequence[Any]] = [headers, *rows]
            row_xml_parts: list[str] = []
            for r_num, row_vals in enumerate(all_rows, start=1):
                cell_parts: list[str] = []
                for c_idx, cell_val in enumerate(row_vals):
                    if cell_val is None:
                        continue
                    col_ref = f"{_index_to_col_letters(c_idx)}{r_num}"
                    if isinstance(cell_val, (int, float)) and not isinstance(cell_val, bool):
                        cell_parts.append(f'<c r="{col_ref}" t="n"><v>{cell_val}</v></c>')
                    else:
                        text_escaped = xml_escape(str(cell_val))
                        cell_parts.append(
                            f'<c r="{col_ref}" t="inlineStr"><is><t>{text_escaped}</t></is></c>'
                        )
                row_xml_parts.append(f'<row r="{r_num}">{"".join(cell_parts)}</row>')

            ws_xml = (
                '<?xml version="1.0" encoding="UTF-8"?>'
                '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
                f'<sheetData>{"".join(row_xml_parts)}</sheetData>'
                "</worksheet>"
            )
            zf.writestr(f"xl/worksheets/sheet{s_idx}.xml", ws_xml)
