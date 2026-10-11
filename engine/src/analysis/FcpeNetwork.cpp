#include "clay/analysis/FcpeNetwork.h"

#include <array>
#include <cstdint>
#include <onnxruntime_cxx_api.h>
#include <stdexcept>
#include <string>

namespace clay::analysis
{

struct FcpeNetwork::Impl
{
    Ort::Env env{ORT_LOGGING_LEVEL_WARNING, "clay-fcpe"};
    Ort::Session session{nullptr};
};

FcpeNetwork::FcpeNetwork(const std::filesystem::path& modelPath, int threads) : impl(std::make_unique<Impl>())
{
    try
    {
        Ort::SessionOptions options;
        options.SetIntraOpNumThreads(threads);
        options.SetGraphOptimizationLevel(ORT_ENABLE_ALL);
        // path::c_str() is wchar_t on Windows and char on macOS, matching ORTCHAR_T.
        impl->session = Ort::Session(impl->env, modelPath.c_str(), options);
    }
    catch (const Ort::Exception& e)
    {
        throw std::runtime_error("could not load FCPE model " + modelPath.string() + ": " + e.what());
    }
}

FcpeNetwork::~FcpeNetwork() = default;

std::vector<float> FcpeNetwork::latent(const std::vector<float>& mel, std::size_t frames) const
{
    if (mel.size() != frames * kMelBands)
        throw std::invalid_argument("FcpeNetwork: mel must hold frames x 128 values");
    if (frames == 0)
        return {};
    try
    {
        const auto memory = Ort::MemoryInfo::CreateCpu(OrtArenaAllocator, OrtMemTypeDefault);
        const std::array<std::int64_t, 3> shape{1, static_cast<std::int64_t>(frames),
                                                static_cast<std::int64_t>(kMelBands)};
        // ONNX Runtime reads the input buffer without changing it; the API wants non-const.
        auto input = Ort::Value::CreateTensor<float>(memory, const_cast<float*>(mel.data()), mel.size(),
                                                     shape.data(), shape.size());
        const char* inputNames[] = {"mel"};
        const char* outputNames[] = {"latent"};
        auto outputs = impl->session.Run(Ort::RunOptions{nullptr}, inputNames, &input, 1, outputNames, 1);
        const float* data = outputs.front().GetTensorData<float>();
        return std::vector<float>(data, data + frames * kPitchBins);
    }
    catch (const Ort::Exception& e)
    {
        throw std::runtime_error(std::string("FCPE network failed: ") + e.what());
    }
}

} // namespace clay::analysis
