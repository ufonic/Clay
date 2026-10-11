#pragma once

// FCPE pitch tracker in C++ (task 2.2): the same results as Python's
// clay_research.harness.trackers.fcpe, checked by parity tests.
//
// Plain-language version of the pipeline:
// 1. Resample the audio to 16 kHz (what the network was trained on).
// 2. Turn it into a log-mel spectrogram: every 10 ms, how much energy sits in each of 128
//    frequency bands spaced like human pitch perception.
// 3. The neural network scores 360 candidate pitches per frame (FcpeNetwork).
// 4. The decoder takes the best-scoring pitch and averages it with its 4 neighbours on
//    each side, weighted by score, for a precise value. Frames whose best score is tiny
//    are unvoiced (0 Hz).
//
// Runs offline on a background thread, never on the audio thread.

#include "clay/analysis/FcpeNetwork.h"

#include <cstddef>
#include <filesystem>
#include <vector>

namespace clay::analysis
{

// Pitch every hopSeconds; 0 = unvoiced. Frame i is centred at i * hopSeconds.
struct PitchTrack
{
    double hopSeconds = 0.01;
    std::vector<float> f0Hz;
};

class FcpeTracker
{
public:
    static constexpr int kModelSampleRate = 16000;
    static constexpr std::size_t kHop = 160;    // 10 ms at 16 kHz
    static constexpr float kThreshold = 0.006f; // torchfcpe default
    static constexpr float kMinHz = 65.0f;      // C2 (analysis SPEC decision 3)
    static constexpr float kMaxHz = 1047.0f;    // C6

    explicit FcpeTracker(const std::filesystem::path& modelPath, int threads = 0);

    // Mono audio at any sample rate (integer Hz). Throws std::invalid_argument on a
    // sample rate <= 0.
    PitchTrack track(const std::vector<float>& mono, int sampleRate) const;

private:
    FcpeNetwork network;
};

// The individual stages, exposed so parity tests can check each one against Python.
namespace fcpe
{
// torchaudio.transforms.Resample(orig, target, lowpass_filter_width=128): windowed-sinc
// (Hann) resampling, rolloff 0.99.
std::vector<float> resample(const std::vector<float>& x, int origRate, int targetRate);

// librosa.filters.mel(sr=16000, n_fft=1024, n_mels=128), Slaney scale and norm:
// 128 x 513 weights, band-major.
std::vector<float> melBasis();

// torchfcpe's MelModule on 16 kHz audio: frames x 128 log-mel values, frame-major.
std::vector<float> logMel(const std::vector<float>& audio16k, std::size_t& frames);

// torchfcpe's local-argmax decoder: frames x 360 scores -> pitch in Hz (0 = unvoiced),
// before Clay's C2-C6 limits.
std::vector<float> decode(const std::vector<float>& latent, std::size_t frames, float threshold);
} // namespace fcpe

} // namespace clay::analysis
