"""Decide OK / MISMATCH / NEEDS_REVIEW for one SI + draft BL pair. Owned by D.

    decide(si, bl) -> CompareResult

Precedence (the first rule that applies wins):
    1. missing_attachment   an SI or BL is None
    2. wrong_doc_type       the "SI" or "BL" is another kind of document
    3. unreadable           a document could not be read, or OCR text disagrees and cannot be trusted
    4. missing_value        a required field is blank or a placeholder
    5. otherwise compare the 7 fields: MISMATCH if any differ, else OK
"""
from .contracts import FIELDS, CompareResult
from .mapping import extract_fields
from .normalize import (is_placeholder, first_line, norm_count, norm_name, norm_port,
                        norm_weight, similarity)

# OCR text is noisy ("AL GUAS" for "AL GURG", "NAN TONG GHIMA" for "NANTONG, CHINA").
# On the real data, OCR noise scores 0.83 to 1.00 similarity while genuinely different
# companies or ports score 0.76 or less. So:
#   similarity >= OCR_SAME       -> same (forgive the noise)
#   similarity <  OCR_DIFFERENT  -> different (clearly another value)
#   in between                   -> unsure (a human decides)
OCR_SAME = 0.80
OCR_DIFFERENT = 0.55
# A parsed document of unknown type is still accepted if it clearly has the fields of an SI/BL.
MIN_FIELDS_FOR_UNKNOWN = 5


def _review(reason, message):
    return CompareResult("NEEDS_REVIEW", review_reason=reason, message=message)


def _display(field, value):
    """What a human should see side by side: the name line for parties and ports, raw otherwise."""
    if field in ("shipper", "consignee", "notify_party", "port_of_loading", "port_of_discharge"):
        return first_line(value)
    return str(value).strip()


def compare_field(field, si_value, bl_value, noisy=False):
    """Return 'same', 'different' or 'unsure' for one field.

    noisy=True means at least one document was read by OCR, so small differences are
    forgiven and numbers that disagree are never called defects on OCR evidence alone.
    """
    if field in ("shipper", "consignee", "notify_party"):
        a, b = norm_name(si_value), norm_name(bl_value)
        exact = a == b
    elif field in ("port_of_loading", "port_of_discharge"):
        (an, ac, _), (bn, bc, _) = norm_port(si_value), norm_port(bl_value)
        if noisy:                       # OCR often drops the comma, so compare "name country" as one string
            a, b = f"{an} {ac}".strip(), f"{bn} {bc}".strip()
            exact = a == b or a.startswith(b) or b.startswith(a)
        else:                           # the port name decides; countries count only if both are present
            a, b = an, bn
            exact = an == bn and (not ac or not bc or ac == bc)
    elif field == "container_count":
        exact = norm_count(si_value) == norm_count(bl_value)
    else:                               # gross_weight_kg
        exact = norm_weight(si_value) == norm_weight(bl_value)

    if exact:
        return "same"
    if not noisy:
        return "different"
    if field in ("container_count", "gross_weight_kg"):
        return "unsure"                 # a misread digit looks exactly like a real defect
    closeness = similarity(a, b)
    if closeness >= OCR_SAME:
        return "same"
    return "different" if closeness < OCR_DIFFERENT else "unsure"


def decide(si, bl):
    if si is None or bl is None:
        which = "SI" if si is None else "BL"
        return _review("missing_attachment", f"The {which} attachment is missing")

    for doc, expected in ((si, "SI"), (bl, "BL")):
        if doc.doc_type == "OTHER" or doc.doc_type in ("SI", "BL") and doc.doc_type != expected:
            what = doc.title.strip() or doc.doc_type
            return _review("wrong_doc_type", f"The {expected} slot holds a different document: {what}")

    for doc, name in ((si, "SI"), (bl, "BL")):
        if doc.error:
            return _review("unreadable", f"The {name} could not be read ({doc.path})")

    si_fields, bl_fields = extract_fields(si), extract_fields(bl)
    for doc, fields, name in ((si, si_fields, "SI"), (bl, bl_fields, "BL")):
        if doc.doc_type == "UNKNOWN" and len(fields) < MIN_FIELDS_FOR_UNKNOWN:
            return _review("unreadable", f"The {name} could not be identified as an SI or BL ({doc.path})")

    missing = {name: [f for f in FIELDS if f not in fields or is_placeholder(fields[f]["value"])]
               for name, fields in (("SI", si_fields), ("BL", bl_fields))}
    if missing["SI"] or missing["BL"]:
        parts = [f"{name}: {', '.join(fs)}" for name, fs in missing.items() if fs]
        # If OCR was involved the value may simply not have been read, so it is a reading problem.
        reason = "unreadable" if (si.noisy or bl.noisy) else "missing_value"
        return _review(reason, "Value missing or blank in " + "; ".join(parts))

    noisy = si.noisy or bl.noisy
    diffs, unsure = [], []
    for field in FIELDS:
        outcome = compare_field(field, si_fields[field]["value"], bl_fields[field]["value"], noisy)
        if outcome == "same":
            continue
        entry = {"field": field, "si": _display(field, si_fields[field]["value"]),
                 "bl": _display(field, bl_fields[field]["value"])}
        (diffs if outcome == "different" else unsure).append(entry)

    if diffs:
        return CompareResult("MISMATCH", has_defect=True, defect_fields=[d["field"] for d in diffs],
                             diffs=diffs, message="Mismatch in " + ", ".join(d["field"] for d in diffs))
    if unsure:
        return CompareResult("NEEDS_REVIEW", review_reason="unreadable", diffs=unsure,
                             message="Scanned text disagrees and cannot be trusted: "
                                     + ", ".join(d["field"] for d in unsure))
    return CompareResult("OK", message="No mismatch detected")
