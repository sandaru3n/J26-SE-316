"""Part 10: PP1 evaluation - metric helpers on a known confusion matrix, frozen-split rules."""

from __future__ import annotations

import json

import numpy as np
import pandas as pd
import pytest

from c2_analyzer.evaluation import pp1
from c2_analyzer.fusion.oof import Reference
from c2_analyzer.nlp.metrics import full_metrics

LABELS = ["benign", "phishing", "malware_delivery"]
# rows = true, columns = predicted
KNOWN = [[8, 2, 0], [1, 3, 1], [0, 0, 5]]


def expand(matrix):
    y_true, y_pred = [], []
    for i, row in enumerate(matrix):
        for j, n in enumerate(row):
            y_true += [i] * n
            y_pred += [j] * n
    return np.array(y_true), np.array(y_pred)


def test_metrics_from_known_confusion_matrix():
    m = pp1.metrics_from_confusion(KNOWN, LABELS)
    precision = [8 / 9, 3 / 5, 5 / 6]
    recall = [8 / 10, 3 / 5, 5 / 5]
    f1 = [16 / 19, 6 / 10, 10 / 11]
    assert m["n"] == 20
    assert m["accuracy"] == pytest.approx(16 / 20)
    assert m["macro_precision"] == pytest.approx(np.mean(precision))
    assert m["macro_recall"] == pytest.approx(np.mean(recall))
    assert m["macro_f1"] == pytest.approx(np.mean(f1))
    assert m["weighted_f1"] == pytest.approx((f1[0] * 10 + f1[1] * 5 + f1[2] * 5) / 20)
    assert m["benign_fpr"] == pytest.approx(2 / 10)
    assert m["per_class"]["phishing"] == pytest.approx(
        {"precision": 0.6, "recall": 0.6, "f1": 0.6, "support": 5}
    )
    assert m["confusion_matrix"] == KNOWN


def test_metrics_agree_with_the_part_4_6a_helpers():
    y_true, y_pred = expand(KNOWN)
    ours = pp1.score(y_true, y_pred, LABELS)
    theirs = full_metrics(y_true, y_pred, None, LABELS)
    for key in pp1.SCALARS:
        assert ours[key] == pytest.approx(theirs[key])
    assert ours["confusion_matrix"] == theirs["confusion_matrix"]
    for label in LABELS:
        assert ours["per_class"][label] == pytest.approx(theirs["per_class"][label])


def test_never_predicted_class_and_missing_benign_give_zeros_not_nan():
    m = pp1.metrics_from_confusion([[3, 0], [2, 0]], ["phishing", "malware_delivery"])
    assert m["per_class"]["malware_delivery"]["precision"] == 0.0
    assert m["per_class"]["malware_delivery"]["f1"] == 0.0
    assert m["benign_fpr"] is None
    assert not any(np.isnan(m[k]) for k in pp1.SCALARS if m[k] is not None)


def test_summarize_is_mean_and_population_std_over_folds():
    folds = [pp1.metrics_from_confusion(KNOWN, LABELS), pp1.metrics_from_confusion(
        [[10, 0, 0], [0, 5, 0], [0, 0, 5]], LABELS)]  # fmt: skip
    summary = pp1.summarize(folds, LABELS)
    values = [folds[0]["macro_f1"], 1.0]
    assert summary["mean"]["macro_f1"] == pytest.approx(np.mean(values))
    assert summary["std"]["macro_f1"] == pytest.approx(np.std(values))
    assert summary["mean"]["f1_phishing"] == pytest.approx((0.6 + 1.0) / 2)


def test_distribution_flags_small_cells():
    dist = pp1.distribution(
        LABELS,
        ["benign"] * 6 + ["phishing"] * 2,
        ["en"] * 5 + ["si"] + ["en", "other"],
        small_cell=5,
    )
    assert dist["by_class"]["benign"] == {"n": 6, "pct": 0.75}
    assert dist["class_by_language"]["benign"]["en"] == 5
    assert {"class": "benign", "language": "si", "n": 1} in dist["small_cells"]
    assert {"class": "benign", "language": "en", "n": 5} not in dist["small_cells"]
    assert dist["small_classes"] == ["phishing", "malware_delivery"]
    assert dist["by_language"]["ta"]["n"] == 0  # fixed buckets, empty listed


def make_ref(split_fp="s" * 64, folds_fp="f" * 64) -> Reference:
    frame = pd.DataFrame(
        {
            "sample_id": ["a", "b", "c"],
            "label": ["benign", "phishing", "benign"],
            "y": [0, 1, 0],
            "split": ["train", "val", "test"],
            "fold": [0, 1, -1],
            "cluster_id": ["c1", "c2", "c3"],
        }
    )
    return Reference("v9.9", ["benign", "phishing"], frame, split_fp, folds_fp)


def test_refuses_to_run_without_the_frozen_split(tmp_path):
    with pytest.raises(pp1.PP1Error, match="no frozen PP1 evaluation set"):
        pp1.check_frozen(make_ref(), tmp_path / "pp1_eval.json")


def test_freeze_then_refuse_a_changed_split(tmp_path):
    path = tmp_path / "pp1_eval.json"
    record, written = pp1.freeze(make_ref(), {"manifest": {"fingerprint": "m"}}, path)
    assert written and record["note"] == "frozen for PP1"
    assert (record["n_train"], record["n_val"], record["n_test"]) == (1, 1, 1)
    assert pp1.check_frozen(make_ref(), path)["split_fingerprint"] == "s" * 64
    again, written = pp1.freeze(make_ref(), {}, path)  # identical -> kept, not rewritten
    assert not written and again["created_at"] == record["created_at"]
    with pytest.raises(pp1.PP1Error, match="split_fingerprint"):
        pp1.check_frozen(make_ref(split_fp="x" * 64), path)
    with pytest.raises(pp1.PP1Error, match="cv_folds_fingerprint"):
        pp1.freeze(make_ref(folds_fp="y" * 64), {}, path)
    assert json.loads(path.read_text(encoding="utf-8")) == record


def test_version_defaults_to_the_frozen_pp1_version_only():
    config = pp1.PP1Config.load()
    assert pp1.resolve_version(None, config) == config.version == "v0.3"
    assert pp1.resolve_version("v0.4", config) == "v0.4"


def test_cli_refuses_without_the_frozen_file(tmp_path, monkeypatch, capsys):
    from c2_analyzer.config import resolve_path

    if not resolve_path(pp1.Path("data/metadata/manifests/dataset_v0.3.json")).is_file():
        pytest.skip("v0.3 manifest not available")
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "pp1_cli", resolve_path(pp1.Path("scripts/pp1_evaluation.py"))
    )
    cli = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cli)
    monkeypatch.setattr(pp1, "frozen_path", lambda version, root=None: tmp_path / "none.json")
    assert cli.main(["--version", "v0.3", "--no-figures"]) == 2
    assert "no frozen PP1 evaluation set" in capsys.readouterr().err
    assert not (tmp_path / "none.json").exists()
