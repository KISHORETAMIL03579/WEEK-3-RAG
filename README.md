# Ask My Docs — Full Project Guide

A minimal Retrieval-Augmented Generation (RAG) app: upload documents, ask
questions, get answers grounded **only** in what you uploaded, with a link
back to the exact source. If the answer isn't in the documents, it says so
instead of guessing.

---

## 1. Project structure

```
project/
├── app.py                   # Flask backend — all the logic lives here
├── qdrant_store.py           # Qdrant vector-DB adapter (only used if VECTOR_BACKEND=qdrant)
├── requirements.txt
├── Dockerfile
├── docker-compose.yml         # self-hosted Qdrant + app, one command: docker compose up --build
├── .github/
│   └── workflows/
│       └── ci.yml             # lint + build + push to GHCR on every push to main
├── templates/
│   ├── index.html            # main chat UI (upload, chunking strategy, chat)
│   └── view.html             # "Open document" viewer (opened in a new tab)
├── uploads/                   # uploaded files land here (created automatically)
├── vectorstore/               # per-session pickled chunk+vector indexes (memory backend only)
├── .env.example               # copy to .env and fill in your own key — see §3
└── .env                       # your real config — never commit this
```

`index.html` and `view.html` **must** be inside a `templates/` folder — that's
where Flask's `render_template()` looks for them by default.

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

1. **Upload** — a PDF, `.txt`, `.md`, or a URL goes to `/upload` or `/load-url`.
2. **Extract** — text is pulled out per page (PDF via PyMuPDF) or per
   logical section (TXT/MD split on blank lines; web pages stripped of
   HTML tags).
3. **Chunk** — the extracted text is split into small pieces ("chunks")
   using one of four strategies (see §5). Chunk size matters: too big and
   irrelevant text rides along with the answer; too small and related
   context gets separated.
4. **Embed** — each chunk's text is sent to an embedding model (via
   OpenRouter) which returns a vector — a list of numbers representing
   the chunk's *meaning*, not just its words. This is what lets the app
   match "How do I get my money back?" to a chunk about "refunds" even
   though no words overlap.
5. **Store** — chunks + vectors are kept in memory in a `VectorStore` and
   also pickled to disk (`vectorstore/<session_id>.pkl`) so a page reload
   doesn't lose your index.
6. **Ask** — your question is embedded the same way, then compared against
   every stored chunk's vector using **cosine similarity** (how close two
   vectors point in the same direction — 1.0 = identical meaning, 0 =
   unrelated). This app also blends in a **TF-IDF** score (classic
   keyword-overlap scoring) so exact tokens like error codes or IDs aren't
   lost to fuzzy semantic matching. See §6 for why both.
7. **Validate** — if the best match's score doesn't clear a minimum
   threshold, the app returns "I don't know" instead of forcing an answer
   from irrelevant chunks.
8. **Generate** — the top-matching chunks are handed to an LLM with a
   strict instruction: *answer only from these excerpts, cite each fact
   like [1] or [2], and say "I don't know" if they're not enough.* The
   chunks' source (filename + page/section) are shown as clickable source
   cards under the answer.

---

## 3. How to run it

### Requirements

```bash
pip install -r requirements.txt
```

This installs Flask, PyMuPDF, Werkzeug, `waitress`, and `qdrant-client`
(only actually imported if you turn on `VECTOR_BACKEND=qdrant` — see §9;
harmless to have installed either way).

### Configuration

Copy the template and fill in your own values:

```bash
cp .env.example .env
```

