---
name: self-review
description: Comprehensive self-review and correction skill for verifying code correctness, running regression tests, and reviewing edge cases before declaring tasks complete.
---

# Self-Review & Correction Skill

## Purpose

Use this skill whenever implementing, correcting, refactoring, or reviewing code.

The goal is to ensure that a code change is not only implemented, but is actually correct, integrated, tested, and compliant with the requested task.

Never declare a task complete immediately after making a code change.

Always perform a self-review and verification cycle first.

---

# Mandatory Workflow

Follow this workflow for every code correction:

```text
Understand Requirement
        ↓
Inspect Existing Code
        ↓
Implement Change
        ↓
Inspect Actual Diff
        ↓
Verify Requirement-by-Requirement
        ↓
Review Integration & Side Effects
        ↓
Review Edge Cases & Security
        ↓
Run Tests
        ↓
Run Runtime / E2E Verification When Applicable
        ↓
Fix Problems Found
        ↓
Run Tests Again
        ↓
Perform Final Self-Review
        ↓
Report Final Status
```

Do not skip a stage unless it is genuinely not applicable.

---

# 1. Requirement Understanding

Before modifying code, determine:

* What exactly is the user asking for?
* What behavior must change?
* What behavior must remain unchanged?
* What are the acceptance criteria?
* What files/components are involved?
* What dependencies are involved?
* What edge cases are relevant?
* Are there security requirements?
* Are there testing requirements?
* Are there ordering constraints?
* Are there restrictions such as "do not modify code yet"?

Do not implement from assumptions when the requirement can be verified from the project/task documentation.

Use the task specification as the source of truth.

---

# 2. Inspect Existing Code Before Changing It

Before making a correction:

1. Locate the existing implementation.
2. Read the complete relevant function/class/component.
3. Inspect its callers.
4. Inspect related dependencies.
5. Inspect existing tests.
6. Inspect configuration.
7. Inspect error handling.
8. Inspect persistence/state management.
9. Inspect related frontend/backend behavior.

Understand why the current implementation behaves as it does.

Do not blindly replace working code.

Prefer the smallest correct change.

---

# 3. Implement the Correction

When making changes:

* Modify only what is required.
* Preserve existing functionality.
* Follow existing project conventions.
* Reuse existing utilities when appropriate.
* Avoid duplicate implementations.
* Avoid dead code.
* Avoid unnecessary abstractions.
* Avoid unrelated refactoring.
* Avoid changing APIs unnecessarily.
* Avoid changing configuration unless required.

If a cleaner architecture is possible but is not required for the task, do not introduce it unnecessarily.

---

# 4. Inspect the Actual Git Diff

Immediately after implementation, inspect the real changes.

Run:

```bash
git status
git diff
```

If changes are staged:

```bash
git diff --cached
```

Review every changed file.

For every change, ask:

* Why was this changed?
* Does it directly support the requirement?
* Is the implementation correct?
* Could it break existing behavior?
* Are error paths handled?
* Are edge cases handled?
* Are inputs validated?
* Are security boundaries preserved?
* Is this change actually necessary?
* Did I accidentally modify unrelated code?

Remove accidental or unrelated changes.

---

# 5. Requirement-by-Requirement Verification

Do not assume that implementation equals completion.

Create an internal verification matrix:

| Requirement   | Implementation | Evidence              | Status            |
| ------------- | -------------- | --------------------- | ----------------- |
| Requirement 1 | File/function  | Test/runtime evidence | PASS/PARTIAL/FAIL |
| Requirement 2 | File/function  | Test/runtime evidence | PASS/PARTIAL/FAIL |

Use these statuses:

### PASS

The requirement is implemented and verified with evidence.

### PARTIAL

Some required behavior exists, but part of the requirement is missing or unverified.

### FAIL

The implementation does not satisfy the requirement.

### NOT VERIFIED

The implementation may exist, but there is insufficient evidence to claim it works.

Never mark something PASS merely because the relevant code exists.

---

# 6. Integration Review

A change is not correct if it works in isolation but breaks the application.

Check affected integrations.

## Backend

Review:

