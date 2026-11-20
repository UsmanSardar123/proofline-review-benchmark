"""Case catalog discovery and ingestion from cases/ directory."""

from pathlib import Path
from typing import Optional

from benchmark.config import BASELINE_COMMIT, get_cases_dir
from benchmark.domain.models import BenchmarkCase


class CaseRegistry:
    """Discovers and parses the eight benchmark cases from disk."""

    def __init__(self, cases_dir: Optional[Path] = None):
        self.cases_dir = cases_dir or get_cases_dir()

    def load_case(self, case_number: int) -> BenchmarkCase:
        case_slug = f"{case_number:02d}"
        case_path = self.cases_dir / case_slug

        if not case_path.is_dir():
            raise FileNotFoundError(f"Case directory not found: {case_path}")

        title = (case_path / "title.txt").read_text(encoding="utf-8").strip()
        body = (case_path / "body.md").read_text(encoding="utf-8").strip()
        patch_file = case_path / "change.patch"
        patch_relpath = f"cases/{case_slug}/change.patch"

        evidence_file = case_path / "evidence.md"
        has_snapshot = evidence_file.is_file()
        snapshot_content = evidence_file.read_text(encoding="utf-8").strip() if has_snapshot else None

        # Upstream commit mapping
        commit_map = {
            1: "b422577",
            2: "9d551b8",
            3: "6cca1e9",
            4: "420baea",
            5: "1f6f2a4",
            6: "fcb0c2a",
            7: "68ef658",
            8: "f869d7c",
        }

        return BenchmarkCase(
            id=f"case-{case_slug}",
            case_number=case_number,
            title=title,
            pr_description=body,
            baseline_commit=BASELINE_COMMIT,
            target_commit=commit_map.get(case_number, "unknown"),
            patch_relpath=patch_relpath,
            has_deployment_snapshot=has_snapshot,
            snapshot_content=snapshot_content,
        )

    def load_all_cases(self) -> list[BenchmarkCase]:
        cases = []
        for n in range(1, 9):
            cases.append(self.load_case(n))
        return cases
