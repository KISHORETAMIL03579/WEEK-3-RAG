
# eval_retrieval.py — Recall@k evaluation for Ask My Docs retrieval.

# WHAT THIS MEASURES
# -------------------
# For a set of questions you already know the answer to, this checks whether
# the CORRECT document shows up in the top-k retrieved chunks — regardless of
# whether the final generated answer was right. That's the "wrong document
# fetched" vs. "right document, wrong answer" split from this week's task:

#     - If recall@k says the doc WASN'T retrieved  -> retrieval problem.
#     - If recall@k says the doc WAS retrieved but your /ask answer was still
#       wrong -> that's a generation problem, and this script can't fix or
#       measure it. Note those separately; don't let this number hide them.

# It runs the SAME question set through three retrieval strategies so you get
# a real before/after instead of a vibe:
#     - embed   : embeddings + cosine similarity only (old behavior)
#     - hybrid  : embeddings + TF-IDF blended         (this week's change)
#     - tfidf   : TF-IDF only (for reference / sanity check)

# HOW TO USE
# ----------
# 1. Fill in DOCS below with paths to a handful of real documents.
# 2. Fill in QUESTIONS with real questions + which document should answer
#    each one (a substring of its filename is enough).
# 3. Run: python eval_retrieval.py
# 4. Read the recall@k line for "embed" (before) and "hybrid" (after).
#    That's your before-and-after number. The per-question ✓/✗ list under
#    each mode tells you exactly which failures were NOT fixed.

# Requires GEMINI_API_KEY to be set in the environment (or .env next to app.py)
# for the embed/hybrid modes to do anything meaningful — without a key their
# embedding score is just 0 for every chunk, so they degrade to TF-IDF ranking,
# which will make embed == hybrid == tfidf. That's expected and tells you your
# key isn't configured, not that hybrid doesn't help.
# """

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from app import (  # noqa: E402
    chunk_text, embed_texts, embed_text, VectorStore, cosine,
    build_index, tokenize, compute_tf, tfidf_vector, cosine_sim,
    extract_pdf_pages, extract_txt_pages, GEMINI_API_KEY,
)

TOP_K = 5
HYBRID_ALPHA = 0.6  # weight on embedding score; must match app.py's HYBRID_ALPHA
                    # to evaluate the exact same config that's live in /ask

# ── 1. Point this at your own documents ─────────────────────────────────
# [(filepath_on_disk, display_name), ...]
DOCS = [
    # ("./uploads/errors.md", "errors.md"),
    # ("./uploads/refund_policy.pdf", "refund_policy.pdf"),
]

# ── 2. Point this at your own failing-question set ──────────────────────
# expected_doc: a substring that appears in the correct source's filename
QUESTIONS = [
    # {"question": "What does error code ERR-4032 mean?", "expected_doc": "errors.md"},
    # {"question": "How many days do I have to request a refund?", "expected_doc": "refund_policy.pdf"},
]

# Optionally load a bigger set from JSON instead of editing this file:
#   python eval_retrieval.py questions.json
# where questions.json is a list of {"question": ..., "expected_doc": ...}


def _extract_pages(filepath: str, ext: str):
    return extract_pdf_pages(filepath) if ext == "pdf" else extract_txt_pages(filepath)


def build_eval_store() -> VectorStore:
    store = VectorStore("eval")
    store.chunks, store.vectors = [], []
    all_texts: list[str] = []

    for filepath, name in DOCS:
        ext = name.rsplit(".", 1)[-1].lower()
        pages = _extract_pages(filepath, ext)
        if not pages:
            print(f"⚠ no extractable text in {name}, skipping")
            continue
        doc_info = {"doc_id": name, "filename": name}
        chunks = chunk_text(doc_info, pages, "structured")
        store.chunks.extend(chunks)
        all_texts.extend(c["text"] for c in chunks)

    if GEMINI_API_KEY and all_texts:
        print(f"Embedding {len(all_texts)} chunks via Gemini…")
        store.vectors = embed_texts(all_texts)
    else:
        store.vectors = []
        if not GEMINI_API_KEY:
            print("⚠ GEMINI_API_KEY not set — embed/hybrid will fall back to TF-IDF-only ranking.")

    return store


