# Ask My Docs — Universal Multimodal RAG & Retrieval Debugging Framework

A production-grade Retrieval-Augmented Generation (RAG) system built with Flask, React, and **pluggable local/cloud backends**. It supports **universal text extraction** (PDFs, Word Docs, CSV/Spreadsheets, Data files, Source Code, and **Images via Vision OCR**), grounded QA with clickable source citations that deep-link into the exact page, side-by-side diagnostic inspection, automated retrieval evaluation (`Hit-Rate@K`, `MRR`, `Recall@K`), and durable, replayable trace logging for error analysis.

Every model call in the pipeline — embeddings, image OCR, and chat/answer generation — is independently switchable between a **fully local, zero-API-key stack (Ollama)** and a **cloud stack (Google Gemini for embeddings/OCR, xAI Grok for chat)**. The whole app also runs with zero cloud keys at all, falling back to offline BM25/TF-IDF keyword search.

---

## ⚡ Quick Start & Setup

### 1. Environment Setup
```bash
git clone <repository-url>
cd WEEK-3-RAG
python -m venv .venv
.venv\Scripts\Activate.ps1
python -c "import sys; print(sys.executable)"
python -m pip install -r requirements.txt
python -c "import pymupdf, docx, flask, werkzeug, waitress, qdrant_client; print('ALL IMPORTS OK')"
cp .env.example .env
```

### 2. Choose your backends (edit `.env`)
The app defaults to **fully local** — no cloud API key required at all:
```bash
ollama pull nomic-embed-text   # embeddings
ollama pull llava              # vision OCR (skip if you never upload images)
ollama pull llama3.1           # chat / answer generation
ollama serve                   # if not already running as a background service
```
To use Google Gemini and/or xAI Grok instead for any of the three pieces, see §7 Configuration — each backend (`EMBED_BACKEND`, `VISION_BACKEND`, `CHAT_BACKEND`) is set independently.

### 3. VS Code Interpreter Selection
```text
Ctrl + Shift + P
       ↓
Python: Select Interpreter
       ↓
.venv\Scripts\python.exe
```

### 4. Launch the Application
```bash
python app.py
```
Open **http://localhost:5000** in your browser. The startup banner tells you which mode actually loaded, e.g.:
```
🚀 Ask My Docs is running → http://localhost:5000
   Mode: embeddings (Ollama (local)) + LLM (Ollama (local))
```

---

## 📖 Table of Contents
1. System Workflows & How It Works
2. Universal File Extraction & Vision OCR
3. Retrieval & RAG System Architecture
4. Deep Dive: Evaluation Suite & Metrics (`/eval`)
5. Backend API Endpoints Architecture
   - 5a. Trace Logging & Replay
   - 5b. Document Viewer, Open Links & Highlighting
6. Codebase Function & File Mapping
7. Configuration & Environment Variables (`.env`)
8. Docker & Docker-Compose Deployment
9. GHCR Container Deployment
10. Testing & Verification
11. Troubleshooting & FAQ

---

## 1. System Workflows & How It Works

```text
 ┌──────────┐     ┌───────────┐     ┌───────────┐     ┌──────────────────┐
 │  Upload  │ ──► │ Universal │ ──► │ Chunking  │ ──► │ Embeddings       │
 │ PDF/Code/│     │ Extract & │     │ (Structured│    │ Gemini (3072-dim)│
 │ Image    │     │ Vision OCR│     │ or Fixed) │     │  or Ollama (768) │
 └──────────┘     └───────────┘     └───────────┘     └──────┬───────────┘
                                                             │
                                                             ▼
                                                    ┌──────────────────┐
                                                    │   VectorStore    │
                                                    │ (Qdrant / Local) │
                                                    └─────────┬────────┘
                                                              │
      ┌───────────────────────────────────────────────────────┘
      ▼
 ┌──────────┐     ┌────────────────┐     ┌─────────────┐     ┌──────────────────┐     ┌──────────────┐
 │ Ask a    │ ──► │ Hybrid Search  │ ──► │ Context     │ ──► │ Grounded Answer  │ ──► │ Trace logged │
 │ Question │     │ (BM25 + Dense  │     │ Validation  │     │ xAI Grok or      │     │ (traces.jsonl,│
 │          │     │  RRF Fusion)   │     │ Threshold   │     │ Ollama (local)   │     │  replayable) │
 └──────────┘     └───────────┘     └─────────────┘     └──────────────────┘     └──────────────┘
```

