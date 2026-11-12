"""Deterministic input parsing and cheap candidate blocking.

The expensive edit distance must never run for every internal/registry pair.
Names are blocked through prefix buckets plus deletion signatures, and only
pairs whose length difference is at most two survive. Levenshtein then applies
the formal ``distance <= 2`` part of the candidate rule.
"""

from collections import defaultdict
from itertools import combinations
from typing import Dict, Iterable, Iterator, List, Optional, Sequence, Set, Tuple

__all__ = [
    "Requirement",
    "parse_requirement",
    "read_requirements",
    "read_registry",
    "RegistryIndex",
    "build_registry_index",
    "iter_candidate_pairs",
]


class Requirement:
    """An internal package requirement and its optional pinned version."""

    __slots__ = ("name", "version")

    def __init__(self, name: str, version: Optional[str] = None) -> None:
        self.name = name
        self.version = version

    def __repr__(self) -> str:
        return f"Requirement(name={self.name!r}, version={self.version!r})"

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Requirement):
            return NotImplemented
        return self.name == other.name and self.version == other.version


def parse_requirement(line: str) -> Optional[Requirement]:
    """Parse ``name==version`` and ``name@version`` lines.

    Blank lines and lines starting with ``#`` are ignored. Names are lowercased
    because package indexes treat names case-insensitively.
    """
    text = line.strip()
    if not text or text.startswith("#"):
        return None

    version: Optional[str] = None
    if "==" in text:
        name, version = text.split("==", 1)
    elif "@" in text:
        name, version = text.split("@", 1)
    else:
        name = text

    name = name.strip().lower()
    version = version.strip() if version is not None else None
    if not name:
        return None
    return Requirement(name=name, version=version or None)


def _read_nonempty_lines(path: str) -> List[str]:
    with open(path, "r", encoding="utf-8") as handle:
        return [
            line.strip()
            for line in handle
            if line.strip() and not line.lstrip().startswith("#")
        ]


def read_requirements(path: str) -> List[Requirement]:
    requirements: List[Requirement] = []
    for line in _read_nonempty_lines(path):
        requirement = parse_requirement(line)
        if requirement is not None:
            requirements.append(requirement)
    return requirements


def read_registry(path: str) -> List[str]:
    return [line.lower() for line in _read_nonempty_lines(path)]


def _prefix_key(name: str) -> str:
    return name[:2] if len(name) >= 2 else name


def deletion_signatures(name: str, max_deletions: int = 2) -> Set[str]:
    """Return subsequences formed by deleting at most ``max_deletions`` chars.

    Two strings with Levenshtein distance at most two share a subsequence
    obtainable by deleting at most two characters from each side. Indexing those
    signatures catches first-character typos without scanning the full registry.
    """
    signatures = {name}
    limit = min(max_deletions, len(name))
    for deletion_count in range(1, limit + 1):
        for removed in combinations(range(len(name)), deletion_count):
            removed_positions = set(removed)
            signatures.add(
                "".join(char for index, char in enumerate(name) if index not in removed_positions)
            )
    return signatures


class RegistryIndex:
    """Block registry names by prefix to avoid the quadratic full scan."""

    def __init__(self, names: Sequence[str]) -> None:
        self.names = sorted(set(names))
        self._by_prefix: Dict[str, List[str]] = defaultdict(list)
        self._by_signature: Dict[str, Set[str]] = defaultdict(set)
        for name in self.names:
            self._by_prefix[_prefix_key(name)].append(name)
            for signature in deletion_signatures(name):
                self._by_signature[signature].add(name)
        for values in self._by_prefix.values():
            values.sort()

    def prefix_matches(self, name: str) -> List[str]:
        return list(self._by_prefix.get(_prefix_key(name), []))

    def signature_matches(self, name: str) -> Set[str]:
        matches: Set[str] = set()
        for signature in deletion_signatures(name):
            matches.update(self._by_signature.get(signature, set()))
        return matches


def build_registry_index(names: Iterable[str]) -> RegistryIndex:
    return RegistryIndex(list(names))


def iter_candidate_pairs(
    requirements: Sequence[Requirement],
    registry: RegistryIndex,
) -> Iterator[Tuple[Requirement, str]]:
    """Yield pairs passing the cheap blocking part of the candidate rule.

    Formal candidate rule: Levenshtein distance <= 2, OR length difference <= 2
    with identical first two characters. Signature blocking preserves the first
    condition even when an edit changes one of the first two characters; the
    detector then computes Levenshtein and rejects false blocking matches.
    """
    for requirement in requirements:
        internal_name = requirement.name
        blocked_names = set(registry.prefix_matches(internal_name))
        blocked_names.update(registry.signature_matches(internal_name))
        for public_name in sorted(blocked_names):
            if abs(len(public_name) - len(internal_name)) <= 2:
                yield requirement, public_name
