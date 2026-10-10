// Audio-thread stress test (roadmap task 0.9): hammer processBlock with random block
// sizes at every supported sample rate and channel layout, and fail on any heap
// allocation or any change to the audio.

#include "../src/PluginProcessor.h"
#include "AllocationCounter.h"

#include <catch2/catch_test_macros.hpp>
#include <catch2/generators/catch_generators.hpp>
#include <chrono>
#include <juce_events/juce_events.h>

namespace
{
constexpr int maxBlockSize = 2048;
constexpr int blocksPerConfig = 5000;

juce::AudioProcessor::BusesLayout layoutFor(const juce::AudioChannelSet& set)
{
    juce::AudioProcessor::BusesLayout layout;
    layout.inputBuses.add(set);
    layout.outputBuses.add(set);
    return layout;
}
} // namespace

TEST_CASE("Allocation counter sees allocations", "[realtime]")
{
    // volatile so the optimizer can't remove the new/delete pair.
    static int* volatile sink = nullptr;
    clay::test::ScopedAllocationCounter counter;
    sink = new int(42);
    delete sink;
    CHECK(counter.count() == 1);
}

TEST_CASE("processBlock never allocates and passes audio through unchanged", "[realtime]")
{
    const juce::ScopedJuceInitialiser_GUI juceInit;

    const auto sampleRate = GENERATE(44100.0, 48000.0, 88200.0, 96000.0);
    const auto channels = GENERATE(1, 2);
    const auto set = channels == 1 ? juce::AudioChannelSet::mono() : juce::AudioChannelSet::stereo();
    CAPTURE(sampleRate, channels);

    clay::PluginProcessor processor;
    REQUIRE(processor.setBusesLayout(layoutFor(set)));
    processor.setRateAndBufferSizeDetails(sampleRate, maxBlockSize);
    processor.prepareToPlay(sampleRate, maxBlockSize);
    CHECK(processor.getLatencySamples() == 0);

    // Everything the loop needs is allocated up front, outside the counted section.
    juce::AudioBuffer<float> audio(channels, maxBlockSize);
    juce::AudioBuffer<float> expected(channels, maxBlockSize);
    juce::MidiBuffer midi;
    juce::Random random(1234);

    std::size_t allocations = 0;
    bool unchanged = true;
    double worstBlockSeconds = 0.0;
    double worstBlockBudget = 1.0;

    for (int block = 0; block < blocksPerConfig; ++block)
    {
        const auto numSamples = random.nextInt({1, maxBlockSize + 1});
        for (int ch = 0; ch < channels; ++ch)
            for (int i = 0; i < numSamples; ++i)
                audio.setSample(ch, i, random.nextFloat() * 2.0f - 1.0f);
        expected.makeCopyOf(audio, true);
        juce::AudioBuffer<float> view(audio.getArrayOfWritePointers(), channels, numSamples);

        const auto start = std::chrono::steady_clock::now();
        {
            clay::test::ScopedAllocationCounter counter;
            processor.processBlock(view, midi);
            allocations += counter.count();
        }
        const std::chrono::duration<double> took = std::chrono::steady_clock::now() - start;

        const auto budget = numSamples / sampleRate;
        if (took.count() / budget > worstBlockSeconds / worstBlockBudget)
        {
            worstBlockSeconds = took.count();
            worstBlockBudget = budget;
        }
        for (int ch = 0; ch < channels && unchanged; ++ch)
            for (int i = 0; i < numSamples && unchanged; ++i)
                unchanged = audio.getSample(ch, i) == expected.getSample(ch, i);
    }

    processor.releaseResources();

    CHECK(allocations == 0);
    CHECK(unchanged);
    // Timing varies on shared CI machines, so report it rather than gate on it.
    UNSCOPED_INFO("worst block used " << (100.0 * worstBlockSeconds / worstBlockBudget)
                                      << "% of its real-time budget");
}
