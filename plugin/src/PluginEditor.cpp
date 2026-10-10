#include "PluginEditor.h"

#include "clay/engine/Version.h"

namespace clay
{
namespace
{
const auto background = juce::Colour(0xff1e1f24);
const auto accent = juce::Colour(0xffd9a066);
} // namespace

PluginEditor::PluginEditor(PluginProcessor& p) : AudioProcessorEditor(&p), processor_(p)
{
    using Mode = PluginProcessor::Mode;

    transferButton_.onClick = [this]
    {
        if (processor_.mode() == Mode::Capture)
            processor_.setMode(Mode::PassThrough);
        else
            processor_.startCapture();
        refreshButtons();
    };
    playButton_.onClick = [this]
    {
        processor_.setMode(processor_.mode() == Mode::Playback ? Mode::PassThrough : Mode::Playback);
        refreshButtons();
    };
    nullButton_.onClick = [this] { processor_.setNullTest(nullButton_.getToggleState()); };

    for (auto* b : {&transferButton_, &playButton_})
    {
        b->setColour(juce::TextButton::buttonOnColourId, accent);
        b->setColour(juce::TextButton::textColourOnId, juce::Colours::black);
        addAndMakeVisible(*b);
    }
    nullButton_.setToggleState(processor_.nullTest(), juce::dontSendNotification);
    addAndMakeVisible(nullButton_);

    setSize(520, 300);
    refreshButtons();
    startTimerHz(10);
}

void PluginEditor::refreshButtons()
{
    using Mode = PluginProcessor::Mode;
    const auto mode = processor_.mode();
    transferButton_.setToggleState(mode == Mode::Capture, juce::dontSendNotification);
    transferButton_.setButtonText(mode == Mode::Capture ? "Stop transfer" : "Transfer");
    playButton_.setToggleState(mode == Mode::Playback, juce::dontSendNotification);
    nullButton_.setEnabled(mode == Mode::Playback);
}

void PluginEditor::timerCallback()
{
    using Mode = PluginProcessor::Mode;
    const auto mode = processor_.mode();
    juce::String text;
    text << (mode == Mode::Capture    ? "Capturing: press play in the host"
             : mode == Mode::Playback ? "Playing captured audio"
                                      : "Pass-through")
         << "\n";
    text << "Captured: " << juce::String(processor_.capturedSeconds(), 2) << " s";
    if (processor_.capturedSeconds() > 0.0)
        text << " (from " << juce::String(processor_.capturedStartSeconds(), 2) << " s)";
    text << "\nHost position: "
         << (processor_.hostReportsPosition() ? juce::String(processor_.hostSeconds(), 3) + " s"
                                              : juce::String("not reported"));
    if (mode == Mode::Playback && processor_.nullTest())
    {
        const auto depth = processor_.nullDepthDb();
        text << "\nNull depth: "
             << (std::isfinite(depth) ? juce::String(depth, 1) + " dB" : juce::String("waiting for audio"))
             << (std::isfinite(depth) && depth < -90.0f ? "  (sample-exact)" : "");
    }
    if (text != status_)
    {
        status_ = text;
        repaint();
    }
    refreshButtons();
}

void PluginEditor::resized()
{
    auto area = getLocalBounds().reduced(24);
    area.removeFromTop(100);
    auto row = area.removeFromTop(36);
    transferButton_.setBounds(row.removeFromLeft(150));
    row.removeFromLeft(10);
    playButton_.setBounds(row.removeFromLeft(150));
    area.removeFromTop(8);
    nullButton_.setBounds(area.removeFromTop(28).withWidth(260));
}

void PluginEditor::paint(juce::Graphics& g)
{
    g.fillAll(background);
    auto area = getLocalBounds().reduced(24);

    g.setColour(accent);
    g.setFont(juce::FontOptions(36.0f, juce::Font::bold));
    g.drawText("Clay", area.removeFromTop(48), juce::Justification::centredLeft);

    g.setColour(juce::Colours::white.withAlpha(0.6f));
    g.setFont(juce::FontOptions(13.0f));
    g.drawText(juce::String("Engine ") + juce::String(engine::versionString().data()) +
                   "  ·  Phase 0: pass-through + Transfer spike",
               area.removeFromTop(20), juce::Justification::centredLeft);

    area.removeFromTop(108);
    g.setColour(juce::Colours::white.withAlpha(0.85f));
    g.setFont(juce::FontOptions(14.0f));
    g.drawMultiLineText(status_, area.getX(), area.getY() + 14, area.getWidth());
}
} // namespace clay
