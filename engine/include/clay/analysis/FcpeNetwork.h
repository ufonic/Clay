#pragma once

// FCPE's neural network, run with ONNX Runtime (task 2.2b).
//
// FCPE finds pitch in three stages; this is the middle one. It takes a log-mel
// spectrogram (128 bands per 10 ms frame) and returns, per frame, 360 scores between 0
// and 1, one for each pitch bin from 32.7 Hz to 1975.5 Hz on a cents scale. The decoder
// (a later stage) turns the scores into a pitch in Hz.
//
// Runs offline on a background thread, never on the audio thread (allocates freely).

#include <cstddef>
#include <filesystem>
#include <memory>
#include <vector>

namespace clay::analysis
{

class FcpeNetwork
{
public:
    static constexpr std::size_t kMelBands = 128;
    static constexpr std::size_t kPitchBins = 360;

    // Loads engine/models/fcpe_c_v001.onnx (or another export with the same shapes).
    // threads = 0 lets ONNX Runtime choose. Throws std::runtime_error on failure.
    explicit FcpeNetwork(const std::filesystem::path& modelPath, int threads = 0);
    ~FcpeNetwork();
    FcpeNetwork(const FcpeNetwork&) = delete;
    FcpeNetwork& operator=(const FcpeNetwork&) = delete;

    // mel: frames x kMelBands values, frame-major. Returns frames x kPitchBins scores.
    std::vector<float> latent(const std::vector<float>& mel, std::size_t frames) const;

private:
    struct Impl;
    std::unique_ptr<Impl> impl;
};

} // namespace clay::analysis
