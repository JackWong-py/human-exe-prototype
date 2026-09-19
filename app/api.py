"""HTTP layer (FastAPI): a JSON API under /api plus two simple pages (/report, /reviews-ui).

Run from the repo root:   uvicorn app.api:app --reload --port 8000
Interactive API docs:     http://localhost:8000/docs
"""
import html
from typing import Any, Optional

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel

try:                                  # makes GEMINI_API_KEY etc. available to whoever needs them
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:                   # pragma: no cover
    pass

from . import db, decide as dec, pipeline, readers, submission
from .contracts import FIELDS
from .inbox import get_inbox

app = FastAPI(title="human.exe backend")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],   # the Vite dev server
    allow_methods=["*"], allow_headers=["*"],
)

STATUS_ORDER = {"NEEDS_REVIEW": 0, "MISMATCH": 1, "OK": 2}


def _stubs():
    return [name for name, mod in (("readers", readers), ("decide", dec))
            if getattr(mod, "IS_STUB", False)]


@app.exception_handler(pipeline.NotFound)
async def _not_found(_req, exc):
    return JSONResponse({"error": str(exc)}, status_code=404)


@app.exception_handler(ValueError)
async def _bad_request(_req, exc):
    return JSONResponse({"error": str(exc)}, status_code=400)


class ResolveIn(BaseModel):
    by: str = "reviewer"
    note: str = ""
    verdict: Optional[str] = None                 # "OK" or "MISMATCH"
    defect_fields: Optional[list[str]] = None     # required with MISMATCH
    si_values: Optional[dict[str, Any]] = None    # corrected values, by field name
    bl_values: Optional[dict[str, Any]] = None


# ---- JSON API --------------------------------------------------------------
@app.get("/api/health")
def health():
    return {"ok": True, "inbox_source": get_inbox().source, "stub_modules": _stubs()}


@app.get("/api/summary")
def summary():
    return db.summary()


@app.post("/api/run")
def run_all(force: bool = False):
    """Process every email. Results already resolved by a human are kept unless force=true."""
    return pipeline.run_all(force=force)


@app.post("/api/run/{email_id}")
def run_one(email_id: str, force: bool = False):
    return pipeline.run_email(email_id, force=force)


@app.post("/api/emails/{email_id}/retry")
def retry(email_id: str):
    return pipeline.retry(email_id)


@app.get("/api/results")
def results(category: Optional[str] = None, status: Optional[str] = None,
            state: Optional[str] = None):
    return db.list_results(category, status, state)


@app.get("/api/emails")     # same rows with an "id" alias, convenient for a React list
def emails():
    return [{**r, "id": r["email_id"]} for r in db.list_results()]


@app.get("/api/results/{email_id}")
def result(email_id: str):
    row = db.get_result(email_id)
    if row is None:
        raise pipeline.NotFound(f"No result for {email_id}")
    return {"result": row, "reviews": db.list_reviews(email_id=email_id),
            "errors": db.list_errors(email_id), "audit": db.list_audit(email_id)}


@app.get("/api/reviews")
def reviews(state: str = Query("OPEN")):
    return db.list_reviews(state)


@app.get("/api/reviews/{review_id}")
def review(review_id: int):
    rv = db.get_review(review_id)
    if rv is None:
        raise pipeline.NotFound(f"Review {review_id} not found")
    return rv


@app.post("/api/reviews/{review_id}/resolve")
def resolve(review_id: int, body: ResolveIn):
    return pipeline.resolve_review(
        review_id, by=body.by or "reviewer", note=body.note, verdict=body.verdict or None,
        defect_fields=body.defect_fields, si_values=body.si_values, bl_values=body.bl_values)


@app.get("/api/errors")
def errors(email_id: Optional[str] = None):
    return db.list_errors(email_id)


@app.get("/api/submission")
def get_submission():
    return submission.build_submission(db.list_results())


@app.post("/api/submission/submit")
def submit(force: bool = False):
    problems = []
    s = db.summary()
    if s["total"] == 0:
        problems.append("Nothing has been run yet (POST /api/run first)")
    if s["by_state"].get("FAILED"):
        problems.append(f"{s['by_state']['FAILED']} email(s) FAILED; retry or fix them first")
    if _stubs():
        problems.append(f"Stub modules still active: {', '.join(_stubs())}")
    if problems and not force:
        return JSONResponse({"error": "Refusing to submit", "problems": problems,
                             "hint": "add ?force=true to submit anyway"}, status_code=409)
    try:
        return get_inbox().submit(submission.build_submission(db.list_results()))
    except RuntimeError as err:       # the loader raises this when the source is a folder
        return JSONResponse({"error": str(err)}, status_code=400)


