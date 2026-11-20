"""Git command execution helpers and inspection utilities."""

from pathlib import Path
import subprocess
from typing import Optional

from benchmark.config import PROJECT_ROOT


class GitError(RuntimeError):
    """Raised when a Git command fails."""
    pass


def run_git(*args: str, cwd: Optional[Path] = None) -> str:
    """Execute a git command and return stripped stdout."""
    workdir = cwd or PROJECT_ROOT
    try:
        res = subprocess.run(
            ["git", *args],
            cwd=str(workdir),
            capture_output=True,
            text=True,
            check=True,
        )
        return res.stdout.strip()
    except subprocess.CalledProcessError as err:
        stderr_msg = err.stderr.strip() if err.stderr else str(err)
        raise GitError(f"git {' '.join(args)} failed: {stderr_msg}") from err


def get_commit_sha(ref: str = "HEAD", cwd: Optional[Path] = None) -> str:
    """Resolve a Git reference or revision to a full SHA-1 hash."""
    return run_git("rev-parse", "--verify", f"{ref}^{{commit}}", cwd=cwd)


def get_diff(base_ref: str, head_ref: str, cwd: Optional[Path] = None) -> str:
    """Generate a unified diff between two Git references."""
    return run_git("diff", base_ref, head_ref, cwd=cwd)


def is_git_clean(cwd: Optional[Path] = None) -> bool:
    """Check whether a working directory has uncommitted modifications."""
    output = run_git("status", "--porcelain", cwd=cwd)
    return len(output.strip()) == 0
