# human.exe: shipping document verification

Reads an inbox of shipping emails, sorts each one into a category and, for the "please check
this draft BL against the SI" requests, compares the two documents on 7 fields (shipper,
consignee, notify party, port of loading, port of discharge, container count, gross weight).
Anything it cannot decide goes to a person, with the evidence, and the report updates when the
person answers.

## Run it

With Docker (the first start processes all 520 emails, so the report is filled):

    docker compose up --build
    open http://localhost:8000/report

Without Docker:

    python3 -m venv .venv && source .venv/bin/activate
    pip install -r requirements.txt
    sudo apt install tesseract-ocr          # reads the scanned PDFs
    uvicorn app.api:app --port 8000
    curl -X POST localhost:8000/api/run     # process every email

Pages: `/report`, `/reviews-ui` (the human review queue), `/docs` (the API).

## Where the emails come from

`INBOX_SOURCE` decides. By default it is the `data/` folder (a copy of the organizers' bundle).
Set `INBOX_SOURCE=http://localhost:8080` to read from the organizers' server instead. Only the
server can score a submission: `POST /api/submission/submit`.

## How it works

1. `app/classify.py` sorts each email (BL_COMPARISON, SI_REQUEST, INVOICE_QUERY, GENERAL, SPAM).
2. For BL_COMPARISON emails `app/readers/` reads the SI and BL (txt, xlsx, docx, PDF, scanned PDF).
3. `app/mapping.py`, `app/normalize.py` and `app/decide.py` compare them: OK, MISMATCH, or
   NEEDS_REVIEW (missing attachment, wrong document, unreadable, missing value).
4. `app/pipeline.py` and `app/db.py` store every result, open a review for each NEEDS_REVIEW,
   record failures visibly and allow retries. `app/api.py` serves it all.

## Check that everything fits together

    python -m unittest discover -s tests
    python scripts/check_contracts.py       # 14 checks, and the totals for the whole inbox