def _embed_scores(store: VectorStore, query: str) -> list[float]:
    if not (GEMINI_API_KEY and store.vectors and len(store.vectors) == len(store.chunks)):
        return [0.0] * len(store.chunks)
    return [cosine(embed_text(query), v) for v in store.vectors]


def _tfidf_scores(query: str, index: dict) -> list[float]:
    q_vec = tfidf_vector(compute_tf(tokenize(query)), index["idf"])
    return [
        cosine_sim(q_vec, tfidf_vector(compute_tf(tokens), index["idf"]))
        for tokens in index["corpus_tokens"]
    ]


def _top_k_filenames(scores: list[float], chunks: list[dict], k: int) -> set:
    ranked = sorted(range(len(scores)), key=lambda i: -scores[i])[:k]
    return {chunks[i]["filename"] for i in ranked}


def recall_at_k(store: VectorStore, questions: list[dict], k: int, mode: str):
    if not store.chunks:
        return 0.0, []

    index = build_index(store.chunks)
    hits = 0
    per_question = []

    for q in questions:
        embed_s = _embed_scores(store, q["question"])
        tfidf_s = _tfidf_scores(q["question"], index)

        if mode == "embed":
            scores = embed_s
        elif mode == "tfidf":
            scores = tfidf_s
        else:  # hybrid
            scores = [HYBRID_ALPHA * e + (1 - HYBRID_ALPHA) * t
                      for e, t in zip(embed_s, tfidf_s)]

        top_docs = _top_k_filenames(scores, store.chunks, k)
        hit = any(q["expected_doc"] in d for d in top_docs)
        hits += hit
        per_question.append((q["question"], hit))

    return hits / len(questions), per_question


def main():
    questions = QUESTIONS
    if len(sys.argv) > 1:
        questions = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))

    if not DOCS or not questions:
        print("Fill in DOCS and QUESTIONS at the top of this script "
              "(or pass a questions.json path as an argument) first.")
        return

    store = build_eval_store()
    if not store.chunks:
        print("No chunks indexed — check DOCS paths.")
        return

    results_by_mode = {}
    for mode in ("embed", "hybrid", "tfidf"):
        score, per_question = recall_at_k(store, questions, TOP_K, mode)
        results_by_mode[mode] = (score, per_question)

    print(f"\n{'MODE':8s} {'RECALL@' + str(TOP_K):12s}")
    print("-" * 24)
    for mode in ("embed", "hybrid", "tfidf"):
        score, _ = results_by_mode[mode]
        print(f"{mode:8s} {score:6.0%}   ({int(round(score*len(questions)))}/{len(questions)})")

    before, _ = results_by_mode["embed"]
    after, _ = results_by_mode["hybrid"]
    delta = after - before
    print(f"\nBefore (embed-only) -> After (hybrid): {before:.0%} -> {after:.0%}  "
          f"({'+' if delta >= 0 else ''}{delta:.0%})")

    print("\nPer-question detail (which failures were fixed, which weren't):")
    for mode in ("embed", "hybrid"):
        print(f"\n  [{mode}]")
        for question, hit in results_by_mode[mode][1]:
            print(f"    {'✓' if hit else '✗'} {question}")

    # Explicitly call out anything hybrid still doesn't fix, so it doesn't
    # get lost in the aggregate recall number.
    still_failing = [
        q for (q, hit_e), (_, hit_h) in
        zip(results_by_mode["embed"][1], results_by_mode["hybrid"][1])
        if not hit_h
    ]
    if still_failing:
        print("\nStill NOT retrieving the right doc after hybrid "
              "(these are not retrieval fixes — look at generation, or the "
              "chunking/section boundaries for these docs):")
        for q in still_failing:
            print(f"    ✗ {q}")


if __name__ == "__main__":
    main()