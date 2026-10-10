import json

import numpy as np
import pytest
from test_mir1k import make_clip

from clay_research.harness import score


def row(rpa, cents=10.0):
    return {
        "clip_id": "x",
        "raw_pitch_accuracy": rpa,
        "voicing_recall": 0.9,
        "voicing_false_alarm": 0.1,
        "cents_error_median": cents,
        "cents_error_p95": 40.0,
    }


def test_summarize_means_and_skips_nan():
    s = score.summarize([row(0.8, 10.0), row(0.6, float("nan"))])
    assert s["raw_pitch_accuracy"] == pytest.approx(0.7)
    assert s["cents_error_median"] == pytest.approx(10.0)
    assert s["clips"] == 2


def test_compare_flags_regressions_in_the_right_direction():
    base = score.summarize([row(0.80, 10.0)])
    _, regressed = score.compare(score.summarize([row(0.82, 9.0)]), base, 0.005)
    assert not regressed  # higher RPA and lower cents error are both better
    lines, regressed = score.compare(score.summarize([row(0.70, 10.0)]), base, 0.005)
    assert regressed
    assert any("raw_pitch_accuracy" in line and "worse" in line for line in lines)
    _, regressed = score.compare(score.summarize([row(0.80, 15.0)]), base, 0.005)
    assert regressed  # cents error went up


def test_end_to_end_on_fake_dataset(tmp_path, monkeypatch):
    root = tmp_path / "mir1k" / "MIR-1K"
    make_clip(root, "Fake_1_01", seconds=1.0)
    monkeypatch.setenv("CLAY_DATA_DIR", str(tmp_path))
    out = tmp_path / "reports"

    code = score.main(["--dataset", "mir1k", "--jobs", "1", "--out", str(out)])

    assert code == 0
    report = json.loads((out / "mir1k_pyin.json").read_text())
    assert report["summary"]["clips"] == 1
    # the fake clip's voice is a clean 220 Hz tone for the first half: pYIN should nail it
    assert report["summary"]["raw_pitch_accuracy"] > 0.9
    assert np.isfinite(report["summary"]["cents_error_median"])
    assert (out / "mir1k_pyin.md").read_text(encoding="utf-8").startswith("# Scoring report")

    # rerunning against itself as a baseline must not report a regression
    code = score.main(
        [
            "--dataset",
            "mir1k",
            "--jobs",
            "1",
            "--out",
            str(out),
            "--baseline",
            str(out / "mir1k_pyin.json"),
        ]
    )
    assert code == 0
