"""Edit-distance algorithms and explicit invocation counters.

Only the Python standard library is used. ``levenshtein`` is the distance used
by the candidate filter, so its invocation count is the metric constrained by
the performance requirement. Counters are public so tests and reports can
reason about the real work performed.
"""

__all__ = [
    "levenshtein",
    "damerau_levenshtein",
    "edit_kind",
    "levenshtein_call_count",
    "damerau_levenshtein_call_count",
    "reset_distance_counters",
]

_LEV_CALLS = 0
_DL_CALLS = 0


def reset_distance_counters() -> None:
    """Reset both edit-distance invocation counters to zero."""
    global _LEV_CALLS, _DL_CALLS
    _LEV_CALLS = 0
    _DL_CALLS = 0


def levenshtein_call_count() -> int:
    """Number of ``levenshtein`` calls since the last reset."""
    return _LEV_CALLS


def damerau_levenshtein_call_count() -> int:
    """Number of ``damerau_levenshtein`` calls since the last reset."""
    return _DL_CALLS


def levenshtein(left: str, right: str) -> int:
    """Classic Levenshtein distance (insert/delete/substitute each cost 1).

    Two-row dynamic programming; memory is O(min(len(left), len(right))).
    """
    global _LEV_CALLS
    _LEV_CALLS += 1

    if left == right:
        return 0
    if not left:
        return len(right)
    if not right:
        return len(left)
    if len(left) < len(right):
        left, right = right, left

    previous = list(range(len(right) + 1))
    for index, left_char in enumerate(left, start=1):
        current = [index]
        for position, right_char in enumerate(right, start=1):
            substitution_cost = 0 if left_char == right_char else 1
            current.append(
                min(
                    previous[position] + 1,
                    current[position - 1] + 1,
                    previous[position - 1] + substitution_cost,
                )
            )
        previous = current
    return previous[-1]


def damerau_levenshtein(left: str, right: str) -> int:
    """Optimal string alignment Damerau-Levenshtein distance.

    An adjacent transposition costs one operation. The restricted (optimal
    string alignment) variant is sufficient for typo detection.
    """
    global _DL_CALLS
    _DL_CALLS += 1

    if left == right:
        return 0
    if not left:
        return len(right)
    if not right:
        return len(left)

    rows = len(left)
    columns = len(right)
    matrix = [[0] * (columns + 1) for _ in range(rows + 1)]
    for row in range(rows + 1):
        matrix[row][0] = row
    for column in range(columns + 1):
        matrix[0][column] = column

    for row in range(1, rows + 1):
        for column in range(1, columns + 1):
            substitution_cost = 0 if left[row - 1] == right[column - 1] else 1
            matrix[row][column] = min(
                matrix[row - 1][column] + 1,
                matrix[row][column - 1] + 1,
                matrix[row - 1][column - 1] + substitution_cost,
            )
            if (
                row > 1
                and column > 1
                and left[row - 1] == right[column - 2]
                and left[row - 2] == right[column - 1]
            ):
                matrix[row][column] = min(
                    matrix[row][column],
                    matrix[row - 2][column - 2] + 1,
                )
    return matrix[rows][columns]


def edit_kind(left: str, right: str, distance: int) -> str:
    """Label the dominant edit class for one reported pair."""
    if left == right:
        return "同名"
    if len(left) == len(right):
        if distance == 1 and _is_adjacent_transposition(left, right):
            return "换位"
        return "字符替换"
    if len(right) > len(left):
        return "插入"
    return "删除"


def _is_adjacent_transposition(left: str, right: str) -> bool:
    mismatches = [
        position
        for position, (left_char, right_char) in enumerate(zip(left, right))
        if left_char != right_char
    ]
    if len(mismatches) != 2:
        return False
    first, second = mismatches
    return (
        second == first + 1
        and left[first] == right[second]
        and left[second] == right[first]
    )
