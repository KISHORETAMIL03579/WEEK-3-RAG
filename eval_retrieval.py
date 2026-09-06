# eval_retrieval.py — Unified 5-Stage Ablation & Recall@K Evaluator for Ask My Docs.

"""
Ablation Stages:
  1. tfidf               : Lexical TF-IDF baseline
  2. bm25-qdrant-blend   : Weighted blend (BM25 + Qdrant Embeddings)
  3. bm25-qdrant-rrf     : BM25 + Qdrant Reciprocal Rank Fusion (RRF)
  4. rrf-rerank          : RRF + Cross-Encoder Reranking
  5. rrf-rerank-rewrite  : Query Rewriting + RRF + Reranking
"""

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from app import (
    chunk_text, embed_texts, embed_text, VectorStore, cosine,
    build_index, tokenize, compute_tf, tfidf_vector, cosine_sim,
    extract_pdf_pages, extract_txt_pages, GEMINI_API_KEY,
    EVAL_PRESETS, _run_eval_preset
)

TOP_K = int(os.environ.get("TOP_K", "3"))
EVAL_CHUNK_MODE = os.environ.get("EVAL_CHUNK_MODE", "structured")

# ── 1. Point this at your documents ─────────────────────────────────────
# [(filepath_on_disk, display_name), ...]
DOCS = [
    # ("./uploads/HRPolicy.pdf", "HRPolicy.pdf"),
]

# ── 2. Test questions + expected ground truth ───────────────────────────
# expected: section title, filename substring, or chunk keyword
QUESTIONS = [
    # {"question": "How many days of annual leave?", "expected": "annual leave"},
    # {"question": "What is the probation period?", "expected": "probation"},
]


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
        chunks = chunk_text(doc_info, pages, EVAL_CHUNK_MODE)
        store.chunks.extend(chunks)
        all_texts.extend(c["text"] for c in chunks)

    if GEMINI_API_KEY and all_texts:
        print(f"Embedding {len(all_texts)} chunks via Gemini…")
        store.vectors = embed_texts(all_texts)
    else:
        store.vectors = []
        if not GEMINI_API_KEY:
            print("⚠ GEMINI_API_KEY not set — dense retrieval will fall back to TF-IDF.")

    return store


def evaluate_preset(store: VectorStore, questions: list[dict], k: int, preset_name: str) -> dict:
    if not store.chunks:
        return {"hit_rate": 0.0, "mrr": 0.0, "hits": 0, "total": len(questions), "results": []}

    preset = EVAL_PRESETS.get(preset_name)
    if not preset:
        preset = {
            "force_tfidf": (preset_name == "tfidf"),
            "mode": "hybrid" if preset_name in ("hybrid", "embed") else "tfidf",
            "rerank": False,
            "rewrite": False,
        }

    per_question = []
    hits = 0

    for idx, q in enumerate(questions, start=1):
        q_text = q.get("question", "").strip()
        expected = q.get("expected") or q.get("expected_doc", "").strip()
        q_id = str(q.get("id") or f"q_{idx}")

        # NOTE: _run_eval_preset()'s signature is
        # (store, q_id, question, expected, k, preset) — this call site was
        # missing q_id, which shifted every argument one position left and
        # raised TypeError before a single question could be scored.
        res = _run_eval_preset(store, q_id, q_text, expected, k, preset)
        hits += int(res["hit"])
        per_question.append(res)

    rr_sum = sum(r.get("reciprocal_rank", 0.0) for r in per_question)
    total = len(questions) or 1

    return {
        "hit_rate": hits / total,
        "mrr": round(rr_sum / total, 4),
        "hits": hits,
        "total": total,
        "results": per_question,
    }


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

    stages = [
        "tfidf",
        "bm25-qdrant-blend",
        "bm25-qdrant-rrf",
        "rrf-rerank",
        "rrf-rerank-rewrite",
    ]

    results_by_mode = {}
    print(f"\n{'STAGE / STRATEGY':32s} {'HIT-RATE@' + str(TOP_K):14s} {'MRR':10s}")
    print("-" * 58)

    for stage in stages:
        res = evaluate_preset(store, questions, TOP_K, stage)
        results_by_mode[stage] = res
        hr = res["hit_rate"]
        mrr = res["mrr"]
        hits = res["hits"]
        total = res["total"]
        print(f"{stage:32s} {hr:6.0%} ({hits}/{total})      {mrr:.4f}")

    baseline = results_by_mode.get("tfidf", {}).get("hit_rate", 0.0)
    final = results_by_mode.get("rrf-rerank-rewrite", {}).get("hit_rate", 0.0)
    delta = final - baseline
    print(f"\nBaseline (TF-IDF) -> Full Pipeline (Rewrite+RRF+Rerank): {baseline:.0%} -> {final:.0%} ({'+' if delta >= 0 else ''}{delta:.0%})")

    print("\nPer-question breakdown (Final Pipeline):")
    for r in results_by_mode.get("rrf-rerank-rewrite", {}).get("results", []):
        mark = "✓" if r["hit"] else "✗"
        rank_str = f" (rank #{r['rank']})" if r["hit"] else ""
        print(f"  {mark} {r['question']}{rank_str}")


if __name__ == "__main__":
    main()