### Workflow 1: Document Upload & Indexing
1. **User Action**: You drop files (PDF, Word, Code, CSV, Image) into the dropzone or type a web URL.
2. **Staging**: The UI validates file extension and size, staging it in the active upload list.
3. **Chunk Strategy Selection**: You select a chunking strategy (`structured`, `128`, `256`, `512` words).
4. **Backend Processing (`/upload`)**:
   - Text is extracted per page or block (`extract_document_pages()`; image uploads route through Vision OCR first — see Workflow 3).
   - Text chunks are generated based on headings and paragraph boundaries.
   - Embeddings are generated via whichever `EMBED_BACKEND` is configured — Gemini's `gemini-embedding-001` (3072-dim) or a local Ollama model like `nomic-embed-text` (768-dim).
   - Vectors and payload metadata (page, section, filename, chunk ID) are stored in **Qdrant** or the in-process memory store, per `VECTOR_BACKEND`.
   - **Graceful degradation**: if the embedding call itself fails (e.g. Ollama not running, a cloud rate limit), the document is still indexed for **keyword-only (BM25/TF-IDF) search** rather than failing the whole upload — the response surfaces a `warning` per-file so the UI can tell you semantic search won't work for that document until it's re-uploaded.
5. **UI Update**: Document list updates with chunk count, file size, and indexed status; any per-file `error`/`warning` is surfaced as an alert.

---

### Workflow 2: Grounded Question-Answering
1. **User Action**: You type a question in the chat input (e.g. *"What does working from home mean?"*).
2. **Search Query Normalization**: If `QUERY_REWRITE_ENABLED=true`, a chat-model call simplifies conversational fluff into a clean search query.
3. **Hybrid Retrieval**:
   - **BM25 Keyword Search**: Finds exact term occurrences (e.g. section numbers like `9.3.4`).
   - **Dense Vector Search**: Finds semantic concepts.
   - **Reciprocal Rank Fusion (RRF)**: Fuses both rankings using $RRF(c) = \sum \frac{1}{k + r(c)}$, normalized so 1.0 = ranked #1 by both methods.
