"""Benchmark test suite."""

import atexit
import os
import tempfile

# Ensure automated test execution isolates evidence files from project workspace
_test_evidence_tmp = tempfile.TemporaryDirectory(prefix="benchmark_test_evidence_")
os.environ.setdefault("BENCHMARK_EVIDENCE_DIR", _test_evidence_tmp.name)


def _cleanup_test_evidence():
    try:
        _test_evidence_tmp.cleanup()
    except Exception:
        pass


atexit.register(_cleanup_test_evidence)
