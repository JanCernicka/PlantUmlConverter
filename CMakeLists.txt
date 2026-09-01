cmake_minimum_required(VERSION 3.16)
project(PlantUmlConverter CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

add_executable(plantumlconverter
    src/main.cpp
    src/lexer.cpp
)
target_include_directories(plantumlconverter PRIVATE src)
