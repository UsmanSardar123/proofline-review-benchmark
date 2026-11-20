"""Filesystem mirror storage for raw provider review evidence."""

import json
from pathlib import Path
from typing import Optional

from benchmark.config import get_evidence_dir


class RawEvidenceStore:
    """Manages raw evidence archival on the filesystem under evidence/raw/."""

    def __init__(self, root_dir: Optional[Path] = None):
        self.root_dir = root_dir or get_evidence_dir()

    def _get_batch_dir(self, batch_id: str) -> Path:
        batch_dir = self.root_dir / batch_id
        batch_dir.mkdir(parents=True, exist_ok=True)
        return batch_dir

    def save_evidence(
        self,
        batch_id: str,
        attempt_id: str,
        content: str,
        metadata: Optional[dict] = None,
    ) -> Path:
        """Save raw review response markdown and metadata sidecar."""
        batch_dir = self._get_batch_dir(batch_id)
        md_file = batch_dir / f"{attempt_id}.md"
        md_file.write_text(content, encoding="utf-8")

        if metadata:
            meta_file = batch_dir / f"{attempt_id}.meta.json"
            meta_file.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

        return md_file

    def get_evidence(self, batch_id: str, attempt_id: str) -> Optional[str]:
        """Read preserved raw review response markdown."""
        md_file = self.root_dir / batch_id / f"{attempt_id}.md"
        if not md_file.is_file():
            return None
        return md_file.read_text(encoding="utf-8")

    def get_metadata(self, batch_id: str, attempt_id: str) -> Optional[dict]:
        """Read response metadata sidecar."""
        meta_file = self.root_dir / batch_id / f"{attempt_id}.meta.json"
        if not meta_file.is_file():
            return None
        return json.loads(meta_file.read_text(encoding="utf-8"))
