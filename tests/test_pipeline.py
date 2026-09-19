"""Backend tests. Run from the repo root (the folder that contains data/):

    python -m unittest discover -s tests -v
"""
import json
import os
import tempfile
import unittest
from unittest import mock

from fastapi.testclient import TestClient

from app import db, pipeline, readers, submission
from app.api import app
from app.inbox import get_inbox

ALL_FIELDS = {"shipper": "A CO", "consignee": "B CO", "notify_party": "B CO",
              "port_of_loading": "SINGAPORE", "port_of_discharge": "KLANG",
              "container_count": "1 x 40'HC", "gross_weight_kg": "20,000"}


def sample_submission():
    for path in ("data/sample_submission.json", "sample_submission.json"):
        if os.path.exists(path):
            with open(path) as fh:
                return json.load(fh)
    raise FileNotFoundError("sample_submission.json not found in data/ or the repo root")


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        os.environ["DB_PATH"] = os.path.join(self.tmp, "test.db")

    def test_every_email_gets_a_result(self):
        s = pipeline.run_all()
        self.assertEqual(s["total"], len(get_inbox().emails()))
        self.assertEqual(s["by_state"].get("FAILED", 0), 0)
        self.assertEqual(sum(s["by_category"].values()), s["total"])

    def test_missing_attachments_open_reviews(self):
        pipeline.run_all()
        open_reviews = {r["email_id"]: r["reason"] for r in db.list_reviews("OPEN")}
        for eid in ("email_506", "email_507", "email_508", "email_509", "email_510"):
            self.assertEqual(open_reviews.get(eid), "missing_attachment", eid)

    def test_failure_is_visible_and_retryable(self):
        with mock.patch.object(readers, "find_si_bl", side_effect=RuntimeError("boom")):
            row = pipeline.run_email("email_001")
        self.assertEqual(row["state"], "FAILED")
        self.assertEqual(row["error_stage"], "read_documents")
        self.assertEqual(len(db.list_errors("email_001")), 1)
        self.assertEqual(pipeline.retry("email_001")["state"], "DONE")

    def test_unknown_email_fails_visibly(self):
        row = pipeline.run_email("email_999")
        self.assertEqual((row["state"], row["error_stage"]), ("FAILED", "load_email"))

    def test_verdict_resolution_is_audited_and_never_overwritten(self):
        pipeline.run_all()
        rv = next(r for r in db.list_reviews("OPEN") if r["email_id"] == "email_506")
        row = pipeline.resolve_review(rv["id"], by="tester", note="checked by phone",
                                      verdict="MISMATCH", defect_fields=["consignee"])
        self.assertEqual((row["status"], row["defect_fields"], row["resolved_by_human"]),
                         ("MISMATCH", ["consignee"], 1))
        self.assertEqual(db.get_review(rv["id"])["state"], "RESOLVED")
        self.assertEqual(db.list_audit("email_506")[-1]["action"], "review_resolved")
        pipeline.run_all()                            # a full re-run must not undo it
        self.assertEqual(db.get_result("email_506")["status"], "MISMATCH")
        with self.assertRaises(ValueError):           # cannot resolve twice
            pipeline.resolve_review(rv["id"], verdict="OK")

    def test_verdict_validation(self):
        pipeline.run_all()
        rv = db.list_reviews("OPEN")[0]
        for bad in (dict(verdict="MISMATCH"), dict(verdict="MAYBE"),
                    dict(verdict="MISMATCH", defect_fields=["nope"]), dict()):
            with self.assertRaises(ValueError):
                pipeline.resolve_review(rv["id"], **bad)

    def test_resolution_with_corrected_values_reruns_decide(self):
        pipeline.run_all()
        rv = next(r for r in db.list_reviews("OPEN") if r["email_id"] == "email_507")  # BL missing
        with self.assertRaises(ValueError):           # no BL values -> still missing
            pipeline.resolve_review(rv["id"], si_values={"shipper": "X"})
        row = pipeline.resolve_review(rv["id"], si_values=ALL_FIELDS, bl_values=ALL_FIELDS)
        self.assertEqual(row["status"], "OK")
        self.assertIn("reviewer input", row["message"])

    def test_submission_matches_sample_shape(self):
        pipeline.run_all()
        sample = sample_submission()
        sub = submission.build_submission(db.list_results())
        self.assertEqual(set(sub), set(sample))
        for eid, entry in sub.items():
            self.assertEqual(set(entry), set(sample[eid]), eid)


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        os.environ["DB_PATH"] = os.path.join(self.tmp, "api.db")
        self.c = TestClient(app)

    def test_end_to_end(self):
        self.assertEqual(self.c.get("/api/health").status_code, 200)
        self.assertEqual(self.c.post("/api/run").status_code, 200)
        rows = self.c.get("/api/results", params={"status": "NEEDS_REVIEW"}).json()
        self.assertTrue(rows and all(r["status"] == "NEEDS_REVIEW" for r in rows))
        self.assertEqual(self.c.get("/api/emails").json()[0]["id"], "email_001")
        for page in ("/report", "/reviews-ui", "/reviews-ui/1"):
            self.assertEqual(self.c.get(page).status_code, 200, page)
        self.assertEqual(self.c.get("/api/results/email_999").status_code, 404)
        r = self.c.post("/api/reviews/1/resolve", json={"verdict": "MISMATCH"})
        self.assertEqual(r.status_code, 400)          # needs defect fields
        r = self.c.post("/api/reviews/1/resolve", json={"verdict": "OK", "note": "ok"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self.c.get("/api/reviews/1").json()["state"], "RESOLVED")

    def test_submit_is_guarded(self):
        self.assertEqual(self.c.post("/api/submission/submit").status_code, 409)   # nothing run
        self.c.post("/api/run")
        r = self.c.post("/api/submission/submit")
        self.assertEqual(r.status_code, 409)                                        # stubs active
        self.assertIn("Stub modules", " ".join(r.json()["problems"]))
        r = self.c.post("/api/submission/submit", params={"force": "true"})
        self.assertEqual(r.status_code, 400)                                        # folder source
        self.assertEqual(len(self.c.get("/api/submission").json()), len(get_inbox().emails()))

    def test_cors_allows_the_vite_dev_server(self):
        r = self.c.get("/api/health", headers={"Origin": "http://localhost:5173"})
        self.assertEqual(r.headers.get("access-control-allow-origin"), "http://localhost:5173")


if __name__ == "__main__":
    unittest.main()
