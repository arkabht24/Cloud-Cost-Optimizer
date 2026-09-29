import unittest

from rag.resource_matching import mentions_resource, resource_blocks
from rag.response_policy import extract_evidence_plan


class ResourceMatchingTests(unittest.TestCase):
    def test_hyphenated_resource_prefix_is_not_a_match(self):
        self.assertTrue(mentions_resource("analytics-vm-01 is running", "analytics-vm-01"))
        self.assertFalse(mentions_resource("analytics-vm-01-data is unattached", "analytics-vm-01"))

    def test_resource_blocks_exclude_adjacent_disk_record(self):
        text = """analytics-vm-01
CPU p95 is 19 percent.
analytics-vm-01-data
Hold deletion pending owner confirmation."""
        blocks = resource_blocks(text, ["analytics-vm-01"], ["analytics-vm-01", "analytics-vm-01-data"])
        self.assertEqual(blocks, ["analytics-vm-01 CPU p95 is 19 percent."])

    def test_evidence_plan_excludes_adjacent_disk_decision(self):
        text = """analytics-vm-01
CPU p95 is 19 percent.
analytics-vm-01-data
Hold deletion pending owner confirmation."""
        plan = extract_evidence_plan(
            "Should we reduce capacity for analytics-vm-01 now?",
            ["analytics-vm-01"],
            [{"id": "ctx-1", "text": text}],
            inventory_names=["analytics-vm-01", "analytics-vm-01-data"],
        )
        joined = " ".join(item["text"] for item in plan["evidence"]).lower()
        self.assertNotIn("hold deletion", joined)
        self.assertNotIn("analytics-vm-01-data", joined)

    def test_rightsizing_plan_excludes_unnamed_associated_disk_detail(self):
        text = """analytics-vm-01 is a development VM.
Its associated 1 TB disk is unattached.
CPU p95 is 19 percent for analytics-vm-01."""
        plan = extract_evidence_plan(
            "Should we reduce capacity for analytics-vm-01 now?",
            ["analytics-vm-01"],
            [{"id": "ctx-2", "text": text}],
            inventory_names=["analytics-vm-01"],
        )
        joined = " ".join(item["text"] for item in plan["evidence"]).lower()
        self.assertNotIn("associated 1 tb disk", joined)


if __name__ == "__main__":
    unittest.main()
