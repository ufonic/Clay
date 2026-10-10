#pragma once

#include "PluginProcessor.h"

namespace clay
{
// Phase 0 placeholder window: shows the name, version, and that audio passes through.
class PluginEditor final : public juce::AudioProcessorEditor
{
public:
    explicit PluginEditor(PluginProcessor&);
    ~PluginEditor() override = default;

    void paint(juce::Graphics&) override;
    void resized() override {}

private:
    JUCE_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR(PluginEditor)
};
} // namespace clay
