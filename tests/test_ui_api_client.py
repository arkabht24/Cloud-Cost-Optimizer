"""Verify that the UI client uses the public analysis API contract."""

import json
import unittest
from unittest.mock import MagicMock, patch

from rag.api_client import request_analysis


class UIAPIClientTests(unittest.TestCase):
    @patch("rag.api_client.urlopen")
    def test_uses_analysis_endpoint_without_trace(self, urlopen):
        response = MagicMock()
        response.read.return_value = b'{"answer":"API answer"}'
        urlopen.return_value.__enter__.return_value = response

        result = request_analysis("What can I optimize?", "demo-cost-lab", "sub-123")

        self.assertEqual(result["answer"], "API answer")
        request = urlopen.call_args.args[0]
        self.assertTrue(request.full_url.endswith("/v1/analyses"))
        payload = json.loads(request.data.decode("utf-8"))
        self.assertEqual(payload["resource_group"], "demo-cost-lab")
        self.assertEqual(payload["subscription"], "sub-123")
        self.assertFalse(payload["include_trace"])


if __name__ == "__main__":
    unittest.main()
