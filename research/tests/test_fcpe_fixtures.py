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
