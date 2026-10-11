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
    # Window must hold at least two periods of the lowest note (2 / 65 Hz ≈ 31 ms). Round
    # *down* to a power of two at or under 64 ms: 1024 at 16 kHz, 2048 at 44.1/48 kHz.
    # (Rounding up gave 93 ms at 44.1 kHz, smearing note edges by ~40 ms.)
    frame_length = int(2 ** np.floor(np.log2(0.064 * sample_rate)))
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


_models: dict[str, object] = {}


def _torch():
    """Import torch on first use (it's slow to import) and keep one thread per process:
    the harness already runs one process per CPU core."""
    import torch

    if "threads_set" not in _models:
        torch.set_num_threads(1)
        _models["threads_set"] = True
    return torch


def crepe(audio: np.ndarray, sample_rate: int, model: str = "full") -> PitchTrack:
    """CREPE (Kim et al. 2018) via torchcrepe: a neural network trained to read pitch from
    raw audio. It hears pitch through breathiness and noise better than pYIN; voicing
    comes from its confidence ("periodicity"), smoothed and cut at 0.21 (torchcrepe's
    recommended threshold)."""
    torch = _torch()
    import torchcrepe

    hop = round(HOP_S * sample_rate)
    x = torch.tensor(audio, dtype=torch.float32)[None, :]
    with torch.no_grad():
        f0, periodicity = torchcrepe.predict(
            x,
            sample_rate,
            hop_length=hop,
            fmin=FMIN_HZ,
            fmax=FMAX_HZ,
            model=model,
            return_periodicity=True,
            batch_size=512,
            device="cpu",
        )
    periodicity = torchcrepe.filter.median(periodicity, 3)
    f0 = torchcrepe.threshold.At(0.21)(f0, periodicity)
    f0 = f0.squeeze(0).numpy()
    times = np.arange(len(f0)) * hop / sample_rate
    return PitchTrack(times=times, frequencies_hz=np.where(np.isfinite(f0), f0, 0.0))


def crepe_tiny(audio: np.ndarray, sample_rate: int) -> PitchTrack:
    """CREPE's smallest model: much faster, a little less accurate."""
    return crepe(audio, sample_rate, model="tiny")


def fcpe(audio: np.ndarray, sample_rate: int) -> PitchTrack:
    """FCPE (2024) via torchfcpe: a fast neural pitch estimator working on a mel
    spectrogram. Fixed 10 ms hop at its internal 16 kHz; frame i is centred at i * 10 ms
    (checked with a test tone)."""
    torch = _torch()
    if "fcpe" not in _models:
        import torchfcpe

        _models["fcpe"] = torchfcpe.spawn_bundled_infer_model(device="cpu")
    model = _models["fcpe"]
    # FCPE expects samples within ±1 and complains otherwise; its internal resampler can
    # overshoot a little, so leave 5% headroom. Level doesn't change pitch.
    peak = float(np.max(np.abs(audio))) if audio.size else 0.0
    if peak > 0.95:
        audio = audio * (0.95 / peak)
    x = torch.tensor(audio, dtype=torch.float32)[None, :, None]
    with torch.no_grad():
        f0 = model.infer(x, sr=sample_rate, f0_min=FMIN_HZ, f0_max=FMAX_HZ)
    f0 = f0.squeeze().numpy()
    times = np.arange(len(f0)) * 0.01
    return PitchTrack(times=times, frequencies_hz=np.where(f0 >= FMIN_HZ, f0, 0.0))


TRACKERS: dict[str, Callable[[np.ndarray, int], PitchTrack]] = {
    "pyin": pyin,
    "crepe": crepe,
    "crepe_tiny": crepe_tiny,
    "fcpe": fcpe,
}
