# Member E guide for the human.exe repo (FastAPI)

You own the backend spine: the API, the database, the pipeline that ties everyone's parts
together, the human-review flow and the report. This guide matches **your actual repo**.

## 1. What is in your repo today

| Path | State |
|---|---|
| `src/`, `package.json`, `vite.config.js` | untouched default Vite + React starter; nothing calls the backend yet |
| `server.py` | FastAPI prototype that asks Gemini to compare the first 10 emails (see Step 6) |
| `app/*.py`, `app/readers/*.py` | 12 files, **all empty (0 bytes)**, committed as placeholders |
| `app/GUIDES.md` | the team plan (Step 0 file list, A to E tasks) |
| `data/`, `loader.py`, `sample_submission.json` | the organizers' bundle: 520 emails, 250 attachments. Fine |
| `.env`, `.venv/`, `__pycache__/` | **committed to git. This is a problem** (Step 2) |

**Why it felt confusing.** The empty files came from the Step 0 file list. The zip I sent
afterwards (`sdoc-backend.zip`) used a different layout (Flask, one `readers.py`, HTML
templates), so it did not fit your repo (FastAPI, a `readers/` folder). **Ignore that zip.**
This patch replaces it and is built for your layout. I tested it on a copy of your repo with
your `data/` folder and your exact FastAPI version: 11 tests pass and the server starts.

## 2. Fix first: leaked API key and committed environment

Your `.env` (which holds `GEMINI_API_KEY`) and your whole `.venv/` (6,377 files) are tracked in
git and are on GitHub. Treat the key as leaked, whether the repo is public or private.

1. Open Google AI Studio (aistudio.google.com/apikey), **delete the old key** and create a new one.
2. Put the new key only in your local `.env`. Never commit it. Share it with teammates privately.
3. The old key stays in git history. Rotating it makes that harmless. Scrubbing history is not
   worth the time in a hackathon.

Git cleanup comes after you apply the patch (Step 3), because the patch brings the `.gitignore`.

## 3. Apply the patch

From the repo root (the folder with `data/` and `loader.py`):

```bash
unzip -o /path/to/e-patch-human-exe.zip
```

**Before you do**, ask A and D whether they already wrote code in `app/classify.py` or
`app/decide.py`. The patch overwrites those two (they are empty in the repo). If they have work,
tell them to keep theirs and only match the function signatures in `app/contracts.py`.

What the patch adds:

| File | Owner | What it is |
|---|---|---|
| `app/contracts.py` | everyone | shared data shapes and constants; change only together |
| `app/pipeline.py`, `app/db.py`, `app/api.py`, `app/inbox.py` | **you** | the pipeline, SQLite storage, FastAPI app, folder/HTTP loader wrapper |
| `app/readers/__init__.py` | B and C | stub `read_document` and `find_si_bl`; `IS_STUB = True` |
| `app/decide.py` | D | stub `decide()`; `IS_STUB = True` |
| `app/classify.py` | A | working first draft of the classifier |
| `app/submission.py` | A | builds `submission.json` in the sample's shape |
| `tests/` | you | 11 tests |
| `.gitignore`, `requirements.txt` | you | ignore `.env`/`.venv`; direct dependencies only |

Left alone: `mapping.py`, `normalize.py` (D), `readers/text.py`, `xlsx.py`, `docx.py` (B),
`pdf.py`, `scan.py` (C). They stay empty until their owners fill them.

## 4. Clean git, then commit in two steps

```bash
# 1) stop tracking the secret and the venv (the files stay on your disk)
git rm -r --cached --quiet .venv .env __pycache__
git add .gitignore
git commit -m "Stop tracking .env, .venv and __pycache__"

# 2) commit the backend skeleton
git add app tests requirements.txt docs
git commit -m "E: pipeline, database, API and stubs"
git push
```

I tested the first block on a copy of your repo: tracked files went from 7,183 to 803.

**Warn your team before you push.** When they pull, git deletes tracked files that stop being
tracked, so **their local `.venv/` and `.env` will disappear**. Message to send:

> Before you pull: copy your `.env` somewhere. After you pull, run
> `python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt`,
> and recreate `.env` with the NEW Gemini key (I will send it privately). `.env` and `.venv`
> are no longer in git and must never be committed again. Please also do not edit files that
> are not yours. Replace your stub, keep the function signatures in `app/contracts.py`, and
> delete the `IS_STUB = True` line when your part is real.

## 5. Install, test, run

```bash
python3 -m venv .venv && source .venv/bin/activate     # or reuse your existing venv
pip install -r requirements.txt
python -m unittest discover -s tests -v                # expect: Ran 11 tests ... OK
uvicorn app.api:app --reload --port 8000
```

Then:

- Open `http://localhost:8000/docs` (the interactive API) and `http://localhost:8000/report`.
- Run everything: `curl -X POST localhost:8000/api/run`.
- **Expected:** 520 emails: BL_COMPARISON 129, GENERAL 144, SI_REQUEST 132, INVOICE_QUERY 75,
  SPAM 40, and **5 open reviews** (emails 506 to 510, `missing_attachment`).
- The report shows a yellow banner "Stub modules still active: readers, decide". That is correct
  until B, C and D finish. While it shows, the BL statuses are placeholders and
  `POST /api/submission/submit` refuses to run.

## 6. Retire `server.py`

Your old `server.py` compared documents by sending them to Gemini. Do not run it next to the new
API. Rename it so nobody starts it by mistake, and keep it for C:

