"""Make the Phase 1 listening set: before/after renders for the owner (task 1.7, pitch part).

Usage (from the repo root):
    uv run --project research python -m clay_research.render.listening_set

Writes renders/phase1/pitch/<clip>/NN_<version>.wav plus NOTES.md. Every WORLD version
of a clip is level-matched to the original (WORLD's resynthesis comes out ~1.5 dB louder,
and louder always sounds "better" in a comparison), so differences you hear are tone,
not volume.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import soundfile as sf

from clay_research.analysis.analyze import analyze
from clay_research.datasets import vocadito
from clay_research.datasets.common import REPO_ROOT, data_root

from .world import render

VERSIONS = [
    ("01_resynth_no_edit", {}),
    ("02_up_1st", {"pitch_shift_st": 1.0}),
    ("03_down_1st", {"pitch_shift_st": -1.0}),
    ("04_up_2st", {"pitch_shift_st": 2.0}),
    ("05_down_2st", {"pitch_shift_st": -2.0}),
    # For comparison only: formants moved with the pitch = the "chipmunk" Clay avoids.
    ("06_up_2st_formants_NOT_preserved", {"pitch_shift_st": 2.0, "formant_shift_st": 2.0}),
]

NOTES = Path(__file__).with_name("listening_notes.md")


def default_clips() -> list[tuple[str, Path]]:
    vs = data_root() / "vocalset" / "data_by_singer"
    clips = [
        ("vocalset_f2_straight", vs / "female2/excerpts/straight/f2_caro_straight.wav"),
        ("vocalset_f9_vibrato", vs / "female9/excerpts/vibrato/f9_caro_vibrato.wav"),
        ("vocalset_m1_straight", vs / "male1/excerpts/straight/m1_caro_straight.wav"),
    ]
    vd = vocadito.dataset_dir() / "Audio"
    clips += [("vocadito_1", vd / "vocadito_1.wav"), ("vocadito_2", vd / "vocadito_2.wav")]
    return [(name, path) for name, path in clips if path.exists()]


def make(name: str, path: Path, out_root: Path) -> Path:
    audio, sr = sf.read(path, dtype="float32", always_2d=False)
    mono = audio.mean(axis=1) if audio.ndim == 2 else audio
    model = analyze(mono, sr)
    out = out_root / name
    out.mkdir(parents=True, exist_ok=True)
    sf.write(out / "00_original.wav", mono, sr)
    model.save(out / "note_model.json")

    neutral = render(mono, model)
    match = float(np.sqrt(np.mean(mono**2)) / max(np.sqrt(np.mean(neutral**2)), 1e-9))
    for label, edits in VERSIONS:
        y = neutral if not edits else render(mono, model.with_all_edits(**edits))
        y = np.clip(y * match, -1.0, 1.0)
        sf.write(out / f"{label}.wav", y, sr)
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", type=Path, default=REPO_ROOT / "renders" / "phase1" / "pitch")
    args = ap.parse_args(argv)
    clips = default_clips()
    if not clips:
        print("No source vocals found; download vocalset and vocadito first (data/README.md).")
        return 2
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "NOTES.md").write_text(NOTES.read_text(encoding="utf-8"), encoding="utf-8")
    for name, path in clips:
        folder = make(name, path, args.out)
        print(f"{name}: {folder}")
    print(f"Listening notes: {args.out / 'NOTES.md'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