* Routes
* Services
* Storage
* Database/vector store
* Sessions
* Authentication
* Authorization
* Error handling
* Logging
* Configuration

## Frontend

Review:

* API calls
* Request/response handling
* State updates
* Loading states
* Error states
* Cancellation
* Browser behavior
* Existing UI behavior

## Infrastructure

Review:

* Docker
* Docker Compose
* Environment variables
* Volumes
* Health checks
* Worker processes
* External services
* Startup/shutdown behavior

Check every caller of a changed function or interface.

---

# 7. Edge-Case Review

Identify the edge cases relevant to the correction.

## API

Check where applicable:

* Missing input
* Empty input
* Invalid input
* Oversized input
* Unauthorized access
* Wrong session
* Dependency failure
* Timeout
* Malformed response

## RAG

Check where applicable:

* No documents
* No matching chunks
* Low similarity
* Duplicate chunks
* Incorrect chunks
* Conflicting chunks
* Empty answer
* LLM failure
* Embedding failure
* Vector-store failure
* Context overflow
* Citation mismatch

## Persistence

Check where applicable:

* Missing file
* Corrupted file
* Concurrent write
* Partial failure
* Rollback failure
* Process restart
* Worker restart
* Persistence recovery

## Frontend

Check where applicable:

* Network failure
* API failure
* Empty response
* Duplicate request
* Request cancellation
* Browser refresh
* Hard refresh
* Invalid state

Do not test irrelevant edge cases just for the sake of testing, but do not ignore obvious failure paths.

---

# 8. Security Self-Review

For backend or infrastructure changes, explicitly review:

* Authentication
* Authorization
* Session isolation
* Input validation
* Path traversal
* SSRF
* XSS
* CSRF where applicable
* Secret exposure
* PII exposure
* Error-message leakage
* File access
* Prompt injection where applicable

Do not claim stronger security guarantees than the implementation actually provides.

For example:

Do NOT write:

> PII is completely protected.

when the implementation only performs pattern-based redaction.

Instead state:

> Pattern-based best-effort redaction is implemented; complete PII detection is not guaranteed.

---

# 9. Multi-Worker and Concurrency Review

For applications using Flask, Gunicorn, Uvicorn, multiple workers, or multiple processes, explicitly review process-local state.

Never assume that:

```python
GLOBAL_STATE = {}
```

is shared between workers.

Review:

* Shared state
* File writes
* File locking
* Database/vector-store state
* Sessions
* Caches
* Concurrent updates
* Worker restarts
* Race conditions
* Atomicity

If persistence or shared state is affected, verify behavior across processes when practical.

---

# 10. Test the Correction

Run the project's existing tests.

Use the project's documented test command when available.

For Python projects, examples include:

```bash
python -m unittest discover -v
```

or:

```bash
pytest -v
```

For targeted tests:

```bash
python -m unittest <test_module> -v
```

Do not fabricate test output.

Record:

* Command executed
* Tests passed
* Tests failed
* Errors/warnings
* Relevant integration results

Passing tests does not automatically prove the requirement is satisfied.

---

# 11. Runtime Verification

If the correction affects runtime behavior, perform a real runtime test when possible.

Use this general process:

```text
Build
  ↓
Start Application
  ↓
Health Check
  ↓
Exercise Changed Functionality
  ↓
Verify Response
  ↓
Check Logs
  ↓
Restart if Persistence Matters
  ↓
Exercise Functionality Again
```

For Docker-based applications, verify where applicable:

```bash
docker compose config
docker compose build
docker compose up -d
docker compose ps
```

Then exercise the actual changed functionality.

Do not claim:

> Docker deployment works

only because:

> Docker image built successfully.

Build verification and runtime verification are different.

---

# 12. RAG Pipeline Review

For RAG-related changes, verify the relevant complete pipeline:

```text
Document
   ↓
Ingestion
   ↓
Chunking
   ↓
Embedding
   ↓
Vector Store
   ↓
Retrieval
   ↓
Reranking
   ↓
Context Construction
   ↓
LLM Generation
   ↓
Grounded Answer
   ↓
Citations
   ↓
Trace
```

