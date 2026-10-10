"""The owner's own dry vocal takes, with hand-checked note labels (task 0.6).

Audio: data/owner_takes/<take>.wav. Labels: research/labels/owner/<take>.json, made with
the labeler (python -m clay_research.labeling.server). Only takes marked verified are
returned, so half-finished labels never reach a score.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import soundfile as sf

from clay_research.labeling import store

from .common import Clip

NAME = "owner_takes"


def clip_ids(audio_dir: Path | None = None, labels_dir: Path | None = None) -> list[str]:
    ids = []
    for take in store.take_names(audio_dir):
        saved = store.load_labels(take, labels_dir)
        if saved is not None and saved[1]:
            ids.append(take)
    return ids


def load(take: str, audio_dir: Path | None = None, labels_dir: Path | None = None) -> Clip:
    saved = store.load_labels(take, labels_dir)
    if saved is None:
        raise FileNotFoundError(f"no labels for take {take!r}")
    audio, sr = sf.read(
        (audio_dir or store.audio_dir()) / f"{store.check_name(take)}.wav",
        dtype="float32",
        always_2d=True,
    )
    return Clip(
        dataset=NAME,
        clip_id=take,
        audio=audio.mean(axis=1),
        sample_rate=sr,
        notes=tuple(saved[0]),
        metadata={"verified": str(saved[1]).lower()},
    )


def iter_clips() -> Iterator[Clip]:
    for take in clip_ids():
        yield load(take)
