# Judge V1 Disagreement Analysis

This document analyzes the disagreements between the Blind Human Ground Truth Labels and the Judge V1 automated evaluations across the 25 HR policy evaluation cases.

---

## 1. Disagreement Summary

* **Total Cases**: 25
* **Agreements**: 17 / 25 (68.00%)
* **Total Disagreements**: 8 cases
* **Analyzed Disagreements**: 2 key representative exemplars selected for few-shot prompt iteration.

| Case ID | Trace ID | Question | Taxonomy Mode | Human Label | Judge V1 | Who Was Correct? |
| :--- | :--- | :--- | :--- | :---: | :---: | :--- |
| **`case_03`** | `c87ef1b4` | Under what conditions can a staff member apply for an emergency salary advance? | Low-K Multi-Clause Truncation | **0** (Fail) | **1** (Pass) | **Human** |
| **`case_18`** | `57b6a4af` | Who is eligible for overtime compensation and how is the rate determined? | Unstated Policy Invariant Refusal | **1** (Pass) | **0** (Fail) | **Human** |

---

## 2. Detailed Disagreement Inspections

### Disagreement 1: `case_03` (Trace ID: `c87ef1b4-a959-420e-b866-5daab98220d0`)

* **Question**: "Under what conditions can a staff member apply for an emergency salary advance?"
* **Taxonomy Failure Mode**: `Low-K Multi-Clause Truncation`
* **Human Label**: `0` (Incorrect / Incomplete)
* **Judge V1 Label**: `1` (Correct)
* **Assistant Answer**:
  > "According to [2], a staff member can apply for an emergency salary advance in the following conditions:
  > * In cases of serious illness;
  > * In legitimate emergencies."
* **Handbook Evidence Context** (`Section 4.2.1 Emergency Salary Advance`, page 24):
  > "4.2.1 An emergency salary advance may be granted to a staff member under the following conditions:
  > a) in cases of serious illness;
  > b) in legitimate emergencies;
  > c) in exceptional and compelling circumstances, if supported by a detailed justification in writing, and approved by the CEO."
* **Verdict on Who Was Right**: **Human was right**.
* **Explanation**:
  Judge V1 awarded a `1` because conditions (a) and (b) matched text in the excerpt. However, the policy explicitly provides a three-tier condition set including condition (c) — exceptional circumstances requiring written justification and CEO authorization. By presenting a truncated two-item list as the complete set of conditions, the answer misleads employees regarding escalation pathways for non-medical/non-emergency compelling circumstances. The human evaluator properly labeled this truncated response `0`.

---

### Disagreement 2: `case_18` (Trace ID: `57b6a4af-6eb3-4ee1-b0be-3c6c9a35e406`)

* **Question**: "Who is eligible for overtime compensation and how is the rate determined?"
* **Taxonomy Failure Mode**: `Unstated Policy Invariant Refusal`
* **Human Label**: `1` (Correct Refusal)
* **Judge V1 Label**: `0` (Incorrect)
* **Assistant Answer**:
  > "I don't know."
* **Handbook Evidence Context** (`Section 4.1 Remuneration`, page 23):
  > The retrieved context covers salary bands, annual increments, and payroll dates, but contains zero clauses defining overtime compensation or overtime hourly rates.
* **Verdict on Who Was Right**: **Human was right**.
* **Explanation**:
  The GESCI HR Policy Manual does not contain an overtime compensation policy. When asked an unstated policy question, the RAG assistant accurately executed a strict refusal (`"I don't know."`), preventing hallucinated pay rates or fabricated eligibility criteria. Judge V1 incorrectly penalized this response with a `0` because it failed to recognize that an unstated policy inquiry requires refusal and that refusing is the 100% factually correct behavior. The human evaluator properly labeled this valid refusal `1`.

---

## 3. Disagreement Root Causes

1. **False-Positive Bias on Truncation**: Judge V1 marked answers `1` when they quoted partial sub-clauses, ignoring missing mandatory conditions.
2. **False-Negative Bias on Unstated Policy Refusals**: Judge V1 marked `"I don't know."` as `0` even when the handbook context contained no answer, penalizing faithful refusal behavior.

---

## 4. Prompt Iteration Strategy for Judge V2

Judge V2 must incorporate explicit few-shot exemplars addressing both error patterns:
1. An exemplar demonstrating that an unstated policy question answered with `"I don't know."` is **correct (`1`)**.
2. An exemplar demonstrating that an incomplete condition list omitting the 3rd clause is **incorrect (`0`)**.
