"""Scan internal requirements against a public package-name registry."""

from dataclasses import asdict, dataclass
from typing import List, Optional, Sequence

from .candidates import (
    RegistryIndex,
    Requirement,
    build_registry_index,
    iter_candidate_pairs,
)
from .confusables import confusable_distance, is_confusable_equivalent
from .distance import (
    damerau_levenshtein,
    damerau_levenshtein_call_count,
    edit_kind,
    levenshtein,
    levenshtein_call_count,
    reset_distance_counters,
)

__all__ = ["Finding", "ScanStats", "detect"]

RISK_HIGH = "高风险"
RISK_MEDIUM = "中风险"
KIND_CONFUSABLE = "混淆字符"


@dataclass(frozen=True)
class Finding:
    """One reported typosquatting candidate."""

    internal: str
    suspect: str
    distance: int
    kind: str
    risk: str
    internal_version: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class ScanStats:
    """Readable counters describing how much distance work was performed."""

    internal_count: int
    registry_count: int
    candidate_pairs: int
    levenshtein_calls: int
    damerau_levenshtein_calls: int
    finding_count: int

    def to_dict(self) -> dict:
        return asdict(self)


def detect(
    requirements: Sequence[Requirement],
    registry_names: Sequence[str],
) -> tuple:
    """Return ``(findings, stats)`` for internal requirements and registry.

    Same-name public packages are never reported. Confusable equivalence takes
    precedence when it explains the pair; otherwise Damerau-Levenshtein gives
    the reported distance so adjacent transpositions count as one operation.
    """
    reset_distance_counters()
    registry = build_registry_index(registry_names)
    findings: List[Finding] = []
    candidate_pairs = 0

    for requirement, public_name in iter_candidate_pairs(requirements, registry):
        internal_name = requirement.name

        # Same-name packages belong to version reconciliation, not confusion.
        if internal_name == public_name:
            continue

        candidate_pairs += 1

        # Formal candidate gate: real Levenshtein distance must be <= 2.
        plain_distance = levenshtein(internal_name, public_name)
        if plain_distance > 2:
            continue

        # Confusable look-alikes are a separate high-risk equivalence signal.
        if is_confusable_equivalent(internal_name, public_name):
            findings.append(
                Finding(
                    internal=internal_name,
                    suspect=public_name,
                    distance=max(1, confusable_distance(internal_name, public_name)),
                    kind=KIND_CONFUSABLE,
                    risk=RISK_HIGH,
                    internal_version=requirement.version,
                )
            )
            continue

        distance = damerau_levenshtein(internal_name, public_name)
        if distance > 2:
            continue

        risk = _classify_risk(distance, internal_name)
        if risk is None:
            continue

        findings.append(
            Finding(
                internal=internal_name,
                suspect=public_name,
                distance=distance,
                kind=edit_kind(internal_name, public_name, distance),
                risk=risk,
                internal_version=requirement.version,
            )
        )

    findings = _deduplicate_and_sort(findings)
    stats = ScanStats(
        internal_count=len(requirements),
        registry_count=len(registry.names),
        candidate_pairs=candidate_pairs,
        levenshtein_calls=levenshtein_call_count(),
        damerau_levenshtein_calls=damerau_levenshtein_call_count(),
        finding_count=len(findings),
    )
    return findings, stats


def _classify_risk(distance: int, internal_name: str) -> Optional[str]:
    # Any single-operation typo (substitution, insertion, deletion, adjacent
    # transposition) is immediately attackable and therefore high risk.
    if distance <= 1:
        return RISK_HIGH
    if distance == 2 and len(internal_name) >= 5:
        return RISK_MEDIUM
    return None


def _deduplicate_and_sort(findings: Sequence[Finding]) -> List[Finding]:
    unique = {finding.internal + "\x1f" + finding.suspect: finding for finding in findings}
    return sorted(unique.values(), key=lambda item: (item.internal, item.suspect))