# ---- simple pages (no build step; the same JSON API can feed a React UI later) --------
CSS = """
body{font:15px/1.5 system-ui,sans-serif;margin:24px auto;max-width:1100px;padding:0 16px;color:#222}
table{border-collapse:collapse;width:100%;margin:8px 0 24px}
th,td{border:1px solid #ddd;padding:6px 8px;text-align:left;vertical-align:top}
th{background:#f5f5f5}.warn{background:#fff3cd;border:1px solid #e0c36a;padding:8px 12px;margin:12px 0}
.tag{padding:1px 8px;border-radius:10px;font-size:13px}
.OK{background:#d8f0dc}.MISMATCH{background:#f9d6d5}.NEEDS_REVIEW{background:#fde9b8}
code{background:#f2f2f2;padding:0 4px}input[type=text],select,textarea{width:100%;box-sizing:border-box;padding:4px}
"""
NAV = ("<nav><a href='/report'>Report</a> | <a href='/reviews-ui'>Review queue</a> | "
       "<a href='/docs'>API docs</a></nav>")


def _e(value):
    return html.escape("" if value is None else str(value))


def _page(body):
    return HTMLResponse(f"<!doctype html><meta charset='utf-8'><title>human.exe</title>"
                        f"<style>{CSS}</style>{NAV}{body}")


@app.get("/", include_in_schema=False)
def index():
    return report()


@app.get("/report", response_class=HTMLResponse)
def report():
    rows = db.list_results()
    s = db.summary()
    checks = sorted((r for r in rows if r["category"] == "BL_COMPARISON" and r["state"] == "DONE"),
                    key=lambda r: (STATUS_ORDER.get(r["status"], 3), r["email_id"]))
    review_of = {r["email_id"]: r["id"] for r in db.list_reviews("OPEN")}
    failed = [r for r in rows if r["state"] == "FAILED"]

    out = ["<h1>Shipping document verification</h1>"]
    if _stubs():
        out.append(f"<div class='warn'>Stub modules still active: <b>{_e(', '.join(_stubs()))}</b>. "
                   "BL results below are placeholders.</div>")
    out.append(f"<p>{s['total']} emails | open reviews: <a href='/reviews-ui'>{s['open_reviews']}</a> | "
               f"failed: {s['by_state'].get('FAILED', 0)} | resolved by a human: {s['human_resolved']}</p>")
    out.append("<p>" + " &nbsp;".join(f"<code>{_e(k)}</code> {v}" for k, v in s["by_category"].items()) + "</p>")

    if failed:
        out.append("<h2>Failed emails</h2><table><tr><th>Email</th><th>Stage</th><th>Error</th><th></th></tr>")
        for r in failed:
            out.append(f"<tr><td>{_e(r['email_id'])}</td><td>{_e(r['error_stage'])}</td>"
                       f"<td>{_e(r['error_message'])}</td>"
                       f"<td><button onclick=\"retry('{_e(r['email_id'])}')\">Retry</button></td></tr>")
        out.append("</table>")

    out.append(f"<h2>Document checks ({len(checks)})</h2>"
               "<table><tr><th>Email</th><th>Status</th><th>What needs attention</th></tr>")
    for r in checks:
        if r["status"] == "OK":
            detail = "No mismatch detected"
        elif r["status"] == "MISMATCH":
            detail = "<br>".join(f"<b>{_e(d['field'])}</b> &nbsp; SI: {_e(d['si'])} / BL: {_e(d['bl'])}"
                                 for d in r["diffs"]) or _e(", ".join(r["defect_fields"]))
        else:
            link = (f" <a href='/reviews-ui/{review_of[r['email_id']]}'>review</a>"
                    if r["email_id"] in review_of else "")
            detail = f"{_e(r['review_reason'])} &mdash; {_e(r['message'])}{link}"
        human = " <small>(human)</small>" if r["resolved_by_human"] else ""
        out.append(f"<tr><td>{_e(r['email_id'])}{human}</td>"
                   f"<td><span class='tag {_e(r['status'])}'>{_e(r['status'])}</span></td><td>{detail}</td></tr>")
    out.append("</table><script>async function retry(id){await fetch('/api/emails/'+id+'/retry',"
               "{method:'POST'});location.reload();}</script>")
    return _page("".join(out))


