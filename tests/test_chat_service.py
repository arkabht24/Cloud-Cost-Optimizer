"""Tests for conversational dashboard FinOps assistance."""

import unittest
from unittest.mock import patch

from rag.chat_service import answer_finops_question


class ChatServiceTests(unittest.TestCase):
    @patch("rag.chat_service.get_llm_response")
    @patch("rag.chat_service.retrieve_best_practice_contexts", return_value=[])
    @patch("rag.chat_service.build_dashboard_data")
    def test_selected_resource_cost_and_run_rate_are_grounded(self, build_dashboard, _retrieve, llm):
        build_dashboard.return_value = {
            "resources": [{
                "name": "sql-example", "type": "Microsoft.Sql/servers", "region": "eastus", "sku": "Standard",
                "cost": {"last_30_days": 300.0, "currency": "USD"},
                "performance": {"metrics": {"DTU p95": "70%"}},
            }]
        }
        llm.return_value = {"text": "Review demand before changing database capacity.", "usage": {"model": "test"}}

        result = answer_finops_question(
            "What is its cost and projected next-week billing?", "demo-cost-lab", context_resource="sql-example"
        )

        self.assertIn("USD 300.00", result["answer"])
        self.assertIn("USD 70.00", result["answer"])
        self.assertIn("not an Azure invoice forecast", result["answer"])
        self.assertIn("FinOps guidance", result["answer"])

    @patch("rag.chat_service.get_llm_response")
    @patch("rag.chat_service.retrieve_best_practice_contexts", return_value=[])
    @patch("rag.chat_service.build_dashboard_data")
    def test_newly_named_resource_wins_over_stale_selected_context(self, build_dashboard, _retrieve, llm):
        build_dashboard.return_value = {
            "resources": [
                {"name": "sql-example", "type": "Microsoft.Sql/servers", "region": "eastus", "sku": None, "cost": {"last_30_days": 300.0, "currency": "USD"}, "performance": {"metrics": {}}},
                {"name": "web-example", "type": "Microsoft.Compute/virtualMachines", "region": "eastus", "sku": "Standard_D4s_v5", "cost": {"last_30_days": 600.0, "currency": "USD"}, "performance": {"metrics": {}}},
            ]
        }
        llm.return_value = {"text": "Use the supplied resource facts.", "usage": {"model": "test"}}

        result = answer_finops_question(
            "What is web-example and what is its next-week run rate?", "demo-cost-lab", context_resource="sql-example"
        )

        self.assertIn("Resource: web-example", result["answer"])
        self.assertIn("USD 600.00", result["answer"])
        self.assertIn("USD 140.00", result["answer"])

    @patch("rag.chat_service.build_dashboard_data")
    def test_deletion_question_does_not_load_dashboard_or_call_model(self, build_dashboard):
        result = answer_finops_question("Can we remove this public IP?", "demo-cost-lab")
        self.assertIn("does not provide deletion or removal guidance", result["answer"])
        build_dashboard.assert_not_called()


if __name__ == "__main__":
    unittest.main()
