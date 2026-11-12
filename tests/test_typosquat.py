"""Acceptance tests for the dependency-confusion / typosquatting detector.

Run with either:
    python -m unittest test_typosquat -v
    python -m unittest discover -s tests -v
"""

import json
import os
import subprocess
import sys
import tempfile
import unittest

from typosquat.candidates import (
    build_registry_index,
    iter_candidate_pairs,
    parse_requirement,
    read_registry,
    read_requirements,
)
from typosquat.confusables import (
    canonicalize,
    confusable_distance,
    is_confusable_equivalent,
)
from typosquat.detector import detect
from typosquat.distance import (
    damerau_levenshtein,
    edit_kind,
    levenshtein,
    levenshtein_call_count,
    reset_distance_counters,
)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEMO_INTERNAL = os.path.join(ROOT, "demo", "internal.txt")
DEMO_REGISTRY = os.path.join(ROOT, "demo", "registry.txt")
LARGE_INTERNAL = os.path.join(ROOT, "fixtures", "large_internal.txt")
LARGE_REGISTRY = os.path.join(ROOT, "fixtures", "large_registry.txt")

REQUIRED_INTERNAL = [
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

REQUIRED_SUSPECTS = {
    ("requests", "requsts"),
    ("colorama", "colourama"),
    ("numpy", "nuimpy"),
    ("click", "clicxk"),
}

FINDING_KEYS = {
    "internal",
    "suspect",
    "distance",
    "kind",
    "risk",
    "internal_version",
}


class DistanceAlgorithmTest(unittest.TestCase):
    def test_levenshtein_basic_operations(self) -> None:
        self.assertEqual(levenshtein("abc", "abc"), 0)
        self.assertEqual(levenshtein("cat", "car"), 1)       # substitution
        self.assertEqual(levenshtein("cat", "cats"), 1)      # insertion
        self.assertEqual(levenshtein("cats", "cat"), 1)      # deletion
        self.assertEqual(levenshtein("kitten", "sitting"), 3)

    def test_damerau_levenshtein_adjacent_transposition_is_one(self) -> None:
        # Adjacent swap costs one under Damerau-Levenshtein, but two under
        # ordinary Levenshtein.
        self.assertEqual(levenshtein("abcde", "abdce"), 2)
        self.assertEqual(damerau_levenshtein("abcde", "abdce"), 1)
        self.assertEqual(damerau_levenshtein("ca", "ac"), 1)
        self.assertEqual(damerau_levenshtein("kitten", "sitting"), 3)

    def test_edit_kind_labels(self) -> None:
        self.assertEqual(edit_kind("cat", "car", 1), "字符替换")
        self.assertEqual(edit_kind("cat", "cats", 1), "插入")
        self.assertEqual(edit_kind("cats", "cat", 1), "删除")
        self.assertEqual(edit_kind("abcde", "abdce", 1), "换位")


class ConfusableTest(unittest.TestCase):
    def test_required_equivalence_table(self) -> None:
        self.assertEqual(canonicalize("l"), canonicalize("1"))
        self.assertEqual(canonicalize("I"), canonicalize("l"))
        self.assertEqual(canonicalize("o"), canonicalize("0"))
        self.assertEqual(canonicalize("rn"), canonicalize("m"))
        self.assertEqual(canonicalize("vv"), canonicalize("w"))
        self.assertEqual(canonicalize("s"), canonicalize("5"))
        self.assertEqual(canonicalize("cl"), canonicalize("d"))
        self.assertEqual(canonicalize("nn"), canonicalize("m"))

        equivalent_pairs = [
            ("l", "1"),
            ("I", "l"),
            ("o", "0"),
            ("rn", "m"),
            ("nn", "m"),
            ("vv", "w"),
            ("s", "5"),
            ("cl", "d"),
        ]
        for left, right in equivalent_pairs:
            self.assertEqual(confusable_distance(left, right), 0)

    def test_ordinary_insertion_is_not_confusable(self) -> None:
        # The inserted letter is not itself a confusable substitution.
        self.assertFalse(is_confusable_equivalent("colorama", "colourama"))
        self.assertFalse(is_confusable_equivalent("numpy", "nuimpy"))

    def test_foo1bar_foobar_is_confusable_high_risk(self) -> None:
        self.assertTrue(is_confusable_equivalent("foo1bar", "foobar"))
        self.assertEqual(confusable_distance("foo1bar", "foobar"), 1)
        findings, _ = detect(
            [parse_requirement("foo1bar")],
            ["foobar"],
        )
        self.assertEqual(len(findings), 1)
        finding = findings[0]
        self.assertEqual(finding.internal, "foo1bar")
        self.assertEqual(finding.suspect, "foobar")
        self.assertEqual(finding.kind, "混淆字符")
        self.assertEqual(finding.risk, "高风险")

    def test_transposition_pair_is_reported(self) -> None:
        findings, _ = detect([parse_requirement("abcde")], ["abdce"])
        self.assertEqual(len(findings), 1)
        finding = findings[0]
        self.assertEqual(finding.distance, 1)
        self.assertEqual(finding.kind, "换位")
        self.assertEqual(finding.risk, "高风险")


class ParsingAndCandidateTest(unittest.TestCase):
    def test_parse_name_equals_and_at_versions(self) -> None:
        self.assertEqual(parse_requirement("requests==2.31.0").version, "2.31.0")
        self.assertEqual(parse_requirement("pyyaml@6.0.1").version, "6.0.1")
        self.assertIsNone(parse_requirement("tenacity").version)
        self.assertIsNone(parse_requirement("# comment"))

    def test_candidate_gate_rejects_distant_and_wrong_prefix_pairs(self) -> None:
        requirements = [parse_requirement("internalpkg")]
        index = build_registry_index(
            [
                "internxpkg",    # same prefix, length diff 0, distance 1 -> candidate
                "xnternalpkg",   # different first char, but distance 1 -> candidate
                "zzzzzzzzzz",    # distant and different first two chars -> blocked
                "internalpkg99", # length diff 2 -> candidate
                "internalpkg999",# length diff 3 -> blocked
            ]
        )
        pairs = list(iter_candidate_pairs(requirements, index))
        suspects = {suspect for _, suspect in pairs}
        self.assertEqual(
            suspects,
            {"internxpkg", "xnternalpkg", "internalpkg99"},
        )


class DemoFixtureTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.requirements = read_requirements(DEMO_INTERNAL)
        cls.registry = read_registry(DEMO_REGISTRY)
        cls.findings, cls.stats = detect(cls.requirements, cls.registry)
        cls.pairs = {(finding.internal, finding.suspect): finding for finding in cls.findings}

    def test_fixture_sizes_and_required_names(self) -> None:
        internal_names = [requirement.name for requirement in self.requirements]
        self.assertEqual(len(self.requirements), 14)
        for name in REQUIRED_INTERNAL:
            self.assertIn(name, internal_names)
        self.assertEqual(len(self.registry), 200)
        for name in REQUIRED_INTERNAL:
            self.assertIn(name, self.registry)

    def test_exact_four_core_typo_pairs_are_reported(self) -> None:
        for internal, suspect in REQUIRED_SUSPECTS:
            self.assertIn((internal, suspect), self.pairs)
        core_pairs = {
            pair for pair in self.pairs if pair[0] in {name for name, _ in REQUIRED_SUSPECTS}
        }
        self.assertSetEqual(core_pairs, REQUIRED_SUSPECTS)

    def test_core_pair_risk_and_distance(self) -> None:
        expected = {
            ("requests", "requsts"): (1, "高风险"),
            ("colorama", "colourama"): (1, "高风险"),
            ("numpy", "nuimpy"): (1, "高风险"),
            ("click", "clicxk"): (1, "高风险"),
        }
        for pair, (distance, risk) in expected.items():
            finding = self.pairs[pair]
            self.assertEqual(finding.distance, distance, pair)
            self.assertEqual(finding.risk, risk, pair)

    def test_same_name_packages_are_never_reported(self) -> None:
        reported_pairs = set(self.pairs)
        for name in REQUIRED_INTERNAL:
            self.assertNotIn((name, name), reported_pairs)

    def test_distant_packages_are_not_reported(self) -> None:
        # Every filler was generated to be at distance > 2; every finding must
        # therefore be one of the deterministic planted pairs.
        allowed = REQUIRED_SUSPECTS | {
            ("foo1bar", "foobar"),
            ("abcde", "abdce"),
        }
        self.assertEqual(set(self.pairs), allowed)
        self.assertEqual(len(self.findings), 6)

    def test_every_finding_has_complete_json_fields_and_versions(self) -> None:
        for finding in self.findings:
            self.assertEqual(set(finding.to_dict()), FINDING_KEYS)
        self.assertEqual(self.pairs[("requests", "requsts")].internal_version, "2.31.0")
        pyyaml_requirement = next(item for item in self.requirements if item.name == "pyyaml")
        self.assertEqual(pyyaml_requirement.version, "6.0.1")


class RiskRuleTest(unittest.TestCase):
    def test_medium_risk_requires_distance_two_and_length_at_least_five(self) -> None:
        findings, _ = detect([parse_requirement("abcde")], ["abxye"])
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].distance, 2)
        self.assertEqual(findings[0].risk, "中风险")

        findings, _ = detect([parse_requirement("abcd")], ["abpq"])
        self.assertEqual(findings, [])

    def test_short_distance_two_name_is_not_reported(self) -> None:
        findings, _ = detect([parse_requirement("abc")], ["abd"])  # distance 1, high
        self.assertEqual(len(findings), 1)
        findings_two, _ = detect([parse_requirement("ab")], ["xy"])  # prefix gate blocks
        self.assertEqual(findings_two, [])


