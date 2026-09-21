"""Drafted replies for emails that need a person (Task 4).

The facts come from the pipeline, never from the model. The steps are:

  1. build_facts(row)      plain facts about one stored result (which file is missing, which values differ)
  2. template_reply(facts) a complete, correct draft written from fixed sentences
  3. optional AI polish    a model may reword the draft, but its answer is CHECKED: if it drops a fact,
                           invents a number, removes the [Your name] placeholder or adds a link, the
                           template is used instead.

Nothing is ever sent. A person reads, edits and sends the draft. Drafting never changes a result.

Settings (.env): GEMINI_API_KEY, GEMINI_MODEL. SUGGEST_AI=off turns the model off completely.
"""
import os
import re
from email.utils import parseaddr
from os.path import basename

from .contracts import CANONICAL_LABELS, FIELDS, RawDoc
from .mapping import extract_fields
from .normalize import is_placeholder

DISCLAIMER = "AI-assisted draft. Read it, edit it and send it yourself. Nothing is sent automatically."
SLOT_NAME = {"SI": "Shipping Instruction (SI)", "BL": "draft Bill of Lading (BL)"}
PLACEHOLDER = "[Your name]"


# ---- the model (optional) ---------------------------------------------------
def get_client():
    """A Gemini client, or None when AI is off or not configured."""
    if os.environ.get("SUGGEST_AI", "auto").lower() == "off":
        return None
    if not (os.environ.get("GEMINI_API_KEY") and os.environ.get("GEMINI_MODEL")):
        return None
    try:
        from google import genai
        return genai.Client()
    except ImportError:
        return None


# ---- 1. facts ---------------------------------------------------------------
GENERIC_MAILBOXES = {"docs", "doc", "info", "sales", "export", "exports", "admin", "support", "office", "cs",
                     "ops", "booking", "bookings", "team", "shipping", "documentation", "noreply", "no"}


def greeting_name(sender):
    """'Hari Mardianto <hari@x.com>' -> 'Hari'; 'elisa_tukiman@x.com' -> 'Elisa'; 'docs@x.com' -> 'Sir or Madam'."""
    name, addr = parseaddr(sender or "")
    if name:
        words = name.split()
    else:
        local = addr.split("@")[0]
        words = re.split(r"[._-]+", local) if re.search(r"[._-]", local) else []       # 'docs' alone is not a person
    word = words[0] if words else ""
    ok = re.fullmatch(r"[A-Za-z][A-Za-z'-]{1,20}", word) and word.lower() not in GENERIC_MAILBOXES
    return word.capitalize() if ok else "Sir or Madam"


def _blank_labels(doc):
    """Labels of the required fields that are missing or blank in one document (a dict, as stored)."""
    got = extract_fields(RawDoc(**doc))
    return [CANONICAL_LABELS[f] for f in FIELDS if f not in got or is_placeholder(got[f]["value"])]


