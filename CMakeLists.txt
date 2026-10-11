cmake_minimum_required(VERSION 3.25)

# macOS: universal binary; minimum macOS matches the owner's 2017 MacBook Pro (Ventura).
# Set before project() so every target picks them up; presets may override.
set(CMAKE_OSX_DEPLOYMENT_TARGET "13.0" CACHE STRING "Minimum macOS version")

project(Clay VERSION 0.0.1 LANGUAGES C CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)

option(CLAY_BUILD_TESTS "Build unit tests" ON)
option(CLAY_BUILD_PLUGIN "Build the JUCE plugin and standalone app" ON)
option(CLAY_WARNINGS_AS_ERRORS "Treat compiler warnings as errors (on in CI)" OFF)

# Warning flags for Clay's own targets only (never third-party code).
function(clay_set_warnings target)
    if(MSVC)
        target_compile_options(${target} PRIVATE /W4 /permissive- /utf-8)
        if(CLAY_WARNINGS_AS_ERRORS)
            target_compile_options(${target} PRIVATE /WX)
        endif()
    else()
        target_compile_options(${target} PRIVATE -Wall -Wextra -Wpedantic -Wshadow -Wconversion)
        if(CLAY_WARNINGS_AS_ERRORS)
            target_compile_options(${target} PRIVATE -Werror)
        endif()
    endif()
endfunction()

if(CLAY_BUILD_TESTS)
    enable_testing()
    add_subdirectory(third_party/Catch2 EXCLUDE_FROM_ALL)
    list(APPEND CMAKE_MODULE_PATH "${Catch2_SOURCE_DIR}/extras")
    include(Catch)
endif()

# nlohmann/json (MIT, header-only): reads/writes note model files. SYSTEM keeps its
# headers out of our warnings-as-errors.
set(JSON_Install OFF CACHE INTERNAL "")
add_subdirectory(third_party/nlohmann_json EXCLUDE_FROM_ALL SYSTEM)

add_subdirectory(engine)

if(CLAY_BUILD_PLUGIN)
    add_subdirectory(third_party/JUCE EXCLUDE_FROM_ALL)
    add_subdirectory(third_party/clap-juce-extensions EXCLUDE_FROM_ALL)
    add_subdirectory(plugin)
endif()
