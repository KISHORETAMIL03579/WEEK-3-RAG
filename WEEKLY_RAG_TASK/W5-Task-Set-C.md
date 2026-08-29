<!-- Soft Suave · The AI Engineering League -->
# Week 5 Practical — Task Set C

## Read 20 real traces and hand back a ranked taxonomy

| | |
|---|---|
| Domain | HR policy |
| Week | 5 — Error Analysis — Reading Traces Like a Professional |
| Module | M3 — Evals & Error Analysis · THE CORE |
| Sat on | Week 6 · Monday |
| Marks | 100 |

> **This is an extension of the app you already built in Week 5.** It is not a build from scratch, and it tests only this week's concepts. Bring your numbers written down.


---

## 1. Problem statement

Your HR assistant has been running all week and your trace file has grown past a thousand lines that nobody has read. The People Ops lead says it 'sometimes quotes the wrong policy', which is not a bug report. Draw a genuinely random sample, read every trace by hand without fixing anything, and turn what you saw into a ranked list your manager can act on.


---

## 2. Requirements

1. Prove your traces are replayable: pick one trace at random by trace_id (seeded, and paste the seed), replay it from the trace alone, and show the replayed output alongside the original. If any field was missing — prompt version, retrieved chunk_ids + scores, model + params, raw output — add it, note it, and say what you could not reconstruct. Confirm no employee names or IDs are written to the trace file unredacted.
2. Draw a RANDOM sample of 20 traces with a seeded selection you paste in the write-up. Not the demo questions, not the ones you remember breaking. Random, and provable.
3. Open-code all 20: one honest sentence per trace describing what you SAW, not what category it belongs to and not what you would fix. 'I don't know why this failed' is a permitted and valuable sentence. Zero code changes during this step — the zero is graded.
4. Cluster your sentences into 4-7 named failure modes. Names must be legible to a stranger: 'cites the superseded 2023 leave policy' beats 'retrieval issue'. Report frequency as a count AND a percent of the 20, plus a severity (creates a legal exposure / merely annoys the employee), plus one example trace_id per mode.
5. Write a falsifiable, dated prediction with numbers: name the ONE mode you will attack next week, the specific change, and the exact delta you expect, e.g. 'filtering on effective_date drops the superseded-policy mode from 30% to under 10%'. Commit it to git with today's date.
6. Write 3 sentences on why a public benchmark score would not have surfaced any of your top-3 modes.


---

## 3. Expected output

A one-page taxonomy.md that fits on one screen: mode name, count, frequency %, severity, example trace_id — 4-7 rows. Plus notes.md with all 20 verbatim open-coding sentences and the seeded sample list, the replay evidence (original vs replayed output for one trace_id), the committed dated prediction (git commit hash included), and the 3-sentence benchmark note.


---

## 4. Evaluation rubric

| Criterion | Points |
|---|---|
| 20 traces from a documented, seeded random sample, plus one trace replayed from the trace alone with the evidence shown | 20 |
| One honest OBSERVATION sentence per trace — descriptions of what happened, not diagnoses, categories, or fixes. Zero fixes applied during coding | 25 |
| 4-7 modes named legibly, each with count, frequency %, severity, and a real example trace_id | 30 |
| A dated, falsifiable prediction with specific numbers, committed to git before any fix | 15 |
| 3 sentences on why a public benchmark would have missed your top modes | 10 |
| **Total** | **100** |

*Zero points for polish, UI, or "it works". This mirrors the House rubric: failure-finding and a number that moved are what score.*


---

## 5. Bonus challenge

Sample 10 MORE traces from your curated demo set — the questions you always show at the People Ops review — and open-code those too. Report the frequency of your top mode in the random sample versus the demo set, as two numbers. Then write the paragraph explaining what your team has been telling itself for the last month.


---

## 6. Submission checklist

- [ ] taxonomy.md: 4-7 modes with count, frequency %, severity, example trace_id — one screen
- [ ] notes.md: 20 verbatim open-coding sentences, one per sampled trace
- [ ] The seeded random sample: seed value and the 20 trace_ids selected
- [ ] Replay evidence: original vs replayed output for one trace_id, plus any field you had to add
- [ ] A one-line confirmation that employee identifiers are redacted before write, not after
- [ ] The dated prediction committed to git, with the commit hash pasted


---

## 7. Common mistakes

- **Deciding your categories first and then reading the traces into them — you will find exactly the modes you expected and nothing else, which is the whole failure this week exists to prevent.**
- **Sampling the 20 questions you already know are broken. A curated sample gives you frequencies that are pure fiction, and frequency is half of your fix order.**
- **Fixing something at trace 6 because it looked like a two-minute change. You now have 14 traces from a different system and a taxonomy describing an app that no longer exists.**
- **Writing 'retrieval issue' or 'hallucination' as a mode name. Neither tells your manager what to do, and both are diagnoses smuggled in as observations — the diagnosis is next week's job.**
- **Predicting 'this should improve things a lot'. Unfalsifiable, so next week you will be unable to be wrong, and being wrong is the only thing that would have taught you anything.**


---

*Set C of 6. Sets A–F are equivalent in difficulty and objectives; only the domain differs.*
