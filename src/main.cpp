#include <fstream>
#include <sstream>
#include <string>

#include <spdlog/spdlog.h>

#include "lexer.h"

int main(int argc, char** argv) {
    spdlog::set_level(spdlog::level::debug);

    if (argc != 2) {
        spdlog::error("usage: plantumlconverter <file.plantuml>");
        return 1;
    }

    const std::string path = argv[1];
    std::ifstream input(path);
    if (!input) {
        spdlog::error("cannot open '{}'", path);
        return 1;
    }
    spdlog::info("opened '{}'", path);

    std::ostringstream buffer;
    buffer << input.rdbuf();
    if (input.bad()) {
        spdlog::error("failed while reading '{}'", path);
        return 1;
    }

    const std::string source = buffer.str();
    spdlog::info("read {} symbols from '{}'", source.size(), path);

    const plantuml::Lexer lexer(source);
    const std::vector<plantuml::Token> tokens = lexer.tokenize();

    return 0;
}
