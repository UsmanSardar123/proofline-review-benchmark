"""Git worktree and repository isolation manager.

Guarantees that AI code reviewers are presented with an application-only Git repository
derived from clean baseline 9b5ac64 with the case patch applied, with zero access to
the benchmark engine, test harness, cases catalog, or answer keys.
"""

from contextlib import contextmanager
from dataclasses import dataclass, field
import io
from pathlib import Path
import shutil
import stat
import subprocess
import tempfile
from typing import Iterator, Optional
import zipfile

from benchmark.cases.registry import CaseRegistry
from benchmark.config import BASELINE_COMMIT, PROJECT_ROOT
from benchmark.git.repo import get_commit_sha, run_git


@dataclass
class IsolatedEnvironment:
    worktree_path: Path
    case_number: int
    case_id: str
    base_commit_sha: str
    head_commit_sha: str
    branch_name: str
    files_present: list[str] = field(default_factory=list)


class GitIsolationManager:
    """Creates, verifies, and tears down isolated application-only review repositories."""

    FORBIDDEN_NAMES = {
        "benchmark",
        "cases",
        "docs",
        "aws",
        "tests",
        "evidence",
        ".github",
        "benchmark.sqlite",
        "benchmark.sqlite-wal",
        "benchmark.sqlite-shm",
    }

    def __init__(self, repo_root: Optional[Path] = None):
        self.repo_root = repo_root or PROJECT_ROOT
        self.registry = CaseRegistry(self.repo_root / "cases")

    def _remove_readonly(self, func, path, exc_info):
        """Error handler for Windows readonly file deletion in shutil.rmtree."""
        try:
            Path(path).chmod(stat.S_IWRITE)
            func(path)
        except Exception:
            pass

    def verify_no_leak(self, target_path: Path) -> tuple[bool, list[str]]:
        """Verify that no benchmark control plane or answer-key files exist in the target path."""
        violations = []
        for item in target_path.iterdir():
            if item.name in self.FORBIDDEN_NAMES:
                violations.append(f"Forbidden directory/file leaked: {item.name}")
        return len(violations) == 0, violations

    def create_isolated_environment(
        self,
        case_number: int,
        target_dir: Path,
    ) -> IsolatedEnvironment:
        """Create a clean, isolated application Git repository for the given case.

        1. Extracts baseline commit (9b5ac64) files.
        2. Initializes a new Git repository.
        3. Commits the baseline application state.
        4. Applies the case patch.
        5. Commits the proposed change.
        6. Verifies the no-leak boundary.
        """
        case = self.registry.get_case(case_number)
        target_dir.mkdir(parents=True, exist_ok=True)

        # 1. Extract clean baseline from repository git archive
        zip_bytes = subprocess.check_output(
            ["git", "-C", str(self.repo_root), "archive", BASELINE_COMMIT, "--format=zip"]
        )
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            zf.extractall(target_dir)

        # 2. Initialize isolated Git repository
        run_git("init", cwd=target_dir)
        run_git("config", "user.name", "Benchmark Reviewer", cwd=target_dir)
        run_git("config", "user.email", "reviewer@proofline.sh", cwd=target_dir)

        # 3. Commit clean baseline
        run_git("add", ".", cwd=target_dir)
        run_git("commit", "-m", "Schedule and deliver reports", cwd=target_dir)
        base_sha = get_commit_sha("HEAD", cwd=target_dir)

        # 4. Apply the case change patch
        patch_path = (self.repo_root / case.patch_relpath).resolve()
        run_git("apply", "-p0", str(patch_path), cwd=target_dir)

        # 5. Commit proposed change
        run_git("add", ".", cwd=target_dir)
        run_git("commit", "-m", case.title, cwd=target_dir)
        head_sha = get_commit_sha("HEAD", cwd=target_dir)

        # 6. Verify isolation boundary
        is_clean, violations = self.verify_no_leak(target_dir)
        if not is_clean:
            raise RuntimeError(f"Reviewer isolation violated in {target_dir}: {violations}")

        files = sorted(f.name for f in target_dir.iterdir() if f.name != ".git")

        return IsolatedEnvironment(
            worktree_path=target_dir,
            case_number=case_number,
            case_id=case.id,
            base_commit_sha=base_sha,
            head_commit_sha=head_sha,
            branch_name="master",
            files_present=files,
        )

    @contextmanager
    def isolated_context(self, case_number: int) -> Iterator[IsolatedEnvironment]:
        """Context manager yielding an ephemeral, isolated application repository."""
        tmp_dir = Path(tempfile.mkdtemp(prefix=f"proofline-case-{case_number:02d}-"))
        try:
            env = self.create_isolated_environment(case_number, tmp_dir)
            yield env
        finally:
            shutil.rmtree(tmp_dir, onerror=self._remove_readonly)
