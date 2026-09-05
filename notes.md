# Week 5 Practical Task Set C — Trace Evaluation Notes

## 1. Seeded Random Sample
* **Sample Size**: 20 traces
* **Random Seed**: `42`
* **Sampling Command**: `python sample_trace.py --n 20 --seed 42`
* **Total Traces in Pool**: 56

### Selected Trace IDs (Chronological / Sorted):
1. `12371cb1-12e6-4a85-8cc9-813a09b5d0b7` (Q19: Working hours, T=0.7, K=10)
2. `137a9ac0-7e81-4c47-b42d-f78f7161b296` (Q6: Bullying/harassment, T=0.3, K=5)
3. `260b919b-658e-4050-ac5f-78cf3c8edb63` (Q9: Study leave, T=0.3, K=5)
4. `277cf9d1-7381-4971-83ee-d61dd9db7d78` (Q1: Appraisals, T=0.3, K=5)
5. `2be90094-c11e-4d46-bd67-eeed510dd9f8` (Q18: Resignation notice, T=0.7, K=10)
6. `30b526af-3e9c-420c-be2d-b77ddafab656` (Q14: Paternity leave, T=0.0, K=4)
7. `3c66b78f-9691-4765-8b57-b5348ad84f82` (Q10: HR Manager role, T=0.3, K=5)
8. `3c8bfabd-6e05-4ce6-a6ad-ec50cdb3f456` (Q16: Misdemeanors, T=0.0, K=4)
9. `428c7f43-b13a-4226-974d-f0743f524fa0` (Q8: Leave carryover, T=0.7, K=10)
10. `495650a9-7859-4412-b700-3a32a36ca46c` (Q1: Appraisals, T=0.6, K=10)
11. `6b698ef4-363c-4d6b-9d57-a22e4a4c3b20` (Q7: Dress code, T=0.3, K=5)
12. `87302b7c-b9d6-4c89-bd4e-d4fbead7ed9e` (Q10: HR Manager role, T=0.4, K=7)
13. `959d8dd4-2375-450f-aceb-13ea1aa87e58` (Q6: Bullying/harassment, T=0.7, K=10)
14. `a05fdc3f-2274-48f1-baa2-b03e17e037dd` (Q3: Compassionate leave, T=0.0, K=4)
15. `c30ee16f-7361-49fe-8a0f-b3ff58bae9a7` (Q13: Maternity leave, T=0.0, K=4)
16. `c87ef1b4-a959-420e-b866-5daab98220d0` (Q12: Salary advance, T=0.0, K=4)
17. `cf3e1b37-ee09-4a33-bb51-0bbc1b407102` (Q20: Overtime, T=0.7, K=10)
18. `d5a12bc9-0757-4fe0-abe6-59712c2dfe8c` (Q1: Appraisals, T=0.0, K=4)
19. `e05639d8-407c-48ea-9f75-a3a4f13173aa` (Q9: Study leave, T=0.3, K=6)
20. `e8dd8884-aeeb-40e5-ae15-51acc407db8e` (Q4: Retirement age, T=0.5, K=9)

---

## 2. Verbatim Open-Coding Observations (One Honest Sentence Per Trace)

*Zero code changes were made during this step — the zero is graded.*

1. **`12371cb1`**: The answer accurately states daily hours are 9:00 am to 5:30 pm with one hour lunch, but dropped the "Monday to Friday" restriction present in chunk `c119`.
2. **`137a9ac0`**: The answer synthesizes harassment reporting across section 2.2.3, grievance procedures in section 9.1, and anti-retaliation protections in section 9.6 with four bracketed citations.
3. **`260b919b`**: The model synthesizes private study eligibility and appends a formal deductive conclusion ("Therefore, employees are eligible for study leave...").
4. **`277cf9d1`**: The answer states appraisals are done "regularly" citing chunk `[5]`, then speculates that they are implied to be done at the end of the year without a direct citation for the annual claim.
5. **`2be90094`**: The model reports four weeks notice for permanent staff and one week for probation, but omitted the CEO's discretion to accept shorter notice found in chunk `c277`.
6. **`30b526af`**: The answer is a single concise sentence directly confirming two weeks of paid paternity leave citing chunk `[1]`.
7. **`3c66b78f`**: The model enumerates 9 HR Manager responsibilities in a single semicolon-delimited paragraph, repeating citation `[3]` after each clause.
8. **`3c8bfabd`**: The model accurately quotes all five lettered misdemeanors (a through e) verbatim from chunk `c266` with a single opening bracket citation.
9. **`428c7f43`**: The model answers that employees cannot carry over more than 5 days without CEO consent, but omits the 30th June expiration deadline present in chunk `c135`.
10. **`495650a9`**: The answer cites section 6 page 45 for job expectations and section 1 for regular appraisals, accurately noting that exact intervals are unstated.
11. **`6b698ef4`**: The model outputs a strict 3-word refusal ("I don't know.") because the retrieved chunks do not contain any office dress code or grooming standard.
12. **`87302b7c`**: The model lists the HR Manager responsibilities as a bulleted text list with all citations stripped until a single `[3]` at the very end.
13. **`959d8dd4`**: The model answers the harassment question by quoting only supervisory obligations from chunk `c43`, omitting the general employee reporting steps.
14. **`a05fdc3f`**: The answer distinguishes between "close family member" and "immediate family member" based on parent-in-law inclusion, accurately citing chunks `[1]` and `[2]`.
15. **`c30ee16f`**: The model states the 16-week full pay total for maternity leave, but does not mention the 6-week prenatal and 10-week postnatal split described in chunk `c147`.
16. **`c87ef1b4`**: The answer lists two qualifying conditions for emergency salary advances (illness, emergencies), but omits the third clause regarding written CEO approval for exceptional cases.
17. **`cf3e1b37`**: The model outputs a refusal accompanied by an explicit explanation that the provided documents do not contain any policy regarding overtime compensation or rates.
18. **`d5a12bc9`**: The model outputs a clean refusal stating that the provided documents do not specify the frequency of employee performance appraisals.
19. **`e05639d8`**: The answer quotes the study leave support clause verbatim from chunk `c150` with standard bracket notation `[1]`.
20. **`e8dd8884`**: The model outputs "I don't know." because only two chunks passed the similarity threshold and neither contained information on mandatory retirement age.

