<!-- Soft Suave · The AI Engineering League -->
# Week 6 Practical — Task Set C

## Validate the policy-answer judge before you trust its number

| | |
|---|---|
| Domain | HR policy |
| Week | 6 — Evals — Measuring Whether a Change Actually Helped |
| Module | M3 — Evals & Error Analysis · THE CORE |
| Sat on | Week 7 · Monday |
| Marks | 100 |

> **This is an extension of the app you already built in Week 6.** It is not a build from scratch, and it tests only this week's concepts. Bring your numbers written down.


---

## 1. Problem statement

Your eval prints a correctness score for every answer your HR assistant gives about the handbook, and that whole number comes out of an LLM judge nobody has ever checked against a human. HR is about to sign off on self-service using that score. Prove the judge agrees with you — or find out it doesn't — and move the agreement figure with evidence.


---

## 2. Requirements

1. Bring the eval set to 25+ cases, each tagged with one Week-5 taxonomy mode, and add at least 2 regression cases replayed verbatim from real failed handbook traces; one command still runs everything and prints pass rate by mode.
2. Move at least 2 criteria out of the judge and into deterministic assertions (a policy section reference is present and resolves to a real section, the handbook version is cited, the notice-period figure is numeric, an out-of-jurisdiction question triggers the refusal path) and delete those criteria from the judge prompt; report the count of assertions vs judged criteria.
3. Hand-label 25 answers blind on the judge's single binary criterion and save the labels to a file BEFORE the judge is run — the file's commit or timestamp must prove the ordering.
4. Run the judge, compute agreement with your labels as a percentage, then iterate the judge prompt using 2 of its OWN disagreements as few-shot examples and re-measure; report agreement before -> after as two numbers.
5. File a one-sentence written prediction of what the iteration would fix BEFORE iterating, then report where the prediction was wrong.


---

## 3. Expected output

labels_25.json (committed first), judge_v1.txt and judge_v2.txt, prediction.txt, the one-command eval table (pass rate by mode), agreement_before and agreement_after as numbers, and a short note on 2 disagreements naming who was right.


---

## 4. Evaluation rubric

| Criterion | Points |
|---|---|
| Blind protocol: 25 hand labels exist and provably predate the judge run (commit order / timestamps). No ordering evidence = 0 here, regardless of the numbers. | 25 |
| Agreement measured and reported before -> after, with the iteration driven by the judge's own disagreements as examples | 30 |
| Assertion/judge split: assertable criteria named, implemented as assertions, and removed from the judge prompt | 20 |
| Disagreement analysis: 2+ disagreements read, a verdict on who was right, and the prediction honestly scored against the outcome | 15 |
| Eval still runs in one command over 25+ mode-tagged cases including real regression cases | 10 |
| **Total** | **100** |

*Zero points for polish, UI, or "it works". This mirrors the House rubric: failure-finding and a number that moved are what score.*


---

## 5. Bonus challenge

Add RAGAS faithfulness and context precision to the handbook-backed cases. Find one answer that scores 0.9+ faithfulness while citing a superseded handbook version's section — confidently, faithfully wrong — and show the two numbers plus why the overall average hides it.


---

## 6. Submission checklist

- [ ] labels_25.json with the commit hash or timestamp proving it predates the judge run
- [ ] judge_v1.txt and judge_v2.txt, diffed, with the 2 disagreement examples visible in v2
- [ ] prediction.txt written before the iteration
- [ ] Terminal output of the single eval command showing pass rate by mode
- [ ] agreement_before / agreement_after, plus assertion count vs judged criteria count


---

## 7. Common mistakes

- **Running the judge first, reading its verdicts, then writing 25 labels — that is not validation, that is agreeing with yourself with extra steps.**
- **Reaching 85% by relabelling the answers you disagreed on instead of fixing the judge — you moved the ruler, not the thing being measured.**
- **Paying a model to check whether a section reference resolves or whether the handbook version is cited — `if` and a lookup table do that for free and never have an off day.**
- **Scoring policy correctness 1-10 and calling within-1 a match; the model cannot tell a 6 from a 7 and neither can you, and the tolerance inflates agreement into meaninglessness.**
- **Reporting one overall pass rate; the average will happily hide a regression on the eligibility/tenure mode while the easy leave-entitlement mode carries the number.**


---

*Set C of 6. Sets A–F are equivalent in difficulty and objectives; only the domain differs.*
