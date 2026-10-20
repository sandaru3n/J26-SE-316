"""PP1 evaluation: one frozen test set, every single-modality baseline, one table.

Part 10: PP1 Evaluation.

Rules (viva):
- **Nothing is trained or re-fitted here.** Every number comes from SAVED predictions:
  the Part 9A OOF tables ``data/processed/fusion/<v>/oof_<arm>.csv`` (train+val = out-of-fold
  probabilities of models trained on the other grouped folds; test = the arm's final
  model), the Part 6A per-seed predictions ``models/xlmr/<v>/seed_*/predictions.jsonl`` and
  the Part 9A ``reports/ablation/<v>/test_predictions.csv``. A missing file means the row is
  skipped and named in the report, never retrained.
- **The evaluation set is frozen.** ``data/splits/<v>/pp1_eval.json`` pins the split and
  CV-folds fingerprints; every run re-verifies the manifest (every file's sha256), checks
  the split was made from that manifest and refuses a split that differs from the frozen one.
- **Same metric code as the Parts.** Test and per-fold metrics come from
  ``metrics_from_confusion`` (accuracy, macro / per-class P / R / F1, weighted F1, benign
  FPR), CV = mean ± std over the 5 grouped folds, each fold scored on its own pages (as
  Parts 4, 6A, 8 and 9A). ``cross_check`` compares every number with the Part reports and
  lists each mismatch, so an inconsistency cannot hide.
- **Tri-modal reference row:** its CV fold models were re-fitted inside the ablation (weights
  chosen on 4 folds); those fused OOF probabilities were not saved, so its CV numbers are
  read from ablation.json (macro precision was not stored there → "—"; macro recall =
  balanced accuracy). Its test labels come from test_predictions.csv.
- The bootstrap CI reuses Part 9A ``fusion.bootstrap`` with the same settings (1,000 paired
  resamples, seed 42), so it reproduces the ablation's CIs.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

from c2_analyzer.config import load_yaml_config, resolve_path
from c2_analyzer.dataset.manifest import manifests_dir, verify
from c2_analyzer.dataset.metadata import MetadataStore
from c2_analyzer.dataset.splits import check_current, load_split, splits_root
from c2_analyzer.fusion import bootstrap
from c2_analyzer.fusion.common import FusionConfig
from c2_analyzer.fusion.oof import Reference, load_oof, load_reference
from c2_analyzer.utils.io import read_json, write_json

FROZEN_FILE = "pp1_eval.json"
BENIGN = "benign"
LANGUAGES = ["en", "si", "ta", "mixed", "other"]
SCOPES = {"test": ("test",), "cv_pool": ("train", "val"), "all": ("train", "val", "test")}
SCALARS = ("accuracy", "macro_precision", "macro_recall", "macro_f1", "weighted_f1", "benign_fpr")


class PP1Error(RuntimeError):
    """The PP1 evaluation set is missing, changed or not the frozen one."""


@dataclass(frozen=True)
class PP1Config:
    raw: dict

    @classmethod
    def load(cls, config_dir: Path | None = None) -> PP1Config:
        return cls(raw=load_yaml_config("pp1", config_dir))

    @property
    def version(self) -> str:
        return str(self.raw["version"])

    @property
    def rows(self) -> dict[str, dict]:
        return dict(self.raw["rows"])

    def path(self, key: str) -> Path:
        return resolve_path(Path(self.raw["paths"][key]))

    def reports_dir(self, version: str) -> Path:
        root = self.path("reports_dir")
        return root if version == self.version else root / version


def resolve_version(requested: str | None, config: PP1Config) -> str:
    """The frozen PP1 version unless another one is asked for EXPLICITLY."""
    return config.version if requested is None else requested


# ---- 1. the frozen evaluation set ------------------------------------------------------------


def frozen_path(version: str, root: Path | None = None) -> Path:
    return (root or splits_root()) / version / FROZEN_FILE


def frozen_record(ref: Reference, info: dict) -> dict:
    counts = ref.frame["split"].value_counts()
    return {
        "version": ref.version,
        "part": "Part 10 - PP1 evaluation",
        "note": "frozen for PP1",
        "split_fingerprint": ref.split_fingerprint,
        "cv_folds_fingerprint": ref.folds_fingerprint,
        "manifest_fingerprint": info.get("manifest", {}).get("fingerprint"),
        "n_train": int(counts.get("train", 0)),
        "n_val": int(counts.get("val", 0)),
        "n_test": int(counts.get("test", 0)),
        "classes": ref.labels,
    }


def check_frozen(ref: Reference, path: Path) -> dict:
    """The frozen record; PP1Error if there is none or the split is not the frozen one."""
    if not path.is_file():
        raise PP1Error(
            f"no frozen PP1 evaluation set ({path}) - run: "
            f"python scripts/pp1_evaluation.py --version {ref.version} --freeze"
        )
    frozen = read_json(path)
    problems = [
        name
        for name, current in (
            ("version", ref.version),
            ("split_fingerprint", ref.split_fingerprint),
            ("cv_folds_fingerprint", ref.folds_fingerprint),
        )
        if frozen.get(name) != current
    ]
    if problems:
        raise PP1Error(
            f"the split of {ref.version} is not the frozen PP1 set ({', '.join(problems)} "
            f"differ from {path.name}) - PP1 numbers must come from the frozen split"
        )
    return frozen


def freeze(ref: Reference, info: dict, path: Path, clock=datetime.now) -> tuple[dict, bool]:
    """(record, written). An identical frozen file is kept; a different one is refused."""
    if path.is_file():
        return check_frozen(ref, path), False
    record = {
        **frozen_record(ref, info),
        "created_at": clock().astimezone().isoformat(timespec="seconds"),
    }
    write_json(record, path)
    return record, True


@dataclass
class EvalSet:
    ref: Reference
    frozen: dict
    manifest: dict  # verify result summary
    languages: dict[str, str] = field(default_factory=dict)  # Part 5A bucket
    declared: dict[str, str] = field(default_factory=dict)  # manifest language

    @property
    def labels(self) -> list[str]:
        return self.ref.labels


def prepare(version: str, do_freeze: bool = False, store: MetadataStore | None = None) -> EvalSet:
    """Verify the manifest + split, (optionally) freeze, then require the frozen set."""
    store = store or MetadataStore()
    check = verify(store, version)
    if not check.ok:
        raise PP1Error(
            f"dataset {version} failed verification ({len(check.missing)} missing, "
            f"{len(check.changed)} changed file(s)) - PP1 needs the unchanged manifest"
        )
    split, info = load_split(version)
    check_current(info, manifests_dir(store), version)
    ref = load_reference(version)  # also refuses split.csv != split.json fingerprint
    path = frozen_path(version)
    frozen = freeze(ref, info, path)[0] if do_freeze else check_frozen(ref, path)
    from c2_analyzer.fusion.data import load_languages

    return EvalSet(
        ref=ref,
        frozen=frozen,
        manifest={
            "version": version,
            "files_checked": check.checked,
            "missing": len(check.missing),
            "changed": len(check.changed),
            "ok": check.ok,
            "fingerprint": info.get("manifest", {}).get("fingerprint"),
        },
        languages=load_languages(version),
        declared=dict(zip(split["sample_id"], split["language"], strict=True)),
    )


# ---- 2. distributions ------------------------------------------------------------------------


def _share(n: int, total: int) -> float:
    return n / total if total else 0.0


def distribution(
    labels: list[str], y_labels: list[str], languages: list[str], small_cell: int
) -> dict:
    """Counts + shares by class, by language and class × language; cells n < small_cell flagged."""
    frame = pd.DataFrame({"label": y_labels, "language": languages})
    total = len(frame)
    buckets = LANGUAGES + sorted(set(languages) - set(LANGUAGES))
    by_class = {c: int((frame["label"] == c).sum()) for c in labels}
    by_language = {b: int((frame["language"] == b).sum()) for b in buckets}
    cross = {
        c: {b: int(((frame["label"] == c) & (frame["language"] == b)).sum()) for b in buckets}
        for c in labels
    }
    small = [
        {"class": c, "language": b, "n": n}
        for c, row in cross.items()
        for b, n in row.items()
        if n < small_cell
    ]
    return {
        "n": total,
        "by_class": {c: {"n": n, "pct": _share(n, total)} for c, n in by_class.items()},
        "by_language": {b: {"n": n, "pct": _share(n, total)} for b, n in by_language.items()},
        "class_by_language": cross,
        "small_cell_threshold": small_cell,
        "small_cells": small,
        "small_classes": [c for c, n in by_class.items() if n < small_cell],
        "small_languages": [b for b, n in by_language.items() if n < small_cell],
    }


def distributions(data: EvalSet, small_cell: int) -> dict:
    frame = data.ref.frame
    result = {}
    for scope, splits in SCOPES.items():
        rows = frame[frame["split"].isin(splits)]
        ids = rows["sample_id"].tolist()
        result[scope] = distribution(
            data.labels,
            rows["label"].tolist(),
            [data.languages.get(i, "unknown") for i in ids],
            small_cell,
        )
        result[scope]["declared_language"] = (
            pd.Series([data.declared.get(i, "unknown") for i in ids]).value_counts().to_dict()
        )
    return result


# ---- 3. metrics ------------------------------------------------------------------------------


def confusion(y_true, y_pred, n_classes: int) -> np.ndarray:
    """Rows = true class, columns = predicted class."""
    matrix = np.zeros((n_classes, n_classes), dtype=int)
    np.add.at(matrix, (np.asarray(y_true, dtype=int), np.asarray(y_pred, dtype=int)), 1)
    return matrix


def _ratio(top: np.ndarray, bottom: np.ndarray) -> np.ndarray:
    return np.divide(top, bottom, out=np.zeros(len(top)), where=bottom > 0)


def metrics_from_confusion(matrix, labels: list[str]) -> dict:
    """Accuracy, macro / weighted F1, macro P / R, benign FPR and per-class P / R / F1 / support.

    Same conventions as Part 4 ``compute_metrics`` (sklearn, zero_division=0): a class never
    predicted has precision 0; macro = plain mean over ALL classes; weighted F1 = F1 weighted
    by support; benign FPR = benign pages predicted as any threat / benign pages.
    """
    m = np.asarray(matrix, dtype=float)
    n = m.sum()
    tp, predicted, support = np.diag(m), m.sum(axis=0), m.sum(axis=1)
    precision, recall = _ratio(tp, predicted), _ratio(tp, support)
    f1 = _ratio(2 * tp, predicted + support)
    b = labels.index(BENIGN) if BENIGN in labels else None
    return {
        "n": int(n),
        "accuracy": float(tp.sum() / n) if n else 0.0,
        "macro_precision": float(precision.mean()),
        "macro_recall": float(recall.mean()),
        "macro_f1": float(f1.mean()),
        "weighted_f1": float((f1 * support).sum() / n) if n else 0.0,
        "benign_fpr": (None if b is None or not support[b] else float(1 - m[b, b] / support[b])),
        "per_class": {
            label: {
                "precision": float(precision[i]),
                "recall": float(recall[i]),
                "f1": float(f1[i]),
                "support": int(support[i]),
            }
            for i, label in enumerate(labels)
        },
        "confusion_matrix": m.astype(int).tolist(),
    }


def score(y_true, y_pred, labels: list[str]) -> dict:
    return metrics_from_confusion(confusion(y_true, y_pred, len(labels)), labels)


def summarize(folds: list[dict], labels: list[str]) -> dict:
    """{"mean", "std"} over folds (population std, as Part 4 ``summarize_folds``)."""
    mean, std = {}, {}
    keys = list(SCALARS) + [f"{k}_{c}" for c in labels for k in ("precision", "recall", "f1")]
    for key in keys:
        if key in SCALARS:
            values = [f[key] for f in folds if f.get(key) is not None]
        else:
            metric, label = key.split("_", 1)
            values = [f["per_class"][label][metric] for f in folds]
        mean[key] = float(np.mean(values)) if values else None
        std[key] = float(np.std(values)) if values else None
    return {"mean": mean, "std": std, "n_folds": len(folds)}


def per_language(y_true, y_pred, languages: list[str], labels: list[str], min_n: int) -> dict:
    """Accuracy with n per language bucket (empty buckets listed with n = 0)."""
    y_true, y_pred, languages = np.asarray(y_true), np.asarray(y_pred), np.asarray(languages)
    result = {}
    for bucket in LANGUAGES + sorted(set(languages.tolist()) - set(LANGUAGES)):
        mask = languages == bucket
        n = int(mask.sum())
        result[bucket] = {
            "n": n,
            "correct": int((y_true[mask] == y_pred[mask]).sum()),
            "accuracy": float((y_true[mask] == y_pred[mask]).mean()) if n else None,
            "small_n": n < min_n,
        }
    return result


# ---- 4. model rows from saved predictions ----------------------------------------------------


@dataclass
class ModelRow:
    key: str
    display: str
    part: str
    model: str
    sources: list[str]
    test_pred: np.ndarray
    fold_metrics: list[dict] | None = None  # None = CV read from a report (tri)
    cv_override: dict | None = None
    note: str | None = None


def _rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(resolve_path(Path(".")).resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def oof_row(key: str, spec: dict, data: EvalSet, folder: Path) -> ModelRow | None:
    oof = load_oof(key, data.ref, folder)  # None if missing, OofError if stale
    if oof is None:
        return None
    pool, test = data.ref.pool, data.ref.test
    pool_proba = oof.proba(pool["sample_id"])
    y_pool, folds = pool["y"].to_numpy(int), pool["fold"].to_numpy(int)
    fold_metrics = [
        score(y_pool[folds == k], pool_proba[folds == k].argmax(axis=1), data.labels)
        for k in sorted(set(folds.tolist()))
    ]
    manifest = oof.manifest
    model = manifest.get("model_display") or manifest.get("model") or key
    if manifest.get("seed") is not None:
        model = f"{model} (seed {manifest['seed']})"
    return ModelRow(
        key=key,
        display=spec["display"],
        part=spec["part"],
        model=str(model),
        sources=[_rel(folder / f"oof_{key}.csv")],
        test_pred=oof.proba(test["sample_id"]).argmax(axis=1),
        fold_metrics=fold_metrics,
    )


def tri_row(spec: dict, data: EvalSet, ablation_dir: Path) -> tuple[ModelRow | None, str | None]:
    """The Part 9A final model; (None, reason) if its saved files are missing."""
    json_path = ablation_dir / "ablation.json"
    csv_path = ablation_dir / "test_predictions.csv"
    missing = [p for p in (json_path, csv_path) if not p.is_file()]
    if missing:
        return None, f"missing {', '.join(_rel(p) for p in missing)}"
    ablation = read_json(json_path)
    if ablation["split"]["split_fingerprint"] != data.ref.split_fingerprint:
        raise PP1Error(f"{json_path} was made on another split")
    final = ablation["final"]
    predictions = pd.read_csv(csv_path, dtype=str, keep_default_na=False).set_index("sample_id")
    if final["key"] not in predictions.columns:
        return None, f"{_rel(csv_path)} has no column {final['key']}"
    index = {label: i for i, label in enumerate(data.labels)}
    test_ids = data.ref.test["sample_id"]
    pred = predictions.loc[test_ids, final["key"]].map(index).to_numpy(int)
    cv = final["cv"]
    mean, std = dict(cv["mean"]), dict(cv["std"])
    for part in (mean, std):
        part["macro_recall"] = part.get("balanced_accuracy")
        part["macro_precision"] = None
    return (
        ModelRow(
            key="tri",
            display=spec["display"],
            part=spec["part"],
            model=f"{final['title']} · {final['strategy_display']}",
            sources=[_rel(csv_path), _rel(json_path)],
            test_pred=pred,
            cv_override={"mean": mean, "std": std, "n_folds": len(final["cv_folds_macro_f1"])},
            note=(
                "CV read from ablation.json (fold models re-fitted inside Part 9A, fused OOF not "
                "saved); macro precision not stored there; macro recall = balanced accuracy"
            ),
        ),
        None,
    )


def xlmr_seeds(data: EvalSet, root: Path) -> dict | None:
    """Test metrics of every saved XLM-R seed + mean ± std (None if no prediction file)."""
    runs = {}
    test_ids = data.ref.test["sample_id"].tolist()
    for folder in sorted(root.glob("seed_*")):
        path = folder / "predictions.jsonl"
        if not path.is_file():
            continue
        rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
        proba = {r["sample_id"]: r["probabilities"] for r in rows if r["split"] == "test"}
        if set(proba) != set(test_ids):
            raise PP1Error(f"{path} does not cover exactly the frozen test pages")
        pred = np.asarray([proba[i] for i in test_ids]).argmax(axis=1)
        runs[folder.name] = score(data.ref.test["y"].to_numpy(int), pred, data.labels)
    if not runs:
        return None
    return {
        "seeds": sorted(runs),
        "per_seed": {s: {k: runs[s][k] for k in SCALARS} for s in sorted(runs)},
        "summary": summarize(list(runs.values()), data.labels),
        "source": _rel(root / "seed_*/predictions.jsonl"),
    }


def load_rows(data: EvalSet, config: PP1Config) -> tuple[list[ModelRow], list[dict]]:
    """(rows found, skipped rows with the reason)."""
    folder = FusionConfig.load().oof_dir(data.ref.version)
    rows, skipped = [], []
    for key, spec in config.rows.items():
        if spec["source"] == "oof":
            row = oof_row(key, spec, data, folder)
            reason = None if row else f"missing {_rel(folder / f'oof_{key}.csv')} (+ .json)"
        else:
            row, reason = tri_row(spec, data, config.path("ablation_dir") / data.ref.version)
        if row is None:
            skipped.append({"key": key, "display": spec["display"], "reason": reason})
        else:
            rows.append(row)
    return rows, skipped


def evaluate_rows(rows: list[ModelRow], data: EvalSet, config: PP1Config) -> list[dict]:
    """Per row: CV mean ± std, test metrics, bootstrap CI, per-language accuracy."""
    y_test = data.ref.test["y"].to_numpy(int)
    test_languages = [data.languages.get(i, "unknown") for i in data.ref.test["sample_id"]]
    settings = FusionConfig.load().bootstrap
    indices = bootstrap.resample_indices(
        len(y_test), int(settings["n_resamples"]), int(settings["seed"])
    )
    confidence = float(settings["confidence"])
    results = []
    for row in rows:
        test = score(y_test, row.test_pred, data.labels)
        cv = row.cv_override or summarize(row.fold_metrics, data.labels)
        boot = bootstrap.summarize(
            test["macro_f1"], bootstrap.bootstrap_scores(y_test, row.test_pred, indices), confidence
        )
        results.append(
            {
                "key": row.key,
                "display": row.display,
                "part": row.part,
                "model": row.model,
                "sources": row.sources,
                "note": row.note,
                "cv": cv,
                "cv_folds": (
                    [{k: f[k] for k in SCALARS} for f in row.fold_metrics]
                    if row.fold_metrics
                    else None
                ),
                "test": test,
                "test_macro_f1_ci": boot,
                "per_language": per_language(
                    y_test,
                    row.test_pred,
                    test_languages,
                    data.labels,
                    int(config.raw["min_language_support"]),
                ),
            }
        )
    return results


def best_per_column(results: list[dict], singles_only: bool = False) -> dict:
    """Column -> keys of the best row(s) on test (lowest benign FPR, highest otherwise)."""
    best = {}
    rows = [r for r in results if not singles_only or r["key"] != "tri"]
    for column in SCALARS:
        values = {r["key"]: r["test"][column] for r in rows if r["test"][column] is not None}
        if not values:
            continue
        target = min(values.values()) if column == "benign_fpr" else max(values.values())
        best[column] = sorted(k for k, v in values.items() if abs(v - target) < 1e-12)
    return best


def paired_comparisons(rows: list[ModelRow], data: EvalSet) -> dict:
    """Tri-modal minus every single row, paired bootstrap on the same resamples (Part 9A)."""
    by_key = {r.key: r for r in rows}
    if "tri" not in by_key:
        return {}
    y_test = data.ref.test["y"].to_numpy(int)
    settings = FusionConfig.load().bootstrap
    indices = bootstrap.resample_indices(
        len(y_test), int(settings["n_resamples"]), int(settings["seed"])
    )
    return {
        key: bootstrap.paired_difference(
            y_test,
            by_key["tri"].test_pred,
            row.test_pred,
            indices,
            float(settings["confidence"]),
        )
        for key, row in by_key.items()
        if key != "tri"
    }


def complementarity(rows: list[ModelRow], data: EvalSet) -> dict:
    """On test: which single rows get each page right (oracle = any single right)."""
    singles = [r for r in rows if r.key != "tri"]
    if not singles:
        return {}
    y = data.ref.test["y"].to_numpy(int)
    right = np.array([r.test_pred == y for r in singles])
    ids = data.ref.test["sample_id"].to_numpy()
    any_right = right.any(axis=0)
    result = {
        "rows": [r.key for r in singles],
        "n": int(len(y)),
        "all_right": int(right.all(axis=0).sum()),
        "all_wrong": int((~any_right).sum()),
        "all_wrong_ids": ids[~any_right].tolist(),
        "oracle_accuracy": float(any_right.mean()),
        "only_right": {
            r.key: int((right[i] & (right.sum(axis=0) == 1)).sum()) for i, r in enumerate(singles)
        },
    }
    tri = next((r for r in rows if r.key == "tri"), None)
    if tri is not None:
        result["tri_accuracy"] = float((tri.test_pred == y).mean())
        result["tri_right_when_all_singles_wrong"] = int(((tri.test_pred == y) & ~any_right).sum())
    return result


# ---- 5. cross-check against the Part reports -------------------------------------------------


def _compare(checks: list, row: str, source: str, metric: str, ours, reported, tol: float):
    if reported is None and ours is None:
        return
    ok = (
        reported is not None
        and ours is not None
        and (ours == reported if isinstance(ours, list) else abs(ours - reported) <= tol)
    )
    checks.append(
        {
            "row": row,
            "source": source,
            "metric": metric,
            "ours": ours,
            "reported": reported,
            "ok": bool(ok),
        }
    )


def _check_test(checks, row, source, ours: dict, reported: dict, tol, labels):
    for metric in SCALARS:
        if metric in reported:
            _compare(checks, row, source, f"test.{metric}", ours[metric], reported[metric], tol)
    for label in labels:
        theirs = reported.get("per_class", {}).get(label, {})
        for metric in ("precision", "recall", "f1", "support"):
            if metric in theirs:
                _compare(
                    checks,
                    row,
                    source,
                    f"test.{label}.{metric}",
                    ours["per_class"][label][metric],
                    theirs[metric],
                    tol,
                )
    if "confusion_matrix" in reported:
        _compare(
            checks,
            row,
            source,
            "test.confusion_matrix",
            ours["confusion_matrix"],
            reported["confusion_matrix"],
            tol,
        )


def _check_cv(checks, row, source, ours: dict, reported: dict, tol):
    for part in ("mean", "std"):
        for metric in ("macro_f1", "weighted_f1", "accuracy", "benign_fpr", "macro_precision"):
            theirs = reported.get(part, {}).get(metric)
            mine = ours[part].get(metric)
            if theirs is not None and mine is not None:
                _compare(checks, row, source, f"cv.{part}.{metric}", mine, theirs, tol)


def cross_check(results: list[dict], seeds: dict | None, config: PP1Config, version: str) -> list:
    """Every comparable number vs ablation.json and each Part's results.json."""
    tol = float(config.raw["tolerance"])
    checks: list[dict] = []
    labels = None
    by_key = {r["key"]: r for r in results}
    ablation_path = config.path("ablation_dir") / version / "ablation.json"
    if ablation_path.is_file():
        ablation = read_json(ablation_path)
        labels = ablation["classes"]
        entries = {e["key"]: e for e in ablation["entries"]}
        entries["tri"] = ablation["final"]
        source = _rel(ablation_path)
        for key, r in by_key.items():
            e = entries.get(key)
            if e is None:
                continue
            _check_test(checks, key, source, r["test"], e["test"], tol, labels)
            if key != "tri":
                _check_cv(checks, key, source, r["cv"], e["cv"], tol)
            for bound in ("ci_low", "ci_high"):
                _compare(
                    checks,
                    key,
                    source,
                    f"test.macro_f1_{bound}",
                    r["test_macro_f1_ci"][bound],
                    e.get("bootstrap", {}).get(bound),
                    tol,
                )
    for key, spec in config.rows.items():
        if key not in by_key or not spec.get("part_report"):
            continue
        path = resolve_path(Path(spec["part_report"])) / version / "results.json"
        if not path.is_file():
            checks.append(
                {"row": key, "source": _rel(path), "metric": "file", "ours": None,
                 "reported": None, "ok": False}  # fmt: skip
            )
            continue
        report = read_json(path)
        model = report["models"][report["best_model"]]
        labels = labels or report["classes"]
        _check_test(checks, key, _rel(path), by_key[key]["test"], model["test"], tol, labels)
        if "cv" in model:
            _check_cv(checks, key, _rel(path), by_key[key]["cv"], model["cv"], tol)
        if key == "text_xlmr" and seeds and "seed_summary" in report:
            stored = report["seed_summary"].get("test", {})
            for part in ("mean", "std"):
                for metric in ("macro_f1", "accuracy", "benign_fpr", "macro_precision"):
                    _compare(
                        checks,
                        "text_xlmr (3 seeds)",
                        _rel(path),
                        f"seeds.test.{part}.{metric}",
                        seeds["summary"][part][metric],
                        stored.get(part, {}).get(metric),
                        tol,
                    )
    return checks


