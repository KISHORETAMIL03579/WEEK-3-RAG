# Ask My Docs — Universal Multimodal RAG & Retrieval Debugging Framework

A production-grade Retrieval-Augmented Generation (RAG) system built with Flask, React, and Google Gemini API. It supports **universal text extraction** (PDFs, Word Docs, CSV/Spreadsheets, Data files, Source Code, and **Images via Gemini 3.7 Vision OCR**), grounded QA with source citations, side-by-side diagnostic inspection, and automated retrieval evaluation (`Hit-Rate@K`, `MRR`, and `Recall@K`).

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
```

### 2. VS Code Interpreter Selection
```text
Ctrl + Shift + P
       ↓
Python: Select Interpreter
       ↓
.venv\Scripts\python.exe
```

### 3. Launch the Application
```bash
python app.py
```
Open **http://localhost:5000** in your browser.

---

## 📖 Table of Contents
1. [System Workflows & How It Works](#1-system-workflows--how-it-works)
   - [Workflow 1: Document Upload & Indexing](#workflow-1-document-upload--indexing)
   - [Workflow 2: Grounded Question-Answering](#workflow-2-grounded-question-answering)
   - [Workflow 3: Multimodal Image OCR](#workflow-3-multimodal-image-ocr)
   - [Workflow 4: Automated Evaluation & Ablation Matrix (`/eval`)](#workflow-4-automated-evaluation--ablation-matrix-eval)
   - [Workflow 5: Document Session Lifecycle](#workflow-5-document-session-lifecycle)
2. [Universal File Extraction & Vision OCR](#2-universal-file-extraction--vision-ocr)
3. [Retrieval & RAG System Architecture](#3-retrieval--rag-system-architecture)
4. [Deep Dive: Evaluation Suite & Metrics (`/eval`)](#4-deep-dive-evaluation-suite--metrics-eval)
5. [Backend API Endpoints Architecture](#5-backend-api-endpoints-architecture)
6. [Codebase Function & File Mapping](#6-codebase-function--file-mapping)
7. [Configuration & Environment Variables (`.env`)](#7-configuration--environment-variables-env)
8. [Docker & Docker-Compose Deployment](#8-docker--docker-compose-deployment)
9. [GHCR Container Deployment](#9-ghcr-container-deployment)
10. [Troubleshooting & FAQ](#10-troubleshooting--faq)

---

## 1. System Workflows & How It Works

```text
 ┌──────────┐     ┌───────────┐     ┌───────────┐     ┌──────────────┐
 │  Upload  │ ──► │ Universal │ ──► │ Chunking  │ ──► │ Gemini       │
 │ PDF/Code/│     │ Extract & │     │ (Structured│    │ Embeddings   │
 │ Image    │     │ Vision OCR│     │ or Fixed) │     │ (3072 dim)   │
 └──────────┘     └───────────┘     └───────────┘     └──────┬───────┘
                                                             │
                                                             ▼
                                                    ┌──────────────────┐
                                                    │   VectorStore    │
                                                    │ (Qdrant / Local) │
                                                    └─────────┬────────┘
                                                              │
      ┌───────────────────────────────────────────────────────┘
      ▼
 ┌──────────┐     ┌────────────────┐     ┌─────────────┐     ┌───────────┐
 │ Ask a    │ ──► │ Hybrid Search  │ ──► │ Context     │ ──► │ Grounded  │
 │ Question │     │ (BM25 + Dense  │     │ Validation  │     │ Answer    │
 │          │     │  RRF Fusion)   │     │ Threshold   │     │ Synthesis │
 └──────────┘     └───────────┘     └─────────────┘     └───────────┘
