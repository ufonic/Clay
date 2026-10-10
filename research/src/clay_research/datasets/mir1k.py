"""MIR-1K loader (Hsu & Jang 2010).

1,000 short clips of amateur Chinese pop singing, 16 kHz stereo: left channel is the
accompaniment, right channel is the solo voice (checked 2026-10-10: voiced frames
correlate 0.70 with right-channel energy, 0.09 with left).

Pitch labels (PitchLabel/*.pv) are one MIDI note number per frame, 0 = unvoiced.
Frames are 40 ms long with a 20 ms hop (640 / 320 samples at 16 kHz), so frame i is
centred at 0.02 * (i + 1) s and a clip of N samples has (N - 640) // 320 + 1 labels.
Checked against all 1,000 clips on 2026-10-10. (Some papers say 10 ms; for this
archive that is wrong.)
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Literal

import numpy as np
import soundfile as sf

from .common import Clip, PitchTrack, data_root, midi_to_hz

NAME = "mir1k"
SAMPLE_RATE = 16000
FRAME_LENGTH = 640  # samples (40 ms)
HOP_LENGTH = 320  # samples (20 ms)

Channel = Literal["voice", "accompaniment", "mix"]


def dataset_dir() -> Path:
    return data_root() / NAME / "MIR-1K"


def clip_ids(root: Path | None = None) -> list[str]:
    root = root or dataset_dir()
    return sorted(p.stem for p in (root / "Wavfile").glob("*.wav"))


def frame_times(n_frames: int) -> np.ndarray:
    """Centre time in seconds of each label frame."""
    return (np.arange(n_frames) * HOP_LENGTH + FRAME_LENGTH / 2) / SAMPLE_RATE


def load_pitch(clip_id: str, root: Path | None = None) -> PitchTrack:
    root = root or dataset_dir()
    midi = np.loadtxt(root / "PitchLabel" / f"{clip_id}.pv", ndmin=1)
    return PitchTrack(times=frame_times(len(midi)), frequencies_hz=midi_to_hz(midi))


def load(clip_id: str, root: Path | None = None, channel: Channel = "voice") -> Clip:
    """Load a clip. channel='voice' (default) returns the isolated singing voice."""
    root = root or dataset_dir()
    stereo, sr = sf.read(root / "Wavfile" / f"{clip_id}.wav", dtype="float32", always_2d=True)
    if sr != SAMPLE_RATE or stereo.shape[1] != 2:
        raise ValueError(f"{clip_id}: expected 16 kHz stereo, got {sr} Hz x {stereo.shape[1]}")
    audio = {
        "accompaniment": stereo[:, 0],
        "voice": stereo[:, 1],
        "mix": stereo.mean(axis=1),
    }[channel]
    singer = clip_id.split("_", 1)[0]
    return Clip(
        dataset=NAME,
        clip_id=clip_id,
        audio=np.ascontiguousarray(audio, dtype=np.float32),
        sample_rate=sr,
        pitch=load_pitch(clip_id, root),
        metadata={"singer": singer, "channel": channel},
    )


def iter_clips(root: Path | None = None, channel: Channel = "voice") -> Iterator[Clip]:
    for cid in clip_ids(root):
        yield load(cid, root, channel)
