<<<<<<< HEAD
"""
app/classify.py  (Member A)

Body-first email classifier for the SDOC inbox.
Contract (must not change): classify(email: dict) -> Classification

Four principles:
  * The body decides; the subject is never used (subjects are decoys).
  * Rules run in a fixed order (spam, BL check, SI, invoice, general). The
    first rule that fires wins, and the result records which rule fired.
  * Attachments are supporting evidence only; they never decide on their own.
  * Every result carries a confidence: "high", "medium" or "low".
"""
from __future__ import annotations

import re

from contracts import Classification

BL_COMPARISON = "BL_COMPARISON"  # compare/confirm SI vs draft BL
SI_REQUEST = "SI_REQUEST"        # delivering / being chased for a shipping instruction
INVOICE_QUERY = "INVOICE_QUERY"  # invoice / D&D / THC / PGI / local charges
SPAM = "SPAM"                    # prize draw, parcel fee, bank officer, mailbox full
GENERAL = "GENERAL"              # bot notifications, chases with nothing attached, greetings


# --- body cleaning -------------------------------------------------------
# Security banner some senders prepend; it mentions "links"/"attachments" and
# would otherwise pollute the rules, so it is stripped before matching.
_BANNER = re.compile(
    r"WARNING:.*?exercise caution.*?(?:links or attachments)\.?",
    re.IGNORECASE | re.DOTALL,
)
# Quoted reply history starts at a long underscore line followed by "From:".
# Only the newest message counts.
_QUOTED = re.compile(r"\n_{10,}\s*\nFrom:")


def clean_body(body: str) -> str:
    """Banner removed and quoted reply history cut off: only the newest message counts."""
    text = _BANNER.sub(" ", body or "").strip()
    return _QUOTED.split(text)[0].strip()


# --- signal patterns (matched against the cleaned body) ------------------
def _compile(patterns):
    return [re.compile(p, re.IGNORECASE) for p in patterns]


# Scam bodies: prize/lottery, parcel-fee, discount blasts, mailbox-full
# phishing, "bank officer" advance-fee. Runs before invoice on purpose.
_SPAM = _compile([
    r"\bcongratulat", r"\byou(?:'ve| have)? won\b", r"\b(?:cash )?prize\b",
    r"\blottery\b", r"\bwinner\b", r"\bclaim your\b", r"\bgift card\b",
    r"\b90% off\b|\bdiscount\b.{0,20}\bexpires\b", r"\bmailbox (?:is )?full\b",
    r"\bverify your (?:account|mailbox|email)\b", r"\bclick (?:here|the link|below)\b",
    r"\bbank officer\b", r"\bbusiness proposal\b", r"\bunclaimed\b",
    r"\bparcel\b.{0,20}\bfee\b", r"\bbitcoin|crypto(?:currency)?\b",
])

# Six scam sender domains seen in the data. Used only as extra evidence when
# the body rules find nothing (never to override a positive rule).
_SPAM_DOMAINS = (
    "webmail-verify.co", "secure-mailbox.org", "parcel-track.co",
    "prize-claims.info", "logistics-deals.biz", "crypto-invest.net",
)

# Ask to compare/confirm the SI against the draft BL. Stays BL_COMPARISON even
# if the wrong doc is attached, the BL is missing, or attachments were dropped.
# Matches the enclosing-both-documents phrasings ("Attached are the SI and
# draft BL", "the shipping instruction and the draft bill of lading") and the
# compare/confirm verbs. NOTE: these describe *enclosed* documents; the trap in
# _SEND_BL_CHASE is a request to *send* a BL and is handled after SI/invoice.
_BL_COMPARE = _compile([
    r"\bcompare the SI and (?:the )?draft BL\b",
    r"\bassist to check the draft BL against the SI\b",
    r"\bcheck the details and confirm\b",
    r"\bconfirm the BL is in order\b",
    r"\bconfirm the draft BL\b",
    r"\bverify (?:that )?the BL matches the SI\b",
    r"\bthe SI and (?:the )?draft BL\b",
    # "... shipping instruction and the draft bill of lading ..." (both enclosed)
    r"\bshipping instruction and (?:the )?draft bill of lading\b",
    r"\bSI and (?:the )?draft bill of lading\b",
    # "Attached ... SI and draft BL ... for checking" — both docs are enclosed,
    # unlike the "assist to send the draft BL for checking" trap.
    r"\battached\b.{0,30}\bSI and draft BL\b",
    r"\bfor your confirmation\b",
])

# Sender is delivering an SI or being chased to submit one. The body of these
# often also contains "invoice" (Documents Required list), so this rule MUST
# run before the invoice rule.
_SI_FIND = _compile([
    r"\bplease find\b.{0,40}\bshipping instruction",
    r"\bshipping instruction for\b",
    r"\battached\b.{0,40}\bshipping instruction",
])
_SI_CHASE = _compile([
    r"\bsubmit SI\b", r"\bSI\b.{0,10}&.{0,10}\bAED\b",
    r"\breminder\b.{0,40}\bSI\b",
])

