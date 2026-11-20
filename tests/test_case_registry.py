"""Unit tests for benchmark case registry, baseline management, and patch validation."""

import unittest

from benchmark.cases.registry import CaseRegistry
from benchmark.cases.validator import CaseValidator
from benchmark.config import BASELINE_COMMIT
from benchmark.domain.models import BenchmarkCase


class CaseRegistryTests(unittest.TestCase):
    def setUp(self):
        self.registry = CaseRegistry()

    def test_load_all_eight_cases(self):
        cases = self.registry.load_all_cases()
        self.assertEqual(len(cases), 8)
        for idx, case in enumerate(cases, start=1):
            self.assertEqual(case.case_number, idx)
            self.assertEqual(case.id, f"case-{idx:02d}")
            self.assertEqual(case.baseline_commit, BASELINE_COMMIT)
            self.assertTrue(len(case.title) > 0)
            self.assertTrue(len(case.pr_description) > 0)
            self.assertTrue(case.patch_relpath.endswith("change.patch"))

    def test_snapshot_requirements_by_case(self):
        cases = self.registry.load_all_cases()
        for case in cases:
            if case.case_number in {4, 5, 6}:
                self.assertTrue(case.has_deployment_snapshot, f"Case {case.case_number} should have snapshot")
                self.assertIsNotNone(case.snapshot_content)
                self.assertIn("```json", case.snapshot_content)
            else:
                self.assertFalse(case.has_deployment_snapshot, f"Case {case.case_number} should not have snapshot")
                self.assertIsNone(case.snapshot_content)

    def test_lookup_methods(self):
        case_1 = self.registry.get_case(1)
        self.assertEqual(case_1.id, "case-01")
        self.assertEqual(case_1.title, "Page report history by scheduled time")

        case_4 = self.registry.get_case_by_id("case-04")
        self.assertEqual(case_4.case_number, 4)
        self.assertEqual(case_4.title, "Retire the legacy delivery column")

    def test_validate_all_cases_pass(self):
        results = self.registry.validate_all()
        self.assertEqual(len(results), 8)
        for res in results:
            self.assertTrue(
                res.is_valid,
                f"Case {res.case_number} validation failed with errors: {res.errors}",
            )
            self.assertTrue(res.patch_applies_cleanly, f"Case {res.case_number} patch does not apply cleanly")
            self.assertTrue(len(res.patch_sha256) == 64, f"Case {res.case_number} missing valid SHA256")
            if res.case_number in {4, 5, 6}:
                self.assertTrue(res.has_snapshot)
                self.assertTrue(res.snapshot_json_valid)
            else:
                self.assertFalse(res.has_snapshot)

    def test_validator_detects_corrupt_metadata(self):
        validator = CaseValidator()
        corrupt_case = BenchmarkCase(
            id="case-bad",
            case_number=99,
            title="",  # empty title
            pr_description="",  # empty desc
            baseline_commit="wrong-baseline",
            target_commit="unknown",
            patch_relpath="cases/nonexistent/change.patch",
        )
        res = validator.validate_case(corrupt_case)
        self.assertFalse(res.is_valid)
        self.assertTrue(any("empty" in e for e in res.errors))
        self.assertTrue(any("Baseline commit mismatch" in e for e in res.errors))
        self.assertTrue(any("Patch file missing" in e for e in res.errors))


if __name__ == "__main__":
    unittest.main()
