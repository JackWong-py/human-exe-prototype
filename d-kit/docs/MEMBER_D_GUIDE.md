# Member D guide: field mapping, normalisation and the decision

You own the brain of the comparison. B and C turn documents into `RawDoc` objects; **you turn a
pair of them into a verdict**: `OK`, `MISMATCH` (with the differing fields) or `NEEDS_REVIEW`
(with a reason). Everything the scorer measures about defects passes through your code.

## The project in one minute

The inbox has 520 emails. A classifies them; for the 129 `BL_COMPARISON` emails, the system compares
the Shipping Instruction (SI, the reference) with the draft Bill of Lading (BL) on 7 fields:
`shipper`, `consignee`, `notify_party`, `port_of_loading`, `port_of_discharge`, `container_count`,
`gross_weight_kg`. The same field is labelled differently in different documents ("Port of Loading",
"Load Port", "POL"), so you match by meaning.

## What you own

| File | Job |
|---|---|
| `app/mapping.py` | raw label to one of the 7 fields; picks each field's value out of a `RawDoc` |
| `app/normalize.py` | makes values comparable (names, ports, counts, weights, placeholders) |
| `app/decide.py` | `decide(si, bl) -> CompareResult`: the precedence rules and the field comparison |

The interface must never change: `decide(si, bl)` takes two `RawDoc | None` and returns a
`CompareResult` (see `app/contracts.py`). E's pipeline calls it. Do not edit other people's files.

The kit contains a **tested first version of all three files**. Your job is to understand it,
verify it against the source documents, harden it, and keep it correct as B and C deliver.

## Step 0: setup

From the repo root (the folder with `data/` and `app/`):

```bash
unzip -o /path/to/d-kit.zip
python -m unittest tests.test_decide -v      # expect: Ran 17 tests ... OK
python scripts/decide_report.py | tail -8    # expect the counts in Step 4
```

