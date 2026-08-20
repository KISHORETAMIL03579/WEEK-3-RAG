"""
Qdrant-backed VectorStore — a drop-in replacement for the in-memory
VectorStore in app.py, used when VECTOR_BACKEND=qdrant. Only imported
when that mode is actually selected (see app.py's _make_store()), so a
normal run with no Qdrant available is completely unaffected.

WORKS FOR BOTH DEPLOYMENT MODES
---------------------------------
Self-hosted (docker-compose.yml): QDRANT_URL=http://qdrant:6333, no API key.
Qdrant Cloud (cloud.qdrant.io):   QDRANT_URL=https://xxxx.cloud.qdrant.io:6333,
                                  QDRANT_API_KEY=<your cluster's key>.
Identical code path either way — QdrantClient(url=..., api_key=...) simply
ignores api_key=None for an unauthenticated local instance.

DESIGN NOTE — why this isn't a 1:1 swap under the hood
-------------------------------------------------------
Qdrant (like every real vector DB) is built for approximate top-k nearest-
neighbor search via an index (HNSW), not "give me a similarity score
against every single stored vector." hybrid_search() in app.py wants
exactly that second thing, to blend an embedding score with a TF-IDF
score chunk-for-chunk across the whole corpus. Pulling a score for every
vector out of a real ANN index defeats the reason to use one.

So query_scores() asks Qdrant for its top-N ANN candidates (N is larger
than the final top_k actually wanted — see QDRANT_CANDIDATE_POOL) and
returns real cosine scores for just those; everything outside that pool
gets a score of 0.0, same as a production system would do. TF-IDF
blending in hybrid_search() then only runs over that smaller candidate
pool's chunk metadata, not the entire corpus.

Chunk metadata (text, filename, page, method, section, ...) is mirrored
in Python memory (self.chunks) alongside Qdrant, because TF-IDF, listing
chunks, and dedupe are lexical/metadata operations — a vector DB isn't
the right tool for those. self.vectors mirrors the embedding vectors
themselves purely so existing code's `len(store.vectors) ==
len(store.chunks)` checks keep working unmodified regardless of backend.

Metadata filtering (filtered_by_method) IS pushed down into Qdrant as a
real payload filter on the "method" field, rather than filtering in
Python — this is the one place using a real vector DB is a genuine
upgrade over the in-memory version, not just a persistence swap.
"""

from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels

# Imported lazily by app.py, so these reference app's module-level config
# rather than redefining it — avoids two sources of truth for the same URL.
import app as _app


def _client() -> QdrantClient:
    if _QdrantSingleton.client is None:
        _QdrantSingleton.client = QdrantClient(
            url=_app.QDRANT_URL, api_key=_app.QDRANT_API_KEY, timeout=_app.QDRANT_TIMEOUT,
        )
    return _QdrantSingleton.client


class _QdrantSingleton:
    client: QdrantClient | None = None  # one shared client per process, across all sessions


