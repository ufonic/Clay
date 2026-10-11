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


def write(out: Path = FIXTURES) -> None:
    out.mkdir(parents=True, exist_ok=True)
    mel, latent = network_case()
    mel.tofile(out / "network.mel.f32")
    latent.tofile(out / "network.latent.f32")
    meta = {"frames": mel.shape[0], "mel_bands": mel.shape[1], "pitch_bins": latent.shape[1]}
    (out / "network.json").write_text(json.dumps(meta), encoding="utf-8")


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
