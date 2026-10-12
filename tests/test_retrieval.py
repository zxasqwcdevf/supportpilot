import unittest
from supportpilot.retrieval import retrieve, fuse, keyword_matches
from unittest.mock import patch
from scripts.evaluate_retrieval import metrics

DOCS = [{"id": "a", "title": "계정", "keywords": ["비밀번호"], "text": "가입 이메일로 링크를 전송합니다."}, {"id": "b", "title": "팀", "keywords": ["초대"], "text": "동료 초대 방법"}]


class RetrievalTests(unittest.TestCase):
    def test_bm25_recovers_text_without_keyword(self):
        self.assertEqual(retrieve("가입 이메일 링크", DOCS, "keyword"), [])
        self.assertEqual(retrieve("가입 이메일 링크", DOCS, "bm25")[0]["document"]["id"], "a")

    def test_hybrid_dense_only_and_cutoff(self):
        self.assertEqual(retrieve("unknown", DOCS, "hybrid", dense=[.9, .1])[0]["document"]["id"], "a")
        self.assertEqual(retrieve("unknown", DOCS, "hybrid", dense=[.2, .3]), [])

    def test_rrf_combines_ranks(self):
        ranking, scores = fuse([[0, 1], [1]])
        self.assertEqual(ranking[0], 1)

    def test_positive_and_negative_metrics_separate(self):
        self.assertEqual(metrics(["a", "b"], ["b"])["recall_at_3"], .5)
        self.assertFalse(metrics([], ["a"])["negative_abstention"])

    def test_keyword_boundary_and_particle(self):
        self.assertFalse(keyword_matches("프로젝트 CSV 저장", "프로"))
        self.assertTrue(keyword_matches("프로는 얼마인가요", "프로"))
        self.assertTrue(keyword_matches("환불해주세요", "환불"))

    def test_lexical_only_noise_cannot_bypass_gate(self):
        with patch("supportpilot.retrieval.bm25", return_value=[1.03, 1.48]):
            self.assertEqual(retrieve("unknown", DOCS, "hybrid", dense=[.79, .78]), [])

    def test_rrf_tie_uses_dense_score(self):
        with patch("supportpilot.retrieval.bm25", return_value=[4.26, 4.07]):
            hits = retrieve("security", DOCS, "hybrid", dense=[.86, .884])
        self.assertEqual(hits[0]["document"]["id"], "b")

    def test_strong_lexical_match_survives_low_dense(self):
        with patch("supportpilot.retrieval.bm25", return_value=[5, .5]):
            hits = retrieve("exact", DOCS, "hybrid", dense=[.7, .7])
        self.assertEqual([hit["document"]["id"] for hit in hits], ["a"])
