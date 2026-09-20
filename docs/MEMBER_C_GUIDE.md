# Member C guide: PDFs, scans and corrupt files

You own everything that comes out of a PDF. You turn a PDF attachment into a `RawDoc` (the
label/value pairs D compares). There are three kinds of PDF in this data, and each needs its own
handling: a normal PDF with a text layer, a scanned page that is only a picture, and a corrupt file.

## The project in one minute

The inbox has 520 emails. For the 129 that ask "please compare the SI and the draft BL", the system
reads both documents, compares 7 fields (`shipper`, `consignee`, `notify_party`, `port_of_loading`,
`port_of_discharge`, `container_count`, `gross_weight_kg`), and reports OK, MISMATCH or NEEDS_REVIEW.
B reads `.txt`, `.xlsx` and `.docx`. **You read every `.pdf`**: 28 files, of which 20 are text
PDFs (10 SI + BL pairs), 6 are scans (3 pairs, emails 512 to 514) and 2 are corrupt (511 and 515).

## What you own

| File | Job |
|---|---|
| `app/readers/pdf.py` | `read_pdf(path, data) -> RawDoc`: decides which kind of PDF it is; parses text PDFs |
| `app/readers/scan.py` | `read_scan(path, data) -> RawDoc`: OCR for scanned pages, optional vision-model fallback |
| `app/readers/common.py` | shared helpers: `detect_doc_type(title)` and `unreadable(path, why)` (B should use them too) |

`data` is the file's bytes. B's dispatcher gets them with `inbox.read_bytes(path)`, which works for
the `data` folder and for the organizers' HTTP server. Never open files by path yourself.

The kit contains **working, tested code for all three files**. Your job is to understand it, verify
it against the real documents, harden it, and keep it working as the team merges.

## Step 0: setup

```bash
unzip -o /path/to/c-kit.zip          # from the repo root
sudo apt install tesseract-ocr       # Linux. Windows: install Tesseract, then put its full path in .env as TESSERACT_CMD=...
pip install -r requirements.txt      # pdfplumber, pytesseract and pillow are already listed
pip install reportlab                # optional: only used to build small test PDFs
python -m unittest tests.test_pdf_scan -v      # expect: Ran 28 tests ... OK
python scripts/pdf_report.py | tail -12        # one line per PDF
```

Two of the test groups need other people's work, and skip themselves if it is missing:
the fixture cross-check needs D's kit (`fixtures/rawdocs.json`, `app/mapping.py`,
`app/normalize.py`), and the scan tests need the Tesseract program.

**Why not poppler (`pdftotext`, `pdfimages`)?** The team plan mentioned it. The kit uses only Python
libraries (`pdfplumber`, `pytesseract`, `pillow`), so the only program to install is Tesseract. I
checked that it gives the same values as poppler for all 20 text PDFs (140 field values, 0 differences).

## Step 1: what each kind of PDF must return

| The file is | `read_pdf` returns |
|---|---|
| corrupt, empty, or not a PDF (511, 515) | `RawDoc(error="unreadable", doc_type="UNKNOWN")` with a `Reader note` pair saying why. It never raises. |
| a PDF with a text layer | `RawDoc` with `doc_type` from the title, the raw labels and values, `noisy=False` |
| a scan (no text, but an image) | `RawDoc` with `noisy=True`, canonical labels (`Port of Loading`, ...) |
| no text and no image | `unreadable` |

Conventions D relies on. **Confirm each with D:**

