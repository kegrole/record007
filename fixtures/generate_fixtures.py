"""Generate deterministic demo and scale-test fixtures.

The output only depends on the fixed random seed and the rules in this module,
so regenerating fixtures produces byte-identical files and therefore identical
detection result sets.

Usage:
    python -m fixtures.generate_fixtures
    python -m fixtures.generate_fixtures --large-only
"""

import argparse
import os
import random
from typing import List, Sequence, Tuple

from typosquat.candidates import build_registry_index, parse_requirement
from typosquat.distance import damerau_levenshtein, levenshtein

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# The twelve required internal packages plus two rule-specific packages.
DEMO_INTERNAL_LINES = [
    "requests==2.31.0",
    "urllib3==2.2.1",
    "pyyaml@6.0.1",
    "colorama==0.4.6",
    "numpy@1.26.4",
    "pandas==2.2.2",
    "click==8.1.7",
    "jinja2@3.1.4",
    "rich==13.7.1",
    "flask==3.0.3",
    "boto3==1.34.0",
    "tenacity",
    # Rule-specific: confusable equivalence and adjacent transposition.
    "foo1bar",
    "abcde",
]

# Exact-name public packages (version reconciliation, never confusion hits).
SAME_NAME_PACKAGES = [
    "requests",
    "urllib3",
    "pyyaml",
    "colorama",
    "numpy",
    "pandas",
    "click",
    "jinja2",
    "rich",
    "flask",
    "boto3",
    "tenacity",
]

# Explicit confusion/typo pairs required by the acceptance rules.
PLANTED_SUSPECTS = [
    "requsts",       # requests, one deletion, distance 1
    "colourama",     # colorama, one insertion, distance 1
    "nuimpy",        # numpy, one insertion, distance 1
    "clicxk",        # click, one insertion, distance 1
    "foobar",        # foo1bar: 1 <-> l confusable equivalence
    "abdce",         # abcde: adjacent transposition, distance 1
]

REGISTRY_TARGET_SIZE = 200
LARGE_INTERNAL_COUNT = 500
LARGE_REGISTRY_COUNT = 5000


def _write_lines(path: str, lines: Sequence[str]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write("\n".join(lines))
        handle.write("\n")


def _internal_names(lines: Sequence[str]) -> List[str]:
    return [parse_requirement(line).name for line in lines]


def _is_filler_safe(
    candidate: str,
    internal_names: Sequence[str],
    registry_names: Sequence[str],
) -> bool:
    if candidate in registry_names or candidate in internal_names:
        return False
    index = build_registry_index(registry_names + list(internal_names))
    # Keep fillers far from every internal name so only planted pairs can hit.
    for internal in internal_names:
        if candidate[:2] != internal[:2]:
            continue
        if abs(len(candidate) - len(internal)) > 2:
            continue
        if levenshtein(internal, candidate) <= 2:
            return False
        if damerau_levenshtein(internal, candidate) <= 2:
            return False
    # Also avoid accidental filler-vs-filler confusion inside the registry.
    for existing in index.prefix_matches(candidate):
        if abs(len(existing) - len(candidate)) <= 2 and levenshtein(existing, candidate) <= 2:
            return False
    return True


def _random_name(rng: random.Random) -> str:
    vowels = "aeiou"
    consonants = "bcdfghjklmnpqrstvwxz"
    length = rng.randint(6, 14)
    parts: List[str] = []
    for position in range(length):
        alphabet = vowels if position % 2 else consonants
        parts.append(rng.choice(alphabet))
    return "".join(parts)


def generate_demo() -> Tuple[str, str]:
    rng = random.Random(20261112)
    internal_names = _internal_names(DEMO_INTERNAL_LINES)
    registry: List[str] = list(dict.fromkeys(SAME_NAME_PACKAGES + PLANTED_SUSPECTS))

    while len(registry) < REGISTRY_TARGET_SIZE:
        candidate = _random_name(rng)
        if _is_filler_safe(candidate, internal_names, registry):
            registry.append(candidate)

    internal_path = os.path.join(ROOT, "demo", "internal.txt")
    registry_path = os.path.join(ROOT, "demo", "registry.txt")
    _write_lines(internal_path, DEMO_INTERNAL_LINES)
    _write_lines(registry_path, registry)
    return internal_path, registry_path


def generate_large() -> Tuple[str, str]:
    rng = random.Random(77001234)
    internal: List[str] = []
    while len(internal) < LARGE_INTERNAL_COUNT:
        candidate = "pkg" + _random_name(rng) + str(rng.randint(100, 9999))
        if candidate not in internal:
            internal.append(candidate)

    # Plant one known typo per internal package to make the scale scan
    # non-trivial while retaining deterministic expected findings.
    registry: List[str] = list(internal)
    planted: List[str] = []
    for name in internal:
        if len(name) > 6:
            planted.append(name[:3] + name[4:])  # delete the fourth character
        else:
            planted.append(name + "z")
    registry.extend(planted)

    while len(set(registry)) < LARGE_REGISTRY_COUNT:
        candidate = "pub" + _random_name(rng) + str(rng.randint(10000, 99999))
        if candidate not in registry:
            registry.append(candidate)

    # Deduplicate while preserving deterministic order.
    registry = list(dict.fromkeys(registry))
    internal_path = os.path.join(ROOT, "fixtures", "large_internal.txt")
    registry_path = os.path.join(ROOT, "fixtures", "large_registry.txt")
    _write_lines(internal_path, internal)
    _write_lines(registry_path, registry)
    return internal_path, registry_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate deterministic detector fixtures.")
    parser.add_argument("--large-only", action="store_true", help="Generate only the 500x5000 files.")
    parser.add_argument("--demo-only", action="store_true", help="Generate only the demo files.")
    args = parser.parse_args()

    if not args.large_only:
        internal_path, registry_path = generate_demo()
        print(f"demo fixtures: {internal_path}, {registry_path}")
    if not args.demo_only:
        internal_path, registry_path = generate_large()
        print(f"large fixtures: {internal_path}, {registry_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