# ---- 6. findings + limitations (written ONLY from the numbers above) -------------------------


def _pct(value) -> str:
    return "—" if value is None else f"{100 * value:.1f} %"


def findings(report: dict) -> list[str]:
    rows = {r["key"]: r for r in report["rows"]}
    singles = [r for r in report["rows"] if r["key"] != "tri"]
    out = []
    if singles:
        by_test = sorted(singles, key=lambda r: r["test"]["macro_f1"], reverse=True)
        by_cv = sorted(singles, key=lambda r: r["cv"]["mean"]["macro_f1"], reverse=True)
        top, low = by_test[0], by_test[-1]
        out.append(
            f"Strongest single modality on test: {top['display']} (macro-F1 "
            f"{top['test']['macro_f1']:.3f}, 95 % CI [{top['test_macro_f1_ci']['ci_low']:.3f}, "
            f"{top['test_macro_f1_ci']['ci_high']:.3f}]); weakest: {low['display']} "
            f"({low['test']['macro_f1']:.3f})."
        )
        if by_cv[0]["key"] != top["key"]:
            a, b = by_cv[0]["cv"], top["cv"]
            overlap = (
                a["mean"]["macro_f1"] - a["std"]["macro_f1"]
                <= b["mean"]["macro_f1"] + b["std"]["macro_f1"]
            )
            n_pool = report["distributions"]["cv_pool"]["n"]
            out.append(
                f"The ranking depends on the evaluation: on CV ({n_pool} pages) the strongest "
                f"single row is {by_cv[0]['display']} (macro-F1 {a['mean']['macro_f1']:.3f} ± "
                f"{a['std']['macro_f1']:.3f}) and {top['display']} reaches "
                f"{b['mean']['macro_f1']:.3f} ± {b['std']['macro_f1']:.3f}"
                + ("; the mean ± std ranges overlap." if overlap else ".")
            )
        labels = list(top["test"]["per_class"])
        for label in labels:
            f1 = {r["display"]: r["test"]["per_class"][label]["f1"] for r in singles}
            high, low_f1 = max(f1.values()), min(f1.values())
            best = " = ".join(name for name, v in f1.items() if abs(v - high) < 1e-12)
            worst = " = ".join(name for name, v in f1.items() if abs(v - low_f1) < 1e-12)
            support = top["test"]["per_class"][label]["support"]
            out.append(
                f"{label} (test n = {support}): best single {best} F1 {high:.2f}, weakest "
                f"{worst} {low_f1:.2f}."
            )
        fprs = sorted(
            (r for r in report["rows"] if r["test"]["benign_fpr"] is not None),
            key=lambda r: r["test"]["benign_fpr"],
        )
        n_benign = top["test"]["per_class"].get(BENIGN, {}).get("support")
        text = f"Benign FPR on test (argmax, {n_benign} benign pages): " + ", ".join(
            f"{r['display']} {_pct(r['test']['benign_fpr'])}" for r in fprs
        )
        if fprs and all(r["test"]["benign_fpr"] > 0.02 for r in fprs):
            text += ". No row meets the ≤ 2 % target at argmax"
        out.append(text + ".")
    if "text_xlmr" in rows and "text_tfidf" in rows and report.get("xlmr_seeds"):
        s = report["xlmr_seeds"]["summary"]
        tfidf = rows["text_tfidf"]["test"]["macro_f1"]
        relation = "below" if s["mean"]["macro_f1"] < tfidf else "not below"
        out.append(
            f"Text XLM-R (final seed) test macro-F1 {rows['text_xlmr']['test']['macro_f1']:.3f}; "
            f"over {len(report['xlmr_seeds']['seeds'])} seeds {s['mean']['macro_f1']:.3f} ± "
            f"{s['std']['macro_f1']:.3f}, {relation} Text TF-IDF ({tfidf:.3f})."
        )
    comp = report.get("complementarity") or {}
    if comp:
        only = ", ".join(f"{rows[k]['display']} {v}" for k, v in comp["only_right"].items())
        out.append(
            f"Complementarity (test, {comp['n']} pages, {len(comp['rows'])} single rows): all "
            f"right {comp['all_right']}, all wrong {comp['all_wrong']}; pages only one row gets "
            f"right: {only}. Oracle (any single right) {_pct(comp['oracle_accuracy'])}"
            + (
                f" vs tri-modal {_pct(comp['tri_accuracy'])} accuracy."
                if "tri_accuracy" in comp
                else "."
            )
        )
    if "tri" in rows and report.get("paired_vs_tri"):
        tri = rows["tri"]
        parts = []
        for key, d in report["paired_vs_tri"].items():
            parts.append(
                f"{rows[key]['display']} {d['point']:+.3f} [{d['ci_low']:+.3f}, "
                f"{d['ci_high']:+.3f}]" + (" (CI includes 0)" if d["includes_zero"] else "")
            )
        out.append(
            f"Tri-modal reference: test macro-F1 {tri['test']['macro_f1']:.3f} "
            f"[{tri['test_macro_f1_ci']['ci_low']:.3f}, {tri['test_macro_f1_ci']['ci_high']:.3f}],"
            f" benign FPR {_pct(tri['test']['benign_fpr'])}. Tri-modal minus each single row "
            f"(paired bootstrap): " + "; ".join(parts) + "."
        )
    return out