# Finance/billing questions.
_INVOICE = _compile([
    r"\binvoice\b", r"\bD ?& ?D\b", r"\bdemurrage\b|\bdetention\b",
    r"\bTHC\b", r"\bPGI\b", r"\blocal charge", r"\btelex release charge",
    r"\bGR (?:is )?missing\b", r"\breverse PGI\b", r"\bcancel (?:the )?invoice\b",
    r"\bbilled separately\b", r"\boutstanding (?:amount|payment|balance)\b",
])

# The trap: "please assist to send the draft BL ... for checking asap".
# They want a BL sent; nothing is enclosed, so there is nothing to compare.
_SEND_BL_CHASE = _compile([
    r"\bsend the draft BL\b.{0,40}\bcheck",
    r"\bassist to send the draft BL\b",
    r"\bdraft BL\b.{0,20}\bfor checking\b",
])


def _any(patterns, text) -> bool:
    return any(p.search(text) for p in patterns)


def _classify(email: dict) -> Classification:
    """Rules-only classification. Order is fixed; first match wins."""
    body = clean_body(email.get("body", ""))
    sender = (email.get("from", "") or "").lower()

    # 1) SPAM — before invoice, so scam "invoice" subjects can't leak through.
    if _any(_SPAM, body):
        return Classification(SPAM, "high", "spam_body")

    # 2) BL comparison — decided by wording, not by attachments.
    if _any(_BL_COMPARE, body):
        return Classification(BL_COMPARISON, "high", "bl_compare")

    # 3) SI — delivery first, then chase reminders. Before invoice.
    if _any(_SI_FIND, body):
        return Classification(SI_REQUEST, "high", "si_find")
    if _any(_SI_CHASE, body):
        return Classification(SI_REQUEST, "medium", "si_chase")

    # 4) Invoice / finance query.
    if _any(_INVOICE, body):
        return Classification(INVOICE_QUERY, "high", "invoice")

    # 5) "Send me the draft BL for checking" with nothing enclosed -> GENERAL.
    if _any(_SEND_BL_CHASE, body):
        return Classification(GENERAL, "medium", "gen_chase_draft_bl")

    # Insurance: nothing matched but the sender is a known scam domain.
    if any(sender.endswith("@" + d) or sender.endswith("." + d) for d in _SPAM_DOMAINS):
        return Classification(SPAM, "medium", "spam_domain")

    # 6) Default: bot notifications, berthing reports, greetings, etc.
    return Classification(GENERAL, "medium", "general")


# For /submit experiments: flip a whole rule's category without touching the rules.
RULE_OVERRIDES: dict[str, str] = {}   # e.g. {"gen_chase_draft_bl": "SI_REQUEST"}


def classify(email: dict) -> Classification:
    result = _classify(email)
    if result.rule in RULE_OVERRIDES:
        result.category = RULE_OVERRIDES[result.rule]
    return result


if __name__ == "__main__":
    import sys
    from collections import Counter

    from app.inbox import get_inbox

    source = sys.argv[1] if len(sys.argv) > 1 else None
    emails = get_inbox(source).emails()

    cats = Counter()
    rules = Counter()
    conf = Counter()
    for e in emails:
        r = classify(e)
        cats[r.category] += 1
        rules[r.rule] += 1
        conf[r.confidence] += 1

    print(f"total emails: {len(emails)}")
    print(f"category counts: {dict(cats)}")
    print(f"rule counts:     {dict(rules)}")
    print(f"confidence:      {dict(conf)}")
=======
"""Rule-based classifier for the SDOC inbox.

Categories: BL_COMPARISON, SI_REQUEST, INVOICE_QUERY, GENERAL, SPAM.

Design:
  * Rules are checked in PRECEDENCE order; the first one that fires wins.
  * The BODY decides. The subject is never used (subjects are decoys, e.g. an
    RPA-bot subject on an SI reminder, or "Invoice payment" on a scam).
  * Attachments are supporting evidence only, never sufficient on their own.
  * Every result carries the rule name that fired, so a wrong call is easy to
    trace and the reason can be shown to a human reviewer.
"""
import re
from dataclasses import dataclass

BL_COMPARISON = "BL_COMPARISON"
SI_REQUEST = "SI_REQUEST"
INVOICE_QUERY = "INVOICE_QUERY"
GENERAL = "GENERAL"
SPAM = "SPAM"

# The safety banner is prepended to some bodies; it must not influence rules.
_BANNER = re.compile(r"WARNING: This email originated outside.*?attachments\.", re.S | re.I)

I = re.I

