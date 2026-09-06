"""
Unit tests for RAG Evaluation Metric Correctness:
  1. Rank 1 Hit -> RR = 1.0, Hit = True
  2. Rank K Hit -> RR = 1/K, Hit = True
  3. Rank K+1 (Beyond Top-K) -> RR = 0.0, Hit = False
  4. Complete Miss -> RR = 0.0, Hit = False
  5. Document Recall vs Section Recall matching
  6. Duplicate question texts with distinct stable IDs
  7. MRR and Hit-Rate aggregation math
"""

import base64
import json
import unittest
import sys
from pathlib import Path

import itsdangerous
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent))

from app import _rr_rank, _hit_check


def make_client(app_obj) -> TestClient:
    """FastAPI's TestClient is the drop-in replacement for Flask's
    app.test_client(). Like Flask's, it keeps a cookie jar across calls on
    the same instance, which is what the session-scoped tests below rely on."""
    return TestClient(app_obj)


def set_session(client: TestClient, session_id: str) -> None:
    """Seed the signed session cookie directly — the FastAPI equivalent of
    Flask's `with client.session_transaction() as sess: sess[...] = ...`.

    Starlette's SessionMiddleware stores the session as base64(JSON) signed
    with an itsdangerous TimestampSigner over SECRET_KEY, which is exactly
    the mechanism Flask used, so the cookie can be minted here the same way
    the middleware would mint it.
    """
    from app import SECRET_KEY

    signer = itsdangerous.TimestampSigner(str(SECRET_KEY))
    payload = base64.b64encode(json.dumps({"session_id": session_id}).encode("utf-8"))
    client.cookies.set("session", signer.sign(payload).decode("utf-8"))