4. **Context Validation Gate**: Checks if the top match score clears `EMBED_MIN_SCORE` (`0.55` by default, on RRF's normalized scale — not a raw cosine similarity).
   - If the top score is below threshold: immediately outputs *"I don't know — no document content matched your question closely enough."* to prevent hallucination, and returns the closest near-miss for diagnosis.
5. **Answer Synthesis**: Validated context chunks are passed to whichever `CHAT_BACKEND` is configured — xAI Grok or a local Ollama chat model — with strict grounding rules (answer only from the excerpts, cite every fact `[1]`/`[2]`, say "I don't know" if the excerpts don't cover it).
6. **Citations & Inspection**: Returns the synthesized answer alongside **Grounded Sources** cards — numbered badge, filename, page, section, color-coded relevance score, an **Open ↗** button that deep-links into the document viewer at the exact page with the matched passage highlighted (see §5b), and a **▼ View Content** toggle showing the actual retrieved excerpt inline.
7. **Trace Logged**: Every `/ask` call — success or "I don't know" — writes one durable, redacted JSON record to `traces/traces.jsonl` (see §5a).

---

### Workflow 3: Multimodal Image OCR
1. **User Action**: You upload an image file (`.png`, `.jpg`, `.webp`, `.tiff`, `.bmp`, `.gif`).
2. **Base64 Payload Encoding**: `app.py` reads the binary image bytes and base64-encodes them.
3. **Vision OCR Call**, per `VISION_BACKEND`:
   - **Gemini**: calls `GEMINI_VISION_MODEL` (default `gemini-3.7-flash`) with the image as `inline_data`.
   - **Ollama** (default): calls a local vision-capable model (default `llava`) via `/api/generate`'s native `images` field.
   Either way, the prompt is: *"Extract all text, table content, diagram descriptions, titles, bullet points, and key information into clean, structured Markdown."*
4. **Markdown Chunking & Embedding**: Transcribed Markdown text is chunked and embedded like standard text documents.

> **Known limitation**: local vision models (`llava`, `moondream`) are noticeably weaker than Gemini's OCR at dense text and busy scans. Worth spot-checking real output quality before relying on `VISION_BACKEND=ollama` for policy-document-grade scans; you can set `VISION_BACKEND=gemini` independently of your embeddings/chat backend choices if OCR fidelity matters more than staying fully local.

---

### Workflow 4: Automated Evaluation & Ablation Matrix (`/eval`)
1. **User Action**: Navigate to `/eval`. Enter test Q/A pairs or upload a Q/A benchmark PDF.
2. **Preset Selection**: Select ablation ladder presets (`tfidf`, `bm25-qdrant-blend`, `bm25-qdrant-rrf`, `rrf-rerank`, `rrf-rerank-rewrite`).
3. **Execution (`/eval/run`)**: Each preset runs questions through its respective retrieval pipeline.
4. **Metric Calculation**: Computes **`Hit-Rate@K`**, **`MRR`**, **`Recall@K`**, and classifies failure types (`Success`, `Retrieval Failure`, `Generation Failure`).
5. **Side-by-Side Diagnostic Drawer**: Clicking any question opens an inspection drawer showing candidate chunks, raw scores, RRF ranks, and generated answers.

---

### Workflow 5: Document Session Lifecycle
- **Session Isolation**: Each user browser session receives a unique `session_id` and isolated vector collection.
- **Single File Removal (`/remove`)**: Deletes chunks for a specific document and purges its deduplication hash.
- **Session Reset (`/clear`)**: Clears all indexed vectors, uploaded files, and session state.

---

## 2. Universal File Extraction & Vision OCR

| File Category | Extensions | Extraction Method & Behavior |
| :--- | :--- | :--- |
| **Images (Vision OCR)** | `.png`, `.jpg`, `.jpeg`, `.webp`, `.bmp`, `.tiff`, `.gif` | **Gemini or Ollama Vision** (per `VISION_BACKEND`): transcribes visual text, tables, numbers, diagram annotations, and notes into Markdown. |
| **Word Documents** | `.docx`, `.doc` | **python-docx Extractor**: Parses paragraph text, headings, and data tables. |
| **Spreadsheets & Data** | `.csv`, `.tsv`, `.json`, `.xml`, `.yaml`, `.yml` | **Data Formatter**: Converts tabular data into Markdown tables and formatted code blocks. |
| **Source Code & Config** | `.py`, `.js`, `.ts`, `.jsx`, `.tsx`, `.html`, `.css`, `.c`, `.cpp`, `.java`, `.go`, `.rs`, `.php`, `.sql`, `.sh`, `.log`, `.env` | **Code Block Wrapper**: Preserves code formatting inside syntax fences. |
| **Standard Documents** | `.pdf`, `.txt`, `.md`, `.markdown`, `.rst` | **PyMuPDF / Section Splitter**: Page-by-page and heading-based extraction. |

---

## 3. Retrieval & RAG System Architecture

### Why Hybrid Search (BM25 + Dense Embeddings)?
- **Dense Embeddings**: Match semantic meaning (e.g., *"How do I get my money back?"* matches *"refund policy"*).
- **BM25 Keyword Search**: Matches exact technical terms, acronyms, product SKUs, and error codes (e.g., section numbers, `SEC-808`).
- **Reciprocal Rank Fusion (RRF)**: Merges sparse BM25 and dense vector rankings using $RRF(c) = \sum \frac{1}{k + r(c)}$, avoiding raw score normalization issues. `RRF_K=10` here (not the textbook web-scale default of 60) — tuned for a document-sized corpus of a few hundred chunks, where 60 crushed the gap between a genuine top match and a plausible false positive (~1.0 vs ~0.78) far more than 10 does (~1.0 vs ~0.39–0.42).

---

## 4. Deep Dive: Evaluation Suite & Metrics (`/eval`)

### 4.1 Failure Mode Categorization
- **`Success`**: Right document/section retrieved in top-K, correct answer synthesized.
- **`Retrieval Failure`**: Target ground-truth document was missing from top-K candidates (`Hit-Rate@K == 0`).
- **`Generation Failure`**: Right document retrieved, but the chat model failed to synthesize a correct answer.

### 4.2 Quantitative Evaluation Metrics
- **`Hit-Rate@K`** (e.g. `Hit-Rate@3`): Percentage of test questions where the correct document appeared in the top-K retrieved candidates.
- **`MRR` (Mean Reciprocal Rank)**: Measures average reciprocal rank ($1/\text{rank}$) across all test queries.
- **`Recall@K`**: Ratio of expected section coverage.

---

## 5. Backend API Endpoints Architecture

| HTTP Method | Route | Description |
| :--- | :--- | :--- |
| `POST` | `/upload` | Universal file upload & vector indexing endpoint |
| `POST` | `/upload-cancel` | Cancels in-flight upload, safely removes extracted file, and unindexes doc from vector store |
| `POST` | `/load-url` | Web page fetch & HTML text extraction endpoint |
| `POST` | `/ask` | Hybrid retrieval & grounded QA endpoint; writes a trace record per call |
| `GET` | `/status` | Returns session indexed document counts, backend info (`embeddings_backend`, `chat_backend`, `vector_backend`, `retrieval_mode`) |
| `POST` | `/remove` | Removes a specific document from vector store |
| `POST` | `/clear` | Clears all documents and vectors for the current session |
| `POST` | `/eval/run` | Runs evaluation benchmark matrix across presets |
| `GET` | `/eval` | Evaluation Matrix & Inspection Drawer UI |
| `GET` | `/file/<doc_id>` | Renders the document viewer page |
| `GET` | `/file/<doc_id>/raw` | Streams the raw file bytes (used by the PDF `<embed>`) |
| `GET` | `/file/<doc_id>/pages` | Returns extracted per-page text (used by the non-PDF text viewer) |
| `GET` | `/healthz` | System liveness & configuration health check (`embeddings_configured`, `chat_configured`, `retrieval_mode`, `vector_backend`) |
| `GET` | `/readyz` | System readiness check; validates live connectivity to Qdrant vector backend |
| `GET` | `/orphans` | Lists unindexed / cleanup-failed orphaned documents (requires active session or `X-Admin-Key` header) |
| `GET` | `/traces` | Lists all logged trace_ids |
| `POST` | `/replay/<trace_id>` | Replays a trace from the trace record alone; returns original vs. replayed raw output (session-scoped or requires `X-Admin-Key`) |

---

## 5a. Trace Logging & Replay (W5 Task Set C)

Every `/ask` call writes one durable, redacted JSON line to `traces/traces.jsonl` (path configurable via `TRACE_LOG_PATH`), in addition to the existing console-only `RAGTracer` step logs. Each record carries: `trace_id`, `question` (redacted), `retrieval_mode`, `retrieved` (chunk_id + doc_id + filename + page + section + score + text, all redacted), `model`, `temperature`, `prompt_version`, `raw_output` (redacted), `answer`, `found`, and `latency_ms`. See `trace_store.py` for the redaction rules and prompt-version registry.

**Workflow for the Task Set C write-up:**
1. Run the app and ask it a realistic mix of real HR questions (not just demo questions) so `traces/traces.jsonl` accumulates real traffic.
2. `python sample_trace.py --n 20 --seed <your_seed>` — prints (and can save) the seeded 20 trace_ids. Paste the seed and the list into `notes.md`.
3. `python sample_trace.py --replay-pick --seed <your_seed>` to seed-pick one trace_id, then replay via `POST`:
   ```bash
   curl -X POST http://localhost:5000/replay/<trace_id>
   ```
   *(Note: `/replay/<trace_id>` is session-scoped. Provide your session cookie or include the `-H "X-Admin-Key: <key>"` header if replaying cross-session).* Paste both original and replayed outputs into `notes.md`, along with `fields_missing_from_trace` / `reconstruction_note` if either is non-null.
4. Read all 20 traces by hand (`grep trace_id traces/traces.jsonl` or open the file directly) and write one observation sentence each in `notes.md` — no fixes, no categorizing yet.
5. Cluster into 4–7 named modes in `taxonomy.md`, write the dated prediction, commit it, and paste the commit hash.

**Redaction note:** `trace_store.redact()` is pattern-based (employee IDs, emails, phone numbers, SSN-shaped strings, and `Name: <Two Words>` style labeled fields) — not an NER model. A free-text employee name typed into a question without a label (e.g. "what's John Smith's leave balance") will NOT reliably be caught. State this limitation explicitly in your submission rather than overclaiming full redaction.

---

## 5b. Document Viewer, Open Links & Highlighting

Clicking **Open ↗** on any source card navigates to `/file/<doc_id>?page=N&hl=<snippet>`. What happens next depends on file type:

- **Non-PDF documents** (`.txt`, `.md`, extracted Word/CSV/code text) render through a custom React page-by-page viewer (`static/js/view.js`) with **real in-page highlighting**: the `hl` snippet (the first ~100 characters of the actual retrieved chunk, not the raw question — the question almost never appears verbatim in the source) is matched against the page text with a whitespace-flexible regex, since chunk text gets newlines collapsed during ingestion while the raw page text keeps them.
- **PDF documents** are handed to the **browser's own native PDF plugin** via `<embed>` — there is no API surface for us to inject a highlight into that renderer's content. What *does* work: the standard `#page=N` URL fragment (supported by Chrome/Firefox/Safari/Edge/Brave) jumps straight to the cited page. For the passage itself, a banner above the embed shows the exact excerpt text to look for, with a nudge to use the browser's native Find (Ctrl/Cmd+F) — an honest fallback rather than a highlight that silently does nothing.

`templates/view.html` injects `window.DOC_ID` / `DOC_FILENAME` / `DOC_EXT` as the very first script in `<head>` (via Flask's `tojson` filter, which safely escapes the values for script-context embedding) — before the React/Babel CDN scripts even load, so the viewer never depends on a `?doc_id=` query param that the route never actually has (the Flask route is `/file/<doc_id>`, a path segment).

> If you see red squiggly "Property assignment expected" errors on the `{{ doc_id | tojson }}` lines in VS Code — that's the editor's JS linter misreading Jinja2 template syntax as literal JavaScript. It's a local editor-only false positive; Flask replaces every `{{ ... }}` with a real value before the browser ever sees the page. Install the **Better Jinja** extension and set this file's language mode to **Jinja HTML** to silence it.

---

## 6. Codebase Function & File Mapping

| Feature / Logic | File Location | Key Function / Component |
| :--- | :--- | :--- |
| **Universal File Extraction** | `app.py` | `extract_document_pages()`, `extract_image_pages()`, `extract_docx_pages()` |
| **Vision OCR (Gemini + Ollama)** | `app.py` | `extract_image_pages()`, `_gemini_vision_ocr()`, `_ollama_vision_ocr()` |
| **Embeddings (Gemini + Ollama)** | `app.py` | `embed_texts()`, `_gemini_embed_batch()`, `_ollama_embed_batch()`, `_embeddings_configured()` |
| **Chat / Generation (xAI + Ollama)** | `app.py` | `_chat_call()` dispatcher, `_xai_chat_call()`, `_ollama_chat_call()`, `_chat_configured()` |
| **Semantic & Fixed Chunking** | `app.py` | `chunk_text()`, `structured_chunk()`, `fixed_chunk()` |
| **Qdrant Vector DB Backend** | `qdrant_store.py` | `QdrantVectorStore`, `add()`, `query()` |
| **Hybrid Search & RRF** | `app.py` | `reciprocal_rank_fusion()`, `hybrid_search()` |
| **Context Validation Gate** | `app.py` | `validate_context()` |
| **LLM Reranker & Rewriter** | `app.py` | `rerank_with_llm()`, `rewrite_query()` |
| **Evaluation Suite & Matrix** | `app.py`, `eval_retrieval.py` | `/eval/run`, `_run_eval_preset()`, `recall_at_k()` |
| **Trace Logging & Replay** | `trace_store.py`, `app.py` | `TraceStore`, `redact()`, `/replay/<trace_id>`, `sample_trace.py` (CLI) |
| **Main React Application** | `static/js/app.js` | React Chat UI, `SourceItem` grounded-source cards, Dropzone, Staged File List |
| **Evaluation React UI** | `static/js/eval.js` | React Evaluation Matrix & Inspection Drawer |
| **Document Viewer React UI** | `static/js/view.js`, `templates/view.html` | React Embedded Document Viewer, page-jump + highlight logic |

---

## 7. Configuration & Environment Variables (`.env`)

Copy `.env.example` to `.env` and fill in what you need — see the file itself for full inline documentation. Summary:

### Embeddings (retrieval)
| Variable | Default | Description |
| :--- | :--- | :--- |
| `EMBED_BACKEND` | `ollama` | `ollama` (local, no key) or `gemini` (needs `GEMINI_API_KEY`) |
| `OLLAMA_URL` | `http://localhost:11434` | Local Ollama server address |
| `OLLAMA_EMBED_MODEL` | `nomic-embed-text` | Local embedding model (768-dim) |
| `GEMINI_API_KEY` | *(empty)* | Required only if `EMBED_BACKEND=gemini` |
| `EMBED_MODEL` | `gemini-embedding-001` | Gemini embedding model (3072-dim) |

### Vision OCR (image uploads)
| Variable | Default | Description |
| :--- | :--- | :--- |
| `VISION_BACKEND` | `ollama` | `ollama` (local) or `gemini` |
| `OLLAMA_VISION_MODEL` | `llava` | Local vision model (also: `moondream`, `llama3.2-vision`) |
| `GEMINI_VISION_MODEL` | `gemini-3.7-flash` | Gemini vision model, only used if `VISION_BACKEND=gemini` |

### Chat / Generation, Reranking, Query Rewriting
| Variable | Default | Description |
| :--- | :--- | :--- |
| `CHAT_BACKEND` | `ollama` | `ollama` (local) or `xai` (needs `XAI_API_KEY`) |
| `OLLAMA_CHAT_MODEL` | `llama3.1` | Local chat model (also: `qwen2.5`, `mistral`) |
| `XAI_API_KEY` | *(empty)* | Required only if `CHAT_BACKEND=xai` |
| `XAI_URL` | `https://api.x.ai/v1` | xAI API base URL |
| `XAI_MODEL` | `grok-4.3` | xAI model (also: `grok-4.5`, `grok-4.20`) |

### Retrieval tuning
| Variable | Default | Description |
| :--- | :--- | :--- |
| `RETRIEVAL_MODE` | `hybrid` | `hybrid` (BM25+embeddings via RRF), `hybrid-legacy` (weighted blend), or `embed` |
| `EMBED_MIN_SCORE` | `0.55` | Context validation threshold, on RRF's normalized 0–1 scale |
| `TOP_K` | `8` | Candidate chunks retrieved |
| `MAX_CONTEXT_TOKENS` | `6000` | Context token budget cap |
| `RRF_K` | `10` | RRF smoothing constant (tuned for document-sized corpora, not web-scale) |
| `HYBRID_ALPHA` | `0.6` | Embedding weight, only used by `RETRIEVAL_MODE=hybrid-legacy` |
| `BM25_K1` / `BM25_B` | `1.5` / `0.75` | Standard BM25 term-saturation / length-normalization constants |

### Reranking & query rewriting (both off by default)
| Variable | Default | Description |
| :--- | :--- | :--- |
| `RERANK_ENABLED` | `false` | Second-pass LLM relevance judgment on top candidates |
| `RERANK_TOP_N` | `8` | How many candidates get reranked |
| `RERANK_MIN_RELEVANCE` | `5` | Minimum LLM relevance score (0–10) to keep a candidate |
| `QUERY_REWRITE_ENABLED` | `false` | LLM rewrites the question into a cleaner search query before retrieval |

### Vector backend
| Variable | Default | Description |
| :--- | :--- | :--- |
| `VECTOR_BACKEND` | `qdrant` | `qdrant` (real vector DB) or `memory` (in-process, zero setup) |
| `QDRANT_URL` | *(required if qdrant)* | Qdrant Cloud or self-hosted endpoint |
| `QDRANT_API_KEY` | *(required if Qdrant Cloud)* | Qdrant Cloud API key |
| `QDRANT_TIMEOUT` | `10` | Request timeout (seconds) |
| `QDRANT_CANDIDATE_POOL` | `30` | ANN candidates returned per query before hybrid re-ranking |

### Trace logging, chunking defaults, ops
| Variable | Default | Description |
| :--- | :--- | :--- |
| `TRACE_LOG_PATH` | `traces/traces.jsonl` | Durable `/ask` trace log path (see §5a) |
| `DEFAULT_CHUNK_MODE` | `structured` | Default chunking strategy |
| `DEFAULT_CHUNK_SIZE` | `512` | Default fixed chunk size (words) |
| `SECRET_KEY` | *(random per-process if unset)* | Signs session cookies — **mandatory in production** to preserve session continuity across worker restarts |
| `ADMIN_API_KEY` | *(empty)* | Optional administrative token for inspecting cross-session `/orphans` and replaying traces via `X-Admin-Key` header |
| `LOG_LEVEL` | `INFO` | `DEBUG` / `INFO` / `WARNING` / `ERROR` |
| `PORT` / `HOST` | `5000` / `127.0.0.1` | Set `HOST=0.0.0.0` when running inside Docker |
| `APP_DEBUG` | `false` | Flask debug mode — never enable outside local dev |

---

## 8. Docker & Docker-Compose Deployment

`docker-compose.yaml` runs a self-hosted Qdrant instance alongside the app in one command:
```bash
docker compose up --build
```
This starts:
- **`qdrant`**: `qdrant/qdrant:v1.13.4`, bound to `127.0.0.1:6333` on the host to prevent direct network exposure. Readiness is validated via a native bash socket probe on `/readyz` (`qdrant:v1.13.4` has no `curl`), protected by `stop_grace_period: 30s` and bounded by resource limits (`cpus: "2"`, `memory: 4G`).
- **`app`**: built from the included `Dockerfile` (Python 3.11-slim base, non-root `appuser`), served via **Gunicorn** (`--workers 2 --timeout 120 app:app`), loopback-bound to `127.0.0.1:5000:5000` on the host to prevent unauthenticated public exposure. Resource limits (`cpus: "2"`, `memory: 4G`) and `stop_grace_period: 30s` protect against runaway OCR/embedding workloads and ensure clean request drainage on shutdown.

### Production Network & Reverse Proxy Architecture
In production deployments, the application should never be exposed directly to the public internet without a reverse proxy or cloud load balancer:
```text
Internet / Clients
       │
       ▼
Reverse Proxy / LB (Nginx / Caddy / Cloudflare / AWS ALB)
       │
       ▼ [127.0.0.1:5000 / Internal Docker Network]
Gunicorn WSGI Server (2 workers, 120s timeout)
       │
       ▼
Flask Application (Ask My Docs)
  ├── Qdrant Vector Store (127.0.0.1:6333 / http://qdrant:6333)
  └── Model Backends (Host Ollama via host.docker.internal / Cloud APIs)
```

To point at **Qdrant Cloud** instead of the bundled container, set in your `.env` before running compose:
```bash
VECTOR_BACKEND=qdrant
QDRANT_URL=https://xxxx.aws.cloud.qdrant.io:6333
QDRANT_API_KEY=<your cluster key>
```

The `app` container's health check hits `/healthz` directly via Python standard library — a fast way to confirm the container came up healthy: `docker compose ps`.

> **Production Secrets Enforcement:**
> `docker-compose.yaml` enforces `${SECRET_KEY:?SECRET_KEY must be set in .env to preserve session continuity}`. Startup will fail fast with a descriptive error if `SECRET_KEY` is omitted, preventing inadvertent deployment with ephemeral per-process session cookies.

> **Deployment Architecture Note (Single-Host vs Clustered):**
> The bundled Docker Compose configuration is hardened for a **single-host deployment** (`restart: unless-stopped`, non-root container user `appuser`, isolated loopback bindings, durable host volume mounts for `./uploads`, `./vectorstore`, and `./traces`, and `filelock` for cross-worker serialized writes).
> For multi-node or horizontally scaled deployments across multiple container instances, shared network storage (e.g., NFS, AWS EFS) or object storage (S3/GCS) is required for `./uploads` and `./traces` because trace persistence, document retrieval, and `orphans.jsonl` conflict-resolution rely on host filesystem durability and atomic file locking (`filelock`).
> Note on Markdown (`*.md`): `.dockerignore` excludes repository markdown docs to keep image layers lean. Any user markdown documents intended for indexing should be uploaded through the UI or placed directly into the volume-mounted `./uploads/` directory.

---

## 9. GHCR Container Deployment

`.github/workflows/python-app.yml` builds and publishes this app's Docker image to the **GitHub Container Registry (GHCR)** on every push to `main`:
- Lints with `flake8` (hard-fails only on real syntax errors: `E9,F63,F7,F82`; everything else is reported but non-blocking).
- Builds the image and tags it both `:latest` and `:<commit-sha>`.
- Pushes to `ghcr.io/<owner>/<repo>:latest` (lowercased automatically, since GHCR requires it) — only on an actual push to `main`, never on a pull request (PRs, especially from forks, don't get write access to secrets by design).

To pull and run the published image directly, without cloning the repo:
```bash
docker pull ghcr.io/<owner>/<repo>:latest
docker run -p 5000:5000 --env-file .env ghcr.io/<owner>/<repo>:latest
```
Requires `packages: write` permission on the workflow's `GITHUB_TOKEN` (already configured) — no personal access token or extra scopes needed.

---

## 10. Testing & Verification

The repository includes a comprehensive automated test suite alongside interactive benchmark and diagnostic tools:

### Automated Test Suite (`unittest`)
Run the regression test suite covering retrieval logic, Qdrant transactional consistency, rollback on failure, trace redaction, prompt versioning, session isolation, orphan persistence, and replay security:
```bash
python -m unittest test_eval_metrics.py -v
```
All 47 unit and integration tests run offline without external API keys or live Ollama/Qdrant servers (using in-memory mocks and controlled error injection).

Key areas verified by the suite:
- **Evaluation & Retrieval Metrics**: Context relevance, answer relevance, groundedness, MRR, Hit-Rate@K, and diagnostic categorizations.
- **Qdrant Transactional Consistency**: Rollback on insertion failure, atomic add/remove/clear operations, deterministic point IDs, and payload indexing.
- **Multi-Worker & Multi-Process State Synchronization**: Atomic manifest persistence and filesystem-mtime change detection guaranteeing cache coherence and manifest synchronization across multiple Gunicorn worker processes.
- **Durable Orphan Tracking**: Persistence and resolution tracking in `orphans.jsonl`, cross-process locking (`filelock`), and crash-recovery state preservation.
- **Session & Replay Security**: Session isolation for `/orphans` and `/replay/<trace_id>`, admin authentication via `X-Admin-Key`, and sensitive path redaction.
- **Trace Auditing**: Deep redaction (`redact_deep()`), prompt version pinning and SHA-256 hash validation, and deterministic trace sampling (`sample_trace.py`).

### Interactive & Diagnostic Tools
- **`eval_retrieval.py`** — CLI tool computing `Hit-Rate@K`, `MRR`, and failure categorization directly against your indexed documents:
  ```bash
  python eval_retrieval.py
  ```
- **The `/eval` UI** (see §4) — Web-based evaluation matrix to benchmark retrieval presets against realistic HR question sets with side-by-side diagnostic drawers.
- **`/healthz` & `/readyz`** — Liveness check (`/healthz`) and readiness check (`/readyz` verifies vector store connectivity).
- **Flask Test Client** — For automated end-to-end testing of document ingestion, hybrid search, and viewer routes in offline mode.

---

## 11. Troubleshooting & FAQ

**"HTTP 429 Too Many Requests" during upload (Gemini embeddings)**
Gemini's free tier has a real requests-per-minute quota — this is the quota, not a bug. Either space out large uploads, upgrade your Gemini tier, or switch `EMBED_BACKEND=ollama` for no rate limit at all (see §7).

**"Could not reach Ollama... Connection refused"**
`ollama serve` isn't running, or the model referenced (`OLLAMA_EMBED_MODEL`/`OLLAMA_VISION_MODEL`/`OLLAMA_CHAT_MODEL`) hasn't been pulled yet. As of this fix, a failed embedding no longer fails the whole upload — the document indexes in keyword-only mode with a warning instead.

**Upload "succeeded" but semantic search doesn't seem to work for one document**
Check the upload response for a per-file `warning` field — this means embeddings failed for that specific file (see above) and it's keyword-search-only until re-uploaded with a working embeddings backend.

**Clicking "Open ↗" on a source shows "No document ID specified."**
This was a real bug (fixed): `templates/view.html` wasn't passing `doc_id` into `window.DOC_ID`. If you're still seeing it, confirm you're on the current `view.html`/`view.js`.

**Opened a PDF source but the passage isn't highlighted**
Expected for PDFs — see §5b. The page-jump (`#page=N`) works; in-document highlighting doesn't, because the browser's native PDF plugin gives no hook for it. Look for the banner showing the exact passage text, and use your browser's Find (Ctrl/Cmd+F).

**VS Code shows red errors on `{{ doc_id | tojson }}` in `view.html`**
Editor-only false positive — see the note at the end of §5b.

**Local chat model (Ollama) drops citations or answers outside the retrieved excerpts**
A known, real tradeoff of `CHAT_BACKEND=ollama` — smaller local models follow strict grounding/citation instructions less reliably than a frontier cloud model. Try `OLLAMA_CHAT_MODEL=qwen2.5` (tends to follow strict formats a bit better at similar size) before assuming the retrieval pipeline itself is broken, or switch `CHAT_BACKEND=xai` if citation discipline matters more than staying fully local.