"""
tests/test_classify.py  (Member A)

Golden-set guard for the classifier. Every time a wrong call is fixed, add the
email id here so it can never regress. Run:

    python3 -m unittest tests.test_classify -v
"""
import unittest

from app.classify import classify, clean_body
from app.inbox import get_inbox

# email_id -> expected category. These pin the traps documented in the guide.
GOLDEN = {
    "email_001": "BL_COMPARISON",   # "Attached are the SI and draft BL ... confirm"
    "email_004": "BL_COMPARISON",   # same template, different wording
    "email_005": "BL_COMPARISON",   # "shipping instruction and the draft bill of lading"
    "email_021": "SI_REQUEST",      # subject "RPA Billing", body chases SI
    "email_075": "GENERAL",         # bot "Billing Process completed" notification
    "email_095": "GENERAL",         # "assist to send the draft BL for checking", nothing attached
    "email_323": "GENERAL",         # bot notification
    "email_417": "SPAM",            # scam subject imitates an invoice
    "email_429": "SI_REQUEST",      # SI typed in body; also says "invoice"
    "email_501": "BL_COMPARISON",   # wrong paper attached, still a comparison ask
    "email_506": "BL_COMPARISON",   # attachments dropped
    "email_507": "BL_COMPARISON",   # BL missing
    "email_511": "BL_COMPARISON",   # corrupt PDF, both docs enclosed
    "email_512": "BL_COMPARISON",   # scanned image PDFs, both docs enclosed
}


class TestClassify(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.by_id = {e["email_id"]: e for e in get_inbox().emails()}

    def test_golden_categories(self):
        for eid, expected in GOLDEN.items():
            with self.subTest(email=eid):
                self.assertEqual(classify(self.by_id[eid]).category, expected)

    def test_subject_is_never_used(self):
        # email_417's subject says "Invoice payment" but the body is a scam.
        self.assertEqual(classify(self.by_id["email_417"]).category, "SPAM")

    def test_quoted_history_is_stripped(self):
        # email_095's newest message is the "send draft BL" chase; the quoted
        # history below "____ From:" must not be classified.
        cleaned = clean_body(self.by_id["email_095"]["body"])
        self.assertNotIn("Please follow the previous instruction", cleaned)
        self.assertIn("draft BL", cleaned)

    def test_banner_is_stripped(self):
        cleaned = clean_body(self.by_id["email_095"]["body"])
        self.assertNotIn("originated outside", cleaned)

    def test_every_email_has_a_category(self):
        valid = {"BL_COMPARISON", "SI_REQUEST", "INVOICE_QUERY", "SPAM", "GENERAL"}
        for e in self.by_id.values():
            self.assertIn(classify(e).category, valid)

    def test_no_low_confidence(self):
        # Today no email should fall through to "low"; every rule sets high/medium.
        low = [e["email_id"] for e in self.by_id.values()
               if classify(e).confidence == "low"]
        self.assertEqual(low, [])


if __name__ == "__main__":
    unittest.main()
