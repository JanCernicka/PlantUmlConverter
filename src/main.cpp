#include <cstdlib>
#include <fstream>
#include <sstream>
#include <string>

#include <spdlog/spdlog.h>

#include "lexer.h"

namespace {

// Applies the log level from the SPDLOG_LEVEL environment variable. Accepted
// values are trace, debug, info, warn, error, critical and off. Unset or empty
// keeps the default (info); an unrecognised value is reported and ignored.
void configure_log_level() {
    spdlog::set_level(spdlog::level::info);

    const char* value = std::getenv("SPDLOG_LEVEL");
    if (value == nullptr || *value == '\0') {
        return;
    }

    const spdlog::level::level_enum level = spdlog::level::from_str(value);
    // from_str maps unknown names to off, so distinguish a real "off".
    if (level == spdlog::level::off && std::string(value) != "off") {
        spdlog::warn("unknown SPDLOG_LEVEL '{}', using info", value);
        return;
    }
    spdlog::set_level(level);
}

}  // namespace

int main(int argc, char** argv) {
    configure_log_level();

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
