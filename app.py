import os
import re
import sys
import math
import json
import time
import uuid
import pickle
import hashlib
import urllib.request
import urllib.parse
import html.parser
from pathlib import Path
from collections import Counter

import fitz  # PyMuPDF
from flask import Flask, request, jsonify, render_template, session, send_file
from werkzeug.utils import secure_filename

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass


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
app.secret_key = os.environ.get("SECRET_KEY", "ask-my-docs-secret-2026")
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
HASH_STORE: dict[str, set[str]] = {}
# Tracks which content-hash belongs to which doc_id, per session, so that
# removing a single document can also forget its hash (see remove_doc()).
# Without this, a removed document's hash stays in HASH_STORE forever and
# re-uploading the exact same file later is incorrectly rejected as a
# duplicate for the rest of the session.
HASH_BY_DOC: dict[str, dict[str, str]] = {}
SESSION_FILES: dict[str, dict[str, dict]] = {}
CHUNK_COUNTS: dict[str, dict[str, int]] = {}

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

    def load(self) -> None:
        if self.path.exists():
            try:
                data = pickle.loads(self.path.read_bytes())
                self.chunks = data["chunks"]
                self.vectors = data["vectors"]
            except Exception:
                self.chunks, self.vectors = [], []

    def save(self) -> None:
        self.path.write_bytes(pickle.dumps({"chunks": self.chunks, "vectors": self.vectors}))

    def add(self, chunks: list[dict], vectors: list[list[float]]) -> None:
        self.chunks.extend(chunks)
        self.vectors.extend(vectors)
        self.save()

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
            self.save()
        return removed


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
            continue
        for meta in data.values():
            referenced.add(str(Path(meta.get("path", "")).resolve()))
    for f in UPLOAD_FOLDER.iterdir():
        if f.name.endswith(".manifest.json"):
            continue
        if str(f.resolve()) not in referenced:
            f.unlink(missing_ok=True)


_sweep_orphan_uploads()


def _get_store(sid: str) -> VectorStore:
    """Return this session's vector store, evicting stale/overflowing sessions."""
    now = time.time()
    for s in list(SESSION_ACCESS):
        if now - SESSION_ACCESS[s] > SESSION_TTL:
            VECTOR_STORE.pop(s, None)
            SESSION_ACCESS.pop(s, None)
            HASH_STORE.pop(s, None)
            HASH_BY_DOC.pop(s, None)
            (VECTOR_FOLDER / f"{s}.pkl").unlink(missing_ok=True)
            _cleanup_session_files(s)
    if len(SESSION_ACCESS) >= MAX_SESSIONS and sid not in SESSION_ACCESS:
        oldest = min(SESSION_ACCESS, key=SESSION_ACCESS.get)
        VECTOR_STORE.pop(oldest, None)
        SESSION_ACCESS.pop(oldest, None)
        HASH_STORE.pop(oldest, None)
        HASH_BY_DOC.pop(oldest, None)
        (VECTOR_FOLDER / f"{oldest}.pkl").unlink(missing_ok=True)
        _cleanup_session_files(oldest)
    SESSION_ACCESS[sid] = now
    _load_session_manifest(sid)

    store = VECTOR_STORE.get(sid)
    if store is None:
        store = VectorStore(sid)
        store.load()
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


def fetch_web_page(url: str) -> tuple[str, str]:
    """Fetch a URL and return (title, cleaned text)."""
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 AskMyDocs/1.0"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        raw = resp.read().decode("utf-8", errors="ignore")
    parser = _TextExtractor()
    parser.feed(raw)
    title = parser.title or urllib.parse.urlparse(url).netloc
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
        nonlocal block_type
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

        # Heading detection
        heading_match = re.match(r"^#{1,4}\s+(.*)", stripped)
        if heading_match:
            flush()
            current_section = heading_match.group(1).strip()
            current_section = re.sub(r"\*\*(.+?)\*\*", r"\1", current_section)
            current_section = re.sub(r"`(.+?)`", r"\1", current_section)
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

    index = build_index(store.chunks)
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
    a = answer.lower().strip()
    return any(m in a for m in _DONT_KNOW_MARKERS)


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


