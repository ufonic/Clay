#pragma once

// The note model: Clay's single source of truth (CLAUDE.md § 2; spec: docs/model/SPEC.md).
//
// C++ port of research/src/clay_research/model/note_model.py (task 2.1). Two parts, kept
// apart on purpose:
// - analysis: what was sung (pitch every 5 ms, loudness, the notes). Never changed by
//   editing.
// - edits: a few numbers per note (pitch shift, drift amount, formant shift, gain).
// Audio is always rendered from analysis + edits, so "undo everything" = reset the edits.
//
// Reads and writes the same JSON files as Python ("clay.note_model" version 1). Parity
// tests check every derived curve against Python on committed fixtures.

#include <string>
#include <string_view>
#include <vector>

namespace clay::model
{

inline constexpr std::string_view kSchema = "clay.note_model";
inline constexpr int kVersion = 1;
inline constexpr double kHopSeconds = 0.005;       // SPEC decision 1: 5 ms frames
inline constexpr double kTransitionSeconds = 0.03; // edits fade over 30 ms at note edges
inline constexpr double kBridgeSeconds = 0.3;      // gaps up to this glide note to note

struct NoteEdit
{
    double pitchShiftSt = 0.0;   // move the whole note, semitones
    double driftScale = 1.0;     // 1 = keep the singer's wobble/vibrato; 0 = flatten
    double formantShiftSt = 0.0; // change voice character without changing pitch
    double gainDb = 0.0;

    bool isNeutral() const { return *this == NoteEdit{}; }
    bool operator==(const NoteEdit&) const = default;
};

struct Note
{
    double onset = 0.0;  // seconds
    double offset = 0.0; // seconds
    double centerMidi = 0.0;
    NoteEdit edit;

    bool operator==(const Note&) const = default;
};

// Per-frame edit amounts (see NoteModel::editCurves).
struct EditCurves
{
    std::vector<double> pitch;   // semitones
    std::vector<double> formant; // semitones
    std::vector<double> gain;    // dB
    std::vector<double> flatten; // 0 = keep drift, 1 = remove it
};

struct NoteModel
{
    int sampleRate = 44100;
    double duration = 0.0;      // seconds
    std::vector<double> f0Midi; // per frame; NaN = unvoiced
    std::vector<double> rmsDb;  // per frame
    std::vector<Note> notes;
    std::string analysisVersion = "1.0";
    double hopSeconds = kHopSeconds;

    // Frame i is at i * hopSeconds.
    std::vector<double> times() const;

    // --- editing (analysis is never touched) ---
    bool isNeutral() const;
    void resetEdits();

    // --- what to render ---
    // Each note's edit holds from onset to offset; gaps up to kBridgeSeconds glide from
    // one note's edit to the next; elsewhere edits fade to zero over kTransitionSeconds.
    EditCurves editCurves() const;
    // Pitch to render per frame: analysed pitch + shift, with drift scaled. NaN = unvoiced.
    std::vector<double> targetF0Midi() const;
    // True where an edit can reach (notes, their fades, bridged gaps). Elsewhere the
    // renderer keeps the original audio (breaths, noise between phrases).
    std::vector<bool> noteSpan() const;

    // --- JSON ---
    // Throws std::runtime_error if the text is not a Clay note model of this version.
    static NoteModel fromJson(std::string_view text);
    std::string toJson() const;
};

} // namespace clay::model
