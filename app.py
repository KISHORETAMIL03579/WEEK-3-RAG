import os
import re
import sys
import math
import json
import time
import uuid
import pickle
import hashlib
import logging
import secrets
import ipaddress
import socket
import urllib.request
import urllib.parse
import urllib.error
import html.parser
from pathlib import Path
from collections import Counter

import pymupdf as fitz  # PyMuPDF — imports the real module directly, avoiding
                        # the deprecated `import fitz` legacy-alias shim that
                        # prints the runtime warning. Every fitz.* call below
                        # is unaffected since this is just a local alias.
from flask import Flask, request, jsonify, render_template, session, send_file
from werkzeug.utils import secure_filename

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger("ask_my_docs")


def _load_env():
    env_path = Path(__file__).parent / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_env()

# ─────────────────────────────────────────────────────────────────────────────
#  App Setup
# ─────────────────────────────────────────────────────────────────────────────

app = Flask(__name__)
_env_secret = os.environ.get("SECRET_KEY")
if _env_secret:
    app.secret_key = _env_secret
else:
    # No hardcoded fallback — a shared, source-controlled secret key means
    # every deployment that forgets to set SECRET_KEY signs session
    # cookies with the same key, letting anyone forge another user's
    # session. A random per-process key at least means cookies from one
    # run can't be forged by someone who read this file; the real fix in
    # any actual production deployment is still to set SECRET_KEY
    # explicitly so sessions survive a restart.
    app.secret_key = secrets.token_hex(32)
    logger.warning(
        "SECRET_KEY not set — using a random per-process key. Sessions will "
        "NOT survive a server restart, and running multiple instances "
        "(e.g. gunicorn --workers N) will break sessions since each "
        "process gets a different key. Set SECRET_KEY explicitly for any "
        "real deployment."
    )
app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024  # 50 MB per request

BASE_DIR = Path(__file__).parent
UPLOAD_FOLDER = BASE_DIR / "uploads"
VECTOR_FOLDER = BASE_DIR / "vectorstore"
UPLOAD_FOLDER.mkdir(exist_ok=True)
VECTOR_FOLDER.mkdir(exist_ok=True)
ALLOWED_EXTENSIONS = {"pdf", "txt", "md"}

# Per-session stores
VECTOR_STORE: dict[str, "VectorStore"] = {}
SESSION_ACCESS: dict[str, float] = {}
HASH_STORE: dict[str, set[tuple[str, str]]] = {}
# Tracks which (content-hash, chunk_mode) key belongs to which doc_id, per
# session, so that removing a single document can also forget that key (see
# remove_doc()). Keying on (hash, chunk_mode) instead of hash alone means the
# exact same file can be indexed under several chunking strategies at once —
# needed to actually compare retrieval quality across chunk sizes, instead of
# only ever seeing a hypothetical chunk-count preview for strategies you
# never actually indexed. Uploading the same file + same chunk_mode twice is
# still rejected as a duplicate.
HASH_BY_DOC: dict[str, dict[str, tuple[str, str]]] = {}
SESSION_FILES: dict[str, dict[str, dict]] = {}
CHUNK_COUNTS: dict[str, dict[str, int]] = {}

# Maps a client-generated upload_id -> the time it was cancelled. /upload
# checks this (see below) so a mid-flight cancel can (a) stop processing
# any remaining files in a multi-file batch, and (b) roll back whatever
# was already added to the store during THIS call before the response
# goes out — since a single embedding call can take real wall-clock time,
# this is the honest, achievable version of "cancel": not always an
# instant interrupt, but a guaranteed "nothing stays indexed" outcome.
CANCELLED_UPLOADS: dict[str, float] = {}
CANCELLED_UPLOAD_TTL = 10 * 60  # forget stale cancel signals after 10 minutes


def _sweep_cancelled_uploads() -> None:
    now = time.time()
    for uid in [u for u, t in CANCELLED_UPLOADS.items() if now - t > CANCELLED_UPLOAD_TTL]:
        CANCELLED_UPLOADS.pop(uid, None)

SESSION_TTL = 60 * 60  # 1 hour
MAX_SESSIONS = 20

# ─────────────────────────────────────────────────────────────────────────────
#  OpenRouter config (embeddings + LLM)
# ─────────────────────────────────────────────────────────────────────────────

OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
OPENROUTER_URL = "https://openrouter.ai/api/v1"
LLM_MODEL = os.environ.get("LLM_MODEL", "deepseek/deepseek-chat")
EMBED_MODEL = os.environ.get("EMBED_MODEL", "openai/text-embedding-3-small")
EMBED_MIN_SCORE = float(os.environ.get("EMBED_MIN_SCORE", "0.30"))
EMBED_BATCH = 32

# Retrieval strategy for the embeddings path. "hybrid" combines cosine
# similarity with TF-IDF so exact tokens (error codes, IDs, acronyms) aren't
# lost to semantic blurring. "embed" is the old behavior, kept only so you
# can flip back to it and measure the before/after with the same code.
RETRIEVAL_MODE = os.environ.get("RETRIEVAL_MODE", "hybrid")  # "hybrid" | "embed"
HYBRID_ALPHA = float(os.environ.get("HYBRID_ALPHA", "0.6"))  # weight on embedding score

# How many chunks retrieval returns, before token-budget trimming below.
TOP_K = int(os.environ.get("TOP_K", "5"))

# Hard cap on how many tokens' worth of retrieved chunk TEXT get sent to
# the LLM as context, regardless of how many chunks TOP_K allows through.
#
# Why this is needed even though TOP_K already exists: TOP_K caps the
# COUNT of chunks, not their combined SIZE. Structured chunking has no
# hard upper bound on a single chunk (see structured_chunk() /
# split_by_sentences() — an unstructured document with no real sentence
# punctuation can produce one abnormally large chunk). Even 5 large
# chunks — or just one — can already blow past a reasonable context
# budget, drive up latency/cost, and in the worst case exceed the model's
# actual context window. This trims the already-retrieved, already-ranked
# list down to what actually fits, on top of (not instead of) TOP_K.
MAX_CONTEXT_TOKENS = int(os.environ.get("MAX_CONTEXT_TOKENS", "3000"))

# Which VectorStore implementation backs retrieval. "memory" (default) is
# the original brute-force in-process store — zero setup, pickled to disk.
# "qdrant" swaps in a real vector database with an actual ANN index (HNSW)
# behind it. The SAME code path handles both self-hosted Qdrant (via
# docker-compose.yml, QDRANT_API_KEY left unset) and Qdrant Cloud (a
# cluster URL + API key from cloud.qdrant.io) — only QDRANT_URL and
# QDRANT_API_KEY differ between the two; see qdrant_store.py.
VECTOR_BACKEND = os.environ.get("VECTOR_BACKEND", "memory")
QDRANT_URL = os.environ.get("QDRANT_URL", "http://localhost:6333")
QDRANT_API_KEY = os.environ.get("QDRANT_API_KEY") or None  # None for self-hosted, unauthenticated
QDRANT_TIMEOUT = float(os.environ.get("QDRANT_TIMEOUT", "10"))
# ANN candidates pulled from Qdrant before TF-IDF re-ranks for hybrid
# search — see qdrant_store.py's module docstring for why this differs
# from the in-memory backend's "score every chunk" approach.
QDRANT_CANDIDATE_POOL = int(os.environ.get("QDRANT_CANDIDATE_POOL", "30"))