class QdrantVectorStore:
    """Same public interface as app.VectorStore: load, save, add, query,
    query_scores, get_tfidf_index, clear, remove_doc, filtered_by_method,
    plus .chunks and .vectors attributes — so _get_store() can hand
    either backend to the rest of the app with no caller needing to know
    which one it got."""

    def __init__(self, sid: str, method_filter: str | None = None):
        self.sid = sid
        self.collection = f"chunks_{sid}"
        self.method_filter = method_filter
        self.chunks: list[dict] = []
        self.vectors: list[list[float]] = []
        self._tfidf_index_cache: dict | None = None
        # Set whenever a backend delete call fails — the local mirror still
        # gets updated so the UI doesn't get stuck, but this makes the
        # failure visible to whoever called remove_doc()/clear(), instead
        # of only ever showing up as a warning buried in server logs while
        # the API response reports plain success.
        self.last_backend_error: str | None = None

    def _collection_exists(self) -> bool:
        names = [c.name for c in _client().get_collections().collections]
        return self.collection in names

    def _ensure_collection(self, dim: int) -> None:
        if self._collection_exists():
            return
        _client().create_collection(
            collection_name=self.collection,
            vectors_config=qmodels.VectorParams(size=dim, distance=qmodels.Distance.COSINE),
        )

    def _qdrant_filter(self):
        if not self.method_filter:
            return None
        return qmodels.Filter(must=[
            qmodels.FieldCondition(key="method", match=qmodels.MatchValue(value=self.method_filter))
        ])

    @staticmethod
    def _point_id(chunk_id: str) -> str:
        # Qdrant point IDs must be a UUID or unsigned int; chunk ids look
        # like "abc123::c4" — namespace into a deterministic UUID5 rather
        # than trying to sanitize the string.
        import uuid as _uuid
        return str(_uuid.uuid5(_uuid.NAMESPACE_URL, chunk_id))

    # ── Persistence ──────────────────────────────────────────────────────

    def load(self) -> None:
        """Rehydrate the local chunk/vector mirror from Qdrant (e.g. after
        a process restart — Qdrant already persisted the vectors; this
        just repopulates the in-memory metadata mirror)."""
        try:
            if not self._collection_exists():
                return
        except Exception:
            _app.logger.warning("Qdrant not reachable at %s during load() — "
                               "starting this session empty.", _app.QDRANT_URL, exc_info=True)
            return
        chunks, vectors = [], []
        offset = None
        while True:
            points, offset = _client().scroll(
                collection_name=self.collection, with_payload=True, with_vectors=True,
                limit=256, offset=offset,
            )
            for p in points:
                chunks.append(p.payload)
                vectors.append(p.vector)
            if offset is None:
                break
        self.chunks, self.vectors = chunks, vectors
        self._tfidf_index_cache = None

    def save(self) -> None:
        pass  # Qdrant persists on every upsert; nothing to flush locally

    # ── Mutation ─────────────────────────────────────────────────────────

    def add(self, chunks: list[dict], vectors: list[list[float]]) -> None:
        self.chunks.extend(chunks)
        self.vectors.extend(vectors)
        self._tfidf_index_cache = None
        if not vectors:
            return  # TF-IDF-only mode: nothing to index into Qdrant
        self._ensure_collection(dim=len(vectors[0]))
        points = [
            qmodels.PointStruct(id=self._point_id(c["id"]), vector=v, payload=c)
            for c, v in zip(chunks, vectors)
        ]
        _client().upsert(collection_name=self.collection, points=points)

    def remove_doc(self, doc_id: str) -> int:
        before = len(self.chunks)
        self.last_backend_error = None
        try:
            if self._collection_exists():
                _client().delete(
                    collection_name=self.collection,
                    points_selector=qmodels.FilterSelector(filter=qmodels.Filter(must=[
                        qmodels.FieldCondition(key="doc_id", match=qmodels.MatchValue(value=doc_id))
                    ])),
                )
        except Exception as exc:
            self.last_backend_error = f"Qdrant delete failed: {exc}"
            _app.logger.warning("Qdrant delete-by-doc_id failed for %s — local mirror still "
                               "updated, but the collection may retain stale points.",
                               doc_id, exc_info=True)
        kept = [(c, v) for c, v in zip(self.chunks, self.vectors) if c["doc_id"] != doc_id]
        self.chunks = [c for c, _ in kept]
        self.vectors = [v for _, v in kept]
        removed = before - len(self.chunks)
        if removed:
            self._tfidf_index_cache = None
        return removed

    def clear(self) -> None:
        self.last_backend_error = None
        try:
            if self._collection_exists():
                _client().delete_collection(self.collection)
        except Exception as exc:
            self.last_backend_error = f"Qdrant delete_collection failed: {exc}"
            _app.logger.warning("Qdrant delete_collection failed for %s during clear().",
                               self.collection, exc_info=True)
        self.chunks, self.vectors = [], []
        self._tfidf_index_cache = None

    # ── Retrieval ────────────────────────────────────────────────────────

    def get_tfidf_index(self) -> dict:
        """Mirrors VectorStore.get_tfidf_index()'s caching exactly, over
        this store's local chunk mirror — TF-IDF is a lexical operation
        Qdrant doesn't do, so it always runs against Python-side chunks
        regardless of backend."""
        if self._tfidf_index_cache is None:
            self._tfidf_index_cache = _app.build_index(self.chunks)
        return self._tfidf_index_cache

    def query(self, vector: list[float], top_k: int = 5, min_score: float = 0.0) -> list[dict]:
        try:
            if not self._collection_exists():
                return []
            hits = _client().search(
                collection_name=self.collection, query_vector=vector,
                query_filter=self._qdrant_filter(),
                limit=top_k, score_threshold=min_score,
            )
        except Exception:
            _app.logger.warning("Qdrant search failed — returning no results for this query.",
                               exc_info=True)
            return []
        return [{**h.payload, "score": h.score} for h in hits]

    def query_scores(self, vector: list[float]) -> list[float]:
        """Approximates the in-memory backend's "score against every
        chunk" by scoring only the top ANN candidates (see module
        docstring) and defaulting everything else to 0.0."""
        try:
            if not self._collection_exists():
                return [0.0] * len(self.chunks)
            hits = _client().search(
                collection_name=self.collection, query_vector=vector,
                query_filter=self._qdrant_filter(),
                limit=_app.QDRANT_CANDIDATE_POOL,
            )
        except Exception:
            _app.logger.warning("Qdrant search failed during hybrid scoring — "
                               "treating all candidates as score 0.0 for this query.",
                               exc_info=True)
            hits = []
        score_by_id = {h.payload["id"]: h.score for h in hits}
        return [score_by_id.get(c["id"], 0.0) for c in self.chunks]

    def filtered_by_method(self, method: str) -> "QdrantVectorStore":
        """Unlike the in-memory backend, this pushes the filter down into
        Qdrant itself (see _qdrant_filter()) rather than slicing lists in
        Python. The local .chunks/.vectors mirror is narrowed too, purely
        so callers that inspect them directly (e.g. the TF-IDF fallback,
        or a plain `if not store.chunks` check) see a consistent view
        regardless of which backend is active."""
        view = QdrantVectorStore(self.sid, method_filter=method)
        has_vectors = len(self.vectors) == len(self.chunks)
        matched = [i for i, c in enumerate(self.chunks) if c.get("method") == method]
        view.chunks = [self.chunks[i] for i in matched]
        view.vectors = [self.vectors[i] for i in matched] if has_vectors else []
        return view