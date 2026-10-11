// Parity: each stage of the C++ FCPE tracker against Python (torchfcpe) on committed
// fixtures (clay_research.parity.fcpe_fixtures), then the whole pipeline against the
// roadmap's analysis-parity tolerances.

#include "clay/analysis/Fcpe.h"

#include <algorithm>
#include <catch2/catch_test_macros.hpp>
#include <catch2/generators/catch_generators.hpp>
#include <cmath>
#include <cstddef>
#include <fstream>
#include <nlohmann/json.hpp>
#include <sstream>
#include <string>
#include <vector>

using namespace clay::analysis;

namespace
{
const std::string kFixtures = std::string(CLAY_FIXTURES_DIR) + "/fcpe/";
const std::string kModel = std::string(CLAY_MODELS_DIR) + "/fcpe_c_v001.onnx";

std::vector<float> readFloats(const std::string& name)
{
    std::ifstream in(kFixtures + name, std::ios::binary | std::ios::ate);
    REQUIRE(in.good());
    const auto bytes = static_cast<std::size_t>(in.tellg());
    std::vector<float> v(bytes / sizeof(float));
    in.seekg(0);
    in.read(reinterpret_cast<char*>(v.data()), static_cast<std::streamsize>(bytes));
    return v;
}

float maxAbsDiff(const std::vector<float>& a, const std::vector<float>& b, std::size_t count)
{
    float worst = 0.0f;
    for (std::size_t i = 0; i < count; ++i)
        worst = std::max(worst, std::abs(a[i] - b[i]));
    return worst;
}

// The tracker's 5% headroom step, so stage inputs match what Python fed torchfcpe.
std::vector<float> withHeadroom(std::vector<float> audio)
{
    float peak = 0.0f;
    for (float v : audio)
        peak = std::max(peak, std::abs(v));
    if (peak > 0.95f)
    {
        const auto gain = static_cast<float>(0.95 / static_cast<double>(peak));
        for (float& v : audio)
            v *= gain;
    }
    return audio;
}

const FcpeTracker& tracker()
{
    static const FcpeTracker t(kModel);
    return t;
}
} // namespace

TEST_CASE("Mel filter bank matches librosa", "[analysis][fcpe][parity]")
{
    const auto expected = readFloats("mel_basis.f32");
    const auto basis = fcpe::melBasis();
    REQUIRE(basis.size() == expected.size());
    const float worst = maxAbsDiff(basis, expected, basis.size());
    INFO("max difference " << worst);
    REQUIRE(worst < 1e-7f); // weights are at most ~0.003
}

TEST_CASE("FCPE stages match torchfcpe", "[analysis][fcpe][parity]")
{
    const int rate = GENERATE(44100, 48000, 96000);
    const std::string prefix = "pipeline_" + std::to_string(rate) + ".";
    INFO("sample rate " << rate);
    const auto audio = withHeadroom(readFloats(prefix + "audio.f32"));

    // 1. Resampling to 16 kHz (torchaudio).
    const auto expectedResampled = readFloats(prefix + "resampled.f32");
    const auto resampled = fcpe::resample(audio, rate, FcpeTracker::kModelSampleRate);
    REQUIRE(resampled.size() == expectedResampled.size());
    const float resampleDiff = maxAbsDiff(resampled, expectedResampled, resampled.size());
    INFO("resample max difference " << resampleDiff);
    REQUIRE(resampleDiff < 1e-5f);

    // 2. Log-mel spectrogram (Python's last frame is torchfcpe's appended copy).
    const auto expectedMel = readFloats(prefix + "mel.f32");
    std::size_t frames = 0;
    const auto mel = fcpe::logMel(expectedResampled, frames);
    REQUIRE((frames + 1) * FcpeNetwork::kMelBands == expectedMel.size());
    // Two FFT libraries round differently in float32. In bands ~100 dB below a frame's
    // peak that rounding is a visible fraction of the value, and the log magnifies it, so
    // near-silent bands get a looser bound. (Measured: ~0.3% of values, max 0.005.)
    constexpr float kSixtyDb = 6.9078f; // ln(1000): 60 dB in natural-log energy
    float loudDiff = 0.0f, quietDiff = 0.0f;
    for (std::size_t f = 0; f < frames; ++f)
    {
        const float* e = expectedMel.data() + f * FcpeNetwork::kMelBands;
        const float* a = mel.data() + f * FcpeNetwork::kMelBands;
        const float peak = *std::max_element(e, e + FcpeNetwork::kMelBands);
        for (std::size_t b = 0; b < FcpeNetwork::kMelBands; ++b)
        {
            float& worst = e[b] > peak - kSixtyDb ? loudDiff : quietDiff;
            worst = std::max(worst, std::abs(a[b] - e[b]));
        }
    }
    INFO("log-mel max difference: within 60 dB of peak " << loudDiff << ", below " << quietDiff);
    REQUIRE(loudDiff < 1e-3f);
    REQUIRE(quietDiff < 0.05f);
}

TEST_CASE("FCPE tracker meets analysis parity with Python", "[analysis][fcpe][parity]")
{
    const int rate = GENERATE(44100, 48000, 96000);
    const std::string prefix = "pipeline_" + std::to_string(rate) + ".";
    INFO("sample rate " << rate);
    const auto expected = readFloats(prefix + "f0.f32");
    const auto track = tracker().track(readFloats(prefix + "audio.f32"), rate);
    REQUIRE(track.f0Hz.size() == expected.size());

    std::size_t agree = 0;
    std::vector<double> cents;
    for (std::size_t i = 0; i < expected.size(); ++i)
    {
        const bool a = track.f0Hz[i] > 0.0f, b = expected[i] > 0.0f;
        agree += a == b ? 1u : 0u;
        if (a && b)
            cents.push_back(std::abs(1200.0 * std::log2(static_cast<double>(track.f0Hz[i]) / expected[i])));
    }
    REQUIRE(!cents.empty());
    std::sort(cents.begin(), cents.end());
    const double voicing = static_cast<double>(agree) / static_cast<double>(expected.size());
    INFO("voicing agreement " << voicing << ", median " << cents[cents.size() / 2] << " cents, max "
                              << cents.back() << " cents");
    // docs/ROADMAP.md "Analysis parity".
    REQUIRE(voicing >= 0.995);
    REQUIRE(cents[cents.size() / 2] <= 1.0);
    REQUIRE(cents.back() <= 5.0);
}

TEST_CASE("FCPE tracker handles silence and very short input", "[analysis][fcpe]")
{
    const auto empty = tracker().track({}, 44100);
    REQUIRE(empty.f0Hz.size() == 1);
    REQUIRE(empty.f0Hz[0] == 0.0f);

    const auto silence = tracker().track(std::vector<float>(48000, 0.0f), 48000);
    // 1 s at 16 kHz gives 100 mel frames; torchfcpe appends one copy of the last -> 101.
    REQUIRE(silence.f0Hz.size() == 101);
    REQUIRE(std::all_of(silence.f0Hz.begin(), silence.f0Hz.end(), [](float f) { return f == 0.0f; }));

    REQUIRE_THROWS(tracker().track({0.0f}, 0));
}