def estimate_tokens(text: str) -> int:
    """
    Rough token-count estimate. There's no real tokenizer available
    offline for arbitrary models, so this uses the standard ~4-characters-
    per-token rule of thumb for English text (the same approximation most
    LLM providers themselves suggest when a real tokenizer isn't handy).
    Not exact — good enough for a budget guard, not for billing.
    """
    return max(1, len(text) // 4)


def fit_to_token_budget(results: list[dict], max_tokens: int) -> list[dict]:
    """
    Greedily keep results — assumed already sorted best-first by score —
    until the cumulative estimated token count would exceed max_tokens.

    Always keeps at least the single best-scoring result, even if it
    alone exceeds the budget: an answer grounded in one long chunk is
    still better than refusing to answer at all. Everything after that
    is dropped once the running total would tip over the limit, so a
    handful of oversized chunks can't silently balloon the prompt sent to
    the LLM regardless of how large TOP_K is set to.
    """
    kept: list[dict] = []
    used = 0
    for r in results:
        t = estimate_tokens(r.get("text", ""))
        if kept and used + t > max_tokens:
            break
        kept.append(r)
        used += t
    return kept

_simple_tokenizer = re.compile(r"[\w]+")


def _openrouter_call(path: str, payload: dict) -> dict:
    req = urllib.request.Request(
        f"{OPENROUTER_URL}/{path}",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=90) as resp:
        return json.loads(resp.read().decode("utf-8"))


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Batch-embed texts via OpenRouter. Returns list of vectors."""
    out: list[list[float]] = []
    for i in range(0, len(texts), EMBED_BATCH):
        batch = texts[i:i + EMBED_BATCH]
        data = _openrouter_call("embeddings", {"model": EMBED_MODEL, "input": batch})
        vectors = [d["embedding"] for d in sorted(data["data"], key=lambda x: x["index"])]
        out.extend(vectors)
    return out


def embed_text(text: str) -> list[float]:
    return embed_texts([text])[0]


# ─────────────────────────────────────────────────────────────────────────────
#  VectorStore (in-memory + disk-persisted)
# ─────────────────────────────────────────────────────────────────────────────

def _dot(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b))


def _norm(a: list[float]) -> float:
    return math.sqrt(sum(x * x for x in a))


def cosine(a: list[float], b: list[float]) -> float:
    denom = _norm(a) * _norm(b)
    return 0.0 if denom == 0 else _dot(a, b) / denom


class VectorStore:
    """A tiny persistent vector index: chunk metadata + embedding vectors."""

    def __init__(self, sid: str):
        self.sid = sid
        self.chunks: list[dict] = []
        self.vectors: list[list[float]] = []
        self.path = VECTOR_FOLDER / f"{sid}.pkl"
        # Cached TF-IDF index (token frequencies + IDF weights) for this
        # store's current chunk set. None means "needs rebuilding" — see
        # get_tfidf_index(). Invalidated by every mutation below so it's
        # never stale, but never rebuilt more often than necessary either.
        self._tfidf_index_cache: dict | None = None
        self.last_backend_error: str | None = None  # always None for this backend; see QdrantVectorStore

    def load(self) -> None:
        if self.path.exists():
            try:
                data = pickle.loads(self.path.read_bytes())
                self.chunks = data["chunks"]
                self.vectors = data["vectors"]
                self._tfidf_index_cache = None
            except Exception:
                logger.warning("Corrupted vector store at %s — starting fresh", self.path, exc_info=True)
                self.chunks, self.vectors = [], []

    def save(self) -> None:
        self.path.write_bytes(pickle.dumps({"chunks": self.chunks, "vectors": self.vectors}))

    def add(self, chunks: list[dict], vectors: list[list[float]]) -> None:
        self.chunks.extend(chunks)
        self.vectors.extend(vectors)
        self._tfidf_index_cache = None
        self.save()

    def get_tfidf_index(self) -> dict:
        """
        Return this store's TF-IDF index, building it once and caching it
        until the next mutation (add/remove_doc/clear/load all invalidate
        the cache).

        Why: without this, build_index() re-tokenizes and recomputes IDF
        over the ENTIRE chunk corpus on every single question that uses
        the TF-IDF path — repeated, wasted work that scales with corpus
        size and gets worse the more documents are indexed. The index
        only actually changes when chunks change, so it's safe to reuse
        between questions.
        """
        if self._tfidf_index_cache is None:
            self._tfidf_index_cache = build_index(self.chunks)
        return self._tfidf_index_cache

    def query(self, vector: list[float], top_k: int = 5,
              min_score: float = 0.0) -> list[dict]:
        scored = [(i, cosine(vector, v)) for i, v in enumerate(self.vectors)]
        scored = [(i, s) for i, s in scored if s >= min_score]
        scored.sort(key=lambda x: -x[1])
        return [{**self.chunks[i], "score": s} for i, s in scored[:top_k]]

    def query_scores(self, vector: list[float]) -> list[float]:
        """Cosine similarity of `vector` against every chunk, unfiltered and
        in chunk order. Used by hybrid_search() to line embedding scores up
        against TF-IDF scores index-for-index before combining them."""
        return [cosine(vector, v) for v in self.vectors]

    def clear(self) -> None:
        self.chunks, self.vectors = [], []
        self._tfidf_index_cache = None
        self.path.unlink(missing_ok=True)

    def remove_doc(self, doc_id: str) -> int:
        """Remove all chunks + vectors for a doc. Returns how many were removed."""
        before = len(self.chunks)
        kept = [(c, v) for c, v in zip(self.chunks, self.vectors)
                if c["doc_id"] != doc_id]
        self.chunks = [c for c, _ in kept]
        self.vectors = [v for _, v in kept]
        removed = before - len(self.chunks)
        if removed:
            self._tfidf_index_cache = None
            self.save()
        return removed

    def filtered_by_method(self, method: str) -> "VectorStore":
        """
        Return an ephemeral, non-persisted view containing only chunks
        indexed under the given chunking strategy ("structured", "128",
        "256", "512").

        This is what makes chunk-size comparison real rather than
        hypothetical: once the same document has been uploaded under two
        or more strategies (see the (hash, chunk_mode) dedupe key in
        /upload), /ask can restrict retrieval to just one strategy at a
        time, so you can directly see whether a given question is found
        under 128-word chunks but missed under 512-word chunks, etc.

        Never call .save()/.add() on the returned view — it shares no
        state with the real store and isn't written to disk.
        """
        view = VectorStore(f"{self.sid}__view")
        # In TF-IDF-only mode (no embeddings configured) self.vectors is []
        # while self.chunks isn't — zip(chunks, vectors) would silently
        # truncate to the shorter list and drop every chunk. Filter by
        # index instead so this works whether or not vectors are present.
        has_vectors = len(self.vectors) == len(self.chunks)
        matched = [i for i, c in enumerate(self.chunks) if c.get("method") == method]
        view.chunks = [self.chunks[i] for i in matched]
        view.vectors = [self.vectors[i] for i in matched] if has_vectors else []
        return view


def _manifest_path(sid: str) -> Path:
    return UPLOAD_FOLDER / f"{sid}.manifest.json"


def _save_session_manifest(sid: str) -> None:
    """Persist the doc_id → file mapping so it survives a server restart."""
    files = SESSION_FILES.get(sid)
    if files:
        _manifest_path(sid).write_text(json.dumps({
            doc_id: {"path": str(info["path"]), "name": info["name"]}
            for doc_id, info in files.items()
        }), encoding="utf-8")
    else:
        _manifest_path(sid).unlink(missing_ok=True)


def _load_session_manifest(sid: str) -> None:
    """Restore the file mapping for a session from disk."""
    if sid in SESSION_FILES:
        return
    manifest = _manifest_path(sid)
    if not manifest.exists():
        return
    try:
        data = json.loads(manifest.read_text(encoding="utf-8"))
    except Exception:
        logger.warning("Corrupted session manifest at %s — ignoring", manifest, exc_info=True)
        return
    files: dict[str, dict] = {}
    for doc_id, meta in data.items():
        p = Path(meta.get("path", ""))
        if p.exists():
            files[doc_id] = {"path": p, "name": meta.get("name", p.name)}
    if files:
        SESSION_FILES[sid] = files


def _cleanup_session_files(sid: str) -> None:
    """Delete any uploaded files retained for a session."""
    files = SESSION_FILES.pop(sid, None)
    if files:
        for info in files.values():
            info["path"].unlink(missing_ok=True)
    _manifest_path(sid).unlink(missing_ok=True)


def _sweep_orphan_uploads() -> None:
    """Remove upload files not referenced by any session manifest."""
    referenced: set[str] = set()
    for manifest in UPLOAD_FOLDER.glob("*.manifest.json"):
        try:
            data = json.loads(manifest.read_text(encoding="utf-8"))
        except Exception:
            logger.warning("Corrupted manifest during startup sweep: %s — skipping", manifest, exc_info=True)
            continue
        for meta in data.values():
            referenced.add(str(Path(meta.get("path", "")).resolve()))
    for f in UPLOAD_FOLDER.iterdir():
        if f.name.endswith(".manifest.json"):
            continue
        if str(f.resolve()) not in referenced:
            f.unlink(missing_ok=True)


_sweep_orphan_uploads()


def _make_store(sid: str):
    """Construct + load the right VectorStore implementation for `sid`,
    based on VECTOR_BACKEND. Both implementations expose the same
    interface, so nothing downstream needs to know or care which one it
    got. The qdrant_store import is lazy — only needed, and only
    attempted, when VECTOR_BACKEND=qdrant is actually set."""
    if VECTOR_BACKEND == "qdrant":
        from qdrant_store import QdrantVectorStore
        store = QdrantVectorStore(sid)
    else:
        store = VectorStore(sid)
    store.load()
    return store


def _evict_session_store(sid: str) -> None:
    """Release backend-specific storage for an evicted/cleared session.
    Safe to call even if that session never used the currently-active
    backend — the pickle file simply won't exist, or the Qdrant call
    will find no matching collection."""
    (VECTOR_FOLDER / f"{sid}.pkl").unlink(missing_ok=True)
    if VECTOR_BACKEND == "qdrant":
        try:
            from qdrant_store import QdrantVectorStore
            QdrantVectorStore(sid).clear()
        except Exception:
            logger.warning("Failed to release Qdrant collection for evicted session %s", sid, exc_info=True)


def _get_store(sid: str) -> VectorStore:
    """Return this session's vector store, evicting stale/overflowing sessions."""
    now = time.time()
    for s in list(SESSION_ACCESS):
        if now - SESSION_ACCESS[s] > SESSION_TTL:
            VECTOR_STORE.pop(s, None)
            SESSION_ACCESS.pop(s, None)
            HASH_STORE.pop(s, None)
            HASH_BY_DOC.pop(s, None)
            _evict_session_store(s)
            _cleanup_session_files(s)
    if len(SESSION_ACCESS) >= MAX_SESSIONS and sid not in SESSION_ACCESS:
        oldest = min(SESSION_ACCESS, key=SESSION_ACCESS.get)
        VECTOR_STORE.pop(oldest, None)
        SESSION_ACCESS.pop(oldest, None)
        HASH_STORE.pop(oldest, None)
        HASH_BY_DOC.pop(oldest, None)
        _evict_session_store(oldest)
        _cleanup_session_files(oldest)
    SESSION_ACCESS[sid] = now
    _load_session_manifest(sid)

    store = VECTOR_STORE.get(sid)
    if store is None:
        store = _make_store(sid)
        VECTOR_STORE[sid] = store
    return store


def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


# ─────────────────────────────────────────────────────────────────────────────
#  Text Extraction
# ─────────────────────────────────────────────────────────────────────────────

def extract_pdf_pages(filepath: str) -> list[dict]:
    """Extract text from each page of a PDF. Returns list of {page, text}."""
    pages = []
    try:
        doc = fitz.open(filepath)
    except Exception:
        logger.info("Could not open PDF %s (corrupt, encrypted, or not a real PDF)", filepath, exc_info=True)
        return []
    for page_num, page in enumerate(doc, start=1):
        text = page.get_text("text").strip()
        if text:
            pages.append({"page": page_num, "text": text})
    doc.close()
    return pages


def extract_txt_pages(filepath: str) -> list[dict]:
    """Treat a .txt or .md file as logical sections separated by blank lines."""
    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
        text = f.read().strip()
    sections = [s.strip() for s in re.split(r"\n{3,}", text) if s.strip()]
    if not sections:
        sections = [text]
    return [{"page": i + 1, "text": s} for i, s in enumerate(sections)]


# ─────────────────────────────────────────────────────────────────────────────
#  Web Page Loading
# ─────────────────────────────────────────────────────────────────────────────

_IGNORE_TAGS = {"script", "style", "noscript", "svg", "canvas", "nav", "header", "footer"}


class _TextExtractor(html.parser.HTMLParser):
    def __init__(self):
        super().__init__()
        self.skip_depth = 0
        self.in_title = False
        self.title = None
        self.parts: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag in _IGNORE_TAGS:
            self.skip_depth += 1
        if tag == "title":
            self.in_title = True
        if tag in ("p", "div", "li", "h1", "h2", "h3", "h4", "tr", "br", "blockquote"):
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in _IGNORE_TAGS:
            self.skip_depth = max(0, self.skip_depth - 1)
        if tag == "title":
            self.in_title = False
        if tag in ("p", "div", "li", "h1", "h2", "h3", "h4", "blockquote"):
            self.parts.append("\n")

    def handle_data(self, data):
        if self.skip_depth:
            return
        if self.in_title:
            self.title = data.strip()
            return
        self.parts.append(data)

    def get_text(self) -> str:
        text = "".join(self.parts)
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r"\n\s*\n+", "\n\n", text)
        return text.strip()


