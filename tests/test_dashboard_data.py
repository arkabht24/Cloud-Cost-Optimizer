"""Checks for the normalized dashboard payload used by the React client."""

import unittest

from azure.dashboard_data import build_dashboard_data


class DashboardDataTests(unittest.TestCase):
    def test_demo_dashboard_has_resource_cost_and_performance_data(self):
        dashboard = build_dashboard_data("demo-cost-lab", days=30)

        self.assertEqual(dashboard["source"], "demo")
        self.assertEqual(dashboard["availability"]["inventory"], "available")
        self.assertEqual(len(dashboard["cost_trend"]), 30)
        self.assertGreater(dashboard["summary"]["total_cost"], 0)
        analytics_vm = next(item for item in dashboard["resources"] if item["name"] == "analytics-vm-01")
        self.assertEqual(analytics_vm["performance"]["metrics"]["CPU p95"], "19%")
        self.assertEqual(analytics_vm["optimization"]["status"], "not_requested")
        self.assertIn("timestamp", dashboard["cost_trend"][0])
        self.assertIsNone(dashboard["summary"]["potential_monthly_savings"])


if __name__ == "__main__":
    unittest.main()
