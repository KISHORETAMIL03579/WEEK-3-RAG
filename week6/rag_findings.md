# Week 6 RAG Findings & Error Analysis

This document records the substantive underlying RAG and retrieval problems identified during the Week 6 evaluation experiment against the 2018 GESCI HR Policy Manual (`WEEKLY_RAG_TASK/HRPolicy.pdf`).

Per the Week 6 protocol, **application RAG code was strictly frozen** during evaluation. The findings below document the root causes, evidence, severity, and recommended fixes for future development iterations.

---

## 1. Finding 1: Low-K Multi-Clause Entitlement Truncation

* **Trace ID**: `66f5c2a9-720c-4a6a-8180-3203ffca66cc` (Q11: Sick Leave) & `c87ef1b4-a959-420e-b866-5daab98220d0` (Q12: Emergency Salary Advance)
* **Taxonomy Mode**: `Low-K Multi-Clause Truncation`
* **Observed Behavior**:
  At default retrieval budget ($K=4$), the RAG system retrieves only the primary chunk (`5.3.2` paragraph 1) while omitting secondary qualifying clauses on qualifying service tenure (2 consecutive months) and statutory half-pay tiers (1 day full pay + 1 day half pay). In Q12, the 3rd condition for emergency advances (CEO written approval for exceptional cases) was cut off.
* **Likely Cause**:
  Fixed/structured chunking boundaries break complex policy rules into separate vector chunks. When $K=4$, only the highest similarity chunk enters the LLM prompt context window.
* **Evidence**:
  - Trace `66f5c2a9` ($K=4$): Answer quoted only 1 day full pay.
  - Trace `067c1ade` ($K=10$): Answer successfully incorporated the 2-month qualifying period and half-pay tier.
* **Severity**: **High / Legal & Financial Exposure** (Employees receive incomplete entitlement statements from self-service HR).
* **Recommended Fix**:
  Implement parent-document retrieval (small-to-big retrieval) or increase candidate context window budget ($K=8\text{--}10$) combined with cross-encoder reranking.

---

## 2. Finding 2: Sub-Clause Dispersal Across Disparate Policy Chapters

* **Trace ID**: `c71b8fb1-7b8f-4e6b-817f-23c63546364b` (Q6: Harassment & Bullying Reporting)
* **Taxonomy Mode**: `Sub-Clause Dispersal Across Disparate Policy Chapters`
* **Observed Behavior**:
  The assistant reported the immediate managerial escalation ladder from Section 2.2.3 (page 11), but omitted the formal 30-day resolution timeline from Section 9.1.1 (page 59) and the anti-retaliation whistleblower protections from Section 9.6 (page 67).
* **Likely Cause**:
  Organizational policies span disparate chapters (Code of Conduct in Chapter 2 vs. Formal Grievance Procedures in Chapter 9). Standard dense vector search without semantic query expansion retrieves chunks clustered in only one chapter.
* **Evidence**:
  Trace `c71b8fb1` retrieved only Chapter 2 chunks. Trace `137a9ac0` ($K=5$) retrieved across Chapters 2 and 9.
* **Severity**: **High / Operational & Compliance Exposure**
* **Recommended Fix**:
  Enable multi-query decomposition or HyDE (Hypothetical Document Embeddings) to expand procedural queries into related administrative pathways.

---

## 3. Finding 3: Citation Drifting & In-Prose Structural Inversion

* **Trace ID**: `cfd0d330-3cb8-48b2-8ea9-42b7194689bb` (Q14: Paternity Leave) & `ded4abe6-1b42-4fdf-9730-a8dc9550b06b` (Q16: Misdemeanors)
* **Taxonomy Mode**: `Citation Drifting & In-Prose Structural Inversion`
* **Observed Behavior**:
  When temperature increases ($T \ge 0.7$), the LLM injects chunk metadata directly into opening sentences (`"According to section 5.3.3 Parental Leave in HRPolicy.pdf (page 37)..."`) or shifts bracket citations from the claim sentence to the list introductory header.
* **Likely Cause**:
  The context prompt format provides `(Section: ..., Page: ...)` metadata headers above each chunk text. At higher temperatures, the model attends to and echoes these prompt headers directly in prose.
* **Evidence**:
  - $T=0.0$ (`30b526af`): Clean citation bracket at end of claim (`"...entitled to paternity leave of two weeks with full pay [1]."`).
  - $T=0.7$ (`cfd0d330`): Inline metadata header injection.
* **Severity**: **Low / UI & Automated Citation Parser Fragility**
* **Recommended Fix**:
  Enforce strict citation grammar via system prompt few-shot demonstrations and keep temperature $\le 0.2$ for factual question-answering.

---

## 4. Finding 4: Invariant Refusals on Absent Policies

* **Trace ID**: `64d8a643-69d6-4afb-9f2b-58f62ed4cef8` (Q4: Retirement Age), `9d868423-12f1-4413-a601-6afcebffbaec` (Q7: Dress Code), `57b6a4af-6eb3-4ee1-b0be-3c6c9a35e406` (Q20: Overtime)
* **Taxonomy Mode**: `Unstated Policy Invariant Refusal`
* **Observed Behavior**:
  When asked about policies unstated in the manual, the assistant returns `"I don't know."` or informative refusals.
* **Likely Cause**:
  The system prompt instructions strictly prohibit hallucinations when context similarity is insufficient.
* **Evidence**:
  All unstated queries invariantly returned refusal responses across all temperature and top-K settings.
* **Severity**: **Low / Desirable Behavior**
* **Recommended Fix**:
  Preserve this guardrail and provide a user-facing referral link to the HR helpdesk for unstated topics.

---

## 5. Finding 5: Embedding Similarity Threshold Starvation

* **Trace ID**: `7f03ac6c-c991-458a-972a-b1822472f0f6` (Q5: Probation Period), `50dbc236-8cb9-43c9-b7b5-27a3a5f8b9ec` (Q15: WFH), `1666a48b-7033-4ef1-be69-c00609349e1e` (Q19: Working Hours)
* **Taxonomy Mode**: `Embedding Similarity Threshold Starvation`
* **Observed Behavior**:
  Increasing $Top-K$ from 4 to 10 produced zero additional chunks because only 3–4 chunks in the entire manual met the `EMBED_MIN_SCORE = 0.55` threshold.
* **Likely Cause**:
  The corpus contains focused, isolated clauses for these topics without distributed secondary references.
* **Evidence**:
  Q5 retrieved 4 chunks at $K=4$ and identical 4 chunks at $K=10$.
* **Severity**: **Low / Informational**
* **Recommended Fix**:
  Apply adaptive $K$ scaling or dynamic threshold relaxation only when candidate pool is sparse.
