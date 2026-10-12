import unittest
from unittest.mock import patch
from supportpilot.generation import generate, verify_direct_evidence, source_snippets

DOCS = [{"id": "plan-v1", "title": "요금제", "version": "1", "text": "Pro 요금제는 월 29,000원이며 최대 5명의 팀원을 지원합니다."}]


class DirectEvidenceTests(unittest.TestCase):
    def test_quota_unsupported_skips_generation(self):
        with patch("supportpilot.generation.request_completion", side_effect=[
            {"has_answering_policy": True, "needs_user_facts": False, "supporting_ids": ["plan-v1"], "missing_fields": []},
            {"directly_supported": False},
        ]) as request:
            result = generate("Pro의 월간 API 호출 제한은 몇 회인가요?", DOCS)
        self.assertEqual(result["reason"], "no_answering_policy")
        self.assertEqual(result["citations"], [])
        self.assertEqual(request.call_count, 2)
        self.assertEqual(result["model_calls"], 2)

    def test_invented_snippet_rejected(self):
        with patch("supportpilot.generation.request_completion", return_value={"directly_supported": True, "snippet_ids": ["plan-v1:s999"]}):
            with self.assertRaises(ValueError):
                verify_direct_evidence("API 호출 제한", DOCS, {})

    def test_supported_without_snippet_rejected(self):
        with patch("supportpilot.generation.request_completion", return_value={"directly_supported": True, "snippet_ids": []}):
            with self.assertRaises(ValueError):
                verify_direct_evidence("월 가격", DOCS, {})

    def test_verifier_not_given_previous_verdict(self):
        with patch("supportpilot.generation.request_completion", return_value={"directly_supported": False}) as request:
            verify_direct_evidence("API 호출 제한", DOCS, {"decision": "answerable"})
        self.assertNotIn('"decision"', request.call_args.args[0][1]["content"])

    def test_selected_quote_copied_from_source(self):
        with patch("supportpilot.generation.request_completion", return_value={"directly_supported": True, "snippet_ids": ["plan-v1:s0"]}):
            result = verify_direct_evidence("팀원 수", DOCS, {})
        self.assertEqual(result["evidence"][0]["quote"], DOCS[0]["text"])

    def test_snippet_offsets_preserve_original_whitespace(self):
        docs = [{"id": "p", "title": "policy", "version": "1", "text": "  최대  5명입니다.  링크는 30분 유효합니다."}]
        snippets = source_snippets(docs)
        self.assertEqual(len(snippets), 2)
        for snippet in snippets:
            self.assertEqual(docs[0]["text"][snippet["start"]:snippet["end"]], snippet["quote"])

    def test_false_premise_with_selected_policy_can_answer(self):
        docs = [{"id": "password", "title": "policy", "version": "1", "text": "링크는 30분 유효합니다."}]
        with patch("supportpilot.generation.request_completion", side_effect=[
            {"has_answering_policy": True, "needs_user_facts": False, "supporting_ids": ["password"], "missing_fields": []},
            {"directly_supported": True, "snippet_ids": ["password:s0"]},
            {"status": "draft", "answer": "30분 유효하므로 한 시간 뒤에는 사용할 수 없습니다.", "evidence": [{"id": "password", "quote": "링크는 30분 유효합니다."}]},
        ]):
            self.assertEqual(generate("한 시간 뒤 쓸 수 있나요?", docs)["status"], "draft")