```bash
git mv server.py prototype_gemini.py
```

Things wrong with it today (worth telling C, who may reuse the Gemini idea for scanned documents):

- `pd` (pandas) is used but never imported, and pandas is not in `requirements.txt`, so every
  `.xlsx` email fails.
- Paths are doubled: attachments are already named `attachments/email_x_SI.pdf`, and the code
  joins `data/attachments/` in front, giving `data/attachments/attachments/...`. Only `.txt` works
  (it goes through `inbox.read_text`).
- `.docx` files are not handled at all.
- It calls the model on every request, only for the first 10 emails, and never classifies
  anything (`category` is hard-coded). Its `MATCH` status is not one of the required `OK`,
  `MISMATCH`, `NEEDS_REVIEW`.
- Check that the model name `gemini-1.5-flash-8b` still works with your key.

`app/api.py` already calls `load_dotenv()`, so `GEMINI_API_KEY` is available to any module.

## 7. What you own: a code tour

Read in this order: `contracts.py`, then `pipeline.py`, `db.py`, `api.py`.

- **`process(email)`** (pipeline.py): classify, then read documents, then decide. It returns a
  plain dict and writes nothing. A's scoring script reuses it.
- **`run_email(email_id)`**: wraps every stage. Any exception is stored with its stage and shows
  as `FAILED`. It never overwrites a result a human resolved (unless `force=true`).
- **Reviews:** a `NEEDS_REVIEW` result opens exactly one review with both documents' extracted
  values as evidence. `resolve_review` either takes a verdict (`OK` or `MISMATCH` plus defect
  fields) or corrected values, which it feeds back through `decide()`.
- **Audit:** every failure, retry and resolution is recorded in the `audit` table.
- **Submission guard:** `POST /api/submission/submit` refuses while stubs are active or any
  email failed (override with `?force=true`). It only works when `INBOX_SOURCE` is the
  organizers' HTTP server; with the `data` folder it returns a clear 400.

Where emails come from: `app/inbox.py` reads `INBOX_SOURCE` (default `data`). To use the
organizers' server instead: `export INBOX_SOURCE=http://localhost:8080`.

## 8. Try the human-in-the-loop yourself

1. Open `/reviews-ui`, open the review for `email_506`, choose verdict **MISMATCH**, tick
   `consignee`, click Resolve. Back on `/report` the row says MISMATCH and "(human)".
2. Open the review for `email_507` (the BL is missing), type all 7 BL values, Resolve.
   With the real `decide()` this re-runs the comparison. With the stub it becomes OK.
3. `curl -X POST localhost:8000/api/run` again: both results stay as the human set them.
4. `curl localhost:8000/api/results/email_506` shows the audit trail.
5. Failure and retry: `curl -X POST localhost:8000/api/run/email_999`. It appears under "Failed
   emails" on `/report` with a Retry button (the email does not exist, so it fails at `load_email`).

## 9. Integrating as teammates merge

Every time A, B, C or D merges:

```bash
git pull
python -m unittest discover -s tests -v      # must stay green
curl -X POST localhost:8000/api/run          # human-resolved results are kept
```

Look at `/report`. When both stubs are gone the banner disappears and the submission guard opens.
If a teammate's code crashes the pipeline, the email shows as FAILED with the stage, so you can
tell them exactly where.

## 10. Frontend (your React app)

The React app is still the default starter, so decide who builds it. The JSON API is complete.
The pages at `/report` and `/reviews-ui` are a working demo UI with no build step. To use React,
the backend already allows the Vite dev server (`http://localhost:5173`):

```jsx
useEffect(() => {
  fetch('http://localhost:8000/api/results?category=BL_COMPARISON')
    .then(r => r.json()).then(setRows)
}, [])
```

| Screen | Endpoint |
|---|---|
| summary cards | `GET /api/summary` |
| report table | `GET /api/results?category=BL_COMPARISON` (fields: `status`, `diffs`, `defect_fields`, `review_reason`) |
| review queue | `GET /api/reviews` |
| review detail | `GET /api/reviews/{id}` (`evidence.si`, `evidence.bl`) |
| resolve | `POST /api/reviews/{id}/resolve` with `{"by":"name","note":"...","verdict":"MISMATCH","defect_fields":["consignee"]}` or `{"si_values":{"shipper":"..."},"bl_values":{...}}` |
| failed emails | `GET /api/results?state=FAILED`, then `POST /api/emails/{id}/retry` |
| run all | `POST /api/run` |

## 11. Endpoint cheat sheet

`GET /api/health`, `GET /api/summary`, `POST /api/run`, `POST /api/run/{email_id}`,
`POST /api/emails/{email_id}/retry`, `GET /api/results`, `GET /api/results/{email_id}`,
`GET /api/emails`, `GET /api/reviews`, `GET /api/reviews/{id}`, `POST /api/reviews/{id}/resolve`,
`GET /api/errors`, `GET /api/submission`, `POST /api/submission/submit`.

## 12. Done checklist

- [ ] old Gemini key revoked, new key only in local `.env`
- [ ] `.env` and `.venv` no longer tracked; team warned before pulling
- [ ] patch applied, 11 tests pass, `/report` shows 520 emails and 5 open reviews
- [ ] `server.py` renamed to `prototype_gemini.py`
- [ ] teammates told to replace their stubs and keep the signatures
- [ ] you resolved a review by hand and saw the audit trail
- [ ] a decision made on who builds the React UI
