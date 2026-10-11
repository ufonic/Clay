#include "clay/analysis/Fcpe.h"

#include <algorithm>
#include <cmath>
#include <cstdint>
#include <memory>
#include <numbers>
#include <numeric>
#include <pffft/pffft.h>
#include <stdexcept>

namespace clay::analysis
{
namespace
{
constexpr std::size_t kMelBands = FcpeNetwork::kMelBands;
constexpr std::size_t kPitchBins = FcpeNetwork::kPitchBins;
constexpr std::size_t kFft = 1024; // n_fft == win_size
constexpr std::size_t kBins = kFft / 2 + 1;
constexpr int kLowpassWidth = 128; // torchfcpe passes lowpass_filter_width=128
constexpr double kRolloff = 0.99;
constexpr double kPi = std::numbers::pi;

// --- librosa's Slaney mel scale ---
constexpr double kFSp = 200.0 / 3.0;
constexpr double kMinLogHz = 1000.0;
constexpr double kMinLogMel = kMinLogHz / kFSp; // 15
const double kLogStep = std::log(6.4) / 27.0;

double hzToMel(double hz)
{
    return hz >= kMinLogHz ? kMinLogMel + std::log(hz / kMinLogHz) / kLogStep : hz / kFSp;
}

double melToHz(double mel)
{
    return mel >= kMinLogMel ? kMinLogHz * std::exp(kLogStep * (mel - kMinLogMel)) : kFSp * mel;
}

struct PffftSetup
{
    PffftSetup()
    {
        if (setup == nullptr)
            throw std::runtime_error("PFFFT setup failed");
    }
    ~PffftSetup() { pffft_destroy_setup(setup); }
    PffftSetup(const PffftSetup&) = delete;
    PffftSetup& operator=(const PffftSetup&) = delete;
    PFFFT_Setup* setup = pffft_new_setup(static_cast<int>(kFft), PFFFT_REAL);
};

struct AlignedFloats
{
    explicit AlignedFloats(std::size_t n) : data(static_cast<float*>(pffft_aligned_malloc(n * sizeof(float))))
    {
    }
    ~AlignedFloats() { pffft_aligned_free(data); }
    AlignedFloats(const AlignedFloats&) = delete;
    AlignedFloats& operator=(const AlignedFloats&) = delete;
    float* data;
};
} // namespace

namespace fcpe
{

std::vector<float> resample(const std::vector<float>& x, int origRate, int targetRate)
{
    if (origRate <= 0 || targetRate <= 0)
        throw std::invalid_argument("resample: sample rates must be positive");
    if (origRate == targetRate)
        return x;
    const int g = std::gcd(origRate, targetRate);
    const auto orig = static_cast<std::int64_t>(origRate / g);
    const auto target = static_cast<std::int64_t>(targetRate / g);

    // Kernel, exactly as torchaudio's _get_sinc_resample_kernel (float64 maths, stored as
    // float32). Its time offsets j / target are computed in float32 there; so are ours.
    const double base = static_cast<double>(std::min(orig, target)) * kRolloff;
    const auto width = static_cast<std::int64_t>(std::ceil(kLowpassWidth * static_cast<double>(orig) / base));
    const std::int64_t taps = 2 * width + orig;
    std::vector<float> kernel(static_cast<std::size_t>(target * taps));
    const double scale = base / static_cast<double>(orig);
    for (std::int64_t j = 0; j < target; ++j)
    {
        const float offset = static_cast<float>(-j) / static_cast<float>(target);
        for (std::int64_t k = 0; k < taps; ++k)
        {
            const double idx = static_cast<double>(k - width) / static_cast<double>(orig);
            double t = (static_cast<double>(offset) + idx) * base;
            t = std::clamp(t, -static_cast<double>(kLowpassWidth), static_cast<double>(kLowpassWidth));
            const double c = std::cos(t * kPi / kLowpassWidth / 2.0);
            const double window = c * c;
            t *= kPi;
            const double sinc = t == 0.0 ? 1.0 : std::sin(t) / t;
            kernel[static_cast<std::size_t>(j * taps + k)] = static_cast<float>(sinc * (window * scale));
        }
    }

    // Apply: zero-pad (width, width + orig), slide by orig, one output per kernel row.
    const auto length = static_cast<std::int64_t>(x.size());
    const std::int64_t blocks = length / orig + 1;
    // torchaudio: ceil(target * length / orig), with the quotient rounded to float32 first.
    const auto wanted = static_cast<std::int64_t>(
        std::ceil(static_cast<float>(static_cast<double>(target * length) / static_cast<double>(orig))));
    std::vector<float> y(static_cast<std::size_t>(std::min(wanted, blocks * target)));
    for (std::int64_t b = 0; b < blocks; ++b)
    {
        const std::int64_t start = b * orig - width; // first input sample under the kernel
        const std::int64_t k0 = std::max<std::int64_t>(0, -start);
        const std::int64_t k1 = std::min<std::int64_t>(taps, length - start);
        for (std::int64_t j = 0; j < target; ++j)
        {
            const std::int64_t out = b * target + j;
            if (out >= static_cast<std::int64_t>(y.size()))
                break;
            const float* kj = kernel.data() + j * taps;
            double acc = 0.0;
            for (std::int64_t k = k0; k < k1; ++k)
                acc +=
                    static_cast<double>(kj[k]) * static_cast<double>(x[static_cast<std::size_t>(start + k)]);
            y[static_cast<std::size_t>(out)] = static_cast<float>(acc);
        }
    }
    return y;
}

std::vector<float> melBasis()
{
    constexpr double sr = FcpeTracker::kModelSampleRate;
    constexpr std::size_t mels = kMelBands;
    // fft_frequencies: k * sr / n_fft (numpy rfftfreq: k * 1 / (n * (1 / sr))).
    std::vector<double> fftFreqs(kBins);
    const double step = 1.0 / (static_cast<double>(kFft) * (1.0 / sr));
    for (std::size_t k = 0; k < kBins; ++k)
        fftFreqs[k] = static_cast<double>(k) * step;
    // mel_frequencies(n_mels + 2, fmin=0, fmax=sr/2): numpy linspace in mel, then to Hz.
    std::vector<double> melF(mels + 2);
    const double maxMel = hzToMel(sr / 2.0);
    const double melStep = maxMel / static_cast<double>(mels + 1);
    for (std::size_t i = 0; i < melF.size(); ++i)
        melF[i] = melToHz(i + 1 == melF.size() ? maxMel : static_cast<double>(i) * melStep);

    std::vector<float> weights(mels * kBins);
    for (std::size_t i = 0; i < mels; ++i)
    {
        const double fdiffLo = melF[i + 1] - melF[i];
        const double fdiffHi = melF[i + 2] - melF[i + 1];
        const double enorm = 2.0 / (melF[i + 2] - melF[i]);
        for (std::size_t k = 0; k < kBins; ++k)
        {
            const double lower = -(melF[i] - fftFreqs[k]) / fdiffLo;
            const double upper = (melF[i + 2] - fftFreqs[k]) / fdiffHi;
            const auto w = static_cast<float>(std::max(0.0, std::min(lower, upper)));
            weights[i * kBins + k] = static_cast<float>(static_cast<double>(w) * enorm);
        }
    }
    return weights;
}

std::vector<float> logMel(const std::vector<float>& audio16k, std::size_t& frames)
{
    constexpr std::size_t hop = FcpeTracker::kHop;
    const std::size_t len = audio16k.size();
    const std::size_t padLeft = (kFft - hop) / 2;
    const std::size_t padRight =
        std::max((kFft - hop + 1) / 2, kFft > len + padLeft ? kFft - len - padLeft : std::size_t{0});
    const bool reflect = padRight < len;

    std::vector<float> padded(padLeft + len + padRight, 0.0f);
    std::copy(audio16k.begin(), audio16k.end(), padded.begin() + static_cast<std::ptrdiff_t>(padLeft));
    if (reflect)
    {
        for (std::size_t i = 0; i < padLeft; ++i)
            padded[i] = audio16k[padLeft - i];
        for (std::size_t i = 0; i < padRight; ++i)
            padded[padLeft + len + i] = audio16k[len - 2 - i];
    }

    frames = 1 + (padded.size() - kFft) / hop;
    static const std::vector<float> basis = melBasis();
    std::vector<float> window(kFft);
    for (std::size_t n = 0; n < kFft; ++n) // torch.hann_window (periodic)
        window[n] = static_cast<float>(0.5 - 0.5 * std::cos(2.0 * kPi * static_cast<double>(n) / kFft));

    const PffftSetup fft;
    AlignedFloats in(kFft), out(kFft), work(kFft);
    std::vector<float> mag(kBins);
    std::vector<float> mel(frames * kMelBands);
    for (std::size_t f = 0; f < frames; ++f)
    {
        const float* src = padded.data() + f * hop;
        for (std::size_t n = 0; n < kFft; ++n)
            in.data[n] = src[n] * window[n];
        pffft_transform_ordered(fft.setup, in.data, out.data, work.data, PFFFT_FORWARD);
        // Ordered real output: [DC, Nyquist, re1, im1, re2, im2, ...].
        mag[0] = std::sqrt(out.data[0] * out.data[0] + 1e-9f);
        mag[kBins - 1] = std::sqrt(out.data[1] * out.data[1] + 1e-9f);
        for (std::size_t k = 1; k + 1 < kBins; ++k)
        {
            const float re = out.data[2 * k];
            const float im = out.data[2 * k + 1];
            mag[k] = std::sqrt(re * re + im * im + 1e-9f);
        }
        for (std::size_t b = 0; b < kMelBands; ++b)
        {
            const float* w = basis.data() + b * kBins;
            double acc = 0.0;
            for (std::size_t k = 0; k < kBins; ++k)
                acc += static_cast<double>(w[k]) * static_cast<double>(mag[k]);
            mel[f * kMelBands + b] = std::log(std::max(static_cast<float>(acc), 1e-5f));
        }
    }
    return mel;
}

std::vector<float> decode(const std::vector<float>& latent, std::size_t frames, float threshold)
{
    if (latent.size() != frames * kPitchBins)
        throw std::invalid_argument("decode: latent must hold frames x 360 values");
    // Cents above 10 Hz for each bin, evenly spaced from 32.70 Hz to 1975.5 Hz.
    static const std::vector<double> centTable = []
    {
        std::vector<double> c(kPitchBins);
        const double lo = 1200.0 * std::log2(32.70 / 10.0);
        const double hi = 1200.0 * std::log2(1975.5 / 10.0);
        for (std::size_t i = 0; i < kPitchBins; ++i)
            c[i] = lo + (hi - lo) * static_cast<double>(i) / static_cast<double>(kPitchBins - 1);
        return c;
    }();

    std::vector<float> f0(frames, 0.0f);
    for (std::size_t f = 0; f < frames; ++f)
    {
        const float* y = latent.data() + f * kPitchBins;
        const auto best = static_cast<std::ptrdiff_t>(std::max_element(y, y + kPitchBins) - y);
        if (y[best] <= threshold)
            continue; // unvoiced
        double num = 0.0, den = 0.0;
        for (std::ptrdiff_t d = -4; d <= 4; ++d)
        {
            // Indices are clamped at the edges, so edge bins count more than once (as in torch).
            constexpr auto last = static_cast<std::ptrdiff_t>(kPitchBins - 1);
            const auto i = static_cast<std::size_t>(std::clamp<std::ptrdiff_t>(best + d, 0, last));
            num += centTable[i] * static_cast<double>(y[i]);
            den += static_cast<double>(y[i]);
        }
        f0[f] = static_cast<float>(10.0 * std::exp2(num / den / 1200.0));
    }
    return f0;
}

} // namespace fcpe

FcpeTracker::FcpeTracker(const std::filesystem::path& modelPath, int threads) : network(modelPath, threads) {}

PitchTrack FcpeTracker::track(const std::vector<float>& mono, int sampleRate) const
{
    if (sampleRate <= 0)
        throw std::invalid_argument("FcpeTracker: sample rate must be positive");
    PitchTrack out;
    // Leave 5% headroom, as the Python wrapper does (FCPE expects samples within +-1).
    std::vector<float> audio = mono;
    float peak = 0.0f;
    for (float v : audio)
        peak = std::max(peak, std::abs(v));
    if (peak > 0.95f)
    {
        const auto gain = static_cast<float>(0.95 / static_cast<double>(peak));
        for (float& v : audio)
            v *= gain;
    }

    const auto audio16k = fcpe::resample(audio, sampleRate, kModelSampleRate);
    std::size_t melFrames = 0;
    auto mel = fcpe::logMel(audio16k, melFrames);
    // torchfcpe counts frames from the *original* length in units of the 16 kHz hop, then
    // adds one copy of the last frame if that's more than it has (or cuts if fewer).
    const std::size_t wanted = audio.size() / kHop + 1;
    if (wanted > melFrames && melFrames > 0)
    {
        // Copy first: inserting a vector's own elements can invalidate the source.
        const std::vector<float> last(mel.end() - static_cast<std::ptrdiff_t>(kMelBands), mel.end());
        mel.insert(mel.end(), last.begin(), last.end());
        ++melFrames;
    }
    else if (wanted < melFrames)
    {
        melFrames = wanted;
        mel.resize(melFrames * kMelBands);
    }

    out.f0Hz = fcpe::decode(network.latent(mel, melFrames), melFrames, kThreshold);
    for (float& f : out.f0Hz)
    {
        f = std::min(f, kMaxHz);
        if (f < kMinHz)
            f = 0.0f;
    }
    return out;
}

} // namespace clay::analysis
