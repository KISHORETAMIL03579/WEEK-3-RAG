# Ask My Docs — Universal Multimodal RAG & Retrieval Debugging Framework

A production-grade Retrieval-Augmented Generation (RAG) system built with FastAPI, React, and **pluggable local/cloud backends**. It supports **universal text extraction** (PDFs, Word Docs, CSV/Spreadsheets, Data files, Source Code, and **Images via Vision OCR**), grounded QA with clickable source citations that deep-link into the exact page, side-by-side diagnostic inspection, automated retrieval evaluation (`Hit-Rate@K`, `MRR`, `Recall@K`), and durable, replayable trace logging for error analysis.

Every model call in the pipeline — embeddings, image OCR, and chat/answer generation — is independently switchable between a **fully local, zero-API-key stack (Ollama)** and a **cloud stack (Google Gemini for embeddings/OCR, xAI Grok for chat)**. The whole app also runs with zero cloud keys at all, falling back to offline BM25/TF-IDF keyword search.

---

## ⚡ Quick Start & Setup

### 1. Environment Setup
### Option A: Complete Docker Compose Deployment (Recommended)
With Docker installed, you can start the entire stack (FastAPI + React 18 SPA, Qdrant Vector DB, Ollama inference engine, and automatic model initialization) in a single command:

```bash
# 1. Copy environment template and configure secret key
cp .env.example .env

# 2. Build and start all services in detached mode
docker compose up -d --build
```

`docker compose` automatically:
1. Builds the React 18 + TypeScript + Vite frontend and FastAPI container (`weekly-rag-build-app:latest`).
2. Starts the Qdrant vector database (`weekly-rag-build-qdrant`, image: `qdrant/qdrant:v1.13.4`).
3. Starts the Ollama inference engine (`weekly-rag-build-ollama`, image: `ollama/ollama:0.33.3`).
4. Executes `ollama_init` to automatically pull all 3 required models into the persistent `ollama_data` volume:
   - `nomic-embed-text` (Dense embeddings)
   - `llava` (Multimodal Vision OCR)
   - `llama3.1:8b` (Chat and grounded QA generation)

