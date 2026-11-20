"""Unit tests for ReviewContext and ContextManager."""

import unittest

from benchmark.cases.context import ContextManager, ContextSafetyError
from benchmark.domain.enums import ContextCondition


class ContextManagerTests(unittest.TestCase):
    def setUp(self):
        self.mgr = ContextManager()

    def test_code_only_context_case_01(self):
        ctx = self.mgr.build_context(1, ContextCondition.CODE_ONLY)
        self.assertEqual(ctx.case_number, 1)
        self.assertEqual(ctx.case_id, "case-01")
        self.assertEqual(ctx.context_condition, ContextCondition.CODE_ONLY)
        self.assertIsNone(ctx.snapshot_content)
        self.assertTrue(len(ctx.context_hash) == 64)
        self.assertIn("scheduled_at", ctx.patch_diff)

        prompt = self.mgr.format_review_prompt(ctx)
        self.assertIn("Page report history by scheduled time", prompt)
        self.assertIn("```diff", prompt)
        self.assertNotIn("Operational & Deployment Context", prompt)

    def test_code_and_snapshot_context_case_04(self):
        ctx = self.mgr.build_context(4, ContextCondition.CODE_AND_SNAPSHOT)
        self.assertEqual(ctx.case_number, 4)
        self.assertEqual(ctx.context_condition, ContextCondition.CODE_AND_SNAPSHOT)
        self.assertIsNotNone(ctx.snapshot_content)
        self.assertIn("inventory-204", ctx.snapshot_content)

        prompt = self.mgr.format_review_prompt(ctx)
        self.assertIn("Operational & Deployment Context", prompt)
        self.assertIn("inventory-204", prompt)
        self.assertIn("```diff", prompt)

    def test_code_and_snapshot_for_case_without_snapshot(self):
        # Case 02 does not have a deployment snapshot
        ctx = self.mgr.build_context(2, ContextCondition.CODE_AND_SNAPSHOT)
        self.assertIsNone(ctx.snapshot_content)
        prompt = self.mgr.format_review_prompt(ctx)
        self.assertNotIn("Operational & Deployment Context", prompt)

    def test_context_hash_ablation_difference(self):
        # The same case under CODE_ONLY vs CODE_AND_SNAPSHOT must yield distinct hashes
        ctx_code_only = self.mgr.build_context(4, ContextCondition.CODE_ONLY)
        ctx_with_snap = self.mgr.build_context(4, ContextCondition.CODE_AND_SNAPSHOT)
        self.assertNotEqual(ctx_code_only.context_hash, ctx_with_snap.context_hash)

    def test_context_safety_violation_detection(self):
        # Attempting to inject answer key words raises ContextSafetyError
        with self.assertRaises(ContextSafetyError):
            self.mgr.build_context(
                case_number=1,
                condition=ContextCondition.CODE_ONLY,
                patch_diff="diff --git a/reports.py b/reports.py\n+ # Leaked answer_key: defect found here",
            )

    def test_provenance_audit_tracking(self):
        ctx = self.mgr.build_context(5, ContextCondition.CODE_AND_SNAPSHOT)
        prov = ctx.provenance
        self.assertEqual(prov["case_id"], "case-05")
        self.assertEqual(prov["case_number"], 5)
        self.assertEqual(prov["condition"], "CODE_AND_SNAPSHOT")
        self.assertTrue(prov["has_snapshot"])
        self.assertTrue("cases/05/change.patch" in prov["patch_path"])
        self.assertTrue("generated_at" in prov)


if __name__ == "__main__":
    unittest.main()
