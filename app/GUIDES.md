The trick to working in parallel is to agree on the interfaces first. After that, each person owns separate files and codes against stubs, so nobody waits for anyone else.

## Step 0: everyone, first 30-45 minutes

1. **Repo and ownership:** Create the repo with one file per owner. Nobody edits another person's file without asking, which avoids merge conflicts.
   - `app/classify.py` (A)
   - `app/readers/text.py`, `xlsx.py`, `docx.py` (B)
   - `app/readers/pdf.py`, `scan.py` (C)
   - `app/mapping.py`, `normalize.py`, `decide.py` (D)
   - `app/api.py`, `db.py`, `pipeline.py` (E)
2. **Agree these five signatures:**
   - `classify(email) -> (category, confidence)` (A)
   - `read_document(path) -> RawDoc` (B, which calls C's `read_pdf`)
   - `find_si_bl(email) -> (RawDoc | None, RawDoc | None)` (B)
   - `decide(si, bl) -> CompareResult` (D)
   - `run_email(email) -> EmailResult` (E)
3. **Agree the three data shapes:**
   - `RawDoc`: `doc_type` (SI, BL or OTHER), `title`, `pairs` (label, value, source snippet), `error` (`None` or `unreadable`), and `noisy` (True if read by OCR).
   - `CompareResult`: `status`, `has_defect`, `defect_fields`, `review_reason`, and `diffs` (field, SI value, BL value).
   - `EmailResult`: the category plus an optional `CompareResult`.
4. **Golden set:** Each person copies these into `fixtures/`, so everyone tests against the same cases:
   - `email_001`: all fields match.
   - `013`: port mismatch.
   - `097`: weight mismatch.
   - `501`: wrong document type.
   - `507`: BL missing.
   - `511`: corrupt PDF.
   - `512`: scanned PDF.
   - `516`: blank SI value.

E pushes the skeleton with stub functions that return fixed values, so the pipeline runs end to end from minute one. Everyone else replaces their stub.

## A: classifier, submission and scoring

1. Wrap `loader.Inbox` so the source (folder or `http://localhost:8080`) comes from one env var.
2. Write body-first rules. Use the subject only as a tie-breaker, because subjects are decoys.
   - **SPAM:** links, prizes, unpaid customs fees.
   - **BL_COMPARISON:** phrases like "compare the SI and draft BL" or "confirm the BL is in order", usually with attachments.
   - **SI_REQUEST:** "Please find Shipping instruction for…" and "submit SI & AED".
   - **INVOICE_QUERY:** invoice, GR missing, D&D, THC, PGI.
   - **GENERAL:** everything else.
3. Watch the trap: "send the draft BL for checking" with no attachments is not `BL_COMPARISON`.
4. Write `build_submission(results)` so it produces all 520 keys in the sample's shape. For non-BL emails, copy the sample's default values.
5. Write `scripts/score.py`, which runs all emails, writes `submission.json`, calls `inbox.submit()`, and logs the score with a note on what changed. Use it to test the ambiguous clusters, changing one thing per submission.
6. After the first score, do error analysis with D, then own the demo script and slides.

**Done when:** the category counts look sane and `submission.json` has 520 keys.

## B: readers for txt, xlsx and docx, plus document type

1. **`.txt`:** The first line is the title. Lines look like `Label: value`, indented continuation lines append to the value, and `====` lines are skipped.
2. **`.xlsx`:** Skip the header rows, then read two-column label/value rows. Weights may arrive as numbers, so convert them to strings.
3. **`.docx`:** Read the paragraphs and the table rows. Labels carry Chinese suffixes and cells can hold multiple lines.
4. **Document type from the title, never the filename:**
   - A title containing "INSTRUCTION" means SI.
   - A title containing "BILL OF LADING" means BL.
   - "COMMERCIAL INVOICE", "PACKING LIST" and "CERTIFICATE OF ORIGIN" mean OTHER.
   - `email_501_BL.txt` is really an invoice.
5. **`find_si_bl`:** Use the `_SI` / `_BL` filename only as a slot hint. Return `None` when a document is absent (506-510 have none, or an SI only).
6. Write tests that every txt, xlsx and docx pair yields at least 7 label pairs.

**Done when:** all three formats return `RawDoc`s and the doc-type detector is correct on 501-505.

## C: PDFs, scans and corrupt files

1. Route PDFs first. If `pdftotext` errors or returns empty and the file has no image, it is corrupt. Return `error="unreadable"` (511 and 515).
2. **Text PDFs:** Split label and value on two or more spaces and append indented continuation lines. Handle labels that wrap, where the value sits on the next line.
3. **Container table roll-up:** Count the rows for container count and sum the weights for gross weight. Emit both as synthetic pairs, and flag it if they disagree with a printed total.
4. **Scans:** Extract the embedded image, crop the top half, upscale 3×, threshold around 170, and run Tesseract with `--psm 6`. Set `noisy=True`, because OCR errors like "128.544" and "NAN TONG GHIMA" are expected.
5. **Optional:** Add a vision model as a second reader if you have an API key. If OCR and vision disagree, lower the confidence.
6. Test on the 10 text PDF pairs (059, 160, 208, 273, 313, 351, 407, 411, 434, 499), the 3 scans (512-514), and the 2 corrupt files.

**Done when:** every text PDF yields all 7 fields and the corrupt files are flagged.

## D: mapping, normalisation and decision

Start with hand-written `RawDoc` fixtures so you never wait for B or C.

1. **`mapping.py`:** Map labels to the 7 fields by meaning, after stripping Chinese characters and lowercasing. Ignore `NET WEIGHT`. Treat "To the Order of" as a consignee alias, and check it against the BL in the same email.
2. **`normalize.py`:**
   - Names: compare the first line only, ignoring case and punctuation, with LTD/LIMITED and &/AND treated as equal.
   - Ports: compare the name before the comma and ignore the LOCODE.
   - Container count: the leading integer.
   - Weight: strip separators, and treat blank, `N/A` or `____` as missing.
3. **Comparison:** Work field by field, marking each as equal, different or unknown. If `noisy` is set, treat a fuzzy ratio of about 0.85 or higher as equal.
4. **`decide`, in this precedence:**
   1. A missing attachment gives `NEEDS_REVIEW` with `missing_attachment`.
   2. A non-SI/BL document gives `wrong_doc_type`.
   3. A document with an error gives `unreadable`.
   4. A missing value gives `missing_value`.
   5. Otherwise compare, and return `MISMATCH` or `OK`.
5. Write unit tests on the golden set. `013` should flag `port_of_discharge`, `097` should flag `gross_weight_kg`, and `516` should return `missing_value`.
6. Print the diffs for the first 30 mismatches and eyeball them with A.

**Done when:** it runs on all 124 pairs without crashing and the hard set gives the expected reasons.

## E: API, database, review queue and report

1. **Skeleton and stubs:** Push these in Step 0.
2. **SQLite tables:** `results` (category, status, reason, defect fields, diffs, evidence), `reviews` (open or resolved, resolution, audit fields), and `errors` (stage, message, attempt).
3. **`run_email`:** Wrap each stage in try/except. A failure stores the stage and message and shows as `FAILED`, never silently. `POST /emails/{id}/retry` re-runs it.
4. **Endpoints:** Build the API as sketched earlier:
   - `POST /run`
   - `GET /results`
   - `GET /reviews`
   - `POST /reviews/{id}/resolve`
   - `GET /submission`
   - `POST /submission/submit`
5. **Review flow:** Each review item stores the reason plus both documents' extracted values and source snippets. Resolving one applies the corrected values, calls `decide` again, and writes an audit entry.
6. **Report page:** Serve `/report` as simple HTML. It lists each email with its status and the SI and BL values side by side, and shows "No mismatch detected" for OK. Add a small review page with a correction form.
7. Add a Dockerfile and compose file.

**Done when:** `POST /run` covers all 520 emails, failures are visible, and a resolved review updates the report.

## Checkpoints and working rules

- **CP1, walking skeleton:** The txt pairs work end to end and you make the first `/submit`. Everyone merges to `main`.
- **CP2:** xlsx, docx and PDFs work, and the hard set (501-520) gives the right reasons.
- **CP3:** The review queue, retries and report page work.
- **CP4:** Freeze features and rehearse the demo.
- **Rules:** Use small PRs and merge to `main` at least hourly. If you're blocked, code against fixtures and don't wait.
- **Finishing early:** B helps C with the PDFs, A helps D with testing, and C helps E with the review page.

If you tell me how many hours you have, I can put clock times on the checkpoints, and I can also generate the repo skeleton with the shared data classes and stubs so E doesn't have to write it.