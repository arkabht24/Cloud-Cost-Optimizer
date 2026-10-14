"""Checks for the portable stakeholder report renderer."""

import unittest

from azure.dashboard_data import build_dashboard_data
from azure.stakeholder_report import render_stakeholder_report


class StakeholderReportTests(unittest.TestCase):
    def test_report_contains_dashboard_facts_and_ai_response(self):
        dashboard = build_dashboard_data("demo-cost-lab", days=7)
        html = render_stakeholder_report(
            dashboard,
            {
                "analytics-vm-01": {
                    "answer": "Review measured utilization before changing capacity.",
                    "decision": {"decision": "needs_review"},
                }
            },
        )
        self.assertIn("Cloud Cost Optimiser", html)
        self.assertIn("analytics-vm-01", html)
        self.assertIn("Review required", html)
        self.assertIn("Review measured utilization", html)


if __name__ == "__main__":
    unittest.main()
