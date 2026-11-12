"""Dependency-confusion / typosquatting detector (standard library only)."""

from .distance import (
    damerau_levenshtein,
    levenshtein,
    reset_distance_counters,
    levenshtein_call_count,
    damerau_levenshtein_call_count,
)
from .detector import detect, Finding, ScanStats

__all__ = [
    "levenshtein",
    "damerau_levenshtein",
    "reset_distance_counters",
    "levenshtein_call_count",
    "damerau_levenshtein_call_count",
    "detect",
    "Finding",
    "ScanStats",
]

__version__ = "1.0.0"
