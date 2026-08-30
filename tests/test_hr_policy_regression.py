"""Offline end-to-end regression checks using the supplied HR policy."""

import io
import os
import tempfile
import unittest
from pathlib import Path

# Keep the regression suite deterministic and independent of cloud services.
os.environ["VECTOR_BACKEND"] = "memory"
os.environ["GEMINI_API_KEY"] = ""

import app  # noqa: E402


PROJECT_ROOT = Path(__file__).resolve().parents[1]
HR_POLICY = PROJECT_ROOT / "WEEKLY_RAG_TASK" / "HRPolicy.pdf"


class HRPolicyRegressionTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        temp_path = Path(self.temp_dir.name)
        self.original_upload_folder = app.UPLOAD_FOLDER
        self.original_vector_folder = app.VECTOR_FOLDER
        self.original_trace_dir = app.TRACE_LOG_DIR
        self.original_trace_file = app.TRACE_LOG_FILE
        app.UPLOAD_FOLDER = temp_path / "uploads"
        app.VECTOR_FOLDER = temp_path / "vectorstore"
        app.TRACE_LOG_DIR = temp_path / "traces"
        app.TRACE_LOG_FILE = app.TRACE_LOG_DIR / "hr_traces.jsonl"
        for directory in (app.UPLOAD_FOLDER, app.VECTOR_FOLDER, app.TRACE_LOG_DIR):
            directory.mkdir()
        app.VECTOR_STORE.clear()
        app.SESSION_FILES.clear()
        app.SESSION_ACCESS.clear()
        app.HASH_STORE.clear()
        app.HASH_BY_DOC.clear()
        app.CHUNK_COUNTS.clear()
        self.client = app.app.test_client()

    def tearDown(self):
        app.VECTOR_STORE.clear()
        app.SESSION_FILES.clear()
        app.SESSION_ACCESS.clear()
        app.HASH_STORE.clear()
        app.HASH_BY_DOC.clear()
        app.CHUNK_COUNTS.clear()
        app.UPLOAD_FOLDER = self.original_upload_folder
        app.VECTOR_FOLDER = self.original_vector_folder
        app.TRACE_LOG_DIR = self.original_trace_dir
        app.TRACE_LOG_FILE = self.original_trace_file
        self.temp_dir.cleanup()

    def test_hr_policy_upload_search_and_failure_tracing(self):
        with HR_POLICY.open("rb") as policy:
            upload = self.client.post(
                "/upload",
                data={"files": (io.BytesIO(policy.read()), "HRPolicy.pdf"), "chunk_mode": "structured"},
                content_type="multipart/form-data",
            )
        self.assertEqual(upload.status_code, 200, upload.get_json())
        self.assertTrue(upload.get_json()["ok"])

        status = self.client.get("/status").get_json()
        self.assertEqual(status["documents"][0]["filename"], "HRPolicy.pdf")
        self.assertGreater(status["total_chunks"], 0)

        answer = self.client.post("/ask", json={"query": "What is leave without pay?", "chunk_mode": "structured"})
        self.assertEqual(answer.status_code, 200, answer.get_json())
        self.assertTrue(answer.get_json()["found"], answer.get_json())
        self.assertIn("leave", answer.get_json()["answer"].lower())

        miss = self.client.post("/ask", json={"query": "What is the interstellar travel policy?", "chunk_mode": "structured"})
        self.assertEqual(miss.status_code, 200, miss.get_json())
        self.assertFalse(miss.get_json()["found"], miss.get_json())

        traces = app.TRACE_LOG_FILE.read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(traces), 2)
        self.assertIn('"failure_mode": "SUCCESS"', traces[0])
        self.assertIn('"failure_mode": "RETRIEVAL_FAILURE"', traces[1])


if __name__ == "__main__":
    unittest.main(verbosity=2)
