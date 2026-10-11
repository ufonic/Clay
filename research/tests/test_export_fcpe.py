"""The committed FCPE ONNX model (used by the C++ engine) must match torchfcpe."""

from clay_research.parity import export_fcpe


def test_committed_onnx_matches_pytorch():
    assert export_fcpe.ONNX_PATH.exists(), "run python -m clay_research.parity.export_fcpe"
    # Latent scores are 0..1; float32 rounding differences are ~1e-6.
    assert export_fcpe.max_difference() < 1e-4
