# Ask My Docs — Full Project Guide
A minimal Retrieval-Augmented Generation (RAG) app: upload documents, ask questions, get answers grounded **only** in what you uploaded, with a link back to the exact source. If the answer isn't in the documents, it says so instead of guessing.

---

## 1. Project structure
```
project/
├── app.py                 # Flask backend — all the logic lives here
├── eval_retrieval.py       # standalone recall@k harness (retrieval quality testing)
├── templates/
│   ├── index.html          # main chat UI (upload, chunking strategy, chat)
│   └── view.html           # "Open document" viewer (opened in a new tab)
├── uploads/                 # uploaded files land here (created automatically)
├── vectorstore/             # per-session pickled chunk+vector indexes (auto-created)
└── .env                     # optional — API keys / config (see §3)
```
`index.html` and `view.html` **must** be inside a `templates/` folder — that's where Flask's `render_template()` looks for them by default.

---

## 2. What the app actually does (plain-English flow)
```
 ┌──────────┐     ┌───────────┐     ┌───────────┐     ┌──────────────┐
 │  Upload  │ ──► │  Extract  │ ──► │   Chunk   │ ──► │    Embed     │
 │ PDF/TXT/ │     │   text    │     │  (split   │     │ (turn text   │
 │ MD / URL │     │  per page │     │  into     │     │  into number │
 │          │     │           │     │  pieces)  │     │  vectors)    │
 └──────────┘     └───────────┘     └───────────┘     └──────┬───────┘
                                                              │
                                                              ▼
                                                     ┌──────────────────┐
                                                     │   VectorStore     │
                                                     │ (chunks + vectors, │
                                                     │  pickled to disk)  │
                                                     └─────────┬─────────┘
                                                               │
      ┌────────────────────────────────────────────────────────┘
      ▼
 ┌──────────┐     ┌────────────────┐     ┌─────────────┐     ┌───────────┐
 │   Ask a  │ ──► │    Retrieve    │ ──► │  Validate   │ ──► │  Generate  │
 │ question │     │ (hybrid search:│     │ (is the top │     │  grounded  │
 │          │     │  embeddings +  │     │  score good │     │  answer +  │
 │          │     │  TF-IDF blend) │     │  enough?)   │     │  citations │
 └──────────┘     └────────────────┘     └──────┬──────┘     └───────────┘
                                                  │ no
                                                  ▼
                                          "I don't know."
```
### Step by step
1. **Upload** — a PDF, `.txt` , `.md` , or a URL goes to `/upload`  or `/load-url` .
2. **Extract** — text is pulled out per page (PDF via PyMuPDF) or per logical section (TXT/MD split on blank lines; web pages stripped of HTML tags).
3. **Chunk** — the extracted text is split into small pieces ("chunks") using one of four strategies (see §5). Chunk size matters: too big and irrelevant text rides along with the answer; too small and related context gets separated.
4. **Embed** — each chunk's text is sent to an embedding model (via OpenRouter) which returns a vector — a list of numbers representing the chunk's _meaning_, not just its words. This is what lets the app match "How do I get my money back?" to a chunk about "refunds" even though no words overlap.
5. **Store** — chunks + vectors are kept in memory in a `VectorStore`  and also pickled to disk (`vectorstore/<session_id>.pkl` ) so a page reload doesn't lose your index.
6. **Ask** — your question is embedded the same way, then compared against every stored chunk's vector using **cosine similarity** (how close two vectors point in the same direction — 1.0 = identical meaning, 0 = unrelated). This app also blends in a **TF-IDF** score (classic keyword-overlap scoring) so exact tokens like error codes or IDs aren't lost to fuzzy semantic matching. See §6 for why both.
7. **Validate** — if the best match's score doesn't clear a minimum threshold, the app returns "I don't know" instead of forcing an answer from irrelevant chunks.
8. **Generate** — the top-matching chunks are handed to an LLM with a strict instruction: _answer only from these excerpts, cite each fact like [1] or [2], and say "I don't know" if they're not enough._ The chunks' source (filename + page/section) are shown as clickable source cards under the answer.
---

## 3. How to run it
### Requirements
```bash
pip install flask pymupdf werkzeug waitress
```
(`waitress` is optional — a production-friendly WSGI server; the app falls back to Flask's built-in dev server if it isn't installed.)

