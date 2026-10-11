"""Blind listening set for task 1.6: three time stretchers at ±10% (also covers 1.7 time).

Usage (from the repo root):
    uv run --project research python -m clay_research.render.time_compare

Writes renders/phase1/time_compare/<clip>/<letter>_{slower,faster}_10pct.wav, NOTES.md,
and KEY.md (open after listening). All versions are level-matched to the original.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import soundfile as sf

from clay_research.analysis.analyze import analyze
from clay_research.datasets.common import REPO_ROOT

from . import stretchers
from .listening_set import default_clips

METHODS = {
    "X": ("Signalsmith Stretch", stretchers.signalsmith),
    "Y": ("WORLD frames (Clay's own rebuild)", stretchers.world),
    "Z": ("Rubber Band R3", stretchers.rubberband),
}
RATIOS = {"slower_10pct": 1.1, "faster_10pct": 0.9}
NOTES = Path(__file__).with_name("time_compare_notes.md")


def _rms(x: np.ndarray) -> float:
    return float(np.sqrt(np.mean(np.square(x, dtype=np.float64))))


def make(name: str, path: Path, out_root: Path) -> None:
    audio, sr = sf.read(path, dtype="float32", always_2d=False)
    mono = audio.mean(axis=1) if audio.ndim == 2 else audio
    model = analyze(mono, sr)
    out = out_root / name
    out.mkdir(parents=True, exist_ok=True)
    sf.write(out / "0_original.wav", mono, sr)
    for letter, (_, fn) in METHODS.items():
        for label, ratio in RATIOS.items():
            if fn is stretchers.world:
                y = fn(mono, sr, ratio, model)
            else:
                y = fn(mono, sr, ratio)
            y = y * (_rms(mono) / max(_rms(y), 1e-9))
            sf.write(out / f"{letter}_{label}.wav", np.clip(y, -1.0, 1.0), sr)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", type=Path, default=REPO_ROOT / "renders" / "phase1" / "time_compare")
    args = ap.parse_args(argv)
    clips = default_clips()
    if not clips:
        print("No source vocals found; download vocalset and vocadito first (data/README.md).")
        return 2
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "NOTES.md").write_text(NOTES.read_text(encoding="utf-8"), encoding="utf-8")
    key = ["# Answer key (open after listening)", ""]
    key += [f"- **{letter}**: {desc}" for letter, (desc, _) in METHODS.items()]
    (args.out / "KEY.md").write_text("\n".join(key) + "\n", encoding="utf-8")
    for name, path in clips:
        make(name, path, args.out)
        print(f"{name}: done")
    print(f"Listening notes: {args.out / 'NOTES.md'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
