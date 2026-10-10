#include "PluginEditor.h"

#include "clay/engine/Version.h"

namespace clay
{
PluginEditor::PluginEditor(PluginProcessor& p) : AudioProcessorEditor(&p)
{
    setSize(480, 240);
}

void PluginEditor::paint(juce::Graphics& g)
{
    g.fillAll(juce::Colour(0xff1e1f24));
    auto area = getLocalBounds().reduced(24);

    g.setColour(juce::Colour(0xffd9a066));
    g.setFont(juce::FontOptions(40.0f, juce::Font::bold));
    g.drawText("Clay", area.removeFromTop(56), juce::Justification::centredLeft);

    g.setColour(juce::Colours::white.withAlpha(0.75f));
    g.setFont(juce::FontOptions(15.0f));
    const auto version = juce::String("Engine ") + juce::String(engine::versionString().data());
    g.drawText(version, area.removeFromTop(24), juce::Justification::centredLeft);
    g.drawText("Phase 0 pass-through: audio in = audio out", area.removeFromTop(24),
               juce::Justification::centredLeft);
}
} // namespace clay