### Configuration (optional but recommended)
Create a `.env` file next to `app.py`:

```
OPENROUTER_API_KEY=sk-or-...
LLM_MODEL=deepseek/deepseek-chat
EMBED_MODEL=openai/text-embedding-3-small
EMBED_MIN_SCORE=0.30
RETRIEVAL_MODE=hybrid
HYBRID_ALPHA=0.6
PORT=5000
```
- `**OPENROUTER_API_KEY**`  — get one at [openrouter.ai](https://openrouter.ai/) . Without it, the app still works but falls back to a fully offline TF-IDF-only mode (no embeddings, no LLM-generated answers — it stitches together the most relevant sentences instead).
- `**RETRIEVAL_MODE**`  — `hybrid`  (default) blends embeddings + TF-IDF; `embed`  uses embeddings alone (useful for an A/B comparison, see §7).
- `**EMBED_MIN_SCORE**`  — the similarity threshold below which the app says "I don't know" rather than answer from weak matches. Lower this if it's too eager to give up; raise it if it's answering from irrelevant chunks.
### Run
```bash
python app.py
```
You'll see:

```
🚀 Ask My Docs is running → http://localhost:5000
   Mode: embeddings + LLM   (or "TF-IDF (offline fallback)" if no API key)
```
Open that URL in a browser.

### Using it
1. Drop a PDF/TXT/MD file (or paste a URL) in the sidebar.
2. Pick a chunking strategy (Structured is recommended — see §5).
3. Click **Upload & Index document**.
4. Ask a question in the chat box.
5. Read the answer, check the **Sources** cards underneath — click **Open ↗** to view the exact page/section the answer came from.
6. Click **✕** on a document to remove it, or **Clear all documents** to reset the whole session.
---

## 4. Where each piece of logic lives in `app.py` 
| Concern | Function / class |
| ----- | ----- |
| PDF text extraction | `extract_pdf_pages()`  |
| TXT/MD text extraction | `extract_txt_pages()`  |
| Web page fetch + HTML stripping | `fetch_web_page()`, `_TextExtractor`  |
| Fixed-size chunking (128/256/512 words) | `fixed_chunk()`  |
| Structured chunking (headings/paragraphs/tables/code) | `structured_chunk()`, `parse_blocks()`  |
| Sentence splitting (used by structured chunking + fallback answers) | `split_sentences()`  |
| Calling the embeddings API | `embed_text()`, `embed_texts()`  |
| In-memory + on-disk chunk/vector index | `VectorStore` class |
| TF-IDF scoring (offline fallback + hybrid blend) | `tokenize()`, `compute_tf()`, `compute_idf()`, `tfidf_vector()`, `cosine_sim()`  |
| <p>**Hybrid retrieval**</p><p> (this week's improvement)</p> | `hybrid_search()`  |
| "Is this good enough to answer from?" | `validate_context()`  |
| LLM-grounded answer with citations | `generate_answer()`  |
| Offline template-based answer (no API key) | `synthesize_answer()`  |
| Session/document lifecycle (upload, remove, clear, expiry) | `/upload`, `/remove`, `/clear`, `_get_store()`  |
---

## 5. Chunking strategies — what they are and why size matters
| Strategy | What it does | Trade-off |
| ----- | ----- | ----- |
| <p>**Structured**</p><p> (recommended)</p> | Parses headings, paragraphs, code blocks, and tables as distinct blocks; merges tiny fragments together and splits huge ones at sentence boundaries (40–300 words per chunk) | Keeps semantically related text together; best default for mixed-content docs |
| **128 words** | Fixed-size chunks with 20% overlap | Very granular — good for pinpointing exact facts/codes, but a lot of chunks, less surrounding context per chunk |
| **256 words** | Same, larger chunks | A balance between granularity and context |
| **512 words** | Same, largest chunks | More context per chunk, but multiple unrelated ideas can end up sharing one chunk, so a retrieved match may drag in irrelevant text alongside the right answer |
**Why it matters, concretely:** if a chunk is too big, it might contain two unrelated FAQ answers glued together — retrieval finds the chunk correctly, but the LLM has to sift the right sentence out of noise, and citations get fuzzy. If a chunk is too small, one idea can get split across two chunks, and retrieval might grab only half the context needed to answer fully. The sidebar's **"Compare chunk sizes"** panel shows you the resulting chunk count for each strategy on your actual uploaded document, so you can see this trade-off directly instead of guessing.

---

## 6. Why hybrid retrieval (embeddings + TF-IDF)
- **Embeddings** are great at _meaning_: "How do I get my money back?" matches a chunk about "refunds" even with zero shared words.
- **TF-IDF** is great at _exact tokens_: an error code like `ERR-4032` , a product SKU, or a rare acronym can get semantically "blurred" by an embedding model into a fuzzy neighborhood of similar-sounding text, causing the exact chunk to rank lower than it should. TF-IDF scores exact/rare-word overlap directly, so it nails these cases.
`hybrid_search()` computes both scores per chunk and blends them:

```
combined_score = HYBRID_ALPHA * embedding_score + (1 - HYBRID_ALPHA) * tfidf_score
```
`HYBRID_ALPHA` (default `0.6`) controls the blend — higher favors meaning matching, lower favors exact keyword matching.

---

## 7. Measuring whether a change actually helped
`eval_retrieval.py` is a standalone script (not part of the running web app) for proving retrieval quality with a number instead of a feeling.

### What it measures
**Recall@k** — for a set of questions where you already know the correct source document, what fraction of the time does that document appear among the top-k retrieved chunks? This is checked _before_ generation, so it isolates:

- **"Wrong document fetched"** → recall@k says no → retrieval problem.
- **"Right document, wrong answer"** → recall@k says yes, but the /ask answer was still wrong → generation problem (prompt, model, chunk contents) — this script can't measure that part; you check it manually in the running app.
### How to run it
1. Open `eval_retrieval.py` .
2. Fill in `DOCS`  with paths to your real uploaded files: DOCS = [    ("./uploads/errors.md", "errors.md"),    ("./uploads/refund_policy.pdf", "refund_policy.pdf"),]
3. Fill in `QUESTIONS`  with real questions + which document should answer each one: QUESTIONS = [    {"question": "What does error code ERR-4032 mean?", "expected_doc": "errors.md"},    {"question": "How many days for a refund request?", "expected_doc": "refund_policy.pdf"},]
4. Run: python eval_retrieval.py
5. Read the output — it prints recall@k for `embed` -only, `hybrid` , and `tfidf` -only, the before→after delta, and a per-question ✓/✗ list so you can see exactly which questions are still failing after the change.
You can also point it at a JSON file instead of editing the script:

```bash
python eval_retrieval.py my_questions.json
```
where `my_questions.json` is a list of `{"question": ..., "expected_doc": ...}`.

---

## 8. Session & document lifecycle (good to know when debugging)
- Every browser session gets a `session_id`  (stored in a Flask session cookie), and each session has its own isolated `VectorStore` , uploaded files, and dedupe-hash set — uploads in one browser tab don't leak into another user's session.
- Sessions idle for over an hour are evicted automatically (`SESSION_TTL` ), and only the 20 most recent sessions are kept in memory at once (`MAX_SESSIONS` ) — oldest gets evicted first when a new one needs a slot.
- Removing a single document (`/remove` ) deletes its chunks, its stored file, and forgets its content-hash — so you can re-upload the exact same file afterward without it being wrongly flagged "duplicate."
- `/clear`  wipes everything for the current session: chunks, vectors, files, hashes, and the chunk-size comparison stats.
---

## 9. Troubleshooting
| Symptom | Likely cause |
| ----- | ----- |
| "TF-IDF (offline fallback)" mode always, even after setting the key | `.env` not being picked up — confirm it's named exactly `.env` and sits next to `app.py`, or export the var in your shell instead |
| "Duplicate file skipped" for a file you removed and re-uploaded | Old bug — fixed; make sure you're running the current `app.py`  |
| Clicking "Open ↗" shows a blank page | Old bug in `view.html` (a stray syntax error broke the whole script) — fixed; make sure you're running the current `view.html`  |
| Every answer says "I don't know" | `EMBED_MIN_SCORE` too high for your document's content, or the embedding API key/model is misconfigured — check the terminal for errors |
| Answers cite the wrong page | Try Structured chunking instead of a fixed word count, or lower/raise `HYBRID_ALPHA` depending on whether your docs rely more on exact terms or on paraphrased meaning |