# 1. SPAM first: scam subjects imitate invoices, so this must run before INVOICE_QUERY.
SPAM_RULES = [
    ("spam_prize", re.compile(r"monthly draw|gift card|you have won|brand new iphone|claim your|complete this short survey", I)),
    ("spam_parcel", re.compile(r"package could not be delivered|unpaid customs fee", I)),
    ("spam_promo", re.compile(r"\d+\s*% off|buy now before|logistics automation suite|guaranteed \d+% returns", I)),
    ("spam_phishing", re.compile(r"mailbox has exceeded|verify your account|storage (limit|is full)|update your account to avoid", I)),
    ("spam_advance_fee", re.compile(r"bank officer|urgent business proposal|reply with your bank details", I)),
]

# 2. BL_COMPARISON: someone hands us an SI and a draft BL (or the wrong paper) to check.
BL_RULES = [
    ("bl_compare_phrase", re.compile(r"compare the si and (the )?draft bl", I)),
    ("bl_check_against", re.compile(r"check the draft bl against the si", I)),
    ("bl_attached_pair", re.compile(r"(attached|find attached)( are)?( the)? (si|shipping instruction) and (the )?(draft (bl|bill of lading)|bill of lading)", I)),
    ("bl_attached_pair_short", re.compile(r"attached si and draft bl", I)),
    # Wrong document in the pair: still a comparison request, it just cannot be completed.
    ("bl_wrong_doc", re.compile(r"(si) and the (packing list|certificate of origin|commercial invoice).{0,60}confirm the bl", I | re.S)),
]

# 3. SI_REQUEST: an SI is being supplied for processing, or chased.
SI_RULES = [
    ("si_supplied", re.compile(r"please find shipping instruction for", I)),
    ("si_chase", re.compile(r"submit si\b.{0,10}\baed|submit shipping instructions?", I)),
]

# 4. INVOICE_QUERY: money / billing questions about a specific invoice.
INVOICE_RULES = [
    ("inv_gr_missing", re.compile(r"\bGR\b.{0,30}(missing|post)|post the GR", I)),
    ("inv_thc", re.compile(r"\bTHC\b|local charge", I)),
    ("inv_dnd", re.compile(r"D&D|detention charges?", I)),
    ("inv_cancel", re.compile(r"cancel invoice|reverse the PGI", I)),
    # Bare "invoice" is deliberately last and weak.
    ("inv_keyword", re.compile(r"\binvoice\b", I)),
]

# 5. GENERAL rules exist only to record *why* something is general (and to flag
#    the ambiguous "please send the draft BL" chase for /submit experiments).
GENERAL_RULES = [
    ("gen_chase_draft_bl", re.compile(r"send the draft bl", I)),
    ("gen_bot_notification", re.compile(r"automated notification", I)),
    ("gen_berthing", re.compile(r"berthing report", I)),
    ("gen_update_summary", re.compile(r"update summary", I)),
    ("gen_outstanding_list", re.compile(r"list of outstanding bl", I)),
    ("gen_greeting", re.compile(r"happy and prosperous|office resumes", I)),
]


@dataclass
class Classification:
    category: str
    confidence: str  # "high" | "medium" | "low"
    rule: str        # which rule fired, for audit and human review


def clean_body(body: str) -> str:
    return _BANNER.sub(" ", body or "").strip()


def classify(email: dict) -> Classification:
    body = clean_body(email.get("body", ""))
    n_att = len(email.get("attachments") or [])

    for name, rx in SPAM_RULES:
        if rx.search(body):
            return Classification(SPAM, "high", name)

    for name, rx in BL_RULES:
        if rx.search(body):
            return Classification(BL_COMPARISON, "high", name)

    for name, rx in SI_RULES:
        if rx.search(body):
            # A chase is less clear-cut than an SI actually supplied in the body.
            return Classification(SI_REQUEST, "high" if name == "si_supplied" else "medium", name)

    for name, rx in INVOICE_RULES:
        if rx.search(body):
            return Classification(INVOICE_QUERY, "medium" if name == "inv_keyword" else "high", name)

    for name, rx in GENERAL_RULES:
        if rx.search(body):
            # The draft-BL chase is the one genuinely ambiguous template.
            return Classification(GENERAL, "medium" if name == "gen_chase_draft_bl" else "high", name)

    # Nothing matched. Two attachments that look like an SI/BL pair is still a
    # comparison request even if the wording was unexpected.
    names = " ".join(email.get("attachments") or []).upper()
    if n_att and "_SI" in names and "_BL" in names:
        return Classification(BL_COMPARISON, "low", "fallback_attachment_pair")

    return Classification(GENERAL, "low", "fallback_general")


if __name__ == "__main__":
    import glob, json, sys, collections
    root = sys.argv[1] if len(sys.argv) > 1 else "."
    emails = [json.load(open(p)) for p in sorted(glob.glob(f"{root}/inbox/email_*.json"))]
    results = {e["email_id"]: classify(e) for e in emails}
    print(collections.Counter(r.category for r in results.values()))
    print(collections.Counter((r.category, r.rule) for r in results.values()).most_common())
>>>>>>> db16662c206ae14ae84853881eb4ce94aeb344f3