What the kit adds: `app/mapping.py`, `app/normalize.py`, `app/decide.py` (replaces E's stub),
`fixtures/rawdocs.json`, `scripts/decide_report.py`, `tests/test_decide.py`, `tools/make_fixtures.py`
and this guide in `docs/`.

**One-line heads-up for E.** Once your real `decide()` is merged while B and C are still stubs, one
of E's tests fails, because the stub SI has no values. In `tests/test_pipeline.py`, in
`test_resolution_with_corrected_values_reruns_decide`, change the last call to
`pipeline.resolve_review(rv["id"], si_values=ALL_FIELDS, bl_values=ALL_FIELDS)`. I verified this
makes all 28 tests pass. Also expect that until B and C merge, `/report` shows every BL email as
`NEEDS_REVIEW` (`missing_value`). That is correct: their stubs return no values yet.

## Step 1: the contract you work against

`RawDoc` fields: `path`, `doc_type` (`SI`, `BL`, `OTHER` or `UNKNOWN`), `title`, `pairs`
(a list of `[label, value, evidence]`), `error` (`None` or `"unreadable"`), `noisy` (True if
read by OCR).

`CompareResult` fields: `status`, `has_defect`, `defect_fields`, `review_reason`, `diffs`
(`[{"field", "si", "bl"}]`, values as a human should see them) and `message`.

Conventions you rely on. **Confirm each with B and C in writing:**

1. Labels are passed through **raw** (with Chinese suffixes etc.); mapping is your job.
2. A multi-line value is joined with `" | "`. **Line 1 is the name, the rest is the address.**
3. `doc_type` comes from the document's title, never from the filename.
4. For PDFs that only list containers in a table, C adds synthetic pairs `Container Count`
   (rows counted) and `Gross Weight (KG)` (rows summed).
5. Scans set `noisy=True`; a corrupt file has `error="unreadable"` and `doc_type="UNKNOWN"`.
6. **First pair wins** for each field. E prepends reviewer corrections, so they override readers.

## Step 2: what the data does (measured on the real emails)

- **Defects are substitutions.** A party name is swapped while its address block stays the same;
  a port name is swapped while the old LOCODE stays (16 of 19 port differences keep the SI's code,
  e.g. `TUTICORIN, INDIA (KEMBA)`); a weight loses a digit (`216950` vs `215,950`); a container
  count moves by one. Several fields can differ in one email (013 has 1, 025 has 2, 097 has 2).
- **Compare names, not addresses.** Address text differs only in the "blank SI" emails (516 to 520),
  where the SI has just the name and the BL has the full address. Comparing addresses would create
  false alarms.
- **Container type never differs on its own** (same count means same `40'HC`), so comparing the
  count is enough.
- **Placeholders:** `N/A`, `TBA`, `____MT`, `???`, an empty value. `NET WEIGHT` is a decoy next to
  gross weight and must never be read as it.
- **"To the Order of"** appears where other documents say "Consignee", so it is a consignee alias.
- **OCR noise vs real differences.** On the three scans, noisy values score 0.83 to 1.00 text
  similarity (`AL GUAS` vs `AL GURG`; `NAN TONG GHIMA` vs `NANTONG, CHINA`). Genuinely different
  companies and ports score 0.76 or less. That clean gap is why the OCR threshold is 0.80.

## Step 3: read the three files, in this order

**`mapping.py`.** `RULES` is an ordered list of patterns; the first match wins.
Order matters: `Notify Party/Intermediate Consignee` must reach `notify_party` before the consignee
rule sees it, and `NET WEIGHT` is excluded first. Two bugs already fixed and covered by tests:
`Kinds of Packages; Description of Goods` must **not** map to `container_count` (it silently
replaced blank counts), and `CONTAINER NO.` (a table header) must not either.
`extract_fields` picks the first pair per field, except that a later real value beats an earlier
placeholder.

**`normalize.py`.**

| Field | Rule |
|---|---|
| names | line 1 only; uppercase; punctuation removed; `LIMITED`=`LTD`, `PRIVATE`=`PTE`, `&`=`AND`. A different legal entity **stays different** (`APRIL FINE PAPER TRADING` is not `APRIL FINE PAPER TRADING (MIDDLE EAST) FZE`) |
| ports | name before the comma; LOCODE and bracketed notes ignored; countries compared only if both are present |
| container count | the integer before `x` (`6 x 40'HC` gives 6) |
| weight | strip units and separators (`21,577 KG` gives 21577); `128.544` gives 128544 (a dot followed by 3 digits is a thousands separator); `MT` is multiplied by 1000 |
| placeholder | empty, `N/A`, `TBA`, `TBC`, `____MT`, `???`, `-` |

Golden rule: normalise away **formatting**, never **content**.

**`decide.py`.** Precedence, first rule that applies wins:

1. `missing_attachment`: the SI or the BL is `None`.
2. `wrong_doc_type`: a document is `OTHER` (invoice, packing list, certificate of origin), or the SI and
   BL slots are swapped.
3. `unreadable`: a document has `error`, or is `UNKNOWN` with fewer than 5 recognisable fields.
4. `missing_value`: any of the 7 fields is blank or a placeholder in either document (in a scan this
   is reported as `unreadable`, because the text may just not have been read).
5. Otherwise compare the 7 fields: any difference gives `MISMATCH` with `defect_fields` and `diffs`;
   none gives `OK` ("No mismatch detected").

With OCR involved (`noisy`): similarity at or above 0.80 counts as the same, below 0.55 as
different, in between goes to a human (`NEEDS_REVIEW`, `unreadable`). A number that disagrees is
**never** called a defect on OCR evidence alone, because a misread digit looks exactly like one.

## Step 4: run it and check the numbers

```bash
python scripts/decide_report.py               # one line per email + a summary
python scripts/decide_report.py --only mismatch
python scripts/decide_report.py --email email_097    # field-by-field detail
```

Expected summary for the 129 BL emails: **66 OK, 46 MISMATCH, 5 wrong_doc_type,
5 missing_attachment, 5 missing_value, 2 unreadable** (the two corrupt PDFs, 511 and 515). The
three scans (512 to 514) come out `OK`. If your numbers differ after a change, find out why before
moving on.

Note: `app/GUIDES.md` says email 097 "should flag `gross_weight_kg`". That is incomplete; 097 also
differs in `container_count` (10 vs 11). The tests use the correct answer.

## Step 5: verify by eye (the most valuable hour you will spend)

I have no answer key, so **you** are the check. Open `--only mismatch`. For each of the 46, open
the two source files in `data/attachments/` and confirm the difference is real and not formatting.
Then answer these judgement calls and write the decision in a code comment:

1. `email_145`: shipper `APRIL FINE PAPER TRADING` vs `APRIL FINE PAPER TRADING (MIDDLE EAST) FZE`. I
   treat it as a different entity (the address block was kept from the original, which is how the
   other planted defects look). Agree?
2. A mismatch **and** a blank value in the same email: today `NEEDS_REVIEW / missing_value` wins.
   Would a reviewer prefer `MISMATCH`? A can test it with `/submit` on emails 516 to 520.
3. Should the three scans really be `OK`? They look like clean documents with OCR noise. If C's
   OCR gets noisier, expect `NEEDS_REVIEW` instead. That is the safe direction.

Every fix gets a line in `GOLDEN` in `tests/test_decide.py`.

## Step 6: harden

- `UNKNOWN` documents: decide whether 5 recognisable fields is the right bar.
- A LOCODE that contradicts the port name inside one document is an extra tell. Optional.
- Values that contain two fields on one line, or numbers with units you have not seen (`LBS`).
- If the same field appears twice with different values, decide which wins and test it.

## Step 7: stay in sync with B and C

Your fixtures were made by rough readers in `tools/make_fixtures.py` (B and C may borrow ideas, but
it is not production code). When B's and C's real readers land:

```bash
python scripts/decide_report.py --compare
```

It lists every email whose result differs between the fixtures and the real readers. Each difference
is either a **reader bug** (tell B or C which email and which field) or a **fixture error** (fix
`fixtures/rawdocs.json`). The goal is zero differences. Then run `--live` and re-run the tests.

Useful for them: `mapping.unmapped_labels(raw)` lists the labels in a document that map to none of
the 7 fields.

## Step 8: with A and E

- **A** runs `/submit` experiments. Give A the two open questions from Step 5 (2 and 3) as
  experiments. After each real score run, look at the emails whose result changed and check them.
- **E** shows your `diffs` side by side in the report and lets a reviewer correct values. Those
  corrections arrive as first-position pairs with the labels in `CANONICAL_LABELS`, so your mapping must
  keep understanding `Shipper`, `Consignee`, `Notify Party`, `Port of Loading`,
  `Port of Discharge`, `Container Count`, `Gross Weight (KG)`. The tests cover this.

## What I could not verify

- There is no answer key, so the expected results in `GOLDEN` are my reading of the documents, not
  the organizers' truth.
- The OCR threshold is calibrated on only three scans.
- The fixtures come from my rough readers, so they may differ slightly from B's and C's output.

## Done checklist

- [ ] `python -m unittest tests.test_decide` passes (17 tests)
- [ ] you reviewed all 46 mismatches against the source files
- [ ] the three judgement calls in Step 5 are decided and commented
- [ ] B and C agreed the six conventions in Step 1
- [ ] `decide_report.py --compare` shows 0 differences once B and C have merged
- [ ] every wrong decision you fixed has a `GOLDEN` line
