"""Web endpoints for drafted replies (Task 4). Included by app/api.py with one line.

    POST /api/results/{email_id}/draft?ai=true|false   -> the draft as JSON
    GET  /draft/{email_id}                              -> a small page to create, edit and copy a draft
"""
import html

from fastapi import APIRouter
from fastapi.responses import HTMLResponse, JSONResponse

from . import db, suggest

router = APIRouter()


@router.post("/api/results/{email_id}/draft")
def draft(email_id: str, ai: bool = True):
    row = db.get_result(email_id)
    if row is None:
        return JSONResponse({"error": f"No result for {email_id}"}, status_code=404)
    return suggest.draft_reply(row, use_ai=None if ai else False)


PAGE_JS = """
<script>
const ID = "__ID__";
async function make(ai) {
  const note = document.getElementById('note');
  note.textContent = 'Working...';
  const r = await fetch('/api/results/' + ID + '/draft?ai=' + ai, {method: 'POST'});
  const j = await r.json();
  if (!r.ok) { note.textContent = j.error || 'Something went wrong'; return; }
  if (!j.needed) { note.textContent = j.message; return; }
  document.getElementById('to').value = j.to;
  document.getElementById('subject').value = j.subject;
  document.getElementById('body').value = j.body;
  note.textContent = 'Source: ' + j.source + '. ' + j.note;
}
async function copyDraft() {
  const text = 'To: ' + document.getElementById('to').value + '\\nSubject: ' + document.getElementById('subject').value
    + '\\n\\n' + document.getElementById('body').value;
  await navigator.clipboard.writeText(text);
  document.getElementById('note').textContent = 'Copied. Paste it into your email program.';
}
</script>"""


@router.get("/draft/{email_id}", response_class=HTMLResponse)
def draft_page(email_id: str):
    e = html.escape(email_id)
    return HTMLResponse(
        "<!doctype html><meta charset='utf-8'><title>Draft reply</title>"
        "<style>body{font:15px/1.5 system-ui,sans-serif;margin:24px auto;max-width:800px;padding:0 16px;color:#222}"
        "input,textarea{width:100%;box-sizing:border-box;padding:6px;margin:4px 0 12px;font:inherit}"
        ".warn{background:#fff3cd;border:1px solid #e0c36a;padding:8px 12px;margin:12px 0}"
        "button{padding:6px 14px;margin-right:8px}</style>"
        "<nav><a href='/report'>Report</a> | <a href='/reviews-ui'>Review queue</a></nav>"
        f"<h1>Draft reply for {e}</h1>"
        f"<div class='warn'>{html.escape(suggest.DISCLAIMER)}</div>"
        "<p><button onclick='make(true)'>Draft with AI</button>"
        "<button onclick='make(false)'>Template only</button>"
        "<button onclick='copyDraft()'>Copy</button></p>"
        "<p id='note'></p>"
        "<label>To</label><input id='to' readonly>"
        "<label>Subject</label><input id='subject'>"
        "<label>Message (you can edit it)</label><textarea id='body' rows='14'></textarea>"
        + PAGE_JS.replace("__ID__", e))
