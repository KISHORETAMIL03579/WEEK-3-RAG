<<<<<<< ours
# WEEK-3-RAG
=======
# Ask My Docs (Python)

A local RAG-style Q&A app. Upload PDFs/TXT/Markdown, ask questions in plain English, and get answers sourced directly from your documents — no external AI API, no vector DB. Pure Python + Flask + PyMuPDF.

---

## Project Structure

```
ask-my-docs-python/
├── app.py                 # Flask app — all backend logic
├── requirements.txt       # flask, PyMuPDF, werkzeug
├── templates/
│   └── index.html         # Single-page frontend (chat UI, upload, chunking modes)
├── uploads/               # Temp folder for uploaded files (auto-cleaned)
├── server.log             # App stdout (startup banner)
├── server.err.log         # Flask request log + errors
└── test_angular.pdf       # Sample test document
```

No database. Documents are held **in memory** (`DOC_STORE`) per browser session.

---

## How the Flow Works

```
 Browser ──POST /upload──►  Save file to uploads/
                              │
                              ▼
                    Text extraction
                    ├─ PDF  → PyMuPDF, per page        (app.py: extract_pdf_pages)
                    └─ TXT/MD → split on blank lines   (app.py: extract_txt_pages)
                              │
                              ▼
                    Chunking
                    ├─ structured (default) → headings/code/table parsing,
                    │    merge tiny blocks, split big ones  (app.py: structured_chunk)
                    └─ fixed (128/256/512 words) → overlapping windows
                                                  (app.py: fixed_chunk)
                              │
                              ▼
                    Store chunks in DOC_STORE[session_id]
                              │
 Browser ──POST /ask──►  TF-IDF retrieval (app.py: search_chunks)
                              │   tokenize → term frequency → IDF → cosine similarity
                              │   top-4 chunks above 0.05 threshold
                              ▼
                    Answer synthesis (app.py: synthesize_answer)
                              │   score sentences by keyword overlap with query
                              ▼
                    JSON → browser renders answer + source cards
```

### The 5 stages

1. **Upload** — `POST /upload` (multipart). Files validated by extension, saved with a UUID-prefixed name, deleted after indexing.
2. **Extraction** — PDFs read page-by-page with PyMuPDF; text files split into logical sections on `\n{3,}` blank lines. Empty/corrupt docs are skipped (corrupt PDFs return `[]`, not a crash).
3. **Chunking** — the important part for retrieval quality:
   - **Structured**: parses Markdown headings (`#`), code fences (` ``` `), and table rows into semantic blocks. Blocks under 40 words get merged; blocks over 300 words get split at sentence boundaries. Each chunk carries `page`, `section`, `block_type`, `filename` for citation.
   - **Fixed**: sliding word windows with 20% overlap (e.g. 256-word chunks stepped by 205).
4. **Retrieval** — pure-Python TF-IDF. Every chunk becomes a sparse `{term: tf·idf}` vector; the query is vectorized the same way; cosine similarity ranks chunks. Stopwords removed, tokens kept >2 chars. `CONFIDENCE_THRESHOLD = 0.05` filters weak matches.
5. **Answer** — the top-4 chunks' text is split into sentences, each scored by token overlap with the query, and the best 5 are stitched into the final answer. Sources (file, page, score, section, excerpt) are returned for the UI's source cards.

### Frontend

Single `index.html`. Manages: file drag-and-drop, chunking-mode picker (structured / 256 / 128 / 512), upload progress, document list, chat messages, source cards, and status bar. Session state (`docCount`, `chunkCount`) reloads from `GET /status` on page load.

### API

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/`       | GET  | Serve the UI |
| `/upload` | POST | Accept files + `chunk_mode`, index them |
| `/ask`    | POST | `{ "query": "..." }` → answer + sources |
| `/clear`  | POST | Wipe current session's documents |
| `/status` | GET  | Chunk/doc counts for current session |

---

## How to Start

### 1. Install dependencies (first time)

```bash
pip install -r requirements.txt
```

(Python 3.10+ recommended. Uses Flask 3.1, PyMuPDF 1.25, Werkzeug 3.1.)

### 2. Run the server

```bash
python app.py
```

Server starts at **http://localhost:5000** and prints:

```
🚀 Ask My Docs is running → http://localhost:5000
 * Debug mode: on
```

### 3. Use it

1. Open http://localhost:5000
2. Drop a PDF/TXT/MD into the sidebar (or click to browse)
3. Pick a chunking mode — **Structured** is best for headings/Q&A docs, **256/128** for finer-grained matching
4. Click **Upload & Index**
5. Type a question and press Enter — you'll get an answer plus source cards with page + match score

### Useful commands

| Task | Command |
|------|---------|
| Start server | `python app.py` |
| Install deps | `pip install -r requirements.txt` |
| Watch request log | `Get-Content server.err.log -Wait` (Windows) |
| Quick API smoke test | `curl -F "files=@doc.pdf" -F "chunk_mode=structured" http://localhost:5000/upload` |
| Clear a session | POST `/clear` (or the 🗑 button in the UI) |

---

## Notes & Limitations

- **In-memory storage** — documents are lost on server restart, and the debug reloader (`debug=True`) restarts on any `.py` change. Don't edit code while relying on loaded docs.
- **Dev server only** — `app.run(debug=True)` is for development. Use a WSGI server (gunicorn/waitress) for anything real, and don't expose it publicly.
- **Hardcoded `secret_key`** — change it if you deploy.
- **TF-IDF is keyword-based** — no semantics/synonyms, so paraphrased questions may score lower.
- **Short blocks (≤4 words)** are dropped by the structured parser — tiny tables or one-liners may not be indexed.
- Uploaded files are deleted from `uploads/` after indexing; only chunk text is kept.
>>>>>>> theirs
