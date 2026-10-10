#include "PluginProcessor.h"

#include "PluginEditor.h"
#include "clay/engine/Version.h"

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

void PluginProcessor::prepareToPlay(double, int)
{
    setLatencySamples(0);
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

void PluginProcessor::processBlock(juce::AudioBuffer<float>& buffer, juce::MidiBuffer&)
{
    // Pass-through: input channels already hold the input, so leave them untouched.
    // Clear any extra output channels the host gave us. No allocation, locks, or I/O here.
    juce::ScopedNoDenormals noDenormals;
    for (auto ch = getTotalNumInputChannels(); ch < getTotalNumOutputChannels(); ++ch)
        buffer.clear(ch, 0, buffer.getNumSamples());
}

juce::AudioProcessorEditor* PluginProcessor::createEditor()
{
    return new PluginEditor(*this);
}

void PluginProcessor::getStateInformation(juce::MemoryBlock& destData)
{
    // Nothing to save yet beyond a version stamp, so state round-trips can be tested in hosts.
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