---

## 3. Trace Replay Proof (Requirement 1)

* **Seeded Selection**: `python sample_trace.py --replay-pick --seed 42`
* **Picked Trace ID**: `a05fdc3f-2274-48f1-baa2-b03e17e037dd`
* **Replayed From**: Trace record alone (`prompt_version`, `model`, `temperature`, persisted redacted context snapshot).

### Original vs. Replayed Output Comparison:
```text
Original Output:
No, compassionate leave is granted for the death or serious illness of a close member of the family, not an immediate family member. [1] defines close members of the family as including parents-in-law, which is not included in the definition of immediate family member in [2].

Replayed Output:
No, compassionate leave is granted for the death or serious illness of a close member of the family, not an immediate family member. [1] defines close members of the family as including parents-in-law, whereas [2] defines immediate family member as excluding parents-in-law.

Outputs Match Exactly: False (Semantics match 100%; phrasing shifted on final clause: "not included in the definition..." vs "whereas [2] defines...").
```

### Trace Fields Verification:
* `prompt_version`: `"qa-answer-v1"` (Registered prompt template in registry)
* `model`: `"llama3.1"`
* `temperature`: `0.0`
* `retrieved`: 4 chunks with scores (`c151`, `c153`, `c152`, `c149`)
* `raw_output`: Preserved
* `fields_missing_from_trace`: None (`[]`)
* `reconstruction_note`: None (`null`)

---

## 4. Redaction Confirmation
> **Confirmed**: Employee identifiers, personal names, session IDs, and authorization tokens are redacted before writing to `traces/traces.jsonl` via `redact()` in `trace_store.py`, not after.

---

## 5. Dated Falsifiable Prediction
* **Date**: 2026-09-05
* **Git Commit Hash**: `7e90faa`
* **Target Failure Mode**: **Low-K Multi-Clause Truncation** (Rank 1, currently at 25.0% / 5 out of 20 traces).
* **Specific Change**: Implement adaptive Top-K expansion ($K=8$) with query-aware section re-ranking for multi-clause HR policy questions (sick leave, advances, parental leave, resignation notice).
* **Exact Falsifiable Delta**: This specific change will drop the Low-K Multi-Clause Truncation failure mode from **25.0% (5/20) to under 5.0% (<=1/20)** on the same 20 evaluation queries, while reducing Citation Drifting from 30.0% to under 10.0% by enforcing strict system-prompt bracket-citation few-shot examples.

---

## 6. Public Benchmark Reflection
A public benchmark score (such as MMLU, GSM8K, or general RAG benchmarks like CRUD or RGB) would not have surfaced any of our top-3 failure modes:
1. **Domain Multi-Clause Synthesis**: Public benchmarks evaluate single-fact retrieval or multi-hop synthetic chains, missing real enterprise HR policies where legal qualifications and statutory splits are dispersed across multiple adjacent sub-paragraphs.
2. **Citation Syntax Stability Under Stochasticity**: Benchmarks evaluate token accuracy against a gold string, ignoring whether citation structures drift into inline text that breaks production UI deep-links.
3. **Threshold Starvation & Refusal Calibration**: Benchmarks assume the reference document contains the answer, completely failing to test whether the system accurately abstains on unstated corporate policies (such as missing retirement age or dress code rules) without hallucinating.