def _is_public_ip(ip_str: str) -> bool:
    try:
        ip = ipaddress.ip_address(ip_str)
    except ValueError:
        return False
    return not (
        ip.is_private or ip.is_loopback or ip.is_link_local
        or ip.is_multicast or ip.is_reserved or ip.is_unspecified
    )


def _validate_url_is_public(url: str) -> None:
    """
    Raise ValueError if `url` resolves to a private/loopback/link-local/
    reserved address.

    Why: without this, /load-url is a classic SSRF (server-side request
    forgery) vector — someone points it at http://169.254.169.254/ (a
    cloud metadata endpoint), http://localhost:6379 (an internal Redis),
    or any other service only the SERVER can reach, and the fetched
    content gets indexed and can be echoed back in answers. Scheme
    validation alone (http/https only) does nothing to stop this, since
    the hostname itself is the problem, not the protocol.
    """
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError("Only http:// and https:// URLs are allowed")
    hostname = parsed.hostname
    if not hostname:
        raise ValueError("URL has no hostname")
    try:
        infos = socket.getaddrinfo(hostname, None)
    except socket.gaierror as exc:
        raise ValueError(f"Could not resolve hostname '{hostname}': {exc}") from exc
    for family, _, _, _, sockaddr in infos:
        ip_str = sockaddr[0]
        if not _is_public_ip(ip_str):
            raise ValueError(
                f"URL '{hostname}' resolves to a non-public address ({ip_str}) — refusing to fetch"
            )


class _NoAutoRedirect(urllib.request.HTTPRedirectHandler):
    """Disables urllib's automatic redirect-following. Returning None here
    makes urlopen raise HTTPError with the redirect's status code instead
    of silently following it — see fetch_web_page() for why that matters."""
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def fetch_web_page(url: str, max_redirects: int = 5) -> tuple[str, str]:
    """
    Fetch a URL and return (title, cleaned text).

    Redirects are followed manually, one hop at a time, re-running
    _validate_url_is_public() on every hop — not just the URL the user
    typed. Trusting urllib's built-in automatic redirect handling would
    mean the SSRF check only ever covers the first URL; a malicious or
    compromised site could return `301 -> http://169.254.169.254/` and
    the server would have already made that internal request before any
    validation saw it.
    """
    opener = urllib.request.build_opener(_NoAutoRedirect)
    current = url
    raw = None

    for _ in range(max_redirects + 1):
        _validate_url_is_public(current)
        req = urllib.request.Request(
            current,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 AskMyDocs/1.0"},
        )
        try:
            with opener.open(req, timeout=30) as resp:
                raw = resp.read().decode("utf-8", errors="ignore")
            break
        except urllib.error.HTTPError as e:
            if e.code in (301, 302, 303, 307, 308):
                location = e.headers.get("Location")
                if not location:
                    raise ValueError(f"Redirect ({e.code}) with no Location header") from e
                current = urllib.parse.urljoin(current, location)
                continue
            raise
    else:
        raise ValueError(f"Too many redirects (>{max_redirects})")

    if raw is None:
        raise ValueError("Too many redirects")

    parser = _TextExtractor()
    parser.feed(raw)
    title = parser.title or urllib.parse.urlparse(current).netloc
    text = parser.get_text()
    return title, text


# ─────────────────────────────────────────────────────────────────────────────
#  Fixed-Size Chunking
# ─────────────────────────────────────────────────────────────────────────────