A retrieval change must not accidentally break:

* Upload
* Parsing
* Chunking
* Embedding
* Vector indexing
* Hybrid retrieval
* Reranking
* Context limits
* Generation
* Citations
* Trace logging

Verify the behavior that the correction is intended to change.

---

# 13. Trace and Evaluation Task Review

For trace-analysis tasks, distinguish between:

## Infrastructure

Examples:

* Trace store
* Trace IDs
* Trace sampling
* Replay functionality
* Redaction
* Prompt registry
* Prompt hashing

and:

## Assignment Evidence

Examples:

* Actual seeded sample
* Actual trace IDs
* Actual replay
* Original vs replayed output
* Actual manual observations
* Actual taxonomy
* Actual counts
* Actual percentages
* Actual prediction
* Actual Git commit

The existence of infrastructure does NOT prove that the assignment itself is complete.

Never fabricate missing evidence.

---

# 14. Week-5 Task Set C Special Rules

When working on Week-5 Task Set C, follow the required analysis order.

```text
Generate Real Traces
        ↓
Seed Random Sample of 20
        ↓
Select Replay Trace
        ↓
Replay Trace
        ↓
Read All 20 Traces
        ↓
Write One Observation Per Trace
        ↓
Cluster Observations
        ↓
Create Taxonomy
        ↓
Write Falsifiable Prediction
        ↓
Commit Prediction
        ↓
Only Then Implement Subsequent Fix
```

During the observation stage:

**DO NOT modify application code.**

Do not:

* Fix retrieval
* Fix prompts
* Change chunking
* Change ranking
* Change thresholds
* Change models
* Change evaluation logic

before the required baseline analysis is completed.

The baseline must represent the actual system behavior before the fix.

---

# 15. Observation vs Diagnosis

For manual trace analysis, observations must describe what was actually seen.

Avoid prematurely assigning causes.

BAD:

> Retrieval failure.

BAD:

> Hallucination.

BAD:

> Embedding problem.

BAD:

> Need reranking.

GOOD:

> The answer states 20 leave days while the retrieved policy passage states 25 days.

GOOD:

> The question asks about parental leave, but the retrieved passages discuss annual leave.

GOOD:

> The answer contains a policy requirement that does not appear in any of the retrieved chunks.

The observation should be factual and falsifiable.

"I don't know why this failed" is acceptable when the trace does not reveal the cause.

---

# 16. Verify Quantitative Claims

Whenever numbers appear in the implementation, report, documentation, or evaluation, verify them.

Examples:

* Test count
* Trace count
* Accuracy
* Recall
* Hit rate
* MRR
* Frequency
* Percentage
* Latency
* Chunk count
* Worker count
* Token count

Never trust a copied or hardcoded number without checking its source.

For a 20-trace sample:

```text
1 trace  = 5%
2 traces = 10%
3 traces = 15%
4 traces = 20%
5 traces = 25%
6 traces = 30%
7 traces = 35%
8 traces = 40%
9 traces = 45%
10 traces = 50%
```

Percentages must be calculated from the actual sample.

---

# 17. Documentation Review

After making code changes, inspect relevant documentation.

Check:

* README
* Task documentation
* Configuration examples
* API documentation
* Deployment instructions
* Test instructions
* Comments
* Environment variables

Look for:

* Incorrect commands
* Outdated configuration
* Incorrect endpoint methods
* Old test counts
* Duplicate information
* Missing limitations
* Claims that no longer match the code

Documentation must describe the current implementation.

---

# 18. Check for Secrets and Runtime Artifacts

Before completion, inspect Git state.

Ensure that the change did not accidentally add:

* `.env`
* API keys
* Tokens
* Passwords
* Credentials
* Runtime traces
* Uploaded documents
* Generated vector data
* Logs
* Temporary files
* Debug artifacts

Run:

```bash
git status
git diff --stat
git diff
```

Do not commit secrets or runtime-generated data.

---

# 19. When Self-Review Finds a Problem

If a problem is found during self-review and the task allows correction:

