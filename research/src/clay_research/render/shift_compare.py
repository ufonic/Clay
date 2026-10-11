"""Blind listening set: WORLD vs other pitch shifters at ±2 semitones.

Usage (from the repo root):
    uv run --project research python -m clay_research.render.shift_compare

Writes renders/phase1/shift_compare/<clip>/<letter>_{up,down}_2st.wav plus NOTES.md and a
separate KEY.md naming the method behind each letter (open it after listening). Every
method gets the same treatment: original audio between notes (breaths), level-matched
to the original, so only how the notes are shifted differs.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import soundfile as sf

from clay_research.analysis.analyze import analyze
from clay_research.datasets.common import REPO_ROOT

from . import shifters
from .listening_set import default_clips
from .world import splice

# Fixed letters (same on every clip) so the owner can say "Q is best" across vocals.
METHODS = {
    "P": ("Rubber Band R3, formants preserved", shifters.rubberband),
    "Q": ("WORLD (current)", None),
    "R": ("Signalsmith Stretch, NO formant preservation (binding lacks it)", shifters.signalsmith),
    "S": ("PSOLA (Praat overlap-add)", shifters.psola),
}
SHIFTS = {"up_2st": 2.0, "down_2st": -2.0}
NOTES = Path(__file__).with_name("shift_compare_notes.md")


def make(name: str, path: Path, out_root: Path) -> None:
    audio, sr = sf.read(path, dtype="float32", always_2d=False)
    mono = audio.mean(axis=1) if audio.ndim == 2 else audio
    model = analyze(mono, sr)
    out = out_root / name
    out.mkdir(parents=True, exist_ok=True)
    sf.write(out / "0_original.wav", mono, sr)
    for letter, (_, fn) in METHODS.items():
        for label, st in SHIFTS.items():
            if fn is None:
                y = shifters.world(mono, sr, st, model)  # splices internally
            else:
                y = splice(mono, fn(mono, sr, st), model.with_all_edits(pitch_shift_st=st))
            sf.write(out / f"{letter}_{label}.wav", np.clip(y, -1.0, 1.0), sr)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", type=Path, default=REPO_ROOT / "renders" / "phase1" / "shift_compare")
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
