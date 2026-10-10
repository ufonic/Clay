set(CLAY_PLUGIN_FORMATS VST3 Standalone)
if(APPLE)
    list(APPEND CLAY_PLUGIN_FORMATS AU)
endif()

juce_add_plugin(Clay
    PRODUCT_NAME "Clay"
    COMPANY_NAME "Clay"
    BUNDLE_ID "dev.clay.Clay"
    PLUGIN_MANUFACTURER_CODE Clay   # four characters, at least one upper-case
    PLUGIN_CODE Cly1                # four characters, exactly one upper-case
    FORMATS ${CLAY_PLUGIN_FORMATS}
    IS_SYNTH FALSE
    NEEDS_MIDI_INPUT FALSE
    NEEDS_MIDI_OUTPUT FALSE
    IS_MIDI_EFFECT FALSE
    EDITOR_WANTS_KEYBOARD_FOCUS FALSE
    COPY_PLUGIN_AFTER_BUILD FALSE   # install by hand; system plugin folders need admin on Windows
    VST3_CATEGORIES Fx "Pitch Shift"
    AU_MAIN_TYPE kAudioUnitType_Effect
    NEEDS_WEB_BROWSER FALSE
    NEEDS_CURL FALSE)

clap_juce_extensions_plugin(TARGET Clay
    CLAP_ID "dev.clay.Clay"
    CLAP_FEATURES audio-effect pitch-correction)

target_sources(Clay
    PRIVATE
        src/PluginProcessor.cpp
        src/PluginEditor.cpp)

target_compile_definitions(Clay
    PUBLIC
        JUCE_WEB_BROWSER=0
        JUCE_USE_CURL=0
        JUCE_VST3_CAN_REPLACE_VST2=0
        JUCE_DISPLAY_SPLASH_SCREEN=0)

target_link_libraries(Clay
    PRIVATE
        clay::engine
        juce::juce_audio_utils
    PUBLIC
        juce::juce_recommended_config_flags
        juce::juce_recommended_lto_flags
        juce::juce_recommended_warning_flags)
