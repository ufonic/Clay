"""vocadito loader (Bittner et al. 2021; CC BY 4.0): the Phase 1 note-detection gate set.

40 short solo vocal recordings (13.6 min total, 44.1 kHz mono) by different singers in
several languages, with an F0 track and note labels from two independent annotators.

Files: data/vocadito/Audio/vocadito_<id>.wav and data/vocadito/Annotations/
  F0/vocadito_<id>_f0.csv            time (s), f0 (Hz; 0 = unvoiced)
  Notes/vocadito_<id>_notesA1.csv    onset (s), pitch (Hz), duration (s)   (annotator 1)
  Notes/vocadito_<id>_notesA2.csv    same, annotator 2

The two annotators agree on mean note F1 0.740 under the gate's rules (onset ±50 ms,
pitch ±50 cents, offsets ignored; measured 2026-10-10). That agreement is the Phase 1
target: Clay should match each annotator as well as they match each other.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import numpy as np
import soundfile as sf

from .common import Clip, Note, PitchTrack, data_root

NAME = "vocadito"
ANNOTATORS = ("A1", "A2")
# Mean note F1 between the two annotators (onset ±50 ms, pitch ±50 cents, no offsets),
# measured on all 40 clips 2026-10-10. The Phase 1 gate: note_f1_mean >= this.
HUMAN_AGREEMENT_F1 = 0.740


def dataset_dir() -> Path:
    return data_root() / NAME


def clip_ids(root: Path | None = None) -> list[str]:
    root = root or dataset_dir()
    ids = [p.stem.removeprefix("vocadito_") for p in (root / "Audio").glob("vocadito_*.wav")]
    return sorted(ids, key=int)


def load_notes(clip_id: str, annotator: str = "A1", root: Path | None = None) -> list[Note]:
    if annotator not in ANNOTATORS:
        raise ValueError(f"annotator must be one of {ANNOTATORS}")
    root = root or dataset_dir()
    rows = np.loadtxt(
        root / "Annotations" / "Notes" / f"vocadito_{clip_id}_notes{annotator}.csv",
        delimiter=",",
        ndmin=2,
    )
    return [Note(float(t), float(t + d), float(69 + 12 * np.log2(f / 440.0))) for t, f, d in rows]


def load_f0(clip_id: str, root: Path | None = None) -> PitchTrack:
    root = root or dataset_dir()
    rows = np.loadtxt(
        root / "Annotations" / "F0" / f"vocadito_{clip_id}_f0.csv", delimiter=",", ndmin=2
    )
    return PitchTrack(times=rows[:, 0], frequencies_hz=rows[:, 1])


def load(clip_id: str, root: Path | None = None) -> Clip:
    """Audio, the F0 track, and annotator 1's notes (annotator 2: load_notes(id, "A2"))."""
    root = root or dataset_dir()
    audio, sr = sf.read(root / "Audio" / f"vocadito_{clip_id}.wav", dtype="float32", always_2d=True)
    return Clip(
        dataset=NAME,
        clip_id=clip_id,
        audio=audio.mean(axis=1),
        sample_rate=sr,
        pitch=load_f0(clip_id, root),
        notes=tuple(load_notes(clip_id, "A1", root)),
    )


def iter_clips(root: Path | None = None) -> Iterator[Clip]:
    for cid in clip_ids(root):
        yield load(cid, root)
