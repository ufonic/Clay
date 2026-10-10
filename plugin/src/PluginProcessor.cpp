#include "PluginProcessor.h"

#include "PluginEditor.h"
#include "clay/engine/Version.h"

#include <cmath>

namespace clay
{
namespace
{
constexpr auto stateTag = "ClayState";
}

PluginProcessor::PluginProcessor()
    : AudioProcessor(BusesProperties()
                         .withInput("Input", juce::AudioChannelSet::stereo(), true)
                         .withOutput("Output", juce::AudioChannelSet::stereo(), true))
{
}

void PluginProcessor::prepareToPlay(double sampleRate, int samplesPerBlock)
{
    setLatencySamples(0);
    sampleRate_ = sampleRate;
    // All allocation happens here, never in processBlock. A new sample rate or channel
    // count starts with an empty capture.
    const auto channels = std::max(1, getTotalNumInputChannels());
    transfer_.prepare(channels, sampleRate, maxCaptureSeconds);
    scratch_.setSize(std::max(1, getTotalNumOutputChannels()), samplesPerBlock);
}

void PluginProcessor::releaseResources() {}

bool PluginProcessor::isBusesLayoutSupported(const BusesLayout& layouts) const
{
    // Mono or stereo, same layout in and out.
    const auto out = layouts.getMainOutputChannelSet();
    if (out != juce::AudioChannelSet::mono() && out != juce::AudioChannelSet::stereo())
        return false;
    return out == layouts.getMainInputChannelSet();
}

void PluginProcessor::startCapture()
{
    clearRequested_.store(true);
    setMode(Mode::Capture);
}

void PluginProcessor::setNullTest(bool on)
{
    nullResetRequested_.store(true);
    nullTest_.store(on);
}

double PluginProcessor::capturedSeconds() const
{
    return static_cast<double>(transfer_.capturedEnd() - transfer_.capturedStart()) / sampleRate_;
}

double PluginProcessor::capturedStartSeconds() const
{
    return static_cast<double>(transfer_.capturedStart()) / sampleRate_;
}

// clay:realtime-begin
void PluginProcessor::processBlock(juce::AudioBuffer<float>& buffer, juce::MidiBuffer&)
{
    juce::ScopedNoDenormals noDenormals;
    const auto numIn = getTotalNumInputChannels();
    const auto numOut = getTotalNumOutputChannels();
    const auto numSamples = buffer.getNumSamples();
    for (auto ch = numIn; ch < numOut; ++ch)
        buffer.clear(ch, 0, numSamples);

    // Requests from the message thread are applied here so the buffer is only touched
    // by this thread while audio runs.
    if (clearRequested_.exchange(false))
        transfer_.clear();
    if (nullResetRequested_.exchange(false))
    {
        nullResidualEnergy_ = 0.0;
        nullInputEnergy_ = 0.0;
        nullDepthDb_.store(std::numeric_limits<float>::infinity());
    }

    // Where is the host? Transfer only works while the host is playing and tells us its
    // position in samples; otherwise behave as a pass-through.
    std::int64_t position = 0;
    bool playing = false;
    bool hasPosition = false;
    if (auto* hostPlayHead = getPlayHead())
    {
        if (const auto info = hostPlayHead->getPosition())
        {
            playing = info->getIsPlaying();
            if (const auto samples = info->getTimeInSamples())
            {
                position = *samples;
                hasPosition = true;
            }
        }
    }
    hostHasPosition_.store(hasPosition);
    if (hasPosition)
        hostSeconds_.store(static_cast<double>(position) / sampleRate_);
    if (!playing || !hasPosition || numIn == 0)
        return;

    const auto mode = static_cast<Mode>(mode_.load());
    if (mode == Mode::Capture)
    {
        transfer_.write(position, buffer.getArrayOfReadPointers(), numIn, numSamples);
        return;
    }
    if (mode != Mode::Playback || numSamples > scratch_.getNumSamples())
        return;

    const auto inside = transfer_.read(position, scratch_.getArrayOfWritePointers(), numOut, numSamples);
    if (nullTest_.load())
    {
        // Output = captured − live input; measure how close to silence that is.
        for (int ch = 0; ch < numOut; ++ch)
        {
            auto* out = buffer.getWritePointer(ch);
            const auto* captured = scratch_.getReadPointer(ch);
            for (int i = 0; i < numSamples; ++i)
            {
                const auto input = static_cast<double>(out[i]);
                const auto residual = static_cast<double>(captured[i]) - input;
                if (inside > 0)
                {
                    nullResidualEnergy_ += residual * residual;
                    nullInputEnergy_ += input * input;
                }
                out[i] = static_cast<float>(residual);
            }
        }
        if (nullInputEnergy_ > 1e-6)
        {
            const auto ratio = std::max(nullResidualEnergy_ / nullInputEnergy_, 1e-20);
            nullDepthDb_.store(static_cast<float>(10.0 * std::log10(ratio)));
        }
        return;
    }

    // Replace the live input with the capture wherever this block overlaps it.
    if (inside > 0)
        for (int ch = 0; ch < numOut; ++ch)
            buffer.copyFrom(ch, 0, scratch_, ch, 0, numSamples);
}
// clay:realtime-end

juce::AudioProcessorEditor* PluginProcessor::createEditor()
{
    return new PluginEditor(*this);
}

void PluginProcessor::getStateInformation(juce::MemoryBlock& destData)
{
    // Nothing to save yet beyond a version stamp, so state round-trips can be tested in hosts.
    // (The Phase 0 capture lives in memory only and is not saved with the project.)
    juce::ValueTree state(stateTag);
    state.setProperty("engineVersion", juce::String(engine::versionString().data()), nullptr);
    juce::MemoryOutputStream stream(destData, false);
    state.writeToStream(stream);
}

void PluginProcessor::setStateInformation(const void* data, int sizeInBytes)
{
    // Nothing to restore yet; the note model's state arrives in Phase 3.
    juce::ignoreUnused(data, sizeInBytes);
}
} // namespace clay

juce::AudioProcessor* JUCE_CALLTYPE createPluginFilter()
{
    return new clay::PluginProcessor();
}
