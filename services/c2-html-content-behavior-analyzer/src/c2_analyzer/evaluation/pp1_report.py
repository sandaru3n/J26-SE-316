"""PP1 evaluation report: pp1_evaluation.md / .json + confusion-matrix figures.

Part 10: PP1 Evaluation.

Only formats what ``pp1.run`` computed (no metric is computed here). The output has no
timestamp of its own (only the frozen set's created_at), so a re-run on the same saved
predictions writes identical files.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
from matplotlib.figure import Figure

from c2_analyzer.classifiers.dom_baseline.evaluate import confusion_text, plot_confusion_matrix
from c2_analyzer.evaluation.pp1 import LANGUAGES, SCALARS
from c2_analyzer.utils.io import atomic_write_text, write_json

COLUMNS = {
    "accuracy": "Accuracy",
    "macro_precision": "Macro-P",
    "macro_recall": "Macro-R",
    "macro_f1": "Macro-F1",
    "weighted_f1": "Weighted-F1",
    "benign_fpr": "Benign FPR",
}


def _num(value) -> str:
    return "—" if value is None else f"{value:.3f}"


def _pct(value) -> str:
    return "—" if value is None else f"{100 * value:.1f} %"


def _fmt(column: str, value) -> str:
    return _pct(value) if column == "benign_fpr" else _num(value)


def _table(headers: list[str], rows: list[list[str]]) -> list[str]:
    lines = ["| " + " | ".join(headers) + " |", "|" + "---|" * len(headers)]
    return lines + ["| " + " | ".join(row) + " |" for row in rows]


def _flag(n: int, threshold: int) -> str:
    return f"{n} †" if n < threshold else str(n)


def distribution_lines(name: str, dist: dict, labels: list[str]) -> list[str]:
    t = dist["small_cell_threshold"]
    buckets = list(dist["by_language"])
    lines = [f"### {name} (n = {dist['n']})", ""]
    lines += _table(
        ["class", "n", "%"],
        [[c, _flag(v["n"], t), f"{100 * v['pct']:.1f}"] for c, v in dist["by_class"].items()],
    )
    lines += [""]
    lines += _table(
        ["language", "n", "%"],
        [[b, _flag(v["n"], t), f"{100 * v['pct']:.1f}"] for b, v in dist["by_language"].items()],
    )
    lines += [""]
    lines += _table(
        ["class \\ language", *buckets, "total"],
        [
            [c]
            + [_flag(dist["class_by_language"][c][b], t) for b in buckets]
            + [str(dist["by_class"][c]["n"])]
            for c in labels
        ],
    )
    declared = ", ".join(f"{k} {v}" for k, v in sorted(dist["declared_language"].items()))
    lines += [
        "",
        f"† = n < {t} ({len(dist['small_cells'])} of {len(labels) * len(buckets)} class × "
        f"language cells). Manifest (declared) language: {declared}.",
        "",
    ]
    return lines


def _best(report: dict, key: str, column: str, text: str) -> str:
    if key in report["best_single_per_column"].get(column, []):
        text = f"_{text}_"
    return f"**{text}**" if key in report["best_per_column"].get(column, []) else text


def comparison_lines(report: dict) -> list[str]:
    rows = report["rows"]
    lines = [
        "## 4. Baseline comparison",
        "",
        "### Test (frozen 68 pages, argmax)",
        "",
        "Best value per column in **bold** over all rows, _italic_ = best single-modality "
        "row (lowest for benign FPR). Macro-F1 with the paired "
        "bootstrap 95 % CI (1,000 resamples, seed 42 - the Part 9A settings).",
        "",
    ]
    body = []
    for r in rows:
        cells = [r["display"], r["part"], r["model"]]
        for column in SCALARS:
            text = _fmt(column, r["test"][column])
            if column == "macro_f1":
                ci = r["test_macro_f1_ci"]
                text = _best(report, r["key"], column, text)
                text += f" [{ci['ci_low']:.3f}, {ci['ci_high']:.3f}]"
                cells.append(text)
            else:
                cells.append(_best(report, r["key"], column, text))
        body.append(cells)
    lines += _table(["row", "part", "model", *COLUMNS.values()], body)
    lines += ["", "### CV (train+val, 5 grouped folds, mean ± std)", ""]
    body = []
    for r in rows:
        cells = [r["display"]]
        for column in SCALARS:
            mean, std = r["cv"]["mean"].get(column), r["cv"]["std"].get(column)
            if mean is None:
                cells.append("—")
            elif column == "benign_fpr":
                cells.append(f"{100 * mean:.1f} ± {100 * std:.1f} %")
            else:
                cells.append(f"{mean:.3f} ± {std:.3f}")
        body.append(cells)
    lines += _table(["row", *COLUMNS.values()], body)
    notes = [f"- {r['display']}: {r['note']}" for r in rows if r.get("note")]
    lines += [""] + notes + ([""] if notes else [])

    seeds = report.get("xlmr_seeds")
    if seeds:
        lines += ["### Text XLM-R over seeds (test)", ""]
        body = [[s] + [_fmt(c, seeds["per_seed"][s][c]) for c in SCALARS] for s in seeds["seeds"]]
        mean, std = seeds["summary"]["mean"], seeds["summary"]["std"]
        body.append(
            ["**mean ± std**"]
            + [
                (
                    f"{100 * mean[c]:.1f} ± {100 * std[c]:.1f} %"
                    if c == "benign_fpr"
                    else f"{mean[c]:.3f} ± {std[c]:.3f}"
                )
                for c in SCALARS
            ]
        )
        lines += _table(["seed", *COLUMNS.values()], body)
        lines += [
            "",
            f"Source: `{seeds['source']}`. The final model is the seed with the best VAL "
            "macro-F1 (Part 6A), not the best test seed.",
            "",
        ]

    labels = report["classes"]
    lines += ["### Per class (test): precision / recall / F1", ""]
    body = []
    for r in rows:
        cells = [r["display"]]
        for label in labels:
            pc = r["test"]["per_class"][label]
            cells.append(f"{pc['precision']:.2f} / {pc['recall']:.2f} / {pc['f1']:.2f}")
        body.append(cells)
    support = rows[0]["test"]["per_class"] if rows else {}
    lines += _table(
        ["row", *[f"{c} (n={support[c]['support']})" for c in labels]] if rows else ["row"],
        body,
    )
    lines += ["", "### Per language (test): accuracy (correct / n)", ""]
    buckets = list(rows[0]["per_language"]) if rows else LANGUAGES
    body = [
        [r["display"]]
        + [
            (
                "—"
                if not r["per_language"][b]["n"]
                else f"{r['per_language'][b]['accuracy']:.2f} ({r['per_language'][b]['correct']}"
                f"/{r['per_language'][b]['n']})" + (" ⚠" if r["per_language"][b]["small_n"] else "")
            )
            for b in buckets
        ]
        for r in rows
    ]
    lines += _table(["row", *buckets], body)
    lines += ["", "⚠ = n below the min_language_support (small-n, anecdotal).", ""]
    return lines


def confusion_lines(report: dict, figures: bool) -> list[str]:
    lines = ["## 5. Confusion matrices (test; rows = true, columns = predicted)", ""]
    if figures:
        lines += ["![confusion grid](figures/confusion_grid.png)", ""]
    for r in report["rows"]:
        lines += [f"### {r['display']}", ""]
        if figures:
            lines += [f"![{r['key']}](figures/confusion_{r['key']}.png)", ""]
        lines += ["```", confusion_text(r["test"]["confusion_matrix"], report["classes"]), "```"]
        lines += [""]
    return lines


def render_markdown(report: dict, figures: bool = True) -> str:
    frozen, check = report["frozen"], report["manifest_check"]
    labels = report["classes"]
    lines = [
        f"# PP1 evaluation - dataset {report['version']}",
        "",
        f"Part 10. {report['rule'].capitalize()}. Re-run: "
        f"`python scripts/pp1_evaluation.py --version {report['version']}`.",
        "",
        "## 1. Evaluation dataset (frozen)",
        "",
    ]
    lines += _table(
        ["item", "value"],
        [
            ["dataset version", report["version"]],
            ["manifest fingerprint", f"`{check['fingerprint']}`"],
            [
                "manifest verification",
                f"{check['files_checked']} files re-hashed: {check['missing']} missing, "
                f"{check['changed']} changed → {'OK' if check['ok'] else 'FAILED'}",
            ],
            ["split fingerprint", f"`{frozen['split_fingerprint']}`"],
            ["CV-folds fingerprint", f"`{frozen['cv_folds_fingerprint']}`"],
            [
                "pages",
                f"train {frozen['n_train']} · val {frozen['n_val']} · test {frozen['n_test']} "
                f"(CV pool = train+val = {frozen['n_train'] + frozen['n_val']})",
            ],
            ["frozen", f"{frozen['created_at']} - `data/splits/{report['version']}/pp1_eval.json`"],
        ],
    )
    lines += [
        "",
        "Same shared split as every Part (grouped by near-duplicate cluster, stratified by "
        "label × language). Language below = Part 5A detected page language bucket.",
        "",
        "## 2. Distributions",
        "",
    ]
    for scope, name in (("test", "Test"), ("cv_pool", "CV pool (train+val)"), ("all", "All")):
        lines += distribution_lines(name, report["distributions"][scope], labels)

    lines += ["## 3. Models evaluated (saved predictions only)", ""]
    lines += _table(
        ["row", "part", "model", "saved predictions used"],
        [
            [r["display"], r["part"], r["model"], ", ".join(f"`{s}`" for s in r["sources"])]
            for r in report["rows"]
        ],
    )
    if report["skipped"]:
        lines += ["", "**Skipped (saved predictions missing, NOT retrained):**", ""]
        lines += [f"- {s['display']}: {s['reason']}" for s in report["skipped"]]
    lines += [""]
    lines += comparison_lines(report)
    lines += confusion_lines(report, figures)

    checks, mismatches = report["cross_check"], report["mismatches"]
    sources = sorted({c["source"] for c in checks})
    lines += [
        "## 6. Consistency with the existing reports",
        "",
        f"{len(checks)} numbers compared (tolerance 1e-6) with: "
        + ", ".join(f"`{s}`" for s in sources)
        + f". **Mismatches: {len(mismatches)}.**",
        "",
    ]
    if mismatches:
        lines += _table(
            ["row", "source", "metric", "PP1", "reported"],
            [
                [m["row"], m["source"], m["metric"], str(m["ours"]), str(m["reported"])]
                for m in mismatches
            ],
        )
        lines += [""]
    lines += ["## 7. Findings (from the numbers above only)", ""]
    lines += [f"{i}. {text}" for i, text in enumerate(report["findings"], 1)]
    lines += ["", "## 8. Limitations", ""]
    lines += [f"{i}. {text}" for i, text in enumerate(report["limitations"], 1)]
    return "\n".join(lines) + "\n"


def plot_grid(report: dict, path: Path) -> Path:
    """One figure: counts (top) and row-normalised shares (bottom) for every row."""
    rows, labels = report["rows"], report["classes"]
    k = len(rows)
    figure = Figure(figsize=(3.3 * k + 0.6, 7.4), layout="constrained")
    axes = np.atleast_2d(figure.subplots(2, k, squeeze=False))
    for j, r in enumerate(rows):
        counts = np.asarray(r["test"]["confusion_matrix"], dtype=float)
        shares = counts / np.maximum(counts.sum(axis=1, keepdims=True), 1)
        for i, (values, fmt, vmax) in enumerate(
            ((counts, "{:.0f}", counts.max() or 1), (shares, "{:.2f}", 1.0))
        ):
            axis = axes[i, j]
            axis.imshow(values, cmap="Blues", vmin=0, vmax=vmax)
            ticks = range(len(labels))
            axis.set_xticks(ticks, labels if i else [""] * len(labels), rotation=40, ha="right")
            axis.set_yticks(ticks, labels if j == 0 else [""] * len(labels))
            for a in range(len(labels)):
                for b in range(len(labels)):
                    axis.text(
                        b,
                        a,
                        fmt.format(values[a, b]),
                        ha="center",
                        va="center",
                        fontsize=8,
                        color="white" if values[a, b] > vmax / 2 else "black",
                    )
            if i == 0:
                axis.set_title(f"{r['display']}\nmacro-F1 {r['test']['macro_f1']:.3f}", fontsize=9)
        axes[0, 0].set_ylabel("counts\ntrue")
        axes[1, 0].set_ylabel("row-normalised\ntrue")
    figure.suptitle(
        f"PP1 test confusion matrices ({report['version']}, n = {rows[0]['test']['n']})"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(path, dpi=130, metadata={"Software": None})
    return path


def write_reports(report: dict, folder: Path, figures: bool = True) -> list[Path]:
    folder = Path(folder)
    written = []
    if figures and report["rows"]:
        written.append(plot_grid(report, folder / "figures" / "confusion_grid.png"))
        for r in report["rows"]:
            written.append(
                plot_confusion_matrix(
                    r["test"]["confusion_matrix"],
                    report["classes"],
                    f"{r['display']} - test ({report['version']}, n = {r['test']['n']})",
                    folder / "figures" / f"confusion_{r['key']}.png",
                )
            )
    write_json(report, folder / "pp1_evaluation.json")
    atomic_write_text(render_markdown(report, figures), folder / "pp1_evaluation.md")
    return [folder / "pp1_evaluation.md", folder / "pp1_evaluation.json", *written]
