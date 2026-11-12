"""Confusable-character equivalence for look-alike package names.

Equivalence is alignment based rather than a global string rewrite. A pair is
confusable only when the single edit separating the names replaces, inserts,
or deletes characters in an explicit equivalence class. This prevents ordinary
typos such as ``colorama`` -> ``colourama`` from being mislabeled because an
unrelated substring happens to resemble another glyph.
"""

__all__ = [
    "CONFUSABLE_SINGLE_CHARS",
    "CONFUSABLE_MULTI_CHARS",
    "canonicalize",
    "confusable_distance",
    "is_confusable_equivalent",
]

# Single-character visual classes: l<->1, I<->l, o<->0, s<->5.
# Lowercase ``i`` is intentionally absent: the rule names uppercase ``I``.
CONFUSABLE_SINGLE_CHARS = {
    "l": frozenset("l1"),
    "1": frozenset("l1"),
    "o": frozenset("o0"),
    "0": frozenset("o0"),
    "s": frozenset("s5"),
    "5": frozenset("s5"),
}

# Multi-character look-alikes and their visual single-character forms.
CONFUSABLE_MULTI_CHARS = {
    "rn": "m",
    "vv": "w",
    "cl": "d",
    "nn": "m",
}

_SINGLE_CANONICAL = {
    "l": "l",
    "1": "l",
    "o": "o",
    "0": "o",
    "s": "s",
    "5": "s",
}

_MULTI_CLASSES = (
    frozenset(("rn", "nn", "m")),
    frozenset(("vv", "w")),
    frozenset(("cl", "d")),
)


def canonicalize(name: str) -> str:
    """Canonical form for documenting and testing the equivalence table."""
    normalized = name.strip().replace("I", "l").lower()
    for sequence, replacement in CONFUSABLE_MULTI_CHARS.items():
        normalized = normalized.replace(sequence, replacement)
    return "".join(_SINGLE_CANONICAL.get(char, char) for char in normalized)


def _single_equivalent(left: str, right: str) -> bool:
    if left == right:
        return False
    left_class = CONFUSABLE_SINGLE_CHARS.get(left)
    right_class = CONFUSABLE_SINGLE_CHARS.get(right)
    return left_class is not None and left_class == right_class


def _multi_equivalent(left: str, right: str) -> bool:
    if not left or not right or left == right:
        return False
    return any(left in group and right in group for group in _MULTI_CLASSES)


def _confusable_substitution_cost(left: str, right: str) -> int:
    if left == right:
        return 0
    if _single_equivalent(left, right):
        return 1
    return 2


def _is_confusable_char(char: str) -> bool:
    return char in CONFUSABLE_SINGLE_CHARS


def _alignment_distance(left: str, right: str) -> int:
    rows = len(left)
    columns = len(right)
    matrix = [[0] * (columns + 1) for _ in range(rows + 1)]
    for row in range(1, rows + 1):
        matrix[row][0] = row
    for column in range(1, columns + 1):
        matrix[0][column] = column

    for row in range(1, rows + 1):
        for column in range(1, columns + 1):
            deletion_cost = 1 if _is_confusable_char(left[row - 1]) else 2
            insertion_cost = 1 if _is_confusable_char(right[column - 1]) else 2
            matrix[row][column] = min(
                matrix[row - 1][column] + deletion_cost,
                matrix[row][column - 1] + insertion_cost,
                matrix[row - 1][column - 1]
                + _confusable_substitution_cost(left[row - 1], right[column - 1]),
            )
            if row >= 2 and _multi_equivalent(left[row - 2 : row], right[column - 1]):
                matrix[row][column] = min(
                    matrix[row][column], matrix[row - 2][column - 1] + 1
                )
            if column >= 2 and _multi_equivalent(left[row - 1], right[column - 2 : column]):
                matrix[row][column] = min(
                    matrix[row][column], matrix[row - 1][column - 2] + 1
                )
    return matrix[rows][columns]


def _canonical_levenshtein(left: str, right: str) -> int:
    if left == right:
        return 0
    if not left:
        return len(right)
    if not right:
        return len(left)
    if len(left) < len(right):
        left, right = right, left
    previous = list(range(len(right) + 1))
    for row, left_char in enumerate(left, start=1):
        current = [row]
        for column, right_char in enumerate(right, start=1):
            cost = 0 if left_char == right_char else 1
            current.append(
                min(
                    previous[column] + 1,
                    current[column - 1] + 1,
                    previous[column - 1] + cost,
                )
            )
        previous = current
    return previous[-1]


def confusable_distance(internal: str, public: str) -> int:
    """Levenshtein distance after applying the documented confusable mapping."""
    internal_lower = internal.strip().replace("I", "l").lower()
    public_lower = public.strip().replace("I", "l").lower()
    return _canonical_levenshtein(
        canonicalize(internal_lower), canonicalize(public_lower)
    )


def is_confusable_equivalent(internal: str, public: str) -> bool:
    """True when one explicit confusable edit explains the whole difference."""
    internal_lower = internal.strip().replace("I", "l").lower()
    public_lower = public.strip().replace("I", "l").lower()
    if internal_lower == public_lower:
        return False
    return _alignment_distance(internal_lower, public_lower) <= 1
