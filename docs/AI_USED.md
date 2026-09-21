# How AI was used in this project

## In the product

AI is used in two optional places. It never decides whether two documents match.

**1. Scan reader** (`app/readers/scan.py`)
- **What it does:** scanned PDFs have no text, so we read them with OCR (Tesseract). If OCR finds fewer than 7 fields or is unsure, a Gemini vision model reads the page as a fallback. The setting `SCAN_VISION` chooses `off`, `fallback` (the default) or `always`.
- **What we measured:** we compared both readers on our 6 scanned pages. OCR and the model agreed on 35 of 42 fields. Against what is printed on the three pages we read by eye, OCR read 21 of 21 fields correctly and the model 14 of 21. The model returned no fields for one page. The whole test used 6 requests.
- **What we decided:** OCR stays the default and the model is only a safety net. OCR was enough for all six pages. Details: [AI_SCAN_READER.md](AI_SCAN_READER.md).

**2. AI-drafted replies** (`app/suggest.py`)
- **What it does:** for every case that needs a person (missing attachment, wrong document, unreadable file, blank value, defect), the app drafts an email to the sender.
- **Safety design:**
  1. The facts (file names, field names, values) come from our checks, never from the AI.
  2. A complete template draft is always written first.
  3. The AI may only reword the template. Its answer is checked: if it drops a fact, invents a number, removes the `[Your name]` placeholder or adds a link, the template is used instead.
  4. Nothing is sent automatically. A person reads, edits and sends the draft.
  5. Drafting never changes a result.
- **What we measured:** 12 emails tried, 12 AI drafts accepted by the check, 0 rejected. Details: [AI_DRAFTED_REPLIES.md](AI_DRAFTED_REPLIES.md).
- **Privacy:** the request sends the draft text (the sender's first name, field values and file names) to Google's service.

**Where AI is NOT used:** classifying emails, reading text documents, matching the 7 fields, deciding OK, MISMATCH or NEEDS_REVIEW. These are rules, on purpose, so every result can be explained and repeated. The unit tests never call a real model (they use fake ones).

## In development

We used an AI assistant (Claude) throughout the project.

**What the AI produced**
- The design of the pipeline and how the five of us split the work.
- The first version of much of the code: the backend (API, database, pipeline), the wiring of the readers, the scoring script, the contract checker, the drafted-reply feature and the React frontend.
- Tests, and the guides each teammate followed for their task.
- Help reading the organizers' scoreboard. Its confusion table showed where classification loses points.

**What humans did**
- Ran everything on our own computers (Linux and Windows) and fixed what the assistant could not see: Windows text encoding, Git changing line endings and corrupting one PDF, and a missing Tesseract install.
- Read the source documents to check 78 answers (mismatches, review cases and 15 OK results). Two team members shared the work, and all were confirmed.
- Decided the doubtful cases and kept these rules: a shipper that differs by a company suffix counts as a different company; a blank value means "needs review", not a mismatch.
- Applied every code change on a branch, ran the tests, and merged it. Nothing went to `main` without passing tests.
- Ran classification experiments and kept only changes that improved the official score.

**Mistakes the assistant made, and how we caught them**
- **A tool that made the tests call the real model.** A test helper set `SCAN_VISION=always` and never put it back. Later tests then sent scanned pages to Gemini, and the test run looked stuck. We noticed the SDK's notice in the output, found the leak and fixed it.
- **A score script that only classified.** An early scoring script never compared the documents, so every BL email would have been submitted as OK. It was caught by reading the script before the first scoring run.
- **A wrong statement in our own guide.** It said the tests pass without Tesseract. A Windows teammate's run showed two tests fail, and we corrected the guide.
- **A wrong guess about the API key.** The assistant suspected the key type, but the real cause was a misspelled model name. A short test script showed the key worked.

**What we did not trust the AI for**
- The final numbers. They come from the organizers' scoreboard and our own test runs, not from the assistant.
- Anything about outside services (Vercel, Gemini, shadcn/ui). We treated it as untested until someone ran it.
- The comparison itself: the assistant never decides OK or MISMATCH.

## In deployment

- The app runs as one container on Vercel, built from `Dockerfile.vercel` (live address: <LIVE URL>, checked on <DATE>).
- The Gemini key and model name are in Vercel's environment settings. They are not in the code or the repository (`.env` is ignored by Git). A key that leaked earlier was revoked and replaced.
- Both AI features can be switched off (`SCAN_VISION=off`, `SUGGEST_AI=off`). If the AI service is unavailable, the app falls back to OCR and to the plain template, so it keeps working.
- The assistant wrote the Dockerfile and the deployment steps. A team member ran them and checked the live app with `scripts/check_deploy.py`.