@app.get("/reviews-ui", response_class=HTMLResponse)
def reviews_ui(state: str = "OPEN"):
    items = db.list_reviews(state)
    out = [f"<h1>Review queue ({_e(state)})</h1><p><a href='/reviews-ui?state=OPEN'>open</a> | "
           "<a href='/reviews-ui?state=RESOLVED'>resolved</a></p>"
           "<table><tr><th>#</th><th>Email</th><th>Reason</th><th></th></tr>"]
    for r in items:
        out.append(f"<tr><td>{r['id']}</td><td>{_e(r['email_id'])}</td><td>{_e(r['reason'])}</td>"
                   f"<td><a href='/reviews-ui/{r['id']}'>open</a></td></tr>")
    if not items:
        out.append("<tr><td colspan='4'>Nothing here.</td></tr>")
    out.append("</table>")
    return _page("".join(out))


def _doc_html(d, name):
    if not d:
        return f"<h3>{name}</h3><p><i>Not provided</i></p>"
    tags = (f" <span class='tag NEEDS_REVIEW'>{_e(d['error'])}</span>" if d.get("error") else "") + \
           (" <span class='tag'>OCR</span>" if d.get("noisy") else "")
    rows = "".join(f"<tr><td>{_e(p[0])}</td><td>{_e(p[1])}</td><td>{_e(p[2])}</td></tr>"
                   for p in d.get("pairs", [])) or "<tr><td colspan='3'><i>No extracted values</i></td></tr>"
    return (f"<h3>{name}</h3><p><code>{_e(d['path'])}</code> &nbsp; type: <b>{_e(d['doc_type'])}</b> "
            f"&nbsp; title: {_e(d['title'])}{tags}</p>"
            f"<table><tr><th>Label</th><th>Value</th><th>Source</th></tr>{rows}</table>")


REVIEW_JS = """
<script>
const FIELDS = __FIELDS__;
async function resolve(){
  const val = id => document.getElementById(id).value.trim();
  const collect = p => Object.fromEntries(FIELDS.map(f => [f, val(p + '_' + f)]).filter(x => x[1]));
  const body = { by: val('by'), note: val('note'), verdict: val('verdict'),
    defect_fields: FIELDS.filter(f => document.getElementById('d_' + f).checked),
    si_values: collect('si'), bl_values: collect('bl') };
  const r = await fetch('/api/reviews/__ID__/resolve', {method: 'POST',
    headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)});
  const j = await r.json();
  if (r.ok) location = '/report'; else document.getElementById('err').textContent = j.error || JSON.stringify(j);
}
</script>"""


@app.get("/reviews-ui/{review_id}", response_class=HTMLResponse)
def review_ui(review_id: int):
    rv = db.get_review(review_id)
    if rv is None:
        raise pipeline.NotFound(f"Review {review_id} not found")
    res = db.get_result(rv["email_id"]) or {}
    ev = rv["evidence"] or {}
    out = [f"<h1>Review #{rv['id']} &mdash; {_e(rv['email_id'])}</h1>"
           f"<p>Reason: <span class='tag NEEDS_REVIEW'>{_e(rv['reason'])}</span> &nbsp; State: {_e(rv['state'])}"
           f" &nbsp; Subject: {_e(res.get('subject'))}</p>",
           _doc_html(ev.get("si"), "SI (reference)"), _doc_html(ev.get("bl"), "Draft BL")]
    if rv["state"] == "OPEN":
        rows = "".join(f"<tr><td>{f}</td><td><input type='text' id='si_{f}'></td>"
                       f"<td><input type='text' id='bl_{f}'></td>"
                       f"<td><input type='checkbox' id='d_{f}'></td></tr>" for f in FIELDS)
        out.append("<h2>Resolve</h2><p>Either enter corrected values (blank keeps what was extracted) "
                   "or give a verdict.</p><table><tr><th>Field</th><th>SI value</th><th>BL value</th>"
                   f"<th>Defect?</th></tr>{rows}</table>"
                   "<p>Verdict (optional): <select id='verdict'><option value=''>- use corrected values -</option>"
                   "<option>OK</option><option>MISMATCH</option></select></p>"
                   "<p>Your name: <input type='text' id='by' value='reviewer'></p>"
                   "<p>Note: <textarea id='note' rows='2'></textarea></p>"
                   "<button onclick='resolve()'>Resolve</button> <span id='err' style='color:#b00'></span>"
                   + REVIEW_JS.replace("__FIELDS__", str(list(FIELDS)).replace("'", '"'))
                              .replace("__ID__", str(rv["id"])))
    else:
        out.append(f"<h2>Resolution</h2><pre>{_e(rv['resolution'])}</pre>")
    return _page("".join(out))
