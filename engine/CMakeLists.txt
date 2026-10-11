configure_file(src/BuildInfo.h.in "${CMAKE_CURRENT_BINARY_DIR}/generated/clay/engine/BuildInfo.h" @ONLY)

# Core engine: note model, Transfer buffer. Linked by the plugin.
add_library(clay_engine STATIC
    src/NoteModel.cpp
    src/TransferBuffer.cpp
    src/Version.cpp
)
add_library(clay::engine ALIAS clay_engine)

target_include_directories(clay_engine
    PUBLIC
        include
        "${CMAKE_CURRENT_BINARY_DIR}/generated"
)
# JSON is an implementation detail of the note model's file format.
target_link_libraries(clay_engine PRIVATE nlohmann_json::nlohmann_json)
clay_set_warnings(clay_engine)

# Analysis (pitch tracking, note detection). Separate because it needs the ONNX Runtime
# shared library, which the plugin can't load from a DAW's plugin folder yet; the plugin
# links it once that's solved (Phase 3).
add_library(clay_analysis STATIC
    src/analysis/Fcpe.cpp
    src/analysis/FcpeNetwork.cpp
)
add_library(clay::analysis ALIAS clay_analysis)
target_link_libraries(clay_analysis PUBLIC clay::engine PRIVATE onnxruntime::onnxruntime PFFFT::PFFFT)
clay_set_warnings(clay_analysis)

if(CLAY_BUILD_TESTS)
    # Command-line tools for parity checks on real datasets (driven from research/).
    add_executable(clay_fcpe tools/clay_fcpe.cpp)
    target_link_libraries(clay_fcpe PRIVATE clay::analysis)
    clay_set_warnings(clay_fcpe)
    clay_copy_onnxruntime(clay_fcpe)

    add_executable(clay_engine_tests
        tests/FcpeNetworkTests.cpp
        tests/FcpeTests.cpp
        tests/NoteModelTests.cpp
        tests/TransferBufferTests.cpp
        tests/VersionTests.cpp
    )
    target_link_libraries(clay_engine_tests PRIVATE
        clay::engine clay::analysis nlohmann_json::nlohmann_json Catch2::Catch2WithMain)
    # Parity fixtures written by research/ (clay_research.parity.*), committed to the repo.
    target_compile_definitions(clay_engine_tests PRIVATE
        CLAY_FIXTURES_DIR="${CMAKE_CURRENT_SOURCE_DIR}/tests/fixtures"
        CLAY_MODELS_DIR="${CMAKE_CURRENT_SOURCE_DIR}/models")
    clay_set_warnings(clay_engine_tests)
    clay_copy_onnxruntime(clay_engine_tests)
    # PRE_TEST: discover tests when ctest runs, not at build time, so cross-built
    # slices of the universal binary don't have to execute during the build.
    catch_discover_tests(clay_engine_tests DISCOVERY_MODE PRE_TEST)
endif()
