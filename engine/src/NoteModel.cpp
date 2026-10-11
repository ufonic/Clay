#include "clay/engine/NoteModel.h"

#include <algorithm>
#include <cmath>
#include <cstddef>
#include <limits>
#include <nlohmann/json.hpp>
#include <optional>
#include <stdexcept>
#include <utility>

namespace clay::model
{
namespace
{
using Json = nlohmann::ordered_json; // keeps keys in the same order Python writes them

constexpr double kNaN = std::numeric_limits<double>::quiet_NaN();

// numpy.interp(x, xp, fp, left, right), reproduced exactly (including its rules for
// repeated xp values) so curves match Python to the last bit. xp must be non-decreasing.
double interp(double x, const std::vector<double>& xp, const std::vector<double>& fp, double left,
              double right)
{
    const std::size_t n = xp.size();
    if (x > xp[n - 1])
        return right;
    if (x < xp[0])
        return left;
    // Last index j with xp[j] <= x (numpy's binary_search_with_guess).
    const auto j = static_cast<std::size_t>(std::upper_bound(xp.begin(), xp.end(), x) - xp.begin()) - 1;
    if (j == n - 1 || xp[j] == x)
        return fp[j];
    const double slope = (fp[j + 1] - fp[j]) / (xp[j + 1] - xp[j]);
    double y = slope * (x - xp[j]) + fp[j];
    if (std::isnan(y))
    {
        y = slope * (x - xp[j + 1]) + fp[j + 1];
        if (std::isnan(y) && fp[j] == fp[j + 1])
            y = fp[j];
    }
    return y;
}

std::vector<Note> sortedByOnset(const std::vector<Note>& notes)
{
    std::vector<Note> sorted = notes;
    std::stable_sort(sorted.begin(), sorted.end(),
                     [](const Note& a, const Note& b) { return a.onset < b.onset; });
    return sorted;
}

double fadeSeconds(double hop)
{
    return std::max(kTransitionSeconds, hop);
}

// Python's round(v, digits) for the values we write; NaN/inf become JSON null.
Json number(double v, int digits)
{
    if (!std::isfinite(v))
        return nullptr;
    const double scale = std::pow(10.0, digits);
    return std::round(v * scale) / scale;
}

double numberOrNaN(const Json& v)
{
    return v.is_null() ? kNaN : v.get<double>();
}

std::vector<double> frameArray(const Json& arr)
{
    std::vector<double> out;
    out.reserve(arr.size());
    for (const auto& v : arr)
        out.push_back(numberOrNaN(v));
    return out;
}
} // namespace

std::vector<double> NoteModel::times() const
{
    std::vector<double> t(f0Midi.size());
    for (std::size_t i = 0; i < t.size(); ++i)
        t[i] = static_cast<double>(i) * hopSeconds;
    return t;
}

bool NoteModel::isNeutral() const
{
    return std::all_of(notes.begin(), notes.end(), [](const Note& n) { return n.edit.isNeutral(); });
}

void NoteModel::resetEdits()
{
    for (auto& n : notes)
        n.edit = NoteEdit{};
}

EditCurves NoteModel::editCurves() const
{
    const auto t = times();
    EditCurves curves{std::vector<double>(t.size(), 0.0), std::vector<double>(t.size(), 0.0),
                      std::vector<double>(t.size(), 0.0), std::vector<double>(t.size(), 0.0)};
    if (notes.empty())
        return curves;

    const auto sorted = sortedByOnset(notes);
    const double fade = fadeSeconds(hopSeconds);

    // Knots of a piecewise-linear curve: (time, index into sorted, or none = "no edit").
    std::vector<std::pair<double, std::optional<std::size_t>>> knots;
    knots.emplace_back(sorted.front().onset - fade, std::nullopt);
    for (std::size_t i = 0; i < sorted.size(); ++i)
    {
        const Note& n = sorted[i];
        const double start = std::max(n.onset, knots.back().first);
        knots.emplace_back(start, i);
        knots.emplace_back(std::max(n.offset, start), i);
        const bool hasNext = i + 1 < sorted.size();
        if (!hasNext || sorted[i + 1].onset - n.offset > kBridgeSeconds)
        {
            knots.emplace_back(knots.back().first + fade, std::nullopt);
            if (hasNext)
                knots.emplace_back(std::max(sorted[i + 1].onset - fade, knots.back().first), std::nullopt);
        }
    }

    std::vector<double> xs;
    xs.reserve(knots.size());
    for (const auto& k : knots)
        xs.push_back(k.first);

    auto curveOf = [&](auto get, std::vector<double>& out)
    {
        std::vector<double> values;
        values.reserve(knots.size());
        for (const auto& k : knots)
            values.push_back(k.second ? get(sorted[*k.second].edit) : 0.0);
        for (std::size_t i = 0; i < t.size(); ++i)
            out[i] = interp(t[i], xs, values, 0.0, 0.0);
    };
    curveOf([](const NoteEdit& e) { return e.pitchShiftSt; }, curves.pitch);
    curveOf([](const NoteEdit& e) { return e.formantShiftSt; }, curves.formant);
    curveOf([](const NoteEdit& e) { return e.gainDb; }, curves.gain);
    curveOf([](const NoteEdit& e) { return 1.0 - e.driftScale; }, curves.flatten);
    return curves;
}

std::vector<double> NoteModel::targetF0Midi() const
{
    const auto t = times();
    const auto curves = editCurves();
    std::vector<double> center(t.size(), kNaN);
    for (const auto& n : notes) // later notes win where notes overlap (as in Python)
        for (std::size_t i = 0; i < t.size(); ++i)
            if (t[i] >= n.onset && t[i] < n.offset)
                center[i] = n.centerMidi;

    std::vector<double> out(t.size());
    for (std::size_t i = 0; i < t.size(); ++i)
    {
        // Outside notes, flattening has nothing to pull toward: keep the pitch.
        const double drift = std::isfinite(center[i]) ? f0Midi[i] - center[i] : 0.0;
        out[i] = f0Midi[i] + curves.pitch[i] - curves.flatten[i] * drift;
    }
    return out;
}

std::vector<bool> NoteModel::noteSpan() const
{
    const auto t = times();
    std::vector<bool> span(t.size(), false);
    const auto sorted = sortedByOnset(notes);
    const double fade = fadeSeconds(hopSeconds);
    for (std::size_t i = 0; i < sorted.size(); ++i)
    {
        const Note& n = sorted[i];
        double end = n.offset + fade;
        if (i + 1 < sorted.size() && sorted[i + 1].onset - n.offset <= kBridgeSeconds)
            end = sorted[i + 1].onset;
        for (std::size_t k = 0; k < t.size(); ++k)
            if (t[k] >= n.onset - fade && t[k] <= end)
                span[k] = true;
    }
    return span;
}

NoteModel NoteModel::fromJson(std::string_view text)
{
    Json d;
    try
    {
        d = Json::parse(text.begin(), text.end());
    }
    catch (const Json::parse_error& e)
    {
        throw std::runtime_error(std::string("note model is not valid JSON: ") + e.what());
    }
    if (!d.is_object() || d.value("schema", std::string{}) != kSchema)
        throw std::runtime_error("not a Clay note model");
    if (!d.contains("version") || d["version"] != kVersion)
        throw std::runtime_error("unsupported note model version");

    try
    {
        NoteModel m;
        m.sampleRate = d.at("sample_rate").get<int>();
        m.duration = d.at("duration").get<double>();
        m.analysisVersion = d.value("analysis_version", std::string("1.0"));
        const auto& frames = d.at("frames");
        m.hopSeconds = frames.at("hop_s").get<double>();
        m.f0Midi = frameArray(frames.at("f0_midi"));
        m.rmsDb = frameArray(frames.at("rms_db"));
        for (const auto& n : d.at("notes"))
        {
            const auto& e = n.at("edit");
            m.notes.push_back(Note{
                n.at("onset").get<double>(), n.at("offset").get<double>(), n.at("center_midi").get<double>(),
                NoteEdit{e.at("pitch_shift_st").get<double>(), e.at("drift_scale").get<double>(),
                         e.at("formant_shift_st").get<double>(), e.at("gain_db").get<double>()}});
        }
        return m;
    }
    catch (const Json::exception& e)
    {
        throw std::runtime_error(std::string("malformed note model: ") + e.what());
    }
}

std::string NoteModel::toJson() const
{
    auto arr = [](const std::vector<double>& a)
    {
        Json out = Json::array();
        for (double v : a)
            out.push_back(number(v, 4));
        return out;
    };
    Json notesJson = Json::array();
    for (const auto& n : notes)
    {
        // Notes keep full precision so save/load round-trips exactly.
        notesJson.push_back(Json{{"onset", n.onset},
                                 {"offset", n.offset},
                                 {"center_midi", n.centerMidi},
                                 {"edit",
                                  {{"pitch_shift_st", n.edit.pitchShiftSt},
                                   {"drift_scale", n.edit.driftScale},
                                   {"formant_shift_st", n.edit.formantShiftSt},
                                   {"gain_db", n.edit.gainDb}}}});
    }
    const Json d{{"schema", std::string(kSchema)},
                 {"version", kVersion},
                 {"sample_rate", sampleRate},
                 {"duration", number(duration, 6)},
                 {"analysis_version", analysisVersion},
                 {"frames", {{"hop_s", hopSeconds}, {"f0_midi", arr(f0Midi)}, {"rms_db", arr(rmsDb)}}},
                 {"notes", notesJson}};
    return d.dump();
}

} // namespace clay::model
