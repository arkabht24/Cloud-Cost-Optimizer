"""Tests for the deterministic scope gate before RAG retrieval or generation."""

import unittest
from unittest.mock import patch

from rag.query_policy import assess_query_policy
from rag.service import analyze_resources


class QueryPolicyTests(unittest.TestCase):
    def test_deletion_request_is_rejected_before_rag_work(self):
        result = assess_query_policy("Can we delete analytics-vm-01-data today?")
        self.assertFalse(result["allowed"])
        self.assertEqual(result["reason_code"], "deletion_not_supported")

    def test_non_cost_question_is_rejected(self):
        result = assess_query_policy("What is the capital of India?")
        self.assertFalse(result["allowed"])
        self.assertEqual(result["reason_code"], "outside_cost_optimization_scope")

    def test_rightsizing_question_is_allowed(self):
        self.assertTrue(assess_query_policy("Can we downsize retry-lab-vm-01 now?")["allowed"])

    @patch("rag.service.get_llm_response")
    @patch("rag.service.fetch_all_resources")
    def test_rejected_request_does_not_fetch_resources_or_call_llm(self, fetch_resources, get_llm):
        result = analyze_resources("Can we delete analytics-vm-01-data today?")

        self.assertEqual(result["scope"]["response_mode"], "query_policy_rejection")
        self.assertEqual(result["application_usage"]["generation_calls"], 0)
        self.assertIn("does not provide deletion or removal guidance", result["answer"])
        fetch_resources.assert_not_called()
        get_llm.assert_not_called()


if __name__ == "__main__":
    unittest.main()