def build_facts(row):
    """Facts for one stored result (from db.get_result), or None when no reply is needed."""
    if not row or row.get("state") == "FAILED" or row.get("category") != "BL_COMPARISON":
        return None
    status, reason = row.get("status"), row.get("review_reason")
    if status not in ("MISMATCH", "NEEDS_REVIEW"):
        return None
    evidence = row.get("evidence") or {}
    si, bl = evidence.get("si"), evidence.get("bl")
    facts = {"email_id": row["email_id"], "subject": row.get("subject") or "", "to": row.get("sender") or "",
             "name": greeting_name(row.get("sender")), "status": status, "reason": reason, "must_include": []}

    if status == "MISMATCH":
        diffs = [{"label": CANONICAL_LABELS.get(d["field"], d["field"]), "si": d["si"], "bl": d["bl"]}
                 for d in row.get("diffs") or []]
        if not diffs:
            return None
        facts["diffs"] = diffs
        for d in diffs:
            facts["must_include"] += [d["label"], d["si"], d["bl"]]

    elif reason == "missing_attachment":
        facts["missing"] = [slot for slot, doc in (("SI", si), ("BL", bl)) if doc is None]

    elif reason == "wrong_doc_type":
        if si and bl and si["doc_type"] == "BL" and bl["doc_type"] == "SI":          # the two were swapped
            wrong = [{"slot": "SI", "title": "draft Bill of Lading"}, {"slot": "BL", "title": "Shipping Instruction"}]
        else:
            wrong = [{"slot": slot, "title": (doc.get("title") or "").strip()}
                     for slot, doc in (("SI", si), ("BL", bl)) if doc and doc["doc_type"] == "OTHER"]
        facts["wrong"] = wrong
        facts["must_include"] += [w["title"] for w in wrong if w["title"]]

    elif reason == "unreadable":
        broken = [{"slot": slot, "file": basename(doc["path"])}
                  for slot, doc in (("SI", si), ("BL", bl)) if doc and doc.get("error")]
        if broken:
            facts["unreadable"] = broken
            facts["must_include"] += [b["file"] for b in broken]
        else:                                                                        # scans OCR could not read reliably
            labels = [CANONICAL_LABELS.get(d["field"], d["field"]) for d in row.get("diffs") or []]
            facts["unclear"] = labels
            facts["must_include"] += labels

    elif reason == "missing_value":
        blanks = [{"slot": slot, "labels": _blank_labels(doc)} for slot, doc in (("SI", si), ("BL", bl)) if doc]
        facts["blanks"] = [b for b in blanks if b["labels"]]
        for b in facts["blanks"]:
            facts["must_include"] += b["labels"]

    return facts


# ---- 2. the template --------------------------------------------------------
def _and(items):
    items = list(items)
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1]


def template_reply(facts):
    """(subject, body): a complete draft written from fixed sentences."""
    original = re.sub(r"^(?:(?:re|fw|fwd)\s*[:_]\s*)+", "", facts["subject"] or "", flags=re.I).strip()
    subject = "Re: " + (original or f"Documents for {facts['email_id']}")
    reason = facts["reason"]

    if facts["status"] == "MISMATCH":
        lines = "\n".join(f'- {d["label"]}: SI "{d["si"]}" / BL "{d["bl"]}"' for d in facts["diffs"])
        para = ("We compared the Shipping Instruction (SI) with the draft Bill of Lading (BL) and found "
                f"these differences:\n{lines}")
        ask = "Could you please correct the draft BL, or let us know if the SI is the one that should change?"

    elif reason == "missing_attachment":
        missing = facts["missing"]
        what = ("neither the Shipping Instruction (SI) nor the draft Bill of Lading (BL) was"
                if len(missing) == 2 else f"the {SLOT_NAME[missing[0]]} was not" if missing else "a document was not")
        para = f"Thank you for your email. We could not complete the document check because {what} attached."
        ask = ("Could you please resend both documents so that we can compare them?" if len(missing) == 2
               else f"Could you please resend the {SLOT_NAME[missing[0]]}?" if missing
               else "Could you please resend the documents?")

    elif reason == "wrong_doc_type":
        parts = [f"the file sent as the {SLOT_NAME[w['slot']]} is {('a ' + w['title'].lower()) if w['title'] else 'a different document'}"
                 for w in facts["wrong"]]
        para = "Thank you for your email. We could not complete the document check because " + _and(parts) + "."
        ask = "Could you please send the correct " + _and([SLOT_NAME[w["slot"]] for w in facts["wrong"]]) + "?"

    elif reason == "unreadable" and facts.get("unreadable"):
        parts = [f"the file {b['file']}, sent as the {SLOT_NAME[b['slot']]}," if len(facts["unreadable"]) > 1
                 else f"the file {b['file']}, sent as the {SLOT_NAME[b['slot']]}" for b in facts["unreadable"]]
        para = "Thank you for your email. We could not open " + _and(parts) + "."
        ask = "Could you please resend it, ideally as a PDF with selectable text?"

    elif reason == "unreadable":
        para = ("Thank you for your email. The scanned copy is hard to read reliably for: "
                + (_and(facts.get("unclear") or ["some fields"])) + ".")
        ask = "Could you please send a clearer copy, or a PDF with selectable text?"

    else:                                                                            # missing_value
        parts = [f"the {SLOT_NAME[b['slot']]} has no value for {_and(b['labels'])}" for b in facts.get("blanks", [])]
        para = "Thank you for your email. We could not complete the document check because " + (
            _and(parts) if parts else "some required details are blank") + "."
        ask = "Could you please confirm these details so that we can finish the check?"

    return subject, f"Dear {facts['name']},\n\n{para}\n\n{ask}\n\nBest regards,\n{PLACEHOLDER}\n"


