from dataclasses import dataclass
from pathlib import Path

from openpyxl import load_workbook

# Store the information extracted from an XLSX document.
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
    # Convert the title to uppercase so the comparison works regardless of uppercase or lowercase letters.
    title_upper = str(title).upper()

    # If the title contains "INSTRUCTION", classify it as Shipping Instruction (SI).
    if "INSTRUCTION" in title_upper:
        return "SI"

    # If the title contains "BILL OF LADING", classify it as Bill of Lading (BL).
    if "BILL OF LADING" in title_upper:
        return "BL"

    # These are recognised as other document types, not Shipping Instructions or Bills of Lading.
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
        # Open the Excel workbook. 
        # data_only=True reads the displayed/calculated values 
        # instead of Excel formulas.
        workbook = load_workbook(path, data_only=True)

        # Use the first worksheet in the workbook.
        worksheet = workbook.active

    except Exception:
        # If the workbook cannot be opened, return an unreadable document.
        return RawDoc(
            doc_type="OTHER",
            title="",
            pairs=[],
            error="unreadable",
            noisy=False,
        )

    # Read all worksheet rows as values.
    rows = list(worksheet.iter_rows(values_only=True))

    if not rows: # treat the document as unreadable if no rows are found.
        return RawDoc(
            doc_type="OTHER",
            title="",
            pairs=[],
            error="unreadable",
            noisy=False,
        )

    # Search the first several rows for document type/title information.
    title = ""

    # Only check the first 5 rows for the title.
    for row in rows[:5]:
        for cell in row:
            if cell is not None:

                # Convert the cell value to text and remove unnecessary spaces.
                text = str(cell).strip()

                # Check if the cell indicates a Shipping Instruction.
                if "INSTRUCTION" in text.upper():
                    title = text
                    break

                # Check if the cell indicates a Bill of Lading.
                if "BILL OF LADING" in text.upper():
                    title = text
                    break

                # Check if the cell indicates a Commercial Invoice.
                if "COMMERCIAL INVOICE" in text.upper():
                    title = text
                    break

                # Check if the cell indicates a Packing List.
                if "PACKING LIST" in text.upper():
                    title = text
                    break

                # Check if the cell indicates a Certificate of Origin.
                if "CERTIFICATE OF ORIGIN" in text.upper():
                    title = text
                    break

        if title:
            break

    
    doc_type = detect_doc_type(title)

    # Store all extracted label/value pairs here.
    pairs = []

    for row in rows:

        # Column A = label, Column B = value. Skip rows that do not have both a label and a value.
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

    # Return the extracted document information.
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
    # Convert the path into a Path object.
    path = Path(path)

    # Get the file extension and convert it to lowercase.
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