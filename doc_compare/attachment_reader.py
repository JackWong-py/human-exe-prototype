from __future__ import annotations

import csv
import re
from pathlib import Path
from typing import Any

from models import RawDoc


SUPPORTED_EXTENSIONS = {
    ".pdf", ".txt", ".csv", ".docx", ".xlsx", ".xlsm",
}


def read_attachment_text(path: str | Path) -> str:
    """
    Read textual content from a dataset attachment.

    Supported:
      - PDF  : pypdf
      - TXT  : utf-8 / latin-1 fallback
      - CSV  : csv module
      - DOCX : python-docx
      - XLSX : openpyxl

    Raises an exception when extraction fails. The caller converts that
    exception into RawDoc.error so the decision layer returns `unreadable`.
    """
    path = Path(path)
    suffix = path.suffix.casefold()

    if suffix == ".pdf":
        return _read_pdf(path)
    if suffix == ".txt":
        return _read_text(path)
    if suffix == ".csv":
        return _read_csv(path)
    if suffix == ".docx":
        return _read_docx(path)
    if suffix in {".xlsx", ".xlsm"}:
        return _read_xlsx(path)

    raise ValueError(f"Unsupported attachment type: {suffix or '<no extension>'}")


def _read_pdf(path: Path) -> str:
    from pypdf import PdfReader

    reader = PdfReader(str(path))
    chunks: list[str] = []

    for page_no, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        if text.strip():
            chunks.append(text)

    return "\n".join(chunks).strip()


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="latin-1")


def _read_csv(path: Path) -> str:
    rows: list[str] = []

    with path.open("r", encoding="utf-8-sig", newline="") as f:
        for row in csv.reader(f):
            rows.append(" | ".join(str(cell) for cell in row))

    return "\n".join(rows)


def _read_docx(path: Path) -> str:
    from docx import Document

    doc = Document(str(path))
    chunks: list[str] = []

    for paragraph in doc.paragraphs:
        text = paragraph.text.strip()
        if text:
            chunks.append(text)

    for table in doc.tables:
        for row in table.rows:
            values = [cell.text.strip() for cell in row.cells]
            if any(values):
                chunks.append(" | ".join(values))

    return "\n".join(chunks)


def _read_xlsx(path: Path) -> str:
    from openpyxl import load_workbook

    wb = load_workbook(path, read_only=True, data_only=True)
    chunks: list[str] = []

    for ws in wb.worksheets:
        chunks.append(f"[Sheet: {ws.title}]")
        for row in ws.iter_rows(values_only=True):
            values = ["" if value is None else str(value) for value in row]
            if any(value.strip() for value in values):
                chunks.append(" | ".join(values))

    return "\n".join(chunks)


DOC_TYPE_PATTERNS = {
    "SI": (
        r"\bshipping\s+instruction(?:s)?\b",
        r"\bshipping\s+instructions?\b",
        r"\bS\.?I\.?\b",
    ),
    "BL": (
        r"\bbill\s+of\s+lading\b",
        r"\bb\/l\b",
        r"\bB\.?L\.?\b",
    ),
}


def detect_doc_type(text: str, filename: str = "") -> str | None:
    haystack = f"{filename}\n{text[:5000]}"

    # Prefer explicit full phrases before short abbreviations.
    for doc_type in ("SI", "BL"):
        for pattern in DOC_TYPE_PATTERNS[doc_type]:
            if re.search(pattern, haystack, flags=re.IGNORECASE):
                return doc_type

    name = filename.casefold()
    if re.search(r"(^|[_\-\s])si([_\-\s.]|$)", name):
        return "SI"
    if re.search(r"(^|[_\-\s])bl([_\-\s.]|$)", name):
        return "BL"

    return None


LABEL_PATTERNS: dict[str, tuple[str, ...]] = {
    "Shipper": (
        r"shipper",
        r"exporter",
        r"consignor",
    ),
    "Consignee": (
        r"consignee",
        r"consigned\s+to",
        r"to\s+the\s+order\s+of",
        r"to\s+order\s+of",
    ),
    "Port of Loading": (
        r"port\s+of\s+loading",
        r"loading\s+port",
        r"\bpol\b",
    ),
    "Port of Discharge": (
        r"port\s+of\s+discharge",
        r"discharge\s+port",
        r"\bpod\b",
    ),
    "Containers": (
        r"container\s+count",
        r"container\s+quantity",
        r"number\s+of\s+containers",
        r"no\.?\s+of\s+containers",
        r"containers?",
    ),
    "Gross Weight": (
        r"gross\s+weight(?:\s*\(?(?:kg|kgs)\)?)?",
        r"gross\s+wt",
        r"\bg\.?\s*w\.?\b",
    ),
    "Description": (
        r"description\s+of\s+goods",
        r"goods\s+description",
        r"cargo\s+description",
        r"commodity",
        r"description",
    ),
}


def _clean_line(line: str) -> str:
    return re.sub(r"\s+", " ", line).strip()


def extract_labeled_fields(text: str) -> dict[str, str]:
    """
    Heuristic label/value extraction from already-extracted attachment text.

    Handles:
      Label: value
      Label - value
      Label | value
      Label
      value on next line

    It intentionally returns raw labels/values. mapping.py performs the
    semantic mapping and normalization later.
    """
    lines = [_clean_line(line) for line in text.splitlines()]
    lines = [line for line in lines if line]

    fields: dict[str, str] = {}

    for i, line in enumerate(lines):
        for canonical_label, patterns in LABEL_PATTERNS.items():
            if canonical_label in fields:
                continue

            matched = False

            for pattern in patterns:
                m = re.search(
                    rf"(?i)(?:^|\|\s*)({pattern})\s*(?::|-|\||=)\s*(.+)$",
                    line,
                )
                if m:
                    value = m.group(2).strip(" |:-")
                    if value:
                        fields[canonical_label] = value
                        matched = True
                        break

                # Label alone, value on the next line.
                if re.fullmatch(rf"(?i)\s*{pattern}\s*:?\s*", line):
                    if i + 1 < len(lines):
                        nxt = lines[i + 1].strip(" |:-")
                        if nxt:
                            fields[canonical_label] = nxt
                            matched = True
                            break

            if matched:
                continue

    return fields


def rawdoc_from_attachment(
    path: str | Path,
    *,
    noisy: bool = False,
) -> RawDoc:
    path = Path(path)

    try:
        text = read_attachment_text(path)

        if not text.strip():
            return RawDoc(
                doc_type=detect_doc_type("", path.name),
                fields={},
                attachment_present=True,
                error="attachment contains no extractable text",
                noisy=noisy,
                source_name=str(path),
            )

        return RawDoc(
            doc_type=detect_doc_type(text, path.name),
            fields=extract_labeled_fields(text),
            attachment_present=True,
            error=None,
            noisy=noisy,
            source_name=str(path),
        )

    except Exception as exc:
        return RawDoc(
            doc_type=detect_doc_type("", path.name),
            fields={},
            attachment_present=True,
            error=f"{type(exc).__name__}: {exc}",
            noisy=noisy,
            source_name=str(path),
        )
