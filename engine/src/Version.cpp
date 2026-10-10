#include "clay/engine/Version.h"

#include "clay/engine/BuildInfo.h"

namespace clay::engine
{
Version version() noexcept
{
    return {detail::versionMajor, detail::versionMinor, detail::versionPatch};
}

std::string_view versionString() noexcept
{
    return detail::versionString;
}
} // namespace clay::engine
