from dataclasses import dataclass
from pathlib import Path

from openpyxl import load_workbook


@dataclass
class RawDoc:
    doc_type: str
    title: str
    pairs: list
    error: str | None = None
    noisy: bool = False


def detect_doc_type(title: str) -> str:
    """
    Detect document type from the document title/content.
    """
    title_upper = str(title).upper()

    if "INSTRUCTION" in title_upper:
        return "SI"

    if "BILL OF LADING" in title_upper:
        return "BL"

    if (
        "COMMERCIAL INVOICE" in title_upper
        or "PACKING LIST" in title_upper
        or "CERTIFICATE OF ORIGIN" in title_upper
    ):
        return "OTHER"

    return "OTHER"


def read_xlsx(path: str | Path) -> RawDoc:
    """
    Read an XLSX document.

    The workbook contains label/value information in two columns.
    Header rows and blank rows are skipped.
    Numeric values are converted to strings.
    """
    path = Path(path)

    try:
        workbook = load_workbook(path, data_only=True)
        worksheet = workbook.active
    except Exception:
        return RawDoc(
            doc_type="OTHER",
            title="",
            pairs=[],
            error="unreadable",
            noisy=False,
        )

    rows = list(worksheet.iter_rows(values_only=True))

    if not rows:
        return RawDoc(
            doc_type="OTHER",
            title="",
            pairs=[],
            error="unreadable",
            noisy=False,
        )

    # Search the first several rows for document type/title information.
    title = ""

    for row in rows[:5]:
        for cell in row:
            if cell is not None:
                text = str(cell).strip()

                if "INSTRUCTION" in text.upper():
                    title = text
                    break

                if "BILL OF LADING" in text.upper():
                    title = text
                    break

                if "COMMERCIAL INVOICE" in text.upper():
                    title = text
                    break

                if "PACKING LIST" in text.upper():
                    title = text
                    break

                if "CERTIFICATE OF ORIGIN" in text.upper():
                    title = text
                    break

        if title:
            break

    doc_type = detect_doc_type(title)

    pairs = []

    for row in rows:
        if len(row) < 2:
            continue

        label = row[0]
        value = row[1]

        # Skip blank rows.
        if label is None or str(label).strip() == "":
            continue

        label = str(label).strip()

        # Skip rows without a value.
        if value is None:
            continue

        # Convert numbers such as gross weight to strings.
        value = str(value).strip()

        if value == "":
            continue

        source = f"{label}: {value}"

        pairs.append((label, value, source))

    return RawDoc(
        doc_type=doc_type,
        title=title,
        pairs=pairs,
        error=None,
        noisy=False,
    )


def read_document(path: str | Path) -> RawDoc:
    """
    Read a document based on its file extension.
    """
    path = Path(path)
    extension = path.suffix.lower()

    if extension == ".xlsx":
        return read_xlsx(path)

    return RawDoc(
        doc_type="OTHER",
        title="",
        pairs=[],
        error="unreadable",
        noisy=False,
    )