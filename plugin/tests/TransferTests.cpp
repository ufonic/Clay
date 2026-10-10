// Transfer spike (task 0.8) driven by a fake host: capture what the "host" plays, play it
// back at the same timeline positions in different block sizes, and check it is
// sample-exact, allocation-free, and that the null test reads silence.

#include "../src/PluginProcessor.h"
#include "AllocationCounter.h"

#include <catch2/catch_test_macros.hpp>
#include <juce_events/juce_events.h>
#include <random>

namespace
{
constexpr double testSampleRate = 48000.0;
constexpr int maxBlock = 1024;

// What the host's clip sounds like at timeline sample p (deterministic, like a clip).
float clipSample(std::int64_t p, int channel)
{
    return 0.5f * std::sin(static_cast<float>(p) * 0.013f + static_cast<float>(channel)) +
           0.1f * static_cast<float>((p * 31) % 17) / 17.0f;
}

class FakeHost final : public juce::AudioPlayHead
{
public:
    juce::Optional<PositionInfo> getPosition() const override
    {
        PositionInfo info;
        info.setIsPlaying(playing);
        info.setTimeInSamples(position);
        return info;
    }
    std::int64_t position = 0;
    bool playing = true;
};

struct Rig
{
    juce::ScopedJuceInitialiser_GUI juceInit;
    clay::PluginProcessor processor;
    FakeHost host;
    juce::AudioBuffer<float> audio{2, maxBlock};
    juce::MidiBuffer midi;
    std::mt19937 rng{99};

    Rig()
    {
        processor.setPlayHead(&host);
        processor.setRateAndBufferSizeDetails(testSampleRate, maxBlock);
        processor.prepareToPlay(testSampleRate, maxBlock);
    }

    // Plays timeline [from, to) through the plugin in random block sizes. The host feeds
    // the clip delayed by `inputOffset` samples. Calls check(position, block) per block.
    template <typename Check>
    std::size_t play(std::int64_t from, std::int64_t to, int inputOffset, Check check)
    {
        std::uniform_int_distribution<int> blockSize(1, maxBlock);
        std::size_t allocations = 0;
        for (auto p = from; p < to;)
        {
            const auto n = static_cast<int>(std::min<std::int64_t>(blockSize(rng), to - p));
            for (int c = 0; c < 2; ++c)
                for (int i = 0; i < n; ++i)
                    audio.setSample(c, i, clipSample(p + i - inputOffset, c));
            juce::AudioBuffer<float> view(audio.getArrayOfWritePointers(), 2, n);
            host.position = p;
            {
                clay::test::ScopedAllocationCounter counter;
                processor.processBlock(view, midi);
                allocations += counter.count();
            }
            check(p, view);
            p += n;
        }
        return allocations;
    }
};
} // namespace

TEST_CASE("Transfer captures and plays back sample-exactly without allocating", "[transfer]")
{
    Rig rig;
    rig.processor.startCapture();
    const auto captureAllocs = rig.play(4800, 4800 + 96000, 0, [](auto, auto&) {});
    CHECK(captureAllocs == 0);
    CHECK(rig.processor.capturedSeconds() == 2.0);
    CHECK(rig.processor.capturedStartSeconds() == 0.1);

    // Play back with a *different* live input (silence) to prove the output comes from
    // the capture, not the input.
    rig.processor.setMode(clay::PluginProcessor::Mode::Playback);
    bool exact = true;
    std::uniform_int_distribution<int> blockSize(1, maxBlock);
    std::size_t playbackAllocs = 0;
    for (std::int64_t p = 4800; p < 4800 + 96000;)
    {
        const auto n = static_cast<int>(std::min<std::int64_t>(blockSize(rig.rng), 4800 + 96000 - p));
        rig.audio.clear();
        juce::AudioBuffer<float> view(rig.audio.getArrayOfWritePointers(), 2, n);
        rig.host.position = p;
        {
            clay::test::ScopedAllocationCounter counter;
            rig.processor.processBlock(view, rig.midi);
            playbackAllocs += counter.count();
        }
        for (int c = 0; c < 2; ++c)
            for (int i = 0; i < n; ++i)
                exact = exact && view.getSample(c, i) == clipSample(p + i, c);
        p += n;
    }
    CHECK(playbackAllocs == 0);
    CHECK(exact);
}

TEST_CASE("Null test reads silence in sync and catches a one-sample offset", "[transfer]")
{
    Rig rig;
    rig.processor.startCapture();
    rig.play(0, 48000, 0, [](auto, auto&) {});

    rig.processor.setMode(clay::PluginProcessor::Mode::Playback);
    rig.processor.setNullTest(true);
    float loudest = 0.0f;
    rig.play(0, 48000, 0, [&](auto, juce::AudioBuffer<float>& out)
             { loudest = std::max(loudest, out.getMagnitude(0, out.getNumSamples())); });
    CHECK(loudest == 0.0f);
    CHECK(rig.processor.nullDepthDb() < -150.0f);

    // Same clip arriving one sample late: the null test must expose it.
    rig.processor.setNullTest(true); // resets the measurement
    rig.play(0, 48000, 1, [](auto, auto&) {});
    CHECK(rig.processor.nullDepthDb() > -40.0f);
}

TEST_CASE("Transfer does nothing while the host is stopped", "[transfer]")
{
    Rig rig;
    rig.host.playing = false;
    rig.processor.startCapture();
    rig.play(0, 4800, 0, [](auto, auto&) {});
    CHECK(rig.processor.capturedSeconds() == 0.0);

    rig.processor.setMode(clay::PluginProcessor::Mode::Playback);
    bool passedThrough = true;
    rig.play(0, 4800, 0,
             [&](std::int64_t p, juce::AudioBuffer<float>& out)
             {
                 for (int i = 0; i < out.getNumSamples(); ++i)
                     passedThrough = passedThrough && out.getSample(0, i) == clipSample(p + i, 0);
             });
    CHECK(passedThrough);
}
