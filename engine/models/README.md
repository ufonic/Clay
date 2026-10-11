# Engine models

| File | What | Source / licence | Regenerate |
|---|---|---|---|
| `fcpe_c_v001.onnx` | FCPE pitch network: log-mel (1, frames, 128) → latent (1, frames, 360) | Bundled model of [torchfcpe](https://github.com/CNChTu/FCPE) 0.0.4, MIT licence; exported with weight norm folded in, ONNX opset 17 | `uv run --project research python -m clay_research.parity.export_fcpe` |

`research/tests/test_export_fcpe.py` checks the committed file still matches torchfcpe
(max latent difference < 1e-4; currently ~2e-6).