def fixed_chunk(doc_info: dict, pages: list[dict], chunk_size: int,
                overlap_ratio: float = 0.2) -> list[dict]:
    """Split document text into overlapping fixed-size word chunks."""
    overlap = max(1, int(chunk_size * overlap_ratio))
    step = max(1, chunk_size - overlap)
    chunks = []
    chunk_index = 0

    for page_data in pages:
        words = page_data["text"].split()
        i = 0
        while i < len(words):
            end = min(i + chunk_size, len(words))
            text = " ".join(words[i:end])
            if text.strip():
                chunks.append({
                    "id": f"{doc_info['doc_id']}::p{page_data['page']}::c{chunk_index}",
                    "doc_id": doc_info["doc_id"],
                    "filename": doc_info["filename"],
                    "page": page_data["page"],
                    "section": None,
                    "block_type": "paragraph",
                    "text": text,
                    "chunk_index": chunk_index,
                    "method": f"{chunk_size}",
                })
                chunk_index += 1
            i += step

    return chunks


# ─────────────────────────────────────────────────────────────────────────────
#  Structured Chunking
# ─────────────────────────────────────────────────────────────────────────────

STRUCT_MIN_WORDS = 40
STRUCT_MAX_WORDS = 300


_NUMBERED_HEADING_RE = re.compile(r"^\d+(\.\d+)*\.?\s+[A-Z][A-Za-z].*$")
_ALLCAPS_HEADING_RE = re.compile(r"^[A-Z][A-Z0-9 ,&'/\-]{2,70}$")


def _looks_like_plain_heading(stripped: str) -> bool:
    """
    Detects section headings in real-world documents that were never
    written in Markdown — numbered ("2.1 Duties, Rights and Obligations
    of GESCI") or ALL-CAPS ("INTRODUCTION", "OFFENCES") titles, the
    overwhelmingly common style in Word/PDF-extracted policy manuals,
    contracts, and handbooks.

    Constrained to short, title-like lines specifically so it does NOT
    misfire on numbered body sentences like "6.6. These records will be
    updated as required by law..." — a real heading is a few words with
    no trailing sentence punctuation; a numbered clause is a full
    sentence and will fail the word-count/punctuation checks below.
    """
    if not stripped or len(stripped) > 90:
        return False
    words = stripped.split()
    if not (1 <= len(words) <= 12):
        return False
    if _NUMBERED_HEADING_RE.match(stripped) and not stripped.endswith((".", ";", ",")):
        return True
    if _ALLCAPS_HEADING_RE.match(stripped) and any(c.isalpha() for c in stripped):
        return True
    return False


def parse_blocks(text: str, base_section: str = "Overview") -> list[dict]:
    """
    Parse plain text (or Markdown) into semantic blocks.
    Detects: headings (## style), code fences (```), table rows (|…|),
    and paragraph boundaries (blank lines).
    """
    lines = text.split("\n")
    blocks = []
    current_section = base_section
    buffer: list[str] = []
    block_type = "paragraph"
    in_code = False

    def flush():
        joined = " ".join(buffer).replace("  ", " ").strip()
        if not joined:
            buffer.clear()
            return
        words = len(joined.split())
        if block_type in ("code", "table") or words > 4:
            blocks.append({
                "type": block_type,
                "section": current_section,
                "text": joined,
            })
        buffer.clear()

    for line in lines:
        stripped = line.strip()

        # Code fence toggle
        if stripped.startswith("```"):
            if not in_code:
                flush()
                in_code = True
                block_type = "code"
            else:
                flush()
                in_code = False
                block_type = "paragraph"
            continue

        if in_code:
            if stripped:
                buffer.append(stripped)
            continue

        # Heading detection — Markdown style, or plain numbered/ALL-CAPS
        # (see _looks_like_plain_heading for why the latter is needed)
        heading_match = re.match(r"^#{1,4}\s+(.*)", stripped)
        if heading_match:
            flush()
            current_section = heading_match.group(1).strip()
            current_section = re.sub(r"\*\*(.+?)\*\*", r"\1", current_section)
            current_section = re.sub(r"`(.+?)`", r"\1", current_section)
            block_type = "paragraph"
            continue

        if _looks_like_plain_heading(stripped):
            flush()
            current_section = stripped
            block_type = "paragraph"
            continue

        # Table row
        if stripped.startswith("|") and stripped.endswith("|"):
            if block_type != "table":
                flush()
                block_type = "table"
            if not re.match(r"^[\|\s\-:]+$", stripped):
                cell_text = re.sub(r"\|", " ", stripped).strip()
                buffer.append(cell_text)
            continue

        # Blank line = paragraph boundary
        if not stripped:
            flush()
            block_type = "paragraph"
            continue

        # Normal line — strip Markdown noise
        cleaned = stripped
        cleaned = re.sub(r"^[-*>]\s+", "", cleaned)
        cleaned = re.sub(r"\*\*(.+?)\*\*", r"\1", cleaned)
        cleaned = re.sub(r"`(.+?)`", r"\1", cleaned)
        cleaned = re.sub(r"\[(.+?)\]\(.+?\)", r"\1", cleaned)
        if cleaned:
            buffer.append(cleaned)

    flush()
    return blocks


SENTENCE_ABBREV = {
    "e.g", "i.e", "etc", "vs", "dr", "mr", "mrs", "ms", "prof", "st",
    "inc", "ltd", "co", "no", "vol", "fig", "al", "et", "approx",
}

_ABBREV_RE = re.compile(
    r"\b(" + "|".join(re.escape(a) for a in SENTENCE_ABBREV) + r")\.", re.IGNORECASE)


def split_sentences(text: str) -> list[str]:
    """
    Split text into sentences without breaking on common abbreviations
    (e.g. "e.g.", "Dr.") or decimal numbers ("1.5").
    """
    # Protect abbreviations and decimals so their periods aren't sentence endings
    protected = _ABBREV_RE.sub(lambda m: m.group(0).replace(".", "\x00"), text)
    protected = re.sub(r"\b(\d+)\.(\d+)\b",
                       lambda m: m.group(1) + "\x00" + m.group(2), protected)

    # Sentence ends: punctuation followed by whitespace + capital/CJK, or end-of-string
    parts = re.split(r"(?<=[.!?])\s+(?=[A-Z\u4e00-\u9fff])|(?<=[.!?])$", protected)

    sentences = []
    for part in parts:
        part = part.strip().replace("\x00", ".")
        if part:
            sentences.append(part)
    return sentences


def split_by_sentences(block: dict, max_words: int) -> list[dict]:
    result = []
    buf: list[str] = []
    count = 0

    for sent in split_sentences(block["text"]):
        w = len(sent.split())
        if count + w > max_words and buf:
            result.append({**block, "text": " ".join(buf)})
            buf = [sent]
            count = w
        else:
            buf.append(sent)
            count += w

    if buf:
        result.append({**block, "text": " ".join(buf)})
    return result


def _make_chunk(doc_info: dict, block: dict, index: int) -> dict:
    pages = block.get("pages") or [block.get("page", 1)]
    return {
        "id": f"{doc_info['doc_id']}::c{index}",
        "doc_id": doc_info["doc_id"],
        "filename": doc_info["filename"],
        "page": pages[0],
        "page_end": pages[-1] if len(pages) > 1 else None,
        "section": block.get("section"),
        "block_type": block.get("type", "paragraph"),
        "text": block["text"],
        "chunk_index": index,
        "method": "structured",
    }


