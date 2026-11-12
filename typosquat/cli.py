"""Command-line entry point for the typosquatting detector."""

import argparse
import sys
from typing import List, Optional

try:
    from .candidates import read_registry, read_requirements
    from .detector import detect
    from .report import write_report
except ImportError:  # pragma: no cover - supports direct script execution
    import os

    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from typosquat.candidates import read_registry, read_requirements
    from typosquat.detector import detect
    from typosquat.report import write_report

__all__ = ["build_parser", "main"]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m typosquat.cli",
        description="Detect typosquatting public package names against an internal dependency list.",
    )
    parser.add_argument("--internal", required=True, help="Path to the internal dependency list.")
    parser.add_argument("--registry", required=True, help="Path to the full public package-name list.")
    parser.add_argument("--out", required=True, help="Path for the JSON report.")
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    requirements = read_requirements(args.internal)
    registry_names = read_registry(args.registry)
    findings, stats = detect(requirements, registry_names)
    write_report(args.out, findings, stats)

    print(
        "内部包数: {internal}，公共包名数: {registry}，命中数: {hits}".format(
            internal=stats.internal_count,
            registry=stats.registry_count,
            hits=stats.finding_count,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