At minimum, set `OPENROUTER_API_KEY` (get one at
[openrouter.ai](https://openrouter.ai)). Everything else has a working
default. **Never commit a real `.env` or paste its contents anywhere**
(chat, issues, screenshots) — treat any key that leaves that file as
compromised and rotate it immediately.

Every environment variable the app actually reads:

| Variable | Default | What it controls |
|---|---|---|
| `OPENROUTER_API_KEY` | *(empty)* | Without it, the app runs in fully offline TF-IDF-only mode — no embeddings, no LLM, no network calls |
| `LLM_MODEL` | `deepseek/deepseek-chat` | Any OpenRouter chat model slug. Confirmed alternatives: `openai/gpt-5-mini` (400k context), `openai/gpt-4o-mini` (cheaper, 128k) |
| `EMBED_MODEL` | `openai/text-embedding-3-small` | Any OpenRouter embedding model slug. Confirmed alternatives: `baai/bge-base-en-v1.5`, `baai/bge-m3`. **Switching requires re-indexing** — old and new vectors are incompatible; `/clear` and re-upload |
| `EMBED_MIN_SCORE` | `0.30` | Similarity threshold below which the embeddings path says "I don't know" rather than answer from a weak match |
| `TFIDF_MIN_SCORE` | `0.15` | Same idea, for the offline TF-IDF path — without this gate, a single incidentally-shared word could produce a confident-looking answer to a completely unrelated question |
| `RETRIEVAL_MODE` | `hybrid` | `hybrid` blends embeddings + TF-IDF; `embed` uses embeddings alone (for A/B comparison) |
| `HYBRID_ALPHA` | `0.6` | Weight on the embedding score in the hybrid blend (0–1). Higher favors meaning-based matching; lower favors exact keyword/code matching |
| `TOP_K` | `5` | How many chunks retrieval returns, before token-budget trimming |
| `MAX_CONTEXT_TOKENS` | `3000` | Hard cap on chunk-text tokens sent to the LLM, regardless of how many chunks `TOP_K` allows through |
| `VECTOR_BACKEND` | `memory` | `memory` (pickled files, zero setup) or `qdrant` (real vector DB — see §9) |
| `QDRANT_URL` | `http://localhost:6333` | Only used if `VECTOR_BACKEND=qdrant` — self-hosted or Cloud cluster URL |
| `QDRANT_API_KEY` | *(empty)* | Only used if `VECTOR_BACKEND=qdrant` — leave empty for self-hosted, required for Qdrant Cloud |
| `QDRANT_TIMEOUT` | `10` | Seconds before a Qdrant request times out — raise on a distant/cold cluster |
| `QDRANT_CANDIDATE_POOL` | `30` | How many ANN candidates Qdrant returns before hybrid search TF-IDF-reranks within that pool (see §9) |
| `SECRET_KEY` | *(random per-process)* | Signs session cookies. Set explicitly for any real deployment — otherwise sessions won't survive a restart or work across multiple worker processes |
| `LOG_LEVEL` | `INFO` | `DEBUG`, `INFO`, `WARNING`, or `ERROR` |
| `HOST` | `127.0.0.1` | Leave as-is for a normal local run. **Must** be `0.0.0.0` inside Docker (`docker-compose.yml` already sets this) — otherwise the container's port mapping silently doesn't work |
| `PORT` | `5000` | |
| `APP_DEBUG` | `false` | Flask's debug mode — leave false outside local development |

### Run — three ways

**A. Directly with Python** (simplest, uses the in-memory backend by default):
```bash
python app.py
```
You'll see:
```
🚀 Ask My Docs is running → http://localhost:5000
   Mode: embeddings + LLM   (or "TF-IDF (offline fallback)" if no API key)
```

**B. Self-hosted Docker, building locally** (uses Qdrant automatically — see §9):
```bash
docker compose up --build
```

**C. Pull the pre-built image from GHCR** instead of building it yourself
(published automatically by `.github/workflows/ci.yml` on every push to
`main`):
```bash
docker pull ghcr.io/YOUR-GITHUB-USERNAME/YOUR-REPO-NAME:latest
docker run -p 5000:5000 --env-file .env ghcr.io/YOUR-GITHUB-USERNAME/YOUR-REPO-NAME:latest
```
Use all-lowercase for the username/repo portion — GHCR requires it
regardless of how the repo is cased on GitHub. `HOST=0.0.0.0` must be set
in your `.env` for this option too, same reasoning as Docker Compose.

Open **http://localhost:5000** in a browser for any of the three.

### Using it

1. Drop a PDF/TXT/MD file (or paste a URL) in the sidebar.
2. Pick a chunking strategy (Structured is recommended — see §5).
3. Click **Upload & Index document**.
4. Ask a question in the chat box.
5. Read the answer, check the **Sources** cards underneath — click
   **Open ↗** to view the exact page/section the answer came from.
6. Click **✕** on a document to remove it, or **Clear all documents** to
   reset the whole session.

---

## 4. Where each piece of logic lives in `app.py`

| Concern | Function / class |
|---|---|
| PDF text extraction | `extract_pdf_pages()` |
| TXT/MD text extraction | `extract_txt_pages()` |
| Web page fetch + HTML stripping | `fetch_web_page()`, `_TextExtractor` |
| Fixed-size chunking (128/256/512 words) | `fixed_chunk()` |
| Structured chunking (headings/paragraphs/tables/code) | `structured_chunk()`, `parse_blocks()` |
| Sentence splitting (used by structured chunking + fallback answers) | `split_sentences()` |
| Calling the embeddings API | `embed_text()`, `embed_texts()` |
| In-memory + on-disk chunk/vector index | `VectorStore` class |
| TF-IDF scoring (offline fallback + hybrid blend) | `tokenize()`, `compute_tf()`, `compute_idf()`, `tfidf_vector()`, `cosine_sim()` |
| **Hybrid retrieval** (this week's improvement) | `hybrid_search()` |
| "Is this good enough to answer from?" | `validate_context()` |
| LLM-grounded answer with citations | `generate_answer()` |
| Offline template-based answer (no API key) | `synthesize_answer()` |
| Session/document lifecycle (upload, remove, clear, expiry) | `/upload`, `/remove`, `/clear`, `_get_store()` |

---

## 5. Chunking strategies — what they are and why size matters

| Strategy | What it does | Trade-off |
|---|---|---|
| **Structured** (recommended) | Parses headings, paragraphs, code blocks, and tables as distinct blocks; merges tiny fragments together and splits huge ones at sentence boundaries (40–300 words per chunk) | Keeps semantically related text together; best default for mixed-content docs |
| **128 words** | Fixed-size chunks with 20% overlap | Very granular — good for pinpointing exact facts/codes, but a lot of chunks, less surrounding context per chunk |
| **256 words** | Same, larger chunks | A balance between granularity and context |
| **512 words** | Same, largest chunks | More context per chunk, but multiple unrelated ideas can end up sharing one chunk, so a retrieved match may drag in irrelevant text alongside the right answer |

**Why it matters, concretely:** if a chunk is too big, it might contain two
unrelated FAQ answers glued together — retrieval finds the chunk correctly,
but the LLM has to sift the right sentence out of noise, and citations get
fuzzy. If a chunk is too small, one idea can get split across two chunks,
and retrieval might grab only half the context needed to answer fully. The
sidebar's **"Compare chunk sizes"** panel shows you the resulting chunk
count for each strategy on your actual uploaded document, so you can see
this trade-off directly instead of guessing.

---

## 6. Why hybrid retrieval (embeddings + TF-IDF)

- **Embeddings** are great at *meaning*: "How do I get my money back?"
  matches a chunk about "refunds" even with zero shared words.
- **TF-IDF** is great at *exact tokens*: an error code like `ERR-4032`, a
  product SKU, or a rare acronym can get semantically "blurred" by an
  embedding model into a fuzzy neighborhood of similar-sounding text,
  causing the exact chunk to rank lower than it should. TF-IDF scores
  exact/rare-word overlap directly, so it nails these cases.

`hybrid_search()` computes both scores per chunk and blends them:

```
combined_score = HYBRID_ALPHA * embedding_score + (1 - HYBRID_ALPHA) * tfidf_score
```

`HYBRID_ALPHA` (default `0.6`) controls the blend — higher favors meaning
matching, lower favors exact keyword matching.

---

## 7. Session & document lifecycle (good to know when debugging)

- Every browser session gets a `session_id` (stored in a Flask session
  cookie), and each session has its own isolated `VectorStore`, uploaded
  files, and dedupe-hash set — uploads in one browser tab don't leak into
  another user's session.
- Sessions idle for over an hour are evicted automatically
  (`SESSION_TTL`), and only the 20 most recent sessions are kept in memory
  at once (`MAX_SESSIONS`) — oldest gets evicted first when a new one
  needs a slot.
- Removing a single document (`/remove`) deletes its chunks, its stored
  file, and forgets its content-hash — so you can re-upload the exact same
  file afterward without it being wrongly flagged "duplicate."
- `/clear` wipes everything for the current session: chunks, vectors,
  files, hashes, and the chunk-size comparison stats.

---

## 8. Production hardening

Everything in this section was implemented and verified by actually
running it against a live instance of the app, not just reasoned about.

### Security

- **SSRF protection on `/load-url`.** Before this, pasting a URL like
  `http://169.254.169.254/latest/meta-data/` (a cloud metadata endpoint)
  or `http://localhost:6379` would make the *server* fetch it, and the
  result would get indexed and could be echoed back in an answer.
  `_validate_url_is_public()` resolves the hostname and rejects
  private/loopback/link-local/reserved addresses before fetching — and
  redirects are followed **manually, one hop at a time**, re-validating
  every hop, not just the URL you typed. A naive check on only the
  initial URL would miss a malicious site that returns
  `302 -> http://169.254.169.254/`.
- **No shared hardcoded `SECRET_KEY`.** Previously, if `SECRET_KEY` wasn't
  set in the environment, every deployment fell back to the same
  hardcoded string in source control — meaning anyone could forge a
  session cookie for any deployment that forgot to set it. Now it
  generates a random per-process key instead, with a loud startup
  warning that sessions won't survive a restart and won't work correctly
  across multiple worker processes until you set `SECRET_KEY` explicitly.

### Observability

- **Structured logging** (`logging` module, configurable via `LOG_LEVEL`)
  replaced every silent `except Exception: pass`. The most important one:
  the embeddings/LLM path in `/ask` used to fail silently and fall back
  to TF-IDF with zero signal that anything was wrong — a bad API key, a
  rate limit, or an OpenRouter outage would look identical to normal
  offline operation. Now it logs a warning with the full traceback before
  falling back.
- **`GET /healthz`** — a liveness endpoint that doesn't touch session
  state (so a load balancer or Docker healthcheck with no cookies gets a
  clean 200), reporting whether embeddings are configured and how many
  sessions are currently active.

### Performance

- **Cached TF-IDF index.** `VectorStore.get_tfidf_index()` builds the
  index (tokenization + IDF over the whole corpus) once and reuses it
  until the store is mutated (`add`/`remove_doc`/`clear` all invalidate
  it). Previously this was rebuilt from scratch on every single question,
  in both the TF-IDF fallback path and the TF-IDF half of hybrid search —
  wasted work that scaled with how many documents were indexed.

### Answer quality / safety

- **`TOP_K` and `MAX_CONTEXT_TOKENS`.** `TOP_K` (default 5) caps how many
  chunks retrieval returns; `MAX_CONTEXT_TOKENS` (default 3000) caps how
  many tokens' worth of chunk *text* actually get sent to the LLM. These
  are different guarantees — structured chunking has no hard upper bound
  on a single chunk's size (an unstructured document with no real
  sentence punctuation can produce one huge chunk), so 5 large chunks (or
  even one) could already exceed a reasonable context budget with
  `TOP_K` alone doing nothing to stop it. `fit_to_token_budget()` greedily
  keeps the highest-scored chunks until the budget would be exceeded,
  always keeping at least one even if it alone goes over.

### New/changed environment variables

| Variable | Default | Purpose |
|---|---|---|
| `SECRET_KEY` | *(random per-process if unset)* | Session cookie signing — **set this explicitly for any real deployment** |
| `LOG_LEVEL` | `INFO` | Logging verbosity (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |
| `TOP_K` | `5` | How many chunks retrieval returns before token-budget trimming |
| `MAX_CONTEXT_TOKENS` | `3000` | Token budget for chunk text sent to the LLM |
| `VECTOR_BACKEND` | `memory` | `memory` (pickled files, zero setup) or `qdrant` (real vector DB — see §9b) |

### Status update: Qdrant is now implemented (previously listed as deferred)

An earlier version of this README listed the pickled-files/in-memory
storage layer as a known multi-process scaling limitation, with a Qdrant
migration "deliberately not bundled" as future work. That work is done —
see §9b below. `VECTOR_BACKEND=memory` (the default) is unchanged and
still the right choice for local dev / a single-process course project;
switch to `qdrant` once you need multi-worker deployment or a real ANN
index.

## 9. Vector DB backend — Qdrant (optional, `VECTOR_BACKEND=qdrant`)

### Why

The default `memory` backend is a brute-force Python list scored with
plain cosine similarity, pickled to disk. Fine at hundreds of chunks and
a single process. It does **not** survive running multiple `gunicorn`
workers (each has its own separate copy in memory), and doesn't scale
past a few thousand chunks before brute-force scoring gets slow. Qdrant
fixes both: a real ANN index (HNSW) shared across processes.

### Same code, two deployment options

Both point at the exact same `QdrantVectorStore` adapter
(`qdrant_store.py`) — only two env vars differ:

| | Self-hosted (Docker) | Qdrant Cloud |
|---|---|---|
| `QDRANT_URL` | `http://qdrant:6333` (or `http://localhost:6333` outside Docker) | `https://xxxx.aws.cloud.qdrant.io:6333` from your cluster dashboard |
| `QDRANT_API_KEY` | unset (no auth by default) | your cluster's API key |
| Setup | `docker compose up --build` | Sign up at cloud.qdrant.io, create a free-tier cluster |

### Running self-hosted

```bash
docker compose up --build
```
One command builds the app image and starts both the app and Qdrant.
`docker-compose.yml` already sets `VECTOR_BACKEND=qdrant` and
`QDRANT_URL=http://qdrant:6333` for you — just set your real
`OPENROUTER_API_KEY` in a `.env` file first (docker-compose reads it from
there automatically).

### Running against Qdrant Cloud instead

Skip `docker-compose.yml`'s `qdrant` service entirely and just run the
app normally with:
```
VECTOR_BACKEND=qdrant
QDRANT_URL=https://xxxx.aws.cloud.qdrant.io:6333
QDRANT_API_KEY=your_cluster_api_key
```

### What's actually different under the hood

- **Retrieval** goes through Qdrant's real ANN search instead of scoring
  every stored vector in a Python loop.
- **Hybrid search stays correct, but adapts**: a real vector DB doesn't
  hand back a score for every vector (that defeats the point of an ANN
  index) — so `query_scores()` asks Qdrant for its top ~30 candidates and
  TF-IDF-blends only within that pool, instead of scoring the whole
  corpus. See `qdrant_store.py`'s module docstring for the full reasoning.
- **Chunk-strategy filtering (`filtered_by_method`) is pushed down into
  Qdrant** as a real payload filter, rather than filtered in Python —
  the one place this backend is a genuine capability upgrade, not just a
  persistence swap.
- **TF-IDF fallback still works identically** — `get_tfidf_index()` is
  mirrored on the Qdrant adapter with the same caching behavior, since
  TF-IDF is a lexical operation a vector DB was never meant to do.
- Session eviction and `/clear` release the Qdrant collection, not just a
  pickle file, so switching backends doesn't leak collections over time.

### Verifying it works

There's no automated test suite shipped for this adapter. Before trusting
it, run the app once against a real Qdrant instance (self-hosted or
Cloud): upload a document, ask a question that should be answered from
it, and confirm a source card comes back. That's the real proof — no
amount of code review substitutes for actually hitting a live Qdrant
instance at least once.

## 10. Troubleshooting

| Symptom | Likely cause |
|---|---|
| "TF-IDF (offline fallback)" mode always, even after setting the key | `.env` not being picked up — confirm it's named exactly `.env` and sits next to `app.py`, or export the var in your shell instead |
| "Duplicate file skipped" for a file you removed and re-uploaded | Old bug — fixed; make sure you're running the current `app.py` |
| Clicking "Open ↗" shows a blank page | Old bug in `view.html` (a stray syntax error broke the whole script) — fixed; make sure you're running the current `view.html` |
| Every answer says "I don't know" | `EMBED_MIN_SCORE`/`TFIDF_MIN_SCORE` too high for your document's content, or the embedding API key/model is misconfigured — check the terminal for errors |
| (Fixed) TF-IDF-only mode confidently answered a totally unrelated question | The offline path had no real "should we answer at all" gate — a single incidentally-shared word (e.g. "policy") could clear the very permissive `CONFIDENCE_THRESHOLD` used for candidate filtering. Fixed by adding `TFIDF_MIN_SCORE` (default 0.15) and gating it through `validate_context()`, same as the embeddings path already did with `EMBED_MIN_SCORE` |
| Answers cite the wrong page | Try Structured chunking instead of a fixed word count, or lower/raise `HYBRID_ALPHA` depending on whether your docs rely more on exact terms or on paraphrased meaning |
| Sessions reset every restart | `SECRET_KEY` isn't set — check the startup log for the warning, then set it explicitly |
| A `/load-url` request gets rejected with "resolves to a non-public address" | Working as intended — that URL points at an internal/private address; this is the SSRF protection, not a bug |
| `docker compose up` starts with no errors, but `localhost:5000` refuses to connect / hangs | `HOST` isn't set to `0.0.0.0` inside the container — `docker-compose.yml` already sets this, but if you're running the Dockerfile directly (`docker run` without compose), pass `-e HOST=0.0.0.0` yourself. Binding to `127.0.0.1` (the default, correct for a bare-metal run) is invisible from outside a container, so the port mapping silently does nothing |



docker pull ghcr.io/your-username/your-repo:abc1234...


docker run -p 5000:5000 --env-file .env ghcr.io/your-username/your-repo:latest