```text
Find Problem
     ↓
Determine Root Cause
     ↓
Correct Problem
     ↓
Run Affected Tests
     ↓
Run Regression Tests
     ↓
Perform Self-Review Again
```

Do not simply report a known correctable problem and declare the task complete.

However, if the task explicitly prohibits changes during the current phase, respect that restriction.

Example:

> "Zero code changes during the 20-trace observation stage."

In that case:

1. Record the issue.
2. Do not modify code.
3. Complete the required analysis.
4. Make the correction only during the permitted correction phase.

---

# 20. Regression Review

After fixing a problem discovered during self-review:

* Re-run the affected tests.
* Re-run the broader test suite when practical.
* Re-check the original requirement.
* Re-check the actual diff.
* Re-check integration.
* Re-check the original failure scenario.

Do not assume the second implementation is correct just because it fixes the first problem.

---

# 21. Final Completion Checklist

Before declaring the task complete:

```text
[ ] Requirement understood correctly
[ ] Existing implementation inspected
[ ] Requested correction implemented
[ ] Actual Git diff reviewed
[ ] No unnecessary changes
[ ] Requirement-by-requirement verification completed
[ ] Integration reviewed
[ ] Edge cases reviewed
[ ] Security reviewed
[ ] Concurrency/multi-worker behavior reviewed where applicable
[ ] Automated tests executed
[ ] Runtime/E2E tests executed where applicable
[ ] Regression tests executed after corrections
[ ] Documentation reviewed
[ ] No secrets committed
[ ] No runtime artifacts committed
[ ] Remaining risks identified
[ ] Final verdict supported by evidence
```

Only declare `COMPLETE` when the evidence supports it.

---

# Final Self-Review Report

After completing the work, provide the following report.

## 1. Implementation Summary

Briefly describe what was changed.

## 2. Requirement Verification

| Requirement   | Status                         | Evidence |
| ------------- | ------------------------------ | -------- |
| Requirement 1 | PASS/PARTIAL/FAIL/NOT VERIFIED | Evidence |
| Requirement 2 | PASS/PARTIAL/FAIL/NOT VERIFIED | Evidence |

## 3. Tests Executed

Include:

* Test command
* Result
* Number passed
* Number failed
* Important runtime/E2E verification

Never fabricate results.

## 4. Problems Found During Self-Review

List:

* Problem
* Root cause
* Correction
* Verification

## 5. Remaining Risks

Use:

* P0 — Blocker
* P1 — High
* P2 — Medium
* P3 — Low

Only report genuine remaining risks.

## 6. Final Verdict

Use exactly one:

* `COMPLETE`
* `COMPLETE WITH WARNINGS`
* `PARTIALLY COMPLETE`
* `NOT COMPLETE`
* `IMPLEMENTED BUT NOT VERIFIED`

Explain the reason briefly.

---

# Critical Rules

1. Never declare completion immediately after implementation.
2. Always inspect the actual Git diff.
3. Always verify requirements against actual behavior.
4. Passing tests alone does not prove correctness.
5. A successful build does not prove runtime correctness.
6. Infrastructure implementation does not prove assignment completion.
7. Never fabricate evidence.
8. Never fabricate tests or test results.
9. Never fabricate trace IDs, outputs, percentages, or commit hashes.
10. Never claim verification that was not actually performed.
11. Do not silently change acceptance criteria.
12. Do not perform unrelated refactoring.
13. Respect zero-change and analysis-only phases.
14. If a correctable problem is found, fix it when permitted.
15. After fixing a problem, test again.
16. After testing again, perform another self-review.
17. Review both positive behavior and failure behavior.
18. Distinguish implementation, testing, runtime verification, and actual task completion.
19. Be explicit about what is proven and what is not proven.
20. Only report `COMPLETE` when evidence supports the claim.

---

# Core Principle

The standard is not:

> "I changed the code and it looks correct."

The standard is:

> "I understood the requirement, inspected the existing implementation, made the correction, reviewed the actual diff, verified the requirement, tested the behavior, checked integration and edge cases, corrected any problems found during self-review, retested, and can provide evidence that the final implementation works."