def limitations(report: dict) -> list[str]:
    test = report["distributions"]["test"]
    out = [
        f"Small test set: {test['n']} pages. Test macro-F1 95 % CIs are "
        + ", ".join(
            f"{r['test_macro_f1_ci']['ci_high'] - r['test_macro_f1_ci']['ci_low']:.2f}"
            for r in report["rows"]
        )
        + " wide (rows in table order); one page moves accuracy by "
        f"{100 / max(test['n'], 1):.1f} points."
    ]
    zero = [k for k, d in (report.get("paired_vs_tri") or {}).items() if d["includes_zero"]]
    if zero:
        names = {r["key"]: r["display"] for r in report["rows"]}
        out.append(
            "The tri-modal gain over "
            + ", ".join(names[k] for k in zero)
            + " is not established: those paired-bootstrap CIs include 0."
        )
    small = [f"{c} {test['by_class'][c]['n']}" for c in test["by_class"]]
    out.append(
        "Few test pages per threat class (" + ", ".join(small) + "); per-class F1 of the small "
        "classes changes by large steps with one page."
    )
    lang = test["by_language"]
    out.append(
        f"Few non-English test pages: si {lang['si']['n']}, ta {lang['ta']['n']}, mixed "
        f"{lang['mixed']['n']}, other {lang['other']['n']} (Part 5A detected language). "
        "Per-language accuracy for si / ta / mixed is anecdotal; no Sinhala / Tamil claim can be "
        "made from this test set."
    )
    if any(r["key"] == "tri" for r in report["rows"]):
        out.append(
            "The tri-modal CV row is read from the Part 9A ablation (fused OOF was not saved); "
            "its CV macro precision is not available. The fusion's arm OOF came from arm "
            "models that saw the fusion's held-out fold (standard stacking, not fully nested)."
        )
    if report["skipped"]:
        out.append(
            "Rows skipped (saved predictions missing): "
            + "; ".join(f"{s['display']} - {s['reason']}" for s in report["skipped"])
            + "."
        )
    out.append(
        "Part 6B (intent-level text classification) is pending; Content-only here is the "
        "page-level 6A classifier."
    )
    out.append(
        "Behavior-only is a page-class classifier over static-JS / behavior features; the "
        "behavior pattern detection-rate evaluation (real-page benchmark) is preliminary "
        "(small n) and is not part of these numbers."
    )
    out.append(
        "All metrics are at argmax. The benign-FPR operating point (≤ 2 % on OOF) of the "
        "Part 9A / 9B reports is not re-evaluated here."
    )
    return out


