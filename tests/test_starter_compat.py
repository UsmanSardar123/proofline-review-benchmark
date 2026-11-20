"""Compatibility regression tests ensuring starter application remains untouched."""

import json
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import reports


class StarterCompatibilityTests(unittest.TestCase):
    def test_scheduled_report_lifecycle(self):
        con = sqlite3.connect(":memory:")
        reports.migrate(con)

        # Schedule report
        job_id = reports.schedule(con, "Weekly orders", 1700000000)
        self.assertEqual(job_id, 1)

        # Verify summary before delivery
        s1 = reports.summary(con)
        self.assertEqual(s1["pending"], 1)
        self.assertEqual(s1["delivered"], 0)

        # Deliver due
        delivered = reports.deliver_due(con, "reports", 1700000001)
        self.assertEqual(delivered, 1)

        # Verify summary after delivery
        s2 = reports.summary(con)
        self.assertEqual(s2["pending"], 0)
        self.assertEqual(s2["delivered"], 1)

        # Check history
        h = reports.history(con, 10)
        self.assertEqual(len(h.rows), 1)
        self.assertEqual(h.rows[0][1], "Weekly orders")
        con.close()

    def test_aws_packaging_and_smoke_check(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            out_template = Path(tmp_dir) / "test-stack.json"
            # Test package command
            subprocess.run(
                [sys.executable, "aws/deploy.py", "package", "--output", str(out_template)],
                check=True,
                capture_output=True,
                text=True,
            )
            self.assertTrue(out_template.is_file())

            # Test smoke check
            result = subprocess.run(
                [sys.executable, "aws/deploy.py", "smoke", "--template", str(out_template)],
                check=True,
                capture_output=True,
                text=True,
            )
            output = json.loads(result.stdout)
            self.assertEqual(output["request_id"], "local-smoke")
            self.assertEqual(output["delivered_this_run"], 1)
            self.assertEqual(output["summary"]["delivered"], 1)
            self.assertEqual(output["summary"]["pending"], 0)


if __name__ == "__main__":
    unittest.main()
