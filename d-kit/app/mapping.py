"""Map the many raw labels used by SI/BL documents onto the 7 canonical fields, by meaning.

Owned by D. The examples in comments are real labels from the data.
"""
import re

from .contracts import FIELDS

_CJK = re.compile(r"[\u3000-\u303f\u3400-\u4dbf\u4e00-\u9fff\uff00-\uffef]+")

# Checked in order: the first pattern that matches decides. Order matters, e.g. "Notify
# Party/Intermediate Consignee" must hit notify_party before the consignee pattern sees it.
RULES = [
    # "NET WEIGHT" sits right next to gross weight in some SIs and must never be read as it.
    (None, re.compile(r"\bnet\b|\btare\b|measurement|\bcbm\b")),
    ("gross_weight_kg", re.compile(r"\bgross\b")),           # Gross Weight (KG), Gross Wt (kgs), TOTAL Gross Wt
    ("notify_party", re.compile(r"\bnotify\b")),             # NOTIFY PARTY, Notify, Notify Party/Intermediate Consignee
    ("port_of_loading", re.compile(r"port of loading|\bpol\b|load port|loading port")),
    ("port_of_discharge", re.compile(r"port of discharge|\bpod\b|discharge port")),
    # "No. of Containers or Packages", "Total Containers", "Container Count". Not "CONTAINER NO."
    # (a table header) and not "Kinds of Packages; Description of Goods" (the goods, not a count).
    ("container_count", re.compile(r"^(no\.? of |total |number of )?containers?\b(?!\s*no\b)")),
    ("shipper", re.compile(r"^(shipper|exporter)")),         # Shipper/Exporter, Shipper (Principal or Seller)
    ("consignee", re.compile(r"^consignee|to the order of")),  # Consignee (Non-Negotiable), To the Order of
]


def clean_label(label):
    """Lowercase, drop Chinese text and punctuation: 'Gross Weight毛重(KGS)' -> 'gross weight kgs'."""
    text = _CJK.sub(" ", label or "").lower()
    text = re.sub(r"[^a-z0-9/. ]", " ", text)
    return " ".join(text.split())


def map_label(label):
    """Return the canonical field name for a raw label, or None if it is not one of the 7."""
    text = clean_label(label)
    for field, rx in RULES:
        if rx.search(text):
            return field
    return None


def extract_fields(raw):
    """RawDoc -> {field: {"value": str, "evidence": str, "label": str}}.

    Contract: pairs are in priority order, so the FIRST pair mapping to a field wins
    (reviewer corrections are prepended). The one exception is a placeholder such as
    'N/A': a later real value beats an earlier placeholder.
    """
    from .normalize import is_placeholder

    found = {}
    for pair in raw.pairs:
        label, value = pair[0], "" if pair[1] is None else str(pair[1])
        evidence = pair[2] if len(pair) > 2 else ""
        field = map_label(label)
        if field is None:
            continue
        if field not in found or (is_placeholder(found[field]["value"]) and not is_placeholder(value)):
            found[field] = {"value": value, "evidence": evidence, "label": label}
    return found


def unmapped_labels(raw):
    """Labels in a document that map to none of the 7 fields (useful when debugging a reader)."""
    return [p[0] for p in raw.pairs if map_label(p[0]) is None]


assert set(f for f, _ in RULES if f) == set(FIELDS)
