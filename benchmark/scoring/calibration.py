"""Calibration and threshold management for deterministic review scoring."""

from dataclasses import dataclass, field
import hashlib
import json
from typing import Optional

from benchmark.scoring.matcher import MatchingConfig


@dataclass
class CalibrationProfile:
    """Configurable scoring and matching parameters versioned for reproducibility."""
    name: str
    version: str
    line_tolerance: int = 5
    match_threshold: float = 0.45
    min_keyword_matches: int = 1
    require_file_match: bool = True
    severity_strictness: str = "standard"  # 'standard', 'strict', 'lenient'
    description: str = ""
    profile_hash: str = ""

    def __post_init__(self):
        if not self.profile_hash:
            param_str = (
                f"{self.name}:{self.version}:{self.line_tolerance}:{self.match_threshold}:"
                f"{self.min_keyword_matches}:{self.require_file_match}:{self.severity_strictness}"
            )
            self.profile_hash = hashlib.sha256(param_str.encode("utf-8")).hexdigest()[:16]

    def to_matching_config(self) -> MatchingConfig:
        """Convert calibration profile to FindingMatcher configuration."""
        return MatchingConfig(
            line_tolerance=self.line_tolerance,
            require_file_match=self.require_file_match,
            min_keyword_matches=self.min_keyword_matches,
            match_threshold=self.match_threshold,
        )


STANDARD_PROFILE = CalibrationProfile(
    name="standard-v1",
    version="v1.0",
    line_tolerance=5,
    match_threshold=0.45,
    min_keyword_matches=1,
    require_file_match=True,
    severity_strictness="standard",
    description="Standard balanced threshold profile for general benchmark evaluation.",
)

STRICT_PROFILE = CalibrationProfile(
    name="strict-v1",
    version="v1.0",
    line_tolerance=2,
    match_threshold=0.60,
    min_keyword_matches=2,
    require_file_match=True,
    severity_strictness="strict",
    description="Strict precision-oriented profile requiring exact line proximity and multiple keywords.",
)

LENIENT_PROFILE = CalibrationProfile(
    name="lenient-v1",
    version="v1.0",
    line_tolerance=12,
    match_threshold=0.35,
    min_keyword_matches=1,
    require_file_match=False,
    severity_strictness="lenient",
    description="Lenient recall-oriented profile permitting broader line tolerance and partial file match.",
)


class CalibrationRegistry:
    """Stores, discovers, and retrieves calibration profiles."""

    _DEFAULT_PROFILES = [STANDARD_PROFILE, STRICT_PROFILE, LENIENT_PROFILE]

    def __init__(self):
        self._profiles: dict[str, CalibrationProfile] = {}
        for p in self._DEFAULT_PROFILES:
            self.register(p)

    def register(self, profile: CalibrationProfile) -> None:
        """Register a versioned calibration profile."""
        self._profiles[profile.name.lower()] = profile

    def get_profile(self, name: str) -> CalibrationProfile:
        """Retrieve a calibration profile by name."""
        key = name.lower()
        if key not in self._profiles:
            raise KeyError(f"Unknown calibration profile: '{name}'. Available: {list(self._profiles.keys())}")
        return self._profiles[key]

    def list_profiles(self) -> list[str]:
        """List registered calibration profiles."""
        return sorted(self._profiles.keys())

    @classmethod
    def get(cls, name: str) -> CalibrationProfile:
        """Convenience classmethod to retrieve a profile by name."""
        return cls().get_profile(name)

    @classmethod
    def get_all_profiles(cls) -> list[CalibrationProfile]:
        """Convenience classmethod to retrieve all registered profile instances."""
        registry = cls()
        return [registry.get_profile(k) for k in registry.list_profiles()]
