#include "clay/engine/TransferBuffer.h"

#include <catch2/catch_test_macros.hpp>
#include <random>
#include <vector>

using clay::engine::TransferBuffer;

namespace
{
// Deterministic "host audio": the value at timeline sample p on channel c.
float hostSample(std::int64_t p, int c)
{
    return static_cast<float>((p * 7 + c * 1000) % 2000) / 1000.0f - 1.0f;
}

struct Block
{
    std::vector<std::vector<float>> channels;
    std::vector<float*> pointers;

    Block(int numChannels, int numSamples)
        : channels(static_cast<std::size_t>(numChannels),
                   std::vector<float>(static_cast<std::size_t>(numSamples)))
    {
        for (auto& ch : channels)
            pointers.push_back(ch.data());
    }
    void fillFromHost(std::int64_t position)
    {
        for (std::size_t c = 0; c < channels.size(); ++c)
            for (std::size_t i = 0; i < channels[c].size(); ++i)
                channels[c][i] = hostSample(position + static_cast<std::int64_t>(i), static_cast<int>(c));
    }
};

// Plays the host timeline from `from` to `to` in random block sizes, capturing it.
void captureRange(TransferBuffer& buffer, std::int64_t from, std::int64_t to, std::mt19937& rng)
{
    std::uniform_int_distribution<int> blockSize(1, 1024);
    for (auto p = from; p < to;)
    {
        const auto n = static_cast<int>(std::min<std::int64_t>(blockSize(rng), to - p));
        Block block(buffer.numChannels(), n);
        block.fillFromHost(p);
        buffer.write(p, block.pointers.data(), buffer.numChannels(), n);
        p += n;
    }
}
} // namespace

TEST_CASE("Captured audio plays back sample-exactly in different block sizes", "[transfer]")
{
    TransferBuffer buffer;
    buffer.prepare(2, 48000.0, 10.0);
    std::mt19937 rng(42);
    captureRange(buffer, 1000, 200000, rng);

    REQUIRE(buffer.capturedStart() == 1000);
    REQUIRE(buffer.capturedEnd() == 200000);

    std::uniform_int_distribution<int> blockSize(1, 777);
    bool exact = true;
    for (std::int64_t p = 1000; p < 200000 && exact;)
    {
        const auto n = static_cast<int>(std::min<std::int64_t>(blockSize(rng), 200000 - p));
        Block out(2, n);
        CHECK(buffer.read(p, out.pointers.data(), 2, n) == n);
        for (int c = 0; c < 2; ++c)
            for (int i = 0; i < n; ++i)
                exact = exact && out.channels[static_cast<std::size_t>(c)][static_cast<std::size_t>(i)] ==
                                     hostSample(p + i, c);
        p += n;
    }
    CHECK(exact);
}

TEST_CASE("Reading outside the captured range gives silence", "[transfer]")
{
    TransferBuffer buffer;
    buffer.prepare(1, 1000.0, 10.0);
    std::mt19937 rng(1);
    captureRange(buffer, 100, 200, rng);

    Block out(1, 300);
    CHECK(buffer.read(0, out.pointers.data(), 1, 300) == 100);
    CHECK(out.channels[0][99] == 0.0f);
    CHECK(out.channels[0][100] == hostSample(100, 0));
    CHECK(out.channels[0][199] == hostSample(199, 0));
    CHECK(out.channels[0][200] == 0.0f);
}

TEST_CASE("Negative positions and positions past capacity are ignored", "[transfer]")
{
    TransferBuffer buffer;
    buffer.prepare(1, 1000.0, 1.0); // capacity 1000 samples
    Block in(1, 100);
    in.fillFromHost(-50);
    CHECK(buffer.write(-50, in.pointers.data(), 1, 100) == 50);
    CHECK(buffer.capturedStart() == 0);
    CHECK(buffer.capturedEnd() == 50);

    in.fillFromHost(950);
    CHECK(buffer.write(950, in.pointers.data(), 1, 100) == 50);
    CHECK(buffer.capturedEnd() == 1000);
}

TEST_CASE("A jump while capturing silences the gap instead of replaying old audio", "[transfer]")
{
    TransferBuffer buffer;
    buffer.prepare(1, 1000.0, 10.0);
    std::mt19937 rng(7);
    captureRange(buffer, 0, 3000, rng); // first take fills 0..3000
    buffer.clear();

    captureRange(buffer, 0, 500, rng);     // new take starts at 0 ...
    captureRange(buffer, 2000, 2500, rng); // ... and the host jumps to 2000

    Block out(1, 1500);
    buffer.read(500, out.pointers.data(), 1, 1500);
    bool gapSilent = true;
    for (auto v : out.channels[0])
        gapSilent = gapSilent && v == 0.0f;
    CHECK(gapSilent);
}

TEST_CASE("Mono capture plays on both output channels", "[transfer]")
{
    TransferBuffer mono;
    mono.prepare(1, 1000.0, 1.0);
    Block in(1, 10);
    in.fillFromHost(0);
    mono.write(0, in.pointers.data(), 1, 10);
    Block out(2, 10);
    mono.read(0, out.pointers.data(), 2, 10);
    CHECK(out.channels[0] == in.channels[0]);
    CHECK(out.channels[1] == in.channels[0]);
}

TEST_CASE("clear() forgets the capture", "[transfer]")
{
    TransferBuffer buffer;
    buffer.prepare(2, 1000.0, 1.0);
    std::mt19937 rng(3);
    captureRange(buffer, 0, 500, rng);
    REQUIRE(buffer.hasCapture());
    buffer.clear();
    CHECK_FALSE(buffer.hasCapture());
    Block out(2, 100);
    CHECK(buffer.read(0, out.pointers.data(), 2, 100) == 0);
}
