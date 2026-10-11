"""The committed FCPE fixtures must match what Python computes today."""

import json

import numpy as np

from clay_research.parity import fcpe_fixtures as fx


def test_network_fixture_is_current():
    meta = json.loads((fx.FIXTURES / "network.json").read_text(encoding="utf-8"))
    shape_in = (meta["frames"], meta["mel_bands"])
    shape_out = (meta["frames"], meta["pitch_bins"])
    mel, latent = fx.network_case()
    # Small float differences between CPUs are fine; anything bigger means stale files.
    np.testing.assert_allclose(fx.read("network.mel.f32", shape_in), mel, atol=1e-4)
    np.testing.assert_allclose(fx.read("network.latent.f32", shape_out), latent, atol=1e-4)


def test_pipeline_fixtures_are_current():
    meta = json.loads((fx.FIXTURES / "pipeline.json").read_text(encoding="utf-8"))
    basis = fx.read("mel_basis.f32", tuple(meta["mel_basis_shape"]))
    np.testing.assert_allclose(basis, fx.mel_basis(), atol=1e-7)
    for sr in fx.PIPELINE_RATES:
        case = fx.pipeline_case(sr)
        np.testing.assert_array_equal(
            np.fromfile(fx.FIXTURES / f"pipeline_{sr}.audio.f32", dtype="<f4"), case["audio"]
        )
        f0 = np.fromfile(fx.FIXTURES / f"pipeline_{sr}.f0.f32", dtype="<f4")
        assert f0.shape == case["f0"].shape
        voiced = (f0 > 0) & (case["f0"] > 0)
        assert np.mean((f0 > 0) == (case["f0"] > 0)) > 0.995
        cents = 1200 * np.abs(np.log2(f0[voiced] / case["f0"][voiced]))
        assert np.max(cents) < 1.0
