"""Export FCPE's neural network to ONNX for the C++ engine (task 2.2).

Usage (from the repo root):
    uv run --project research python -m clay_research.parity.export_fcpe

FCPE has three stages; only the middle one is a neural network:
1. audio -> 16 kHz -> log-mel spectrogram (128 bands, 10 ms hop)  [ported to C++ by hand]
2. mel -> "latent": per frame, 360 scores, one per pitch bin       [this ONNX file]
3. latent -> pitch in Hz (weighted average around the best bin)    [ported to C++ by hand]

Writes engine/models/fcpe_c_v001.onnx (the bundled torchfcpe model, MIT licence) and
checks ONNX Runtime against PyTorch on a test signal.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import torch

from clay_research.datasets.common import REPO_ROOT

ONNX_PATH = REPO_ROOT / "engine" / "models" / "fcpe_c_v001.onnx"
OPSET = 17


def load_network() -> tuple[torch.nn.Module, torch.nn.Module]:
    """(wav2mel, network) from the bundled torchfcpe model, weight norm folded in."""
    import torchfcpe
    from torch.nn.utils import parametrize

    infer = torchfcpe.spawn_bundled_infer_model(device="cpu")
    net = infer.model.eval()
    if parametrize.is_parametrized(net.output_proj):
        parametrize.remove_parametrizations(net.output_proj, "weight")
    return infer.wav2mel, net


class _Latent(torch.nn.Module):
    def __init__(self, net: torch.nn.Module):
        super().__init__()
        self.net = net

    def forward(self, mel: torch.Tensor) -> torch.Tensor:  # (1, frames, 128) -> (1, frames, 360)
        return self.net(mel)


def export(path: Path = ONNX_PATH) -> Path:
    _, net = load_network()
    path.parent.mkdir(parents=True, exist_ok=True)
    dummy = torch.randn(1, 200, 128)
    torch.onnx.export(
        _Latent(net),
        (dummy,),
        str(path),
        input_names=["mel"],
        output_names=["latent"],
        dynamic_axes={"mel": {1: "frames"}, "latent": {1: "frames"}},
        opset_version=OPSET,
        dynamo=False,
    )
    return path


def test_mel(seconds: float = 4.0) -> np.ndarray:
    """Mel of a sung-like test tone with vibrato and a gap, via torchfcpe's own wav2mel."""
    sr = 16000
    t = np.arange(int(seconds * sr)) / sr
    f = 220 * 2 ** ((3 * np.sin(2 * np.pi * 0.25 * t) + 0.3 * np.sin(2 * np.pi * 5.5 * t)) / 12)
    x = sum(0.2 / k * np.sin(2 * np.pi * k * np.cumsum(f) / sr) for k in range(1, 8))
    x[int(1.5 * sr) : int(2.0 * sr)] = 0.0
    wav2mel, _ = load_network()
    with torch.no_grad():
        return wav2mel(torch.tensor(x, dtype=torch.float32)[None, :, None], sr).numpy()


def max_difference(path: Path = ONNX_PATH) -> float:
    import onnxruntime as ort

    _, net = load_network()
    mel = test_mel()
    with torch.no_grad():
        ref = net(torch.from_numpy(mel)).numpy()
    sess = ort.InferenceSession(str(path), providers=["CPUExecutionProvider"])
    out = sess.run(["latent"], {"mel": mel})[0]
    return float(np.max(np.abs(out - ref)))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.parse_args(argv)
    path = export()
    print(f"Wrote {path} ({path.stat().st_size / 1e6:.1f} MB)")
    print(f"ONNX Runtime vs PyTorch, max latent difference: {max_difference(path):.2e}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