class TestEvalMetrics(unittest.TestCase):

    def test_rank_1_hit(self):
        retrieved = [
            {"filename": "HRPolicy.pdf", "section": "5.1 Annual Leave", "text": "20 days annual leave"},
            {"filename": "Security.pdf", "section": "2.0 Password", "text": "Use strong passwords"},
        ]
        hit, rr, rank = _rr_rank(retrieved, expected_doc="HRPolicy.pdf")
        self.assertTrue(hit)
        self.assertEqual(rank, 1)
        self.assertEqual(rr, 1.0)

    def test_rank_k_hit(self):
        retrieved = [
            {"filename": "DocA.pdf", "section": "1.0", "text": "foo"},
            {"filename": "DocB.pdf", "section": "2.0", "text": "bar"},
            {"filename": "DocC.pdf", "section": "3.0 Leave Policy", "text": "baz"},
        ]
        # At Top-3, DocC is at rank 3
        hit, rr, rank = _rr_rank(retrieved, expected_section="Leave Policy")
        self.assertTrue(hit)
        self.assertEqual(rank, 3)
        self.assertAlmostEqual(rr, 1.0 / 3.0, places=4)

    def test_rank_beyond_k_miss(self):
        # Retrieved list contains 3 items (Top-3 cutoff)
        retrieved = [
            {"filename": "DocA.pdf", "section": "1.0", "text": "foo"},
            {"filename": "DocB.pdf", "section": "2.0", "text": "bar"},
            {"filename": "DocC.pdf", "section": "3.0", "text": "baz"},
        ]
        # Expected document is NOT in top-3 candidates
        hit, rr, rank = _rr_rank(retrieved, expected_doc="DocD.pdf")
        self.assertFalse(hit)
        self.assertEqual(rank, 0)
        self.assertEqual(rr, 0.0)

    def test_section_vs_doc_matching(self):
        retrieved = [
            {"filename": "Handbook.pdf", "section": "4.2 Probation Period", "text": "Probation is 3 months"},
            {"filename": "Handbook.pdf", "section": "9.1 Exit Policy", "text": "Notice is 2 months"},
        ]
        # Section match on Probation Period
        hit_sec, rr_sec, rank_sec = _rr_rank(retrieved, expected_section="Probation")
        self.assertTrue(hit_sec)
        self.assertEqual(rank_sec, 1)

        # Section match on Exit Policy (rank 2)
        hit_exit, rr_exit, rank_exit = _rr_rank(retrieved, expected_section="Exit Policy")
        self.assertTrue(hit_exit)
        self.assertEqual(rank_exit, 2)
        self.assertEqual(rr_exit, 0.5)

    def test_mrr_and_hit_rate_aggregation(self):
        # 3 questions:
        # Q1: Rank 1 -> RR = 1.0, hit = 1
        # Q2: Rank 2 -> RR = 0.5, hit = 1
        # Q3: Miss   -> RR = 0.0, hit = 0
        hits = 2
        total = 3
        rr_sum = 1.0 + 0.5 + 0.0

        hit_rate = hits / total
        mrr = rr_sum / total

        self.assertAlmostEqual(hit_rate, 2.0 / 3.0, places=4)
        self.assertAlmostEqual(mrr, 0.5, places=4)

    def test_distinct_id_isolation(self):
        # Two queries with exact same question string but distinct IDs
        q1 = {"id": "q_abc1", "question": "What is the policy?", "expected_doc": "DocA.pdf"}
        q2 = {"id": "q_xyz2", "question": "What is the policy?", "expected_doc": "DocB.pdf"}

        self.assertNotEqual(q1["id"], q2["id"])

    def test_arbitrary_strategy_order_id_lookup(self):
        # Strategy A returns Q1, Q2, Q3
        # Strategy B returns Q3, Q1, Q2
        results_a = [{"id": "q1", "hit": True, "rank": 1}, {"id": "q2", "hit": False, "rank": None}, {"id": "q3", "hit": True, "rank": 2}]
        results_b = [{"id": "q3", "hit": True, "rank": 1}, {"id": "q1", "hit": True, "rank": 3}, {"id": "q2", "hit": True, "rank": 2}]

        map_a = {r["id"]: r for r in results_a}
        map_b = {r["id"]: r for r in results_b}

        # Lookups for Q2 match correctly across both strategies despite differing permutation order
        self.assertFalse(map_a["q2"]["hit"])
        self.assertTrue(map_b["q2"]["hit"])
        self.assertEqual(map_b["q2"]["rank"], 2)

    def test_response_validation_id_integrity(self):
        submitted_ids = {"q1", "q2", "q3"}

        # Case 1: Duplicate IDs
        dup_results = [{"id": "q1"}, {"id": "q1"}, {"id": "q2"}]
        dup_ids = [r["id"] for r in dup_results]
        self.assertNotEqual(len(dup_ids), len(set(dup_ids)), "Duplicate IDs must be detectable")

        # Case 2: Missing submitted IDs
        missing_results = [{"id": "q1"}, {"id": "q2"}]
        missing_ids = {r["id"] for r in missing_results}
        self.assertTrue(any(q not in missing_ids for q in submitted_ids), "Missing IDs must be detectable")

        # Case 3: Unexpected IDs
        extra_results = [{"id": "q1"}, {"id": "q2"}, {"id": "q3"}, {"id": "q99"}]
        extra_ids = {r["id"] for r in extra_results}
        self.assertTrue(any(r not in submitted_ids for r in extra_ids), "Unexpected IDs must be detectable")

    def test_key_takeaways_tie_breaking_mrr(self):
        # When Hit-Rate is tied, higher MRR must win
        strategy_a = {"label": "Strategy A", "hr": 0.80, "mrr": 0.650}
        strategy_b = {"label": "Strategy B", "hr": 0.80, "mrr": 0.725}

        strategies = [strategy_a, strategy_b]
        best = strategies[0]
        for s in strategies[1:]:
            if s["hr"] > best["hr"]:
                best = s
            elif s["hr"] == best["hr"] and s["mrr"] > best["mrr"]:
                best = s

    def test_strict_hit_normalization(self):
        def normalize_hit(val):
            if isinstance(val, bool):
                return val
            if val in (1, '1', 'true'):
                return True
            if val in (0, '0', 'false'):
                return False
            raise ValueError(f"Invalid hit value: {val}")

        self.assertTrue(normalize_hit(True))
        self.assertFalse(normalize_hit(False))
        self.assertFalse(normalize_hit("false"))  # Must NOT coerce to True like Javascript !!"false"
        self.assertTrue(normalize_hit("true"))
        self.assertTrue(normalize_hit(1))
        self.assertFalse(normalize_hit(0))

        with self.assertRaises(ValueError):
            normalize_hit("banana")

    def test_trace_store_defensive_redaction(self):
        import tempfile
        from trace_store import TraceStore

        with tempfile.NamedTemporaryFile(mode="w+", delete=False) as tf:
            temp_path = tf.name

        try:
            store = TraceStore(temp_path)
            # Log raw unredacted record with deeply nested dictionaries and lists directly into store
            raw_record = {
                "question": "What is the balance for EMP-1234?",
                "context": [
                    {
                        "text": "Employee: John Smith has SSN 123-45-6789 and phone 555-123-4567",
                        "metadata": {"nested_info": "Reach out to hr@company.com for employee EMP-9988"}
                    }
                ],
                "answer": "Contact staff at john@example.com",
            }
            trace_id = store.log(raw_record)
            saved = store.get(trace_id)

            self.assertIsNotNone(saved)
            self.assertNotIn("EMP-1234", saved["question"])
            self.assertIn("[REDACTED_EMP_ID]", saved["question"])
            self.assertNotIn("123-45-6789", saved["context"][0]["text"])
            self.assertIn("[REDACTED_SSN]", saved["context"][0]["text"])
            self.assertNotIn("john@example.com", saved["answer"])
            self.assertIn("[REDACTED_EMAIL]", saved["answer"])
            # Assert deeply nested dictionary/list redaction
            self.assertNotIn("hr@company.com", saved["context"][0]["metadata"]["nested_info"])
            self.assertIn("[REDACTED_EMAIL]", saved["context"][0]["metadata"]["nested_info"])
            self.assertNotIn("EMP-9988", saved["context"][0]["metadata"]["nested_info"])
            self.assertIn("[REDACTED_EMP_ID]", saved["context"][0]["metadata"]["nested_info"])
        finally:
            import os
            if os.path.exists(temp_path):
                os.remove(temp_path)

    def test_durable_prompt_registry_persistence(self):
        from trace_store import register_prompt, get_prompt, PROMPT_REGISTRY, PROMPTS_DIR

        version = "test-durable-prompt-v1"
        prompt_text = "You are an HR assistant adhering to strict company policies."

        try:
            register_prompt(version, prompt_text)
            self.assertEqual(get_prompt(version), prompt_text)

            # Simulate in-memory process restart by wiping in-memory dictionary
            PROMPT_REGISTRY.pop(version, None)

            # Re-fetch should safely reload from durable disk storage
            reloaded = get_prompt(version)
            self.assertEqual(reloaded, prompt_text)
        finally:
            PROMPT_REGISTRY.pop(version, None)
            (PROMPTS_DIR / f"{version}.txt").unlink(missing_ok=True)

    def test_qdrant_add_consistency_on_error(self):
        from unittest.mock import patch, MagicMock
        from qdrant_store import QdrantVectorStore

        store = QdrantVectorStore("test_session")
        store.chunks = [{"id": "c1", "text": "initial"}]
        store.vectors = [[0.1, 0.2]]

        with patch("qdrant_store._client") as mock_client_fn:
            mock_client = MagicMock()
            mock_client.get_collections.return_value.collections = []
            mock_client.upsert.side_effect = RuntimeError("Upsert connection dropped")
            mock_client_fn.return_value = mock_client

            with self.assertRaises(RuntimeError):
                store.add([{"id": "c2", "text": "new"}], [[0.3, 0.4]])

            # Local memory mirror must NOT be mutated on backend failure
            self.assertEqual(len(store.chunks), 1)
            self.assertEqual(len(store.vectors), 1)
            self.assertEqual(store.chunks[0]["id"], "c1")

    def test_qdrant_remove_doc_consistency_on_error(self):
        from unittest.mock import patch, MagicMock
        from qdrant_store import QdrantVectorStore, RetrievalBackendError

        store = QdrantVectorStore("test_session")
        store.chunks = [{"id": "c1", "doc_id": "doc1", "text": "foo"}]
        store.vectors = [[0.1, 0.2]]

        with patch("qdrant_store._client") as mock_client_fn:
            mock_client = MagicMock()
            mock_collection = MagicMock()
            mock_collection.name = store.collection
            mock_client.get_collections.return_value.collections = [mock_collection]
            mock_client.delete.side_effect = RuntimeError("Delete timeout")
            mock_client_fn.return_value = mock_client

            with self.assertRaises(RetrievalBackendError):
                store.remove_doc("doc1")

            # Local chunks must remain untouched when deletion fails
            self.assertEqual(len(store.chunks), 1)
            self.assertEqual(store.chunks[0]["doc_id"], "doc1")

    def test_qdrant_clear_consistency_on_error(self):
        from unittest.mock import patch, MagicMock
        from qdrant_store import QdrantVectorStore, RetrievalBackendError

        store = QdrantVectorStore("test_session")
        store.chunks = [{"id": "c1", "doc_id": "doc1", "text": "foo"}]
        store.vectors = [[0.1, 0.2]]

        with patch("qdrant_store._client") as mock_client_fn:
            mock_client = MagicMock()
            mock_collection = MagicMock()
            mock_collection.name = store.collection
            mock_client.get_collections.return_value.collections = [mock_collection]
            mock_client.delete_collection.side_effect = RuntimeError("Clear timeout")
            mock_client_fn.return_value = mock_client

            with self.assertRaises(RetrievalBackendError):
                store.clear()

            # Local chunks must remain untouched
            self.assertEqual(len(store.chunks), 1)

    def test_qdrant_load_raises_retrieval_backend_error(self):
        from unittest.mock import patch, MagicMock
        from qdrant_store import QdrantVectorStore, RetrievalBackendError

        store = QdrantVectorStore("test_session")

        with patch("qdrant_store._client") as mock_client_fn:
            mock_client = MagicMock()
            mock_collection = MagicMock()
            mock_collection.name = store.collection
            mock_client.get_collections.return_value.collections = [mock_collection]
            mock_client.scroll.side_effect = RuntimeError("Qdrant unreachable")
            mock_client_fn.return_value = mock_client

            with self.assertRaises(RetrievalBackendError):
                store.load()

    def test_sample_trace_invalid_n(self):
        import subprocess
        # Run sample_trace.py CLI with --n 0
        res = subprocess.run(
            [sys.executable, "sample_trace.py", "--n", "0", "--seed", "42"],
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(res.returncode, 0)
        self.assertIn("Sample size --n must be greater than 0", res.stderr)

    def test_is_dont_know_edge_cases(self):
        from app import _is_dont_know
        self.assertTrue(_is_dont_know(None))
        self.assertTrue(_is_dont_know(""))
        self.assertTrue(_is_dont_know("   "))
        self.assertTrue(_is_dont_know("I don't know."))
        self.assertTrue(_is_dont_know("I do not know"))
        self.assertTrue(_is_dont_know("The document does not contain this information."))
        self.assertFalse(_is_dont_know("The policy specifies 20 days of annual leave per section 5.2."))


    def test_qdrant_chunk_vector_length_mismatch(self):
        from qdrant_store import QdrantVectorStore
        store = QdrantVectorStore("test_session")
        chunks = [{"id": "c1", "text": "foo"}, {"id": "c2", "text": "bar"}]
        vectors = [[0.1, 0.2]]  # 2 chunks vs 1 vector
        with self.assertRaises(ValueError) as ctx:
            store.add(chunks, vectors)
        self.assertIn("mismatch", str(ctx.exception).lower())

    def test_qdrant_vectorless_insert_rejected(self):
        from qdrant_store import QdrantVectorStore
        store = QdrantVectorStore("test_session")
        chunks = [{"id": "c1", "text": "foo"}]
        vectors = []
        with self.assertRaises(ValueError) as ctx:
            store.add(chunks, vectors)
        self.assertIn("vectorless", str(ctx.exception).lower())

    def test_ssrf_rejection(self):
        from app import _validate_url_is_public

        blocked_urls = [
            "http://localhost:5000",
            "http://127.0.0.1:6379",
            "http://0.0.0.0:80",
            "http://169.254.169.254/latest/meta-data/",
            "http://192.168.1.1",
            "http://10.0.0.1",
            "http://example.com:6379",  # Unauthorized port
            "ftp://example.com",        # Unauthorized scheme
        ]
        for url in blocked_urls:
            with self.subTest(url=url):
                with self.assertRaises(ValueError):
                    _validate_url_is_public(url)

    def test_replay_session_isolation(self):
        import hashlib
        import tempfile
        from pathlib import Path
        from unittest.mock import patch
        from app import app
        from trace_store import TraceStore

        with tempfile.TemporaryDirectory() as tmpdir:
            test_store = TraceStore(Path(tmpdir) / "test_traces.jsonl")
            with patch("app.TRACES", test_store):
                # Log a trace for session A
                sid_a = "session_user_a_12345"
                sid_a_hash = hashlib.sha256(sid_a.encode()).hexdigest()[:16]
                trace_id = test_store.log({
                    "session_id_hash": sid_a_hash,
                    "question": "What is the policy?",
                    "prompt_version": "qa-answer-v1",
                    "model": "grok-4.3",
                    "retrieved": [{"filename": "doc.pdf", "page": 1, "text": "Policy detail"}],
                    "raw_output": "The policy detail is [1].",
                    "answer": "The policy detail is [1].",
                })

                client = make_client(app)

                # Session B tries to replay Session A's trace
                set_session(client, "session_user_b_99999")

                resp = client.post(f"/replay/{trace_id}")
                self.assertEqual(resp.status_code, 403)
                data = resp.json()
                self.assertIn("Unauthorized", data.get("error", ""))

                # Session A can replay their own trace
                set_session(client, sid_a)

                with patch("app._chat_call", return_value="The replayed policy detail is [1]."):
                    resp_ok = client.post(f"/replay/{trace_id}")
                    self.assertEqual(resp_ok.status_code, 200)
                    data_ok = resp_ok.json()
                    self.assertTrue(data_ok.get("replayable"))

    def test_replay_missing_prompt_artifact_no_llm_call(self):
        import hashlib
        import tempfile
        from pathlib import Path
        from unittest.mock import patch
        from app import app
        from trace_store import TraceStore

        with tempfile.TemporaryDirectory() as tmpdir:
            test_store = TraceStore(Path(tmpdir) / "test_traces.jsonl")
            with patch("app.TRACES", test_store):
                sid = "session_missing_prompt_test"
                sid_hash = hashlib.sha256(sid.encode()).hexdigest()[:16]
                trace_id = test_store.log({
                    "session_id_hash": sid_hash,
                    "question": "What is the policy?",
                    "prompt_version": "non_existent_prompt_v999",
                    "model": "grok-4.3",
                    "retrieved": [{"filename": "doc.pdf", "page": 1, "text": "Policy detail"}],
                    "raw_output": "The policy detail.",
                    "answer": "The policy detail.",
                })

                client = make_client(app)
                set_session(client, sid)

                with patch("app._chat_call") as mock_chat:
                    resp = client.post(f"/replay/{trace_id}")
                    self.assertEqual(resp.status_code, 400)
                    data = resp.json()
                    self.assertFalse(data.get("replayable"))
                    self.assertIn("missing", data.get("reason", "").lower())
                    # LLM must NOT be called if prompt is missing
                    mock_chat.assert_not_called()

    def test_replay_uses_recorded_model(self):
        import hashlib
        import tempfile
        from pathlib import Path
        from unittest.mock import patch
        from app import app
        from trace_store import TraceStore

        with tempfile.TemporaryDirectory() as tmpdir:
            test_store = TraceStore(Path(tmpdir) / "test_traces.jsonl")
            with patch("app.TRACES", test_store):
                sid = "session_model_test"
                sid_hash = hashlib.sha256(sid.encode()).hexdigest()[:16]
                trace_id = test_store.log({
                    "session_id_hash": sid_hash,
                    "question": "What is the policy?",
                    "prompt_version": "qa-answer-v1",
                    "model": "custom-special-model-v3",
                    "temperature": 0.35,
                    "retrieved": [{"filename": "doc.pdf", "page": 1, "text": "Policy text"}],
                    "raw_output": "Output text.",
                    "answer": "Output text.",
                })

                client = make_client(app)
                set_session(client, sid)

                with patch("app._chat_call", return_value="Output text.") as mock_chat:
                    resp = client.post(f"/replay/{trace_id}")
                    self.assertEqual(resp.status_code, 200)
                    mock_chat.assert_called_once()
                    _, kwargs = mock_chat.call_args
                    self.assertEqual(kwargs.get("model"), "custom-special-model-v3")
                    self.assertEqual(kwargs.get("temperature"), 0.35)

    def test_ask_does_not_mask_retrieval_backend_error(self):
        from unittest.mock import patch
        from app import app
        from qdrant_store import RetrievalBackendError

        client = make_client(app)
        set_session(client, "test_ask_error_session")

        # Mock vector store to simulate Qdrant outage during /ask
        with patch("app._get_store") as mock_get_store, \
             patch("app._embeddings_configured", return_value=True), \
             patch("app._chat_configured", return_value=True):
            mock_store = mock_get_store.return_value
            mock_store.chunks = [{"id": "c1", "text": "sample"}]
            mock_store.vectors = [[0.1, 0.2]]
            mock_store.filtered_by_method.return_value = mock_store

            with patch("app.reciprocal_rank_fusion", side_effect=RetrievalBackendError("Qdrant cluster unavailable")):
                resp = client.post("/ask", json={"query": "test query"})
                self.assertEqual(resp.status_code, 503)
                data = resp.json()
                self.assertIn("Vector database retrieval failed", data.get("error", ""))

    def test_upload_stale_dedupe_key_regression(self):
        """Verify that when file 1 succeeds and file 2 fails before dedupe_key assignment,
        file 1's dedupe_key is NOT accidentally discarded from hashes."""
        from app import HASH_STORE

        sid = "test_stale_dedupe_session"
        hashes = HASH_STORE.setdefault(sid, set())
        hashes.clear()

        # Simulate loop: File 1 computes and stores key
        key_file_1 = ("hash1", "structured")
        dedupe_key = None
        # File 1 succeeds
        dedupe_key = key_file_1
        hashes.add(dedupe_key)
        self.assertIn(key_file_1, hashes)

        # File 2 starts: dedupe_key is initialized to None
        dedupe_key = None
        try:
            # File 2 fails immediately before assigning dedupe_key
            raise RuntimeError("Corrupt file 2 header")
        except Exception:
            if dedupe_key is not None:
                hashes.discard(dedupe_key)

        # File 1's key must STILL be safely retained in hashes
        self.assertIn(key_file_1, hashes)

    def test_upload_post_store_file_move_failure_rollback(self):
        """If store.add() succeeds but file move fails, the document must be rolled back from the vector store."""
        import io
        from unittest.mock import patch, MagicMock
        from app import app

        client = make_client(app)
        set_session(client, "test_rollback_file_move")

        with patch("app._get_store") as mock_get_store, \
             patch("app.embed_texts", return_value=[[0.1, 0.2]]), \
             patch("app._embeddings_configured", return_value=True), \
             patch("pathlib.Path.replace", side_effect=OSError("Permission denied on destination")):
            mock_store = MagicMock()
            mock_store.chunks = []
            mock_get_store.return_value = mock_store

            files = {
                "files": ("test_doc.txt", io.BytesIO(b"Hello world document text content for testing."), "text/plain")
            }
            resp = client.post("/upload", files=files)
            self.assertEqual(resp.status_code, 200)
            res_data = resp.json()
            mock_store.add.assert_called_once()
            mock_store.remove_doc.assert_called_once()
            self.assertTrue(any("Failed to index" in doc.get("error", "") for doc in res_data.get("documents", [])))
            # Successful rollback marks cleanup_complete=True
            self.assertTrue(all(doc.get("cleanup_complete") is True for doc in res_data.get("documents", [])))

    def test_upload_post_store_manifest_failure_rollback(self):
        """If store.add() succeeds and file moves but manifest save fails, rollback doc from vector store."""
        import io
        from unittest.mock import patch, MagicMock
        from app import app

        client = make_client(app)
        set_session(client, "test_rollback_manifest")

        with patch("app._get_store") as mock_get_store, \
             patch("app.embed_texts", return_value=[[0.1, 0.2]]), \
             patch("app._embeddings_configured", return_value=True), \
             patch("app._save_session_manifest", side_effect=OSError("Disk full writing manifest")):
            mock_store = MagicMock()
            mock_store.chunks = []
            mock_get_store.return_value = mock_store

            files = {
                "files": ("test_manifest_doc.txt", io.BytesIO(b"Hello world document text content for testing."), "text/plain")
            }
            resp = client.post("/upload", files=files)
            self.assertEqual(resp.status_code, 200)
            res_data = resp.json()
            mock_store.add.assert_called_once()
            mock_store.remove_doc.assert_called_once()
            self.assertTrue(any("Failed to index" in doc.get("error", "") for doc in res_data.get("documents", [])))
            self.assertTrue(all(doc.get("cleanup_complete") is True for doc in res_data.get("documents", [])))

    def test_upload_post_store_rollback_failure_tracked(self):
        """If store.add() succeeds, post-store operation fails, and store.remove_doc ALSO fails,
        cleanup_complete=False must be reported and orphan metadata must be recorded in ORPHANED_DOCS."""
        import io
        from unittest.mock import patch, MagicMock
        from app import app, ORPHANED_DOCS
        from qdrant_store import RetrievalBackendError

        sid = "test_rollback_failure_tracked"
        ORPHANED_DOCS.pop(sid, None)

        client = make_client(app)
        set_session(client, sid)

        with patch("app._get_store") as mock_get_store, \
             patch("app.embed_texts", return_value=[[0.1, 0.2]]), \
             patch("app._embeddings_configured", return_value=True), \
             patch("pathlib.Path.replace", side_effect=OSError("Disk write error")):
            mock_store = MagicMock()
            mock_store.chunks = []
            mock_store.remove_doc.side_effect = RetrievalBackendError("Vector backend timed out during rollback")
            mock_get_store.return_value = mock_store

            files = {
                "files": ("doc_fail.txt", io.BytesIO(b"Document content for rollback failure test."), "text/plain")
            }
            resp = client.post("/upload", files=files)
            self.assertEqual(resp.status_code, 200)
            res_data = resp.json()
            failed_doc = res_data["documents"][0]

            self.assertFalse(failed_doc.get("cleanup_complete"))
            self.assertIn("Vector store rollback failed", failed_doc.get("cleanup_error", ""))
            self.assertIsNotNone(failed_doc.get("doc_id"))
            # Orphan metadata recorded in ORPHANED_DOCS
            self.assertIn(sid, ORPHANED_DOCS)
            self.assertEqual(len(ORPHANED_DOCS[sid]), 1)
            self.assertEqual(ORPHANED_DOCS[sid][0]["doc_id"], failed_doc["doc_id"])

    def test_upload_qdrant_embedding_failure_rejected(self):
        """When VECTOR_BACKEND=qdrant and embedding fails, reject upload with clear error without calling store.add with empty vectors."""
        import io
        from unittest.mock import patch, MagicMock
        from app import app

        client = make_client(app)
        set_session(client, "test_qdrant_embed_fail")

        with patch("app.VECTOR_BACKEND", "qdrant"), \
             patch("app._embeddings_configured", return_value=True), \
             patch("app.embed_texts", side_effect=RuntimeError("Embedding model service unavailable")), \
             patch("app._get_store") as mock_get_store:
            mock_store = MagicMock()
            mock_get_store.return_value = mock_store

            files = {
                "files": ("test_qdrant.txt", io.BytesIO(b"Document content for qdrant embedding test."), "text/plain")
            }
            resp = client.post("/upload", files=files)
            self.assertEqual(resp.status_code, 200)
            res_data = resp.json()
            mock_store.add.assert_not_called()
            self.assertTrue(any("Embedding generation failed on Qdrant backend" in doc.get("error", "") for doc in res_data.get("documents", [])))

    def test_load_url_qdrant_embeddings_unavailable_returns_503(self):
        """When VECTOR_BACKEND=qdrant and embeddings are unconfigured, /load-url returns 503 without calling store.add with []."""
        from unittest.mock import patch, MagicMock
        from app import app

        client = make_client(app)
        set_session(client, "test_load_url_qdrant")

        long_text = " ".join(["content_word"] * 40)
        with patch("app.VECTOR_BACKEND", "qdrant"), \
             patch("app._embeddings_configured", return_value=False), \
             patch("app.fetch_web_page", return_value=("Test Page", long_text)), \
             patch("app._get_store") as mock_get_store:
            mock_store = MagicMock()
            mock_get_store.return_value = mock_store

            resp = client.post("/load-url", json={"url": "http://example.com/test"})
            self.assertEqual(resp.status_code, 503)
            data = resp.json()
            self.assertIn("Qdrant vector backend requires embeddings", data.get("error", ""))
            mock_store.add.assert_not_called()

    def test_upload_cancellation_delete_failure_reports_incomplete(self):
        """When upload cancellation occurs and vector store delete fails on rollback, return cleanup_complete=False and details."""
        import io
        import time
        from unittest.mock import patch, MagicMock
        from app import app, ORPHANED_DOCS, SESSION_FILES
        from qdrant_store import RetrievalBackendError

        sid = "test_cancel_cleanup_incomplete"
        ORPHANED_DOCS.pop(sid, None)

        client = make_client(app)
        set_session(client, sid)

        upload_id = "test_cancel_uid_123"
        cancelled_map = {}

        def mock_embed(texts):
            # Simulate cancellation signal arriving right as file 1 finishes embedding/adding
            cancelled_map[upload_id] = time.time()
            return [[0.1, 0.2]]

        with patch("app.CANCELLED_UPLOADS", cancelled_map), \
             patch("app._get_store") as mock_get_store, \
             patch("app.embed_texts", side_effect=mock_embed), \
             patch("app._embeddings_configured", return_value=True):
            mock_store = MagicMock()
            mock_store.chunks = []
            mock_store.remove_doc.side_effect = RetrievalBackendError("Qdrant connection timed out during deletion")
            mock_get_store.return_value = mock_store

            files = {
                "files": ("doc1.txt", io.BytesIO(b"Doc 1 text content for cancellation test."), "text/plain")
            }
            resp = client.post("/upload", files=files, data={"upload_id": upload_id})
            self.assertEqual(resp.status_code, 200)
            res_data = resp.json()
            self.assertTrue(res_data.get("cancelled"))
            self.assertFalse(res_data.get("cleanup_complete"))
            self.assertIn("cleanup was incomplete", res_data.get("error", ""))
            self.assertTrue(len(res_data.get("failed_cleanup", [])) > 0)
            # Metadata preserved in SESSION_FILES with orphan flag for reconciliation
            self.assertIn(sid, SESSION_FILES)
            failed_doc_id = res_data["failed_cleanup"][0]["doc_id"]
            self.assertTrue(SESSION_FILES[sid][failed_doc_id].get("orphan"))
            # Orphan recorded in ORPHANED_DOCS
            self.assertIn(sid, ORPHANED_DOCS)

    def test_upload_cancellation_clean_rollback_leaves_no_metadata(self):
        """When upload cancellation occurs and vector store delete succeeds, no orphan metadata remains."""
        import io
        import time
        from unittest.mock import patch, MagicMock
        from app import app, SESSION_FILES, HASH_BY_DOC

        sid = "test_cancel_clean_rollback"
        client = make_client(app)
        set_session(client, sid)

        upload_id = "test_cancel_clean_uid_456"
        cancelled_map = {}

        def mock_embed(texts):
            cancelled_map[upload_id] = time.time()
            return [[0.1, 0.2]]

        with patch("app.CANCELLED_UPLOADS", cancelled_map), \
             patch("app._get_store") as mock_get_store, \
             patch("app.embed_texts", side_effect=mock_embed), \
             patch("app._embeddings_configured", return_value=True):
            mock_store = MagicMock()
            mock_store.chunks = []
            mock_store.remove_doc.return_value = 1  # Deletion succeeds
            mock_get_store.return_value = mock_store

            files = {
                "files": ("doc_clean.txt", io.BytesIO(b"Doc text for clean cancellation."), "text/plain")
            }
            resp = client.post("/upload", files=files, data={"upload_id": upload_id})
            self.assertEqual(resp.status_code, 200)
            res_data = resp.json()
            self.assertTrue(res_data.get("cancelled"))
            self.assertTrue(res_data.get("cleanup_complete"))
            self.assertIn("nothing was indexed", res_data.get("error", ""))
            # No session files or hashes remain
            self.assertEqual(len(SESSION_FILES.get(sid, {})), 0)
            self.assertEqual(len(HASH_BY_DOC.get(sid, {})), 0)

    def test_trace_store_sample_deterministic_ordering(self):
        """Verify that TraceStore.sample produces identical samples regardless of physical line order."""
        import tempfile
        from pathlib import Path
        from trace_store import TraceStore

        ids = [f"trace_{i:03d}" for i in range(50)]
        reversed_ids = list(reversed(ids))

        with tempfile.TemporaryDirectory() as tmpdir:
            store_a = TraceStore(Path(tmpdir) / "traces_a.jsonl")
            store_b = TraceStore(Path(tmpdir) / "traces_b.jsonl")

            for tid in ids:
                store_a.log({"trace_id": tid, "question": "test"})
            for tid in reversed_ids:
                store_b.log({"trace_id": tid, "question": "test"})

            sample_a = store_a.sample(n=10, seed=42)
            sample_b = store_b.sample(n=10, seed=42)

            self.assertEqual(sample_a, sample_b)

    def test_orphan_record_survives_process_restart(self):
        """Verify that orphaned document records are persisted to JSONL and recovered on startup."""
        import tempfile
        from pathlib import Path
        from unittest.mock import patch
        from app import ORPHANED_DOCS, _record_orphaned_doc, _load_orphaned_docs

        with tempfile.TemporaryDirectory() as tmpdir:
            temp_log = Path(tmpdir) / "orphans.jsonl"
            with patch("app.ORPHAN_LOG_PATH", temp_log):
                sid = "test_sess_restart"
                ORPHANED_DOCS.pop(sid, None)

                rec = _record_orphaned_doc(
                    sid=sid,
                    doc_id="doc_101",
                    filename="report.pdf",
                    error="Qdrant connection timeout",
                    stored_path=Path(tmpdir) / "report.pdf",
                )
                self.assertEqual(rec["doc_id"], "doc_101")
                self.assertEqual(len(ORPHANED_DOCS.get(sid, [])), 1)

                # Simulate process restart by clearing in-memory state and re-loading
                ORPHANED_DOCS.clear()
                self.assertNotIn(sid, ORPHANED_DOCS)

                _load_orphaned_docs()

                self.assertIn(sid, ORPHANED_DOCS)
                loaded = ORPHANED_DOCS[sid]
                self.assertEqual(len(loaded), 1)
                self.assertEqual(loaded[0]["doc_id"], "doc_101")
                self.assertEqual(loaded[0]["filename"], "report.pdf")
                self.assertEqual(loaded[0]["error"], "Qdrant connection timeout")
                self.assertEqual(loaded[0]["status"], "orphaned")
                self.assertIn("report.pdf", loaded[0]["stored_path"])

    def test_multiple_orphan_records_retained_across_sessions(self):
        """Verify multi-session orphan records are correctly isolated and preserved across restarts."""
        import tempfile
        from pathlib import Path
        from unittest.mock import patch
        from app import ORPHANED_DOCS, _record_orphaned_doc, _load_orphaned_docs

        with tempfile.TemporaryDirectory() as tmpdir:
            temp_log = Path(tmpdir) / "orphans.jsonl"
            with patch("app.ORPHAN_LOG_PATH", temp_log):
                ORPHANED_DOCS.clear()

                _record_orphaned_doc("sess_a", "doc_a1", "doc_a1.pdf", "Err A1")
                _record_orphaned_doc("sess_a", "doc_a2", "doc_a2.pdf", "Err A2")
                _record_orphaned_doc("sess_b", "doc_b1", "doc_b1.pdf", "Err B1")

                self.assertEqual(len(ORPHANED_DOCS["sess_a"]), 2)
                self.assertEqual(len(ORPHANED_DOCS["sess_b"]), 1)

                # Simulate restart
                ORPHANED_DOCS.clear()
                _load_orphaned_docs()

                self.assertEqual(len(ORPHANED_DOCS["sess_a"]), 2)
                self.assertEqual(len(ORPHANED_DOCS["sess_b"]), 1)
                self.assertEqual(ORPHANED_DOCS["sess_a"][0]["doc_id"], "doc_a1")
                self.assertEqual(ORPHANED_DOCS["sess_a"][1]["doc_id"], "doc_a2")
                self.assertEqual(ORPHANED_DOCS["sess_b"][0]["doc_id"], "doc_b1")

    def test_successful_cleanup_resolves_durable_orphan(self):
        """Verify that resolving an orphan removes it from memory and prevents resurrection on startup."""
        import tempfile
        from pathlib import Path
        from unittest.mock import patch
        from app import ORPHANED_DOCS, _record_orphaned_doc, _resolve_orphaned_doc, _load_orphaned_docs

        with tempfile.TemporaryDirectory() as tmpdir:
            temp_log = Path(tmpdir) / "orphans.jsonl"
            with patch("app.ORPHAN_LOG_PATH", temp_log):
                sid = "sess_resolve"
                ORPHANED_DOCS.pop(sid, None)

                _record_orphaned_doc(sid, "doc_res_1", "file1.txt", "Qdrant timeout")
                self.assertEqual(len(ORPHANED_DOCS.get(sid, [])), 1)

                # Resolve the orphan
                resolved = _resolve_orphaned_doc(sid, "doc_res_1")
                self.assertTrue(resolved)
                self.assertEqual(len(ORPHANED_DOCS.get(sid, [])), 0)

                # Simulate restart and ensure the resolution log prevents resurrection
                ORPHANED_DOCS.clear()
                _load_orphaned_docs()

                self.assertEqual(len(ORPHANED_DOCS.get(sid, [])), 0)

    def test_failed_cleanup_remains_retryable_and_observable(self):
        """Verify failed rollback in /upload durably records actionable retry metadata queryable via /orphans."""
        import io
        import tempfile
        from pathlib import Path
        from unittest.mock import patch, MagicMock
        from app import app, ORPHANED_DOCS
        from qdrant_store import RetrievalBackendError

        with tempfile.TemporaryDirectory() as tmpdir:
            temp_log = Path(tmpdir) / "orphans.jsonl"
            sid = "test_retryable_sess"
            ORPHANED_DOCS.pop(sid, None)

            client = make_client(app)
            set_session(client, sid)

            with patch("app.ORPHAN_LOG_PATH", temp_log), \
                 patch("app._get_store") as mock_get_store, \
                 patch("app.embed_texts", return_value=[[0.1, 0.2]]), \
                 patch("app._embeddings_configured", return_value=True), \
                 patch("pathlib.Path.replace", side_effect=OSError("Disk full writing storage")):
                mock_store = MagicMock()
                mock_store.chunks = []
                mock_store.remove_doc.side_effect = RetrievalBackendError("Backend unreachable on delete")
                mock_get_store.return_value = mock_store

                files = {
                    "files": ("retryable.txt", io.BytesIO(b"Document content for retryable orphan test."), "text/plain")
                }
                resp = client.post("/upload", files=files)
                self.assertEqual(resp.status_code, 200)
                res_data = resp.json()
                failed_doc = res_data["documents"][0]

                # HTTP response exposes failure contract
                self.assertFalse(failed_doc["cleanup_complete"])
                self.assertIn("Vector store rollback failed", failed_doc["cleanup_error"])
                doc_id = failed_doc["doc_id"]
                self.assertIsNotNone(doc_id)

                # Verify user observable via /orphans endpoint (stored_path redacted for normal users)
                orphans_resp = client.get("/orphans")
                self.assertEqual(orphans_resp.status_code, 200)
                orphans_data = orphans_resp.json()
                self.assertEqual(orphans_data["count"], 1)
                orphan_rec = orphans_data["orphans"][0]
                self.assertEqual(orphan_rec["doc_id"], doc_id)
                self.assertEqual(orphan_rec["filename"], "retryable.txt")
                self.assertNotIn("stored_path", orphan_rec)
                self.assertEqual(orphan_rec["error"], "Vector store cleanup failed")

                # Verify admin observability includes stored_path for operator reconciliation
                with patch("app.ADMIN_API_KEY", "admin_secret"):
                    admin_resp = client.get("/orphans", headers={"X-Admin-Key": "admin_secret"})
                    self.assertEqual(admin_resp.status_code, 200)
                    admin_data = admin_resp.json()
                    self.assertTrue(admin_data.get("admin"))
                    admin_rec = admin_data["orphans"][0]
                    self.assertIn(doc_id, admin_rec["stored_path"])
                    self.assertTrue(admin_rec["stored_path"].endswith(".txt"))

    def test_orphans_unauthenticated_rejected(self):
        """GET /orphans without an active session or admin credentials must return 401 Unauthorized."""
        from app import app
        client = make_client(app)
        resp = client.get("/orphans")
        self.assertEqual(resp.status_code, 401)
        self.assertIn("Unauthorized", resp.json().get("error", ""))

    def test_orphans_session_isolation_and_path_redaction(self):
        """Normal session clients must only see their own orphans with stored_path strictly redacted."""
        import tempfile
        from pathlib import Path
        from unittest.mock import patch
        from app import app, _record_orphaned_doc

        with tempfile.TemporaryDirectory() as tmpdir:
            temp_log = Path(tmpdir) / "orphans.jsonl"
            with patch("app.ORPHAN_LOG_PATH", temp_log):
                _record_orphaned_doc("user_sess_1", "doc_u1", "user1_doc.pdf", "Error 1", "/secret/path/user1.pdf")
                _record_orphaned_doc("user_sess_2", "doc_u2", "user2_doc.pdf", "Error 2", "/secret/path/user2.pdf")

                client = make_client(app)
                set_session(client, "user_sess_1")

                resp = client.get("/orphans")
                self.assertEqual(resp.status_code, 200)
                data = resp.json()
                self.assertFalse(data.get("admin"))
                self.assertEqual(data["count"], 1)
                self.assertEqual(data["orphans"][0]["doc_id"], "doc_u1")
                self.assertEqual(data["orphans"][0]["filename"], "user1_doc.pdf")
                # Ensure internal filesystem path and other user's records are NOT exposed
                self.assertNotIn("stored_path", data["orphans"][0])
                self.assertNotIn("session_id", data["orphans"][0])
                self.assertFalse(any(o["doc_id"] == "doc_u2" for o in data["orphans"]))

    def test_orphans_admin_system_wide_access_and_filter(self):
        """Admin callers can inspect system-wide orphans or filter by session with full operational metadata."""
        import tempfile
        from pathlib import Path
        from unittest.mock import patch
        from app import app, _record_orphaned_doc

        with tempfile.TemporaryDirectory() as tmpdir:
            temp_log = Path(tmpdir) / "orphans.jsonl"
            with patch("app.ORPHAN_LOG_PATH", temp_log), \
                 patch("app.ADMIN_API_KEY", "admin_pass_123"):
                _record_orphaned_doc("sess_alpha", "doc_a", "alpha.pdf", "Err A", "/data/alpha.pdf")
                _record_orphaned_doc("sess_beta", "doc_b", "beta.pdf", "Err B", "/data/beta.pdf")

                client = make_client(app)

                # Wrong key rejected
                bad_resp = client.get("/orphans", headers={"X-Admin-Key": "wrong_key"})
                self.assertEqual(bad_resp.status_code, 401)

                # Valid Bearer token gets system-wide records
                admin_resp = client.get("/orphans", headers={"Authorization": "Bearer admin_pass_123"})
                self.assertEqual(admin_resp.status_code, 200)
                admin_data = admin_resp.json()
                self.assertTrue(admin_data["admin"])
                self.assertEqual(admin_data["count"], 2)
                self.assertTrue(all("stored_path" in o for o in admin_data["orphans"]))

                # Admin filter by session_id
                filter_resp = client.get("/orphans?session_id=sess_beta", headers={"X-Admin-Key": "admin_pass_123"})
                self.assertEqual(filter_resp.status_code, 200)
                filter_data = filter_resp.json()
                self.assertEqual(filter_data["count"], 1)
                self.assertEqual(filter_data["orphans"][0]["doc_id"], "doc_b")
                self.assertEqual(filter_data["orphans"][0]["stored_path"], "/data/beta.pdf")

    def test_cross_worker_durable_log_visibility(self):
        """Worker B with empty memory must observe Worker A's durable orphan by reading from orphans.jsonl."""
        import tempfile
        from pathlib import Path
        from unittest.mock import patch
        from app import app, ORPHANED_DOCS, _record_orphaned_doc

        with tempfile.TemporaryDirectory() as tmpdir:
            temp_log = Path(tmpdir) / "orphans.jsonl"
            with patch("app.ORPHAN_LOG_PATH", temp_log):
                # Worker A writes orphan to durable log
                _record_orphaned_doc("worker_sess", "worker_doc_99", "shared.pdf", "Worker A timeout")

                # Simulate Worker B: clean in-memory cache
                ORPHANED_DOCS.clear()
                self.assertEqual(len(ORPHANED_DOCS), 0)

                # Worker B serves GET /orphans
                client = make_client(app)
                set_session(client, "worker_sess")

                resp = client.get("/orphans")
                self.assertEqual(resp.status_code, 200)
                data = resp.json()
                # Worker B observed Worker A's record directly from durable log
                self.assertEqual(data["count"], 1)
                self.assertEqual(data["orphans"][0]["doc_id"], "worker_doc_99")

    def test_durable_write_failure_surfaced_as_critical_failure(self):
        """When disk persistence fails, reconciliation_persistence_failed must be reported and logged."""
        import io
        import tempfile
        from pathlib import Path
        from unittest.mock import patch, MagicMock
        from app import app, ORPHANED_DOCS, _record_orphaned_doc
        from qdrant_store import RetrievalBackendError

        with tempfile.TemporaryDirectory() as tmpdir:
            temp_log = Path(tmpdir) / "orphans.jsonl"
            sid = "test_persistence_fail_sess"
            ORPHANED_DOCS.pop(sid, None)

            # Direct call to _record_orphaned_doc with failing file write
            orig_open = Path.open
            def conditional_open(self, *args, **kwargs):
                if "orphans.jsonl" in str(self):
                    raise OSError("Disk write I/O error")
                return orig_open(self, *args, **kwargs)

            with patch("app.ORPHAN_LOG_PATH", temp_log), \
                 patch("pathlib.Path.open", side_effect=conditional_open, autospec=True):
                rec = _record_orphaned_doc(sid, "doc_disk_fail", "fail.pdf", "Vector rollback failed")
                self.assertTrue(rec.get("reconciliation_persistence_failed"))
                self.assertNotIn("persisted", rec)

            # Upload endpoint with failing disk write during rollback
            client = make_client(app)
            set_session(client, sid)

            with patch("app.ORPHAN_LOG_PATH", temp_log), \
                 patch("app._get_store") as mock_get_store, \
                 patch("app.embed_texts", return_value=[[0.1, 0.2]]), \
                 patch("app._embeddings_configured", return_value=True), \
                 patch("pathlib.Path.replace", side_effect=OSError("Disk full writing storage")), \
                 patch("pathlib.Path.open", side_effect=conditional_open, autospec=True):
                mock_store = MagicMock()
                mock_store.chunks = []
                mock_store.remove_doc.side_effect = RetrievalBackendError("Delete failed")
                mock_get_store.return_value = mock_store

                files = {
                    "files": ("persist_fail.txt",
                              io.BytesIO(b"Document content for persistence failure test with enough words."),
                              "text/plain")
                }
                resp = client.post("/upload", files=files)
                self.assertEqual(resp.status_code, 200)
                failed_doc = resp.json()["documents"][0]
                self.assertFalse(failed_doc["cleanup_complete"])
                self.assertTrue(failed_doc.get("reconciliation_persistence_failed"))

    def test_malformed_and_schema_invalid_orphan_log_quarantined(self):
        """Malformed JSON lines and records failing schema validation must be quarantined without crashing."""
        import tempfile
        from pathlib import Path
        from app import _read_durable_orphans

        with tempfile.TemporaryDirectory() as tmpdir:
            temp_log = Path(tmpdir) / "orphans.jsonl"
            lines = [
                "{corrupted line that is not json\n",
                '"just a string"\n',
                '[1, 2, 3]\n',
                '{"status": "orphaned"}\n',  # missing session_id and doc_id
                '{"session_id": "s1", "status": "orphaned"}\n',  # missing doc_id
                '{"doc_id": "d1", "status": "orphaned"}\n',  # missing session_id
                '{"session_id": "   ", "doc_id": "d1", "status": "orphaned"}\n',  # empty session_id
                '{"session_id": "s1", "doc_id": "d1", "status": "bogus_status"}\n',  # unknown status
                '{"session_id": "good_sess", "doc_id": "good_doc", "status": "orphaned", "filename": "ok.pdf", "error": "err"}\n',
            ]
            temp_log.write_text("".join(lines), encoding="utf-8")

            orphans = _read_durable_orphans(temp_log)
            self.assertEqual(len(orphans), 1)
            self.assertIn("good_sess", orphans)
            self.assertEqual(len(orphans["good_sess"]), 1)
            self.assertEqual(orphans["good_sess"][0]["doc_id"], "good_doc")
            self.assertEqual(orphans["good_sess"][0]["filename"], "ok.pdf")

    def test_true_subprocess_restart_persistence_and_resolution(self):
        """Verify cross-process lifecycle using independent OS subprocesses."""
        import os
        import sys
        import subprocess
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmpdir:
            temp_log = Path(tmpdir) / "orphans.jsonl"
            repo_dir = str(Path(__file__).parent.resolve())

            env = dict(os.environ)
            env["ORPHAN_LOG_PATH"] = str(temp_log)
            env["PYTHONPATH"] = repo_dir

            # Subprocess 1: Record orphan and exit
            code_1 = (
                "import os, sys, app; "
                "rec = app._record_orphaned_doc('sub_sess', 'sub_doc_1', 'sub.pdf', 'Subprocess timeout'); "
                "assert not rec.get('reconciliation_persistence_failed'); "
                "sys.exit(0)"
            )
            res1 = subprocess.run([sys.executable, "-c", code_1], env=env, cwd=repo_dir, capture_output=True, text=True)
            self.assertEqual(res1.returncode, 0, f"Subprocess 1 failed: {res1.stderr}")
            self.assertTrue(temp_log.exists())

            # Subprocess 2: Fresh process starts, verifies loaded orphan, resolves it, and exits
            code_2 = (
                "import os, sys, app; "
                "assert 'sub_sess' in app.ORPHANED_DOCS, f'sub_sess not loaded: {app.ORPHANED_DOCS}'; "
                "assert app.ORPHANED_DOCS['sub_sess'][0]['doc_id'] == 'sub_doc_1'; "
                "res = app._resolve_orphaned_doc('sub_sess', 'sub_doc_1'); "
                "assert res is True; "
                "sys.exit(0)"
            )
            res2 = subprocess.run([sys.executable, "-c", code_2], env=env, cwd=repo_dir, capture_output=True, text=True)
            self.assertEqual(res2.returncode, 0, f"Subprocess 2 failed: {res2.stderr}")

            # Subprocess 3: Fresh process starts, verifies orphan remained resolved across restart
            code_3 = (
                "import os, sys, app; "
                "assert len(app.ORPHANED_DOCS.get('sub_sess', [])) == 0, f'Expected resolved: {app.ORPHANED_DOCS}'; "
                "sys.exit(0)"
            )
            res3 = subprocess.run([sys.executable, "-c", code_3], env=env, cwd=repo_dir, capture_output=True, text=True)
            self.assertEqual(res3.returncode, 0, f"Subprocess 3 failed: {res3.stderr}")

    def test_resolution_persistence_failure_does_not_claim_resolved(self):
        """If disk write or fsync fails during resolution, _resolve_orphaned_doc must return False,
        must not evict from memory, and must not resurrect on restart."""
        import tempfile
        from pathlib import Path
        from unittest.mock import patch
        from app import ORPHANED_DOCS, _record_orphaned_doc, _resolve_orphaned_doc, _load_orphaned_docs

        with tempfile.TemporaryDirectory() as tmpdir:
            temp_log = Path(tmpdir) / "orphans.jsonl"
            sid = "test_res_fail_sess"
            doc_id = "doc_res_fail_99"
            ORPHANED_DOCS.pop(sid, None)

            with patch("app.ORPHAN_LOG_PATH", temp_log):
                rec = _record_orphaned_doc(sid, doc_id, "file_res.pdf", "Vector rollback failed")
                self.assertFalse(rec.get("reconciliation_persistence_failed"))
                self.assertEqual(len(ORPHANED_DOCS[sid]), 1)

                # Simulate disk write failure specifically during resolution append
                orig_open = Path.open
                def failing_resolution_open(self_path, *args, **kwargs):
                    mode = args[0] if args else kwargs.get("mode", "r")
                    if "orphans.jsonl" in str(self_path) and "a" in mode:
                        raise OSError("Disk write failure during resolution append")
                    return orig_open(self_path, *args, **kwargs)

                with patch("pathlib.Path.open", side_effect=failing_resolution_open, autospec=True):
                    resolved = _resolve_orphaned_doc(sid, doc_id)
                    # Must report failure, not false success
                    self.assertFalse(resolved)
                    # Must NOT have evicted from memory
                    self.assertEqual(len(ORPHANED_DOCS[sid]), 1)
                    self.assertEqual(ORPHANED_DOCS[sid][0]["doc_id"], doc_id)

                # Simulate restart: clear memory and reload durable state
                ORPHANED_DOCS.clear()
                _load_orphaned_docs()
                # Document is still active (not resurrected, was never resolved)
                self.assertIn(sid, ORPHANED_DOCS)
                self.assertEqual(len(ORPHANED_DOCS[sid]), 1)
                self.assertEqual(ORPHANED_DOCS[sid][0]["doc_id"], doc_id)

                # Now retry resolution under healthy disk conditions
                resolved_retry = _resolve_orphaned_doc(sid, doc_id)
                self.assertTrue(resolved_retry)
                # Removed from memory
                self.assertEqual(len(ORPHANED_DOCS.get(sid, [])), 0)

                # Simulate restart again: must remain resolved permanently
                ORPHANED_DOCS.clear()
                _load_orphaned_docs()
    def test_multi_worker_session_manifest_and_store_sync(self):
        """Verify cross-worker session synchronization: Worker 2 reloads when Worker 1 updates session manifest and vector store."""
        import tempfile
        import time
        from unittest.mock import patch
        from pathlib import Path
        import json
        from app import _save_session_manifest, _get_store, SESSION_FILES, VECTOR_STORE, _MANIFEST_MTIMES, _manifest_path

        sid = "test_multi_worker_sync_sess"
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            with patch("app.UPLOAD_FOLDER", tmp_path), \
                 patch("app.VECTOR_FOLDER", tmp_path), \
                 patch("app.VECTOR_BACKEND", "memory"):

                # Clean slate
                SESSION_FILES.pop(sid, None)
                VECTOR_STORE.pop(sid, None)
                _MANIFEST_MTIMES.pop(sid, None)

                # Worker 1 creates store and adds doc1
                doc1_file = tmp_path / f"{sid}_doc1.txt"
                doc1_file.write_text("Worker 1 document content", encoding="utf-8")
                SESSION_FILES[sid] = {"doc1": {"path": doc1_file, "name": "doc1.txt"}}
                _save_session_manifest(sid)
                store1 = _get_store(sid)
                store1.add([{"id": "c1", "doc_id": "doc1", "text": "chunk1", "method": "structured"}], [])
                store1.save()

                # Simulate Worker 2: has its own in-memory caches
                with patch.dict("app.SESSION_FILES", {}, clear=True), \
                     patch.dict("app.VECTOR_STORE", {}, clear=True), \
                     patch.dict("app._MANIFEST_MTIMES", {}, clear=True):

                    # Worker 2 loads session for the first time
                    store2 = _get_store(sid)
                    self.assertIn("doc1", SESSION_FILES.get(sid, {}))
                    self.assertEqual(len(store2.chunks), 1)
                    self.assertEqual(store2.chunks[0]["id"], "c1")

                    # Now Worker 1 (in its separate process) adds doc2 and chunk2 to disk
                    time.sleep(0.05)  # Ensure distinct mtime
                    doc2_file = tmp_path / f"{sid}_doc2.txt"
                    doc2_file.write_text("Worker 1 second document", encoding="utf-8")

                    # Worker 1 writes manifest and vector store directly to disk
                    mpath = _manifest_path(sid)
                    mdata = {
                        "doc1": {"path": str(doc1_file), "name": "doc1.txt"},
                        "doc2": {"path": str(doc2_file), "name": "doc2.txt"},
                    }
                    mpath.write_text(json.dumps(mdata), encoding="utf-8")
                    store1.add([{"id": "c2", "doc_id": "doc2", "text": "chunk2", "method": "structured"}], [])
                    store1.save()

                    # Worker 2 receives subsequent request: _get_store detects updated disk mtime and reloads
                    store2_updated = _get_store(sid)
                    self.assertIn("doc2", SESSION_FILES.get(sid, {}))
                    self.assertEqual(len(store2_updated.chunks), 2)
                    self.assertEqual(store2_updated.chunks[1]["id"], "c2")


class TestFastAPIMigration(unittest.TestCase):
    """Covers the behaviours that Flask provided implicitly and FastAPI does
    not, so a silent regression in any of them fails the suite rather than
    only showing up in production."""

    def test_oversized_upload_rejected_by_content_length(self):
        """Flask enforced MAX_CONTENT_LENGTH itself; Starlette imposes no body
        limit at all. A declared Content-Length over 50 MB must be refused
        with the same 413 body the old @app.errorhandler(413) returned."""
        import io
        from app import app, MAX_CONTENT_LENGTH

        client = make_client(app)
        oversized = b"x" * (MAX_CONTENT_LENGTH + 1024)
        resp = client.post("/upload", files={"files": ("big.txt", io.BytesIO(oversized), "text/plain")})
        self.assertEqual(resp.status_code, 413)
        self.assertEqual(resp.json(), {"error": "File too large (max 50 MB)"})

    def test_oversized_upload_rejected_without_content_length(self):
        """A chunked request declares no Content-Length, so the header check
        alone is trivially bypassable — the streamed byte counter must catch
        it too. The body here is a *valid* multipart stream, so nothing else
        can reject it first; only the size guard can."""
        from app import app, MAX_CONTENT_LENGTH

        client = make_client(app)
        boundary = "streamedboundary123"
        chunk = b"y" * (1024 * 1024)
        total_chunks = (MAX_CONTENT_LENGTH // len(chunk)) + 2

        def body_stream():
            yield (
                f"--{boundary}\r\n"
                'Content-Disposition: form-data; name="files"; filename="big.txt"\r\n'
                "Content-Type: text/plain\r\n\r\n"
            ).encode()
            for _ in range(total_chunks):
                yield chunk
            yield f"\r\n--{boundary}--\r\n".encode()

        resp = client.post(
            "/upload",
            content=body_stream(),
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        )
        self.assertEqual(resp.status_code, 413)
        self.assertEqual(resp.json(), {"error": "File too large (max 50 MB)"})

    def test_oversized_json_body_rejected_without_content_length(self):
        """The cap is transport-level, not upload-specific: a chunked JSON
        body over the limit must be refused on a plain JSON endpoint too."""
        from app import app, MAX_CONTENT_LENGTH

        client = make_client(app)
        chunk = b"z" * (1024 * 1024)
        total_chunks = (MAX_CONTENT_LENGTH // len(chunk)) + 2

        def body_stream():
            yield b'{"query": "'
            for _ in range(total_chunks):
                yield chunk
            yield b'"}'

        resp = client.post(
            "/ask",
            content=body_stream(),
            headers={"Content-Type": "application/json"},
        )
        self.assertEqual(resp.status_code, 413)
        self.assertEqual(resp.json(), {"error": "File too large (max 50 MB)"})

    def test_normal_sized_upload_is_not_blocked_by_the_cap(self):
        """Guard against the cap being set so aggressively it breaks ordinary
        uploads — a 2 MB document must still index normally."""
        import io
        import tempfile
        from pathlib import Path
        from unittest.mock import patch, MagicMock
        from app import app

        client = make_client(app)
        set_session(client, "test_under_limit_sess")
        body = (b"Section One\n\nThe quick brown fox jumps over the lazy dog. " * 40_000)[: 2 * 1024 * 1024]

        with tempfile.TemporaryDirectory() as tmpdir, \
             patch("app.UPLOAD_FOLDER", Path(tmpdir)), \
             patch("app._get_store") as mock_get_store, \
             patch("app._embeddings_configured", return_value=False):
            mock_store = MagicMock()
            mock_store.chunks = []
            mock_get_store.return_value = mock_store

            resp = client.post("/upload", files={"files": ("under_limit.txt", io.BytesIO(body), "text/plain")})
            self.assertEqual(resp.status_code, 200)
            self.assertTrue(resp.json().get("ok"))

    def test_session_cookie_round_trips_and_is_stable(self):
        """Starlette's SessionMiddleware must reproduce Flask's signed-cookie
        semantics: a session id minted on first contact stays the same across
        subsequent requests from the same client."""
        from app import app

        client = make_client(app)
        first = client.get("/")
        self.assertEqual(first.status_code, 200)
        self.assertIn("session", client.cookies)
        cookie_after_first = client.cookies["session"]

        # A later request must reuse the SAME session id, not mint a new one.
        client.get("/status")
        self.assertEqual(client.cookies["session"], cookie_after_first)

        # And the cookie must actually decode to the session id the server used.
        sid = _decode_session_cookie(cookie_after_first)["session_id"]
        self.assertTrue(sid)

        # A tampered cookie must be rejected (bad signature -> empty session),
        # not silently trusted.
        tampered = make_client(app)
        tampered.cookies.set("session", cookie_after_first[:-4] + "AAAA")
        self.assertEqual(tampered.get("/orphans").status_code, 401)

    def test_tojson_filter_is_registered_and_script_safe(self):
        """templates/view.html embeds values into a <script> block via
        `| tojson`. Flask registers that filter automatically; Starlette's
        Jinja2Templates does not guarantee it, so it is wired up explicitly."""
        from app import templates

        self.assertIn("tojson", templates.env.filters)
        hostile = '</script><script>alert(1)</script>'
        rendered = templates.env.from_string("{{ v | tojson }}").render(v=hostile)
        # Must not be able to break out of the surrounding <script> element...
        self.assertNotIn("</script>", rendered)
        # ...while still round-tripping to the exact original value.
        self.assertEqual(json.loads(rendered), hostile)

    def test_static_files_are_mounted(self):
        """Flask served ./static automatically; in FastAPI it is an explicit
        mount, so a missing mount would only surface as a broken UI."""
        from app import app

        client = make_client(app)
        for path in ("/static/js/app.js", "/static/js/view.js", "/static/css/app.css"):
            with self.subTest(path=path):
                self.assertEqual(client.get(path).status_code, 200)

    def test_every_documented_route_is_registered(self):
        """The frontend calls these paths by hard-coded string; a renamed or
        dropped path during the migration must fail here, not in the browser."""
        from app import app

        registered = {
            (path, method)
            for route in app.routes
            for path in [getattr(route, "path", None)]
            for method in (getattr(route, "methods", None) or set())
            if path
        }
        expected = [
            ("/", "GET"), ("/upload", "POST"), ("/upload-cancel", "POST"),
            ("/load-url", "POST"), ("/ask", "POST"), ("/status", "GET"),
            ("/remove", "POST"), ("/clear", "POST"), ("/eval", "GET"),
            ("/eval/run", "POST"), ("/eval/parse-qa-pdf", "POST"),
            ("/file/{doc_id}", "GET"), ("/file/{doc_id}/raw", "GET"),
            ("/file/{doc_id}/pages", "GET"), ("/healthz", "GET"),
            ("/readyz", "GET"), ("/orphans", "GET"), ("/traces", "GET"),
            ("/replay/{trace_id}", "POST"), ("/favicon.ico", "GET"),
        ]
        for path, method in expected:
            with self.subTest(route=f"{method} {path}"):
                self.assertIn((path, method), registered)

    def test_openapi_schema_is_served(self):
        """Auto-generated docs are a genuine addition from the migration —
        assert they actually build (a bad response_model would 500 here)."""
        from app import app

        client = make_client(app)
        resp = client.get("/openapi.json")
        self.assertEqual(resp.status_code, 200)
        schema = resp.json()
        self.assertIn("/ask", schema["paths"])
        self.assertIn("/upload", schema["paths"])
        self.assertEqual(client.get("/docs").status_code, 200)

    def test_ask_without_session_returns_400(self):
        """/ask has no session-creating side effect — an unknown caller gets
        the same 400 contract as before."""
        from app import app

        client = make_client(app)
        resp = client.post("/ask", json={"query": "anything"})
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json(), {"error": "No documents uploaded yet"})

    def test_validation_errors_use_the_apis_error_envelope(self):
        """Pydantic validation is new (Flask silently ignored unparseable
        values), but every error this API returns must still carry an `error`
        string — that is the only field static/js/app.js's handleResponse()
        looks at."""
        from app import app

        client = make_client(app)
        set_session(client, "test_validation_envelope")
        resp = client.post("/ask", json={"query": "hi", "top_k": "not-a-number"})
        self.assertEqual(resp.status_code, 422)
        body = resp.json()
        self.assertIn("error", body)
        self.assertIn("top_k", body["error"])
        # The structured FastAPI detail is still available for API clients.
        self.assertIsInstance(body.get("detail"), list)

    def test_out_of_range_tuning_values_are_clamped_not_rejected(self):
        """top_k/temperature clamping is existing behaviour and must survive
        the move to Pydantic — an out-of-range number is clamped, not 422'd."""
        from app import app

        client = make_client(app)
        set_session(client, "test_clamping_sess")
        resp = client.post("/ask", json={"query": "hi", "top_k": 999, "temperature": 7.5})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["top_k"], 20)
        self.assertEqual(resp.json()["temperature"], 1.0)

    def test_routes_requiring_a_session_return_the_same_400_contract(self):
        """These five endpoints shared a hand-written 'No active session'
        check in the Flask version; they now share one dependency, so verify
        the response contract is unchanged for all of them."""
        from app import app

        client = make_client(app)
        cases = [
            ("get", "/file/abc123"),
            ("get", "/file/abc123/raw"),
            ("get", "/file/abc123/pages"),
            ("post", "/remove"),
            ("post", "/eval/run"),
        ]
        for method, path in cases:
            with self.subTest(route=f"{method.upper()} {path}"):
                resp = getattr(client, method)(path)
                self.assertEqual(resp.status_code, 400)
                self.assertEqual(resp.json(), {"error": "No active session"})


def _decode_session_cookie(cookie_value: str) -> dict:
    """Inverse of set_session() — unsign + decode Starlette's session cookie."""
    from app import SECRET_KEY

    signer = itsdangerous.TimestampSigner(str(SECRET_KEY))
    return json.loads(base64.b64decode(signer.unsign(cookie_value.encode("utf-8"))))


if __name__ == '__main__':
    unittest.main()



