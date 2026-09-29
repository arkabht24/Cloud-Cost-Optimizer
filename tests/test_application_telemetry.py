"""Offline checks for optional application usage and framework cost behavior."""

import unittest

from evals.pricing import calculate_cost
from evals.telemetry import collect_application_usage


class ApplicationTelemetryTests(unittest.TestCase):
    def test_local_ollama_usage_has_zero_provider_charge(self):
        usage = collect_application_usage({
            "application_usage": {
                "provider": "ollama",
                "deployment": "local",
                "model": "llama3.2:latest",
                "input_tokens": 10,
                "output_tokens": 4,
                "total_tokens": 14,
                "generation_calls": 1,
            }
        })
        self.assertEqual(usage["status"], "available")
        cost = calculate_cost(usage)
        self.assertEqual(cost["status"], "local_model_no_provider_charge")
        self.assertEqual(cost["provider_inference_cost"], 0.0)

    def test_missing_usage_does_not_fail_the_evaluation(self):
        usage = collect_application_usage({"answer": "answer"})
        self.assertEqual(usage["status"], "missing")
        self.assertIn("No application usage telemetry", usage["message"])
        self.assertEqual(calculate_cost(usage)["provider_inference_cost"], None)

    def test_inconsistent_tokens_are_marked_partial(self):
        usage = collect_application_usage({
            "application_usage": {
                "provider": "gemini",
                "deployment": "api",
                "model": "gemini-test",
                "input_tokens": 10,
                "output_tokens": 4,
                "total_tokens": 99,
            }
        })
        self.assertEqual(usage["status"], "partial")
        self.assertIn("inconsistent", usage["message"])
        self.assertEqual(calculate_cost(usage)["provider_inference_cost"], None)

    def test_api_cost_uses_approved_catalog_rate(self):
        cost = calculate_cost({
            "status": "available", "provider": "gemini", "deployment": "api",
            "model": "gemini-3.6-flash", "input_tokens": 1_000_000, "output_tokens": 1_000_000,
        })
        self.assertEqual(cost["provider_inference_cost"], 4.5)
        self.assertEqual(cost["pricing_tier"], "paid")
        self.assertEqual(cost["pricing_verified_at"], "2026-09-25")


if __name__ == "__main__":
    unittest.main()
