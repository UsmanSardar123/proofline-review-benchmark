"""Unit and safety tests for SafeCampaignRunner (Cases 03-08)."""

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from benchmark.domain.enums import ContextCondition
from benchmark.orchestrator.campaign import (
    ALLOWED_CAMPAIGN_CASES,
    CampaignBudgetError,
    CampaignValidationError,
    SafeCampaignRunner,
)
from benchmark.providers.cloudflare import NeuronTracker


class TestSafeCampaignRunner(unittest.TestCase):
    """Test suite ensuring strict safety, scope, anti-leak, and budgeting for the campaign runner."""

    def setUp(self):
        self.runner = SafeCampaignRunner()

    def test_preflight_audit_cases_03_to_08(self):
        """Verify that Cases 03 to 08 pass all preflight checks without leaks."""
        result = self.runner.audit_preflight(target_cases=ALLOWED_CAMPAIGN_CASES)
        self.assertTrue(result.is_valid, f"Preflight failed: {result.errors}")
        self.assertEqual(len(result.case_audits), 6)
        self.assertEqual(result.allowed_cases, [3, 4, 5, 6, 7, 8])

        for audit in result.case_audits:
            self.assertTrue(audit.leak_check_passed)
            self.assertEqual(audit.status, "VALID")
            self.assertGreater(audit.prompt_length_chars, 500)
            self.assertLess(audit.estimated_input_tokens, 4096)
            self.assertGreater(audit.estimated_neurons, 0)
            self.assertIn(audit.case_number, [3, 4, 5, 6, 7, 8])

        # Verify aggregate compute is reasonable (< 1,000 Neurons)
        self.assertLess(result.total_estimated_neurons, 1000)
        self.assertGreater(result.remaining_daily_budget, result.total_estimated_neurons)

    def test_scope_boundary_enforcement(self):
        """Verify that attempting to run cases outside Cases 03-08 fails closed."""
        result_with_case1 = self.runner.audit_preflight(target_cases=[1, 2, 3])
        self.assertFalse(result_with_case1.is_valid)
        self.assertTrue(any("Scope violation" in e for e in result_with_case1.errors))

        result_with_case9 = self.runner.audit_preflight(target_cases=[9])
        self.assertFalse(result_with_case9.is_valid)
        self.assertTrue(any("Scope violation" in e for e in result_with_case9.errors))

    def test_anti_leak_fails_closed_on_defect_id_in_prompt(self):
        """Verify that any prompt leaking a ground-truth defect ID fails preflight."""
        with patch.object(self.runner.context_manager, "format_review_prompt", return_value="Here is defect gt-case-03 in the code"):
            result = self.runner.audit_preflight(target_cases=[3])
            self.assertFalse(result.is_valid)
            self.assertTrue(any("LEAK DETECTED" in e and "gt-case-03" in e for e in result.errors))

    def test_anti_leak_fails_closed_on_defect_category_in_prompt(self):
        """Verify that any prompt leaking a defect category header fails preflight."""
        with patch.object(self.runner.context_manager, "format_review_prompt", return_value="Here is the review. Defect Category: LOGIC_BUG"):
            result = self.runner.audit_preflight(target_cases=[3])
            self.assertFalse(result.is_valid)
            self.assertTrue(any("LEAK DETECTED" in e and "ground truth header" in e for e in result.errors))

    def test_fails_closed_on_exceeded_neuron_budget(self):
        """Verify that preflight fails closed if projected compute exceeds local daily ceiling."""
        # Artificially set low limit
        low_limit_runner = SafeCampaignRunner(daily_neuron_limit=100)
        result = low_limit_runner.audit_preflight(target_cases=ALLOWED_CAMPAIGN_CASES)
        self.assertFalse(result.is_valid)
        self.assertTrue(any("Budget violation" in e for e in result.errors))

    def test_fails_closed_on_corrupt_neuron_tracker(self):
        """Verify that preflight fails closed if neuron tracker usage file is corrupt."""
        with tempfile.NamedTemporaryFile("w", delete=False) as tf:
            tf.write("CORRUPTED_JSON_DATA{{{")
            corrupt_path = Path(tf.name)

        try:
            corrupt_tracker = NeuronTracker(usage_file=corrupt_path)
            runner = SafeCampaignRunner()
            runner.neuron_tracker = corrupt_tracker
            result = runner.audit_preflight(target_cases=[3])
            self.assertFalse(result.is_valid)
            self.assertTrue(any("NeuronTracker verification failed" in e for e in result.errors))
        finally:
            if corrupt_path.exists():
                corrupt_path.unlink()

    def test_dry_run_execution_zero_cost(self):
        """Verify dry-run simulation generates report, touches zero external APIs, and incurs $0.00."""
        report = self.runner.execute_dry_run(target_cases=ALLOWED_CAMPAIGN_CASES)
        self.assertEqual(report.mode, "dry_run")
        self.assertEqual(report.total_planned, 6)
        self.assertEqual(report.completed, 6)
        self.assertEqual(report.failed, 0)
        self.assertEqual(report.skipped, 0)
        self.assertEqual(report.actual_dollar_cost, 0.0)
        self.assertEqual(len(report.case_results), 6)

        for res in report.case_results:
            self.assertEqual(res.status, "DRY_RUN")
            self.assertIsNotNone(res.content_hash_sha256)
            self.assertIn(res.case_number, ALLOWED_CAMPAIGN_CASES)

    def test_live_execution_unauthorized_boundary(self):
        """Verify that execute_live_campaign raises PermissionError if authorized is False."""
        with self.assertRaises(PermissionError):
            self.runner.execute_live_campaign(authorized=False)

    def test_per_request_budget_check_halts_loop(self):
        """Verify that budget is checked before each case request in the campaign loop."""
        # Call 1: initial_neurons = 0; Call 2: curr_used before Case 3 = 5001 (exceeds 5000 limit)
        with patch.object(self.runner.neuron_tracker, "get_daily_used_neurons", side_effect=[0, 5001, 5001]):
            with patch.object(self.runner, "audit_preflight") as mock_audit:
                mock_preflight = MagicMock()
                mock_preflight.is_valid = True
                mock_preflight.current_neurons_consumed = 0
                mock_preflight.case_audits = []
                mock_audit.return_value = mock_preflight

                with patch.object(self.runner.batch_repo, "create"):
                    with patch.object(self.runner.attempt_repo, "create"):
                        with patch.object(self.runner.batch_repo, "update_status"):
                            report = self.runner.execute_live_campaign(authorized=True, target_cases=[3, 4])
                            self.assertIsNotNone(report.halt_reason)
                            self.assertIn("Daily Neuron budget ceiling reached", report.halt_reason)
                            self.assertEqual(report.completed, 0)
                            self.assertEqual(report.skipped, 2)


if __name__ == "__main__":
    unittest.main()