```

### Workflow 1: Document Upload & Indexing
1. **User Action**: You drop files (PDF, Word, Code, CSV, Image) into the dropzone or type a web URL.
2. **Staging**: The UI validates file extension and size, staging it in the active upload list.
3. **Chunk Strategy Selection**: You select a chunking strategy (`structured`, `128`, `256`, `512` words).
4. **Backend Processing (`/upload`)**:
   - Text is extracted per page or block.
   - Text chunks are generated based on headings and paragraph boundaries.
   - 3072-dimensional embeddings are generated via Gemini `gemini-embedding-001`.
   - Vectors and payload metadata (page, filename, chunk ID) are stored in **Qdrant Vector DB**.
5. **UI Update**: Document list updates with chunk count, file size, and indexed status.

---

### Workflow 2: Grounded Question-Answering
1. **User Action**: You type a question in the chat input (e.g. *"What is the password length requirement under SEC-808?"*).
2. **Search Query Normalization**: If `QUERY_REWRITE_ENABLED=true`, an LLM call simplifies conversational fluff into a clean search query.
3. **Hybrid Retrieval**:
   - **BM25 Keyword Search**: Finds exact term occurrences (`SEC-808`).
   - **Dense Vector Search**: Finds semantic concepts.
   - **Reciprocal Rank Fusion (RRF)**: Fuses both rankings using $RRF(c) = \sum \frac{1}{k + r(c)}$.
4. **Context Validation Gate**: Checks if top match score clears `EMBED_MIN_SCORE` (`0.55`).
   - If match score < 0.55: Immediately outputs *"I don't know."* to prevent hallucination.
5. **Answer Synthesis**: Validated context chunks are passed to **Gemini 3.7 Flash** with strict grounding rules.
6. **Citations & Inspection**: Returns the synthesized answer alongside clickable source cards. Clicking **Open ↗** opens the document viewer at the exact page.

---

### Workflow 3: Multimodal Image OCR
1. **User Action**: You upload an image file (`.png`, `.jpg`, `.webp`, `.tiff`, `.bmp`).
2. **Base64 Payload Encoding**: `app.py` reads the binary image bytes and converts them into a base64 `inline_data` object.
3. **Gemini Vision OCR Call**: Calls **Gemini 3.7 Flash** with prompt:
   *"Extract all text, table content, diagram descriptions, titles, bullet points, and key information into Markdown."*
4. **Markdown Chunking & Embedding**: Transcribed Markdown text is chunked and embedded like standard text documents.

---

### Workflow 4: Automated Evaluation & Ablation Matrix (`/eval`)
1. **User Action**: Navigate to `/eval`. Enter test Q/A pairs or upload a Q/A benchmark PDF.
2. **Preset Selection**: Select ablation ladder presets (`tfidf`, `bm25-qdrant-blend`, `bm25-qdrant-rrf`, `rrf-rerank`, `rrf-rerank-rewrite`).
3. **Execution (`/eval/run`)**: Each preset runs questions through its respective retrieval pipeline.
4. **Metric Calculation**: Computes **`Hit-Rate@K`**, **`MRR`**, **`Recall@K`**, and classifies failure types (`Success`, `Retrieval Failure`, `Generation Failure`).
5. **Side-by-Side Diagnostic Drawer**: Clicking any question opens an inspection drawer showing candidate chunks, raw scores, RRF ranks, and LLM answers.

---

### Workflow 5: Document Session Lifecycle
- **Session Isolation**: Each user browser session receives a unique `session_id` and isolated vector collection.
- **Single File Removal (`/remove`)**: Deletes chunks for a specific document and purges its deduplication hash.
- **Session Reset (`/clear`)**: Clears all indexed vectors, uploaded files, and session state.

---

## 2. Universal File Extraction & Vision OCR

| File Category | Extensions | Extraction Method & Behavior |
| :--- | :--- | :--- |
| **Images (Vision OCR)** | `.png`, `.jpg`, `.jpeg`, `.webp`, `.bmp`, `.tiff`, `.gif` | **Gemini 3.7 Flash Vision API**: Transcribes visual text, tables, numbers, diagram annotations, and notes into Markdown. |
| **Word Documents** | `.docx`, `.doc` | **python-docx Extractor**: Parses paragraph text, headings, and data tables. |
| **Spreadsheets & Data** | `.csv`, `.tsv`, `.json`, `.xml`, `.yaml`, `.yml` | **Data Formatter**: Converts tabular data into Markdown tables and formatted code blocks. |
| **Source Code & Config** | `.py`, `.js`, `.ts`, `.jsx`, `.tsx`, `.html`, `.css`, `.c`, `.cpp`, `.java`, `.go`, `.rs`, `.php`, `.sql`, `.sh`, `.log`, `.env` | **Code Block Wrapper**: Preserves code formatting inside syntax fences. |
| **Standard Documents** | `.pdf`, `.txt`, `.md`, `.markdown`, `.rst` | **PyMuPDF / Section Splitter**: Page-by-page and heading-based extraction. |

---

## 3. Retrieval & RAG System Architecture

### Why Hybrid Search (BM25 + Dense Embeddings)?
- **Dense Embeddings**: Match semantic meaning (e.g., *"How do I get my money back?"* matches *"refund policy"*).
- **BM25 Keyword Search**: Matches exact technical terms, acronyms, product SKUs, and error codes (e.g., `ERR-4032`, `SEC-808`, `WFH-04`).
- **Reciprocal Rank Fusion (RRF)**: Merges sparse BM25 and dense vector rankings using $RRF(c) = \sum \frac{1}{k + r(c)}$, avoiding raw score normalization issues.

---

## 4. Deep Dive: Evaluation Suite & Metrics (`/eval`)

### 4.1 Failure Mode Categorization
- **`Success`**: Right document/section retrieved in top-K, correct answer synthesized.
- **`Retrieval Failure`**: Target ground-truth document was missing from top-K candidates (`Hit-Rate@K == 0`).
- **`Generation Failure`**: Right document retrieved, but LLM failed to synthesize a correct answer.

### 4.2 Quantitative Evaluation Metrics
- **`Hit-Rate@K`** (e.g. `Hit-Rate@3`): Percentage of test questions where the correct document appeared in the top-K retrieved candidates.
- **`MRR` (Mean Reciprocal Rank)**: Measures average reciprocal rank ($1/\text{rank}$) across all test queries.
- **`Recall@K`**: Ratio of expected section coverage.

---

## 5. Backend API Endpoints Architecture

| HTTP Method | Route | Description |
| :--- | :--- | :--- |
| `POST` | `/upload` | Universal file upload & vector indexing endpoint |
| `POST` | `/load-url` | Web page fetch & HTML text extraction endpoint |
| `POST` | `/ask` | Hybrid retrieval & grounded QA endpoint |
| `GET` | `/status` | Returns session indexed document counts & backend info |
| `POST` | `/remove` | Removes a specific document from vector store |
| `POST` | `/clear` | Clears all documents and vectors for the current session |
| `POST` | `/eval/run` | Runs evaluation benchmark matrix across presets |
| `GET` | `/view/<filename>` | Renders document page viewer |
| `GET` | `/healthz` | System liveness & health check endpoint |

---

## 6. Codebase Function & File Mapping

| Feature / Logic | File Location | Key Function / Component |
| :--- | :--- | :--- |
| **Universal File Extraction** | [`app.py`](file:///d:/AI/WEEK-3-RAG/app.py) | `extract_document_pages()`, `extract_image_pages()`, `extract_docx_pages()` |
| **Gemini Vision OCR** | [`app.py`](file:///d:/AI/WEEK-3-RAG/app.py) | `extract_image_pages()` (inline_data base64 payload) |
| **Semantic & Fixed Chunking** | [`app.py`](file:///d:/AI/WEEK-3-RAG/app.py) | `chunk_text()`, `structured_chunk()`, `fixed_chunk()` |
| **Qdrant Vector DB Backend** | [`qdrant_store.py`](file:///d:/AI/WEEK-3-RAG/qdrant_store.py) | `QdrantVectorStore`, `add()`, `query()` |
| **Hybrid Search & RRF** | [`app.py`](file:///d:/AI/WEEK-3-RAG/app.py) | `reciprocal_rank_fusion()`, `hybrid_search()` |
| **Context Validation Gate** | [`app.py`](file:///d:/AI/WEEK-3-RAG/app.py) | `validate_context()` |
| **LLM Reranker & Rewriter** | [`app.py`](file:///d:/AI/WEEK-3-RAG/app.py) | `rerank_with_llm()`, `rewrite_query()` |
| **Evaluation Suite & Matrix** | [`app.py`](file:///d:/AI/WEEK-3-RAG/app.py) & [`eval_retrieval.py`](file:///d:/AI/WEEK-3-RAG/eval_retrieval.py) | `/eval/run`, `_run_eval_preset()`, `recall_at_k()` |
| **Main React Application** | [`static/js/app.js`](file:///d:/AI/WEEK-3-RAG/static/js/app.js) | React Chat UI, Dropzone, Staged File List |
| **Evaluation React UI** | [`static/js/eval.js`](file:///d:/AI/WEEK-3-RAG/static/js/eval.js) | React Evaluation Matrix & Inspection Drawer |
| **Document Viewer React UI** | [`static/js/view.js`](file:///d:/AI/WEEK-3-RAG/static/js/view.js) | React Embedded Document Viewer |

---

## 7. Configuration & Environment Variables (`.env`)

| Variable | Default | Description |
| :--- | :--- | :--- |
| `GEMINI_API_KEY` | *(required)* | Google Gemini API Key |
| `LLM_MODEL` | `gemini-3.7-flash` | Gemini LLM for QA synthesis & Vision OCR |
| `EMBED_MODEL` | `gemini-embedding-001` | Embedding model (`3072` vector dimensions) |
| `VECTOR_BACKEND` | `qdrant` | Vector backend (`qdrant` or `memory`) |
| `QDRANT_URL` | *(url)* | Qdrant Cloud or local endpoint (`http://localhost:6333`) |
| `QDRANT_SCROLL_LIMIT` | `5000` | Vector retrieval scroll limit |
| `RETRIEVAL_MODE` | `hybrid` | Search strategy (`hybrid`, `embed`, `tfidf`) |
| `EMBED_MIN_SCORE` | `0.55` | Context validation threshold gate |
| `TOP_K` | `8` | Candidate chunks retrieved |
| `MAX_CONTEXT_TOKENS` | `6000` | Context token budget cap |
| `RERANK_ENABLED` | `true` | Enables second-pass LLM reranker |
| `QUERY_REWRITE_ENABLED` | `true` | Enables query rewriting |
| `DEFAULT_CHUNK_MODE` | `structured` | Default chunking strategy |
| `DEFAULT_CHUNK_SIZE` | `512` | Default chunk size |

