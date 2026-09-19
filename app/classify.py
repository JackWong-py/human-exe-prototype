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
