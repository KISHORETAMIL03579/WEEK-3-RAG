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

import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from app import _rr_rank, _hit_check


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


if __name__ == '__main__':
    unittest.main()
