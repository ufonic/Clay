// Parity: the C++ FCPE network (ONNX Runtime) must reproduce Python's output on the
// committed fixture (clay_research.parity.fcpe_fixtures).

#include "clay/analysis/FcpeNetwork.h"

#include <algorithm>
#include <catch2/catch_test_macros.hpp>
#include <cmath>
#include <cstddef>
#include <fstream>
#include <nlohmann/json.hpp>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>

using clay::analysis::FcpeNetwork;

namespace
{
const std::string kFixtures = std::string(CLAY_FIXTURES_DIR) + "/fcpe/";
const std::string kModel = std::string(CLAY_MODELS_DIR) + "/fcpe_c_v001.onnx";

std::vector<float> readFloats(const std::string& path, std::size_t count)
{
    std::ifstream in(path, std::ios::binary);
    REQUIRE(in.good());
    std::vector<float> v(count);
    in.read(reinterpret_cast<char*>(v.data()), static_cast<std::streamsize>(count * sizeof(float)));
    REQUIRE(static_cast<std::size_t>(in.gcount()) == count * sizeof(float));
    return v;
}

nlohmann::json readJson(const std::string& path)
{
    std::ifstream in(path);
    REQUIRE(in.good());
    std::stringstream ss;
    ss << in.rdbuf();
    return nlohmann::json::parse(ss.str());
}
} // namespace

TEST_CASE("FCPE network matches Python on the fixture", "[analysis][fcpe][parity]")
{
    const auto meta = readJson(kFixtures + "network.json");
    const auto frames = meta["frames"].get<std::size_t>();
    REQUIRE(meta["mel_bands"].get<std::size_t>() == FcpeNetwork::kMelBands);
    REQUIRE(meta["pitch_bins"].get<std::size_t>() == FcpeNetwork::kPitchBins);

    const auto mel = readFloats(kFixtures + "network.mel.f32", frames * FcpeNetwork::kMelBands);
    const auto expected = readFloats(kFixtures + "network.latent.f32", frames * FcpeNetwork::kPitchBins);

    const FcpeNetwork net(kModel);
    const auto latent = net.latent(mel, frames);
    REQUIRE(latent.size() == expected.size());

    float worst = 0.0f;
    for (std::size_t i = 0; i < latent.size(); ++i)
        worst = std::max(worst, std::abs(latent[i] - expected[i]));
    INFO("max difference " << worst);
    // Scores are 0..1; CPU-specific float rounding is ~1e-6.
    REQUIRE(worst < 1e-4f);
}

TEST_CASE("FCPE network handles empty input and rejects bad shapes", "[analysis][fcpe]")
{
    const FcpeNetwork net(kModel);
    REQUIRE(net.latent({}, 0).empty());
    REQUIRE_THROWS_AS(net.latent(std::vector<float>(100), 1), std::invalid_argument);
    REQUIRE_THROWS_AS(FcpeNetwork("does/not/exist.onnx"), std::runtime_error);
}