- **Application URL**: [http://localhost:5000](http://localhost:5000)
- **API Documentation**: [http://localhost:5000/docs](http://localhost:5000/docs) (Swagger UI) & [http://localhost:5000/redoc](http://localhost:5000/redoc)
- **Stopping the stack**: `docker compose down` (stops all services immediately with zero host background processes).

---

### Option B: Local Python Development
If you prefer running directly on your host machine:

```bash
git clone https://github.com/KISHORETAMIL03579/WEEKLY-RAG-BUILD.git
cd WEEKLY-RAG-BUILD
python -m venv .venv
.venv\Scripts\Activate.ps1
python -c "import sys; print(sys.executable)"
python -m pip install -r requirements.txt
python -c "import pymupdf, docx, fastapi, uvicorn, itsdangerous, werkzeug, qdrant_client; print('ALL IMPORTS OK')"
cp .env.example .env
```

### 2. Choose your backends (edit `.env`)
The app defaults to **fully local** — no cloud API key required at all:
Launch the application:
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
`app.py` still runs standalone — its `__main__` block now starts **uvicorn** (with the autoreloader when `APP_DEBUG=true`). Equivalent, if you prefer driving the server directly:
```bash
uvicorn app:app --host 127.0.0.1 --port 5000 --reload
```
Open **http://localhost:5000** in your browser. The startup banner tells you which mode actually loaded, e.g.:
```
🚀 Ask My Docs is running → http://localhost:5000
   Mode: embeddings (Ollama (local)) + LLM (Ollama (local))
   API docs: http://localhost:5000/docs
```
`python app.py` automatically checks if `frontend/dist` is present and builds the React 18 + Vite frontend if needed before starting Uvicorn. Open **http://localhost:5000**.

Because the app is now FastAPI, the whole JSON API is self-documenting: **Swagger UI at `/docs`**, **ReDoc at `/redoc`**, and the raw schema at **`/openapi.json`** — generated from the request/response models in `app.py`, so it cannot drift from the code.

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
| `GET` | `/docs`, `/redoc`, `/openapi.json` | Auto-generated interactive API documentation (FastAPI) |

Every path, HTTP method, request body and response body above is unchanged from the backend API contract — `frontend/src/services/api.ts` calls them with strongly typed TypeScript models. Path parameters are written `{doc_id}` internally (FastAPI syntax), and the URLs on the wire are identical.

**Request/response validation.** JSON bodies are parsed into Pydantic models (`AskRequest`, `LoadUrlRequest`, `RemoveRequest`, `EvalRunRequest`, `UploadCancelRequest`), and the fixed-shape endpoints (`/status`, `/healthz`, `/readyz`, `/traces`, `/clear`, `/remove`, `/upload-cancel`) declare response models. Endpoints whose payload genuinely varies by branch (`/ask`, `/upload`, `/load-url`, `/eval/run`, `/orphans`, `/replay/<id>`, `/file/<id>/pages`) return plain dicts so their wire format stays byte-identical.

The models are deliberately permissive where the old code was — unknown keys are ignored (`extra="ignore"`), every field is optional with the same defaults, an entirely absent body is treated as `{}`, and `top_k` / `temperature` are still *clamped* to their supported ranges rather than rejected. The one genuinely new behaviour: a value that cannot be parsed at all (e.g. `"top_k": "abc"`, previously ignored in silence) now returns **422**. That response uses this API's normal `{"error": "..."}` envelope — see `_validation_error_handler` in `app.py` — so `handleResponse()` in `frontend/src/services/api.ts` surfaces a real message rather than a bare status code, with FastAPI's structured `detail` array alongside it.

**Request size limit.** Every request body is capped at **50 MB**. Flask enforced this via `MAX_CONTENT_LENGTH`; Starlette imposes no limit of its own, so `MaxBodySizeMiddleware` in `app.py` re-implements it — rejecting an oversized `Content-Length` up front, *and* counting bytes for chunked requests that declare no length. Both paths return `413 {"error": "File too large (max 50 MB)"}`, exactly as the old `@app.errorhandler(413)` did.

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

Clicking **Open ↗** on any source card navigates to `/#/file/<doc_id>?page=N&hl=<snippet>` in the React SPA. What happens next depends on file type:

- **Non-PDF documents** (`.txt`, `.md`, extracted Word/CSV/code text) render through the React page-by-page viewer (`frontend/src/pages/ViewerPage.tsx`) with **real in-page highlighting**: the `hl` snippet (the first ~100 characters of the actual retrieved chunk, not the raw question — the question almost never appears verbatim in the source) is matched against the page text with a whitespace-flexible regex, since chunk text gets newlines collapsed during ingestion while the raw page text keeps them.
- **PDF documents** are handed to the **browser's own native PDF plugin** via `<embed>` with `/file/{doc_id}/raw` — there is no API surface for us to inject a highlight into that renderer's content. What *does* work: the standard `#page=N` URL fragment (supported by Chrome/Firefox/Safari/Edge/Brave) jumps straight to the cited page. For the passage itself, a banner above the embed shows the exact excerpt text to look for, with a nudge to use the browser's native Find (Ctrl/Cmd+F) — an honest fallback rather than a highlight that silently does nothing.

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
| **Main React Application** | `frontend/src/pages/ChatPage.tsx` | React 18 Chat UI, `SourceItem` grounded-source cards, Dropzone, Staged File List |
| **Evaluation React UI** | `frontend/src/pages/EvaluationPage.tsx` | React 18 Evaluation Matrix & Inspection Drawer |
| **Document Viewer React UI** | `frontend/src/pages/ViewerPage.tsx` | React 18 Embedded Document Viewer, page-jump + highlight logic |

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
| `SECRET_KEY` | *(random per-process if unset)* | Signs session cookies (Starlette `SessionMiddleware`, itsdangerous) — **mandatory in production** to preserve session continuity across worker restarts |
| `APP_ENV` | *(empty)* | Set to `production` to make `SECRET_KEY` mandatory (boot fails without it). `ENV` / `FLASK_ENV` still work as legacy aliases |
| `SESSION_COOKIE_SECURE` | `false` | Adds the `Secure` flag to the session cookie. Enable **only** behind TLS — browsers silently drop `Secure` cookies over plain HTTP |
| `ADMIN_API_KEY` | *(empty)* | Optional administrative token for inspecting cross-session `/orphans` and replaying traces via `X-Admin-Key` header |
| `LOG_LEVEL` | `INFO` | `DEBUG` / `INFO` / `WARNING` / `ERROR` |
| `PORT` / `HOST` | `5000` / `127.0.0.1` | Set `HOST=0.0.0.0` when running inside Docker |
| `APP_DEBUG` | `false` | Turns on uvicorn's autoreloader + debug logging for `python app.py` — never enable outside local dev |

---

## 8. Docker & Docker-Compose Deployment
 
The repository provides a single canonical [`docker-compose.yml`](file:///d:/RAG_WEEK_3/WEEK-3-RAG/docker-compose.yml) orchestrating the production multi-container deployment:

```bash
docker compose up -d --build
```

### Services Managed by Docker Compose:
1. **`weekly-rag-build-app`**:
   - Multi-stage build (`Dockerfile`): Stage 1 compiles the React 18 + TypeScript + Vite SPA into `/build/frontend/dist`; Stage 2 sets up Python 3.11-slim runtime with non-root `appuser`.
   - Served via **Gunicorn with Uvicorn ASGI workers** (`gunicorn app:app -k uvicorn_worker.UvicornWorker --workers 2 --timeout 120`).
   - Published securely on `127.0.0.1:5000:5000`.
   - Connected via Docker internal DNS to `http://qdrant:6333` and `http://ollama:11434`.
2. **`weekly-rag-build-qdrant`**:
   - Official `qdrant/qdrant:v1.13.4` vector database.
   - Named volume `qdrant_data:/qdrant/storage` guarantees all indexed vector embeddings persist across container restart and down/up cycles.
   - Socket-based `/readyz` healthcheck (`exec 3<>/dev/tcp/127.0.0.1/6333`).
3. **`weekly-rag-build-ollama`**:
   - Official `ollama/ollama:0.33.3` inference engine running entirely within Docker.
   - Port mapped to `127.0.0.1:11434:11434`.
   - Named volume `ollama_data:/root/.ollama` stores all model weights persistently without cluttering host machine storage.
4. **`weekly-rag-build-ollama-init`**:
   - One-shot initialization container that waits for `ollama` health, checks downloaded models, and automatically and idempotently pulls:
     - `nomic-embed-text` (Embeddings)
     - `llava` (Vision OCR)
     - `llama3.1:8b` (Chat / Generation)

---

### Image Updates & Rebuilding with Latest Code
When you make code changes and run:
```bash
docker compose up -d --build
```
- Docker builds the new `weekly-rag-build-app:latest` image using Docker layer caching (avoiding re-downloading npm or pip packages if `package.json` / `requirements.txt` haven't changed).
- The existing container is replaced seamlessly in-place.
- Old untagged build layers can be cleaned anytime with `docker image prune -f`.
- **Downloaded models and vectors are preserved**: Because models are stored in `ollama_data` and vectors in `qdrant_data`, rebuilding the application image does **not** re-download model weights or wipe indexed documents!

---

### Clean Lifecycle Management (Stopping & Starting)
Because Ollama runs strictly inside its Docker container (and not as a host background service):
- **Start stack**: `docker compose up -d`
- **Check status**: `docker compose ps`
- **View live logs**: `docker compose logs -f`
- **Stop everything cleanly**: `docker compose down` (instantly stops and removes containers; zero processes remain on host machine)
- **Reset all data**: `docker compose down -v` (removes named volumes `qdrant_data` and `ollama_data`)

---

### Production Network & Reverse Proxy Architecture
In production deployments, the application should never be exposed directly to the public internet without a reverse proxy or cloud load balancer:
```text
Internet / Clients
       │
       ▼
Reverse Proxy / LB (Nginx / Caddy / Cloudflare / AWS ALB)
       │
       ▼ [127.0.0.1:5000 / Internal Docker Network]
Gunicorn process manager (2 uvicorn ASGI workers, 120s timeout)
       │
       ▼
FastAPI Application (Ask My Docs)
  ├── Qdrant Vector Store (http://qdrant:6333)
  └── Ollama Model Inference (http://ollama:11434)
```
```

> **Concurrency model:** every route handler is a plain `def`, not `async def`. Starlette runs sync handlers in a threadpool, so the app's blocking `urllib.request` calls to Ollama / Gemini / xAI, blocking file I/O, and blocking Qdrant client calls behave exactly as they did under Gunicorn's sync workers — no event loop to starve. Converting the I/O layer to `httpx.AsyncClient` / an async Qdrant client would be a separate, much larger change.
> **Concurrency model:** every route handler is a plain `def`, not `async def`. Starlette runs sync handlers in a threadpool, so the app's blocking `urllib.request` calls to Ollama / Gemini / xAI, blocking file I/O, and blocking Qdrant client calls behave safely — no event loop starvation.

To point at **Qdrant Cloud** instead of the bundled container, set in your `.env` before running compose:
```bash
VECTOR_BACKEND=qdrant
QDRANT_URL=https://xxxx.aws.cloud.qdrant.io:6333
QDRANT_API_KEY=<your cluster key>
```

The `app` container's health check hits `/healthz` directly via Python standard library — a fast way to confirm the container came up healthy: `docker compose ps`.

> **Production Secrets Enforcement:**
> `docker-compose.yaml` enforces `${SECRET_KEY:?SECRET_KEY must be set in .env to preserve session continuity}`. Startup will fail fast with a descriptive error if `SECRET_KEY` is omitted, preventing inadvertent deployment with ephemeral per-process session cookies.
> `docker-compose.yml` enforces `${SECRET_KEY:?SECRET_KEY must be set in .env to preserve session continuity}`. Startup will fail fast with a descriptive error if `SECRET_KEY` is omitted, preventing inadvertent deployment with ephemeral per-process session cookies.

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
All 60 unit and integration tests run offline without external API keys or live Ollama/Qdrant servers (using in-memory mocks and controlled error injection).

Key areas verified by the suite:
- **Evaluation & Retrieval Metrics**: Context relevance, answer relevance, groundedness, MRR, Hit-Rate@K, and diagnostic categorizations.
- **Qdrant Transactional Consistency**: Rollback on insertion failure, atomic add/remove/clear operations, deterministic point IDs, and payload indexing.
- **Multi-Worker & Multi-Process State Synchronization**: Atomic manifest persistence and filesystem-mtime change detection guaranteeing cache coherence and manifest synchronization across multiple Gunicorn worker processes.
- **Durable Orphan Tracking**: Persistence and resolution tracking in `orphans.jsonl`, cross-process locking (`filelock`), and crash-recovery state preservation.
- **Session & Replay Security**: Session isolation for `/orphans` and `/replay/<trace_id>`, admin authentication via `X-Admin-Key`, and sensitive path redaction.
- **Trace Auditing**: Deep redaction (`redact_deep()`), prompt version pinning and SHA-256 hash validation, and deterministic trace sampling (`sample_trace.py`).
- **Web-Layer Contracts** (`TestFastAPIMigration`): the 50 MB body cap on both the `Content-Length` and chunked/streamed paths, session-cookie round-tripping and tamper rejection, the `/assets` static mount for compiled Vite assets, the full route table the frontend depends on, and the shared "No active session" 400 contract.

### Interactive & Diagnostic Tools
- **`eval_retrieval.py`** — CLI tool computing `Hit-Rate@K`, `MRR`, and failure categorization directly against your indexed documents:
  ```bash
  python eval_retrieval.py
  ```
- **The `/eval` UI** (see §4) — Web-based evaluation matrix to benchmark retrieval presets against realistic HR question sets with side-by-side diagnostic drawers.
- **`/healthz` & `/readyz`** — Liveness check (`/healthz`) and readiness check (`/readyz` verifies vector store connectivity).
- **`/docs` & `/redoc`** — Auto-generated interactive API documentation. Swagger UI at `/docs` will execute real requests against the running app, which makes it a usable manual test console for every endpoint in §5.
- **FastAPI Test Client** (`from fastapi.testclient import TestClient`) — For automated end-to-end testing of document ingestion, hybrid search, and viewer routes in offline mode. It keeps a cookie jar across calls on the same instance, so session-scoped flows work the same way Flask's test client handled them. Flask's `client.session_transaction()` has no direct equivalent; `set_session()` in `test_eval_metrics.py` mints the signed session cookie directly instead (same itsdangerous mechanism the middleware uses).

---

## 11. Troubleshooting & FAQ

**"HTTP 429 Too Many Requests" during upload (Gemini embeddings)**
Gemini's free tier has a real requests-per-minute quota — this is the quota, not a bug. Either space out large uploads, upgrade your Gemini tier, or switch `EMBED_BACKEND=ollama` for no rate limit at all (see §7).

**"Could not reach Ollama... Connection refused"**
`ollama serve` isn't running, or the model referenced (`OLLAMA_EMBED_MODEL`/`OLLAMA_VISION_MODEL`/`OLLAMA_CHAT_MODEL`) hasn't been pulled yet. As of this fix, a failed embedding no longer fails the whole upload — the document indexes in keyword-only mode with a warning instead.

**Upload "succeeded" but semantic search doesn't seem to work for one document**
Check the upload response for a per-file `warning` field — this means embeddings failed for that specific file (see above) and it's keyword-search-only until re-uploaded with a working embeddings backend.

**Opened a PDF source but the passage isn't highlighted**
Expected for PDFs — see §5b. The page-jump (`#page=N`) works; in-document highlighting doesn't, because the browser's native PDF plugin gives no hook for it. Look for the banner showing the exact passage text, and use your browser's Find (Ctrl/Cmd+F).

**Local chat model (Ollama) drops citations or answers outside the retrieved excerpts**
A known, real tradeoff of `CHAT_BACKEND=ollama` — smaller local models follow strict grounding/citation instructions less reliably than a frontier cloud model. Try `OLLAMA_CHAT_MODEL=qwen2.5` (tends to follow strict formats a bit better at similar size) before assuming the retrieval pipeline itself is broken, or switch `CHAT_BACKEND=xai` if citation discipline matters more than staying fully local.