---

## 8. Testing & Functional Verification

The codebase includes an end-to-end integration test suite and metric benchmark verification scripts:

### Automated Integration Test Suite (`scratch/test_rag.py`)
Runs automated testing across all endpoints:
```bash
python scratch/test_rag.py
```
**Tests Covered**:
- `test_healthz`: Verifies server health check response (`200 OK`).
- `test_status`: Verifies Qdrant vector store payload counts.
- `test_chunking_strategies`: Tests `structured`, `128`, `256`, `512` word chunkers.
- `test_tfidf_fallback`: Verifies offline BM25 fallback path without API keys.
- `test_upload_endpoint`: Verifies file ingestion, text parsing, and Qdrant indexing.
- `test_ask_endpoint`: Verifies hybrid search, RRF fusion, context validation gate, and LLM answer synthesis.

**Execution Result**:
```text
Ran 6 tests in 9.160s
OK (100% Passed)
```

---

### Real-Time HR Policy Benchmark Suite (`scratch/test_hr_policy_realtime.py`)
Runs an end-to-end benchmark against a realistic 7-section HR & Security policy document:
```bash
python scratch/test_hr_policy_realtime.py
```

---

### CLI Retrieval Evaluation Tool (`eval_retrieval.py`)
Computes `Hit-Rate@K`, `MRR`, and failure categorization directly from the command line:
```bash
python eval_retrieval.py
```