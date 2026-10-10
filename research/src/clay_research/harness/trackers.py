"""Pitch trackers the harness can score. Each maps (audio, sample_rate) -> PitchTrack."""

from __future__ import annotations

from collections.abc import Callable

import librosa
import numpy as np

from clay_research.datasets.common import PitchTrack

# Vocal range for the baseline: C2 (65 Hz) to C6 (1047 Hz).
FMIN_HZ = 65.0
FMAX_HZ = 1047.0
HOP_S = 0.01  # 10 ms; the roadmap asks for F0 every 5-10 ms


def pyin(audio: np.ndarray, sample_rate: int) -> PitchTrack:
    """pYIN (Mauch & Dixon 2014) via librosa: the Phase 0/1 baseline tracker.

    YIN finds the period by looking for where the signal best matches a delayed copy
    of itself; pYIN tries many YIN thresholds and lets an HMM pick a smooth path of
    pitch + voiced/unvoiced decisions through the candidates.
    """
    hop = round(HOP_S * sample_rate)
    # Window must hold at least two periods of the lowest note: 2 / 65 Hz ≈ 31 ms; use ~64 ms.
    frame_length = int(2 ** np.ceil(np.log2(0.064 * sample_rate)))
    f0, voiced, _ = librosa.pyin(
        audio,
        fmin=FMIN_HZ,
        fmax=FMAX_HZ,
        sr=sample_rate,
        frame_length=frame_length,
        hop_length=hop,
    )
    times = librosa.times_like(f0, sr=sample_rate, hop_length=hop)
    freqs = np.where(voiced & np.isfinite(f0), f0, 0.0)
    return PitchTrack(times=times, frequencies_hz=freqs)


TRACKERS: dict[str, Callable[[np.ndarray, int], PitchTrack]] = {
    "pyin": pyin,
}
