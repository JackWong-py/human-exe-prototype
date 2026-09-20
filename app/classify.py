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
