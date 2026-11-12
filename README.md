# Typosquatting Detector

A dependency-confusion detector implemented with the Python standard library only. It compares an internal dependency list against the complete set of public package names and reports public names that are visually or typographically close to internal packages.

## Usage

```bash
python -m typosquat.cli \
  --internal demo/internal.txt \
  --registry demo/registry.txt \
  --out out/report.json
```

The command prints one summary line containing the internal package count, public package-name count, and number of findings. The JSON report contains:

- `summary`: input sizes, candidate pairs, hit count, and readable distance-call counters.
- `findings`: one object per hit with `internal`, `suspect`, `distance`, `kind`, `risk`, and `internal_version`.

`internal_version` is `null` when the internal list contains no version. Both `name==version` and `name@version` are accepted.

## Distance Algorithms

Both algorithms are separately importable from `typosquat.distance`:

- `levenshtein(left, right)`: insertion, deletion, and substitution each cost one operation.
- `damerau_levenshtein(left, right)`: the optimal-string-alignment variant; one adjacent transposition costs one operation.

Example:

```python
from typosquat.distance import levenshtein, damerau_levenshtein

levenshtein("abcde", "abdce")            # 2
damerau_levenshtein("abcde", "abdce")    # 1
```

The detector uses Levenshtein for the formal candidate gate and Damerau-Levenshtein for the reported distance of ordinary edits, so adjacent swaps are reported as distance 1 and labeled `换位`.

## Confusable Equivalence

The confusable table is implemented in `typosquat/confusables.py`:

| Rule | Equivalent forms |
| --- | --- |
| Lowercase L / digit one | `l` ↔ `1` |
| Uppercase I / lowercase L | `I` ↔ `l` |
| Letter O / zero | `o` ↔ `0` |
| Letter M / adjacent sequence | `rn` ↔ `m`, `nn` ↔ `m` |
| Letter W / adjacent sequence | `vv` ↔ `w` |
| Letter S / five | `s` ↔ `5` |
| Letter D / adjacent sequence | `cl` ↔ `d` |

Confusable detection is alignment based. A pair is labeled `混淆字符` only when the complete difference is explained by one explicit equivalence edit. Ordinary insertion or deletion of a non-confusable character keeps its ordinary label, such as `插入` or `删除`.

## Candidate And Risk Rules

A pair enters distance evaluation only when it satisfies either blocking condition:

- It can share a subsequence after at most two character deletions, which is necessary for Levenshtein distance ≤ 2; or
- Its first two characters match and its length difference is at most 2.

The detector then computes Levenshtein and keeps only pairs whose true distance is at most 2. Exact same-name packages are always skipped because they belong to version reconciliation, not typosquatting.

Risk classification:

- `高风险`: a confusable-equivalent pair, or an ordinary edit with Damerau-Levenshtein distance 1.
- `中风险`: distance 2 and the internal name length is at least 5.
- Other pairs are not reported.

The possible ordinary-edit labels are `字符替换`, `插入`, `删除`, `换位`, and `混淆字符`.

## Performance

A naive scan performs all `internal_count × registry_count` Levenshtein calls. This package blocks names by prefix, length difference, and deletion signatures before invoking distance code.

The scale fixture contains 500 internal names and 5,000 registry names. The measured scan uses 230,058 Levenshtein calls, below the required limit of 1,500,000. The count is available through:

```python
from typosquat.distance import levenshtein_call_count, reset_distance_counters

reset_distance_counters()
# run detect(...)
levenshtein_call_count()
```

The same count is written to the report field `summary.levenshtein_calls`.

## Fixtures And Tests

Regenerate deterministic fixtures:

```bash
python -m fixtures.generate_fixtures
```

Generated files:

- `demo/internal.txt`: the 12 required internal packages plus `foo1bar` and `abcde`.
- `demo/registry.txt`: exactly 200 deterministic public names, including same-name packages and planted confusion names.
- `fixtures/large_internal.txt`: 500 internal names.
- `fixtures/large_registry.txt`: 5,000 public names.

Run tests:

```bash
python -m unittest test_typosquat -v
```
