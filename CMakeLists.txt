cmake_minimum_required(VERSION 3.16)
project(PlantUmlConverter CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

include(FetchContent)
FetchContent_Declare(
    spdlog
    GIT_REPOSITORY https://github.com/gabime/spdlog.git
    GIT_TAG        v1.15.3
    GIT_SHALLOW    TRUE
)
FetchContent_MakeAvailable(spdlog)

add_executable(plantumlconverter
    src/main.cpp
    src/lexer.cpp
)
target_include_directories(plantumlconverter PRIVATE src)
target_link_libraries(plantumlconverter PRIVATE spdlog::spdlog)