@app.route("/upload", methods=["POST"])
def upload():
    if "session_id" not in session:
        session["session_id"] = str(uuid.uuid4())

    sid = session["session_id"]
    chunk_mode = request.form.get("chunk_mode", "structured")

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

            if content_hash in hashes:
                filepath.unlink(missing_ok=True)
                results.append({"filename": original_name, "error": "Duplicate file skipped"})
                continue
            hashes.add(content_hash)

            doc_id = str(uuid.uuid4())[:8]
            doc_info = {"doc_id": doc_id, "filename": original_name}

            pages = (extract_pdf_pages(str(filepath)) if ext == "pdf"
                     else extract_txt_pages(str(filepath)))

            if not pages:
                filepath.unlink(missing_ok=True)
                hashes.discard(content_hash)
                reason = ("No extractable text (password-protected or scanned PDF?)"
                          if ext == "pdf" else "Empty file")
                results.append({"filename": original_name, "error": reason})
                continue

            new_chunks = chunk_text(doc_info, pages, chunk_mode)
            if not new_chunks:
                filepath.unlink(missing_ok=True)
                hashes.discard(content_hash)
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
                "hash": content_hash,
                "result": {
                    "filename": original_name,
                    "pages": len(pages),
                    "chunks": len(new_chunks),
                    "method": chunk_mode,
                },
            })
        except Exception as exc:
            filepath.unlink(missing_ok=True)
            hashes.discard(content_hash) if "content_hash" in locals() else None
            results.append({"filename": original_name, "error": f"Failed to index: {exc}"})

    if not pending:
        return jsonify({"ok": False, "error": "No valid documents were indexed.",
                        "documents": results}), 400

    store = _get_store(sid)
    for item in pending:
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
        except Exception as exc:
            item["filepath"].unlink(missing_ok=True)
            hashes.discard(item["hash"])
            results.append({"filename": item["filename"],
                            "error": f"Failed to index: {exc}"})

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
    return render_template("view.html", doc_id=doc_id, filename=info["name"])


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

    # Path 1: embeddings + LLM (if configured and vectors exist)
    if OPENROUTER_API_KEY and store.vectors and len(store.vectors) == len(store.chunks):
        try:
            if RETRIEVAL_MODE == "hybrid":
                results = hybrid_search(store, query, top_k=5)
                results = [r for r in results if r["score"] >= EMBED_MIN_SCORE]
            else:
                q_vec = embed_text(query)
                results = store.query(q_vec, top_k=5, min_score=EMBED_MIN_SCORE)
            if not validate_context(results, EMBED_MIN_SCORE):
                return jsonify({
                    "found": False,
                    "answer": "I don't know — no document content matched your question closely enough.",
                    "sources": [],
                })
            answer = generate_answer(query, results)
            return jsonify({
                "found": not _is_dont_know(answer),
                "answer": answer or "I don't know.",
                "sources": annotate_openable(results),
            })
        except Exception:
            pass  # fall through to TF-IDF

    # Path 2: offline TF-IDF fallback
    chunks = store.chunks
    index = build_index(chunks)
    results = search_chunks(query, chunks, index, top_k=4)
    resp = synthesize_answer(query, results)
    resp["sources"] = annotate_openable(resp.get("sources", []))
    return jsonify(resp)


@app.route("/clear", methods=["POST"])
def clear():
    sid = session.get("session_id")
    if sid:
        store = VECTOR_STORE.pop(sid, None)
        if store:
            store.clear()
        SESSION_ACCESS.pop(sid, None)
        HASH_STORE.pop(sid, None)
        HASH_BY_DOC.pop(sid, None)
        CHUNK_COUNTS.pop(sid, None)
        _cleanup_session_files(sid)
    return jsonify({"ok": True})


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

    return jsonify({"ok": True, "removed_chunks": removed_chunks})


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
        "mode": "TF-IDF",
    })


@app.errorhandler(413)
def too_large(_e):
    return jsonify({"error": "File too large (max 50 MB)"}), 413


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("APP_DEBUG", "").lower() in ("1", "true", "yes")
    print(f"\n🚀 Ask My Docs is running → http://localhost:{port}")
    print(f"   Mode: {'embeddings + LLM' if OPENROUTER_API_KEY else 'TF-IDF (offline fallback)'}\n")
    try:
        from waitress import serve
        serve(app, host="127.0.0.1", port=port)
    except ImportError:
        app.run(debug=debug, port=port)