"""FCPE parity fixtures for the C++ engine (task 2.2).

Usage (from the repo root):
    uv run --project research python -m clay_research.parity.fcpe_fixtures

Writes engine/tests/fixtures/fcpe/:
- network.json + network.mel.f32 + network.latent.f32: a 2.5 s test tone's log-mel
  spectrogram and the network's output for it (ONNX Runtime, same version as C++).
Arrays are raw little-endian float32, frame-major; the .json gives the shapes.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

from clay_research.datasets.common import REPO_ROOT

from . import export_fcpe

FIXTURES = REPO_ROOT / "engine" / "tests" / "fixtures" / "fcpe"
NETWORK_SECONDS = 2.5


def network_case() -> tuple[np.ndarray, np.ndarray]:
    """(mel, latent) for the first NETWORK_SECONDS of export_fcpe's test tone."""
    import onnxruntime as ort

    mel = export_fcpe.test_mel()[:, : int(NETWORK_SECONDS * 100) + 1, :]
    sess = ort.InferenceSession(str(export_fcpe.ONNX_PATH), providers=["CPUExecutionProvider"])
    latent = sess.run(["latent"], {"mel": np.ascontiguousarray(mel)})[0]
    return mel[0].astype("<f4"), latent[0].astype("<f4")


PIPELINE_RATES = (44100, 48000, 96000)
PIPELINE_SECONDS = 2.0


def synthetic_vocal(sr: int, seconds: float = PIPELINE_SECONDS) -> np.ndarray:
    """Deterministic singing-like test audio: a glide with vibrato, silence, a breath-like
    noise burst, then a loud note that clips past 0.95 (exercises peak scaling)."""
    rng = np.random.default_rng(sr)
    n = int(seconds * sr)
    t = np.arange(n) / sr
    midi = 57 + 4 * np.clip(t / 0.8, 0, 1) + 0.3 * np.sin(2 * np.pi * 5.5 * t)
    f = 440 * 2 ** ((midi - 69) / 12)
    phase = 2 * np.pi * np.cumsum(f) / sr
    x = sum(0.3 / k * np.sin(k * phase) for k in range(1, 10))
    x[(t > 0.9) & (t < 1.1)] = 0.0
    burst = (t >= 1.1) & (t < 1.3)
    x[burst] = 0.05 * rng.standard_normal(int(burst.sum()))
    x[t >= 1.4] *= 1.6  # peaks above 0.95
    return x.astype(np.float32)


def pipeline_case(sr: int) -> dict[str, np.ndarray]:
    """Every stage of clay_research.harness.trackers.fcpe on synthetic_vocal(sr)."""
    import torch

    from clay_research.harness import trackers

    audio = synthetic_vocal(sr)
    track = trackers.fcpe(audio, sr)
    wav2mel, _ = export_fcpe.load_network()
    peak = float(np.max(np.abs(audio)))
    scaled = audio * (0.95 / peak) if peak > 0.95 else audio
    x = torch.tensor(scaled, dtype=torch.float32)[None, :, None]
    with torch.no_grad():
        mel = wav2mel(x, sr)[0].numpy()  # also builds torchfcpe's resampler for sr
        resampled = wav2mel.resample_kernel[str(sr)](x.squeeze(-1))[0].numpy()
    return {
        "audio": audio,
        "resampled": resampled.astype("<f4"),
        "mel": mel.astype("<f4"),
        "f0": track.frequencies_hz.astype("<f4"),
    }


def mel_basis() -> np.ndarray:
    wav2mel, _ = export_fcpe.load_network()
    return wav2mel.mel_extractor.mel_basis.numpy().astype("<f4")  # (128, 513)


def write(out: Path = FIXTURES) -> None:
    out.mkdir(parents=True, exist_ok=True)
    mel, latent = network_case()
    mel.tofile(out / "network.mel.f32")
    latent.tofile(out / "network.latent.f32")
    meta = {"frames": mel.shape[0], "mel_bands": mel.shape[1], "pitch_bins": latent.shape[1]}
    (out / "network.json").write_text(json.dumps(meta), encoding="utf-8")

    basis = mel_basis()
    basis.tofile(out / "mel_basis.f32")
    cases = {}
    for sr in PIPELINE_RATES:
        case = pipeline_case(sr)
        for key, arr in case.items():
            arr.tofile(out / f"pipeline_{sr}.{key}.f32")
        cases[str(sr)] = {
            key: len(arr) if arr.ndim == 1 else arr.shape[0] for key, arr in case.items()
        }
    pipeline = {"mel_basis_shape": list(basis.shape), "cases": cases}
    (out / "pipeline.json").write_text(json.dumps(pipeline, indent=1), encoding="utf-8")


def read(name: str, shape: tuple[int, int], root: Path = FIXTURES) -> np.ndarray:
    return np.fromfile(root / name, dtype="<f4").reshape(shape)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.parse_args(argv)
    write()
    print(f"Fixtures: {FIXTURES}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
