# RAG Evaluation Self-Review Skill

## Purpose

Perform an independent self-review of all changes made to the RAG
retrieval evaluation system before declaring the task complete.

Do not assume that code working in the UI means the evaluation is
correct.

The review must validate:

1. Functional correctness
2. Retrieval metric correctness
3. Ablation correctness
4. API contract consistency
5. Ground-truth correctness
6. Error handling
7. Security
8. Maintainability
9. Regression risk
10. Test coverage

---

## Step 1 — Understand the architecture

Before reviewing changes, identify:

- frontend evaluation page
- evaluation API endpoint
- retrieval functions
- BM25 implementation
- Qdrant retrieval
- weighted blending
- RRF
- reranking
- query rewriting
- ground-truth matching
- Recall@K calculation
- MRR calculation

Trace the complete flow:

UI
→ API
→ validation
→ retrieval
→ ranking
→ evaluation
→ response
→ UI

Do not review individual files in isolation.

---

## Step 2 — Check API contract

Verify that:

- frontend field names exactly match backend field names
- there are no duplicate fields representing the same concept
- top_k/k are not both used unless explicitly required
- strategy_filter/chunk_mode are not both used unless explicitly required
- preset/stage names match exactly between frontend and backend
- request validation exists
- response schema is stable

Report every mismatch.

---

## Step 3 — Check evaluation correctness

Verify:

### Recall@K

Correct formula:

hits / total_questions

Check that:

- every question is evaluated
- missing results are not silently treated as success
- top-K is actually respected
- duplicate documents/chunks are handled correctly
- ground truth is matched correctly

### MRR

For every question:

rank = first relevant result position

reciprocal_rank = 1 / rank

If not found:

reciprocal_rank = 0

MRR:

sum(reciprocal_rank) / total_questions

Check the implementation manually.

Never trust variable names alone.

---

## Step 4 — Check ground truth

Determine whether evaluation is:

- document-level
- section-level
- chunk-level

The UI description and implementation must agree.

Reject ambiguous behavior where:

UI says "section"
but backend only checks filename.

If document-level evaluation is intentional,
call the metric Document Recall@K.

---

## Step 5 — Check ablation logic

Verify that every stage is a real retrieval configuration.

Expected progression:

TF-IDF
→ BM25 + Qdrant weighted blend
→ BM25 + Qdrant RRF
→ RRF + reranking
→ RRF + reranking + query rewriting

Check that:

- each stage actually changes the retrieval pipeline
- stages are not only renamed UI options
- dependencies are respected
- the same question set is used for every stage
- the same Top-K is used
- the same ground truth is used

Do not accept fake ablation results.

---

## Step 6 — Check result alignment

For every question:

- question ID must remain stable
- result must belong to the correct question
- strategy result must belong to the correct strategy
- rank must refer to the correct result
- missing results must be explicit

Never rely only on array position if IDs are available.

---

## Step 7 — Check security

Search for:

- dangerouslySetInnerHTML
- innerHTML
- eval
- Function()
- document.write
- unsanitized HTML
- user input inserted into HTML
- user input inserted into JavaScript
- unsafe URL handling

Any user/API-controlled value rendered as HTML must be treated as a security issue.

Prefer normal React text rendering.

---

## Step 8 — Check React state management

Look for:

- mutation of state objects
- array index used as key
- uncontrolled/controlled input problems
- event bubbling bugs
- inaccessible interactive elements
- duplicate state
- unnecessary state
- stale closures

Prefer immutable updates.

---

## Step 9 — Check validation

Verify:

- at least one question is required
- every question has ground truth
- Top-K is an integer
- Top-K has a reasonable upper bound
- at least one strategy is selected
- invalid strategy names are rejected
- empty requests are rejected

Errors must tell the developer/user exactly what is wrong.

---

## Step 10 — Check error handling

Test:

- backend 400
- backend 404
- backend 500
- non-JSON response
- timeout
- network failure
- empty retrieval result
- empty Qdrant result
- missing embedding
- reranker failure
- query rewriting failure

Do not convert every failure into a generic "Network Error".

---

## Step 11 — Check performance

Look for:

- repeated embedding calls
- repeated index creation
- unnecessary Qdrant requests
- sequential requests that could be batched
- reranking more candidates than necessary
- query rewriting more times than necessary

Estimate cost:

number_of_questions
× number_of_strategies
× embedding_calls
× reranker_calls
× rewrite_calls

Report expensive operations.

---

## Step 12 — Check regression risk

Compare the changed code against the previous behavior.

Verify:

- /ask still works
- normal retrieval still works
- Qdrant retrieval still works
- BM25 still works
- RRF still works
- reranking does not change unrelated behavior
- query rewriting failures do not break the entire request

---

## Step 13 — Run adversarial test cases

Test at minimum:

1. Exact filename question
2. Exact error-code question
3. Exact numeric question
4. Paraphrased question
5. Conceptual question
6. Question whose answer is absent
7. Question with wrong expected document
8. Empty expected value
9. Duplicate question
10. Very long question
11. Special HTML characters
12. Malicious-looking HTML input
13. No Qdrant results
14. No BM25 results
15. Reranker failure
16. Query rewrite failure

---

## Step 14 — Review metrics manually

For a small hand-created dataset, manually calculate:

Recall@K
MRR

Then compare the manual result against the application's result.

If they differ, the implementation is wrong.

---

## Step 15 — Final self-review report

Before declaring the task complete, produce:

### Summary

- What changed
- Why it changed

### Findings

| Severity | File | Issue | Impact | Recommendation |
|----------|------|-------|--------|----------------|

Severity:

P0 = correctness/security blocker
P1 = major issue
P2 = moderate issue
P3 = minor improvement

### Evaluation correctness

- Recall@K: PASS/FAIL
- MRR: PASS/FAIL
- Ground truth: PASS/FAIL
- Ablation: PASS/FAIL
- Result alignment: PASS/FAIL

### Security

- XSS: PASS/FAIL
- unsafe DOM: PASS/FAIL
- input validation: PASS/FAIL

### Regression

- Existing retrieval: PASS/FAIL
- API compatibility: PASS/FAIL
- UI behavior: PASS/FAIL

### Final verdict

Choose exactly one:

PASS
PASS WITH WARNINGS
FAIL — CHANGES REQUIRED

Never declare PASS if any P0 or P1 issue remains.

---

## Important rule

Do not modify code during the self-review unless explicitly instructed.

First identify and report problems.

After the developer fixes the problems,
run the self-review again from the beginning.

Do not assume previous fixes are correct.