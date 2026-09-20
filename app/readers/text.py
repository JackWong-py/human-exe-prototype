from dataclasses import dataclass
from pathlib import Path

# Store the information extracted from a document. 
# This common structure allows TXT, XLSX, and DOCX readers to return document data in the same format.
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
    # Convert the title to uppercase so the comparison 
    # works regardless of uppercase or lowercase letters.
    title_upper = title.upper()

    # If the title contains "INSTRUCTION", 
    # classify the document as Shipping Instruction (SI).
    if "INSTRUCTION" in title_upper:
        return "SI"

    # If the title contains "BILL OF LADING", 
    # # classify the document as Bill of Lading (BL).
    if "BILL OF LADING" in title_upper:
        return "BL"

    # These document titles are recognised as other 
    # document types rather than SI or BL.
    if (
        "COMMERCIAL INVOICE" in title_upper
        or "PACKING LIST" in title_upper
        or "CERTIFICATE OF ORIGIN" in title_upper
    ):
        return "OTHER"

    # If the title does not match any known document type, 
    # classify it as OTHER.
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

    # Convert the file path into a Path object 
    # so it can be handled easily.
    path = Path(path)

    try:
        # Try to read the TXT file using UTF-8 encoding.
        text = path.read_text(encoding="utf-8")

    except UnicodeDecodeError:
        # If UTF-8 cannot read the file, try Latin-1 encoding. 
        # # This allows the reader to handle different text encodings.
        text = path.read_text(encoding="latin-1")

    except Exception:
        # If the file cannot be read, return an unreadable document.
        return RawDoc(
            doc_type="OTHER",
            title="",
            pairs=[],
            error="unreadable",
            noisy=False,
        )

    # Split the document into separate lines.
    lines = text.splitlines()

    # If the document contains no lines, treat it as unreadable.
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

    # Detect the actual document type from the title.
    doc_type = detect_doc_type(title)

    # Store all extracted label/value pairs.
    pairs = []

    # These variables temporarily store the pair 
    # currently being processed.
    current_label = None
    current_value = []
    current_source = []

    def save_current():
        """Save the current label/value pair."""
        nonlocal current_label, current_value, current_source

        # Only save the pair if a label was found.
        if current_label is not None:
            # Combine multiple continuation lines into one value.
            value = " | ".join(v for v in current_value if v).strip()   # " | " between lines: line 1 is the name

            # Combine the source lines into one source snippet.
            source = " ".join(current_source).strip()

            # Store the label, value, and source together.
            pairs.append((current_label, value, source))

        # Reset the temporary variables for the next pair.
        current_label = None
        current_value = []
        current_source = []

    # Process every line after the document title.
    for line in lines[1:]:

        # Remove unnecessary spaces from the line.
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

                # Add the continuation text to the current value.
                current_value.append(stripped)

                # Also keep the text for the source snippet.
                current_source.append(stripped)

            continue

        # Normal Label: value line.
        if ":" in stripped:
            save_current()

            # Split only at the first colon. 
            # This prevents additional colons inside the value 
            # from being treated as another label.
            label, value = stripped.split(":", 1)

            # Store the cleaned label.
            current_label = label.strip()

            # Store the first value.
            current_value = [value.strip()]

            # Store the complete line as the source snippet.
            current_source = [stripped]

    # Save the final pair.
    save_current()

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

    # Use the TXT reader for .txt files.
    if extension == ".txt":
        return read_txt(path)

    # Use the XLSX reader for .xlsx files.
    if extension == ".xlsx":
        from app.readers.xlsx import read_xlsx
        return read_xlsx(path)

    # Use the DOCX reader for .docx files.
    if extension == ".docx":
        from app.readers.docx import read_docx
        return read_docx(path)

    # If the file extension is not recognized, return an unreadable document.
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

    # Get the list of attachments from the email. 
    # If there are no attachments, use an empty list.
    attachments = email.get("attachments", [])

    # These variables will store the detected SI and BL documents.
    si_doc = None
    bl_doc = None

    for filename in attachments:
        path = Path("data/attachments") / filename

        if not path.exists():
            continue

        doc = read_document(path)

        if doc.error is not None:
            continue

        # If the actual document is an SI, store it if an SI has not already been found.
        if doc.doc_type == "SI" and si_doc is None:
            si_doc = doc

        # If the actual document is a BL, store it if a BL has not already been found.
        elif doc.doc_type == "BL" and bl_doc is None:
            bl_doc = doc

    return si_doc, bl_doc

# Check if the document filename matches the actual document type. 
# This helps detect incorrectly named files and flag them for human review instead of trusting the filename.
def check_filename_mismatch(filename, doc_type):
    """
    Check whether the filename's _SI / _BL hint
    matches the actual detected document type.

    Returns:
        None - no mismatch
        dict - mismatch information
    """
    # Convert the filename to uppercase so the check works regardless of uppercase or lowercase letters.
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

    # If the filename and actual document type do not match, return the mismatch information. 
    # Other parts of the system can use this information to display a warning or send the document for human review.
    return {
        "filename": str(filename),
        "filename_type": filename_hint,
        "actual_type": doc_type,
        "message": (
            f"Filename suggests {filename_hint}, "
            f"but actual document type is {doc_type}."
        ),
    }