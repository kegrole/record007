"""JSON report rendering for typosquatting scan results."""

import json
import os
from typing import Sequence

from .detector import Finding, ScanStats

__all__ = ["build_report", "write_report"]

REPORT_SCHEMA_VERSION = 1


def build_report(findings: Sequence[Finding], stats: ScanStats) -> dict:
    """Build a deterministic, JSON-serializable report object."""
    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "summary": {
            "internal_packages": stats.internal_count,
            "registry_packages": stats.registry_count,
            "candidate_pairs": stats.candidate_pairs,
            "hits": stats.finding_count,
            "levenshtein_calls": stats.levenshtein_calls,
            "damerau_levenshtein_calls": stats.damerau_levenshtein_calls,
        },
        "findings": [finding.to_dict() for finding in findings],
    }


def write_report(
    path: str,
    findings: Sequence[Finding],
    stats: ScanStats,
) -> dict:
    """Write the report as UTF-8 JSON and return the rendered object."""
    report = build_report(findings, stats)
    parent = os.path.dirname(os.path.abspath(path))
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2, sort_keys=False)
        handle.write("\n")
    return report
