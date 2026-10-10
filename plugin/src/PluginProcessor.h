#pragma once

#include "clay/engine/TransferBuffer.h"

#include <atomic>
#include <juce_audio_processors/juce_audio_processors.h>
#include <limits>

namespace clay
{
// Phase 0: pass-through processor plus the Transfer spike (task 0.8). Records what the
// host plays through the plugin by timeline position, then plays it back in sync.
class PluginProcessor final : public juce::AudioProcessor
{
public:
    enum class Mode : int
    {
        PassThrough, // audio in = audio out
        Capture,     // record the host's audio while it plays (still passes it through)
        Playback,    // output the captured audio at the host's playhead position
    };

    // How long a capture can be. Phase 0 keeps it in memory; Phase 3 streams to disk.
    static constexpr double maxCaptureSeconds = 180.0;

    PluginProcessor();
    ~PluginProcessor() override = default;

    void prepareToPlay(double sampleRate, int samplesPerBlock) override;
    void releaseResources() override;
    bool isBusesLayoutSupported(const BusesLayout& layouts) const override;

    void processBlock(juce::AudioBuffer<float>&, juce::MidiBuffer&) override;
    using AudioProcessor::processBlock;

    juce::AudioProcessorEditor* createEditor() override;
    bool hasEditor() const override { return true; }

    const juce::String getName() const override { return JucePlugin_Name; }
    bool acceptsMidi() const override { return false; }
    bool producesMidi() const override { return false; }
    bool isMidiEffect() const override { return false; }
    double getTailLengthSeconds() const override { return 0.0; }

    // Some hosts misbehave with zero programs, so report one.
    int getNumPrograms() override { return 1; }
    int getCurrentProgram() override { return 0; }
    void setCurrentProgram(int) override {}
    const juce::String getProgramName(int) override { return {}; }
    void changeProgramName(int, const juce::String&) override {}

    void getStateInformation(juce::MemoryBlock& destData) override;
    void setStateInformation(const void* data, int sizeInBytes) override;

    // --- Transfer controls (message thread) ---
    // Starts a fresh capture (forgets the previous one).
    void startCapture();
    void setMode(Mode m) { mode_.store(static_cast<int>(m)); }
    Mode mode() const { return static_cast<Mode>(mode_.load()); }
    // Null test: in Playback, output captured − live input. In perfect sync with the same
    // clip playing, that is silence; any offset is audible and shows in nullDepthDb().
    void setNullTest(bool on);
    bool nullTest() const { return nullTest_.load(); }

    // --- Status (any thread) ---
    double capturedSeconds() const;
    double capturedStartSeconds() const;
    bool hostReportsPosition() const { return hostHasPosition_.load(); }
    double hostSeconds() const { return hostSeconds_.load(); }
    // Residual level of the null test relative to the input, in dB (lower is better);
    // +inf until enough audio has been compared.
    float nullDepthDb() const { return nullDepthDb_.load(); }

private:
    engine::TransferBuffer transfer_;
    juce::AudioBuffer<float> scratch_;
    double sampleRate_ = 44100.0;

    std::atomic<int> mode_{static_cast<int>(Mode::PassThrough)};
    std::atomic<bool> clearRequested_{false};
    std::atomic<bool> nullTest_{false};
    std::atomic<bool> nullResetRequested_{false};
    std::atomic<bool> hostHasPosition_{false};
    std::atomic<double> hostSeconds_{0.0};
    std::atomic<float> nullDepthDb_{std::numeric_limits<float>::infinity()};
    double nullResidualEnergy_ = 0.0; // audio thread only
    double nullInputEnergy_ = 0.0;    // audio thread only

    JUCE_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR(PluginProcessor)
};
} // namespace clay
