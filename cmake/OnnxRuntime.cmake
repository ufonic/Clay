# ONNX Runtime prebuilt binaries (runs FCPE's pitch network; docs/decisions.md 2026-10-11).
# 1.23.2 is the newest release with an Intel/universal macOS build. Downloaded at configure
# time and checked against the SHA-256 GitHub publishes for each file.
#
# Defines the imported target onnxruntime::onnxruntime (a shared library) and
# clay_copy_onnxruntime(<target>), which copies the runtime next to an executable so it
# runs from the build tree.

include(FetchContent)

set(CLAY_ORT_VERSION 1.23.2)
set(_ort_base "https://github.com/microsoft/onnxruntime/releases/download/v${CLAY_ORT_VERSION}")
if(WIN32)
    set(_ort_url "${_ort_base}/onnxruntime-win-x64-${CLAY_ORT_VERSION}.zip")
    set(_ort_hash 0b38df9af21834e41e73d602d90db5cb06dbd1ca618948b8f1d66d607ac9f3cd)
elseif(APPLE)
    set(_ort_url "${_ort_base}/onnxruntime-osx-universal2-${CLAY_ORT_VERSION}.tgz")
    set(_ort_hash 49ae8e3a66ccb18d98ad3fe7f5906b6d7887df8a5edd40f49eb2b14e20885809)
else()
    message(FATAL_ERROR "Clay builds on Windows and macOS only")
endif()

FetchContent_Declare(onnxruntime_prebuilt
    URL "${_ort_url}"
    URL_HASH SHA256=${_ort_hash}
    DOWNLOAD_EXTRACT_TIMESTAMP ON
)
FetchContent_MakeAvailable(onnxruntime_prebuilt)
set(_ort_dir "${onnxruntime_prebuilt_SOURCE_DIR}")

add_library(onnxruntime::onnxruntime SHARED IMPORTED GLOBAL)
set_target_properties(onnxruntime::onnxruntime PROPERTIES
    INTERFACE_INCLUDE_DIRECTORIES "${_ort_dir}/include"
)
# Mark the headers as system headers so our warnings-as-errors don't apply to them.
set_property(TARGET onnxruntime::onnxruntime PROPERTY
    INTERFACE_SYSTEM_INCLUDE_DIRECTORIES "${_ort_dir}/include")
if(WIN32)
    set_target_properties(onnxruntime::onnxruntime PROPERTIES
        IMPORTED_LOCATION "${_ort_dir}/lib/onnxruntime.dll"
        IMPORTED_IMPLIB "${_ort_dir}/lib/onnxruntime.lib"
    )
else()
    set_target_properties(onnxruntime::onnxruntime PROPERTIES
        IMPORTED_LOCATION "${_ort_dir}/lib/libonnxruntime.${CLAY_ORT_VERSION}.dylib"
        IMPORTED_SONAME "@rpath/libonnxruntime.${CLAY_ORT_VERSION}.dylib"
    )
endif()

# Windows looks for DLLs next to the .exe first (before System32, which ships its own,
# older onnxruntime.dll), so copy ours there. macOS finds it through the build RPATH.
function(clay_copy_onnxruntime target)
    if(WIN32)
        add_custom_command(TARGET ${target} POST_BUILD
            COMMAND ${CMAKE_COMMAND} -E copy_if_different
                $<TARGET_FILE:onnxruntime::onnxruntime> $<TARGET_FILE_DIR:${target}>
            VERBATIM)
    endif()
endfunction()