# ---- run ------------------------------------------------------------------------------------


def run(version: str, config: PP1Config | None = None, do_freeze: bool = False) -> dict:
    config = config or PP1Config.load()
    data = prepare(version, do_freeze=do_freeze)
    rows, skipped = load_rows(data, config)
    results = evaluate_rows(rows, data, config)
    seeds = xlmr_seeds(data, config.path("xlmr_models_dir") / version)
    report = {
        "version": version,
        "part": "Part 10 - PP1 evaluation",
        "rule": "consolidated from saved predictions; no model was trained or re-fitted",
        "frozen": data.frozen,
        "manifest_check": data.manifest,
        "classes": data.labels,
        "distributions": distributions(data, int(config.raw["small_cell"])),
        "rows": results,
        "skipped": skipped,
        "best_per_column": best_per_column(results),
        "best_single_per_column": best_per_column(results, singles_only=True),
        "xlmr_seeds": seeds,
        "paired_vs_tri": paired_comparisons(rows, data),
        "complementarity": complementarity(rows, data),
        "bootstrap_settings": FusionConfig.load().bootstrap,
    }
    if seeds is None and any(r["key"] == "text_xlmr" for r in results):
        skipped.append(
            {
                "key": "text_xlmr_seeds",
                "display": "Text XLM-R (3-seed mean ± std)",
                "reason": "no models/xlmr/<v>/seed_*/predictions.jsonl",
            }
        )
    report["cross_check"] = cross_check(results, seeds, config, version)
    report["mismatches"] = [c for c in report["cross_check"] if not c["ok"]]
    report["findings"] = findings(report)
    report["limitations"] = limitations(report)
    return report
