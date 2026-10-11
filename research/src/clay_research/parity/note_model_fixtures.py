"""Note-model parity fixtures for the C++ engine (task 2.1).

Usage (from the repo root):
    uv run --project research python -m clay_research.parity.note_model_fixtures
    ... --refresh-real   # re-cut the real-vocal case from renders/phase1/pitch/vocadito_1

Writes engine/tests/fixtures/note_model/<case>.model.json (a note model with edits, the
input) and <case>.expected.json (every derived curve, computed by Python at full
precision). The C++ test loads both and must match. Fixtures are committed so CI needs
no datasets. The real case is derived from vocadito (CC BY 4.0): analysis numbers only,
no audio.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import replace
from pathlib import Path

import numpy as np

from clay_research.datasets.common import REPO_ROOT
from clay_research.model.note_model import BRIDGE_S, ModelNote, NoteEdit, NoteModel

FIXTURES = REPO_ROOT / "engine" / "tests" / "fixtures" / "note_model"
REAL_SOURCE = REPO_ROOT / "renders" / "phase1" / "pitch" / "vocadito_1" / "note_model.json"
REAL_SECONDS = 12.0


def _nullable(a: np.ndarray) -> list:
    return [None if not np.isfinite(v) else float(v) for v in a]


def expected_for(model: NoteModel) -> dict:
    """Everything C++ must reproduce, at full precision."""
    curves = model._edit_curves()
    return {
        "times": [float(t) for t in model.times],
        "pitch": [float(v) for v in curves["pitch"]],
        "formant": [float(v) for v in curves["formant"]],
        "gain": [float(v) for v in curves["gain"]],
        "flatten": [float(v) for v in curves["flatten"]],
        "target_f0_midi": _nullable(model.target_f0_midi()),
        "note_span": [bool(v) for v in model.note_span()],
        "is_neutral": model.is_neutral(),
    }


def _varied_edits(model: NoteModel, seed: int) -> NoteModel:
    """Deterministic, varied per-note edits; every 4th note left neutral."""
    rng = np.random.default_rng(seed)
    notes = []
    for i, n in enumerate(model.notes):
        e = NoteEdit(
            pitch_shift_st=float(np.round(rng.uniform(-3, 3), 3)),
            drift_scale=float(np.round(rng.uniform(0, 1.5), 3)),
            formant_shift_st=float(np.round(rng.uniform(-2, 2), 3)),
            gain_db=float(np.round(rng.uniform(-6, 6), 3)),
        )
        notes.append(replace(n, edit=NoteEdit() if i % 4 == 3 else e))
    return replace(model, notes=tuple(notes))


def real_case() -> NoteModel:
    m = NoteModel.load(REAL_SOURCE)
    n = int(REAL_SECONDS / m.hop_s) + 1
    m = replace(
        m,
        duration=REAL_SECONDS,
        f0_midi=m.f0_midi[:n],
        rms_db=m.rms_db[:n],
        notes=tuple(x for x in m.notes if x.onset < REAL_SECONDS),
    )
    return _varied_edits(m, seed=7)


def edge_case() -> NoteModel:
    """Synthetic: unsorted, overlapping, zero-length, bridge-boundary gaps, edges."""
    n = 600  # 3 s
    t = np.arange(n) * 0.005
    f0 = 60 + 0.5 * np.sin(2 * np.pi * 5 * t)
    f0[100:120] = np.nan  # unvoiced gap inside a note
    f0[400:450] = np.nan
    e = NoteEdit
    notes = (
        ModelNote(1.20, 1.60, 61.0, e(pitch_shift_st=2.0, drift_scale=0.0)),  # out of order
        ModelNote(0.0, 0.40, 60.0, e(pitch_shift_st=-1.5, gain_db=3.0)),  # starts at 0
        ModelNote(0.35, 0.80, 60.5, e(formant_shift_st=1.0, drift_scale=0.5)),  # overlaps
        ModelNote(0.80 + BRIDGE_S, 1.20, 62.0, e(pitch_shift_st=1.0)),  # gap == bridge
        ModelNote(1.90 + 1e-9, 2.20, 59.0, e(gain_db=-6.0)),  # gap just over bridge
        ModelNote(2.50, 2.50, 58.0, e(pitch_shift_st=4.0)),  # zero length
        ModelNote(2.90, 3.40, 57.0, e(pitch_shift_st=-2.0, drift_scale=1.5)),  # past the end
    )
    return NoteModel(
        sample_rate=48000,
        duration=n * 0.005,
        f0_midi=f0,
        rms_db=np.linspace(-60, -10, n),
        notes=notes,
        analysis_version="fixture-edge",
    )


def empty_case() -> NoteModel:
    return NoteModel(
        sample_rate=44100,
        duration=0.5,
        f0_midi=np.full(101, np.nan),
        rms_db=np.full(101, -80.0),
        notes=(),
        analysis_version="fixture-empty",
    )


def write_case(name: str, model: NoteModel, out: Path = FIXTURES) -> None:
    out.mkdir(parents=True, exist_ok=True)
    model.save(out / f"{name}.model.json")
    # The C++ side reads the saved file, so compute expectations from the saved version
    # (frame values are rounded to 4 decimals on save).
    saved = NoteModel.load(out / f"{name}.model.json")
    (out / f"{name}.expected.json").write_text(json.dumps(expected_for(saved)), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--refresh-real", action="store_true", help="re-cut the vocadito case")
    args = ap.parse_args(argv)
    write_case("edge", edge_case())
    write_case("empty", empty_case())
    real = FIXTURES / "vocadito_1.model.json"
    if args.refresh_real or not real.exists():
        if not REAL_SOURCE.exists():
            print(f"Missing {REAL_SOURCE}; run clay_research.render.listening_set first.")
            return 2
        write_case("vocadito_1", real_case())
    else:
        write_case("vocadito_1", NoteModel.load(real))
    print(f"Fixtures: {FIXTURES}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