class PerformanceCounterTest(unittest.TestCase):
    def test_large_scan_stays_under_levenshtein_budget(self) -> None:
        requirements = read_requirements(LARGE_INTERNAL)
        registry = read_registry(LARGE_REGISTRY)
        self.assertEqual(len(requirements), 500)
        self.assertEqual(len(set(registry)), 5000)

        reset_distance_counters()
        findings, stats = detect(requirements, registry)

        self.assertLessEqual(
            levenshtein_call_count(),
            1_500_000,
            msg=f"actual Levenshtein calls: {levenshtein_call_count()}",
        )
        self.assertEqual(stats.levenshtein_calls, levenshtein_call_count())
        self.assertGreater(len(findings), 0)

    def test_counter_is_readable_and_reset(self) -> None:
        reset_distance_counters()
        levenshtein("abc", "abd")
        self.assertEqual(levenshtein_call_count(), 1)
        reset_distance_counters()
        self.assertEqual(levenshtein_call_count(), 0)


class CliAndReportTest(unittest.TestCase):
    def test_cli_writes_report_and_prints_summary(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output = os.path.join(temporary, "nested", "report.json")
            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "typosquat.cli",
                    "--internal",
                    DEMO_INTERNAL,
                    "--registry",
                    DEMO_REGISTRY,
                    "--out",
                    output,
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=True,
            )
            self.assertIn("内部包数", completed.stdout)
            self.assertIn("公共包名数", completed.stdout)
            self.assertIn("命中数", completed.stdout)
            with open(output, "r", encoding="utf-8") as handle:
                report = json.load(handle)
            self.assertEqual(len(report["findings"]), 6)
            for finding in report["findings"]:
                self.assertEqual(set(finding), FINDING_KEYS)
            self.assertIn("levenshtein_calls", report["summary"])


if __name__ == "__main__":
    unittest.main()
