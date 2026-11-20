"""Case catalog discovery, ingestion, and validation from cases/ directory."""

from pathlib import Path
from typing import Optional

from benchmark.cases.validator import CaseValidator, ValidationResult
from benchmark.config import BASELINE_COMMIT, get_cases_dir
from benchmark.domain.models import BenchmarkCase


class CaseRegistry:
    """Discovers, parses, and validates the eight benchmark cases from disk."""

    COMMIT_MAP = {
        1: "b422577",
        2: "9d551b8",
        3: "6cca1e9",
        4: "420baea",
        5: "1f6f2a4",
        6: "fcb0c2a",
        7: "68ef658",
        8: "f869d7c",
    }

    def __init__(self, cases_dir: Optional[Path] = None):
        self.cases_dir = cases_dir or get_cases_dir()
        self._cache: dict[int, BenchmarkCase] = {}
        self._validator: Optional[CaseValidator] = None

    @property
    def validator(self) -> CaseValidator:
        if self._validator is None:
            self._validator = CaseValidator()
        return self._validator

    def load_case(self, case_number: int) -> BenchmarkCase:
        """Load and cache a single benchmark case by number (1 to 8)."""
        if case_number in self._cache:
            return self._cache[case_number]

        case_slug = f"{case_number:02d}"
        case_path = self.cases_dir / case_slug

        if not case_path.is_dir():
            raise FileNotFoundError(f"Case directory not found: {case_path}")

        title = (case_path / "title.txt").read_text(encoding="utf-8").strip()
        body = (case_path / "body.md").read_text(encoding="utf-8").strip()
        patch_relpath = f"cases/{case_slug}/change.patch"

        evidence_file = case_path / "evidence.md"
        has_snapshot = evidence_file.is_file()
        snapshot_content = evidence_file.read_text(encoding="utf-8").strip() if has_snapshot else None

        case = BenchmarkCase(
            id=f"case-{case_slug}",
            case_number=case_number,
            title=title,
            pr_description=body,
            baseline_commit=BASELINE_COMMIT,
            target_commit=self.COMMIT_MAP.get(case_number, "unknown"),
            patch_relpath=patch_relpath,
            has_deployment_snapshot=has_snapshot,
            snapshot_content=snapshot_content,
        )
        self._cache[case_number] = case
        return case

    def get_case(self, case_number: int) -> BenchmarkCase:
        """Retrieve a case by its numeric index (1..8)."""
        return self.load_case(case_number)

    def get_case_by_id(self, case_id: str) -> BenchmarkCase:
        """Retrieve a case by slug ID (e.g. 'case-01')."""
        num = int(case_id.replace("case-", ""))
        return self.load_case(num)

    def load_all_cases(self) -> list[BenchmarkCase]:
        """Load and cache all 8 benchmark cases in numerical order."""
        return [self.load_case(n) for n in range(1, 9)]

    def validate_case(self, case_number: int) -> ValidationResult:
        """Validate a single case for patch integrity and metadata completeness."""
        case = self.load_case(case_number)
        return self.validator.validate_case(case)

    def validate_all(self) -> list[ValidationResult]:
        """Validate all 8 benchmark cases and return validation results."""
        cases = self.load_all_cases()
        return self.validator.validate_all(cases)