def structured_chunk(doc_info: dict, pages: list[dict]) -> list[dict]:
    """
    Structured chunking pipeline:
      1. Parse each page into semantic blocks
      2. Merge tiny blocks (< STRUCT_MIN_WORDS)
      3. Split huge blocks (> STRUCT_MAX_WORDS) at sentence boundaries
      4. Attach metadata: section title, block type, page, filename
    """
    chunks = []
    chunk_index = 0
    merge_buffer: dict | None = None

    def flush_merge():
        nonlocal merge_buffer, chunk_index
        if merge_buffer is not None:
            chunks.append(_make_chunk(doc_info, merge_buffer, chunk_index))
            chunk_index += 1
            merge_buffer = None

    for page_data in pages:
        page_num = page_data["page"]
        blocks = parse_blocks(page_data["text"])

        for block in blocks:
            words = len(block["text"].split())

            if words < STRUCT_MIN_WORDS:
                if merge_buffer is None:
                    merge_buffer = {**block, "page": page_num, "pages": [page_num]}
                else:
                    if merge_buffer["pages"][-1] != page_num:
                        merge_buffer["pages"].append(page_num)
                    merge_buffer["text"] += " " + block["text"]
                    if len(merge_buffer["text"].split()) >= STRUCT_MIN_WORDS:
                        flush_merge()
                continue

            flush_merge()

            if words > STRUCT_MAX_WORDS:
                for sub in split_by_sentences(block, STRUCT_MAX_WORDS):
                    sub["page"] = page_num
                    sub["pages"] = [page_num]
                    chunks.append(_make_chunk(doc_info, sub, chunk_index))
                    chunk_index += 1
            else:
                block["page"] = page_num
                block["pages"] = [page_num]
                chunks.append(_make_chunk(doc_info, block, chunk_index))
                chunk_index += 1

    flush_merge()

    return chunks


def chunk_text(doc_info: dict, pages: list[dict], chunk_mode: str) -> list[dict]:
    if chunk_mode == "structured":
        return structured_chunk(doc_info, pages)
    size = int(chunk_mode) if chunk_mode.isdigit() else 256
    return fixed_chunk(doc_info, pages, size)


# ─────────────────────────────────────────────────────────────────────────────
#  Pure-Python TF-IDF Retrieval (offline fallback)
# ─────────────────────────────────────────────────────────────────────────────

STOPWORDS = {
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "shall", "can", "to", "of", "in", "for",
    "on", "with", "at", "by", "from", "up", "about", "into", "through",
    "and", "but", "or", "if", "while", "when", "where", "who", "which",
    "that", "this", "these", "those", "it", "its", "all", "each", "both",
    "more", "most", "other", "some", "no", "not", "only", "same", "than",
    "too", "very", "just", "your", "you", "they", "we", "he", "she", "i",
    "my", "their", "our", "his", "her", "also", "how", "what", "so", "as",
}

CONFIDENCE_THRESHOLD = 0.05
# CONFIDENCE_THRESHOLD above only filters which chunks are even considered
# candidates — it's deliberately low so search_chunks() doesn't miss
# anything. It is NOT a "should we actually answer" gate: a single
# incidentally-shared word (e.g. both the query and an unrelated document
# containing the word "policy") can clear 0.05 easily, producing a
# confident-looking answer with source citations for a question that has
# nothing to do with the document. TFIDF_MIN_SCORE below is the real gate
# — checked via validate_context() in /ask, the same way EMBED_MIN_SCORE
# already gates the embeddings path.
TFIDF_MIN_SCORE = float(os.environ.get("TFIDF_MIN_SCORE", "0.15"))


def tokenize(text: str) -> list[str]:
    """Lowercase, extract word tokens (incl. Unicode/CJK), remove stopwords."""
    tokens = _simple_tokenizer.findall(text.lower())
    return [t for t in tokens if len(t) > 2 and t not in STOPWORDS]


def compute_tf(tokens: list[str]) -> dict[str, float]:
    if not tokens:
        return {}
    counts = Counter(tokens)
    total = len(tokens)
    return {t: c / total for t, c in counts.items()}


def compute_idf(corpus_tokens: list[list[str]]) -> dict[str, float]:
    n = len(corpus_tokens)
    doc_freq: dict[str, int] = {}
    for tokens in corpus_tokens:
        for t in set(tokens):
            doc_freq[t] = doc_freq.get(t, 0) + 1
    return {t: math.log((1 + n) / (1 + df)) + 1.0 for t, df in doc_freq.items()}


def tfidf_vector(tf: dict[str, float], idf: dict[str, float]) -> dict[str, float]:
    return {t: tf_val * idf.get(t, 1.0) for t, tf_val in tf.items()}


def cosine_sim(vec_a: dict[str, float], vec_b: dict[str, float]) -> float:
    common = set(vec_a) & set(vec_b)
    if not common:
        return 0.0
    dot = sum(vec_a[t] * vec_b[t] for t in common)
    norm_a = math.sqrt(sum(v * v for v in vec_a.values()))
    norm_b = math.sqrt(sum(v * v for v in vec_b.values()))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def build_index(chunks: list[dict]) -> dict:
    corpus_tokens = [tokenize(c["text"]) for c in chunks]
    return {"corpus_tokens": corpus_tokens, "idf": compute_idf(corpus_tokens)}


def search_chunks(query: str, chunks: list[dict], index: dict,
                  top_k: int = 4) -> list[dict]:
    """TF-IDF cosine similarity search — offline fallback."""
    if not chunks:
        return []

    query_tokens = tokenize(query)
    if not query_tokens:
        return []

    idf = index["idf"]
    q_vec = tfidf_vector(compute_tf(query_tokens), idf)

    scored = []
    for chunk, tokens in zip(chunks, index["corpus_tokens"]):
        c_vec = tfidf_vector(compute_tf(tokens), idf)
        score = cosine_sim(q_vec, c_vec)
        if score >= CONFIDENCE_THRESHOLD:
            scored.append({**chunk, "score": score})

    scored.sort(key=lambda x: -x["score"])
    return scored[:top_k]


def hybrid_search(store: "VectorStore", query: str, top_k: int = 5,
                  alpha: float = HYBRID_ALPHA) -> list[dict]:
    """
    Rank chunks by a weighted blend of embedding similarity and TF-IDF
    similarity, instead of embeddings alone.

    Why: pure embedding search is good at "what does the policy say about
    refunds" (meaning) but can bury an exact token like "ERR-4032" under
    semantically-similar-but-wrong chunks, because embeddings compress exact
    strings into fuzzy meaning space. TF-IDF does the opposite: great at
    exact/rare tokens, poor at paraphrase. Blending catches both. This is
    THE single change for this week — it only touches ranking inside the
    embeddings path; the TF-IDF-only fallback path is untouched.
    """
    if not store.chunks:
        return []

    embed_scores = (store.query_scores(embed_text(query))
                    if store.vectors and len(store.vectors) == len(store.chunks)
                    else [0.0] * len(store.chunks))

    index = store.get_tfidf_index()
    q_vec = tfidf_vector(compute_tf(tokenize(query)), index["idf"])
    tfidf_scores = [
        cosine_sim(q_vec, tfidf_vector(compute_tf(tokens), index["idf"]))
        for tokens in index["corpus_tokens"]
    ]

    combined = [alpha * e + (1 - alpha) * t for e, t in zip(embed_scores, tfidf_scores)]
    ranked = sorted(range(len(combined)), key=lambda i: -combined[i])[:top_k]

    return [
        {**store.chunks[i], "score": combined[i],
         "embed_score": embed_scores[i], "tfidf_score": tfidf_scores[i]}
        for i in ranked
    ]


def synthesize_answer(query: str, results: list[dict]) -> dict:
    """Template-based answer for the offline fallback path."""
    if not results:
        return {
            "found": False,
            "answer": (
                "I don't know — I couldn't find a relevant answer in the uploaded "
                "documents. Try uploading more documents or rephrasing your question."
            ),
            "sources": [],
        }

    seen: set[str] = set()
    sources = []
    all_text = " ".join(r["text"] for r in results)

    for r in results:
        key = f"{r['doc_id']}::p{r['page']}"
        if key not in seen:
            seen.add(key)
            sources.append(r)

    query_words = set(tokenize(query))
    sentences = split_sentences(all_text)

    scored_sents = []
    for s in sentences:
        s = s.strip()
        if len(s) < 20:
            continue
        s_words = set(tokenize(s))
        overlap = len(query_words & s_words)
        scored_sents.append((overlap, s))

    scored_sents.sort(key=lambda x: -x[0])

    seen_sents: set[str] = set()
    top_sents = []
    for _, s in scored_sents:
        if s not in seen_sents:
            seen_sents.add(s)
            top_sents.append(s)
        if len(top_sents) >= 5:
            break

    answer = " ".join(top_sents) if top_sents else results[0]["text"][:500] + "…"

    return {"found": True, "answer": answer, "sources": sources}


