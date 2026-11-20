"""Case validation and integrity verification for the benchmark cases."""

from dataclasses import dataclass, field
import hashlib
import json
from pathlib import Path
import re
import subprocess
from typing import Optional

from benchmark.config import BASELINE_COMMIT, PROJECT_ROOT
from benchmark.domain.models import BenchmarkCase


@dataclass
class ValidationResult:
    case_number: int
    case_id: str
    is_valid: bool
    patch_sha256: str = ""
    patch_applies_cleanly: bool = False
    has_snapshot: bool = False
    snapshot_json_valid: bool = False
    errors: list[str] = field(default_factory=list)


class CaseValidator:
    """Verifies patch integrity, metadata completeness, and git apply compatibility."""

    EXPECTED_TARGET_COMMITS = {
        1: "b422577",
        2: "9d551b8",
        3: "6cca1e9",
        4: "420baea",
        5: "1f6f2a4",
        6: "fcb0c2a",
        7: "68ef658",
        8: "f869d7c",
    }

    CASES_REQUIRING_SNAPSHOT = {4, 5, 6}

    def __init__(self, repo_root: Optional[Path] = None):
        self.repo_root = repo_root or PROJECT_ROOT

    def validate_case(self, case: BenchmarkCase) -> ValidationResult:
        errors = []
        patch_sha256 = ""
        applies_cleanly = False
        snapshot_valid = False

        # 1. Validate metadata fields
        if not case.title or not case.title.strip():
            errors.append("Case title is empty.")
        if not case.pr_description or not case.pr_description.strip():
            errors.append("PR description is empty.")
        if case.baseline_commit != BASELINE_COMMIT:
            errors.append(f"Baseline commit mismatch: expected {BASELINE_COMMIT}, got {case.baseline_commit}")

        expected_commit = self.EXPECTED_TARGET_COMMITS.get(case.case_number)
        if expected_commit and not case.target_commit.startswith(expected_commit):
            errors.append(f"Target commit mismatch: expected prefix {expected_commit}, got {case.target_commit}")

        # 2. Validate patch file existence and checksum
        patch_path = self.repo_root / case.patch_relpath
        if not patch_path.is_file():
            errors.append(f"Patch file missing at: {case.patch_relpath}")
        else:
            patch_bytes = patch_path.read_bytes()
            if len(patch_bytes) == 0:
                errors.append("Patch file is empty.")
            else:
                patch_sha256 = hashlib.sha256(patch_bytes).hexdigest()

                # 3. Validate git patch apply dry-run
                try:
                    res = subprocess.run(
                        ["git", "-C", str(self.repo_root), "apply", "--check", "-p0", str(patch_path)],
                        capture_output=True,
                        text=True,
                    )
                    if res.returncode == 0:
                        applies_cleanly = True
                    else:
                        errors.append(f"git apply --check failed: {res.stderr.strip()}")
                except Exception as exc:
                    errors.append(f"Failed to execute git apply: {exc}")

        # 4. Validate deployment snapshot for cases requiring evidence
        if case.case_number in self.CASES_REQUIRING_SNAPSHOT:
            if not case.has_deployment_snapshot or not case.snapshot_content:
                errors.append(f"Case {case.case_number} requires a deployment snapshot but none was found.")
            else:
                # Extract and parse JSON block from evidence markdown
                json_match = re.search(r"```json\s*(\{.*?\})\s*```", case.snapshot_content, re.DOTALL)
                if not json_match:
                    errors.append(f"Case {case.case_number} evidence.md does not contain a valid ```json block.")
                else:
                    try:
                        parsed = json.loads(json_match.group(1))
                        if not isinstance(parsed, dict) or "observation" not in parsed:
                            errors.append("Parsed evidence JSON missing 'observation' field.")
                        else:
                            snapshot_valid = True
                    except json.JSONDecodeError as err:
                        errors.append(f"Malformed JSON in evidence.md: {err}")
        else:
            if case.has_deployment_snapshot:
                errors.append(f"Case {case.case_number} should not have a deployment snapshot.")

        is_valid = len(errors) == 0
        return ValidationResult(
            case_number=case.case_number,
            case_id=case.id,
            is_valid=is_valid,
            patch_sha256=patch_sha256,
            patch_applies_cleanly=applies_cleanly,
            has_snapshot=case.has_deployment_snapshot,
            snapshot_json_valid=snapshot_valid,
            errors=errors,
        )

    def validate_all(self, cases: list[BenchmarkCase]) -> list[ValidationResult]:
        return [self.validate_case(c) for c in cases]