1. Labels are passed through **raw** for text PDFs (D's mapping deals with `Load Port`, `POL`, ...).
   Scan labels are the canonical ones, because OCR damages labels ("Portof", "Notity").
2. A multi-line value is joined with `" | "`. **Line 1 is the name, the rest the address.**
3. `doc_type` comes from the title (`common.detect_doc_type`), never from the filename.
4. If a PDF lists containers in a table but prints no count or total, you add `Container Count`
   and `Gross Weight (KG)` pairs by counting and summing the rows. If it does print them, the printed
   value is used, and a note is added to its evidence if the rows disagree.
5. Scans set `noisy=True`. Then D forgives small text differences and never calls a number
   mismatch a defect on OCR evidence alone.
6. **The first pair for a field wins.** Vision-model pairs are put before OCR pairs for that reason.

## Step 2: read the code, in this order

**`common.py`.** `detect_doc_type` looks at the title with spaces and punctuation ignored, so
`BILL OF LADING`, `BILLOF LADING` and `Bill  of  Lading` all work. "INSTRUCTION" means SI, "BILL OF
LADING" means BL, invoice / packing list / certificate of origin mean OTHER. `fuzzy=True` (for OCR)
also accepts a window that is 85% similar.

**`pdf.py`.** Three ideas, each fixing a real problem I found in this data:

1. *Label and value columns.* Every text PDF has labels at the left and values in a second column
   (x = 170 in these files). `_value_column` finds that column, so it also works if a different PDF
   moves it. A value that continues on the next lines is joined with `" | "`.
2. *Words are kept in writing order, not sorted by position (`use_text_flow=True`).* In some PDFs a
   long label runs into the value on the same line (`Notify Party/Intermediate Consignee` over
   `CERIEX`). Sorting by position interleaves them into `ConsCigEnReIEeX`. Writing order keeps them
   apart. Test: `test_label_that_overflows_into_the_value`.
3. *The container table.* Lines like `GSLB0479748  40'HC  UNCOATED ... PAPER  21,887` are collected as
   rows. They stop the label parsing, and feed the roll-up when a total is not printed. (In this data
   all 20 text PDFs print their totals and every total equals its rows, so the roll-up is a safety
   net. It is tested with synthetic PDFs.)

A bug inside the parser is **not** caught on purpose. E's pipeline then shows the email as FAILED
with the stack trace, instead of hiding a bug behind "unreadable".

**`scan.py`.** The pipeline: render the page at the scan's own resolution, crop to the dark text,
upscale to about 450 dpi with LANCZOS, make it black and white at threshold 170, run Tesseract
(`--psm 6`), then match each line's first words to a label with fuzzy matching. Choices that matter:

- **Render at the image's native resolution** (`srcsize` divided by page width), not at 450 dpi
  directly. Rendering at 450 dpi read `128,544` as `126.544`. Native size then LANCZOS gave clean
  text. Do not "simplify" this.
- **Threshold 170** keeps the text and drops the faint "SCANNED COPY - NO OCR TEXT LAYER" watermark.
- **Labels never contain digits.** `Containers 6 x` is the label `Containers` plus the value. Without
  this guard the number was swallowed by the label (a bug I hit and fixed; two tests cover it).
- **Missing Tesseract raises `OcrUnavailable`** instead of returning "unreadable". You want to
  notice at once: the emails show as FAILED in the report, you install it, and press Retry.
- Every OCR pair keeps its raw line and confidence in its evidence:
  `OCR line 8 (confidence 96): Gross Weight 128,544 KG`.

## Step 3: verify against the real files (do this yourself)

I have no answer key, so **you** are the check. I read three scans by eye and the tests use those
values, but you should look at more.

```bash
python scripts/pdf_report.py --file email_208_SI.pdf     # every pair with its evidence
python scripts/pdf_report.py --save-images /tmp/ocr      # saves what Tesseract is shown for each scan
```

1. Open `email_208_SI.pdf` in a PDF viewer and compare it with the report: the notify party is
   `CERIEX`, and the label overlaps it visually.
2. Open `email_411_*` and look at the weight label. In the file it is `TOTAL Gross Weightnn(KGS)`
   (the Chinese characters became junk). Your reader keeps it as is. D's mapping copes.
3. Open `email_514_BL.pdf`. The page itself is smudged on the `Port of Loading` line: the true text
   is `NANTONG, CHINA` and OCR reads `NAN TONG GHIMA`. That is expected, and D's fuzzy match forgives
   it. Do not try to "fix" the OCR to be perfect.
4. Compare the saved images in `/tmp/ocr` with the originals for the six scans.
5. Then run all 15 PDF-based emails through your readers and D's `decide`:
   `python scripts/decide_report.py --live` once B's dispatcher routes PDFs to you. Every result
   should match D's fixtures.

## Step 4: harden

The hidden test data may hold other layouts. In rough order of likelihood:

- **Scans with a different dpi, skew or rotation.** `TARGET_DPI` and the threshold are tuned on six
  files. Try `--save-images` on a scan you make yourself (print one and photograph it).
- **A scan that also has a text layer** (hidden OCR text). `read_pdf` will treat it as a text PDF,
  which is right, but check the fields.
- **Multi-page PDFs.** Handled (pairs from all pages, title from page 1), but only tested lightly.
- **A PDF with a different column position or no multi-line values.** `_value_column` falls back to
  "left edge + 113 points" when nothing starts far to the right. If a layout breaks, print the words'
  `x0` values (see `_lines`) and adjust.
- **Different container-table columns.** `ROW_RX` expects `AAAA1234567  40'HC  ... 21,887`.

Every layout you fix gets a test in `tests/test_pdf_scan.py` (use `make_pdf` to build a small PDF).

## Step 5: optional vision fallback (a Gemini model reads the page)

The team's `prototype_gemini.py` used Gemini for documents. Here it is a **fallback for scans only**,
because OCR is deterministic, free and already correct on all six scans. The vision model is only
asked when OCR finds fewer than 7 fields or is unsure. In `.env` (never committed; `scan.py` loads it, so it also works in tests and scripts):

```
GEMINI_API_KEY=<the NEW key, not the one that was in git>
GEMINI_MODEL=<a model name that works with your key>
SCAN_VISION=fallback        # off | fallback | always
```

- I could **not** test this against the real API (no network here). The logic is tested with a fake
  client (7 tests: never called when OCR is fine, first in `always`, replaces a missing Tesseract,
  a failing model never breaks the pipeline). Try it on one scan with `SCAN_VISION=always` and read
  the pairs with `pdf_report.py --file email_512_SI.pdf`.
- I did not pick a model name for you, because names change. Use one that works with your key.
- A vision reading is put **before** the OCR pairs, and the document stays `noisy=True` so D stays
  cautious. Check that the model copied the text exactly and did not "correct" it.
- Mind privacy and cost: the page image is sent to a third party. Six files is nothing, but decide
  before using it on real documents.

## Step 6: stay in sync with the others

- **B** must call you for PDFs. Give B this, and tell B to use `common.detect_doc_type` and
  `common.unreadable` instead of writing their own:

  ```python
  from .pdf import read_pdf

  def read_document(path, inbox=None):
      data = inbox.read_bytes(path)
      if path.lower().endswith(".pdf"):
          return read_pdf(path, data)
      ...   # B's txt / xlsx / docx readers
  ```
- **D** compares the result. Agree the six conventions in Step 1 in writing. When B has merged,
  D's `python scripts/decide_report.py --compare` shows every email where the real readers differ
  from D's fixtures. Each difference is a reader bug or a fixture error.
- **E** shows any crash as FAILED with a Retry button. If Tesseract is not installed you will see
  the six scan emails fail with a clear message. If E builds a Docker image, it needs
  `apt-get install -y tesseract-ocr`.

## What I could not verify

- The vision fallback against a real model (see Step 5).
- Windows and macOS. Everything here was run on Linux.
- Scans other than the six in the data. The OCR settings are tuned on those.
- The expected values in the scan tests are what I read from three rendered pages by eye, not from
  the organizers' answer key.

## Done checklist

- [ ] `python -m unittest tests.test_pdf_scan` passes (28 tests)
- [ ] Tesseract installed on your machine, and `TESSERACT_CMD` set if you are on Windows
- [ ] you compared at least the 208 SI, the 411 weight label and the 514 BL scan with the originals
- [ ] the six conventions agreed with D; the dispatcher snippet sent to B
- [ ] `decide_report.py --compare` shows no PDF differences once B has merged
- [ ] any layout you fixed has a test; the vision fallback tried on one scan (or deliberately left off)
