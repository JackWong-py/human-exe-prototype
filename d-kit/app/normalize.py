"""Turn raw field values into comparable forms. Owned by D.

Rule of thumb: normalise away *formatting* (case, punctuation, separators, port codes,
unit text) but never away *content* (a different company, port, count or weight).
"""
import difflib
import re

_PLACEHOLDER = re.compile(
    r"^\W*(n/?a|tba|tbc|tbd|nil|none|null|to be (advised|confirmed))?\W*$|"   # '', N/A, TBA, '-'
    r"^[_?\-.\s]+(mts?|kgs?)?$",                                                # '____MT', '???', '____'
    re.I,
)
_SUFFIX = {"LIMITED": "LTD", "PRIVATE": "PTE", "BERHAD": "BHD", "INCORPORATED": "INC",
           "CORPORATION": "CORP", "COMPANY": "CO", "&": "AND"}


def is_placeholder(value):
    """True for empty or 'not filled in' values: '', 'N/A', 'TBA', '____MT', '???'."""
    return value is None or bool(_PLACEHOLDER.match(str(value)))


def first_line(value):
    """Multi-line values arrive joined with ' | ' (or newlines). Line 1 is the name, the rest the address."""
    return re.split(r"\s*\|\s*|\r?\n", str(value).strip(), maxsplit=1)[0].strip()


def norm_name(value):
    """'MOORIM SP CO., LTD | 656, GANGNAM-DAERO ...' -> 'MOORIM SP CO LTD' (name only, no address)."""
    text = re.sub(r"[^A-Z0-9& ]", " ", first_line(value).upper())
    return " ".join(_SUFFIX.get(w, w) for w in text.split())


def norm_port(value):
    """'PORT KLANG (WESTPORT), MALAYSIA (MYPKG)' -> ('PORT KLANG', 'MALAYSIA', 'MYPKG')."""
    text = first_line(value).upper()
    code = re.search(r"\(([A-Z]{5})\)", text)
    text = re.sub(r"\([^)]*\)", " ", text)
    parts = [re.sub(r"[^A-Z0-9/ ]", " ", p) for p in text.split(",")]
    parts = [" ".join(p.split()) for p in parts if p.strip()]
    name = parts[0] if parts else ""
    country = parts[-1] if len(parts) > 1 else ""
    return name, country, code.group(1) if code else None


def norm_count(value):
    """"6 x 40'HC" -> 6 ; "4X40'HC" -> 4 ; "12" -> 12."""
    text = str(value)
    m = re.search(r"(\d+)\s*[xX\u00d7]", text) or re.search(r"\d+", text)
    return int(m.group(1) if m and m.lastindex else m.group(0)) if m else None


def norm_weight(value):
    """'21,577 KG' -> 21577.0 ; '128.544' -> 128544.0 (a dot followed by 3 digits is a thousands separator)."""
    text = str(value)
    m = re.search(r"\d[\d.,]*", text)
    if not m:
        return None
    number = m.group(0).rstrip(".,")
    if re.fullmatch(r"\d{1,3}([.,]\d{3})+", number):
        number = re.sub(r"[.,]", "", number)
    else:
        number = number.replace(",", "")
    weight = float(number)
    return weight * 1000 if re.search(r"\b(mt|mts|tons?|tonnes?)\b", text, re.I) else weight


def similarity(a, b):
    """0..1 text similarity ignoring spaces: used only to forgive OCR noise."""
    a, b = a.replace(" ", ""), b.replace(" ", "")
    return difflib.SequenceMatcher(None, a, b).ratio() if a and b else 0.0
