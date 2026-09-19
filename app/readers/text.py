from dataclasses import dataclass
from pathlib import Path


@dataclass
class RawDoc:
    doc_type: str
    title: str
    pairs: list
    error: str | None = None
    noisy: bool = False


def detect_doc_type(title: str) -> str:
    """
    Detect document type from the document title.

    Returns:
        SI    - Shipping Instruction
        BL    - Bill of Lading
        OTHER - Other document type
    """
    title_upper = title.upper()

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


def read_txt(path: str | Path) -> RawDoc:
    """
    Read a TXT document.

    Format:
        First line = document title
        Label: value
          continuation line
        ==== = separator and ignored
    """
    path = Path(path)

    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        text = path.read_text(encoding="latin-1")
    except Exception:
        return RawDoc(
            doc_type="OTHER",
            title="",
            pairs=[],
            error="unreadable",
            noisy=False,
        )

    lines = text.splitlines()

    if not lines:
        return RawDoc(
            doc_type="OTHER",
            title="",
            pairs=[],
            error="unreadable",
            noisy=False,
        )

    # First line is always the document title.
    title = lines[0].strip()

    doc_type = detect_doc_type(title)

    pairs = []
    current_label = None
    current_value = []
    current_source = []

    def save_current():
        """Save the current label/value pair."""
        nonlocal current_label, current_value, current_source

        if current_label is not None:
            value = " ".join(current_value).strip()
            source = " ".join(current_source).strip()

            pairs.append((current_label, value, source))

        current_label = None
        current_value = []
        current_source = []

    for line in lines[1:]:
        stripped = line.strip()

        # Skip empty lines.
        if not stripped:
            continue

        # Skip separator lines such as ====================
        if set(stripped) == {"="}:
            continue

        # Indented lines are continuation lines.
        if line[0].isspace():
            if current_label is not None:
                current_value.append(stripped)
                current_source.append(stripped)

            continue

        # Normal Label: value line.
        if ":" in stripped:
            save_current()

            label, value = stripped.split(":", 1)

            current_label = label.strip()
            current_value = [value.strip()]
            current_source = [stripped]

    # Save the final pair.
    save_current()

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

    if extension == ".txt":
        return read_txt(path)

    if extension == ".xlsx":
        from app.readers.xlsx import read_xlsx
        return read_xlsx(path)

    if extension == ".docx":
        from app.readers.docx import read_docx
        return read_docx(path)

    return RawDoc(
        doc_type="OTHER",
        title="",
        pairs=[],
        error="unreadable",
        noisy=False,
    )

def find_si_bl(email):
    """
    Find the Shipping Instruction (SI) and Bill of Lading (BL)
    from an email's attachments.

    The filename (_SI / _BL) is only used as a slot hint.
    The actual document type comes from read_document().
    """
    attachments = email.get("attachments", [])

    si_doc = None
    bl_doc = None

    for filename in attachments:
        path = Path("data/attachments") / filename

        if not path.exists():
            continue

        doc = read_document(path)

        if doc.error is not None:
            continue

        if doc.doc_type == "SI" and si_doc is None:
            si_doc = doc

        elif doc.doc_type == "BL" and bl_doc is None:
            bl_doc = doc

    return si_doc, bl_doc

def check_filename_mismatch(filename, doc_type):
    """
    Check whether the filename's _SI / _BL hint
    matches the actual detected document type.

    Returns:
        None - no mismatch
        dict - mismatch information
    """
    filename_upper = str(filename).upper()

    filename_hint = None

    if "_SI" in filename_upper:
        filename_hint = "SI"
    elif "_BL" in filename_upper:
        filename_hint = "BL"

    # No SI/BL hint in filename
    if filename_hint is None:
        return None

    # Filename and actual document type match
    if filename_hint == doc_type:
        return None

    return {
        "filename": str(filename),
        "filename_type": filename_hint,
        "actual_type": doc_type,
        "message": (
            f"Filename suggests {filename_hint}, "
            f"but actual document type is {doc_type}."
        ),
    }