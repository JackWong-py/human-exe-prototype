# Run 1: Baseline (Step 5)
### 20260920-154601: first real run

**final_score 0.9539** = 0.30 x classification F1 (0.8463) + 0.20 x defect F1 (1.0000) + 0.50 x end-to-end (1.0000)

| measure | value |
|---|---|
| classification accuracy | 0.8115 |
| end-to-end (defects flagged with the exact fields) | 46 of 46 = 1.0000 |
| defect precision / recall / F1 | 1.000 / 1.000 / 1.000 |
| field-level F1 | 1.000 |
| emails with exactly the right defect fields | 1.000 (of 200 comparable emails) |
| escalation recall / precision (reliability, not in the final score) | 0.850 / 1.000 |

| category | precision | recall | F1 | tp | fp | fn |
|---|---|---|---|---|---|---|
| BL_COMPARISON | 1.000 | 0.586 | 0.739 | 129 | 0 | 91 |
| SI_REQUEST | 0.947 | 1.000 | 0.973 | 125 | 7 | 0 |
| INVOICE_QUERY | 1.000 | 1.000 | 1.000 | 75 | 0 | 0 |
| GENERAL | 0.368 | 0.883 | 0.520 | 53 | 91 | 7 |
| SPAM | 1.000 | 1.000 | 1.000 | 40 | 0 | 0 |

Classification mistakes (real category -> what we said):
- BL_COMPARISON -> GENERAL: 91 emails
- GENERAL -> SI_REQUEST: 7 emails

Review reasons caught: wrong_doc_type 5/5, missing_attachment 5/5, unreadable 2/5, missing_value 5/5

# Run 2: Experiment 1 – chase emails as SI_REQUEST
(same scoreboard output as baseline)
Experiment 1: rejected

# Run 3: Experiment 2 – reminders as GENERAL
(same scoreboard output as baseline)
Experiment 2: rejected

# Run 4: Final
(same scoreboard output as baseline)
Final run: no experiment changes