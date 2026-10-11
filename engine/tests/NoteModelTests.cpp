// Parity tests: the C++ note model must match Python on committed fixtures
// (engine/tests/fixtures/note_model, made by clay_research.parity.note_model_fixtures).

#include "clay/engine/NoteModel.h"

#include <catch2/catch_test_macros.hpp>
#include <catch2/generators/catch_generators.hpp>
#include <cmath>
#include <cstddef>
#include <fstream>
#include <nlohmann/json.hpp>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>

using clay::model::NoteModel;

namespace
{
// Same arithmetic in both languages; a tiny tolerance absorbs fused multiply-add
// differences between compilers.
constexpr double kTol = 1e-9;

std::string readFile(const std::string& name)
{
    std::ifstream in(std::string(CLAY_FIXTURES_DIR) + "/note_model/" + name, std::ios::binary);
    REQUIRE(in.good());
    std::stringstream ss;
    ss << in.rdbuf();
    return ss.str();
}

void requireSame(const std::vector<double>& actual, const nlohmann::json& expected, const char* what)
{
    INFO(what);
    REQUIRE(actual.size() == expected.size());
    for (std::size_t i = 0; i < actual.size(); ++i)
    {
        INFO("frame " << i);
        if (expected[i].is_null())
        {
            REQUIRE(std::isnan(actual[i]));
        }
        else
        {
            REQUIRE_FALSE(std::isnan(actual[i]));
            REQUIRE(std::abs(actual[i] - expected[i].get<double>()) <= kTol);
        }
    }
}

void requireSameModel(const NoteModel& a, const NoteModel& b)
{
    REQUIRE(a.sampleRate == b.sampleRate);
    REQUIRE(a.duration == b.duration);
    REQUIRE(a.analysisVersion == b.analysisVersion);
    REQUIRE(a.hopSeconds == b.hopSeconds);
    REQUIRE(a.notes == b.notes);
    REQUIRE(a.f0Midi.size() == b.f0Midi.size());
    for (std::size_t i = 0; i < a.f0Midi.size(); ++i)
    {
        REQUIRE(std::isnan(a.f0Midi[i]) == std::isnan(b.f0Midi[i]));
        if (!std::isnan(a.f0Midi[i]))
            REQUIRE(std::abs(a.f0Midi[i] - b.f0Midi[i]) <= 1e-12);
        REQUIRE(std::abs(a.rmsDb[i] - b.rmsDb[i]) <= 1e-12);
    }
}
} // namespace

TEST_CASE("Note model derived curves match Python", "[model][parity]")
{
    const std::string name = GENERATE(as<std::string>{}, "vocadito_1", "edge", "empty");
    INFO("fixture " << name);
    const auto model = NoteModel::fromJson(readFile(name + ".model.json"));
    const auto expected = nlohmann::json::parse(readFile(name + ".expected.json"));

    requireSame(model.times(), expected["times"], "times");
    const auto curves = model.editCurves();
    requireSame(curves.pitch, expected["pitch"], "pitch curve");
    requireSame(curves.formant, expected["formant"], "formant curve");
    requireSame(curves.gain, expected["gain"], "gain curve");
    requireSame(curves.flatten, expected["flatten"], "flatten curve");
    requireSame(model.targetF0Midi(), expected["target_f0_midi"], "target f0");

    const auto span = model.noteSpan();
    const auto& expectedSpan = expected["note_span"];
    REQUIRE(span.size() == expectedSpan.size());
    for (std::size_t i = 0; i < span.size(); ++i)
    {
        INFO("frame " << i);
        REQUIRE(span[i] == expectedSpan[i].get<bool>());
    }
    REQUIRE(model.isNeutral() == expected["is_neutral"].get<bool>());
}

TEST_CASE("Note model JSON round-trips and matches Python's file", "[model][parity]")
{
    const std::string name = GENERATE(as<std::string>{}, "vocadito_1", "edge", "empty");
    INFO("fixture " << name);
    const std::string pythonText = readFile(name + ".model.json");
    const auto model = NoteModel::fromJson(pythonText);

    // C++ -> JSON -> C++ keeps everything.
    requireSameModel(NoteModel::fromJson(model.toJson()), model);

    // The C++-written file holds the same values as the Python-written one.
    const auto ours = nlohmann::json::parse(model.toJson());
    const auto theirs = nlohmann::json::parse(pythonText);
    REQUIRE(ours["schema"] == theirs["schema"]);
    REQUIRE(ours["version"] == theirs["version"]);
    REQUIRE(ours["notes"] == theirs["notes"]);
    REQUIRE(ours["frames"]["f0_midi"].size() == theirs["frames"]["f0_midi"].size());
    for (const char* key : {"f0_midi", "rms_db"})
        for (std::size_t i = 0; i < ours["frames"][key].size(); ++i)
        {
            const auto& a = ours["frames"][key][i];
            const auto& b = theirs["frames"][key][i];
            REQUIRE(a.is_null() == b.is_null());
            if (!a.is_null())
                REQUIRE(std::abs(a.get<double>() - b.get<double>()) <= 1e-12);
        }
}

TEST_CASE("Note model rejects files that are not Clay note models", "[model]")
{
    REQUIRE_THROWS_AS(NoteModel::fromJson("not json"), std::runtime_error);
    REQUIRE_THROWS_AS(NoteModel::fromJson(R"({"schema": "something else"})"), std::runtime_error);
    REQUIRE_THROWS_AS(NoteModel::fromJson(R"({"schema": "clay.note_model", "version": 2})"),
                      std::runtime_error);
    REQUIRE_THROWS_AS(NoteModel::fromJson(R"({"schema": "clay.note_model", "version": 1})"),
                      std::runtime_error);
}

TEST_CASE("Editing never touches the analysis; reset restores neutral", "[model]")
{
    auto model = NoteModel::fromJson(readFile("vocadito_1.model.json"));
    const auto f0Before = model.f0Midi;
    REQUIRE_FALSE(model.isNeutral());
    model.resetEdits();
    REQUIRE(model.isNeutral());
    for (std::size_t i = 0; i < f0Before.size(); ++i)
        REQUIRE((std::isnan(f0Before[i]) ? std::isnan(model.f0Midi[i]) : f0Before[i] == model.f0Midi[i]));
    // With no edits the target pitch is the analysed pitch.
    const auto target = model.targetF0Midi();
    for (std::size_t i = 0; i < target.size(); ++i)
        REQUIRE((std::isnan(f0Before[i]) ? std::isnan(target[i]) : target[i] == f0Before[i]));
}
