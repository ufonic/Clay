"""Shared types and paths for dataset loaders."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[4]


def data_root() -> Path:
    """Where downloaded datasets live: $CLAY_DATA_DIR, or <repo>/data."""
    env = os.environ.get("CLAY_DATA_DIR")
    return Path(env) if env else REPO_ROOT / "data"


@dataclass(frozen=True)
class PitchTrack:
    """Frame-level pitch labels. Unvoiced frames have frequency 0."""

    times: np.ndarray  # seconds, shape (n,)
    frequencies_hz: np.ndarray  # Hz, shape (n,); 0 = unvoiced

    @property
    def voiced(self) -> np.ndarray:
        return self.frequencies_hz > 0


@dataclass(frozen=True)
class Clip:
    """One audio clip plus whatever labels its dataset provides."""

    dataset: str
    clip_id: str
    audio: np.ndarray  # float32, shape (samples,) mono or (samples, channels)
    sample_rate: int
    pitch: PitchTrack | None = None
    metadata: dict[str, str] = field(default_factory=dict)

    @property
    def duration(self) -> float:
        return self.audio.shape[0] / self.sample_rate


def midi_to_hz(midi: np.ndarray) -> np.ndarray:
    """MIDI note number (fractional allowed) to Hz; values <= 0 map to 0 (unvoiced)."""
    midi = np.asarray(midi, dtype=np.float64)
    hz = 440.0 * np.power(2.0, (midi - 69.0) / 12.0)
    return np.where(midi > 0, hz, 0.0)
