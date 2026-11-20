"""Deterministic claim extraction from AI review responses."""

import json
from pathlib import Path
import re
from typing import Optional
import uuid

from benchmark.domain.models import ReviewFinding, ReviewResponse


class FindingExtractor:
    """Extracts structured code review findings and claims from review responses."""

    KNOWN_FILES = [
        "reports.py",
        "console.py",
        "migrations/001_initial.sql",
        "migrations/002_retire_format.sql",
        "migrations/002_pending_by_queue.sql",
        "README.md",
    ]

    SEVERITY_KEYWORDS = {
        "critical": "critical",
        "high": "critical",
        "severe": "critical",
        "error": "error",
        "bug": "error",
        "warning": "warning",
        "warn": "warning",
        "medium": "warning",
        "suggestion": "info",
        "info": "info",
        "low": "info",
        "note": "info",
    }

    def extract_findings(self, response: ReviewResponse) -> list[ReviewFinding]:
        """Extract atomic findings from a ReviewResponse object."""
        content = response.raw_content.strip()
        if not content:
            return []

        # 1. Attempt JSON structure extraction
        json_findings = self._extract_from_json(response, content)
        if json_findings is not None:
            return json_findings

        # 2. Markdown / Text heuristic extraction
        return self._extract_from_markdown(response, content)

    def _extract_from_json(self, response: ReviewResponse, content: str) -> Optional[list[ReviewFinding]]:
        """Extract findings if the response contains structured JSON."""
        json_text = None
        if content.startswith("{") and content.endswith("}"):
            json_text = content
        else:
            match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", content, re.DOTALL)
            if match:
                json_text = match.group(1)

        if not json_text:
            return None

        try:
            data = json.loads(json_text)
            items = data.get("findings") or data.get("issues") or data.get("comments") or []
            if not isinstance(items, list):
                return None

            findings = []
            for item in items:
                if isinstance(item, dict):
                    f_id = f"find-{uuid.uuid4().hex[:12]}"
                    file_p = item.get("file") or item.get("file_path")
                    line_s = item.get("line") or item.get("line_start")
                    line_e = item.get("line_end")
                    sev = str(item.get("severity", "warning")).lower()
                    summary = item.get("summary") or item.get("title") or item.get("message") or "Code issue"
                    comment = item.get("description") or item.get("comment") or summary

                    findings.append(
                        ReviewFinding(
                            id=f_id,
                            response_id=response.id,
                            attempt_id=response.attempt_id,
                            file_path=file_p,
                            line_start=int(line_s) if line_s else None,
                            line_end=int(line_e) if line_e else None,
                            reported_severity=self.SEVERITY_KEYWORDS.get(sev, "warning"),
                            summary=summary[:255],
                            raw_comment_slice=comment[:1000],
                        )
                    )
            return findings
        except (json.JSONDecodeError, ValueError):
            return None

    def _extract_from_markdown(self, response: ReviewResponse, content: str) -> list[ReviewFinding]:
        """Extract atomic findings from unstructured markdown text."""
        findings = []

        # Split content into candidate blocks by markdown headers, numbered items, or grouped bullet blocks
        if re.search(r"\n#{2,4}\s+", content):
            blocks = re.split(r"\n(?=#{2,4}\s+)", content)
        elif re.search(r"\n\d+\.\s+", content):
            blocks = re.split(r"\n(?=\d+\.\s+)", content)
        elif re.search(r"[-*]\s+\*\*(?:File|Line|Comment|Severity)\*\*:", content, re.IGNORECASE):
            # Property-based bullet list represents a unified finding
            blocks = [content]
        else:
            blocks = re.split(r"\n(?=[-*]\s+)", content)

        for block in blocks:
            b_text = block.strip()
            if not b_text or len(b_text) < 15:
                continue

            # Skip general greetings or empty review summaries
            lower = b_text.lower()
            if "looks good to me" in lower or "lgtm" in lower or "no defects found" in lower:
                continue

            # Identify target file
            target_file = None
            for kf in self.KNOWN_FILES:
                if kf in b_text or kf.replace("/", "\\") in b_text:
                    target_file = kf
                    break

            # Identify line numbers
            line_start, line_end = None, None
            line_match = re.search(r"(?:line[s]?|:)\s*(\d+)(?:\s*(?:to|-)\s*(\d+))?", b_text, re.IGNORECASE)
            if line_match:
                try:
                    line_start = int(line_match.group(1))
                    if line_match.group(2):
                        line_end = int(line_match.group(2))
                except (ValueError, TypeError):
                    pass

            # Identify severity
            severity = "warning"
            for sk, mapped in self.SEVERITY_KEYWORDS.items():
                if re.search(rf"\b{sk}\b", lower):
                    severity = mapped
                    break

            # Check if this block describes an actionable issue or recommendation
            has_issue_cue = any(
                term in lower
                for term in [
                    "issue", "bug", "defect", "problem", "error", "warning", "flaw",
                    "skip", "drop", "starv", "break", "fail", "regression", "conflict",
                    "oversized", "deadlock", "rfc", "quot", "recommendation"
                ]
            )

            if target_file or line_start or has_issue_cue:
                # Extract summary line (first non-empty line of block)
                lines = [ln.strip("#-* \t") for ln in b_text.splitlines() if ln.strip("#-* \t")]
                summary = lines[0] if lines else "Identified code review issue"
                f_id = f"find-{uuid.uuid4().hex[:12]}"

                findings.append(
                    ReviewFinding(
                        id=f_id,
                        response_id=response.id,
                        attempt_id=response.attempt_id,
                        file_path=target_file,
                        line_start=line_start,
                        line_end=line_end,
                        reported_severity=severity,
                        summary=summary[:255],
                        raw_comment_slice=b_text[:1000],
                    )
                )

        return findings
