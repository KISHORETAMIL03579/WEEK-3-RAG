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
import os
import app as _app

QDRANT_SCROLL_LIMIT = int(os.environ.get("QDRANT_SCROLL_LIMIT", "256"))


def _client() -> QdrantClient:
    if _QdrantSingleton.client is None:
        _QdrantSingleton.client = QdrantClient(
            url=_app.QDRANT_URL,
            api_key=_app.QDRANT_API_KEY,
            timeout=_app.QDRANT_TIMEOUT,
            prefer_grpc=False,
        )
    return _QdrantSingleton.client


class _QdrantSingleton:
    client: QdrantClient | None = None  # one shared client per process, across all sessions


RetrievalBackendError = _app.RetrievalBackendError


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
        client = _client()
        if not self._collection_exists():
            client.create_collection(
                collection_name=self.collection,
                vectors_config=qmodels.VectorParams(size=dim, distance=qmodels.Distance.COSINE),
            )
        # Ensure payload indexes exist regardless of whether the collection
        # was just created or already existed — Qdrant requires an explicit
        # index on any field you filter by (remove_doc()'s doc_id filter,
        # filtered_by_method()'s method filter).
        for field_name in ("doc_id", "method"):
            try:
                client.create_payload_index(
                    collection_name=self.collection,
                    field_name=field_name,
                    field_schema="keyword",
                )
            except Exception as exc:
                err_msg = str(exc).lower()
                if "already exists" in err_msg or "already indexed" in err_msg:
                    _app.logger.debug("Payload index on %s already exists in %s", field_name, self.collection)
                else:
                    _app.logger.warning("Failed to create Qdrant payload index on %s (%s): %s",
                                        field_name, self.collection, exc)

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
        """Rehydrate the local chunk/vector mirror from Qdrant with controlled
        exception handling wrapping the full scroll pagination sequence."""
        try:
            if not self._collection_exists():
                return
            chunks, vectors = [], []
            offset = None
            while True:
                points, offset = _client().scroll(
                    collection_name=self.collection, with_payload=True, with_vectors=True,
                    limit=QDRANT_SCROLL_LIMIT, offset=offset,
                )
                for p in points:
                    chunks.append(p.payload)
                    vectors.append(p.vector)
                if offset is None:
                    break
            self.chunks, self.vectors = chunks, vectors
            self._tfidf_index_cache = None
        except Exception as exc:
            self.last_backend_error = f"Qdrant load failed: {exc}"
            _app.logger.error("Qdrant load failed for collection %s: %s",
                              self.collection, exc, exc_info=True)
            raise RetrievalBackendError(f"Failed to load collection from Qdrant: {exc}") from exc

    def save(self) -> None:
        pass  # Qdrant persists on every upsert; nothing to flush locally

    # ── Mutation ─────────────────────────────────────────────────────────

    def add(self, chunks: list[dict], vectors: list[list[float]]) -> None:
        if not chunks:
            return
        if not vectors:
            raise ValueError(
                "QdrantVectorStore requires non-empty embedding vectors for all chunks. "
                "Vectorless / TF-IDF-only inserts cannot be durably persisted in Qdrant."
            )
        if len(chunks) != len(vectors):
            raise ValueError(
                f"Chunk/vector length mismatch: {len(chunks)} chunks vs {len(vectors)} vectors"
            )

        self._ensure_collection(dim=len(vectors[0]))
        points = [
            qmodels.PointStruct(id=self._point_id(c["id"]), vector=v, payload=c)
            for c, v in zip(chunks, vectors)
        ]
        # Write to Qdrant FIRST: if upsert fails, local mirror is not left desynchronized
        _client().upsert(collection_name=self.collection, points=points)

        # Confirm write in local mirror
        self.chunks.extend(chunks)
        self.vectors.extend(vectors)
        self._tfidf_index_cache = None

    def remove_doc(self, doc_id: str) -> int:
        """Consistency-first deletion: deletes from Qdrant first. If backend
        deletion fails, raises RetrievalBackendError and preserves local mirror."""
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
            _app.logger.error("Qdrant delete-by-doc_id failed for %s: %s", doc_id, exc, exc_info=True)
            raise RetrievalBackendError(f"Failed to delete document from Qdrant: {exc}") from exc

        # Only mutate local mirror after backend confirmation
        kept = [(c, v) for c, v in zip(self.chunks, self.vectors) if c["doc_id"] != doc_id]
        self.chunks = [c for c, _ in kept]
        self.vectors = [v for _, v in kept]
        removed = before - len(self.chunks)
        if removed:
            self._tfidf_index_cache = None
        return removed

    def clear(self) -> None:
        """Consistency-first clear: drops collection from Qdrant first.
        If backend drop fails, raises RetrievalBackendError and preserves local mirror."""
        self.last_backend_error = None
        try:
            if self._collection_exists():
                _client().delete_collection(self.collection)
        except Exception as exc:
            self.last_backend_error = f"Qdrant delete_collection failed: {exc}"
            _app.logger.error("Qdrant delete_collection failed for %s: %s", self.collection, exc, exc_info=True)
            raise RetrievalBackendError(f"Failed to clear Qdrant collection: {exc}") from exc

        # Only clear local mirror after backend confirmation
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
            response = _client().query_points(
                collection_name=self.collection, query=vector,
                query_filter=self._qdrant_filter(),
                limit=top_k, score_threshold=min_score,
            )
            hits = response.points
        except Exception as exc:
            self.last_backend_error = f"Qdrant query failed: {exc}"
            _app.logger.error("Qdrant retrieval query failed for collection %s: %s",
                              self.collection, exc, exc_info=True)
            raise RetrievalBackendError(f"Vector retrieval failed: {exc}") from exc
        return [{**h.payload, "score": h.score} for h in hits]

    def query_scores(self, vector: list[float]) -> list[float]:
        """Scores top ANN candidates from Qdrant, propagating backend errors
        if the vector database fails rather than silently returning all zeros."""
        try:
            if not self._collection_exists():
                return [0.0] * len(self.chunks)
            response = _client().query_points(
                collection_name=self.collection, query=vector,
                query_filter=self._qdrant_filter(),
                limit=_app.QDRANT_CANDIDATE_POOL,
            )
            hits = response.points
        except Exception as exc:
            self.last_backend_error = f"Qdrant query_scores failed: {exc}"
            _app.logger.error("Qdrant query_scores failed for collection %s: %s",
                              self.collection, exc, exc_info=True)
            raise RetrievalBackendError(f"Vector hybrid scoring failed: {exc}") from exc
        score_by_id = {h.payload["id"]: h.score for h in hits}
        return [score_by_id.get(c["id"], 0.0) for c in self.chunks]

    def filtered_by_method(self, method: str) -> "QdrantVectorStore":
        view = QdrantVectorStore(self.sid, method_filter=method)
        has_vectors = len(self.vectors) == len(self.chunks)
        matched = [i for i, c in enumerate(self.chunks) if c.get("method") == method]
        view.chunks = [self.chunks[i] for i in matched]
        view.vectors = [self.vectors[i] for i in matched] if has_vectors else []
        return view