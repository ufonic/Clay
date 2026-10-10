"""VocalSet loader (Wilkins et al., ISMIR 2018; CC BY 4.0).

20 singers performing scales, arpeggios, long tones, and excerpts in many techniques
(vibrato, belt, breathy, vocal fry, ...). No pitch labels: each clip is labelled with
singer, context, technique, and (when present) vowel, all taken from its path:

    VocalSet/data_by_singer/<singer>/<context>/<technique>/<file>.wav

The archive stores every file three times (by singer, technique, vowel); the download
script extracts only data_by_singer.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import numpy as np
import soundfile as sf

from .common import Clip, data_root

NAME = "vocalset"
VOWELS = {"a", "e", "i", "o", "u"}


def dataset_dir() -> Path:
    return data_root() / NAME / "data_by_singer"


def clip_ids(root: Path | None = None) -> list[str]:
    """All clip IDs ('<singer>/<context>/<technique>/<stem>'), sorted."""
    root = root or dataset_dir()
    return sorted(
        p.relative_to(root).with_suffix("").as_posix()
        for p in root.glob("*/*/*/*.wav")
        if not p.name.startswith("._")
    )


def labels_from_id(clip_id: str) -> dict[str, str]:
    singer, context, technique, stem = clip_id.split("/")
    labels = {"singer": singer, "context": context, "technique": technique}
    last = stem.rsplit("_", 1)[-1]
    if last in VOWELS:
        labels["vowel"] = last
    return labels


def load(clip_id: str, root: Path | None = None) -> Clip:
    root = root or dataset_dir()
    audio, sr = sf.read(root / f"{clip_id}.wav", dtype="float32", always_2d=False)
    if audio.ndim == 2:  # a few files may be stereo; keep mono for analysis
        audio = audio.mean(axis=1).astype(np.float32)
    return Clip(
        dataset=NAME,
        clip_id=clip_id,
        audio=audio,
        sample_rate=sr,
        metadata=labels_from_id(clip_id),
    )


def iter_clips(root: Path | None = None) -> Iterator[Clip]:
    for cid in clip_ids(root):
        yield load(cid, root)
