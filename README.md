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
LLM_MODEL=openai/gpt-5-mini
EMBED_MODEL=openai/text-embedding-3-small
EMBED_MIN_SCORE=0.30
RETRIEVAL_MODE=hybrid
HYBRID_ALPHA=0.6
PORT=5000
```
- `**OPENROUTER_API_KEY**`  — get one at [openrouter.ai](https://openrouter.ai/) . Without it, the app still works but falls back to a fully offline TF-IDF-only mode (no embeddings, no LLM-generated answers — it stitches together the most relevant sentences instead). **Never commit a real key or paste one into chat/docs/screenshots** — treat any key that's left your local `.env`  as compromised and rotate it at openrouter.ai immediately.
- `**LLM_MODEL**`  — any OpenRouter chat model slug. Currently set to `openai/gpt-5-mini`  (400k context). Other confirmed working alternatives: `openai/gpt-4o-mini`  (cheaper, 128k context), `deepseek/deepseek-chat`  (app.py's built-in fallback default if `LLM_MODEL`  is unset entirely).
- `**EMBED_MODEL**`  — any OpenRouter embedding model slug. Confirmed working alternatives: `baai/bge-base-en-v1.5`  (768-dim, solid general default) and `baai/bge-m3`  (1024-dim, strong multilingual/long-document performance). **Switching this requires re-indexing** — vectors from different embedding models live in different, incompatible vector spaces, so `/clear`  and re-upload after changing it; don't expect old and new vectors to compare meaningfully in the same session.
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

## 9. Production hardening
Everything in this section was implemented and verified by actually running it (see `test_app.py`), not just reasoned about.

### Security
- **SSRF protection on** `**/load-url**` **.** Before this, pasting a URL like `http://169.254.169.254/latest/meta-data/`  (a cloud metadata endpoint) or `http://localhost:6379`  would make the _server_ fetch it, and the result would get indexed and could be echoed back in an answer. `_validate_url_is_public()`  resolves the hostname and rejects private/loopback/link-local/reserved addresses before fetching — and redirects are followed **manually, one hop at a time**, re-validating every hop, not just the URL you typed. A naive check on only the initial URL would miss a malicious site that returns `302 -> http://169.254.169.254/` .
- **No shared hardcoded** `**SECRET_KEY**` **.** Previously, if `SECRET_KEY`  wasn't set in the environment, every deployment fell back to the same hardcoded string in source control — meaning anyone could forge a session cookie for any deployment that forgot to set it. Now it generates a random per-process key instead, with a loud startup warning that sessions won't survive a restart and won't work correctly across multiple worker processes until you set `SECRET_KEY`  explicitly.
### Observability
- **Structured logging** (`logging`  module, configurable via `LOG_LEVEL` ) replaced every silent `except Exception: pass` . The most important one: the embeddings/LLM path in `/ask`  used to fail silently and fall back to TF-IDF with zero signal that anything was wrong — a bad API key, a rate limit, or an OpenRouter outage would look identical to normal offline operation. Now it logs a warning with the full traceback before falling back.
- `**GET /healthz**`  — a liveness endpoint that doesn't touch session state (so a load balancer or Docker healthcheck with no cookies gets a clean 200), reporting whether embeddings are configured and how many sessions are currently active.
### Performance
- **Cached TF-IDF index.** `VectorStore.get_tfidf_index()`  builds the index (tokenization + IDF over the whole corpus) once and reuses it until the store is mutated (`add` /`remove_doc` /`clear`  all invalidate it). Previously this was rebuilt from scratch on every single question, in both the TF-IDF fallback path and the TF-IDF half of hybrid search — wasted work that scaled with how many documents were indexed.
### Answer quality / safety
- `**TOP_K**`  **and** `**MAX_CONTEXT_TOKENS**` **.** `TOP_K`  (default 5) caps how many chunks retrieval returns; `MAX_CONTEXT_TOKENS`  (default 3000) caps how many tokens' worth of chunk _text_ actually get sent to the LLM. These are different guarantees — structured chunking has no hard upper bound on a single chunk's size (an unstructured document with no real sentence punctuation can produce one huge chunk), so 5 large chunks (or even one) could already exceed a reasonable context budget with `TOP_K`  alone doing nothing to stop it. `fit_to_token_budget()`  greedily keeps the highest-scored chunks until the budget would be exceeded, always keeping at least one even if it alone goes over.
### Testing
- `**test_app.py**`  — an actual pytest suite covering the upload/ask/ remove/clear lifecycle, the duplicate-file dedupe fix, multi-strategy chunk comparison, the token-budget guard, TF-IDF cache invalidation, and every SSRF case above (including the redirect-hop test). Run with: pip install pytestpytest test_app.py -v
### New/changed environment variables
| Variable | Default | Purpose |
| ----- | ----- | ----- |
| `SECRET_KEY`  | _(random per-process if unset)_ | <p>Session cookie signing — </p><p>**set this explicitly for any real deployment**</p> |
| `LOG_LEVEL`  | `INFO`  | Logging verbosity (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |
| `TOP_K`  | `5`  | How many chunks retrieval returns before token-budget trimming |
| `MAX_CONTEXT_TOKENS`  | `3000`  | Token budget for chunk text sent to the LLM |
### Known limitation still deferred (by design, not oversight)
The storage layer is still pickled files + in-memory dicts, not a real database or vector DB — this is a genuine multi-process/scaling limitation (each `gunicorn` worker has its own separate memory), not something this hardening pass fixes. See the Qdrant architecture plan discussed separately — that's the correct next step, deliberately not bundled into this pass since it's an infrastructure migration, not a hardening fix.

## 10. Troubleshooting
| Symptom | Likely cause |
| ----- | ----- |
| "TF-IDF (offline fallback)" mode always, even after setting the key | `.env` not being picked up — confirm it's named exactly `.env` and sits next to `app.py`, or export the var in your shell instead |
| "Duplicate file skipped" for a file you removed and re-uploaded | Old bug — fixed; make sure you're running the current `app.py`  |
| Clicking "Open ↗" shows a blank page | Old bug in `view.html` (a stray syntax error broke the whole script) — fixed; make sure you're running the current `view.html`  |
| Every answer says "I don't know" | `EMBED_MIN_SCORE` too high for your document's content, or the embedding API key/model is misconfigured — check the terminal for errors |
| Answers cite the wrong page | Try Structured chunking instead of a fixed word count, or lower/raise `HYBRID_ALPHA` depending on whether your docs rely more on exact terms or on paraphrased meaning |
| Sessions reset every restart | `SECRET_KEY` isn't set — check the startup log for the warning, then set it explicitly |
| A `/load-url` request gets rejected with "resolves to a non-public address" | Working as intended — that URL points at an internal/private address; this is the SSRF protection, not a bug |




