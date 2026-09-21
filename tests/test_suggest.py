"""Tests for drafted replies (Task 4). Run after apply_task4_patch.py:

    python -m unittest tests.test_suggest -v

No test calls a real model: a fake client stands in for it.
"""
import os
import tempfile
import unittest
from unittest import mock

os.environ.setdefault("SCAN_VISION", "off")

from fastapi.testclient import TestClient  # noqa: E402

from app import db, pipeline, suggest  # noqa: E402
from app.api import app  # noqa: E402


class FakeClient:
    def __init__(self, reply=None, error=None):
        self.models, self.calls, self._reply, self._error = self, 0, reply, error
        self.last_prompt = ""

    def generate_content(self, model, contents):
        self.calls += 1
        self.last_prompt = contents
        if self._error:
            raise self._error
        return mock.Mock(text=self._reply)


def setup_db():
    os.environ["DB_PATH"] = os.path.join(tempfile.mkdtemp(), "t.db")
    for eid in ("email_001", "email_097", "email_501", "email_506", "email_507", "email_511", "email_516", "email_417"):
        pipeline.run_email(eid)


class TemplateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        setup_db()

    def draft(self, eid):
        return suggest.draft_reply(db.get_result(eid), use_ai=False)

    def test_missing_bl(self):
        d = self.draft("email_507")
        self.assertTrue(d["needed"])
        self.assertIn("draft Bill of Lading (BL) was not attached", d["body"])
        self.assertIn("resend the draft Bill of Lading (BL)", d["body"])
        self.assertTrue(d["subject"].startswith("Re: "))
        self.assertTrue(d["body"].rstrip().endswith("[Your name]"))

    def test_nothing_attached_names_both_documents(self):
        self.assertIn("neither the Shipping Instruction (SI) nor the draft Bill of Lading (BL)", self.draft("email_506")["body"])

    def test_wrong_document_names_what_was_sent(self):
        body = self.draft("email_501")["body"]
        self.assertIn("a commercial invoice", body)
        self.assertIn("send the correct draft Bill of Lading (BL)", body)

    def test_corrupt_file_names_the_file(self):
        self.assertIn("email_511_BL.pdf", self.draft("email_511")["body"])

    def test_blank_value_names_the_field(self):
        self.assertIn("Gross Weight (KG)", self.draft("email_516")["body"])

    def test_mismatch_lists_both_values(self):
        body = self.draft("email_097")["body"]
        self.assertIn("Container Count", body)
        self.assertIn("Gross Weight (KG)", body)
        self.assertIn('SI "10 x 40\'HC" / BL "11 x 40\'HC"', body)

    def test_no_reply_for_ok_or_other_categories(self):
        self.assertFalse(self.draft("email_001")["needed"])      # everything matches
        self.assertFalse(self.draft("email_417")["needed"])      # spam
        self.assertFalse(suggest.draft_reply(None)["needed"])

    def test_reply_subject_has_a_single_re(self):
        facts = suggest.build_facts(db.get_result("email_507"))
        for original in ("RE_ TO CONFIRM DOCS _ 5AKR", "Re: RE: TO CONFIRM DOCS _ 5AKR", "TO CONFIRM DOCS _ 5AKR"):
            subject, _ = suggest.template_reply({**facts, "subject": original})
            self.assertEqual(subject, "Re: TO CONFIRM DOCS _ 5AKR", original)

    def test_greeting_name(self):
        for sender, expected in (("Hari Mardianto <hari@x.com>", "Hari"), ("elisa_tukiman@april.com.my", "Elisa"),
                                 ("docs@vitalsolutions.sg", "Sir or Madam"), ("sales.team@x.com", "Sir or Madam"),
                                 ("", "Sir or Madam"), ("<12345@x.com>", "Sir or Madam")):
            self.assertEqual(suggest.greeting_name(sender), expected, sender)


class AiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        setup_db()

    def row(self):
        return db.get_result("email_097")

    def polished(self):
        subject, body = suggest.template_reply(suggest.build_facts(self.row()))
        return body.replace("Could you please correct", "It would be great if you could correct")

    def test_a_good_rewrite_is_used(self):
        client = FakeClient(reply=self.polished())
        d = suggest.draft_reply(self.row(), client=client)
        self.assertEqual((d["source"], client.calls), ("ai", 1))
        self.assertIn("It would be great", d["body"])
        self.assertIn("Every fact was checked", d["note"])

    def test_the_prompt_forbids_new_facts(self):
        client = FakeClient(reply=self.polished())
        suggest.draft_reply(self.row(), client=client)
        self.assertIn("Do not add facts", client.last_prompt)
        self.assertIn('SI "10 x 40\'HC"', client.last_prompt)

    def test_a_dropped_fact_is_rejected(self):
        bad = self.polished().replace("Gross Weight (KG)", "the weight")
        d = suggest.draft_reply(self.row(), client=FakeClient(reply=bad))
        self.assertEqual(d["source"], "template")
        self.assertIn("rejected", d["note"])

    def test_an_invented_number_is_rejected(self):
        bad = self.polished().replace("Best regards,", "Please reply within 24 hours.\n\nBest regards,")
        d = suggest.draft_reply(self.row(), client=FakeClient(reply=bad))
        self.assertEqual(d["source"], "template")
        self.assertIn("new number", d["note"])

    def test_a_link_or_missing_placeholder_is_rejected(self):
        for bad in (self.polished() + "See https://example.com", self.polished().replace("[Your name]", "John")):
            self.assertEqual(suggest.draft_reply(self.row(), client=FakeClient(reply=bad))["source"], "template")

    def test_a_failing_model_falls_back(self):
        d = suggest.draft_reply(self.row(), client=FakeClient(error=RuntimeError("quota")))
        self.assertEqual(d["source"], "template")
        self.assertIn("RuntimeError", d["note"])

    def test_no_key_means_template_and_ai_false_never_calls_the_model(self):
        with mock.patch.dict(os.environ, {"GEMINI_API_KEY": "", "GEMINI_MODEL": ""}):
            self.assertIsNone(suggest.get_client())
            self.assertEqual(suggest.draft_reply(self.row())["source"], "template")
        client = FakeClient(reply=self.polished())
        suggest.draft_reply(self.row(), client=client, use_ai=False)
        self.assertEqual(client.calls, 0)

    def test_suggest_ai_off_disables_the_client(self):
        with mock.patch.dict(os.environ, {"SUGGEST_AI": "off", "GEMINI_API_KEY": "k", "GEMINI_MODEL": "m"}):
            self.assertIsNone(suggest.get_client())

    def test_drafting_never_changes_the_result(self):
        before = db.get_result("email_097")
        suggest.draft_reply(before, client=FakeClient(reply=self.polished()))
        self.assertEqual(db.get_result("email_097"), before)


class WebTests(unittest.TestCase):
    def setUp(self):
        setup_db()
        self.c = TestClient(app)

    def test_endpoint_returns_a_template_draft(self):
        r = self.c.post("/api/results/email_507/draft", params={"ai": "false"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["source"], "template")

    def test_endpoint_uses_the_model_when_available(self):
        _, body = suggest.template_reply(suggest.build_facts(db.get_result("email_507")))
        with mock.patch.object(suggest, "get_client", return_value=FakeClient(reply=body.replace("Thank you for your email.", "Thanks for your message."))):
            j = self.c.post("/api/results/email_507/draft").json()
        self.assertEqual(j["source"], "ai")

    def test_unknown_email_is_404_and_ok_email_needs_no_reply(self):
        self.assertEqual(self.c.post("/api/results/email_999/draft").status_code, 404)
        self.assertFalse(self.c.post("/api/results/email_001/draft").json()["needed"])

    def test_the_page_shows_the_warning_and_is_linked_from_the_app(self):
        page = self.c.get("/draft/email_507")
        self.assertEqual(page.status_code, 200)
        self.assertIn("Nothing is sent automatically", page.text)
        self.assertIn("/draft/email_507", self.c.get("/report").text)
        rid = next(r["id"] for r in db.list_reviews("OPEN") if r["email_id"] == "email_507")
        self.assertIn("/draft/email_507", self.c.get(f"/reviews-ui/{rid}").text)

if __name__ == "__main__":
    unittest.main()
