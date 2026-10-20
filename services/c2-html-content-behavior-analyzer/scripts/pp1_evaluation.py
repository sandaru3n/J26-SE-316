"""Part 10: PP1 evaluation - consolidates the saved baseline results (trains nothing).

Thin CLI wrapper - all logic lives in ``c2_analyzer.evaluation``.

    python scripts/pp1_evaluation.py --freeze          # once: write data/splits/v0.3/pp1_eval.json
    python scripts/pp1_evaluation.py                   # the frozen PP1 set (configs/pp1.yaml: v0.3)
    python scripts/pp1_evaluation.py --version v0.4    # any other version only when named

Refuses to run without the frozen split (pp1_eval.json) or when the manifest / split changed.
Outputs: reports/pp1/{pp1_evaluation.md, pp1_evaluation.json, figures/}.
"""

from __future__ import annotations

import argparse
import sys
import time


def _pct(value) -> str:
    return "—" if value is None else f"{100 * value:.1f} %"


def print_summary(report: dict) -> None:
    from c2_analyzer.evaluation.pp1 import SCALARS

    print(f"\nPP1 EVALUATION - {report['version']} (test n={report['frozen']['n_test']})")
    for s in report["skipped"]:
        print(f"SKIPPED {s['display']}: {s['reason']}")
    header = f"{'row':<30}" + "".join(f"{c[:12]:>13}" for c in SCALARS) + f"{'95 % CI':>17}"
    print(header)
    print("-" * len(header))
    for r in report["rows"]:
        cells = "".join(
            f"{_pct(r['test'][c]) if c == 'benign_fpr' else format(r['test'][c], '.3f'):>13}"
            for c in SCALARS
        )
        ci = r["test_macro_f1_ci"]
        print(f"{r['display'][:30]:<30}{cells}   [{ci['ci_low']:.3f}, {ci['ci_high']:.3f}]")
    print(
        f"\ncross-check: {len(report['cross_check'])} numbers, "
        f"{len(report['mismatches'])} mismatch(es)"
    )
    for m in report["mismatches"]:
        print(
            f"  MISMATCH {m['row']} {m['metric']}: {m['ours']} vs {m['reported']} ({m['source']})"
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--version", default=None, help="dataset version (default: the frozen PP1 version)"
    )
    parser.add_argument(
        "--freeze",
        action="store_true",
        help="write pp1_eval.json if missing (an existing different one is refused)",
    )
    parser.add_argument("--no-figures", action="store_true")
    args = parser.parse_args(argv)

    from c2_analyzer.evaluation.pp1 import PP1Config, PP1Error, resolve_version, run
    from c2_analyzer.evaluation.pp1_report import write_reports

    config = PP1Config.load()
    version = resolve_version(args.version, config)
    started = time.perf_counter()
    try:
        report = run(version, config, do_freeze=args.freeze)
    except (PP1Error, FileNotFoundError, ValueError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2
    paths = write_reports(report, config.reports_dir(version), figures=not args.no_figures)
    print_summary(report)
    print(
        f"\nwrote {paths[0].parent} ({len(paths)} files) in {time.perf_counter() - started:.1f} s"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
