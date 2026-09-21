\# AI scan reader

What it does: The AI scan reader uses OCR to extract fields from scanned PDFs. Gemini vision can also read scanned pages when OCR is incomplete or uncertain.

When the model is used: fallback, because OCR performed better than the vision model in the test.

Results on the 6 scanned pages: OCR agreed with the model on 35 of 42 fields. Against what is printed: OCR 21/21, model 14/21.

What went wrong and what we fixed: The vision model returned no fields for one scanned page. No code fix was required.

Cost and privacy: The page image is sent to a third party; 6 requests were made for the whole test.

Limits: Tested on 6 pages only; the model can misread or "correct" text, which is why OCR stays as the default and results stay marked as scanned.