# ---- 3. optional AI polish, always checked ---------------------------------
def _norm(text):
    return re.sub(r"\s+", " ", (text or "").replace("\u201c", '"').replace("\u201d", '"').replace("\u2019", "'")).strip().lower()


def _numbers(text):
    return {n.rstrip(".,") for n in re.findall(r"\d[\d,.]*", text or "")}


def validate(text, facts, template_body):
    """(ok, why). The model's text must keep every fact and add nothing new."""
    if not text or len(text) < 40:
        return False, "the answer was empty or too short"
    if len(text) > 2 * len(template_body) + 200:
        return False, "the answer was much longer than the draft"
    if PLACEHOLDER not in text:
        return False, f"the {PLACEHOLDER} placeholder was removed"
    if re.search(r"https?://|www\.", text, re.I):
        return False, "the answer contains a link"
    low = _norm(text)
    for needle in facts["must_include"]:
        if needle and _norm(needle) not in low:
            return False, f"the fact {needle!r} is missing"
    invented = _numbers(text) - _numbers(template_body) - _numbers(facts["subject"])
    if invented:
        return False, f"the answer contains a new number ({sorted(invented)[0]})"
    return True, ""


PROMPT = """You are helping a shipping documentation team. Improve the wording of the email draft below so it
sounds natural, polite and professional.
Rules:
- Keep every name, number, document title, field name and file name exactly as written.
- Do not add facts, dates, deadlines, promises, links or attachments.
- Do not mention that you are an AI.
- Keep the greeting line, and end with "Best regards," followed by the line {placeholder}.
- Keep it under {words} words. Return only the email text, nothing else.

Draft:
---
{draft}
---"""


def _polish(client, facts, template_body):
    words = max(60, int(len(template_body.split()) * 1.4))
    prompt = PROMPT.format(placeholder=PLACEHOLDER, words=words, draft=template_body)
    reply = client.models.generate_content(model=os.environ.get("GEMINI_MODEL", ""), contents=prompt)
    text = re.sub(r"^```[a-z]*|```$", "", (reply.text or "").strip(), flags=re.M).strip() + "\n"
    ok, why = validate(text, facts, template_body)
    return (text, "") if ok else (None, why)


# ---- the one function the API calls ----------------------------------------
def draft_reply(row, client=None, use_ai=None):
    """The draft for one stored result.

    use_ai: None = use the model when it is configured, False = template only.
    client: pass a fake in tests; otherwise get_client() decides.
    Never raises because of the model, and never changes the result it is given.
    """
    facts = build_facts(row)
    if facts is None:
        return {"needed": False, "message": "No reply is needed for this email.", "disclaimer": DISCLAIMER}
    subject, body = template_reply(facts)
    result = {"needed": True, "to": facts["to"], "subject": subject, "body": body, "source": "template",
              "note": "", "disclaimer": DISCLAIMER}
    if use_ai is False:
        result["note"] = "Template only (AI not requested)."
        return result
    client = client if client is not None else get_client()
    if client is None:
        result["note"] = "AI is off or not configured (GEMINI_API_KEY, GEMINI_MODEL); showing the template."
        return result
    try:
        text, why = _polish(client, facts, body)
    except Exception as exc:                                    # noqa: BLE001 - a model failure must never break the page
        result["note"] = f"The AI service failed ({type(exc).__name__}); showing the template."
        return result
    if text is None:
        result["note"] = f"The AI wording was rejected ({why}); showing the template."
        return result
    result.update(body=text, source="ai", note="Reworded by AI. Every fact was checked against the pipeline's facts.")
    return result