# ─────────────────────────────────────────────────────────────────────────────
#  Validation + LLM-grounded generation
# ─────────────────────────────────────────────────────────────────────────────

_DONT_KNOW_MARKERS = (
    "i don't know", "i do not know", "cannot answer", "can't answer",
    "not enough information", "doesn't contain", "does not contain",
    "not available in the", "no information",
)


def validate_context(results: list[dict], min_score: float) -> bool:
    """Reject retrieval when nothing clears the similarity bar."""
    if not results:
        return False
    return results[0]["score"] >= min_score


def _is_dont_know(answer: str) -> bool:
    """
    Detects a genuine refusal, not just the incidental presence of a
    refusal-like phrase somewhere in a real answer.

    Why this can't be a plain substring search: the system prompt asks
    the model to reply with EXACTLY "I don't know." when it can't
    answer — but a real, substantive, correctly-cited answer to a broad
    question (e.g. one spanning two sections of a document) can easily
    include a hedging clause like "the manual does not contain a single
    consolidated list, but section 2.2 states..." A naive `marker in
    answer` check flags that whole answer as "not found" and the
    frontend discards it entirely, even though the model did answer.

    So: check for an exact (or near-exact, allowing trivial punctuation)
    match to the instructed refusal first. As a fallback, catch short
    responses that are still basically just a refusal in slightly
    different words — but require the response to actually BE short, so
    a hedge embedded in a longer, real answer is never caught by this.
    """
    a = answer.lower().strip()
    if a.rstrip(".") in ("i don't know", "i do not know"):
        return True
    word_count = len(a.split())
    return word_count <= 12 and any(m in a for m in _DONT_KNOW_MARKERS)


