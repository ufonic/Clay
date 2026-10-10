#pragma once

#include "PluginProcessor.h"

namespace clay
{
// Phase 0 window: name/version plus the Transfer spike controls and status.
class PluginEditor final : public juce::AudioProcessorEditor, private juce::Timer
{
public:
    explicit PluginEditor(PluginProcessor&);
    ~PluginEditor() override = default;

    void paint(juce::Graphics&) override;
    void resized() override;

private:
    void timerCallback() override;
    void refreshButtons();

    PluginProcessor& processor_;
    juce::TextButton transferButton_{"Transfer"};
    juce::TextButton playButton_{"Play captured"};
    juce::ToggleButton nullButton_{"Null test (captured - live)"};
    juce::String status_;

    JUCE_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR(PluginEditor)
};
} // namespace clay