def generate_answer(query: str, results: list[dict]) -> str:
    """Ask the LLM to produce a grounded answer with [N] source citations."""
    context_blocks = []
    for i, r in enumerate(results, start=1):
        loc = f"{r['filename']} (page {r['page']})"
        if r.get("section"):
            loc += f", section: {r['section']}"
        context_blocks.append(f"[{i}] {loc}\n{r['text']}")

    system = (
        "You are a grounded question-answering assistant. Answer using ONLY the "
        "document excerpts provided. Cite every fact with its source number like "
        "[1] or [2]. If the excerpts do not contain enough information to answer "
        "the question, reply exactly with: \"I don't know.\" Do not use outside "
        "knowledge. Be concise and direct."
    )
    user = (
        "DOCUMENTS:\n\n" + "\n\n".join(context_blocks) +
        f"\n\nQUESTION: {query}\n\nANSWER:"
    )

    data = _openrouter_call("chat/completions", {
        "model": LLM_MODEL,
        "temperature": 0,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    })
    try:
        return data["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError, TypeError):
        return ""


# ─────────────────────────────────────────────────────────────────────────────
#  Flask Routes
# ─────────────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    if "session_id" not in session:
        session["session_id"] = str(uuid.uuid4())
    return render_template("index.html")


def _index_into_store(sid: str, doc_info: dict, pages: list[dict],
                      chunk_mode: str, chunks_out: list[dict],
                      embedding_ok: bool) -> None:
    """Chunk pages and add them to the session's vector store."""
    store = _get_store(sid)
    new_chunks = chunk_text(doc_info, pages, chunk_mode)
    chunks_out.append(new_chunks)

    if embedding_ok:
        vectors = embed_texts([c["text"] for c in new_chunks])
    else:
        vectors = []
    store.add(new_chunks, vectors)


@app.route("/upload-cancel", methods=["POST"])
def upload_cancel():
    """
    Signals that an in-flight /upload call (identified by the same
    upload_id the client sent with its FormData) should be cancelled.
    This just records the signal — /upload itself is what actually acts
    on it, checking between files and rolling back anything already
    added before it returns. If /upload has already finished and
    returned by the time this arrives, the signal is simply ignored
    (nothing left to cancel) and cleaned up by the TTL sweep.
    """
    _sweep_cancelled_uploads()
    data = request.get_json(silent=True) or {}
    upload_id = (data.get("upload_id") or "").strip()
    if upload_id:
        CANCELLED_UPLOADS[upload_id] = time.time()
    return jsonify({"ok": True})


@app.route("/upload", methods=["POST"])
def upload():
    if "session_id" not in session:
        session["session_id"] = str(uuid.uuid4())

    sid = session["session_id"]
    chunk_mode = request.form.get("chunk_mode", "structured")
    upload_id = (request.form.get("upload_id") or "").strip()
    _sweep_cancelled_uploads()

    files = request.files.getlist("files")
    if not files:
        return jsonify({"error": "No files provided"}), 400

    hashes = HASH_STORE.setdefault(sid, set())
    embedding_ok = bool(OPENROUTER_API_KEY)
    results = []
    pending: list[dict] = []

    for f in files:
        if not f or not allowed_file(f.filename):
            results.append({"filename": getattr(f, "filename", "?") or "?",
                            "error": "Unsupported file type (allowed: PDF, TXT, MD)"})
            continue

        original_name = f.filename
        ext = (original_name.rsplit(".", 1)[1] if "." in original_name else "").lower()

        safe_name = secure_filename(original_name) or "document"
        if not safe_name.lower().endswith("." + ext):
            safe_name = f"{safe_name}.{ext}"
        filepath = UPLOAD_FOLDER / f"{uuid.uuid4()}_{safe_name}"

        try:
            f.save(filepath)
            with open(filepath, "rb") as fh:
                content_hash = hashlib.sha256(fh.read()).hexdigest()
            dedupe_key = (content_hash, chunk_mode)

            if dedupe_key in hashes:
                filepath.unlink(missing_ok=True)
                results.append({"filename": original_name,
                                "error": f"Already indexed under the '{chunk_mode}' strategy — "
                                         f"pick a different chunking strategy to compare, or remove "
                                         f"the existing one first."})
                continue
            hashes.add(dedupe_key)

            doc_id = str(uuid.uuid4())[:8]
            doc_info = {"doc_id": doc_id, "filename": original_name}

            pages = (extract_pdf_pages(str(filepath)) if ext == "pdf"
                     else extract_txt_pages(str(filepath)))

            if not pages:
                filepath.unlink(missing_ok=True)
                hashes.discard(dedupe_key)
                reason = ("No extractable text (password-protected or scanned PDF?)"
                          if ext == "pdf" else "Empty file")
                results.append({"filename": original_name, "error": reason})
                continue

            new_chunks = chunk_text(doc_info, pages, chunk_mode)
            if not new_chunks:
                filepath.unlink(missing_ok=True)
                hashes.discard(dedupe_key)
                results.append({"filename": original_name, "error": "No chunks produced"})
                continue

            CHUNK_COUNTS.setdefault(sid, {})
            for mode in ("structured", "128", "256", "512"):
                CHUNK_COUNTS[sid][mode] = len(chunk_text(doc_info, pages, mode))

            pending.append({
                "filepath": filepath,
                "doc_id": doc_id,
                "filename": original_name,
                "ext": ext,
                "chunks": new_chunks,
                "hash": dedupe_key,
                "result": {
                    "filename": original_name,
                    "pages": len(pages),
                    "chunks": len(new_chunks),
                    "method": chunk_mode,
                },
            })
        except Exception as exc:
            filepath.unlink(missing_ok=True)
            if "dedupe_key" in locals():
                hashes.discard(dedupe_key)
            results.append({"filename": original_name, "error": f"Failed to index: {exc}"})

    if not pending:
        return jsonify({"ok": False, "error": "No valid documents were indexed.",
                        "documents": results}), 400

    store = _get_store(sid)
    committed_doc_ids: list[str] = []  # tracks what THIS call actually added, for rollback below
    was_cancelled = False

    for item in pending:
        if upload_id and upload_id in CANCELLED_UPLOADS:
            # Stop processing any remaining files in this batch — no
            # point embedding/indexing more once cancellation was
            # requested. Whatever's already committed gets rolled back
            # below, after the loop.
            was_cancelled = True
            item["filepath"].unlink(missing_ok=True)
            hashes.discard(item["hash"])
            continue
        try:
            if embedding_ok:
                vectors = embed_texts([c["text"] for c in item["chunks"]])
            else:
                vectors = []
            store.add(item["chunks"], vectors)

            stored_path = UPLOAD_FOLDER / f"{sid}__{item['doc_id']}.{item['ext']}"
            item["filepath"].replace(stored_path)
            SESSION_FILES.setdefault(sid, {})[item["doc_id"]] = {
                "path": stored_path,
                "name": item["filename"],
            }
            _save_session_manifest(sid)

            # Remember which hash belongs to this doc_id so /remove can
            # release it later (see remove_doc()) — otherwise re-uploading
            # the same file after removing it is wrongly flagged duplicate.
            HASH_BY_DOC.setdefault(sid, {})[item["doc_id"]] = item["hash"]

            item["result"]["doc_id"] = item["doc_id"]
            item["result"]["openable"] = True
            results.append(item["result"])
            committed_doc_ids.append(item["doc_id"])
        except Exception as exc:
            item["filepath"].unlink(missing_ok=True)
            hashes.discard(item["hash"])
            results.append({"filename": item["filename"],
                            "error": f"Failed to index: {exc}"})

    # Final check: even if cancellation only arrived after every file had
    # already finished committing, honor it anyway — roll back everything
    # this call just added rather than leave it silently indexed. This is
    # the guaranteed part of "cancel": maybe not always an instant stop,
    # but always a clean "nothing stays indexed" outcome.
    if upload_id and upload_id in CANCELLED_UPLOADS:
        was_cancelled = True
    if was_cancelled:
        for doc_id in committed_doc_ids:
            store.remove_doc(doc_id)
            info = SESSION_FILES.get(sid, {}).pop(doc_id, None)
            if info:
                info["path"].unlink(missing_ok=True)
            doc_hash = HASH_BY_DOC.get(sid, {}).pop(doc_id, None)
            if doc_hash is not None:
                hashes.discard(doc_hash)
        _save_session_manifest(sid)
        CANCELLED_UPLOADS.pop(upload_id, None)
        return jsonify({"ok": False, "cancelled": True,
                        "error": "Upload cancelled — nothing was indexed.",
                        "documents": []})

    return jsonify({"ok": True, "documents": results, "total_chunks": len(store.chunks),
                    "chunk_comparison": CHUNK_COUNTS.get(sid, {})})


@app.route("/load-url", methods=["POST"])
def load_url():
    if "session_id" not in session:
        session["session_id"] = str(uuid.uuid4())

    sid = session["session_id"]
    data = request.get_json(silent=True) or {}
    url = (data.get("url") or "").strip()
    chunk_mode = data.get("chunk_mode", "structured")

    if not url:
        return jsonify({"error": "Empty URL"}), 400

    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        return jsonify({"error": "URL must start with http:// or https://"}), 400

    embedding_ok = bool(OPENROUTER_API_KEY)

    try:
        title, text = fetch_web_page(url)
    except Exception as exc:
        return jsonify({"error": f"Failed to fetch URL: {exc}"}), 400

    if len(text.split()) < 20:
        return jsonify({"error": "Page returned too little text to index."}), 400

    doc_id = str(uuid.uuid4())[:8]
    doc_info = {"doc_id": doc_id, "filename": title[:80] or parsed.netloc}
    pages = [{"page": 1, "text": text}]

    new_chunks = chunk_text(doc_info, pages, chunk_mode)
    if not new_chunks:
        return jsonify({"error": "No chunks produced from this page."}), 400

    store = _get_store(sid)
    if embedding_ok:
        try:
            vectors = embed_texts([c["text"] for c in new_chunks])
            store.add(new_chunks, vectors)
        except Exception as exc:
            return jsonify({"error": f"Embedding failed: {exc}"}), 500
    else:
        store.add(new_chunks, [])

    CHUNK_COUNTS.setdefault(sid, {})
    for mode in ("structured", "128", "256", "512"):
        CHUNK_COUNTS[sid][mode] = len(chunk_text(doc_info, pages, mode))

    return jsonify({"ok": True, "documents": [{
        "filename": doc_info["filename"],
        "doc_id": doc_id,
        "openable": False,
        "pages": 1,
        "chunks": len(new_chunks),
        "method": chunk_mode,
    }], "total_chunks": len(store.chunks),
        "chunk_comparison": CHUNK_COUNTS.get(sid, {})})


@app.route("/file/<doc_id>", methods=["GET"])
def serve_file(doc_id: str):
    """View an uploaded document (e.g. PDF) in an HTML viewer page."""
    sid = session.get("session_id")
    if not sid:
        return jsonify({"error": "No active session"}), 400
    info = SESSION_FILES.get(sid, {}).get(doc_id)
    if not info or not info["path"].exists():
        return jsonify({"error": "File not found or no longer available"}), 404
    name = info["name"]
    ext = (name.rsplit(".", 1)[1] if "." in name else "").lower()
    return render_template("view.html", doc_id=doc_id, filename=name, ext=ext)


@app.route("/file/<doc_id>/raw", methods=["GET"])
def serve_file_raw(doc_id: str):
    """Stream the raw PDF bytes (used by the viewer page's embedded viewer)."""
    sid = session.get("session_id")
    if not sid:
        return jsonify({"error": "No active session"}), 400
    info = SESSION_FILES.get(sid, {}).get(doc_id)
    if not info or not info["path"].exists():
        return jsonify({"error": "File not found or no longer available"}), 404
    return send_file(info["path"], download_name=info["name"], as_attachment=False)


@app.route("/file/<doc_id>/pages", methods=["GET"])
def serve_file_pages(doc_id: str):
    """Return the extracted pages (for the text viewer) of an uploaded document."""
    sid = session.get("session_id")
    if not sid:
        return jsonify({"error": "No active session"}), 400
    info = SESSION_FILES.get(sid, {}).get(doc_id)
    if not info or not info["path"].exists():
        return jsonify({"error": "File not found or no longer available"}), 404

    name = info["name"]
    ext = (name.rsplit(".", 1)[1] if "." in name else "").lower()
    try:
        pages = (extract_pdf_pages(str(info["path"])) if ext == "pdf"
                 else extract_txt_pages(str(info["path"])))
    except Exception as exc:
        return jsonify({"error": f"Could not read document: {exc}"}), 500

    return jsonify({
        "filename": name,
        "ext": ext,
        "total_pages": len(pages),
        "pages": [{"num": i + 1, "text": p.get("text", "")} for i, p in enumerate(pages)],
    })


@app.route("/ask", methods=["POST"])
def ask():
    if "session_id" not in session:
        return jsonify({"error": "No documents uploaded yet"}), 400

    sid = session["session_id"]
    data = request.get_json()
    query = (data or {}).get("query", "").strip()
    # Optional: restrict retrieval to one chunking strategy, so you can
    # directly compare "does hybrid search find the answer under 128-word
    # chunks?" vs. 512-word, etc. Requires the same document to have been
    # uploaded under that strategy already (see /upload's dedupe key).
    method_filter = (data or {}).get("chunk_mode", "").strip() or None

    if not query:
        return jsonify({"error": "Empty query"}), 400

    def annotate_openable(results):
        files = SESSION_FILES.get(sid, {})
        for r in results:
            r["openable"] = r["doc_id"] in files
        return results

    store = _get_store(sid)
    if not store.chunks:
        return jsonify({
            "found": False,
            "answer": "No documents have been uploaded yet. Please upload a PDF, text file, or web page first.",
            "sources": [],
        })

    active_store = store
    if method_filter:
        active_store = store.filtered_by_method(method_filter)
        if not active_store.chunks:
            return jsonify({
                "found": False,
                "answer": (f"No documents are indexed under the '{method_filter}' chunking "
                          f"strategy yet. Upload one under that strategy first, or ask "
                          f"without a strategy filter to search everything indexed."),
                "sources": [],
            })

    # Path 1: embeddings + LLM (if configured and vectors exist)
    if OPENROUTER_API_KEY and active_store.vectors and len(active_store.vectors) == len(active_store.chunks):
        try:
            if RETRIEVAL_MODE == "hybrid":
                raw_results = hybrid_search(active_store, query, top_k=TOP_K)
            else:
                q_vec = embed_text(query)
                # min_score=0.0 here deliberately — capture the true top
                # candidate before any threshold filtering, so a below-
                # threshold rejection below can still report what it was
                # closest to, instead of an empty list with no diagnostic
                # information at all (see closest_match below).
                raw_results = active_store.query(q_vec, top_k=TOP_K, min_score=0.0)
            near_miss = raw_results[0] if raw_results else None
            results = [r for r in raw_results if r["score"] >= EMBED_MIN_SCORE]
            # TOP_K caps how many CHUNKS come back, not how many TOKENS
            # they add up to — trim to the context budget before this
            # goes anywhere near the LLM. Applied here (not just inside
            # generate_answer) so the "sources" shown to the user are
            # exactly what actually grounded the answer, never more.
            results = fit_to_token_budget(results, MAX_CONTEXT_TOKENS)
            if not validate_context(results, EMBED_MIN_SCORE):
                return jsonify({
                    "found": False,
                    "answer": "I don't know — no document content matched your question closely enough.",
                    "sources": [],
                    "closest_match": ({
                        "filename": near_miss["filename"],
                        "section": near_miss.get("section"),
                        "page": near_miss.get("page"),
                        "score": round(near_miss["score"], 4),
                        "threshold": EMBED_MIN_SCORE,
                    } if near_miss else None),
                })
            answer = generate_answer(query, results)
            return jsonify({
                "found": not _is_dont_know(answer),
                "answer": answer or "I don't know.",
                "sources": annotate_openable(results),
            })
        except Exception:
            logger.warning(
                "Embeddings/LLM path failed for a query — falling back to TF-IDF-only. "
                "This usually means a bad API key, rate limit, or network issue with OpenRouter.",
                exc_info=True,
            )
            # fall through to TF-IDF

    # Path 2: offline TF-IDF fallback
    chunks = active_store.chunks
    index = active_store.get_tfidf_index()
    results = search_chunks(query, chunks, index, top_k=TOP_K)
    results = fit_to_token_budget(results, MAX_CONTEXT_TOKENS)
    if not validate_context(results, TFIDF_MIN_SCORE):
        near_miss = results[0] if results else None
        return jsonify({
            "found": False,
            "answer": "I don't know — no document content matched your question closely enough.",
            "sources": [],
            "closest_match": ({
                "filename": near_miss["filename"],
                "section": near_miss.get("section"),
                "page": near_miss.get("page"),
                "score": round(near_miss["score"], 4),
                "threshold": TFIDF_MIN_SCORE,
            } if near_miss else None),
        })
    resp = synthesize_answer(query, results)
    resp["sources"] = annotate_openable(resp.get("sources", []))
    return jsonify(resp)


@app.route("/clear", methods=["POST"])
def clear():
    sid = session.get("session_id")
    backend_error = None
    if sid:
        # _get_store() reconnects to the real backend (Qdrant collection
        # or pickle file) if it isn't already cached in this process's
        # memory — using VECTOR_STORE.pop() directly here would silently
        # no-op after any restart/worker respawn, since it'd find nothing
        # to pop and never actually call .clear() on the real backend.
        store = _get_store(sid)
        store.clear()
        backend_error = getattr(store, "last_backend_error", None)
        VECTOR_STORE.pop(sid, None)
        SESSION_ACCESS.pop(sid, None)
        HASH_STORE.pop(sid, None)
        HASH_BY_DOC.pop(sid, None)
        CHUNK_COUNTS.pop(sid, None)
        _cleanup_session_files(sid)
    resp = {"ok": True}
    if backend_error:
        resp["warning"] = (f"Cleared locally, but the vector database delete "
                          f"failed: {backend_error}. The data may still exist "
                          f"in the backend.")
    return jsonify(resp)


@app.route("/remove", methods=["POST"])
def remove_doc():
    """Remove a single document: its chunks, its retained file, its manifest
    entry, and its content hash (so the same file can be re-uploaded later
    without being wrongly flagged as a duplicate)."""
    sid = session.get("session_id")
    if not sid:
        return jsonify({"error": "No active session"}), 400
    data = request.get_json(silent=True) or {}
    doc_id = (data.get("doc_id") or "").strip()
    if not doc_id:
        return jsonify({"error": "Missing doc_id"}), 400

    removed_chunks = 0
    store = _get_store(sid)
    if any(c["doc_id"] == doc_id for c in store.chunks):
        removed_chunks = store.remove_doc(doc_id)

    files = SESSION_FILES.get(sid, {})
    info = files.pop(doc_id, None)
    if info:
        info["path"].unlink(missing_ok=True)
    _save_session_manifest(sid)

    # Forget this doc's content hash so a future re-upload of the same
    # file isn't rejected as a stale duplicate.
    doc_hash = HASH_BY_DOC.get(sid, {}).pop(doc_id, None)
    if doc_hash is not None:
        HASH_STORE.get(sid, set()).discard(doc_hash)

    resp = {"ok": True, "removed_chunks": removed_chunks}
    backend_error = getattr(store, "last_backend_error", None)
    if backend_error:
        # Removed from the local view either way, but the real backend
        # (Qdrant) delete failed — surface this so it's not just a
        # server-log warning nobody sees. The document may reappear if
        # the session reloads from the backend later.
        resp["warning"] = (f"Removed locally, but the vector database delete "
                          f"failed: {backend_error}. The data may still exist "
                          f"in the backend.")
    return jsonify(resp)


@app.route("/healthz", methods=["GET"])
def healthz():
    """
    Liveness/readiness endpoint for deployment monitoring (load balancers,
    Docker/Kubernetes healthchecks, uptime pings). Deliberately does NOT
    touch session state — it should return 200 even for a caller with no
    cookies at all, which is exactly what a healthcheck request looks
    like. Reports whether the embeddings/LLM path is configured, not
    whether it's currently reachable — an actual OpenRouter call on every
    healthcheck would be slow and cost money for something checked every
    few seconds.
    """
    return jsonify({
        "status": "ok",
        "embeddings_configured": bool(OPENROUTER_API_KEY),
        "retrieval_mode": RETRIEVAL_MODE if OPENROUTER_API_KEY else "tfidf-only",
        "vector_backend": VECTOR_BACKEND,
        "active_sessions": len(SESSION_ACCESS),
    })


@app.route("/status", methods=["GET"])
def status():
    sid = session.get("session_id")
    chunks = _get_store(sid).chunks if sid else []

    session_files = SESSION_FILES.get(sid, {})

    docs_seen: dict[str, dict] = {}
    for c in chunks:
        if c["doc_id"] not in docs_seen:
            docs_seen[c["doc_id"]] = {
                "filename": c["filename"],
                "doc_id": c["doc_id"],
                "chunk_count": 0,
                "method": c["method"],
                "openable": c["doc_id"] in session_files,
            }
        docs_seen[c["doc_id"]]["chunk_count"] += 1

    return jsonify({
        "total_chunks": len(chunks),
        "documents": list(docs_seen.values()),
        "methods": sorted({c["method"] for c in chunks}),
        "mode": (RETRIEVAL_MODE if OPENROUTER_API_KEY else "tfidf-only"),
        "vector_backend": VECTOR_BACKEND,
    })


@app.errorhandler(413)
def too_large(_e):
    return jsonify({"error": "File too large (max 50 MB)"}), 413


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    # Defaults to loopback-only — safe for `python app.py` on your own
    # machine (not reachable from your LAN). MUST be "0.0.0.0" when run
    # inside Docker: a container's own loopback interface is invisible to
    # `docker run -p`/docker-compose's port mapping, so binding to
    # 127.0.0.1 in a container means the port mapping silently does
    # nothing — the container starts fine, but nothing outside it can
    # ever reach the server. docker-compose.yml sets HOST=0.0.0.0 for
    # exactly this reason; don't set it that way for a bare local run
    # unless you actually want this reachable from your whole network.
    host = os.environ.get("HOST", "127.0.0.1")
    debug = os.environ.get("APP_DEBUG", "").lower() in ("1", "true", "yes")
    print(f"\n🚀 Ask My Docs is running → http://localhost:{port}")
    print(f"   Mode: {'embeddings + LLM' if OPENROUTER_API_KEY else 'TF-IDF (offline fallback)'}\n")
    try:
        from waitress import serve
        serve(app, host=host, port=port)
    except ImportError:
        app.run(host=host, debug=debug, port=port)